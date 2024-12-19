import logging
from typing import List, Dict, Optional
from models.morpho_data import MarketPosition, Market
from models.user_data import MarketCap
from utils.token_amount import TokenAmount
from .base import BaseStrategy, MarketAction, ReallocationStrategy

logger = logging.getLogger(__name__)

class SimpleMaxAPYStrategy(BaseStrategy):
    """Simple strategy that reallocates based on market caps and APY"""
    
    def calculate_reallocation(
        self,
        positions: List[MarketPosition],
        market_caps: List[MarketCap],
        market_data: Optional[Dict[str, Market]] = None
    ) -> ReallocationStrategy:
        """
        Calculate reallocation strategy based on current positions and caps
        
        Args:
            positions: List of current market positions
            market_caps: List of market caps set by the user
            market_data: Dictionary of markets by uniqueKey
            
        Returns:
            ReallocationStrategy with list of actions to take
        """
        if not market_data:
            return ReallocationStrategy(actions=[], total_reallocation_value=TokenAmount.from_wei(0))
            
        # Step 1: Group positions by loan token
        grouped_positions = self.process_positions(positions, market_data)
        
        # Fix market cap IDs (remove leading //)
        fixed_caps = []
        for cap in market_caps:
            if cap.market_id.startswith('//'):
                cap.market_id = '0x' + cap.market_id[2:]
            fixed_caps.append(cap)
            
        caps_by_market = {cap.market_id: cap for cap in fixed_caps}
        actions = []
        total_asset = None  # Will be initialized with first token
        
        # Process each token group
        for group in grouped_positions:
            token = group['loan_token']
            token_addr = token['address']
            symbol = token['symbol']
            decimals = int(token.get('decimals', 18))
            
            logger.info(f"\nProcessing {symbol} positions (token: {token_addr}):")
            
            # Get available markets for this token
            available_markets = self.filter_available_markets(token_addr, market_data)
            if not available_markets:
                logger.info(f"No available markets for {symbol}")
                continue
                
            # Find best market (highest APY) that has a cap
            best_market = None
            for market in available_markets:
                if market.unique_key in caps_by_market:
                    best_market = market
                    break
                    
            if not best_market:
                logger.info(f"No capped markets available for {symbol}")
                continue
                
            best_cap = caps_by_market[best_market.unique_key]
            best_apy = float(best_market.state['supplyApy'])
            
            # Check each position for potential reallocation
            for pos in group['markets']:
                market = market_data.get(pos.unique_key)
                if not market:
                    continue
                    
                current_apy = float(market.state['supplyApy'])
                
                # If current market has lower APY, consider moving funds
                if current_apy < best_apy and pos.unique_key != best_market.unique_key:
                    amount = TokenAmount.from_wei(pos.supply_assets, decimals)
                    logger.info(
                        f"Move {amount.to_units()} {symbol} from "
                        f"market ({pos.unique_key[:10]})({current_apy:.2%}) to "
                        f"market ({best_market.unique_key[:10]})({best_apy:.2%})"
                    )
                    
                    actions.append(MarketAction(
                        market_id=pos.unique_key,
                        action_type='withdraw',
                        amount=amount,
                        current_position=pos,
                        target_cap=best_cap
                    ))
                    
                    actions.append(MarketAction(
                        market_id=best_market.unique_key,
                        action_type='supply',
                        amount=amount,
                        current_position=pos,
                        target_cap=best_cap
                    ))
                    
                    if total_asset is None:
                        total_asset = amount
                    else:
                        total_asset += amount
        
        return ReallocationStrategy(
            actions=actions,
            total_reallocation_value=total_asset if total_asset else TokenAmount.from_wei(0)
        )
