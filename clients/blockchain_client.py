import os
import json
import logging
from web3 import Web3
from web3.middleware import geth_poa_middleware
from web3.gas_strategies.rpc import rpc_gas_price_strategy
from eth_account import Account
from typing import Dict, Optional, Tuple
from web3.types import TxReceipt

logger = logging.getLogger(__name__)

# Contract Constants
AGENT_CONTRACT_ADDRESS = "0x6a9BA5c91fDd608b3F85c3E031a4f531f331f545"
AGENT_ABI_PATH = os.path.join(os.path.dirname(__file__), "../utils/abi/agent-v1.json")

class BlockchainClient:
    def __init__(self):
        provider_url = os.getenv('WEB3_PROVIDER_URL')
        if not provider_url:
            raise ValueError("WEB3_PROVIDER_URL environment variable not set")
            
        self.w3 = Web3(Web3.HTTPProvider(provider_url))
        
        # Add PoA middleware for Base chain
        self.w3.middleware_onion.inject(geth_poa_middleware, layer=0)
        
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
                'value': value or 0
            }
            
            # Simulate transaction
            logger.info("Simulating transaction...")
            self.w3.eth.call(call_data)
            logger.info("Transaction simulation successful")
            return True
            
        except Exception as e:
            logger.error(f"Transaction simulation failed: {str(e)}")
            return False

    async def send_transaction(
        self,
        tx_data: Dict,
        value: Optional[int] = None
    ) -> Tuple[str, TxReceipt]:
        """
        Send a transaction to the blockchain
        
        Args:
            tx_data: Transaction data dictionary
            value: Optional value in wei to send with transaction
            
        Returns:
            Tuple of (transaction hash, transaction receipt)
        """
        try:
            # Simulate transaction first
            if not await self.simulate_transaction(tx_data, value):
                raise ValueError("Transaction simulation failed")
            
            # Get the latest nonce
            nonce = self.w3.eth.get_transaction_count(self.account.address)
            logger.info(f"Using nonce: {nonce}")
            
            # Update transaction data
            tx_data.update({
                'nonce': nonce,
                'from': self.account.address,
            })
            
            if value:
                tx_data['value'] = value
                
            # Let Base handle gas estimation
            if 'gas' in tx_data:
                del tx_data['gas']
            if 'maxFeePerGas' in tx_data:
                del tx_data['maxFeePerGas']
            if 'maxPriorityFeePerGas' in tx_data:
                del tx_data['maxPriorityFeePerGas']
            
            # Estimate gas with buffer
            estimated_gas = self.w3.eth.estimate_gas(tx_data)
            gas_buffer = 1.2  # 20% buffer
            tx_data['gas'] = int(estimated_gas * gas_buffer)
            logger.info(f"Estimated gas (with {gas_buffer}x buffer): {tx_data['gas']}")
            
            # Sign transaction
            signed_tx = self.account.sign_transaction(tx_data)
            
            # Send transaction
            tx_hash = self.w3.eth.send_raw_transaction(signed_tx.rawTransaction)
            tx_hash_hex = tx_hash.hex()
            logger.info(f"Transaction sent: {tx_hash_hex}")
            
            # Wait for receipt
            logger.info("Waiting for transaction receipt...")
            receipt = self.w3.eth.wait_for_transaction_receipt(tx_hash)
            
            # Log receipt details
            status = 'successful' if receipt['status'] == 1 else 'failed'
            gas_used = receipt['gasUsed']
            block_number = receipt['blockNumber']
            logger.info(
                f"Transaction {status} in block {block_number}. "
                f"Gas used: {gas_used} ({(gas_used/tx_data['gas'])*100:.1f}% of estimate)"
            )
            
            return tx_hash_hex, receipt
            
        except Exception as e:
            logger.error(f"Transaction failed: {str(e)}")
            raise

    async def send_rebalance_transaction(self, tx_data: Dict) -> Tuple[str, TxReceipt]:
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
            tx_data['gasPrice'] = gas_price
            
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
