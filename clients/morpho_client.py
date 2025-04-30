import os
import logging
import asyncio
from typing import List, Optional, Dict, Any
from gql import gql, Client
from gql.transport.aiohttp import AIOHTTPTransport
from aiohttp import ClientTimeout, TCPConnector, ClientSession
from models.morpho_data import UserMarketData, Market, MarketPosition, PositionState, Asset, Chain, MorphoBlue, DailyApys, BadDebt, Warning, MarketState, safe_decimal
from models.morpho_subgraph import UserPositionsSubgraph
from queries.morpho_queries import GET_USER_MARKET_POSITIONS, GET_MARKETS
from clients.morpho_subgraph_client import MorphoSubgraphClient
from queries.morpho_subgraph import GET_MARKETS_SUBGRAPH
from config.networks import get_network_config
from decimal import Decimal, InvalidOperation
from datetime import datetime

logger = logging.getLogger(__name__)

logger.setLevel(logging.DEBUG)

# Remove hardcoded subgraph URLs
# SUBGRAPH_URLS = { ... }

class MorphoClient:
    # Remove hardcoded API endpoint if legacy fallback is not network specific or removed
    # MORPHO_API_ENDPOINT = "https://blue-api.morpho.org/graphql"
    MAX_RETRIES = 3
    TIMEOUT_SECONDS = 60  # Increased timeout for AWS environment

    # Accept only chain_id
    def __init__(self, chain_id: int):
        self.chain_id = chain_id
        logger.info(f"Initializing MorphoClient for chain ID: {self.chain_id}")

        # Get network specific config
        network_config = get_network_config(self.chain_id) # Handles unsupported chain error

        # Get subgraph URL based on chain_id
        subgraph_url = network_config.get("subgraph_url")
        if not subgraph_url:
             raise ValueError(f"subgraph_url not configured for chain ID: {chain_id}")
        logger.info(f"[{self.chain_id}] Using Subgraph URL: {subgraph_url}")

        # Get legacy API endpoint from config (might be None)
        self.morpho_api_endpoint = network_config.get("morpho_api_url")
        if not self.morpho_api_endpoint:
            logger.warning(f"[{self.chain_id}] morpho_api_url not configured for chain ID {self.chain_id}. Legacy fallback might fail.")
        else:
            logger.info(f"[{self.chain_id}] Using legacy Morpho API endpoint: {self.morpho_api_endpoint}")

        self.connector = TCPConnector(limit=10)
        # Initialize subgraph client with the specific URL
        self.subgraph_client = MorphoSubgraphClient(subgraph_url=subgraph_url)

    async def _execute_query(self, query, variables=None, use_legacy_endpoint: bool = False):
        """Execute a GraphQL query with proper session management.
           Can target legacy endpoint if specified.
        """
        target_url = self.morpho_api_endpoint if use_legacy_endpoint else self.subgraph_client.subgraph_url
        if not target_url:
             error_msg = f"[{self.chain_id}] Target URL is not configured ({'legacy' if use_legacy_endpoint else 'subgraph'})."
             logger.error(error_msg)
             raise ValueError(error_msg)

        logger.debug(f"[{self.chain_id}] Executing query against: {target_url}")
        timeout = ClientTimeout(total=self.TIMEOUT_SECONDS)
        async with ClientSession(connector=self.connector, timeout=timeout) as session:
            transport = AIOHTTPTransport(url=target_url)
            async with Client(
                transport=transport,
                fetch_schema_from_transport=True
            ) as client:
                return await client.execute(query, variable_values=variables)

    async def get_user_positions(self, address: str, chain_id: int = 8453) -> UserMarketData:
        """Fetch user's positions from Morpho API using subgraph client
        
        Args:
            address: User's ethereum address
            chain_id: Chain ID (default: 8453 for Base)
            
        Returns:
            UserMarketData: User's positions and transactions
        """
        # Ensure the correct chain_id is used, overriding default if necessary
        if chain_id != self.chain_id:
            logger.warning(f"[{self.chain_id}] get_user_positions called with chain_id {chain_id}, but client initialized with {self.chain_id}. Using {chain_id}.")
            # Re-initialize subgraph client or handle appropriately if necessary
            # For now, assume subgraph client was initialized correctly for self.chain_id
            # and legacy fallback needs the passed chain_id.
            current_chain_id = chain_id
        else:
            current_chain_id = self.chain_id

        try:
            # Use the subgraph client (already configured for its URL)
            # get_user_positions in subgraph client doesn't need chain_id
            subgraph_positions = await self.subgraph_client.get_user_positions(address)
            
            # Convert subgraph positions to UserMarketData
            if not subgraph_positions.positions:
                logger.info(f"[{self.chain_id}] No positions found in subgraph for {address}, falling back to legacy API")
                # Pass the potentially overridden chain_id to legacy method
                return await self._get_user_positions_legacy(address, current_chain_id)
                
            # Convert the subgraph positions to our internal model
            # This is a simplified conversion - you might need to adapt this
            # to your specific UserMarketData model
            return self._convert_subgraph_to_user_market_data(subgraph_positions, address)
            
        except Exception as e:
            logger.error(f"[{self.chain_id}] Error in subgraph fetch for {address}, falling back to legacy API: {str(e)}")
            # Pass the potentially overridden chain_id to legacy method
            return await self._get_user_positions_legacy(address, current_chain_id)
            
    def _convert_subgraph_to_user_market_data(self, subgraph_data: UserPositionsSubgraph, address: str) -> UserMarketData:
        """Convert subgraph data to UserMarketData format"""
        market_positions = []
        
        for position in subgraph_data.positions:
            # Only include positions with non-zero amounts
            amount = position.get_amount()
            if amount <= 0:
                continue
                
            # Create a MarketPosition object with all required fields
            try:
                # Supply assets and shares for this position
                supply_assets = Decimal(amount) if position.side == "SUPPLIER" else Decimal(0)
                borrow_assets = Decimal(amount) if position.side == "BORROWER" else Decimal(0)
                
                # Handle None values in shares
                shares = position.shares or "0"
                supply_shares = Decimal(shares) if position.side == "SUPPLIER" else Decimal(0)
                borrow_shares = Decimal(shares) if position.side == "BORROWER" else Decimal(0)
                
                # Create PositionState object - the correct way to pass state to MarketPosition
                position_state = PositionState(
                    supply_shares=supply_shares,
                    supply_assets=supply_assets,
                    supply_assets_usd=Decimal(0),  # Placeholder, ideally calculate if price available
                    borrow_shares=borrow_shares,
                    borrow_assets=borrow_assets,
                    borrow_assets_usd=Decimal(0),   # Placeholder, ideally calculate if price available
                )
                
                # Create a minimal Market object with required fields
                market = Market(
                    id=position.market.id,
                    lltv="0",  # Default value
                    unique_key=position.market.id,
                    irm_address="0x0",  # Default value
                    oracle_address="0x0",  # Default value
                    collateral_price="0",  # Default value
                    morpho_blue=MorphoBlue(
                        id="0",
                        address="0x0",
                        chain=Chain(id=self.chain_id) # Use instance chain_id
                    ),
                    oracle_info={},
                    loan_asset=Asset(
                        id=position.asset.id,
                        address=position.asset.id,
                        symbol=position.asset.symbol or "Unknown",
                        name=position.asset.name or "Unknown Token",
                        decimals=position.asset.decimals or 18
                    ),
                    collateral_asset=Asset(
                        id="0x0",  # Default
                        address="0x0",  # Default
                        symbol="Unknown",
                        name="Unknown Token",
                        decimals=18
                    ),
                    state=MarketState.from_dict({
                        'borrowAssets': 0,
                        'supplyAssets': 0,
                        'borrowAssetsUsd': "0",
                        'supplyAssetsUsd': "0",
                        'borrowShares': "0",
                        'supplyShares': "0",
                        'liquidityAssets': 0,
                        'liquidityAssetsUsd': "0",
                        'collateralAssets': "0",
                        'collateralAssetsUsd': "0",
                        'utilization': "0",
                        'supplyApy': position.market.get_supply_rate(),
                        'borrowApy': position.market.get_borrow_rate(),
                        'fee': 0,
                        'timestamp': int(datetime.now().timestamp()),
                        'rateAtUTarget': "0",
                        'monthlySupplyApy': "0",
                        'monthlyBorrowApy': "0",
                        'dailySupplyApy': "0",
                        'dailyBorrowApy': "0",
                        'weeklySupplyApy': "0",
                        'weeklyBorrowApy': "0"
                    }),
                    daily_apys=DailyApys(
                        net_supply_apy=safe_decimal(position.market.get_supply_rate()),
                        net_borrow_apy=safe_decimal(position.market.get_borrow_rate())
                    ),
                    warnings=[],
                    bad_debt=BadDebt(underlying=0, usd=0),
                    realized_bad_debt=BadDebt(underlying=0, usd=0),
                    oracle={}
                )
                
                # Create the MarketPosition with proper objects
                market_position = MarketPosition(
                    state=position_state,
                    market=market,
                    unique_key=position.market.id
                )
                
                market_positions.append(market_position)
            except Exception as e:
                logger.error(f"Error creating MarketPosition: {e}")
                logger.exception("Stack trace:")
        
        # Log the conversion for debugging
        logger.info(f"Converted {len(market_positions)} active positions from subgraph data for {address}")
        
        # Create UserMarketData with all required fields
        return UserMarketData(
            market_positions=market_positions,
            transactions=[]  # The subgraph doesn't provide transactions data
        )

    async def _get_user_positions_legacy(self, address: str, chain_id: int) -> UserMarketData:
        """Legacy method to fetch user's positions from Morpho API
        
        Args:
            address: User's ethereum address
            chain_id: Chain ID (default: 8453 for Base)
            
        Returns:
            UserMarketData: User's positions and transactions
        """
        logger.info(f"[{self.chain_id}] Fetching legacy positions for {address} on chain {chain_id}")
        if not self.morpho_api_endpoint:
             logger.error(f"[{self.chain_id}] Cannot fetch legacy positions, MORPHO_API_URL not configured.")
             return UserMarketData(market_positions=[], transactions=[])

        for attempt in range(self.MAX_RETRIES):
            try:
                query = gql(GET_USER_MARKET_POSITIONS)
                
                result = await self._execute_query(
                    query,
                    variables={"address": address, "chainId": chain_id},
                    use_legacy_endpoint=True # Target legacy API
                )
                
                # Get raw user data
                user_data = result['userByAddress']
                
                # Filter out empty positions before creating UserMarketData
                if 'marketPositions' in user_data:
                    filtered_positions = []
                    for pos in user_data['marketPositions']:
                        
                        # Safer access to state and supplyAssets
                        state = pos.get('state')
                        if state is None:
                            logger.warning(f"Position has None state: {pos}")
                            continue
                            
                        try:
                            supply_assets_raw = state.get('supplyAssets', 0)
                            
                            # Handle the case where supplyAssets is explicitly None
                            supply_assets = 0 if supply_assets_raw is None else int(supply_assets_raw)
                            if supply_assets > 0:
                                filtered_positions.append(pos)
                        except (TypeError, ValueError) as e:
                            logger.error(f"Error processing position supply assets: {e}, position: {pos}")
                            continue

                    user_data['marketPositions'] = filtered_positions
                
                return UserMarketData.from_graphql(user_data)
                
            except asyncio.TimeoutError:
                logger.warning(
                    f"Timeout fetching user positions (attempt {attempt + 1}/{self.MAX_RETRIES})"
                )
                if attempt == self.MAX_RETRIES - 1:
                    logger.error("Max retries reached for fetching user positions")
                    raise
                await asyncio.sleep(1 * (attempt + 1))  # Exponential backoff
                
            except Exception as e:
                logger.error(f"Error fetching user positions from Morpho: {str(e)}")
                logger.exception("Detailed stacktrace:")
                if attempt == self.MAX_RETRIES - 1:
                    raise
                await asyncio.sleep(1 * (attempt + 1))
        
        # Default return with empty data if we exit the loop without returning or raising
        logger.warning(f"Returning empty UserMarketData after all attempts for {address}")
        return UserMarketData(market_positions=[], transactions=[])

    def _convert_subgraph_market_to_market(self, subgraph_market_data: Dict[str, Any]) -> Optional[Market]:
        """Convert raw subgraph market data dictionary to a Market object."""
        try:
            market_id = subgraph_market_data.get('id')
            if not market_id:
                logger.warning("Skipping market due to missing id")
                return None

            # --- Map Assets ---
            loan_asset_data = subgraph_market_data.get('borrowedToken')
            collateral_asset_data = subgraph_market_data.get('inputToken')

            if not loan_asset_data or not collateral_asset_data:
                logger.warning(f"Skipping market {market_id}: Missing loan or collateral asset data")
                return None

            loan_asset = Asset(
                id=loan_asset_data.get('id', '0x'),
                address=loan_asset_data.get('id', '0x'),
                symbol=loan_asset_data.get('symbol', 'Unknown'),
                name=loan_asset_data.get('name', 'Unknown Token'),
                decimals=int(loan_asset_data.get('decimals', 18)),
            )
            collateral_asset = Asset(
                id=collateral_asset_data.get('id', '0x'),
                address=collateral_asset_data.get('id', '0x'),
                symbol=collateral_asset_data.get('symbol', 'Unknown'),
                name=collateral_asset_data.get('name', 'Unknown Token'),
                decimals=int(collateral_asset_data.get('decimals', 18)),
            )

            # --- Extract Prices ---
            # Use alias if defined in query, otherwise default field name
            loan_price_usd = safe_decimal(loan_asset_data.get('lastPriceUsd') or loan_asset_data.get('lastPriceUSD'))
            collateral_price_usd = safe_decimal(collateral_asset_data.get('lastPriceUsd') or collateral_asset_data.get('lastPriceUSD'))
            collateral_price_str = str(collateral_price_usd) # For Market.collateral_price

            # --- Extract Raw Amounts/Shares ---
            total_supply_assets_raw = safe_decimal(subgraph_market_data.get('totalSupply', '0'))
            total_borrow_assets_raw = safe_decimal(subgraph_market_data.get('totalBorrow', '0'))
            total_collateral_assets_raw = safe_decimal(subgraph_market_data.get('totalCollateral', '0'))
            total_supply_shares_raw = safe_decimal(subgraph_market_data.get('totalSupplyShares', '0'))
            total_borrow_shares_raw = safe_decimal(subgraph_market_data.get('totalBorrowShares', '0'))

            # --- Calculate Derived Values ---
            liquidity_assets = total_supply_assets_raw - total_borrow_assets_raw
            utilization = (total_borrow_assets_raw / total_supply_assets_raw) if total_supply_assets_raw > 0 else Decimal(0)

            # --- Calculate USD Values ---
            supply_assets_usd = total_supply_assets_raw * loan_price_usd
            borrow_assets_usd = total_borrow_assets_raw * loan_price_usd
            liquidity_assets_usd = liquidity_assets * loan_price_usd
            collateral_assets_usd = total_collateral_assets_raw * collateral_price_usd

            # --- Extract APYs ---
            rates = subgraph_market_data.get('rates', [])
            supply_apy = Decimal(0)
            borrow_apy = Decimal(0)
            for rate in rates:
                side = rate.get('side', '').upper()
                apy_value = safe_decimal(rate.get('rate'))
                if side in ('SUPPLIER', 'LENDER'): # Handle both potential side names
                    supply_apy = apy_value
                elif side == 'BORROWER':
                    borrow_apy = apy_value

            # --- Extract Other Fields ---
            lltv = safe_decimal(subgraph_market_data.get('lltv', '0'))
            fee_raw = safe_decimal(subgraph_market_data.get('fee', '0'))
            # Assuming fee is in basis points (check subgraph schema)
            fee = fee_raw / Decimal(10000)
            timestamp = int(subgraph_market_data.get('lastUpdate', 0))
            irm_address = subgraph_market_data.get('irm', '0x')
            oracle_address = subgraph_market_data.get('oracleAddress', '0x') # Use direct field if available

            # --- Construct MarketState ---
            # Note: Some fields like rateAtUTarget are not directly available from this subgraph query
            market_state_data = {
                'borrowAssets': str(total_borrow_assets_raw),
                'supplyAssets': str(total_supply_assets_raw),
                'borrowAssetsUsd': str(borrow_assets_usd),
                'supplyAssetsUsd': str(supply_assets_usd),
                'borrowShares': str(total_borrow_shares_raw),
                'supplyShares': str(total_supply_shares_raw),
                'liquidityAssets': str(liquidity_assets),
                'liquidityAssetsUsd': str(liquidity_assets_usd),
                'collateralAssets': str(total_collateral_assets_raw),
                'collateralAssetsUsd': str(collateral_assets_usd),
                'utilization': str(utilization),
                'supplyApy': str(supply_apy),
                'borrowApy': str(borrow_apy),
                'fee': str(fee),
                'timestamp': timestamp,
                'rateAtUTarget': "0", # Default or placeholder
                 # Assuming APYs from subgraph are annualized; set daily/weekly/monthly to the same for now
                'dailySupplyApy': str(supply_apy),
                'dailyBorrowApy': str(borrow_apy),
                'weeklySupplyApy': str(supply_apy), # Placeholder
                'weeklyBorrowApy': str(borrow_apy), # Placeholder
                'monthlySupplyApy': str(supply_apy), # Placeholder
                'monthlyBorrowApy': str(borrow_apy), # Placeholder
            }
            market_state = MarketState.from_dict(market_state_data)

            # --- Construct DailyApys ---
            daily_apys = DailyApys(
                net_supply_apy=supply_apy,
                net_borrow_apy=borrow_apy
            )

            # --- Construct MorphoBlue ---
            # Subgraph query doesn't seem to include protocol details directly
            # Using defaults for now
            morpho_blue = MorphoBlue(
                id="morphoBlueV1", # Default/Placeholder
                address="0xBBBBBbbBBBBBbbBbbBBbbBBBbBBbbBBbBbbBBbB", # Default/Placeholder Morpho Blue address
                chain=Chain(id=self.chain_id) # Use instance chain_id
            )

            # --- Construct Market ---
            # Placeholder for warnings, bad debt, oracle info as they aren't in the base query
            market = Market(
                id=market_id,
                unique_key=market_id,
                lltv=str(lltv),
                irm_address=irm_address,
                oracle_address=oracle_address,
                collateral_price=collateral_price_str,
                morpho_blue=morpho_blue,
                oracle_info={}, # Placeholder
                loan_asset=loan_asset,
                collateral_asset=collateral_asset,
                state=market_state,
                daily_apys=daily_apys,
                warnings=[], # Placeholder
                bad_debt=BadDebt(underlying=0, usd=0), # Placeholder - Use int 0
                realized_bad_debt=BadDebt(underlying=0, usd=0), # Placeholder - Use int 0
                oracle={} # Placeholder - Map from subgraph's oracle field if needed
            )
            return market

        except (InvalidOperation, TypeError, ValueError, KeyError, AttributeError) as e:
            logger.error(f"Error converting subgraph market data {subgraph_market_data.get('id', 'UNKNOWN')}: {e}")
            logger.debug(f"Subgraph data causing conversion error: {subgraph_market_data}")
            return None
        except Exception as e: # Catch any other unexpected errors during conversion
             logger.error(f"Unexpected error converting subgraph market data {subgraph_market_data.get('id', 'UNKNOWN')}: {e}")
             logger.exception("Stack trace for conversion error:")
             return None

    async def get_markets(self, first: int = 1000, chain_id: Optional[int] = None) -> List[Market]:
        """Fetch markets, prioritizing the subgraph and falling back to the legacy API.

        Args:
            first: Number of markets to fetch (max 1000 for subgraph).
            chain_id: Chain ID to fetch for. If None, uses the client's initialized chain_id.

        Returns:
            List[Market]: List of markets.
        """
        current_chain_id = chain_id if chain_id is not None else self.chain_id
        if chain_id is not None and chain_id != self.chain_id:
             logger.warning(f"[{self.chain_id}] get_markets called with chain_id {chain_id}, but client initialized with {self.chain_id}. Fetching for {chain_id}.")
             # This implies the subgraph_client might be for the wrong network if we proceed.
             # For simplicity now, we assume the call to subgraph_client.get_markets will handle this,
             # or we rely on the legacy fallback for the overridden chain_id.
        else:
             logger.info(f"[{self.chain_id}] Attempting to fetch markets (first={first}, chain_id={current_chain_id})")

        try:
            # Pass chain_id to subgraph client's get_markets
            subgraph_markets_data = await self.subgraph_client.get_markets(first=first, chain_id=current_chain_id)

            if subgraph_markets_data:
                markets = []
                for market_data in subgraph_markets_data:
                    # Conversion helper now uses self.chain_id implicitly
                    market = self._convert_subgraph_market_to_market(market_data)
                    if market:
                        markets.append(market)

                if markets:
                     logger.info(f"[{self.chain_id}] Successfully fetched and converted {len(markets)} markets from subgraph for chain {current_chain_id}.")
                     return markets
                else:
                    logger.warning(f"[{self.chain_id}] Subgraph returned data for chain {current_chain_id}, but conversion resulted in zero markets.")
            else:
                 logger.warning(f"[{self.chain_id}] Subgraph client returned no market data for chain {current_chain_id}.")

        except Exception as e:
            logger.error(f"[{self.chain_id}] Error fetching or processing markets from subgraph for chain {current_chain_id}: {str(e)}")
            logger.exception("Subgraph fetch/processing stack trace:")

        # Fallback to legacy API if subgraph fails or returns no usable data
        logger.warning(f"[{self.chain_id}] Falling back to legacy API to fetch markets for chain {current_chain_id}.")
        return await self._get_markets_legacy(first=first, chain_id=current_chain_id)

    async def _get_markets_legacy(self, chain_id: int, first: int = 100) -> List[Market]:
        """Fetch all markets from Morpho legacy API (used as fallback)

        Args:
            chain_id: Chain ID (required).
            first: Number of markets to fetch (max 100 for legacy API).

        Returns:
            List[Market]: List of markets
        """
        logger.info(f"[{self.chain_id}] Fetching legacy markets (first={first}) for chain {chain_id}")
        if not self.morpho_api_endpoint:
             logger.error(f"[{self.chain_id}] Cannot fetch legacy markets, MORPHO_API_URL not configured.")
             return []

        for attempt in range(self.MAX_RETRIES):
            try:
                logger.debug(f"[{self.chain_id}] Fetching legacy markets (attempt {attempt + 1}) for chain {chain_id}")
                query = gql(GET_MARKETS)

                result = await self._execute_query(
                    query,
                    variables={
                        "first": first,
                        "where": {"whitelisted": True, "chainId_in": [chain_id]} # Use provided chain_id
                    },
                    use_legacy_endpoint=True # Target legacy API
                )

                logger.debug(f"[{self.chain_id}] Legacy markets API response received for chain {chain_id}, checking structure")
                if not result:
                    logger.error("Legacy API returned None result")
                    raise ValueError("Legacy API returned None result")

                if 'markets' not in result:
                    logger.error(f"Missing 'markets' key in legacy API result. Got keys: {result.keys()}")
                    raise ValueError(f"Missing 'markets' key in legacy API result")

                if 'items' not in result['markets']:
                    logger.error(f"Missing 'items' key in legacy markets result. Got keys: {result['markets'].keys()}")
                    raise ValueError(f"Missing 'items' key in legacy markets result")

                markets_data = result['markets']['items']
                logger.debug(f"[{self.chain_id}] Found {len(markets_data)} legacy markets in API response")
                markets = []

                for i, market_data in enumerate(markets_data):
                    try:
                        # Skip markets with no collateral asset (not yet initialized)
                        if not market_data.get('collateralAsset'):
                            logger.debug(f"[{self.chain_id}] Skipping legacy market {i} - missing collateralAsset")
                            continue

                        # Flag to track if we should skip this market
                        skip_market = False

                        # Check for any None values in critical fields
                        for field in ['loanAsset', 'state', 'dailyApys']:
                            if market_data.get(field) is None:
                                logger.warning(f"[{self.chain_id}] Legacy market {i} has None {field}, skipping")
                                skip_market = True
                                break

                        # Special handling for badDebt and realizedBadDebt - allow them to be None
                        # but replace with default values
                        if market_data.get('badDebt') is None:
                            logger.warning(f"[{self.chain_id}] Legacy market {i} has None badDebt, using default")
                            market_data['badDebt'] = {'underlying': 0, 'usd': 0}

                        if market_data.get('realizedBadDebt') is None:
                            logger.warning(f"[{self.chain_id}] Legacy market {i} has None realizedBadDebt, using default")
                            market_data['realizedBadDebt'] = {'underlying': 0, 'usd': 0}

                        # Check nested fields to prevent None subscript errors
                        if not skip_market:
                            for field, nested_fields in {
                                'morphoBlue': ['id', 'address', 'chain'],
                                'loanAsset': ['id', 'address', 'symbol', 'name', 'decimals'],
                                'collateralAsset': ['id', 'address', 'symbol', 'name', 'decimals'],
                                'dailyApys': ['netSupplyApy', 'netBorrowApy']
                            }.items():
                                if field not in market_data or market_data[field] is None:
                                    logger.warning(f"[{self.chain_id}] Legacy market {i} has None {field}, skipping")
                                    skip_market = True
                                    break

                                for nested_field in nested_fields:
                                    if nested_field not in market_data[field] or market_data[field][nested_field] is None:
                                        logger.warning(f"[{self.chain_id}] Legacy market {i} has None {field}.{nested_field}, skipping")
                                        skip_market = True
                                        break

                                if skip_market:
                                    break

                        # Check for morphoBlue.chain.id specially since it's deeply nested
                        if not skip_market and (
                            not market_data.get('morphoBlue') or
                            not market_data['morphoBlue'].get('chain') or
                            not market_data['morphoBlue']['chain'].get('id')):
                            logger.warning(f"[{self.chain_id}] Legacy market {i} has missing morphoBlue.chain.id, skipping")
                            skip_market = True

                        # If any validation failed, skip this market
                        if skip_market:
                            logger.debug(f"[{self.chain_id}] Skipping legacy market {i} due to validation failures")
                            continue

                        logger.debug(f"[{self.chain_id}] Processing legacy market {i}: {market_data.get('uniqueKey', 'unknown key')}")

                        # Create Market object using the factory method
                        market = Market.from_api(market_data)
                        markets.append(market)

                    except Exception as e:
                        logger.error(f"[{self.chain_id}] Error processing legacy market {i}: {str(e)}")
                        logger.debug(f"Legacy market data that caused error: {market_data}")
                        # Continue processing other markets

                logger.info(f"[{self.chain_id}] Successfully processed {len(markets)} legacy markets")
                return markets # Return successfully processed markets

            except asyncio.TimeoutError:
                logger.warning(
                    f"[{self.chain_id}] Timeout fetching legacy markets (attempt {attempt + 1}/{self.MAX_RETRIES})"
                )
                if attempt == self.MAX_RETRIES - 1:
                    logger.error("Max retries reached for fetching legacy markets")
                    # raise # Re-raise timeout after retries
                    break # Exit loop if max retries reached
                await asyncio.sleep(1 * (attempt + 1))

            except Exception as e:
                logger.error(f"[{self.chain_id}] Error fetching legacy markets from Morpho: {str(e)}")
                logger.exception("Legacy stack trace:")
                if attempt == self.MAX_RETRIES - 1:
                    # raise # Re-raise exception after retries
                    break # Exit loop if max retries reached
                await asyncio.sleep(1 * (attempt + 1))

        # Corrected indentation for the final return
        # Default return with empty list if we exit the loop without returning or raising
        logger.warning(f"[{self.chain_id}] Returning empty markets list after all attempts in legacy fallback for chain {chain_id}")
        return [] # Ensure return [] is always reached if loop finishes without success

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.connector.close()
