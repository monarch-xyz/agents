from dataclasses import dataclass
from typing import List, Optional
from decimal import Decimal
from datetime import datetime

@dataclass
class Asset:
    id: str
    address: str
    symbol: str
    name: str
    decimals: int
    price_usd: Decimal

@dataclass
class RewardAsset:
    address: str
    price_usd: Decimal
    spot_price_eth: Decimal

@dataclass
class Reward:
    yearly_supply_tokens: str
    asset: RewardAsset
    amount_per_supplied_token: str
    amount_per_borrowed_token: int

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
    rewards: List[Reward]
    monthly_supply_apy: Decimal
    monthly_borrow_apy: Decimal
    daily_supply_apy: Decimal
    daily_borrow_apy: Decimal
    weekly_supply_apy: Decimal
    weekly_borrow_apy: Decimal

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
class MarketPosition:
    supply_shares: Decimal
    supply_assets: Decimal
    supply_assets_usd: Decimal
    borrow_shares: Decimal
    borrow_assets: Decimal
    borrow_assets_usd: Decimal
    market: Market
    unique_key: str

    @property
    def id(self) -> str:
        """Get the unique market identifier"""
        return self.unique_key

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
                    price_usd=Decimal(str(pos['market']['loanAsset']['priceUsd']))
                ),
                collateral_asset=Asset(
                    id=pos['market']['collateralAsset']['id'],
                    address=pos['market']['collateralAsset']['address'],
                    symbol=pos['market']['collateralAsset']['symbol'],
                    name=pos['market']['collateralAsset']['name'],
                    decimals=pos['market']['collateralAsset']['decimals'],
                    price_usd=Decimal(str(pos['market']['collateralAsset']['priceUsd']))
                ),
                state=MarketState(
                    borrow_assets=pos['market']['state']['borrowAssets'],
                    supply_assets=pos['market']['state']['supplyAssets'],
                    borrow_assets_usd=Decimal(str(pos['market']['state']['borrowAssetsUsd'])),
                    supply_assets_usd=Decimal(str(pos['market']['state']['supplyAssetsUsd'])),
                    borrow_shares=pos['market']['state']['borrowShares'],
                    supply_shares=pos['market']['state']['supplyShares'],
                    liquidity_assets=pos['market']['state']['liquidityAssets'],
                    liquidity_assets_usd=Decimal(str(pos['market']['state']['liquidityAssetsUsd'])),
                    collateral_assets=pos['market']['state']['collateralAssets'],
                    collateral_assets_usd=Decimal(str(pos['market']['state']['collateralAssetsUsd'])),
                    utilization=Decimal(str(pos['market']['state']['utilization'])),
                    supply_apy=Decimal(str(pos['market']['state']['supplyApy'])),
                    borrow_apy=Decimal(str(pos['market']['state']['borrowApy'])),
                    fee=pos['market']['state']['fee'],
                    timestamp=pos['market']['state']['timestamp'],
                    rate_at_u_target=Decimal(str(pos['market']['state']['rateAtUTarget'])),
                    rewards=[
                        Reward(
                            yearly_supply_tokens=r['yearlySupplyTokens'],
                            asset=RewardAsset(
                                address=r['asset']['address'],
                                price_usd=Decimal(str(r['asset']['priceUsd'])),
                                spot_price_eth=Decimal(str(r['asset']['spotPriceEth']))
                            ),
                            amount_per_supplied_token=r['amountPerSuppliedToken'],
                            amount_per_borrowed_token=r['amountPerBorrowedToken']
                        )
                        for r in pos['market']['state']['rewards']
                    ],
                    monthly_supply_apy=Decimal(str(pos['market']['state']['monthlySupplyApy'])),
                    monthly_borrow_apy=Decimal(str(pos['market']['state']['monthlyBorrowApy'])),
                    daily_supply_apy=Decimal(str(pos['market']['state']['dailySupplyApy'])),
                    daily_borrow_apy=Decimal(str(pos['market']['state']['dailyBorrowApy'])),
                    weekly_supply_apy=Decimal(str(pos['market']['state']['weeklySupplyApy'])),
                    weekly_borrow_apy=Decimal(str(pos['market']['state']['weeklyBorrowApy']))
                ),
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
            
            market_positions.append(MarketPosition(
                supply_shares=Decimal(str(pos['supplyShares'])),
                supply_assets=Decimal(str(pos['supplyAssets'])),
                supply_assets_usd=Decimal(str(pos['supplyAssetsUsd'])),
                borrow_shares=Decimal(str(pos['borrowShares'])),
                borrow_assets=Decimal(str(pos['borrowAssets'])),
                borrow_assets_usd=Decimal(str(pos['borrowAssetsUsd'])),
                market=market,
                unique_key=pos['market']['uniqueKey']
            ))

        # Only include transactions of specific types
        VALID_TRANSACTION_TYPES = {'MarketSupply', 'MarketWithdraw'}
        transactions = []
        
        if 'transactions' in data:
            for tx in data['transactions']:
                if tx['type'] not in VALID_TRANSACTION_TYPES:
                    continue

                transactions.append(
                    Transaction(
                        hash=tx['hash'],
                        timestamp=tx['timestamp'],
                        type=tx['type'],
                        data=TransactionData(   
                            shares=tx['data']['shares'],
                            assets=tx['data']['assets'],
                            market=tx['data']['market']
                        )
                    ))

        return cls(
            market_positions=market_positions,
            transactions=transactions
        )
