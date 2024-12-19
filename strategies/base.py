from dataclasses import dataclass
from typing import List, Dict, Optional, TypedDict
from collections import defaultdict
import logging
from models.morpho_data import MarketPosition, Market
from models.user_data import MarketCap
from utils.token_amount import TokenAmount


logger = logging.getLogger(__name__)


@dataclass
class MarketAction:
    market_id: str  # uniqueKey of the market
    action_type: str  # 'supply' or 'withdraw'
    amount: TokenAmount  # Amount in native token units
    current_position: MarketPosition
    target_cap: Optional[MarketCap] = None


@dataclass
class ReallocationStrategy:
    """Strategy for reallocating positions based on market caps"""
    actions: List[MarketAction]
    total_reallocation_value: TokenAmount  # Total amount in native token units


class GroupedPosition(TypedDict):
    loan_token: Dict  # Full token data including address and symbol
    total_asset: TokenAmount  # Total amount in native token units
    markets: List[MarketPosition]


class BaseStrategy:
    """Base class for all reallocation strategies"""
    
    def process_positions(
        self,
        positions: List[MarketPosition],
        markets: Dict[str, Market],
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

            min_asset = TokenAmount.from_units(1, decimals)
            
            # Skip dust positions
            supply_amount = TokenAmount.from_wei(pos.supply_assets, decimals)
            if supply_amount <= min_asset:
                logger.info(f'Skipping dust position {pos.unique_key} (amount: {supply_amount.to_units()})')
                continue
                
            if not grouped[token_addr]['loan_token']:
                grouped[token_addr]['loan_token'] = token
                grouped[token_addr]['total_asset'] = TokenAmount.from_wei(0, decimals)
                
            grouped[token_addr]['total_asset'] += supply_amount
            grouped[token_addr]['markets'].append(pos)
            
        result = list(grouped.values())
        logger.info(f'Grouped into {len(result)} token groups:')
        for group in result:
            token = group['loan_token']
            logger.info(
                f'- {token.get("symbol", "Unknown")} ({token.get("address", "Unknown")}): '
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
            min_tvl_asset: Minimum TVL in native token units
            
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
    
    def calculate_reallocation(
        self,
        positions: List[MarketPosition],
        market_caps: List[MarketCap],
        market_data: Optional[Dict[str, Market]] = None
    ) -> ReallocationStrategy:
        """Calculate reallocation strategy based on current positions and caps"""
        raise NotImplementedError("Subclasses must implement calculate_reallocation")
