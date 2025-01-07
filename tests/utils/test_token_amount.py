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
    
    # Addition should raise assertion error
    with pytest.raises(AssertionError):
        _ = usdc + eth
    
    # Subtraction should raise assertion error
    with pytest.raises(AssertionError):
        _ = usdc - eth
    
    # Comparison should raise assertion error
    with pytest.raises(AssertionError):
        _ = usdc > eth
