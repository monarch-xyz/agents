from dataclasses import dataclass
from typing import List, Dict, Optional, TypedDict
from collections import defaultdict
import logging
import os
import json
from web3 import Web3
from web3.contract import Contract
from models.morpho_data import MarketPosition, Market
from models.user_data import MarketCap
from utils.token_amount import TokenAmount
from config.contracts import MORPHO_BLUE_ADDRESS, MORPHO_BLUE_ABI_PATH


logger = logging.getLogger(__name__)


@dataclass
class MarketAction:
    market_id: str  # uniqueKey of the market
    action_type: str  # 'supply' or 'withdraw'
    amount: TokenAmount  # Amount in native token units (0 if using shares)
    shares: TokenAmount  # Share amount for withdrawals
    current_position: MarketPosition
    target_cap: Optional[MarketCap] = None
    
    @classmethod
    def create_withdrawal(
        cls,
        market_id: str,
        position: MarketPosition,
        market: Market,
        move_amount: int,
        use_max_shares: bool = False,
        target_cap: Optional[MarketCap] = None
    ) -> 'MarketAction':
        """Create a withdrawal action with proper amount/share handling"""
        decimals = int(market.loan_asset.get('decimals', 18))
        
        if use_max_shares:
            # Use shares for max withdrawal
            return cls(
                market_id=market_id,
                action_type='withdraw',
                amount=TokenAmount.from_wei(0, decimals),
                shares=TokenAmount.from_wei(position.supply_shares, 0),
                current_position=position,
                target_cap=target_cap
            )
        else:            
            return cls(
                market_id=market_id,
                action_type='withdraw',
                amount=move_amount,
                shares=TokenAmount.from_wei(0, decimals),
                current_position=position,
                target_cap=target_cap
            )
    
    @classmethod
    def create_supply(
        cls,
        market_id: str,
        amount: TokenAmount,
        position: MarketPosition,
        target_cap: Optional[MarketCap] = None
    ) -> 'MarketAction':
        """Create a supply action"""
        return cls(
            market_id=market_id,
            action_type='supply',
            amount=amount,
            shares=TokenAmount.from_wei(0, amount.decimals),
            current_position=position,
            target_cap=target_cap
        )


@dataclass
class ReallocationStrategy:
    """Strategy for reallocating positions based on market caps"""
    actions: List[MarketAction]


class GroupedPosition(TypedDict):
    loan_token: Dict  # Full token data including address and symbol
    total_asset: TokenAmount  # Total amount in native token units
    markets: List[MarketPosition]


class BaseStrategy:
    """Base class for all reallocation strategies"""
    
    def __init__(self):
        """Initialize Web3 contract instance"""
        provider_url = os.getenv('WEB3_PROVIDER_URL')
        if not provider_url:
            raise ValueError("WEB3_PROVIDER_URL environment variable not set")
            
        self.w3 = Web3(Web3.HTTPProvider(provider_url))
        
        # Load Morpho Blue contract
        with open(MORPHO_BLUE_ABI_PATH) as f:
            morpho_blue_abi = json.load(f)
            
        self.morpho_blue_contract = self.w3.eth.contract(
            address=Web3.to_checksum_address(MORPHO_BLUE_ADDRESS),
            abi=morpho_blue_abi
        )
        
        logger.info("Initialized Morpho Blue contract")
    
    def group_positions_by_loan_asset(
        self,
        positions: List[MarketPosition],
        markets: Dict[str, Market],
    ) -> List[GroupedPosition]:
        """
        Group positions by loan token address
        
        Args:
            positions: List of market positions
            markets: Dictionary of markets by uniqueKey
            
        Returns:
            List of grouped positions by loan token
        """
        
        # Group positions by loan token address
        grouped = defaultdict(lambda: {
            'loan_token': {},
            'total_asset': TokenAmount.from_wei(0),
            'markets': []
        })
        
        for pos in positions:
            market = markets.get(pos.unique_key)
            if not market:
                logger.warning(f'Market not found for position {pos.unique_key}')
                continue
                
            token = market.loan_asset
            if not token or 'address' not in token:
                logger.warning(f'Invalid loan asset data for market {pos.unique_key}: {token}')
                continue
                
            token_addr = token['address']
            decimals = int(token.get('decimals', 18))

            supply_amount = TokenAmount.from_wei(pos.supply_assets, decimals)
                
            if not grouped[token_addr]['loan_token']:
                grouped[token_addr]['loan_token'] = token
                grouped[token_addr]['total_asset'] = TokenAmount.from_wei(0, decimals)
                
            grouped[token_addr]['total_asset'] += supply_amount
            grouped[token_addr]['markets'].append(pos)
            
        result = list(grouped.values())

        logger.info("User has {} grouped positions".format(len(result)))
        for group in result:
            token = group['loan_token']
            logger.info(
                f'- {token.get("symbol", "Unknown")}: '
                f'{group["total_asset"].to_units()} tokens across {len(group["markets"])} markets'
            )
            
        return result
    
    def filter_available_markets(
        self,
        loan_token_addr: str,
        markets: Dict[str, Market]
    ) -> List[Market]:
        """
        Filter markets by loan token address and minimum TVL
        
        Args:
            loan_token_addr: Token address to filter by
            markets: Dictionary of markets by uniqueKey
            
        Returns:
            List of available markets sorted by APY (highest first)
        """
        available = []

        min_tvl_asset = int(10_000)
        
        for market in markets.values():
            supply_assets_usd = int(market.state['supplyAssetsUsd'])

            if (
                market.loan_asset['address'] == loan_token_addr and
                supply_assets_usd >= min_tvl_asset
            ):
                available.append(market)
                
        # Sort by APY (highest first)
        return sorted(
            available,
            key=lambda m: float(m.state['supplyApy']),
            reverse=True
        )
    
    def get_market_liquidity(self, market_id: str) -> int:
        """Get available liquidity for a market directly from the contract
        
        Args:
            market_id: Market unique key
            
        Returns:
            Available liquidity in wei
        """
        # Get market state from contract
        market_state = self.morpho_blue_contract.functions.market(market_id).call()
        
        # Market state returns:
        # - totalSupplyAssets (uint128)
        # - totalSupplyShares (uint128)
        # - totalBorrowAssets (uint128)
        # - totalBorrowShares (uint128)
        # - lastUpdate (uint128)
        # - fee (uint128)
        total_supply = market_state[0]  # totalSupplyAssets
        total_borrow = market_state[2]  # totalBorrowAssets
        
        # Available liquidity is supply - borrow
        liquidity = total_supply - total_borrow
        
        logger.debug(f"Market liquidity from contract ({market_id}): {liquidity}")
        return liquidity
    
    def calculate_reallocation(
        self,
        positions: List[MarketPosition],
        market_caps: List[MarketCap],
        market_data: Optional[Dict[str, Market]] = None
    ) -> ReallocationStrategy:
        """Calculate reallocation strategy based on current positions and caps"""
        raise NotImplementedError("Subclasses must implement calculate_reallocation")
