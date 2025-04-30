import os
import logging
import asyncio
from typing import List, Optional, Dict, Any
from gql import gql, Client
from gql.transport.aiohttp import AIOHTTPTransport
from aiohttp import ClientTimeout, TCPConnector, ClientSession
from models.morpho_subgraph import UserPositionsSubgraph
from queries.morpho_subgraph import GET_USER_POSITIONS_SUBGRAPH, GET_MARKETS_SUBGRAPH

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)

class MorphoSubgraphClient:
    MAX_RETRIES = 3
    TIMEOUT_SECONDS = 60

    # Accept subgraph_url in constructor
    def __init__(self, subgraph_url: str):
        if not subgraph_url:
             raise ValueError("Subgraph URL must be provided to MorphoSubgraphClient")
        self.subgraph_url = subgraph_url # Store the URL
        logger.info(f"Initialized MorphoSubgraphClient with URL: {self.subgraph_url}")

        self.connector = TCPConnector(limit=10)
        # Get API key from environment variable
        self.api_key = os.getenv("GRAPH_API_KEY")
        if not self.api_key:
            logger.warning("GRAPH_API_KEY environment variable not set. Subgraph queries may fail.")

    async def _execute_query(self, query, variables=None):
        """Execute a GraphQL query with proper session management"""
        timeout = ClientTimeout(total=self.TIMEOUT_SECONDS)
        
        # Add authorization header if API key is available
        headers = {}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
            
        async with ClientSession(connector=self.connector, timeout=timeout) as session:
            transport = AIOHTTPTransport(
                url=self.subgraph_url, # Use the instance URL
                headers=headers
            )
            async with Client(
                transport=transport,
                fetch_schema_from_transport=True
            ) as client:
                return await client.execute(query, variable_values=variables)

    async def get_user_positions(self, address: str) -> UserPositionsSubgraph:
        """Fetch user's positions from Morpho subgraph
        
        Args:
            address: User's ethereum address
            
        Returns:
            UserPositionsSubgraph: User's positions parsed from subgraph data
        """
        address = address.lower()  # normalize address
        
        for attempt in range(self.MAX_RETRIES):
            try:
                query = gql(GET_USER_POSITIONS_SUBGRAPH)
                
                result = await self._execute_query(
                    query,
                    variables={"userAddress": address}
                )
                
                logger.debug(f"Received subgraph data for {address}")
                
                # Parse the response into our model
                user_positions = UserPositionsSubgraph.from_graphql(result)
                
                # Log positions count
                position_count = len(user_positions.positions)
                logger.info(f"Found {position_count} positions for user {address}")
                
                # Log active positions with non-zero amounts
                active_positions = [
                    pos for pos in user_positions.positions 
                    if pos.get_amount() > 0
                ]
                
                logger.info(f"User {address} has {len(active_positions)} active positions")
                
                return user_positions
                
            except asyncio.TimeoutError:
                logger.warning(
                    f"Timeout fetching user positions from subgraph (attempt {attempt + 1}/{self.MAX_RETRIES})"
                )
                if attempt == self.MAX_RETRIES - 1:
                    logger.error("Max retries reached for fetching user positions from subgraph")
                    raise
                await asyncio.sleep(1 * (attempt + 1))
                
            except Exception as e:
                logger.error(f"Error fetching user positions from Morpho subgraph: {str(e)}")
                logger.exception("Detailed stacktrace:")
                if attempt == self.MAX_RETRIES - 1:
                    raise
                await asyncio.sleep(1 * (attempt + 1))
        
        # Default return if we exit the for loop without returning or raising
        logger.warning(f"Returning empty UserPositionsSubgraph after all attempts for {address}")
        # Create an empty UserPositionsSubgraph with no positions
        return UserPositionsSubgraph(positions=[])
    
    async def get_markets(self, first: int = 1000, chain_id: int = 8453) -> List[Dict[str, Any]]:
        """Fetch markets from the Morpho subgraph.

        Args:
            first: Maximum number of markets to fetch.
            chain_id: Chain ID to filter markets (currently ignored by query, but kept for consistency).

        Returns:
            List[Dict[str, Any]]: Raw list of market data dictionaries from the subgraph.
        """
        # Note: chain_id filtering needs to be added to the GQL query or handled post-fetch if subgraph supports it.
        # Currently, the WHERE clause in GET_MARKETS_SUBGRAPH is basic.
        variables = {
            "first": first,
            "where": {}
        }

        for attempt in range(self.MAX_RETRIES):
            try:
                query = gql(GET_MARKETS_SUBGRAPH) # Use the new query
                logger.debug(f"Executing subgraph markets query (attempt {attempt + 1}): variables={variables}")
                result = await self._execute_query(query, variables=variables)

                if not result or 'markets' not in result:
                    logger.warning(f"Subgraph query attempt {attempt + 1} returned no 'markets' data.")
                    # Don't retry immediately if the structure is wrong, might be a query/schema issue
                    if attempt == self.MAX_RETRIES - 1:
                         logger.error("Max retries reached, subgraph query failed to return market data.")
                         return [] # Return empty list on failure after retries
                    await asyncio.sleep(1 * (attempt + 1))
                    continue # Go to next attempt

                markets_data = result['markets']
                logger.info(f"Successfully fetched {len(markets_data)} raw markets from subgraph (attempt {attempt + 1})")
                return markets_data # Return the raw list of dicts

            except asyncio.TimeoutError:
                logger.warning(
                    f"Timeout fetching markets from subgraph (attempt {attempt + 1}/{self.MAX_RETRIES})"
                )
                if attempt == self.MAX_RETRIES - 1:
                    logger.error("Max retries reached for fetching markets from subgraph")
                    return [] # Return empty list on timeout after retries
                await asyncio.sleep(1 * (attempt + 1))

            except Exception as e:
                logger.error(f"Error fetching markets from Morpho subgraph: {str(e)}")
                logger.exception("Detailed stacktrace:")
                if attempt == self.MAX_RETRIES - 1:
                     logger.error("Max retries reached after exception fetching markets from subgraph")
                     return [] # Return empty list on exception after retries
                await asyncio.sleep(1 * (attempt + 1))

        logger.error("Exited market fetch loop unexpectedly, returning empty list.")
        return [] # Should not be reached if logic is correct, but acts as safety net

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.connector.close() 