import os
import json
import logging
from web3 import Web3
from web3.middleware.geth_poa import geth_poa_middleware # Corrected import path
from web3.gas_strategies.rpc import rpc_gas_price_strategy
from eth_account import Account
from typing import Dict, Optional, Tuple, cast
from web3.types import TxReceipt, TxParams, Wei
# Import network config functions instead of contracts config
from config.networks import get_network_config, get_rpc_url, get_agent_contract_address
from config.contracts import AGENT_ABI_PATH # Keep ABI path for now

logger = logging.getLogger(__name__)

class BlockchainClient:
    # Accept chain_id in constructor
    def __init__(self, chain_id: int):
        self.chain_id = chain_id
        logger.info(f"Initializing BlockchainClient for chain ID: {self.chain_id}")

        # Get network specific config
        network_config = get_network_config(self.chain_id) # Handles unsupported chain error
        rpc_url = get_rpc_url(self.chain_id) # Handles missing key/config errors
        agent_address = get_agent_contract_address(self.chain_id)
        use_poa = network_config.get("use_poa_middleware", False)

        logger.info(f"[{self.chain_id}] Using RPC URL ending with ...{rpc_url[-10:]}")
        logger.info(f"[{self.chain_id}] Using Agent Contract: {agent_address}")

        try:
            self.w3 = Web3(Web3.HTTPProvider(rpc_url))

            # Inject PoA middleware if required for the network (e.g., Polygon)
            if use_poa:
                self.w3.middleware_onion.inject(geth_poa_middleware, layer=0)
                logger.info(f"[{self.chain_id}] Injected PoA middleware.")

            if not self.w3.is_connected():
                 raise ConnectionError(f"Failed to connect to Web3 provider at inferred URL for chain {self.chain_id}")

            # Verify the actual chain ID matches the expected one
            connected_chain_id = self.w3.eth.chain_id
            if connected_chain_id != self.chain_id:
                 logger.warning(f"[{self.chain_id}] Connected chain ID ({connected_chain_id}) does not match expected chain ID ({self.chain_id})!")
            else:
                 logger.info(f"[{self.chain_id}] Successfully connected to Web3 provider. Chain ID: {connected_chain_id}")

        except Exception as e:
            logger.error(f"[{self.chain_id}] Error initializing Web3 connection: {e}")
            raise

        # Set gas price strategy to use RPC
        self.w3.eth.set_gas_price_strategy(rpc_gas_price_strategy)

        # Initialize account from private key
        private_key = os.getenv('PRIVATE_KEY')
        if not private_key:
            raise ValueError("PRIVATE_KEY environment variable not set")

        self.account = Account.from_key(private_key)

        # Load contract ABI (assuming ABI is the same across chains for now)
        try:
            with open(AGENT_ABI_PATH) as f:
                contract_abi = json.load(f)
        except FileNotFoundError:
             logger.error(f"Agent ABI file not found at: {AGENT_ABI_PATH}")
             raise
        except json.JSONDecodeError:
             logger.error(f"Error decoding JSON from Agent ABI file: {AGENT_ABI_PATH}")
             raise

        # Initialize contract instance with chain-specific address
        self.agent_contract = self.w3.eth.contract(
            address=Web3.to_checksum_address(agent_address),
            abi=contract_abi
        )

        logger.info(f"[{self.chain_id}] Initialized blockchain client with signer address: {self.account.address}")

    def is_connected(self) -> bool:
        """Checks if the Web3 instance is connected."""
        return self.w3 is not None and self.w3.is_connected()

    async def simulate_transaction(
        self,
        tx_data: Dict,
        value: Optional[int] = None
    ) -> bool:
        """
        Simulate a transaction using eth_call
        
        Args:
            tx_data: Transaction data dictionary
            value: Optional value in wei to send with transaction
            
        Returns:
            True if simulation succeeds
        """
        try:
            # Prepare call data
            call_data = {
                'from': self.account.address,
                'to': tx_data.get('to'),
                'data': tx_data.get('data'),
                'value': Wei(value or 0)
            }
            
            # Simulate transaction
            logger.info("Simulating transaction...")
            self.w3.eth.call(cast(TxParams, call_data))
            logger.info(f"[{self.chain_id}] Transaction simulation successful")
            return True
            
        except Exception as e:
            logger.error(f"[{self.chain_id}] Transaction simulation failed: {str(e)}")
            return False

    async def send_rebalance_transaction(self, tx_data: TxParams) -> Tuple[str, TxReceipt]:
        """Send a rebalance transaction"""
        try:
            # Let Base handle gas estimation
            if 'gas' in tx_data:
                del tx_data['gas']
            if 'maxFeePerGas' in tx_data:
                del tx_data['maxFeePerGas']
            if 'maxPriorityFeePerGas' in tx_data:
                del tx_data['maxPriorityFeePerGas']
                
            # Get gas price from RPC
            gas_price = self.w3.eth.generate_gas_price()
            if gas_price is None:
                gas_price = self.w3.eth.gas_price
            
            if gas_price is None:
                 logger.warning(f"[{self.chain_id}] Could not determine gas price via RPC or strategy. Falling back to default? Or raise error?")
                 # Decide on fallback or raise error
                 raise ValueError("Could not determine gas price")
            
            # Add 10% buffer to gas price for faster confirmation
            gas_price = int(gas_price * 1.1)
            
            logger.debug(f"[{self.chain_id}] Using gas price: {gas_price} wei")
            tx_data['gasPrice'] = Wei(gas_price)
            
            # Estimate gas with a 20% buffer
            estimated_gas = self.w3.eth.estimate_gas(tx_data)
            tx_data['gas'] = int(estimated_gas * 1.2)
            
            logger.debug(f"[{self.chain_id}] Estimated gas: {tx_data['gas']}")
            
            # Get nonce
            tx_data['nonce'] = self.w3.eth.get_transaction_count(self.account.address)
            
            # Sign transaction
            signed_tx = self.w3.eth.account.sign_transaction(tx_data, self.account.key)
            
            # Send transaction
            tx_hash = self.w3.eth.send_raw_transaction(signed_tx.rawTransaction)
            logger.info(f"[{self.chain_id}] Transaction sent with hash: {tx_hash.hex()}")
            
            # Wait for receipt
            tx_receipt = self.w3.eth.wait_for_transaction_receipt(tx_hash)
            logger.info(f"[{self.chain_id}] Transaction {tx_hash.hex()} mined in block: {tx_receipt['blockNumber']}")
            
            return tx_hash.hex(), tx_receipt
            
        except Exception as e:
            logger.error(f"[{self.chain_id}] Error sending transaction: {str(e)}")
            raise
