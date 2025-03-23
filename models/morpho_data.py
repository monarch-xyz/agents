from dataclasses import dataclass
from typing import List, Optional
from decimal import Decimal, InvalidOperation, ConversionSyntax
from datetime import datetime
import logging

logger = logging.getLogger(__name__)

@dataclass
class Asset:
    id: str
    address: str
    symbol: str
    name: str
    decimals: int


@dataclass
class MarketState:
    borrow_assets: int
    supply_assets: int
    borrow_assets_usd: Decimal
    supply_assets_usd: Decimal
    borrow_shares: str
    supply_shares: str
    liquidity_assets: int
    liquidity_assets_usd: Decimal
    collateral_assets: str
    collateral_assets_usd: Decimal
    utilization: Decimal
    supply_apy: Decimal
    borrow_apy: Decimal
    fee: int
    timestamp: int
    rate_at_u_target: Decimal
    monthly_supply_apy: Decimal
    monthly_borrow_apy: Decimal
    daily_supply_apy: Decimal
    daily_borrow_apy: Decimal
    weekly_supply_apy: Decimal
    weekly_borrow_apy: Decimal

    @classmethod
    def from_dict(cls, data: dict) -> 'MarketState':
        """Create MarketState from dict with safe decimal conversion"""
        return cls(
            borrow_assets=int(data['borrowAssets']),
            supply_assets=int(data['supplyAssets']),
            borrow_assets_usd=safe_decimal(data['borrowAssetsUsd']),
            supply_assets_usd=safe_decimal(data['supplyAssetsUsd']),
            borrow_shares=str(data['borrowShares']),
            supply_shares=str(data['supplyShares']),
            liquidity_assets=int(data['liquidityAssets']),
            liquidity_assets_usd=safe_decimal(data['liquidityAssetsUsd']),
            collateral_assets=str(data['collateralAssets']),
            collateral_assets_usd=safe_decimal(data['collateralAssetsUsd']),
            utilization=safe_decimal(data['utilization']),
            supply_apy=safe_decimal(data['supplyApy']),
            borrow_apy=safe_decimal(data['borrowApy']),
            fee=int(data['fee']),
            timestamp=int(data['timestamp']),
            rate_at_u_target=safe_decimal(data['rateAtUTarget']),
            monthly_supply_apy=safe_decimal(data['monthlySupplyApy']),
            monthly_borrow_apy=safe_decimal(data['monthlyBorrowApy']),
            daily_supply_apy=safe_decimal(data['dailySupplyApy']),
            daily_borrow_apy=safe_decimal(data['dailyBorrowApy']),
            weekly_supply_apy=safe_decimal(data['weeklySupplyApy']),
            weekly_borrow_apy=safe_decimal(data['weeklyBorrowApy'])
        )


def safe_decimal(value, default="0") -> Decimal:
    """Safely convert a value to Decimal, handling None and other edge cases"""
    if value is None:
        logger.debug(f"Converting None to Decimal({default})")
        return Decimal(default)
        
    # Handle various data types
    try:
        if isinstance(value, str):
            # Handle empty strings
            if not value.strip():
                logger.debug(f"Converting empty string to Decimal({default})")
                return Decimal(default)
                
            # Handle scientific notation and large numbers
            return Decimal(value)
            
        elif isinstance(value, (int, float)):
            # Convert through string to avoid float precision issues
            return Decimal(str(value))
            
        else:
            # Try direct conversion for other types
            return Decimal(str(value))
            
    except (InvalidOperation, ConversionSyntax, ValueError, TypeError) as e:
        logger.warning(f"Could not convert {value} (type: {type(value)}) to Decimal: {str(e)}")
        return Decimal(default)


@dataclass
class DailyApys:
    net_supply_apy: Decimal
    net_borrow_apy: Decimal


@dataclass
class BadDebt:
    underlying: int
    usd: int


@dataclass
class Warning:
    type: str
    level: str


@dataclass
class Chain:
    id: int


@dataclass
class MorphoBlue:
    id: str
    address: str
    chain: Chain


@dataclass
class OracleFeed:
    address: str
    chain: Chain
    description: str
    id: str
    pair: List[str]
    vendor: str


@dataclass
class OracleData:
    base_feed_one: OracleFeed
    base_feed_two: OracleFeed
    quote_feed_one: OracleFeed
    quote_feed_two: Optional[OracleFeed]


