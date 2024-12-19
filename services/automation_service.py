import os
import logging
from typing import List, Dict
from clients.monarch_client import MonarchClient
from clients.morpho_client import MorphoClient
from models.user_data import UserAuthorization
from models.morpho_data import UserMarketData, Market
from strategies.simple_max_apy import SimpleMaxAPYStrategy
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

    async def fetch_markets(self, chain_id: int = 1) -> Dict[str, Market]:
        """Fetch all markets and cache them by uniqueKey"""
        logger.info("Fetching all markets data...")
        markets = await self.morpho_client.get_markets(chain_id=chain_id)
        
        # Cache markets by uniqueKey for easy lookup
        self.markets_by_id = {
            market.unique_key: market
            for market in markets
        }
        
        logger.info(f"Fetched {len(markets)} markets")
        return self.markets_by_id

    async def analyze_user_positions(self, user_address) -> UserMarketData:
        """Analyze positions for a specific user"""
        positions = await self.morpho_client.get_user_positions(user_address)
        return positions

    async def execute_reallocation(self, user: UserAuthorization, positions: UserMarketData):
        """Execute reallocation for a user based on strategy"""
        try:
            # Calculate reallocation strategy
            strategy_result = self.strategy.calculate_reallocation(
                positions=positions.market_positions,
                market_caps=user.market_caps,
                market_data=self.markets_by_id  # Pass the cached market data
            )
            
            if not strategy_result.actions:
                logger.info(f"No reallocation needed for {user.address}")
                return
                
            logger.info(f"Reallocation needed for {user.address}. Total value: {strategy_result.total_reallocation_value}")
            for action in strategy_result.actions:
                market = self.markets_by_id.get(action.market_id)
                if market:
                    logger.info(
                        f"Action: {action.action_type} {action.amount} "
                        f"{market.loan_asset['symbol']} in market {action.market_id} "
                        f"(current APY: {market.state['supplyApy']})"
                    )
            
            # TODO: Execute the reallocation actions
            
        except Exception as e:
            logger.error(f"Error executing reallocation for {user.address}: {str(e)}")
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
                # 4. Analyze positions
                logger.info(f"Analyzing positions for {user.address}")
                positions = await self.analyze_user_positions(user.address)
                
                # 5. Execute reallocation if needed
                await self.execute_reallocation(user, positions)
                
        except Exception as e:
            logger.error(f"Error in automation run: {str(e)}", exc_info=True)
            raise
