import os
import logging
from typing import List, Optional, Dict
from gql import gql, Client
from gql.transport.aiohttp import AIOHTTPTransport
from models.morpho_data import UserMarketData, Market
from queries.morpho_queries import GET_USER_MARKET_POSITIONS, GET_MARKETS

logger = logging.getLogger(__name__)

class MorphoClient:
    MORPHO_API_ENDPOINT = "https://blue-api.morpho.org/graphql"  # TODO: Move to config if needed
    
    def __init__(self):
        self.transport = AIOHTTPTransport(url=self.MORPHO_API_ENDPOINT)
        self.client = Client(transport=self.transport, fetch_schema_from_transport=True)

    async def get_user_positions(self, address: str, chain_id: 8453) -> UserMarketData:
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
            
    async def get_markets(self, first: int = 100) -> List[Market]:
        """Fetch all markets from Morpho API
        
        Args:
            chain_id: Chain ID (default: 1 for Ethereum mainnet)
            first: Number of markets to fetch (default: 100)
            
        Returns:
            List[Market]: List of markets
        """
        try:
            query = gql(GET_MARKETS)
            
            result = await self.client.execute_async(
                query,
                variable_values={
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
            
        except Exception as e:
            logger.error(f"Error fetching markets from Morpho: {str(e)}")
            raise
