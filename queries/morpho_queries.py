GET_USER_MARKET_POSITIONS = """
query getUserMarketPositions($address: String!, $chainId: Int) {
    userByAddress(address: $address, chainId: $chainId) {
        marketPositions {
            state {
                supplyShares
                supplyAssets
                supplyAssetsUsd
                borrowShares
                borrowAssets
                borrowAssetsUsd
            }
            market {
                id
                lltv
                uniqueKey
                irmAddress
                oracleAddress
                collateralPrice
                morphoBlue {
                    id
                    address
                    chain {
                        id
                    }
                }
                oracleInfo {
                    type
                }
                loanAsset {
                    id
                    address
                    symbol
                    name
                    decimals
                    priceUsd
                }
                collateralAsset {
                    id
                    address
                    symbol
                    name
                    decimals
                    priceUsd
                }
                state {
                    borrowAssets
                    supplyAssets
                    borrowAssetsUsd
                    supplyAssetsUsd
                    borrowShares
                    supplyShares
                    liquidityAssets
                    liquidityAssetsUsd
                    collateralAssets
                    collateralAssetsUsd
                    utilization
                    supplyApy
                    borrowApy
                    fee
                    timestamp
                    rateAtUTarget
                    monthlySupplyApy
                    monthlyBorrowApy
                    dailySupplyApy
                    dailyBorrowApy
                    weeklySupplyApy
                    weeklyBorrowApy
                }
                dailyApys {
                    netSupplyApy
                    netBorrowApy
                }
                warnings {
                    type
                    level
                }
                badDebt {
                    underlying
                    usd
                }
                realizedBadDebt {
                    underlying
                    usd
                }
                oracle {
                    data {
                        ... on MorphoChainlinkOracleData {
                            baseFeedOne {
                                address
                                chain {
                                    id
                                }
                                description
                                id
                                pair
                                vendor
                            }
                            baseFeedTwo {
                                address
                                chain {
                                    id
                                }
                                description
                                id
                                pair
                                vendor
                            }
                            quoteFeedOne {
                                address
                                chain {
                                    id
                                }
                                description
                                id
                                pair
                                vendor
                            }
                            quoteFeedTwo {
                                address
                                chain {
                                    id
                                }
                                description
                                id
                                pair
                                vendor
                            }
                        }
                    }
                }
            }
        }
        transactions {
            hash
            timestamp
            type
            data {
                ... on MarketTransferTransactionData {
                    assetsUsd
                    shares
                    assets
                    market {
                        id
                        uniqueKey
                        morphoBlue {
                            chain {
                                id
                            }
                        }
                    }
                }
            }
        }
    }
}
"""

GET_MARKETS = """
query getMarkets($first: Int, $where: MarketFilters) {
    markets(first: $first, where: $where) {
        items {
            id
            lltv
            uniqueKey
            irmAddress
            oracleAddress
            collateralPrice
            morphoBlue {
                id
                address
                chain {
                    id
                }
            }
            oracleInfo {
                type
            }
            loanAsset {
                id
                address
                symbol
                name
                decimals
                priceUsd
            }
            collateralAsset {
                id
                address
                symbol
                name
                decimals
                priceUsd
            }
            state {
                borrowAssets
                supplyAssets
                borrowAssetsUsd
                supplyAssetsUsd
                borrowShares
                supplyShares
                liquidityAssets
                liquidityAssetsUsd
                collateralAssets
                collateralAssetsUsd
                utilization
                supplyApy
                borrowApy
                fee
                timestamp
                rateAtUTarget
                monthlySupplyApy
                monthlyBorrowApy
                dailySupplyApy
                dailyBorrowApy
                weeklySupplyApy
                weeklyBorrowApy
            }
            dailyApys {
                netSupplyApy
                netBorrowApy
            }
            warnings {
                type
                level
            }
            badDebt {
                underlying
                usd
            }
            realizedBadDebt {
                underlying
                usd
            }
            oracle {
                data {
                    ... on MorphoChainlinkOracleData {
                        baseFeedOne {
                            address
                            chain {
                                id
                            }
                            description
                            id
                            pair
                            vendor
                        }
                        baseFeedTwo {
                            address
                            chain {
                                id
                            }
                            description
                            id
                            pair
                            vendor
                        }
                        quoteFeedOne {
                            address
                            chain {
                                id
                            }
                            description
                            id
                            pair
                            vendor
                        }
                        quoteFeedTwo {
                            address
                            chain {
                                id
                            }
                            description
                            id
                            pair
                            vendor
                        }
                    }
                }
            }
        }
    }
}
"""
