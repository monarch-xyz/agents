import os
import logging
from typing import List, Dict, Tuple, Optional
from collections import defaultdict
from clients.monarch_client import MonarchClient
from clients.morpho_client import MorphoClient
from models.user_data import UserAuthorization
from models.morpho_data import UserMarketData, Market
from strategies.simple_max_apy import SimpleMaxAPYStrategy, ReallocationStrategy
from utils.address import get_address_from_private_key

logger = logging.getLogger(__name__)

class AutomationService:
    def __init__(self):
        self.monarch_client = MonarchClient()
        self.morpho_client = MorphoClient()
        self.strategy = SimpleMaxAPYStrategy()
        self.markets_by_id: Dict[str, Market] = {}  # Cache markets by uniqueKey
        
    async def fetch_authorized_users(self) -> List[UserAuthorization]:
        """Fetch users who have authorized the bot"""
        rebalancer_address = get_address_from_private_key()
        return await self.monarch_client.get_authorized_users(rebalancer_address)

    async def fetch_markets(self) -> Dict[str, Market]:
        """Fetch all markets and cache them by uniqueKey"""
        logger.info("Fetching all markets data...")
        markets = await self.morpho_client.get_markets()
        
        # Cache markets by uniqueKey for easy lookup
        self.markets_by_id = {
            market.unique_key: market
            for market in markets
        }
        
        # Group markets by loan asset for logging
        markets_by_asset = defaultdict(list)
        for market in markets:
            asset_symbol = market.loan_asset['symbol']
            markets_by_asset[asset_symbol].append(market)
            
        # Log markets grouped by asset
        logger.info(f"Fetched {len(markets)} markets across {len(markets_by_asset)} assets:")
        for asset_symbol, asset_markets in markets_by_asset.items():
            logger.info(f"\n{asset_symbol} Markets ({len(asset_markets)}):")
            for market in asset_markets:
                state = market.state
                collateral = market.collateral_asset['symbol']
                logger.info(
                    f"* {market.unique_key[:8]}: "
                    f"{asset_symbol}-{collateral}, "
                    f"APY: {state['supplyApy']:.2%}, "
                    f"TVL: ${float(state['supplyAssetsUsd']):,.2f}, "
                    f"Utilization: {float(state['utilization']):.2%}"
                )
        
        return self.markets_by_id

    async def analyze_user_positions(
        self, 
        user: UserAuthorization
    ) -> Tuple[UserMarketData, Optional[ReallocationStrategy]]:
        """
        Analyze positions for a specific user and determine if reallocation is needed
        
        Returns:
            Tuple of (positions, reallocation_strategy)
            If no reallocation is needed, strategy will be None
        """
        positions = await self.morpho_client.get_user_positions(user.address, 8453)
        
        # Calculate reallocation strategy
        strategy_result = self.strategy.calculate_reallocation(
            positions=positions.market_positions,
            market_caps=user.market_caps,
            market_data=self.markets_by_id
        )
        
        if not strategy_result.actions:
            logger.info(f"No reallocation needed for {user.address}")
            return positions, None
            
        logger.info(f"Reallocation needed for {user.address}")
        for action in strategy_result.actions:
            market = self.markets_by_id.get(action.market_id)
            if market:
                logger.info(
                    f"Action: {action.action_type} {action.amount} "
                    f"{market.loan_asset['symbol']} in market {action.market_id[:8]} "
                    f"(current APY: {market.state['supplyApy']:.2%})"
                )
                
        return positions, strategy_result

    async def execute_reallocation(self, strategy_result: ReallocationStrategy):
        """Execute the reallocation actions"""
        try:
            # TODO: Execute the reallocation actions
            pass
        except Exception as e:
            logger.error(f"Error executing reallocation: {str(e)}")
            raise

    async def run(self):
        """Main automation loop"""
        try:
            # 1. Get all markets data first
            await self.fetch_markets()
            
            # 2. Get authorized users
            authorized_users = await self.fetch_authorized_users()
            logger.info(f"Found {len(authorized_users)} authorized users")
            
            # 3. Process each user
            for user in authorized_users:
                logger.info(f"Analyzing positions for {user.address}")
                positions, strategy = await self.analyze_user_positions(user)
                
                # 4. Execute reallocation if needed
                if strategy:
                    await self.execute_reallocation(strategy)
                
        except Exception as e:
            logger.error(f"Error in automation run: {str(e)}", exc_info=True)
            raise
