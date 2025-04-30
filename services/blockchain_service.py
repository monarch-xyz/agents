import os
import json
import logging
from typing import List, Dict, Optional, Tuple, cast
from web3 import Web3
# from web3.contract.contract import Contract # Unused
from web3.types import TxReceipt, TxParams
# from eth_typing import Address # Unused
from models.morpho_data import Market # MarketPosition removed
# from models.user_data import MarketCap # Unused
from strategies.base import MarketAction
# from utils.token_amount import TokenAmount # Unused
from clients.blockchain_client import BlockchainClient

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)

class BlockchainService:
    """Service for composing blockchain transactions"""
    
    def __init__(self, blockchain_client: BlockchainClient):
        self.blockchain_client = blockchain_client
    
    def _build_market_params(self, market: Market) -> tuple:
        """Build market params struct for contract call"""        
        logger.debug(
            f"Building market params - "
            f"loan: {market.loan_asset.address}, "
            f"collateral: {market.collateral_asset.address}, "
            f"oracle: {market.oracle_address}, "
            f"irm: {market.irm_address}, "
            f"lltv: {market.lltv}"
        )
        try:
            params = (
                Web3.to_checksum_address(market.loan_asset.address),
                Web3.to_checksum_address(market.collateral_asset.address),
                Web3.to_checksum_address(market.oracle_address),
                Web3.to_checksum_address(market.irm_address),
                int(market.lltv)
            )
            return params
        except Exception as e:
            logger.error(f"Error building market params for market {market.id}: {str(e)}")
            raise
    
    async def rebalance(
        self,
        user_address: str,
        actions: List[MarketAction],
        markets: Dict[str, Market]
    ) -> Tuple[str, TxReceipt]:
        """
        Compose and send rebalance transaction
        
        Args:
            user_address: Address of the user to rebalance for
            actions: List of market actions from strategy
            markets: Dictionary of markets by uniqueKey
            
        Returns:
            Tuple of (transaction hash, transaction receipt)
        """
        try:
            logger.info(f"Composing rebalance transaction for user: {user_address}")
            logger.debug(f"Actions to process: {len(actions)}")
            
            # Split actions into from (withdrawals) and to (supplies)
            from_markets_params = []  # [(market_params, assets, shares), ...]
            to_markets_params = []    # [(market_params, assets, shares), ...]
            
            
            for action in actions:
                market = markets.get(action.market_id)
                if not market:
                    logger.warning(f"Market not found for action: {action.market_id}, skipping action.")
                    continue
                    
                logger.debug(f"Processing action for market {market.unique_key}")
                logger.debug(f"Action type: {action.action_type}")
                logger.debug(f"Action amount: {action.amount.to_units() if action.amount else 0}")
                logger.debug(f"Action shares: {action.shares.to_units() if action.shares else 0}")
                
                # Build market parameters
                market_params = self._build_market_params(market)
                assets = action.amount.to_wei() if action.amount else 0
                shares = action.shares.to_wei() if action.shares else 0
                
                # Create the tuple for this market action
                market_action_tuple = (market_params, assets, shares)
                
                if action.action_type == 'withdraw':
                    from_markets_params.append(market_action_tuple)
                    logger.info(
                        f"Withdrawal from {market.unique_key[:10]}: "
                        f"assets={action.amount.to_units() if action.amount else 0}, "
                        f"shares={action.shares.to_units() if action.shares else 0}"
                    )
                else:
                    to_markets_params.append(market_action_tuple)
                    logger.info(
                        f"Supply to {market.unique_key[:10]}: "
                        f"assets={action.amount.to_units() if action.amount else 0}"
                    )
            
            if not from_markets_params or not to_markets_params:
                # Handle cases where strategy might result in only one type of action
                # or if markets were skipped.
                logger.warning(f"Rebalance for {user_address} resulted in no valid from/to actions. Skipping tx.")
                # Decide what to return or if an error should be raised
                # For now, let's assume skipping is okay, but might need adjustment.
                # Returning dummy values or raising a specific error might be better.
                raise ValueError("Cannot rebalance: Invalid action combination (no from or no to actions).")
                # Or: return ("0xSKIPPED", {}) # Example placeholder

            # change the last "amount" of the to market to uint256(max), indicating all remaining assets
            to_markets_params[-1] = list(to_markets_params[-1])
            to_markets_params[-1][1] = 2**256 - 1
            
            # Get token address from first market (all markets should have same token)
            token_address = Web3.to_checksum_address(
                markets[actions[0].market_id].loan_asset.address
            )
            
            logger.debug(f"Using token address: {token_address}")
            
            # Log final parameters
            logger.debug("Final transaction parameters:")
            logger.debug(f"user_address: {user_address}")
            logger.debug(f"token_address: {token_address}")
            
            # Build transaction data
            # Get current gas price from Base
            gas_price = self.blockchain_client.w3.eth.gas_price
            logger.debug(f"Current gas price from node: {gas_price}")

            tx_params = {
                'from': self.blockchain_client.account.address,
                'gasPrice': gas_price,
            }

            tx = self.blockchain_client.agent_contract.functions.rebalance(
                Web3.to_checksum_address(user_address),
                token_address,
                from_markets_params,
                to_markets_params
            )

            # Build transaction without nonce/gas initially, casting to TxParams
            built_tx = tx.build_transaction(cast(TxParams, tx_params))
            
            logger.info("Transaction data composed, sending to blockchain client...")
            logger.debug(f"Transaction data (pre-send processing): {built_tx}")
            
            # Send transaction and return results
            return await self.blockchain_client.send_rebalance_transaction(built_tx)
            
        except Exception as e:
            logger.error(f"Error composing/sending rebalance for {user_address}: {str(e)}")
            raise
