GET_USER_POSITIONS_SUBGRAPH = """
query GetUserPositions($userAddress: ID!) {
  account(id: $userAddress) {
    # Filter for only SUPPLIER and BORROWER positions
    supplierPositions: positions(where: {side: SUPPLIER}) {
      side
      shares
      asset {
        id
        symbol
        decimals
        name
      }
      market {
        id
        totalSupplyShares
        totalSupply
        totalBorrowShares
        totalBorrow
        rates {
          id
          side
          rate
        }
      }
    }
    borrowerPositions: positions(where: {side: BORROWER}) {
      side
      shares
      asset {
        id
        symbol
        decimals
        name
      }
      market {
        id
        totalSupplyShares
        totalSupply
        totalBorrowShares
        totalBorrow
        rates {
          id
          side
          rate
        }
      }
    }
  }
}
"""

GET_MARKETS_SUBGRAPH = """
fragment TokenFields on Token {
  id
  symbol
  decimals
  name
  lastPriceUsd: lastPriceUSD # Alias for consistency
}

fragment OracleFields on Oracle {
  id
  oracle # Address
  oracleData
}

fragment RateFields on Rate {
  id
  rate # APY
  side
  type
}

fragment MarketFields on Market {
  id
  lltv
  irm: irmAddress # Alias for consistency
  oracleAddress
  inputToken { # collateralAsset
    ...TokenFields
  }
  inputTokenPriceUSD: collateralPriceUsd # Alias from example? Check schema
  borrowedToken { # loanAsset
    ...TokenFields
  }
  borrowedTokenPriceUSD: loanPriceUsd # Check schema
  totalSupplyShares
  totalBorrowShares
  totalSupply # Supply assets in underlying
  totalBorrow # Borrow assets in underlying
  totalCollateral # Collateral assets in underlying
  fee
  lastUpdate: lastUpdatedTimestamp # Alias for consistency
  rates(orderBy: id, orderDirection: asc) { # Ensure consistent order
    ...RateFields
  }
  # --- Fields needed for MarketState ---
  # borrowAssets -> totalBorrow
  # supplyAssets -> totalSupply
  # borrowAssetsUsd -> Need to calculate: totalBorrow * borrowedToken.lastPriceUsd
  # supplyAssetsUsd -> Need to calculate: totalSupply * borrowedToken.lastPriceUsd
  # borrowShares -> totalBorrowShares
  # supplyShares -> totalSupplyShares
  # liquidityAssets -> Need to calculate: totalSupply - totalBorrow
  # liquidityAssetsUsd -> Need to calculate: liquidityAssets * borrowedToken.lastPriceUsd
  # collateralAssets -> totalCollateral
  # collateralAssetsUsd -> Need to calculate: totalCollateral * inputToken.lastPriceUsd
  # utilization -> Need to calculate: totalBorrow / totalSupply
  # supplyApy -> rates where side=SUPPLIER/LENDER
  # borrowApy -> rates where side=BORROWER
  # fee -> fee (needs conversion?)
  # timestamp -> lastUpdate
  # --- Fields needed for DailyApys ---
  # netSupplyApy -> supplyApy
  # netBorrowApy -> borrowApy
  # --- Other Market fields ---
  # morphoBlue -> Not directly available? Need to construct or use default
  # oracle_info -> Potentially from oracle field?
  # warnings -> Need logic based on data (e.g., missing prices, oracle issues)
  # bad_debt -> Not directly available
  # realized_bad_debt -> Not directly available
  # oracle -> Map from oracle field
}

query GetSubgraphMarkets($first: Int, $where: Market_filter) {
  markets(
    first: $first,
    where: $where,
    orderBy: totalCollateral, # Or another relevant metric like TVL if available
    orderDirection: desc
  ) {
    ...MarketFields
  }
}

fragment TokenFields on Token {
  id
  symbol
  decimals
  name
  lastPriceUSD # Renamed to match schema if needed
}

fragment OracleFields on Oracle {
  id
  oracle # Address
  # oracleData # If available and needed
}
""" 