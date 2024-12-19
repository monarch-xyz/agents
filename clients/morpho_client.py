import os
import logging
from gql import gql, Client
from gql.transport.aiohttp import AIOHTTPTransport
from models.morpho_data import UserMarketData
from queries.morpho_queries import GET_USER_MARKET_POSITIONS

logger = logging.getLogger(__name__)

class MorphoClient:
    MORPHO_API_ENDPOINT = "https://blue-api.morpho.org/graphql"  # TODO: Move to config if needed
    
    def __init__(self):
        self.transport = AIOHTTPTransport(url=self.MORPHO_API_ENDPOINT)
        self.client = Client(transport=self.transport, fetch_schema_from_transport=True)

    async def get_user_positions(self, address: str, chain_id: int = 1) -> UserMarketData:
        """Fetch user's positions from Morpho API
        
        Args:
            address: User's ethereum address
            chain_id: Chain ID (default: 1 for Ethereum mainnet)
            
        Returns:
            UserMarketData: User's positions and transactions
        """
        try:
            query = gql(GET_USER_MARKET_POSITIONS)
            
            result = await self.client.execute_async(
                query,
                variable_values={"address": address, "chainId": chain_id}
            )
            
            return UserMarketData.from_graphql(result['userByAddress'])
            
        except Exception as e:
            logger.error(f"Error fetching user positions from Morpho: {str(e)}")
            raise
