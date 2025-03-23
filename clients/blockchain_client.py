import os
import json
import logging
from web3 import Web3

from web3.gas_strategies.rpc import rpc_gas_price_strategy
from eth_account import Account
from typing import Dict, Optional, Tuple, Any, cast
from web3.types import TxReceipt, TxParams, Wei
from config.contracts import AGENT_CONTRACT_ADDRESS, AGENT_ABI_PATH

logger = logging.getLogger(__name__)

class BlockchainClient:
    def __init__(self):
        provider_url = os.getenv('WEB3_PROVIDER_URL')
        if not provider_url:
            raise ValueError("WEB3_PROVIDER_URL environment variable not set")
            
        self.w3 = Web3(Web3.HTTPProvider(provider_url))
        
        # Set gas price strategy to use RPC
        self.w3.eth.set_gas_price_strategy(rpc_gas_price_strategy)
        
        # Initialize account from private key
        private_key = os.getenv('PRIVATE_KEY')
        if not private_key:
            raise ValueError("PRIVATE_KEY environment variable not set")
            
        self.account = Account.from_key(private_key)
        
        # Load contract
        with open(AGENT_ABI_PATH) as f:
            contract_abi = json.load(f)
            
        self.agent_contract = self.w3.eth.contract(
            address=Web3.to_checksum_address(AGENT_CONTRACT_ADDRESS),
            abi=contract_abi
        )
        
        logger.info(f"Initialized blockchain client with address: {self.account.address}")
        
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
            logger.info("Transaction simulation successful")
            return True
            
        except Exception as e:
            logger.error(f"Transaction simulation failed: {str(e)}")
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
            
            # Add 10% buffer to gas price for faster confirmation
            gas_price = int(gas_price * 1.1)
            
            logger.debug(f"Using gas price: {gas_price} wei")
            tx_data['gasPrice'] = Wei(gas_price)
            
            # Estimate gas with a 20% buffer
            estimated_gas = self.w3.eth.estimate_gas(tx_data)
            tx_data['gas'] = int(estimated_gas * 1.2)
            
            logger.debug(f"Estimated gas: {tx_data['gas']}")
            
            # Get nonce
            tx_data['nonce'] = self.w3.eth.get_transaction_count(self.account.address)
            
            # Sign transaction
            signed_tx = self.w3.eth.account.sign_transaction(tx_data, self.account.key)
            
            # Send transaction
            tx_hash = self.w3.eth.send_raw_transaction(signed_tx.rawTransaction)
            logger.info(f"Transaction sent with hash: {tx_hash.hex()}")
            
            # Wait for receipt
            tx_receipt = self.w3.eth.wait_for_transaction_receipt(tx_hash)
            logger.info(f"Transaction mined in block: {tx_receipt['blockNumber']}")
            
            return tx_hash.hex(), tx_receipt
            
        except Exception as e:
            logger.error(f"Error sending transaction: {str(e)}")
            raise
