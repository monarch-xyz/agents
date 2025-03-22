from decimal import Decimal
from typing import List, Dict, Optional, Any, Literal, Union
from pydantic import BaseModel, Field

class Asset(BaseModel):
    id: str
    symbol: Optional[str] = None
    decimals: Optional[int] = None
    name: Optional[str] = None

class Rate(BaseModel):
    id: str
    side: Literal["BORROWER", "LENDER"]
    rate: str

class Market(BaseModel):
    id: str
    totalSupplyShares: str
    totalSupply: str
    totalBorrowShares: str
    totalBorrow: str
    rates: Optional[List[Rate]] = Field(default_factory=list)
    
    def get_borrow_rate(self) -> str:
        """Get the borrow rate from rates list"""
        for rate in self.rates or []:
            if rate.side == "BORROWER":
                return rate.rate
        return "0"
    
    def get_supply_rate(self) -> str:
        """Get the supply rate from rates list"""
        for rate in self.rates or []:
            if rate.side == "LENDER":
                return rate.rate
        return "0"

class Position(BaseModel):
    side: Literal["SUPPLIER", "BORROWER", "COLLATERAL"]
    shares: Optional[str] = "0"
    asset: Asset
    market: Market
    
    def get_amount(self) -> Decimal:
        """Calculate the actual amount based on shares and market data"""
        shares_value = self.shares or "0"
        
        if self.side == "SUPPLIER" and self.market.totalSupplyShares != "0":
            return (Decimal(shares_value) * Decimal(self.market.totalSupply)) / Decimal(self.market.totalSupplyShares)
        elif self.side == "BORROWER" and self.market.totalBorrowShares != "0":
            return (Decimal(shares_value) * Decimal(self.market.totalBorrow)) / Decimal(self.market.totalBorrowShares)
        return Decimal('0')

class UserPositionsSubgraph(BaseModel):
    positions: List[Position] = Field(default_factory=list)
    
    @classmethod
    def from_graphql(cls, data: Dict[str, Any]) -> 'UserPositionsSubgraph':
        """Create UserPositionsSubgraph instance from GraphQL response"""
        if not data or "account" not in data or not data["account"]:
            return cls(positions=[])
        
        all_positions = []
        
        # Add supplier positions
        if data["account"].get("supplierPositions"):
            for pos in data["account"]["supplierPositions"]:
                if pos.get("shares") is None:
                    pos["shares"] = "0"
                all_positions.append(pos)
        
        # Add borrower positions
        if data["account"].get("borrowerPositions"):
            for pos in data["account"]["borrowerPositions"]:
                if pos.get("shares") is None:
                    pos["shares"] = "0"
                all_positions.append(pos)
        
        return cls(positions=all_positions) 