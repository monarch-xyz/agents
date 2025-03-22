import os
import logging
import asyncio
from typing import List, Optional, Dict
from gql import gql, Client
from gql.transport.aiohttp import AIOHTTPTransport
from aiohttp import ClientTimeout, TCPConnector, ClientSession
from models.morpho_data import UserMarketData, Market, MarketPosition, PositionState, Asset, Chain, MorphoBlue, DailyApys, BadDebt, Warning, MarketState
from models.morpho_subgraph import UserPositionsSubgraph
from queries.morpho_queries import GET_USER_MARKET_POSITIONS, GET_MARKETS
from clients.morpho_subgraph_client import MorphoSubgraphClient
from decimal import Decimal
from datetime import datetime

logger = logging.getLogger(__name__)

logger.setLevel(logging.DEBUG)

class MorphoClient:
    MORPHO_API_ENDPOINT = "https://blue-api.morpho.org/graphql"  # TODO: Move to config if needed
    MAX_RETRIES = 3
    TIMEOUT_SECONDS = 60  # Increased timeout for AWS environment
    
    def __init__(self):
        self.connector = TCPConnector(limit=10)
        self.subgraph_client = MorphoSubgraphClient()

    async def _execute_query(self, query, variables=None):
        """Execute a GraphQL query with proper session management"""
        timeout = ClientTimeout(total=self.TIMEOUT_SECONDS)
        async with ClientSession(connector=self.connector, timeout=timeout) as session:
            transport = AIOHTTPTransport(
                url=self.MORPHO_API_ENDPOINT,
            )
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
        try:
            # Use the subgraph client to get positions
            subgraph_positions = await self.subgraph_client.get_user_positions(address)
            
            # Convert subgraph positions to UserMarketData
            # This requires some mapping between the two models
            # For now, just return the legacy method as a fallback
            if not subgraph_positions.positions:
                logger.info(f"No positions found in subgraph for {address}, falling back to legacy API")
                return await self._get_user_positions_legacy(address, chain_id)
                
            # Convert the subgraph positions to our internal model
            # This is a simplified conversion - you might need to adapt this
            # to your specific UserMarketData model
            return self._convert_subgraph_to_user_market_data(subgraph_positions, address)
            
        except Exception as e:
            logger.error(f"Error in subgraph fetch, falling back to legacy API: {str(e)}")
            return await self._get_user_positions_legacy(address, chain_id)
            
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
                supply_shares = Decimal(position.shares) if position.side == "SUPPLIER" else Decimal(0)
                borrow_shares = Decimal(position.shares) if position.side == "BORROWER" else Decimal(0)
                
                # Create PositionState object - the correct way to pass state to MarketPosition
                position_state = PositionState(
                    supply_shares=supply_shares,
                    supply_assets=supply_assets,
                    supply_assets_usd=Decimal(0),  # We don't have USD value from subgraph
                    borrow_shares=borrow_shares,
                    borrow_assets=borrow_assets,
                    borrow_assets_usd=Decimal(0)   # We don't have USD value from subgraph
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
                        chain=Chain(id=8453)  # Base chain ID
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
                        net_supply_apy=Decimal(position.market.get_supply_rate()),
                        net_borrow_apy=Decimal(position.market.get_borrow_rate())
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

    async def _get_user_positions_legacy(self, address: str, chain_id: int = 8453) -> UserMarketData:
        """Legacy method to fetch user's positions from Morpho API
        
        Args:
            address: User's ethereum address
            chain_id: Chain ID (default: 8453 for Base)
            
        Returns:
            UserMarketData: User's positions and transactions
        """
        for attempt in range(self.MAX_RETRIES):
            try:
                query = gql(GET_USER_MARKET_POSITIONS)
                
                result = await self._execute_query(
                    query,
                    variables={"address": address, "chainId": chain_id}
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

    async def get_markets(self, first: int = 100) -> List[Market]:
        """Fetch all markets from Morpho API
        
        Args:
            chain_id: Chain ID (default: 1 for Ethereum mainnet)
            first: Number of markets to fetch (default: 100)
            
        Returns:
            List[Market]: List of markets
        """
        for attempt in range(self.MAX_RETRIES):
            try:
                query = gql(GET_MARKETS)
                
                result = await self._execute_query(
                    query,
                    variables={
                        "first": first,
                        "where": {"whitelisted": True, "chainId_in": [8453]}
                    }
                )
                
                markets_data = result['markets']['items']
                markets = []
                
                for market_data in markets_data:
                    # Skip markets with no collateral asset (not yet initialized)
                    if not market_data.get('collateralAsset'):
                        continue
                        
                    market = Market(
                        id=market_data['id'],
                        lltv=market_data['lltv'],
                        unique_key=market_data['uniqueKey'],
                        irm_address=market_data['irmAddress'],
                        oracle_address=market_data['oracleAddress'],
                        collateral_price=market_data['collateralPrice'],
                        morpho_blue=market_data['morphoBlue'],
                        oracle_info=market_data['oracleInfo'],
                        loan_asset=market_data['loanAsset'],
                        collateral_asset=market_data['collateralAsset'],
                        state=market_data['state'],
                        daily_apys=market_data['dailyApys'],
                        warnings=market_data['warnings'],
                        bad_debt=market_data['badDebt'],
                        realized_bad_debt=market_data['realizedBadDebt'],
                        oracle=market_data['oracle']
                    )
                    markets.append(market)
                
                return markets
                
            except asyncio.TimeoutError:
                logger.warning(
                    f"Timeout fetching markets (attempt {attempt + 1}/{self.MAX_RETRIES})"
                )
                if attempt == self.MAX_RETRIES - 1:
                    logger.error("Max retries reached for fetching markets")
                    raise
                await asyncio.sleep(1 * (attempt + 1))
                
            except Exception as e:
                logger.error(f"Error fetching markets from Morpho: {str(e)}")
                if attempt == self.MAX_RETRIES - 1:
                    raise
                await asyncio.sleep(1 * (attempt + 1))

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.connector.close()
