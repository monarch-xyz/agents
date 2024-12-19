from dataclasses import dataclass
from typing import Union


@dataclass
class TokenAmount:
    """
    Safe handling of token amounts with high precision integer arithmetic.
    All amounts are stored as raw integers (wei).
    """
    raw: int  # Amount in smallest unit (wei)
    decimals: int  # Token decimals (usually 18)
    
    @classmethod
    def from_wei(cls, wei_amount: Union[int, str], decimals: int = 18) -> 'TokenAmount':
        """Create from wei amount"""
        return cls(raw=int(wei_amount), decimals=decimals)
    
    @classmethod
    def from_units(cls, amount: Union[int, float, str], decimals: int = 18) -> 'TokenAmount':
        """Create from human readable units (e.g., ETH instead of wei)"""
        scaled = float(amount) * (10 ** decimals)
        return cls(raw=int(scaled), decimals=decimals)
    
    def __add__(self, other: 'TokenAmount') -> 'TokenAmount':
        assert self.decimals == other.decimals, "Cannot add tokens with different decimals"
        return TokenAmount(raw=self.raw + other.raw, decimals=self.decimals)
    
    def __sub__(self, other: 'TokenAmount') -> 'TokenAmount':
        assert self.decimals == other.decimals, "Cannot subtract tokens with different decimals"
        return TokenAmount(raw=self.raw - other.raw, decimals=self.decimals)
    
    def __lt__(self, other: 'TokenAmount') -> bool:
        assert self.decimals == other.decimals, "Cannot compare tokens with different decimals"
        return self.raw < other.raw
    
    def __le__(self, other: 'TokenAmount') -> bool:
        assert self.decimals == other.decimals, "Cannot compare tokens with different decimals"
        return self.raw <= other.raw
    
    def __gt__(self, other: 'TokenAmount') -> bool:
        assert self.decimals == other.decimals, "Cannot compare tokens with different decimals"
        return self.raw > other.raw
    
    def __ge__(self, other: 'TokenAmount') -> bool:
        assert self.decimals == other.decimals, "Cannot compare tokens with different decimals"
        return self.raw >= other.raw
    
    def to_units(self, precision: int = 18) -> str:
        """Convert to human readable units with specified decimal precision"""
        units = self.raw / (10 ** self.decimals)
        return f"{units:.{precision}f}"
    
    def to_wei(self) -> int:
        """Get raw wei amount"""
        return self.raw
