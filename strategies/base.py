from dataclasses import dataclass
from typing import List, Dict, Optional, TypedDict, Any
from collections import defaultdict
import logging
import os
import json
from web3 import Web3
from models.morpho_data import MarketPosition, Market, Asset
from models.user_data import MarketCap
from utils.token_amount import TokenAmount
from config.contracts import MORPHO_BLUE_ADDRESS, MORPHO_BLUE_ABI_PATH
from config.networks import get_rpc_url, get_morpho_blue_address


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
        decimals = market.loan_asset.decimals
        
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
            # Create TokenAmount for the move_amount
            amount_token = TokenAmount.from_wei(move_amount, decimals)
            return cls(
                market_id=market_id,
                action_type='withdraw',
                amount=amount_token,
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
    """A typed dictionary for grouped positions by loan token"""
    loan_token: Asset  # The loan token asset
    total_asset: TokenAmount  # Total amount in native token units
    markets: List[MarketPosition]  # List of positions in this token


class BaseStrategy:
    """Base class for all reallocation strategies"""
    
    def __init__(self, chain_id: int):
        """Initialize Web3 and Morpho Blue contract instance for the given chain."""
        self.chain_id = chain_id
        logger.info(f"Initializing BaseStrategy for chain ID: {self.chain_id}")

        # Get RPC URL and Morpho Blue address from config
        provider_url = get_rpc_url(self.chain_id)
        morpho_blue_address = get_morpho_blue_address(self.chain_id)
        logger.info(f"[{self.chain_id}] Strategy using RPC URL ending with ...{provider_url[-10:]}")
        logger.info(f"[{self.chain_id}] Strategy using Morpho Blue address: {morpho_blue_address}")

        # Check if PoA middleware is needed (can check config or assume based on chain ID)
        # For simplicity here, we don't inject it as BlockchainClient handles connections
        # but if strategy needs direct non-read calls, this might need adjustment.
        self.w3 = Web3(Web3.HTTPProvider(provider_url))
        if not self.w3.is_connected():
             raise ConnectionError(f"BaseStrategy failed to connect to Web3 provider for chain {self.chain_id}")
        logger.info(f"[{self.chain_id}] BaseStrategy connected to Web3 provider.")

        try:
            with open(MORPHO_BLUE_ABI_PATH) as f:
                morpho_blue_abi = json.load(f)
        except FileNotFoundError:
             logger.error(f"Morpho Blue ABI file not found at: {MORPHO_BLUE_ABI_PATH}")
             raise
        except json.JSONDecodeError:
             logger.error(f"Error decoding JSON from Morpho Blue ABI file: {MORPHO_BLUE_ABI_PATH}")
             raise

        self.morpho_blue_contract = self.w3.eth.contract(
            address=Web3.to_checksum_address(morpho_blue_address),
            abi=morpho_blue_abi
        )

        logger.info(f"[{self.chain_id}] Initialized Morpho Blue contract reader in BaseStrategy")
    
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
        
        # Use a dict for grouping since we can't use defaultdict with TypedDict
        grouped_by_token: Dict[str, GroupedPosition] = {}
        
        for pos in positions:
            market = markets.get(pos.unique_key)
            if not market:
                logger.warning(f'[{self.chain_id}] Market not found for position {pos.unique_key}')
                continue
                
            token = market.loan_asset
            if not token:
                logger.warning(f'[{self.chain_id}] Invalid loan asset data for market {pos.unique_key}')
                continue
                
            token_addr = token.address
            decimals = token.decimals

            supply_amount = TokenAmount.from_wei(pos.state.supply_assets, decimals)
                
            if token_addr not in grouped_by_token:
                # Create a new GroupedPosition
                grouped_by_token[token_addr] = {
                    'loan_token': token,
                    'total_asset': TokenAmount.from_wei(0, decimals),
                    'markets': []
                }
                
            # Add to existing group
            grouped_position = grouped_by_token[token_addr]
            # Update the total asset
            grouped_position['total_asset'] += supply_amount
            # Add to markets list
            grouped_position['markets'].append(pos)
            
        result = list(grouped_by_token.values())

        logger.info(f"[{self.chain_id}] User has {len(result)} grouped positions by loan asset")
        # Optional detailed logging
        # for group in result:
        #     token = group['loan_token']
        #     logger.info(
        #         f"  - {token.symbol}: "
        #         f'{group["total_asset"].to_units()} tokens across {len(group["markets"])} markets'
        #     )
            
        return result
    
    def filter_available_markets(
        self,
        loan_token_addr: str,
        markets: Dict[str, Market]
    ) -> List[Market]:
        """
        Filter markets by loan token address.
        (Removed TVL filter for simplicity, can be added back if needed)
        
        Args:
            loan_token_addr: Token address to filter by
            markets: Dictionary of markets by uniqueKey
            
        Returns:
            List of available markets sorted by APY (highest first)
        """
        available = []

        for market in markets.values():
            if market.loan_asset and market.loan_asset.address == loan_token_addr:
                available.append(market)
                
        # Sort by APY (highest first), handle potential None or non-float APYs
        def get_sort_key(m: Market):
             try:
                 return float(m.state.supply_apy) if m.state and m.state.supply_apy is not None else -1.0
             except (ValueError, TypeError):
                 return -1.0 # Treat errors/non-numeric as lowest APY

        return sorted(available, key=get_sort_key, reverse=True)
    
    def get_market_liquidity(self, market_id: str) -> int:
        """Get available liquidity for a market directly from the contract
        
        Args:
            market_id: Market unique key
            
        Returns:
            Available liquidity in wei
        """
        try:
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
            
            logger.debug(f"[{self.chain_id}] Market liquidity from contract ({market_id[:10]}...): {liquidity}")
            return liquidity
        except Exception as e:
             logger.error(f"[{self.chain_id}] Failed to get market liquidity from contract for {market_id}: {e}")
             # Decide how to handle contract call errors - return 0 or raise?
             return 0 # Return 0 liquidity on error
    
    def calculate_reallocation(
        self,
        positions: List[MarketPosition],
        market_caps: List[MarketCap],
        market_data: Optional[Dict[str, Market]] = None
    ) -> ReallocationStrategy:
        """Calculate reallocation strategy based on current positions and caps"""
        raise NotImplementedError("Subclasses must implement calculate_reallocation")
