from dataclasses import dataclass
from typing import Union
from decimal import Decimal, getcontext, ROUND_DOWN
import logging

logger = logging.getLogger(__name__)

# Set precision for decimal calculations
getcontext().prec = 78  # Ethereum's uint256 max value has 78 decimal digits

@dataclass
class TokenAmount:
    """
    Safe handling of token amounts with high precision integer arithmetic.
    All amounts are stored as raw integers (wei).
    
    Security features:
    - Uses Decimal for precise calculations
    - Validates decimals parameter
    - Checks for integer overflow
    - Enforces maximum values
    - Safe conversion from float/string units
    """
    raw: int  # Amount in smallest unit (wei)
    decimals: int  # Token decimals (usually 18)
    
    # Maximum supported values
    MAX_UINT256 = 2**256 - 1
    MIN_DECIMALS = 0
    MAX_DECIMALS = 77  # One less than our precision to avoid overflow
    
    def __post_init__(self):
        """Validate the token amount and decimals after initialization"""
        if not isinstance(self.raw, int):
            raise TypeError("Raw amount must be an integer")
        if not isinstance(self.decimals, int):
            raise TypeError("Decimals must be an integer")
            
        if self.raw < 0:
            raise ValueError("Raw amount cannot be negative")
        if self.raw > self.MAX_UINT256:
            raise ValueError(f"Raw amount exceeds maximum value of {self.MAX_UINT256}")
            
        if self.decimals < self.MIN_DECIMALS:
            raise ValueError(f"Decimals cannot be less than {self.MIN_DECIMALS}")
        if self.decimals > self.MAX_DECIMALS:
            raise ValueError(f"Decimals cannot exceed {self.MAX_DECIMALS}")
    
    @classmethod
    def from_wei(cls, wei_amount: Union[int, str, Decimal], decimals: int = 18) -> 'TokenAmount':
        """Create from wei amount with validation"""
        # Convert input to integer
        try:
            if isinstance(wei_amount, Decimal):
                wei_str = f"{wei_amount:.0f}"
                wei_amount = int(wei_str)
            elif isinstance(wei_amount, str):
                wei_amount = int(wei_amount)
            elif isinstance(wei_amount, float):
                raise TypeError("Float values are not supported to avoid precision loss")
            elif not isinstance(wei_amount, int):
                raise TypeError(f"Cannot convert {type(wei_amount)} to integer")
        except ValueError:
            raise ValueError(f"Invalid wei amount: {wei_amount}")
        
        return cls(raw=wei_amount, decimals=decimals)
    
    @classmethod
    def from_units(cls, amount: Union[int, float, str], decimals: int = 18) -> 'TokenAmount':
        """
        Create from human readable units (e.g., ETH instead of wei).
        Uses Decimal for precise calculation.
        """
        # Convert input to Decimal for precise calculation
        try:
            amount_str = str(amount)
            # Check decimal places in input
            if '.' in amount_str:
                decimal_places = len(amount_str.split('.')[1])
                if decimal_places > decimals:
                    raise ValueError(f"Amount has {decimal_places} decimal places, but token only supports {decimals}")
            
            amount_decimal = Decimal(amount_str)
        except ValueError as e:
            raise e
        except:
            raise ValueError(f"Cannot convert {amount} to Decimal")
            
        # Calculate wei amount using Decimal arithmetic
        scaling_factor = Decimal(10) ** decimals
        wei_decimal = amount_decimal * scaling_factor
        
        # For large numbers, convert to string first to avoid precision issues
        wei_str = f"{wei_decimal:.0f}"
        if '.' in wei_str:
            raise ValueError("Amount results in fractional wei")
            
        # Convert to integer and validate bounds
        try:
            wei_amount = int(wei_str)
        except ValueError:
            raise ValueError(f"Cannot convert {wei_str} to integer")
            
        if wei_amount > cls.MAX_UINT256:
            raise ValueError(f"Amount exceeds maximum value of {cls.MAX_UINT256} wei")
            
        return cls(raw=wei_amount, decimals=decimals)
    
    def _validate_other(self, other: 'TokenAmount', operation: str):
        """Validate another TokenAmount for operations"""
        if not isinstance(other, TokenAmount):
            raise TypeError(f"Cannot {operation} TokenAmount with {type(other)}")
        if self.decimals != other.decimals:
            raise ValueError(
                f"Cannot {operation} tokens with different decimals "
                f"({self.decimals} vs {other.decimals})"
            )
    
    def __add__(self, other: 'TokenAmount') -> 'TokenAmount':
        self._validate_other(other, "add")
        result = self.raw + other.raw
        if result > self.MAX_UINT256:
            raise OverflowError("Addition would exceed maximum value")
        return TokenAmount(raw=result, decimals=self.decimals)
    
    def __sub__(self, other: 'TokenAmount') -> 'TokenAmount':
        self._validate_other(other, "subtract")
        if self.raw < other.raw:
            raise ValueError("Subtraction would result in negative amount")
        return TokenAmount(raw=self.raw - other.raw, decimals=self.decimals)
    
    def __lt__(self, other: 'TokenAmount') -> bool:
        self._validate_other(other, "compare")
        return self.raw < other.raw
    
    def __le__(self, other: 'TokenAmount') -> bool:
        self._validate_other(other, "compare")
        return self.raw <= other.raw
    
    def __gt__(self, other: 'TokenAmount') -> bool:
        self._validate_other(other, "compare")
        return self.raw > other.raw
    
    def __ge__(self, other: 'TokenAmount') -> bool:
        self._validate_other(other, "compare")
        return self.raw >= other.raw
    
    def to_units(self, precision: int = None) -> str:
        """
        Convert to human readable units with specified decimal precision.
        Uses Decimal for precise calculation.
        """
        # Use stored decimals if precision not specified
        precision = precision if precision is not None else self.decimals
        
        # Validate precision
        if precision < 0:
            raise ValueError("Precision cannot be negative")
        if precision > self.MAX_DECIMALS:
            raise ValueError(f"Precision cannot exceed {self.MAX_DECIMALS}")
            
        # Convert to Decimal and divide
        amount_decimal = Decimal(self.raw) / (Decimal(10) ** self.decimals)
        
        # Format with specified precision
        return f"{amount_decimal:.{precision}f}"
    
    def to_wei(self) -> int:
        """Get raw wei amount"""
        return self.raw
