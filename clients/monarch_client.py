import os
import logging
from gql import gql, Client
from gql.transport.aiohttp import AIOHTTPTransport

logger = logging.getLogger(__name__)

class MonarchClient:
    def __init__(self):
        endpoint = os.getenv('MONARCH_SUBQUERY_ENDPOINT')
        self.transport = AIOHTTPTransport(url=endpoint)
        self.client = Client(transport=self.transport, fetch_schema_from_transport=True)

    async def get_authorized_users(self):
        """Fetch users who have authorized the bot from Monarch Subquery"""
        try:
            # Define your GraphQL query
            query = gql("""
                query GetAuthorizedUsers {
                    authorizedUsers {
                        address
                        timestamp
                    }
                }
            """)
            
            # Execute the query
            result = await self.client.execute_async(query)
            return [user['address'] for user in result.get('authorizedUsers', [])]
            
        except Exception as e:
            logger.error(f"Error fetching authorized users from Monarch: {str(e)}")
            return []
