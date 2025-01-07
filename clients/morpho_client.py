import os
import logging
import asyncio
from typing import List, Optional, Dict
from gql import gql, Client
from gql.transport.aiohttp import AIOHTTPTransport
from aiohttp import ClientTimeout, TCPConnector, ClientSession
from models.morpho_data import UserMarketData, Market, MarketPosition
from queries.morpho_queries import GET_USER_MARKET_POSITIONS, GET_MARKETS

logger = logging.getLogger(__name__)

class MorphoClient:
    MORPHO_API_ENDPOINT = "https://blue-api.morpho.org/graphql"  # TODO: Move to config if needed
    MAX_RETRIES = 3
    TIMEOUT_SECONDS = 60  # Increased timeout for AWS environment
    
    def __init__(self):
        self.connector = TCPConnector(limit=10)

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
        """Fetch user's positions from Morpho API
        
        Args:
            address: User's ethereum address
            chain_id: Chain ID (default: 1 for Ethereum mainnet)
            
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
                        supply_assets = int(pos.get('supplyAssets', 0))
                        logger.debug(
                            f"Position {pos['market']['uniqueKey'][:10]} has "
                            f"supplyAssets: {supply_assets}"
                        )
                        if supply_assets > 0:
                            filtered_positions.append(pos)

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
