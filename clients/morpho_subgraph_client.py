import os
import logging
import asyncio
from typing import List, Optional, Dict, Any
from gql import gql, Client
from gql.transport.aiohttp import AIOHTTPTransport
from aiohttp import ClientTimeout, TCPConnector, ClientSession
from models.morpho_subgraph import UserPositionsSubgraph
from queries.morpho_subgraph import GET_USER_POSITIONS_SUBGRAPH

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)

class MorphoSubgraphClient:
    # Base subgraph URL for Morpho on Base network
    MORPHO_SUBGRAPH_URL = "https://gateway.thegraph.com/api/subgraphs/id/71ZTy1veF9twER9CLMnPWeLQ7GZcwKsjmygejrgKirqs"
    MAX_RETRIES = 3
    TIMEOUT_SECONDS = 60
    
    def __init__(self):
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
                url=self.MORPHO_SUBGRAPH_URL,
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
    
    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.connector.close() 