import pytest
from decimal import Decimal
from utils.token_amount import TokenAmount

def test_from_wei():
    """Test creating TokenAmount from wei"""
    # Test with USDC (6 decimals)
    amount = TokenAmount.from_wei(1_000_000, decimals=6)  # 1 USDC
    assert amount.raw == 1_000_000
    assert amount.decimals == 6
    assert amount.to_units() == "1.000000"
    
    # Test with ETH (18 decimals)
    amount = TokenAmount.from_wei(1_000_000_000_000_000_000, decimals=18)  # 1 ETH
    assert amount.raw == 1_000_000_000_000_000_000
    assert amount.decimals == 18
    assert amount.to_units() == "1.000000000000000000"

def test_from_units():
    """Test creating TokenAmount from human readable units"""
    # Test with USDC (6 decimals)
    amount = TokenAmount.from_units(1.5, decimals=6)  # 1.5 USDC
    assert amount.raw == 1_500_000
    assert amount.decimals == 6
    assert amount.to_units() == "1.500000"
    
    # Test with ETH (18 decimals)
    amount = TokenAmount.from_units(1.5, decimals=18)  # 1.5 ETH
    assert amount.raw == 1_500_000_000_000_000_000
    assert amount.decimals == 18
    assert amount.to_units() == "1.500000000000000000"

def test_to_units_with_different_precision():
    """Test converting to units with different precision levels"""
    amount = TokenAmount.from_wei(1_234_567, decimals=6)  # 1.234567 USDC
    
    # Default precision (uses token decimals)
    assert amount.to_units() == "1.234567"
    
    # Custom precision
    assert amount.to_units(precision=2) == "1.23"
    assert amount.to_units(precision=4) == "1.2346"
    assert amount.to_units(precision=8) == "1.23456700"

def test_arithmetic_operations():
    """Test arithmetic operations between TokenAmounts"""
    amount1 = TokenAmount.from_units(1.5, decimals=6)  # 1.5 USDC
    amount2 = TokenAmount.from_units(0.5, decimals=6)  # 0.5 USDC
    
    # Addition
    sum_amount = amount1 + amount2
    assert sum_amount.to_units() == "2.000000"
    
    # Subtraction
    diff_amount = amount1 - amount2
    assert diff_amount.to_units() == "1.000000"

def test_comparison_operations():
    """Test comparison operations between TokenAmounts"""
    amount1 = TokenAmount.from_units(1.5, decimals=6)
    amount2 = TokenAmount.from_units(0.5, decimals=6)
    amount3 = TokenAmount.from_units(1.5, decimals=6)
    
    # Greater than
    assert amount1 > amount2
    # Less than
    assert amount2 < amount1
    # Greater than or equal
    assert amount1 >= amount3
    # Less than or equal
    assert amount2 <= amount1

def test_different_decimals_error():
    """Test that operations between different decimal tokens raise errors"""
    usdc = TokenAmount.from_units(1.5, decimals=6)   # USDC
    eth = TokenAmount.from_units(1.5, decimals=18)   # ETH
    
    # Addition should raise ValueError
    with pytest.raises(ValueError, match="Cannot add tokens with different decimals"):
        _ = usdc + eth
    
    # Subtraction should raise ValueError
    with pytest.raises(ValueError, match="Cannot subtract tokens with different decimals"):
        _ = usdc - eth
    
    # Comparison should raise ValueError
    with pytest.raises(ValueError, match="Cannot compare tokens with different decimals"):
        _ = usdc > eth

def test_validation_bounds():
    """Test validation of amount bounds"""
    max_uint256 = 2**256 - 1
    
    # Test maximum value
    TokenAmount.from_wei(max_uint256)  # Should not raise
    
    # Test overflow
    with pytest.raises(ValueError, match="exceeds maximum value"):
        TokenAmount.from_wei(max_uint256 + 1)
    
    # Test negative values
    with pytest.raises(ValueError, match="cannot be negative"):
        TokenAmount(raw=-1, decimals=18)

