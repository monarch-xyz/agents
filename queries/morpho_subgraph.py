GET_USER_POSITIONS_SUBGRAPH = """
query GetUserPositions($userAddress: ID!) {
  account(id: $userAddress) {
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

# Define the market query directly, inlining all fields
GET_MARKETS_SUBGRAPH = """
query GetSubgraphMarkets($first: Int, $where: Market_filter) {
  markets(
    first: $first,
    where: $where,
  ) {
    # --- Inlined Market Fields --- 
    id
    lltv
    irmAddress: irm # Alias
    collateralPriceUSD: inputTokenPriceUSD # Alias
    totalDepositBalanceUSD
    totalBorrowBalanceUSD
    totalSupplyShares
    totalBorrowShares
    totalSupply
    totalBorrow
    totalCollateral
    fee
    totalValueLockedUSD
    lastUpdatedTimestamp: lastUpdate # Alias
    inputToken { # collateralAsset
      # --- Inlined TokenFields --- 
      id
      name
      symbol
      decimals
      lastPriceUSD
    }
    borrowedToken { # loanAsset
      # --- Inlined TokenFields --- 
      id
      name
      symbol
      decimals
      lastPriceUSD
    }
    oracle {
      # --- Inlined OracleFields --- 
      id
      oracleAddress
    }
    rates {
      id
      rate
      side
      type
    }
    # --- End Inlined Fields --- 
  }
}
"""

# Removed old query definition 