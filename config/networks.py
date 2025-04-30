# config/networks.py
import os

# --- Chain IDs ---
BASE_CHAIN_ID = 8453
POLYGON_CHAIN_ID = 137

# --- Constants ---
# Assuming the main Morpho Blue contract address is the same on supported chains
# Adjust if chain-specific addresses are needed
MORPHO_BLUE_ADDRESS = "0xbbbbbbbbbb9cc5e90e3b3af64bdaf62c37eeffcb"

# --- Network Configuration Mapping ---
NETWORKS = {
    BASE_CHAIN_ID: {
        "name": "Base",
        "rpc_alchemy_network": "base-mainnet",
        # Morpho Subgraph (Gateway requires API Key)
        "morpho_subgraph_gateway_id": "71ZTy1veF9twER9CLMnPWeLQ7GZcwKsjmygejrgKirqs",
        # Monarch Subgraph (Direct Studio URL)
        "monarch_subgraph_url": "https://api.studio.thegraph.com/query/110397/monarch-agent-base/version/latest",
        # Legacy Morpho API URL (Optional, based on previous setup)
        "agent_contract_address": "0x6a9BA5c91fDd608b3F85c3E031a4f531f331f545",
        "morpho_blue_address": MORPHO_BLUE_ADDRESS,
        "use_poa_middleware": False,
        "explorer_base_url": "https://basescan.org"
    },
    POLYGON_CHAIN_ID: {
        "name": "Polygon",
        "rpc_alchemy_network": "polygon-mainnet",
        # Morpho Subgraph (Gateway requires API Key)
        "morpho_subgraph_gateway_id": "EhFokmwryNs7qbvostceRqVdjc3petuD13mmdUiMBw8Y",
        # Monarch Subgraph (Direct Studio URL)
        "monarch_subgraph_url": "https://api.studio.thegraph.com/query/110397/monarch-agent-polygon/version/latest",
        "agent_contract_address": "0x01c90eEb82f982301fE4bd11e36A5704673CF18C",
        "morpho_blue_address": "0x1bf0c2541f820e775182832f06c0b7fc27a25f67",
        "use_poa_middleware": False, # Usually False for Polygon with Alchemy
        "explorer_base_url": "https://polygonscan.com"
    },
    # Add configurations for other supported networks here
}

def get_network_config(chain_id: int) -> dict:
    """Retrieve the configuration for a given chain ID."""
    config = NETWORKS.get(chain_id)
    if not config:
        raise ValueError(f"Unsupported chain ID: {chain_id}. No configuration found.")
    return config

def get_morpho_subgraph_url(chain_id: int) -> str:
    """Constructs the Morpho Subgraph URL for the Gateway using an API Key."""
    config = get_network_config(chain_id)
    subgraph_id = config.get("morpho_subgraph_gateway_id")
    if not subgraph_id:
        raise ValueError(f"morpho_subgraph_gateway_id not configured for chain ID {chain_id}")

    api_key = os.getenv("GRAPH_API_KEY")
    if not api_key:
        raise ValueError("GRAPH_API_KEY environment variable not set. Required for Morpho subgraph gateway access.")

    return f"https://gateway.thegraph.com/api/{api_key}/subgraphs/id/{subgraph_id}"

def get_monarch_subgraph_url(chain_id: int) -> str:
     """Gets the Monarch Subgraph URL for the given chain ID."""
     config = get_network_config(chain_id)
     url = config.get("monarch_subgraph_url")
     if not url:
          raise ValueError(f"monarch_subgraph_url not configured for chain ID {chain_id}")
     return url

def get_rpc_url(chain_id: int) -> str:
    """Constructs the RPC URL for a given chain ID using Alchemy."""
    config = get_network_config(chain_id)
    network_name = config.get("rpc_alchemy_network")
    if not network_name:
        raise ValueError(f"rpc_alchemy_network not configured for chain ID {chain_id}")

    api_key = os.getenv("ALCHEMY_API_KEY")
    if not api_key:
        raise ValueError("ALCHEMY_API_KEY environment variable not set.")

    return f"https://{network_name}.g.alchemy.com/v2/{api_key}"

def get_agent_contract_address(chain_id: int) -> str:
    """Gets the agent contract address for the given chain ID."""
    config = get_network_config(chain_id)
    address = config.get("agent_contract_address")
    if not address:
        raise ValueError(f"agent_contract_address not configured for chain ID {chain_id}")
    if not address.startswith("0x"): # Basic format check
         raise ValueError(f"Invalid agent_contract_address format for chain ID {chain_id}: {address}")
    return address

def get_morpho_blue_address(chain_id: int) -> str:
     """Gets the Morpho Blue contract address for the given chain ID."""
     config = get_network_config(chain_id)
     address = config.get("morpho_blue_address")
     if not address:
          raise ValueError(f"morpho_blue_address not configured for chain ID {chain_id}")
     # Basic format check
     if not address.startswith("0x") or len(address) != 42:
          raise ValueError(f"Invalid morpho_blue_address format for chain ID {chain_id}: {address}")
     return address

def get_explorer_url(chain_id: int) -> str:
     """Gets the base explorer URL for the given chain ID."""
     config = get_network_config(chain_id)
     url = config.get("explorer_base_url")
     if not url:
          raise ValueError(f"explorer_base_url not configured for chain ID {chain_id}")
     return url 