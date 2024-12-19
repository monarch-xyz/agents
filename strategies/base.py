from dataclasses import dataclass
from decimal import Decimal
from typing import List, Dict, Optional
from models.morpho_data import MarketPosition
from models.user_data import MarketCap


@dataclass
class MarketAction:
    market_id: str  # uniqueKey of the market
    action_type: str  # 'supply' or 'withdraw'
    amount: Decimal
    current_position: MarketPosition
    target_cap: MarketCap


@dataclass
class ReallocationStrategy:
    """Strategy for reallocating positions based on market caps"""
    actions: List[MarketAction]
    total_reallocation_value: Decimal


class BaseStrategy:
    """Base class for all reallocation strategies"""
    
    def calculate_reallocation(
        self,
        positions: List[MarketPosition],
        market_caps: List[MarketCap],
        market_data: Optional[Dict] = None
    ) -> ReallocationStrategy:
        """Calculate reallocation strategy based on current positions and caps"""
        raise NotImplementedError("Subclasses must implement calculate_reallocation")