@dataclass
class Market:
    id: str
    lltv: str
    unique_key: str
    irm_address: str
    oracle_address: str
    collateral_price: str
    morpho_blue: MorphoBlue
    oracle_info: dict  # Type can be expanded if needed
    loan_asset: Asset
    collateral_asset: Asset
    state: MarketState
    daily_apys: DailyApys
    warnings: List[Warning]
    bad_debt: BadDebt
    realized_bad_debt: BadDebt
    oracle: dict  # Can be expanded if needed
    
    @classmethod
    def from_api(cls, data: dict) -> 'Market':
        """Create a Market object from API response data"""
        try:
            # Debug logging
            required_fields = ['id', 'lltv', 'uniqueKey', 'irmAddress', 'oracleAddress', 
                               'collateralPrice', 'morphoBlue', 'oracleInfo', 'loanAsset', 
                               'collateralAsset', 'state', 'dailyApys', 'warnings', 
                               'badDebt', 'realizedBadDebt', 'oracle']
            
            missing_fields = []
            for field in required_fields:
                if field not in data:
                    missing_fields.append(field)
                    logging.error(f"Missing required field '{field}' in market data")
                    
            if missing_fields:
                logging.error(f"Missing fields in market data: {', '.join(missing_fields)}")
                logging.debug(f"Available fields: {', '.join(data.keys())}")
                    
            # Ensure badDebt and realizedBadDebt have defaults if None
            badDebt = data.get('badDebt') or {'underlying': '0', 'usd': '0'}
            realizedBadDebt = data.get('realizedBadDebt') or {'underlying': '0', 'usd': '0'}
            
            # Log any None values we're fixing with defaults
            if data.get('badDebt') is None:
                logging.debug(f"Using default badDebt for market {data.get('uniqueKey', 'unknown')}")
            if data.get('realizedBadDebt') is None:
                logging.debug(f"Using default realizedBadDebt for market {data.get('uniqueKey', 'unknown')}")
                
            # Check for potential None values in nested fields
            for field, nested_field in [
                ('state', 'supplyAssetsUsd'),
                ('state', 'collateralAssetsUsd'),
                ('dailyApys', 'netSupplyApy'),
                ('dailyApys', 'netBorrowApy')
            ]:
                if field in data and data[field] is not None and nested_field in data[field] and data[field][nested_field] is None:
                    logging.warning(f"Field {field}.{nested_field} is None for market {data.get('uniqueKey', 'unknown')[:8]}, using default '0'")
                    data[field][nested_field] = "0"
                    
            # Create the Market object with careful error handling
            return cls(
                id=data['id'],
                lltv=data['lltv'],
                unique_key=data['uniqueKey'],
                irm_address=data['irmAddress'],
                oracle_address=data['oracleAddress'],
                collateral_price=data['collateralPrice'],
                morpho_blue=MorphoBlue(
                    id=data['morphoBlue']['id'],
                    address=data['morphoBlue']['address'],
                    chain=Chain(id=data['morphoBlue']['chain']['id'])
                ),
                oracle_info=data['oracleInfo'],
                loan_asset=Asset(
                    id=data['loanAsset']['id'],
                    address=data['loanAsset']['address'],
                    symbol=data['loanAsset']['symbol'],
                    name=data['loanAsset']['name'],
                    decimals=data['loanAsset']['decimals']
                ),
                collateral_asset=Asset(
                    id=data['collateralAsset']['id'],
                    address=data['collateralAsset']['address'],
                    symbol=data['collateralAsset']['symbol'],
                    name=data['collateralAsset']['name'],
                    decimals=data['collateralAsset']['decimals']
                ),
                state=MarketState.from_dict(data['state']),
                daily_apys=DailyApys(
                    net_supply_apy=safe_decimal(data['dailyApys']['netSupplyApy']),
                    net_borrow_apy=safe_decimal(data['dailyApys']['netBorrowApy'])
                ),
                warnings=[Warning(type=w['type'], level=w['level']) for w in data['warnings']] if data['warnings'] else [],
                bad_debt=BadDebt(
                    underlying=int(badDebt['underlying']),
                    usd=int(badDebt['usd'])
                ),
                realized_bad_debt=BadDebt(
                    underlying=int(realizedBadDebt['underlying']),
                    usd=int(realizedBadDebt['usd'])
                ),
                oracle=data['oracle']  # Keep as dict as it has different possible shapes
            )
        except KeyError as e:
            logging.error(f"KeyError creating Market from API data: {str(e)}")
            logging.debug(f"Missing key: {e}")
            logging.debug(f"Available keys: {data.keys()}")
            raise
        except TypeError as e:
            logging.error(f"TypeError creating Market from API data: {str(e)}")
            logging.debug(f"Error details: {str(e)}")
            if "'NoneType' object is not subscriptable" in str(e):
                logging.error("This is likely due to a None value in a nested field")
                for field in ['morphoBlue', 'loanAsset', 'collateralAsset', 'state', 'dailyApys', 'badDebt', 'realizedBadDebt']:
                    if field in data:
                        logging.debug(f"Field {field} value: {data[field]}")
            raise
        except Exception as e:
            logging.error(f"Error creating Market from API data: {str(e)}")
            logging.debug(f"Data that caused error: {data}")
            raise


@dataclass
class PositionState:
    supply_shares: Decimal
    supply_assets: Decimal
    supply_assets_usd: Decimal
    borrow_shares: Decimal
    borrow_assets: Decimal
    borrow_assets_usd: Decimal
    
    @classmethod
    def from_dict(cls, data: dict) -> 'PositionState':
        """Create PositionState from dict with safe decimal conversion"""
        return cls(
            supply_shares=safe_decimal(data['supplyShares']),
            supply_assets=safe_decimal(data['supplyAssets']),
            supply_assets_usd=safe_decimal(data['supplyAssetsUsd']),
            borrow_shares=safe_decimal(data['borrowShares']),
            borrow_assets=safe_decimal(data['borrowAssets']),
            borrow_assets_usd=safe_decimal(data['borrowAssetsUsd'])
        )


