import os
import logging
from typing import List
from gql import gql, Client
from gql.transport.aiohttp import AIOHTTPTransport
from models.user_data import UserAuthorization
from queries.monarch_queries import GET_AUTHORIZED_USERS

logger = logging.getLogger(__name__)

class MonarchClient:
    SUBQUERY_ENDPOINT = "https://api.subquery.network/sq/antoncoding/monarch-agent-base"
    
    def __init__(self):
        self.transport = AIOHTTPTransport(url=self.SUBQUERY_ENDPOINT)
        self.client = Client(transport=self.transport, fetch_schema_from_transport=True)

    async def get_authorized_users(self, rebalancer_address: str) -> List[UserAuthorization]:
        """Fetch users who have authorized the bot from Monarch Subquery
        
        Args:
            rebalancer_address: The address of the rebalancer contract
            
        Returns:
            List[UserAuthorization]: List of users and their market caps
        """
        try:
            query = gql(GET_AUTHORIZED_USERS)
            
            # Execute the query with variables
            result = await self.client.execute_async(
                query,
                variable_values={"rebalancer": rebalancer_address}
            )
            
            # Parse the response into our data structures
            users_data = result['users']['nodes']
            return [UserAuthorization.from_graphql(user_data) for user_data in users_data]
            
        except Exception as e:
            logger.error(f"Error fetching authorized users from Monarch: {str(e)}")
            return []