def test_decimal_validation():
    """Test validation of decimals parameter"""
    # Test minimum decimals
    TokenAmount.from_wei(1000, decimals=0)  # Should not raise
    
    # Test maximum decimals
    TokenAmount.from_wei(1000, decimals=77)  # Should not raise
    
    # Test invalid decimals
    with pytest.raises(ValueError, match="Decimals cannot exceed"):
        TokenAmount.from_wei(1000, decimals=78)
    
    with pytest.raises(ValueError, match="Decimals cannot be less than"):
        TokenAmount.from_wei(1000, decimals=-1)

def test_from_units_precision():
    """Test precision handling in from_units"""
    # Test exact conversion
    amount = TokenAmount.from_units("1.5", decimals=6)
    assert amount.raw == 1_500_000
    
    # Test string with many decimal places (should fail if more decimals than allowed)
    with pytest.raises(ValueError, match="Amount has 8 decimal places, but token only supports 6"):
        TokenAmount.from_units("1.23456789", decimals=6)  # 8 decimals for 6 decimal token
    
    # Test large numbers that are still valid
    large_but_valid = "1" + "0" * 20  # 1e20
    amount = TokenAmount.from_units(large_but_valid, decimals=18)
    assert amount.raw == int("1" + "0" * 38)  # 1e38 wei (1e20 * 1e18)
    
    # Test numbers that are too large
    too_large = "1" + "0" * 60  # 1e60
    with pytest.raises(ValueError, match="exceeds maximum value"):
        TokenAmount.from_units(too_large, decimals=18)

def test_arithmetic_overflow():
    """Test overflow protection in arithmetic operations"""
    max_uint256 = 2**256 - 1
    near_max = TokenAmount(raw=max_uint256 - 1000, decimals=18)
    small = TokenAmount(raw=2000, decimals=18)
    
    # Addition overflow
    with pytest.raises(OverflowError, match="exceed maximum value"):
        near_max + small
    
    # Subtraction underflow
    small_amount = TokenAmount(raw=1000, decimals=18)
    large_amount = TokenAmount(raw=2000, decimals=18)
    with pytest.raises(ValueError, match="result in negative"):
        small_amount - large_amount

def test_decimal_precision():
    """Test precise decimal calculations"""
    # Test precise division
    large_amount = TokenAmount.from_wei(10**18, decimals=18)
    assert large_amount.to_units() == "1.000000000000000000"
    
    # Test with different precisions
    amount = TokenAmount.from_wei(1234567890123456789, decimals=18)
    assert amount.to_units(precision=3) == "1.235"
    assert amount.to_units(precision=9) == "1.234567890"
    
    # Test precision validation
    with pytest.raises(ValueError, match="Precision cannot be negative"):
        amount.to_units(precision=-1)
    
    with pytest.raises(ValueError, match="Precision cannot exceed"):
        amount.to_units(precision=78)

def test_type_validation():
    """Test type validation"""
    # Test invalid raw amount type
    with pytest.raises(TypeError, match="Raw amount must be an integer"):
        TokenAmount(raw=1.5, decimals=18)
    
    # Test invalid decimals type
    with pytest.raises(TypeError, match="Decimals must be an integer"):
        TokenAmount(raw=1000, decimals=18.5)
    
    # Test invalid from_units input
    with pytest.raises(ValueError):
        TokenAmount.from_units("invalid", decimals=18)

def test_operation_type_safety():
    """Test type safety in operations"""
    amount = TokenAmount.from_wei(1000, decimals=18)
    
    # Test invalid addition
    with pytest.raises(TypeError):
        amount + 1000
    
    # Test invalid subtraction
    with pytest.raises(TypeError):
        amount - "1000"
    
    # Test invalid comparison
    with pytest.raises(TypeError):
        amount < 1000

def test_from_wei_decimal():
    """Test creating TokenAmount from Decimal wei amounts"""
    # Test with Decimal input
    amount = TokenAmount.from_wei(Decimal('1000000'), decimals=6)
    assert amount.raw == 1_000_000
    assert amount.decimals == 6
    assert amount.to_units() == "1.000000"
    
    # Test with float (should fail)
    with pytest.raises(TypeError, match="Float values are not supported"):
        TokenAmount.from_wei(1000000.0, decimals=6)
    
    # Test with invalid type
    with pytest.raises(TypeError, match="Cannot convert"):
        TokenAmount.from_wei([1000000], decimals=6)
