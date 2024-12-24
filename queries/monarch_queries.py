GET_AUTHORIZED_USERS = """
query GetAuthorizedUsers($rebalancer: Bytes!) {
    users(where: { rebalancer_in: [$rebalancer] }) {
        id
        marketCaps (where: {cap_gt: 0}) {
            marketId
            cap
        }
    }
}
"""
