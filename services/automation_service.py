import os
import logging
import asyncio
from typing import List, Dict, Tuple, Optional
from collections import defaultdict
from web3.types import TxReceipt
from clients.monarch_client import MonarchClient
from clients.morpho_client import MorphoClient
from clients.blockchain_client import BlockchainClient
from services.blockchain_service import BlockchainService
from services.notification_service import NotificationService
from services.gas_service import GasService
from models.user_data import UserAuthorization
from models.morpho_data import UserMarketData, Market
from strategies.simple_max_apy import SimpleMaxAPYStrategy, ReallocationStrategy
from utils.address import get_address_from_private_key

logger = logging.getLogger(__name__)

class AutomationService:
    def __init__(self):
        self.monarch_client = MonarchClient()
        self.morpho_client = MorphoClient()
        self.blockchain_client = BlockchainClient()
        self.blockchain_service = BlockchainService(self.blockchain_client)
        self.strategy = SimpleMaxAPYStrategy()
        self.notification_service = NotificationService()
        
        # Initialize GasService with environment variable
        max_gas_price = int(os.getenv('GAS_POLICY_MIN_GAS', '15'))  # Default to 15 if not set
        max_retries = int(os.getenv('GAS_POLICY_MAX_RETRIES', '180'))  # Default to 180 if not set

        self.gas_service = GasService(max_gas_price=max_gas_price, max_retries=max_retries)
        
        self.markets_by_id: Dict[str, Market] = {}  # Cache markets by uniqueKey
        
        # Get whitelist from environment variable
        whitelist_str = os.getenv('WHITELISTED_ADDRESSES')
        self.whitelisted_addresses = set(addr.lower() for addr in whitelist_str.split(',')) if whitelist_str else set()
        if self.whitelisted_addresses:
            logger.info(f"Whitelist enabled with {len(self.whitelisted_addresses)} addresses")

    async def fetch_authorized_users(self) -> List[UserAuthorization]:
        """Fetch users who have authorized the bot"""
        rebalancer_address = get_address_from_private_key()
        async with self.monarch_client as monarch:
            return await monarch.get_authorized_users(rebalancer_address)

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
            asset_symbol = market.loan_asset.symbol
            markets_by_asset[asset_symbol].append(market)
            
        # Log markets grouped by asset
        logger.info(f"Fetched {len(markets)} markets data")
        
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
        logger.info(f"Fetching positions for user {user.address}")
        positions = await self.morpho_client.get_user_positions(user.address, 8453)
        
        # Log positions count
        logger.info(f"Found {len(positions.market_positions)} market positions for user {user.address}")
        
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
                    f"{market.loan_asset.symbol} in market {action.market_id[:8]} "
                    f"(current APY: {market.state.supply_apy:.2%})"
                )

            else:
                logger.info(f"Market not found for action: {action.market_id}")
                
        return positions, strategy_result

    async def execute_reallocation(
        self,
        user_address: str,
        strategy_result: ReallocationStrategy
    ) -> Tuple[str, TxReceipt]:
        """
        Execute the reallocation actions
        
        Args:
            user_address: Address of the user to rebalance for
            strategy_result: Strategy containing actions to execute
            
        Returns:
            Tuple of (transaction hash, transaction receipt)
            
        Raises:
            Exception if transaction fails
        """
        try:
            logger.info(f"Executing reallocation for user {user_address}")
            
            if not strategy_result.actions:
                raise ValueError("No actions to execute")
                
            # Execute rebalance transaction
            tx_hash, receipt = await self.blockchain_service.rebalance(
                user_address=user_address,
                actions=strategy_result.actions,
                markets=self.markets_by_id
            )
            
            # Send notification
            await self.notification_service.notify_reallocation(
                user_address=user_address,
                actions=[{
                    'market_id': action.market_id,
                    'action_type': action.action_type,
                    'amount_value': action.amount.to_units(),
                    'symbol': self.markets_by_id[action.market_id].loan_asset.symbol
                } for action in strategy_result.actions],
                markets=self.markets_by_id,
                tx_hash=tx_hash
            )
            
            # Log success
            logger.info(
                f"Reallocation executed successfully for {user_address}. "
                f"Transaction: {tx_hash}"
            )
            
            return tx_hash, receipt
            
        except Exception as e:
            logger.error(f"Failed to execute reallocation for {user_address}: {str(e)}")
            raise

    async def run(self):
        """Main automation loop"""
        try:
            # Wait for acceptable gas price before starting
            try:
                gas_price = await self.gas_service.wait_for_acceptable_gas()
                logger.info(f"Gas price acceptable at {gas_price:.1f} gwei. Starting automation...")
            except TimeoutError as e:
                logger.error(str(e))
                return
                
            # Fetch latest market data
            await self.fetch_markets()
            
            # Fetch authorized users
            users = await self.fetch_authorized_users()
            
            # Filter users by whitelist if enabled
            if self.whitelisted_addresses:
                users = [user for user in users if user.address.lower() in self.whitelisted_addresses]
                logger.info(f"Filtered to {len(users)} whitelisted users")
            else:
                logger.info(f"Found {len(users)} authorized users")

            users_reallocation_needed = 0
            users_reallocation_errors = 0
            
            # Process each user
            for user in users:
                try:
                    logger.info(f"Processing user {user.address}")

                    # Refetch market Data
                    await self.fetch_markets()

                    # Analyze positions and get reallocation strategy
                    positions, strategy = await self.analyze_user_positions(user)
                    
                    # Execute reallocation if needed
                    if strategy:
                        users_reallocation_needed += 1
                        await self.execute_reallocation(user.address, strategy)

                    # Wait for 5 seconds before processing next user
                    await asyncio.sleep(5)

                    logger.info(f"====================== Finished processing user {user.address} ======================")
                    
                except Exception as e:
                    logger.error(f"Error processing user {user.address}: {str(e)}")
                    users_reallocation_errors += 1
                    continue
                    
            # Notify about the result
            await self.notification_service.notify_run(users_reallocation_needed, users_reallocation_errors)
            
        except Exception as e:
            logger.error(f"Automation run failed: {str(e)}")
            raise
