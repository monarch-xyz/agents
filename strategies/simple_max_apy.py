import logging
from typing import List, Dict, Optional
from collections import defaultdict
from models.morpho_data import MarketPosition, Market
from models.user_data import MarketCap
from utils.token_amount import TokenAmount
from .base import BaseStrategy, MarketAction, ReallocationStrategy

logger = logging.getLogger(__name__)

class SimpleMaxAPYStrategy(BaseStrategy):
    """Simple strategy that reallocates based on market caps and APY"""
    
    MAX_MARKET_IMPACT_RATIO = 0.05  # 5% of total supply
    
    def __init__(self, max_market_impact_ratio: float = 0.05):
        """
        Initialize strategy with configurable parameters
        
        Args:
            max_market_impact_ratio: Maximum ratio of market's total supply that can be allocated
                                   (default: 0.05 or 5%)
        """
        self.max_market_impact_ratio = max_market_impact_ratio
        # Track allocations in wei to avoid TokenAmount complexity
        self.market_allocations = defaultdict(int)
    
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
            return ReallocationStrategy(actions=[])
            
        # Reset market allocations for new calculation
        self.market_allocations.clear()
            
        # Step 1: Group positions by loan token
        grouped_positions = self.process_positions(positions, market_data)
        
        # Fix market cap IDs (remove leading //)
        fixed_caps = []
        for cap in market_caps:
            if cap.market_id.startswith('//'):
                cap.market_id = '0x' + cap.market_id[2:]
            fixed_caps.append(cap)
            
        caps_by_market = {cap.market_id: cap for cap in fixed_caps}
        
        # Track actions by market to combine them
        withdrawals_by_market = defaultdict(lambda: {
            'amount': None,
            'shares': None,
            'position': None,
            'target_cap': None
        })
        
        supplies_by_market = defaultdict(lambda: {
            'amount': None,
            'position': None,
            'target_cap': None,
            'decimals': None
        })
        
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
            
            # Find all capped markets sorted by APY
            capped_markets = []
            for market in available_markets:
                if market.unique_key in caps_by_market:
                    market_apy = float(market.state['supplyApy'])
                    capped_markets.append((market, market_apy))
            
            # Sort by APY descending
            capped_markets.sort(key=lambda x: x[1], reverse=True)
            
            if not capped_markets:
                logger.info(f"No capped markets available for {symbol}")
                continue
            
            # Check each position for potential reallocation
            for pos in group['markets']:
                market = market_data.get(pos.unique_key)
                if not market:
                    continue
                    
                current_apy = float(market.state['supplyApy'])
                position_amount_wei = int(pos.supply_assets)
                
                # Try each capped market in order of APY until we find one with capacity
                for target_market, target_apy in capped_markets:
                    # Skip if current market has higher APY
                    if current_apy >= target_apy:
                        logger.info(
                            f"Keeping position in market ({pos.unique_key[:10]}) "
                            f"with APY {current_apy:.2%} >= {target_apy:.2%}"
                        )
                        break  # No point trying lower APY markets
                        
                    if pos.unique_key == target_market.unique_key:
                        continue  # Skip same market
                    
                    # Calculate maximum amount that can be moved to this market (in wei)
                    target_market_supply_wei = int(target_market.state.get('supplyAssets', 0))
                    max_allocation_wei = int(target_market_supply_wei * self.max_market_impact_ratio)
                    current_allocation_wei = self.market_allocations[target_market.unique_key]
                    remaining_allocation_wei = max_allocation_wei - current_allocation_wei
                    
                    if remaining_allocation_wei <= 0:
                        logger.info(
                            f"Market {target_market.unique_key[:10]} full - "
                            f"Already at maximum allocation of "
                            f"{TokenAmount.from_wei(max_allocation_wei, decimals).to_units()} {symbol}"
                        )
                        continue  # Try next market
                    
                    # Calculate amount to move (limited by market impact)
                    move_amount_wei = min(position_amount_wei, remaining_allocation_wei)
                    
                    if move_amount_wei <= 0:
                        continue  # Try next market
                    
                    target_cap = caps_by_market[target_market.unique_key]
                    move_amount = TokenAmount.from_wei(move_amount_wei, decimals)
                    
                    # Create withdrawal action - use shares if moving entire position
                    use_max_shares = move_amount_wei >= position_amount_wei
                    withdrawal = MarketAction.create_withdrawal(
                        market_id=pos.unique_key,
                        position=pos,
                        market=market,
                        use_max_shares=use_max_shares,
                        target_cap=target_cap
                    )
                    
                    # Combine with existing withdrawal if any
                    market_withdrawals = withdrawals_by_market[pos.unique_key]
                    if market_withdrawals['shares'] is None:
                        market_withdrawals.update({
                            'shares': withdrawal.shares,
                            'amount': withdrawal.amount,
                            'position': pos,
                            'target_cap': target_cap
                        })
                    else:
                        market_withdrawals['shares'] += withdrawal.shares
                        market_withdrawals['amount'] += withdrawal.amount
                    
                    # Track supply action
                    market_supplies = supplies_by_market[target_market.unique_key]
                    if market_supplies['amount'] is None:
                        market_supplies.update({
                            'amount': move_amount,
                            'position': pos,
                            'target_cap': target_cap,
                            'decimals': decimals
                        })
                    else:
                        market_supplies['amount'] += move_amount
                    
                    # Update market allocation tracking (in wei)
                    self.market_allocations[target_market.unique_key] += move_amount_wei
                    
                    logger.info(
                        f"Move {move_amount.to_units()} {symbol} from "
                        f"market ({pos.unique_key[:10]})({current_apy:.2%}) to "
                        f"market ({target_market.unique_key[:10]})({target_apy:.2%}) "
                        f"[{TokenAmount.from_wei(self.market_allocations[target_market.unique_key], decimals).to_units()}/"
                        f"{TokenAmount.from_wei(max_allocation_wei, decimals).to_units()} allocated]"
                    )
                    break  # Successfully moved to this market, stop trying others

        # Create final list of actions
        actions = []
        
        # Add combined withdrawals
        for market_id, withdrawal in withdrawals_by_market.items():
            if withdrawal['shares'] is not None:
                actions.append(MarketAction(
                    market_id=market_id,
                    action_type='withdraw',
                    amount=withdrawal['amount'],
                    shares=withdrawal['shares'],
                    current_position=withdrawal['position'],
                    target_cap=withdrawal['target_cap']
                ))
        
        # Add combined supplies
        for market_id, supply in supplies_by_market.items():
            if supply['amount'] is not None:
                actions.append(MarketAction(
                    market_id=market_id,
                    action_type='supply',
                    amount=supply['amount'],
                    shares=TokenAmount.from_wei(0, 0),
                    current_position=supply['position'],
                    target_cap=supply['target_cap']
                ))
        
        return ReallocationStrategy(actions=actions)
