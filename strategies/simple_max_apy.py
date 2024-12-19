from decimal import Decimal
from typing import List, Dict, Optional
from models.morpho_data import MarketPosition
from models.user_data import MarketCap
from .base import BaseStrategy, MarketAction, ReallocationStrategy


class SimpleMaxAPYStrategy(BaseStrategy):
    """Simple strategy that reallocates based on market caps and APY"""
    
    def calculate_reallocation(
        self,
        positions: List[MarketPosition],
        market_caps: List[MarketCap],
        market_data: Optional[Dict] = None
    ) -> ReallocationStrategy:
        """
        Calculate reallocation strategy based on current positions and caps
        
        Args:
            positions: List of current market positions
            market_caps: List of market caps set by the user
            market_data: Additional market data (prices, APY, etc.) for future use
            
        Returns:
            ReallocationStrategy with list of actions to take
        """
        actions = []
        total_reallocation_value = Decimal('0')
        
        # Create lookup dictionaries
        positions_by_market = {pos.unique_key: pos for pos in positions}
        caps_by_market = {cap.market_id: cap for cap in market_caps}
        
        # Calculate required actions for each position
        for market_id, position in positions_by_market.items():
            cap = caps_by_market.get(market_id)
            if not cap:
                continue
                
            current_value = position.supply_assets_usd
            target_value = Decimal(str(cap.cap))
            
            if current_value > target_value:
                # Need to withdraw
                withdraw_amount = current_value - target_value
                actions.append(MarketAction(
                    market_id=market_id,
                    action_type='withdraw',
                    amount=withdraw_amount,
                    current_position=position,
                    target_cap=cap
                ))
                total_reallocation_value += withdraw_amount
                
            elif current_value < target_value:
                # Need to supply
                supply_amount = target_value - current_value
                actions.append(MarketAction(
                    market_id=market_id,
                    action_type='supply',
                    amount=supply_amount,
                    current_position=position,
                    target_cap=cap
                ))
                total_reallocation_value += supply_amount
        
        # Sort actions by amount (largest first) for better execution
        actions.sort(key=lambda x: x.amount, reverse=True)
        
        return ReallocationStrategy(
            actions=actions,
            total_reallocation_value=total_reallocation_value
        )
