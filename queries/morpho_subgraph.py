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