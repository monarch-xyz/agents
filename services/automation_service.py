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

        if self.chain_id not in {8453, 137}:
            raise ValueError(f"Unsupported chain ID: {self.chain_id}. Supported: 8453, 137")

        self.monarch_client = MonarchClient(chain_id=self.chain_id)
        self.morpho_client = MorphoClient(chain_id=self.chain_id)
        self.blockchain_client = BlockchainClient(chain_id=self.chain_id)
        self.blockchain_service = BlockchainService(self.blockchain_client)
        self.strategy = SimpleMaxAPYStrategy(chain_id=self.chain_id)
        self.notification_service = NotificationService()

        # Initialize GasService using chain-specific or global env vars
        max_gas_price = int(os.getenv(f'GAS_POLICY_MIN_GAS_{self.chain_id}', os.getenv('GAS_POLICY_MIN_GAS', '15')))
        max_retries = int(os.getenv(f'GAS_POLICY_MAX_RETRIES_{self.chain_id}', os.getenv('GAS_POLICY_MAX_RETRIES', '180')))
        self.gas_service = GasService(max_gas_price=max_gas_price, max_retries=max_retries)

        self.markets_by_id: Dict[str, Market] = {}

        # Whitelist is assumed global for now
        whitelist_str = os.getenv('WHITELISTED_ADDRESSES')
        self.whitelisted_addresses = set(addr.lower() for addr in whitelist_str.split(',')) if whitelist_str else set()
        if self.whitelisted_addresses:
            logger.info(f"[{self.chain_id}] Whitelist enabled with {len(self.whitelisted_addresses)} addresses")

    async def fetch_authorized_users(self) -> List[UserAuthorization]:
        """Fetch users who have authorized the bot for the current network"""
        logger.info(f"[{self.chain_id}] Fetching authorized users...")
        rebalancer_address = get_address_from_private_key()
        async with self.monarch_client as monarch:
            return await monarch.get_authorized_users(rebalancer_address, chain_id=self.chain_id)

    async def fetch_markets(self) -> Dict[str, Market]:
        """Fetch all markets for the current network and cache them by uniqueKey"""
        logger.info(f"[{self.chain_id}] Fetching all markets data...")
        markets = await self.morpho_client.get_markets(chain_id=self.chain_id)

        self.markets_by_id = {
            market.unique_key: market
            for market in markets
        }

        # Log grouped markets (optional)
        # markets_by_asset = defaultdict(list)
        # for market in markets:
        #     asset_symbol = market.loan_asset.symbol
        #     markets_by_asset[asset_symbol].append(market)
        # logger.info(f"[{self.chain_id}] Fetched {len(markets)} markets data grouped by asset")
        logger.info(f"[{self.chain_id}] Fetched {len(markets)} markets data")

        # --- Debug Logging: Print Market Details --- 
        logger.debug(f"--- Market Details for Chain ID: {self.chain_id} ---")
        if not self.markets_by_id:
             logger.debug("  No markets found or cached.")
        else:
             # Sort by ID for consistent logging order
             sorted_market_ids = sorted(self.markets_by_id.keys())
             for market_id in sorted_market_ids:
                market = self.markets_by_id[market_id]
                loan_sym = market.loan_asset.symbol if market.loan_asset else 'N/A'
                coll_sym = market.collateral_asset.symbol if market.collateral_asset else 'N/A'
                # Safely access APYs from state
                supply_apy_str = "N/A"
                borrow_apy_str = "N/A"
                if market.state:
                    try:
                         supply_apy_str = f"{market.state.supply_apy:.4%}" if market.state.supply_apy is not None else "N/A"
                    except (TypeError, ValueError):
                         supply_apy_str = "Error"
                    try:
                         borrow_apy_str = f"{market.state.borrow_apy:.4%}" if market.state.borrow_apy is not None else "N/A"
                    except (TypeError, ValueError):
                         borrow_apy_str = "Error"
                
                logger.debug(
                    f"  Market: {market.id} ({loan_sym}/{coll_sym}) | "
                    f"Supply APY: {supply_apy_str} | Borrow APY: {borrow_apy_str}"
                )
        logger.debug(f"--- End Market Details for Chain ID: {self.chain_id} ---")
        # --- End Debug Logging ---

        return self.markets_by_id

    async def analyze_user_positions(
        self,
        user: UserAuthorization
    ) -> Tuple[UserMarketData, Optional[ReallocationStrategy]]:
        """
        Analyze positions for a specific user on the current network.
        Returns tuple of (positions, reallocation_strategy). Strategy is None if no action needed.
        """
        logger.info(f"[{self.chain_id}] Fetching positions for user {user.address}")
        positions = await self.morpho_client.get_user_positions(user.address, self.chain_id)

        logger.info(f"[{self.chain_id}] Found {len(positions.market_positions)} market positions for user {user.address}")

        strategy_result = self.strategy.calculate_reallocation(
            positions=positions.market_positions,
            market_caps=user.market_caps,
            market_data=self.markets_by_id
        )

        if not strategy_result.actions:
            logger.info(f"[{self.chain_id}] No reallocation needed for {user.address}")
            return positions, None

        logger.info(f"[{self.chain_id}] Reallocation needed for {user.address}")
        # Log actions for clarity
        for action in strategy_result.actions:
            market = self.markets_by_id.get(action.market_id)
            if market:
                 asset_symbol = market.loan_asset.symbol
                 apy_str = f"(APY: {market.state.supply_apy:.2%})" if hasattr(market.state, 'supply_apy') else ""
                 logger.info(
                     f"  Action: {action.action_type} {action.amount} {asset_symbol} in market {action.market_id[:8]} {apy_str}"
                 )
            else:
                logger.warning(f"[{self.chain_id}] Market {action.market_id} not found in cache for reallocation action.")

        return positions, strategy_result

    async def execute_reallocation(
        self,
        user_address: str,
        strategy_result: ReallocationStrategy
    ) -> Tuple[str, TxReceipt]:
        """
        Execute the reallocation actions on the current network.
        Returns tuple of (tx_hash, tx_receipt).
        Raises Exception on failure.
        """
        try:
            logger.info(f"[{self.chain_id}] Executing reallocation for user {user_address}")

            if not strategy_result.actions:
                raise ValueError("No actions to execute")

            tx_hash, receipt = await self.blockchain_service.rebalance(
                user_address=user_address,
                actions=strategy_result.actions,
                markets=self.markets_by_id
            )

            await self.notification_service.notify_reallocation(
                user_address=user_address,
                chain_id=self.chain_id,
                actions=[{
                    'market_id': action.market_id,
                    'action_type': action.action_type,
                    'amount_value': action.amount.to_units(),
                    'symbol': self.markets_by_id[action.market_id].loan_asset.symbol
                } for action in strategy_result.actions],
                markets=self.markets_by_id,
                tx_hash=tx_hash
            )

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
            try:
                gas_price = await self.gas_service.wait_for_acceptable_gas()
                logger.info(f"[{self.chain_id}] Gas price acceptable at {gas_price:.1f} gwei. Starting process...")
            except TimeoutError as e:
                logger.error(f"[{self.chain_id}] {str(e)}")
                return

            await self.fetch_markets()
            users = await self.fetch_authorized_users()

            if self.whitelisted_addresses:
                original_count = len(users)
                users = [user for user in users if user.address.lower() in self.whitelisted_addresses]
                logger.info(f"[{self.chain_id}] Filtered {original_count} users down to {len(users)} whitelisted users")
            else:
                logger.info(f"[{self.chain_id}] Found {len(users)} authorized users")

            users_reallocation_needed = 0
            users_reallocation_errors = 0

            for user in users:
                try:
                    logger.info(f"[{self.chain_id}] Processing user {user.address}")

                    # Consider if refetching market data per user is needed vs potential staleness
                    # await self.fetch_markets()

                    positions, strategy = await self.analyze_user_positions(user)

                    if strategy:
                        users_reallocation_needed += 1
                        await self.execute_reallocation(user.address, strategy)

                    # Consider if a delay is needed between users, especially if running concurrently
                    # await asyncio.sleep(1)

                    logger.info(f"[{self.chain_id}] ====================== Finished processing user {user.address} ======================")

                except Exception as e:
                    logger.error(f"[{self.chain_id}] Error processing user {user.address}: {str(e)}")
                    users_reallocation_errors += 1
                    continue # Continue to the next user on this network

            await self.notification_service.notify_run(self.chain_id, users_reallocation_needed, users_reallocation_errors)
            logger.info(f"[{self.chain_id}] Automation run finished. Reallocations: {users_reallocation_needed}, Errors: {users_reallocation_errors}")

        except Exception as e:
            logger.error(f"[{self.chain_id}] Automation run failed: {str(e)}")
            await self.notification_service.notify_error(self.chain_id, str(e))
            raise
