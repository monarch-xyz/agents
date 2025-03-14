from dataclasses import dataclass
from typing import List, Optional
from decimal import Decimal
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
        return Decimal(default)
    try:
        # Handle scientific notation and large numbers
        return Decimal(str(value))
    except (Decimal.InvalidOperation, Decimal.ConversionSyntax):
        logger.warning(f"Could not convert {value} to Decimal, using default {default}")
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
        
        # if 'transactions' in data:
        #     for tx in data['transactions']:
        #         if tx['type'] not in VALID_TRANSACTION_TYPES:
        #             continue

        #         transactions.append(
        #             Transaction(
        #                 hash=tx['hash'],
        #                 timestamp=tx['timestamp'],
        #                 type=tx['type'],
        #                 data=TransactionData(   
        #                     shares=tx['data']['shares'],
        #                     assets=tx['data']['assets'],
        #                     market=tx['data']['market']
        #                 )
        #             ))

        return cls(
            market_positions=market_positions,
            transactions=transactions
        )
