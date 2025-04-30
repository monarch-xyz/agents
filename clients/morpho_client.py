import os
import logging
import asyncio
from typing import List, Optional, Dict, Any
from aiohttp import TCPConnector
from models.morpho_data import UserMarketData, Market, MarketPosition, PositionState, Asset, Chain, MorphoBlue, DailyApys, BadDebt, Warning, MarketState, safe_decimal
from models.morpho_subgraph import UserPositionsSubgraph
from clients.morpho_subgraph_client import MorphoSubgraphClient
from config.networks import get_network_config, get_morpho_subgraph_url
from decimal import Decimal, InvalidOperation
from datetime import datetime

logger = logging.getLogger(__name__)

logger.setLevel(logging.DEBUG)

class MorphoClient:
    # Removed commented out legacy endpoint definition
    MAX_RETRIES = 3
    TIMEOUT_SECONDS = 60  # Increased timeout for AWS environment

    # Accept only chain_id
    def __init__(self, chain_id: int):
        self.chain_id = chain_id
        logger.info(f"Initializing MorphoClient for chain ID: {self.chain_id}")

        network_config = get_network_config(self.chain_id)
        # Use the helper function to get the Morpho subgraph URL
        subgraph_url = get_morpho_subgraph_url(self.chain_id)
        logger.info(f"[{self.chain_id}] Using Morpho Subgraph URL: {subgraph_url[:40]}...") # Log prefix

        self.subgraph_client = MorphoSubgraphClient(subgraph_url=subgraph_url)

    async def get_user_positions(self, address: str, chain_id: Optional[int] = None) -> UserMarketData:
        """Fetch user's positions from the Morpho subgraph.

        Args:
            address: User's ethereum address.
            chain_id: Chain ID to fetch for. If None, uses the client's initialized chain_id.
                      Note: Currently, MorphoSubgraphClient doesn't use chain_id for this query.

        Returns:
            UserMarketData: User's positions and transactions, or empty if error/not found.
        """
        current_chain_id = chain_id if chain_id is not None else self.chain_id
        if chain_id is not None and chain_id != self.chain_id:
            logger.warning(f"[{self.chain_id}] get_user_positions called with chain_id {chain_id}, mismatch with client's {self.chain_id}. Subgraph client uses its configured URL.")

        try:
            logger.debug(f"[{self.chain_id}] Requesting user positions for {address} from subgraph client.")
            # Use the subgraph client directly
            subgraph_positions = await self.subgraph_client.get_user_positions(address)

            if not subgraph_positions or not subgraph_positions.positions:
                logger.info(f"[{self.chain_id}] No positions found in subgraph for {address}")
                return UserMarketData(market_positions=[], transactions=[])

            # Convert the subgraph positions to our internal model
            return self._convert_subgraph_to_user_market_data(subgraph_positions, address)

        except Exception as e:
            # Log the error and return empty data, no fallback
            logger.error(f"[{self.chain_id}] Error fetching user positions from subgraph for {address}: {str(e)}")
            logger.exception("Subgraph user positions fetch stack trace:")
            return UserMarketData(market_positions=[], transactions=[])

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
            loan_price_usd = safe_decimal(loan_asset_data.get('lastPriceUSD'))
            collateral_price_usd = safe_decimal(collateral_asset_data.get('lastPriceUSD'))
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
            timestamp = int(subgraph_market_data.get('lastUpdatedTimestamp', 0))
            irm_address = subgraph_market_data.get('irmAddress') # Use the alias from the query
            oracle_address = None # Extract from nested oracle object below
            oracle_data = subgraph_market_data.get('oracle')
            if oracle_data:
                 oracle_address = oracle_data.get('oracleAddress')

            # Ensure required addresses are found
            if not irm_address:
                 logger.warning(f"[{self.chain_id}] Skipping market {market_id}: Missing IRM address (irmAddress)")
                 return None
            if not oracle_address:
                 logger.warning(f"[{self.chain_id}] Skipping market {market_id}: Missing Oracle address (oracle.oracleAddress)")
                 return None

            # --- Construct MarketState ---
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
                'rateAtUTarget': "0", # Not directly available
                'dailySupplyApy': str(supply_apy),
                'dailyBorrowApy': str(borrow_apy),
                'weeklySupplyApy': "0", # Placeholder
                'weeklyBorrowApy': "0", # Placeholder
                'monthlySupplyApy': "0", # Placeholder
                'monthlyBorrowApy': "0", # Placeholder
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
            market = Market(
                id=market_id,
                unique_key=market_id,
                lltv=str(lltv),
                irm_address=irm_address, # Use extracted value
                oracle_address=oracle_address, # Use extracted value
                collateral_price=collateral_price_str,
                morpho_blue=morpho_blue,
                oracle_info=oracle_data or {}, # Pass fetched oracle data
                loan_asset=loan_asset,
                collateral_asset=collateral_asset,
                state=market_state,
                daily_apys=daily_apys,
                warnings=[], # Placeholder for runtime warnings
                bad_debt=BadDebt(underlying=0, usd=0), # Not directly available
                realized_bad_debt=BadDebt(underlying=0, usd=0), # Not directly available
                oracle=oracle_data or {} # Keep passing the raw oracle data
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
        """Fetch markets exclusively from the subgraph.

        Args:
            first: Number of markets to fetch (max 1000 for subgraph).
            chain_id: Chain ID to fetch for. If None, uses the client's initialized chain_id.
                      Note: Passed to subgraph client but might not be used in query vars.

        Returns:
            List[Market]: List of markets, or empty list if error/not found.
        """
        current_chain_id = chain_id if chain_id is not None else self.chain_id
        if chain_id is not None and chain_id != self.chain_id:
            logger.warning(f"[{self.chain_id}] get_markets called with chain_id {chain_id}, mismatch with client's {self.chain_id}. Subgraph client uses its configured URL.")

        logger.info(f"[{self.chain_id}] Attempting to fetch markets from subgraph (first={first}, chain_id={current_chain_id})")

        try:
            # Pass chain_id to subgraph client's get_markets
            # The subgraph client handles the actual query execution
            subgraph_markets_data = await self.subgraph_client.get_markets(first=first, chain_id=current_chain_id)

            if not subgraph_markets_data:
                logger.warning(f"[{self.chain_id}] Subgraph client returned no market data for chain {current_chain_id}.")
                return [] # Return empty list if no data

            markets = []
            for market_data in subgraph_markets_data:
                market = self._convert_subgraph_market_to_market(market_data)
                if market:
                    markets.append(market)

            if not markets:
                logger.warning(f"[{self.chain_id}] Subgraph returned data for chain {current_chain_id}, but conversion resulted in zero valid markets.")
                return []
            else:
                 logger.info(f"[{self.chain_id}] Successfully fetched and converted {len(markets)} markets from subgraph for chain {current_chain_id}.")                 
                 return markets

        except Exception as e:
            # Log error and return empty list, no fallback
            logger.error(f"[{self.chain_id}] Error fetching or processing markets from subgraph for chain {current_chain_id}: {str(e)}")
            logger.exception("Subgraph markets fetch/processing stack trace:")
            return [] # Return empty list on error

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        # Close subgraph client connector if it's managed via async context
        if hasattr(self.subgraph_client, '__aexit__'):
             await self.subgraph_client.__aexit__(exc_type, exc_val, exc_tb)
