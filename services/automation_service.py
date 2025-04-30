import os
import logging
import asyncio
from typing import List, Dict, Tuple, Optional, Any
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
    def __init__(self, chain_id: int):
        self.chain_id = chain_id
        logger.info(f"Initializing AutomationService for chain ID: {self.chain_id}")

        # Validate chain ID
        if self.chain_id not in {8453, 137}: # Base, Polygon
            raise ValueError(f"Unsupported chain ID: {self.chain_id}. Supported: 8453, 137")

        # Initialize clients - Pass only chain_id, they will derive URLs
        # MonarchClient might still need an API URL from env or config
        monarch_api_url = os.getenv("MONARCH_API_URL") # Example: Get a global Monarch URL
        # self.monarch_client = MonarchClient(api_url=monarch_api_url)
        self.monarch_client = MonarchClient(chain_id=self.chain_id) # Pass chain_id
        self.morpho_client = MorphoClient(chain_id=self.chain_id)
        self.blockchain_client = BlockchainClient(chain_id=self.chain_id)

        # Initialize services that depend on clients
        self.blockchain_service = BlockchainService(self.blockchain_client)
        self.strategy = SimpleMaxAPYStrategy()
        self.notification_service = NotificationService()

        # Initialize GasService - Assuming gas settings might be chain-specific in future?
        # For now, using global env vars, but could fetch chain-specific ones
        max_gas_price = int(os.getenv(f'GAS_POLICY_MIN_GAS_{self.chain_id}', os.getenv('GAS_POLICY_MIN_GAS', '15'))) 
        max_retries = int(os.getenv(f'GAS_POLICY_MAX_RETRIES_{self.chain_id}', os.getenv('GAS_POLICY_MAX_RETRIES', '180')))
        self.gas_service = GasService(max_gas_price=max_gas_price, max_retries=max_retries)

        self.markets_by_id: Dict[str, Market] = {}  # Cache markets by uniqueKey

        # Whitelist might be global or per-network. Assuming global for now.
        whitelist_str = os.getenv('WHITELISTED_ADDRESSES') 
        self.whitelisted_addresses = set(addr.lower() for addr in whitelist_str.split(',')) if whitelist_str else set()
        if self.whitelisted_addresses:
            logger.info(f"[{self.chain_id}] Whitelist enabled with {len(self.whitelisted_addresses)} addresses")

    async def fetch_authorized_users(self) -> List[UserAuthorization]:
        """Fetch users who have authorized the bot for the current network"""
        logger.info(f"[{self.chain_id}] Fetching authorized users...")
        # Assuming rebalancer address is global for now
        rebalancer_address = get_address_from_private_key()
        async with self.monarch_client as monarch:
            # Pass chain_id if MonarchClient needs it
            return await monarch.get_authorized_users(rebalancer_address, chain_id=self.chain_id)

    async def fetch_markets(self) -> Dict[str, Market]:
        """Fetch all markets for the current network and cache them by uniqueKey"""
        logger.info(f"[{self.chain_id}] Fetching all markets data...")
        # Pass chain_id to get_markets
        markets = await self.morpho_client.get_markets(chain_id=self.chain_id)

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
        logger.info(f"[{self.chain_id}] Fetched {len(markets)} markets data")

        return self.markets_by_id

    async def analyze_user_positions(
        self,
        user: UserAuthorization
    ) -> Tuple[UserMarketData, Optional[ReallocationStrategy]]:
        """
        Analyze positions for a specific user on the current network

        Returns:
            Tuple of (positions, reallocation_strategy)
            If no reallocation is needed, strategy will be None
        """
        logger.info(f"[{self.chain_id}] Fetching positions for user {user.address}")
        # Pass chain_id to get_user_positions
        positions = await self.morpho_client.get_user_positions(user.address, self.chain_id)

        # Log positions count
        logger.info(f"[{self.chain_id}] Found {len(positions.market_positions)} market positions for user {user.address}")

        # Calculate reallocation strategy
        strategy_result = self.strategy.calculate_reallocation(
            positions=positions.market_positions,
            market_caps=user.market_caps, # Assuming market caps from Monarch are relevant for this chain?
            market_data=self.markets_by_id
        )

        if not strategy_result.actions:
            logger.info(f"[{self.chain_id}] No reallocation needed for {user.address}")
            return positions, None

        logger.info(f"[{self.chain_id}] Reallocation needed for {user.address}")
        for action in strategy_result.actions:
            market = self.markets_by_id.get(action.market_id)
            if market:
                logger.info(
                    f"[{self.chain_id}] Action: {action.action_type} {action.amount} "
                    f"{market.loan_asset.symbol} in market {action.market_id[:8]} "
                    f"(current APY: {market.state.supply_apy:.2%})"
                )
            else:
                # This condition might indicate an issue if the market was expected
                logger.warning(f"[{self.chain_id}] Market {action.market_id} not found in cache for reallocation action.")

        return positions, strategy_result

    async def execute_reallocation(
        self,
        user_address: str,
        strategy_result: ReallocationStrategy
    ) -> Tuple[str, TxReceipt]:
        """
        Execute the reallocation actions on the current network

        Args:
            user_address: Address of the user to rebalance for
            strategy_result: Strategy containing actions to execute

        Returns:
            Tuple of (transaction hash, transaction receipt)

        Raises:
            Exception if transaction fails
        """
        try:
            logger.info(f"[{self.chain_id}] Executing reallocation for user {user_address}")

            if not strategy_result.actions:
                raise ValueError("No actions to execute")

            # Execute rebalance transaction (BlockchainService uses the configured BlockchainClient)
            tx_hash, receipt = await self.blockchain_service.rebalance(
                user_address=user_address,
                actions=strategy_result.actions,
                markets=self.markets_by_id
            )

            # Send notification (NotificationService is likely global)
            await self.notification_service.notify_reallocation(
                user_address=user_address,
                chain_id=self.chain_id, # Add chain_id context to notification
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
                f"[{self.chain_id}] Reallocation executed successfully for {user_address}. "
                f"Transaction: {tx_hash}"
            )

            return tx_hash, receipt

        except Exception as e:
            logger.error(f"[{self.chain_id}] Failed to execute reallocation for {user_address}: {str(e)}")
            raise

    async def run(self):
        """Main automation loop for the configured network"""
        logger.info(f"[{self.chain_id}] Starting automation run...")
        try:
            # Wait for acceptable gas price before starting
            try:
                gas_price = await self.gas_service.wait_for_acceptable_gas()
                logger.info(f"[{self.chain_id}] Gas price acceptable at {gas_price:.1f} gwei. Starting process...")
            except TimeoutError as e:
                logger.error(f"[{self.chain_id}] {str(e)}")
                return

            # Fetch latest market data for this network
            await self.fetch_markets()

            # Fetch authorized users for this network
            users = await self.fetch_authorized_users()

            # Filter users by whitelist if enabled (Assuming global whitelist)
            if self.whitelisted_addresses:
                original_count = len(users)
                users = [user for user in users if user.address.lower() in self.whitelisted_addresses]
                logger.info(f"[{self.chain_id}] Filtered {original_count} users down to {len(users)} whitelisted users")
            else:
                logger.info(f"[{self.chain_id}] Found {len(users)} authorized users")

            users_reallocation_needed = 0
            users_reallocation_errors = 0

            # Process each user for this network
            for user in users:
                try:
                    logger.info(f"[{self.chain_id}] Processing user {user.address}")

                    # Refetch market Data before analyzing each user?
                    # Consider staleness vs. rate limiting/performance
                    # await self.fetch_markets() # Maybe remove this redundant fetch

                    # Analyze positions and get reallocation strategy
                    positions, strategy = await self.analyze_user_positions(user)

                    # Execute reallocation if needed
                    if strategy:
                        users_reallocation_needed += 1
                        await self.execute_reallocation(user.address, strategy)

                    # Wait? Maybe not needed if running networks sequentially or if RPC/API handles concurrency
                    # await asyncio.sleep(1) # Reduced wait time or remove

                    logger.info(f"[{self.chain_id}] ====================== Finished processing user {user.address} ======================")

                except Exception as e:
                    logger.error(f"[{self.chain_id}] Error processing user {user.address}: {str(e)}")
                    users_reallocation_errors += 1
                    continue # Continue to the next user on this network

            # Notify about the result for this network run
            await self.notification_service.notify_run(self.chain_id, users_reallocation_needed, users_reallocation_errors)
            logger.info(f"[{self.chain_id}] Automation run finished. Reallocations: {users_reallocation_needed}, Errors: {users_reallocation_errors}")

        except Exception as e:
            logger.error(f"[{self.chain_id}] Automation run failed: {str(e)}")
            await self.notification_service.notify_error(self.chain_id, str(e)) # Notify about the overall run failure
            raise
