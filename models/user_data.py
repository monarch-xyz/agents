from dataclasses import dataclass
from typing import List
from decimal import Decimal

@dataclass
class MarketCap:
    market_id: str
    cap: Decimal

@dataclass
class UserAuthorization:
    address: str
    market_caps: List[MarketCap]

    @classmethod
    def from_graphql(cls, data: dict) -> 'UserAuthorization':
        """Create UserAuthorization from GraphQL response data"""
        market_caps = [
            MarketCap(
                market_id=cap['marketId'].replace('\\x', '0x'),  # Clean up the market ID format
                cap=Decimal(cap['cap'])
            )
            for cap in data['marketCaps']['nodes']
        ]
        
        return cls(
            address=data['id'],
            market_caps=market_caps
        )
