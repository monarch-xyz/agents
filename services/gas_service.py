"""Service for monitoring gas fees"""

import os
import time
import logging
import asyncio
from web3 import Web3
from web3.middleware import geth_poa_middleware

logger = logging.getLogger(__name__)

class GasService:
    """Service for monitoring gas fees on L1"""
    
    def __init__(self, max_gas_price: int = 15, max_retries: int = 180, retry_delay: int = 60):
        """Initialize gas service
        
        Args:
            max_gas_price: Maximum acceptable gas price in gwei (default: 50)
            max_retries: Maximum number of retries (default: 120)
            retry_delay: Delay between retries in seconds (default: 60)
        """
        self.max_gas_price = max_gas_price
        self.max_retries = max_retries
        self.retry_delay = retry_delay
        
        # Initialize Web3
        provider_url = os.getenv('L1_WEB3_PROVIDER_URL')
        if not provider_url:
            raise ValueError("L1_WEB3_PROVIDER_URL environment variable not set")
            
        self.w3 = Web3(Web3.HTTPProvider(provider_url))
        self.w3.middleware_onion.inject(geth_poa_middleware, layer=0)
        
    async def wait_for_acceptable_gas(self) -> float:
        """Wait until gas price is below maximum threshold
        
        Returns:
            Current gas price in gwei
        
        Raises:
            TimeoutError: If gas price remains high after max retries
        """
        for attempt in range(self.max_retries):
            # Get current gas price
            gas_price_wei = self.w3.eth.gas_price
            gas_price_gwei = self.w3.from_wei(gas_price_wei, 'gwei')
            
            logger.info(f"Current L1 gas price: {gas_price_gwei:.1f} gwei {gas_price_wei}")

            if gas_price_gwei <= self.max_gas_price:
                return gas_price_gwei
                
            if attempt < self.max_retries - 1:
                logger.warning(
                    f"Gas price too high ({gas_price_gwei:.1f} gwei > {self.max_gas_price} gwei). "
                    f"Waiting {self.retry_delay} seconds..."
                )
                await asyncio.sleep(self.retry_delay)
            
        raise TimeoutError(
            f"Gas price remained above {self.max_gas_price} gwei for "
            f"{self.max_retries * self.retry_delay} seconds"
        )
