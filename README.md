# Morpho Automation Service

This service automates fund reallocation across Morpho Blue markets for users who have authorized the agent contract.

It runs periodically for configured blockchain networks (e.g., Base, Polygon) to:
1. Fetch user authorizations and market caps from the Monarch Subgraph.
2. Fetch current market data (APYs, etc.) from the Morpho Subgraph.
3. Analyze user positions based on a defined strategy (e.g., `SimpleMaxAPYStrategy`).
4. Execute reallocation transactions via the Agent contract if required.
5. Send notifications via Telegram.

## Setup

### 1. Clone the Repository

```bash
git clone https://github.com/YOUR_USERNAME/agent-backend.git # Replace with your repo URL
cd agent-backend
```

### 2. Create Virtual Environment & Install Dependencies

```bash
# Create virtual environment
python3 -m venv venv

# Activate virtual environment
# On macOS/Linux:
source venv/bin/activate
# On Windows:
# .\venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt
```

### 3. Configure Environment Variables

Create a `.env` file in the root directory of the project and add the following variables:

```env
# --- Required --- 

# Comma-separated list of chain IDs to run the bot on (e.g., Base, Polygon)
# Supported values defined in config/networks.py
SUPPORTED_CHAIN_IDS=8453,137

# Alchemy API Key (used for RPC URLs)
ALCHEMY_API_KEY=your_alchemy_api_key

# Private key of the wallet that will execute rebalance transactions via the agent contract
# !! KEEP THIS SECURE !!
PRIVATE_KEY=0xYourPrivateKeyHere

# Telegram Bot Token (from BotFather)
TELEGRAM_BOT_TOKEN=your_telegram_bot_token

# Telegram Chat ID (where notifications will be sent)
TELEGRAM_CHAT_ID=your_telegram_chat_id # Can be a group chat ID (negative number) or personal chat ID

# The Graph API Key (for authenticated access to Morpho Gateway Subgraphs)
GRAPH_API_KEY=your_the_graph_api_key

# --- Optional --- 

# Comma-separated list of user addresses (lowercase) to exclusively process.
# If commented out or empty, all authorized users will be processed.
# WHITELISTED_ADDRESSES=0xaddress1...,0xaddress2...

# Chain-specific Gas Policy Overrides (Defaults: Min Gas = 15 Gwei, Retries = 180)
# Replace XXXX with the Chain ID (e.g., 8453, 137)
# GAS_POLICY_MIN_GAS_XXXX=30
# GAS_POLICY_MAX_RETRIES_XXXX=120

# Global Gas Policy Fallbacks (if chain-specific are not set)
# GAS_POLICY_MIN_GAS=15
# GAS_POLICY_MAX_RETRIES=180

# Optional: Set log level (DEBUG, INFO, WARNING, ERROR, CRITICAL). Defaults usually INFO.
# LOG_LEVEL=DEBUG 
```

**Important:** Ensure the Agent Contract addresses (`agent_contract_address`) in `config/networks.py` are updated with your deployed contract addresses for each network.

### 4. Run the Service

```bash
python main.py
```

This will start the automation service. It will run the process concurrently for each chain ID specified in `SUPPORTED_CHAIN_IDS`.

## Monitoring

- Check the console output for logs.
- Monitor the configured Telegram chat for notifications on run completion, reallocations, and errors.
- Set `LOG_LEVEL=DEBUG` in your `.env` for more verbose output during development or troubleshooting.

## Development

- The core logic resides in the `services/` directory.
- Clients for external interactions are in `clients/`.
- Network configurations are centralized in `config/networks.py`.
- Reallocation logic is implemented in strategy classes within `strategies/` (e.g., `SimpleMaxAPYStrategy`).
