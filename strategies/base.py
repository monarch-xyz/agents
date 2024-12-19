from dataclasses import dataclass
from typing import List, Dict, Optional, TypedDict
from collections import defaultdict
import logging
from web3 import Web3
from eth_typing import Wei
from models.morpho_data import MarketPosition, Market
from models.user_data import MarketCap


logger = logging.getLogger(__name__)


@dataclass
class MarketAction:
    market_id: str  # uniqueKey of the market
    action_type: str  # 'supply' or 'withdraw'
    amount: Wei  # Amount in native token units (Wei)
    current_position: MarketPosition
    target_cap: Optional[MarketCap] = None


@dataclass
class ReallocationStrategy:
    """Strategy for reallocating positions based on market caps"""
    actions: List[MarketAction]
    total_reallocation_value: Wei  # Total amount in native token units (Wei)


class GroupedPosition(TypedDict):
    loan_token: Dict  # Full token data including address and symbol
    total_asset: Wei  # Total amount in native token units (Wei)
    markets: List[MarketPosition]


class BaseStrategy:
    """Base class for all reallocation strategies"""
    
    def process_positions(
        self,
        positions: List[MarketPosition],
        markets: Dict[str, Market],
        min_asset: Wei = Web3.to_wei(1, 'ether')  # Minimum amount to consider (filter dust)
    ) -> List[GroupedPosition]:
        """
        Group positions by loan token address
        
        Args:
            positions: List of market positions
            markets: Dictionary of markets by uniqueKey
            min_asset: Minimum asset amount to consider (default: 1 token)
            
        Returns:
            List of grouped positions by loan token
        """
        logger.info(f'Processing {len(positions)} positions across {len(markets)} markets')
        
        # Group positions by loan token address
        grouped = defaultdict(lambda: {
            'loan_token': {},
            'total_asset': Wei(0),
            'markets': []
        })
        
        for pos in positions:
            # Skip dust positions
            supply_amount = Wei(int(pos.supply_asset))
            if supply_amount <= min_asset:
                logger.info(f'Skipping dust position {pos.unique_key} (amount: {Web3.from_wei(supply_amount, "ether")})')
                continue
                
            market = markets.get(pos.unique_key)
            if not market:
                logger.warning(f'Market not found for position {pos.unique_key}')
                continue
                
            token = market.loan_asset
            if not token or 'address' not in token:
                logger.warning(f'Invalid loan asset data for market {pos.unique_key}: {token}')
                continue
                
            token_addr = token['address']
            
            if not grouped[token_addr]['loan_token']:
                grouped[token_addr]['loan_token'] = token
                
            grouped[token_addr]['total_asset'] = Wei(int(grouped[token_addr]['total_asset']) + int(supply_amount))
            grouped[token_addr]['markets'].append(pos)
            
        result = list(grouped.values())
        logger.info(f'Grouped into {len(result)} token groups:')
        for group in result:
            token = group['loan_token']
            total = Web3.from_wei(group['total_asset'], 'ether')
            logger.info(
                f'- {token.get("symbol", "Unknown")} ({token.get("address", "Unknown")}): '
                f'{total:.18f} tokens across {len(group["markets"])} markets'
            )
            
        return result
    
    def filter_available_markets(
        self,
        loan_token_addr: str,
        markets: Dict[str, Market],
        min_tvl_asset: Wei = Web3.to_wei(1000, 'ether')  # 1000 tokens minimum TVL
    ) -> List[Market]:
        """
        Filter markets by loan token address and minimum TVL
        
        Args:
            loan_token_addr: Token address to filter by
            markets: Dictionary of markets by uniqueKey
            min_tvl_asset: Minimum TVL in native token units (Wei)
            
        Returns:
            List of available markets sorted by APY (highest first)
        """
        available = []
        
        for market in markets.values():
            supply_assets = Wei(int(market.state['supplyAssets']))
            if (
                market.loan_asset['address'] == loan_token_addr and
                supply_assets >= min_tvl_asset
            ):
                available.append(market)
                
        # Sort by APY (highest first)
        return sorted(
            available,
            key=lambda m: float(m.state['supplyApy']),
            reverse=True
        )
    
    def calculate_reallocation(
        self,
        positions: List[MarketPosition],
        market_caps: List[MarketCap],
        market_data: Optional[Dict[str, Market]] = None
    ) -> ReallocationStrategy:
        """Calculate reallocation strategy based on current positions and caps"""
        raise NotImplementedError("Subclasses must implement calculate_reallocation")