@dataclass
class MarketPosition:
    state: PositionState
    market: Market
    unique_key: str

    @property
    def id(self) -> str:
        """Get the unique market identifier"""
        return self.unique_key
    
    @property
    def supply_shares(self) -> Decimal:
        """Get supply shares from state for backward compatibility"""
        return self.state.supply_shares
        
    @property
    def supply_assets(self) -> Decimal:
        """Get supply assets from state for backward compatibility"""
        return self.state.supply_assets
        
    @property
    def supply_assets_usd(self) -> Decimal:
        """Get supply assets USD from state for backward compatibility"""
        return self.state.supply_assets_usd
        
    @property
    def borrow_shares(self) -> Decimal:
        """Get borrow shares from state for backward compatibility"""
        return self.state.borrow_shares
        
    @property
    def borrow_assets(self) -> Decimal:
        """Get borrow assets from state for backward compatibility"""
        return self.state.borrow_assets
        
    @property
    def borrow_assets_usd(self) -> Decimal:
        """Get borrow assets USD from state for backward compatibility"""
        return self.state.borrow_assets_usd


@dataclass
class TransactionData:
    shares: int
    assets: int
    market: dict  # Simplified market data for transactions


@dataclass
class Transaction:
    hash: str
    timestamp: int
    type: str
    data: TransactionData


@dataclass
class UserMarketData:
    market_positions: List[MarketPosition]
    transactions: List[Transaction]

    @classmethod
    def from_graphql(cls, data: dict) -> 'UserMarketData':
        """Create UserMarketData from GraphQL response data"""
        market_positions = []
        transactions = []

        for pos in data['marketPositions']:
            # log 
            logger.debug(f"Start iteration, Market ID \n: {pos['market']['id']}")

            try: 
                market = Market(
                    id=pos['market']['id'],
                    lltv=pos['market']['lltv'],
                    unique_key=pos['market']['uniqueKey'],
                    irm_address=pos['market']['irmAddress'],
                    oracle_address=pos['market']['oracleAddress'],
                    collateral_price=pos['market']['collateralPrice'],
                    morpho_blue=MorphoBlue(
                        id=pos['market']['morphoBlue']['id'],
                        address=pos['market']['morphoBlue']['address'],
                        chain=Chain(id=pos['market']['morphoBlue']['chain']['id'])
                    ),
                    oracle_info=pos['market']['oracleInfo'],
                    loan_asset=Asset(
                        id=pos['market']['loanAsset']['id'],
                        address=pos['market']['loanAsset']['address'],
                        symbol=pos['market']['loanAsset']['symbol'],
                        name=pos['market']['loanAsset']['name'],
                        decimals=pos['market']['loanAsset']['decimals'],
                    ),
                    collateral_asset=Asset(
                        id=pos['market']['collateralAsset']['id'],
                        address=pos['market']['collateralAsset']['address'],
                        symbol=pos['market']['collateralAsset']['symbol'],
                        name=pos['market']['collateralAsset']['name'],
                        decimals=pos['market']['collateralAsset']['decimals'],
                    ),
                    state=MarketState.from_dict(pos['market']['state']),
                    daily_apys=DailyApys(
                        net_supply_apy=Decimal(str(pos['market']['dailyApys']['netSupplyApy'])),
                        net_borrow_apy=Decimal(str(pos['market']['dailyApys']['netBorrowApy']))
                    ),
                    warnings=[
                        Warning(type=w['type'], level=w['level'])
                        for w in pos['market']['warnings']
                    ],
                    bad_debt=BadDebt(
                        underlying=pos['market']['badDebt']['underlying'],
                        usd=pos['market']['badDebt']['usd']
                    ),
                    realized_bad_debt=BadDebt(
                        underlying=pos['market']['realizedBadDebt']['underlying'],
                        usd=pos['market']['realizedBadDebt']['usd']
                    ),
                    oracle=pos['market']['oracle']
                )
            except Exception as e:
                logger.error(f"Error converting market data: {str(e)}")
                logger.debug(f"Market data: {pos['market']}")
                continue

            # log market data
            logger.debug(f"Convert to Market complete \n")

            # Create position state from the state field
            position_state = PositionState.from_dict(pos['state'])

            market_positions.append(MarketPosition(
                state=position_state,
                market=market,
                unique_key=pos['market']['uniqueKey']
            ))

            # log position data
            logger.debug(f"Convert to MarketPosition complete \n")

        # Only include transactions of specific types
        # VALID_TRANSACTION_TYPES = {'MarketSupply', 'MarketWithdraw'}
        transactions = []
        

        return cls(
            market_positions=market_positions,
            transactions=transactions
        )
