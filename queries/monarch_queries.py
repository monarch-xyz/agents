GET_AUTHORIZED_USERS = """
query GetAuthorizedUsers($rebalancer: String!) {
    users(filter: { rebalancer: { equalTo: $rebalancer } }) {
        nodes {
            id
            marketCaps {
                nodes {
                    marketId
                    cap
                }
            }
        }
    }
}
"""
