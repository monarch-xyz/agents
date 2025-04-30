import os
import logging
import asyncio
from typing import List, Optional
from gql import gql, Client
from gql.transport.aiohttp import AIOHTTPTransport
from aiohttp import ClientTimeout, TCPConnector, ClientSession
from models.user_data import UserAuthorization
from queries.monarch_queries import GET_AUTHORIZED_USERS
from config.networks import get_monarch_subgraph_url

logger = logging.getLogger(__name__)

class MonarchClient:
    MAX_RETRIES = 3
    TIMEOUT_SECONDS = 30
    
    def __init__(self, chain_id: int):
        self.chain_id = chain_id
        logger.info(f"Initializing MonarchClient for chain ID: {self.chain_id}")

        self.subquery_endpoint = get_monarch_subgraph_url(self.chain_id)
        logger.info(f"[{self.chain_id}] Using Monarch Subgraph URL: {self.subquery_endpoint}")

        self.connector = TCPConnector(limit=10)

    async def _execute_query(self, query, variables=None):
        """Execute a GraphQL query with proper session management"""
        timeout = ClientTimeout(total=self.TIMEOUT_SECONDS)
        async with ClientSession(connector=self.connector, timeout=timeout) as session:
            transport = AIOHTTPTransport(
                url=self.subquery_endpoint,
            )
            async with Client(
                transport=transport,
                fetch_schema_from_transport=True
            ) as client:
                return await client.execute(query, variable_values=variables)

    async def get_authorized_users(self, rebalancer_address: str, chain_id: Optional[int] = None) -> List[UserAuthorization]:
        """Fetch users who have authorized the bot from Monarch Subquery
        
        Args:
            rebalancer_address: The address of the rebalancer contract
            chain_id: The chain ID to fetch users for (currently unused by query).
            
        Returns:
            List[UserAuthorization]: List of users and their market caps
        """
        logger.info(f"Fetching authorized users for rebalancer {rebalancer_address} (Chain ID: {chain_id or 'any'})")
        query = gql(GET_AUTHORIZED_USERS)
        
        for attempt in range(self.MAX_RETRIES):
            try:
                # Execute the query with variables
                result = await self._execute_query(
                    query,
                    variables={"rebalancer": rebalancer_address}
                )
                
                # Parse the response into our data structures
                users_data = result['users']
                return [UserAuthorization.from_graphql(user_data) for user_data in users_data]
                
            except asyncio.TimeoutError:
                logger.warning(
                    f"Timeout fetching authorized users (attempt {attempt + 1}/{self.MAX_RETRIES})"
                )
                if attempt == self.MAX_RETRIES - 1:
                    logger.error("Max retries reached for fetching authorized users")
                    return []
                await asyncio.sleep(1 * (attempt + 1))  # Exponential backoff
                
            except Exception as e:
                logger.error(
                    f"Error fetching authorized users from Monarch (attempt {attempt + 1}): {str(e)}"
                )
                if attempt == self.MAX_RETRIES - 1:
                    return []
                await asyncio.sleep(1 * (attempt + 1))  # Exponential backoff
        
        # Default return if we exit the for loop without returning
        return []

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.connector.close()
