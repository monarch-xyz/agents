import logging
from clients.blockchain_client import BlockchainClient
from clients.morpho_client import MorphoClient
from clients.monarch_client import MonarchClient
from typing import List
from models.user_data import UserAuthorization
from utils.address import get_address_from_private_key

logger = logging.getLogger(__name__)

class AutomationService:
    def __init__(self):
        self.blockchain_client = BlockchainClient()
        self.morpho_client = MorphoClient()
        self.monarch_client = MonarchClient()
        self.rebalancer_address = get_address_from_private_key()
        logger.info(f"Initialized automation service with rebalancer address: {self.rebalancer_address}")

    async def fetch_authorized_users(self) -> List[UserAuthorization]:
        logger.info("Fetching authorized users")

        """Fetch users who have authorized the bot"""
        try:
            users = await self.monarch_client.get_authorized_users(self.rebalancer_address)
            logger.info(f"Found {len(users)} authorized users")
            return users
        except Exception as e:
            logger.error(f"Error fetching authorized users: {str(e)}")
            return []

    async def analyze_user_positions(self, user_address):
        """Analyze positions for a specific user"""
        positions = await self.blockchain_client.get_user_positions(user_address)
        # Add analysis logic here
        return positions

    async def execute_reallocation(self, user_address, strategy):
        """Execute the reallocation transaction"""
        try:
            tx = await self.blockchain_client.send_reallocation_transaction(
                user_address, 
                strategy
            )
            logger.info(f"Executed reallocation for {user_address}: {tx}")
            return tx
        except Exception as e:
            logger.error(f"Failed to execute reallocation for {user_address}: {str(e)}")
            return None

    async def run(self):
        """Main execution flow"""
        logger.info("Starting automation run")
        
        try:
            # 1. Fetch authorized users
            authorized_users = await self.fetch_authorized_users()
            logger.info(f"Found {len(authorized_users)} authorized users")

            # 2. Process each user
            for user in authorized_users:
                # 3. Analyze positions
                positions = await self.analyze_user_positions(user.address)
                
                # 4. Determine if reallocation is needed
                if self._should_reallocate(positions):
                    strategy = self._determine_strategy(positions)
                    await self.execute_reallocation(user.address, strategy)

        except Exception as e:
            logger.error(f"Error in automation run: {str(e)}", exc_info=True)

    def _should_reallocate(self, positions):
        """Determine if reallocation is needed based on positions"""
        # Add your reallocation criteria here
        return False

    def _determine_strategy(self, positions):
        """Determine the reallocation strategy based on positions"""
        # Add your strategy logic here
        return {}
