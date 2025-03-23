import os
import json
import logging
from typing import List, Dict, Optional, Tuple
from web3 import Web3
from web3.contract.contract import Contract
from web3.types import TxReceipt, TxParams
from eth_typing import Address
from models.morpho_data import Market, MarketPosition
from models.user_data import MarketCap
from strategies.base import MarketAction
from utils.token_amount import TokenAmount
from clients.blockchain_client import BlockchainClient

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)

class BlockchainService:
    """Service for composing blockchain transactions"""
    
    def __init__(self, blockchain_client: BlockchainClient):
        self.blockchain_client = blockchain_client
    
    def _build_market_params(self, market: Market) -> tuple:
        """Build market params struct for contract call"""        
        logger.debug(f"Building market params for market: {market.loan_asset.address}")
        logger.debug(f"Collateral asset: {market.collateral_asset.address}")
        logger.debug(f"Oracle address: {market.oracle_address}")
        logger.debug(f"IRM address: {market.irm_address}")
        logger.debug(f"LLTV: {market.lltv}")

        try:
            params = (
                Web3.to_checksum_address(market.loan_asset.address),
                Web3.to_checksum_address(market.collateral_asset.address),
                Web3.to_checksum_address(market.oracle_address),
                Web3.to_checksum_address(market.irm_address),
                int(market.lltv)
            )
            logger.debug(
                f"Built market params - "
                f"loan: {params[0]}, "
                f"collateral: {params[1]}, "
                f"oracle: {params[2]}, "
                f"irm: {params[3]}, "
                f"lltv: {params[4]}"
            )
            return params
        except Exception as e:
            logger.error(f"Error building market params: {str(e)}")
            # logger.error(f"Market data: {market.__dict__}")
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
                    logger.warning(f"Market not found for action: {action.market_id}")
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
            
            if not from_markets_params:
                raise ValueError("No withdrawal actions found")

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
            logger.debug(f"Current gas price: {gas_price}")

            tx_data = self.blockchain_client.agent_contract.functions.rebalance(
                Web3.to_checksum_address(user_address),  # onBehalf
                token_address,  # token
                from_markets_params,  # fromMarkets array [(market_params, assets, shares), ...]
                to_markets_params     # toMarkets array [(market_params, assets, shares), ...]
            ).build_transaction({
                'from': self.blockchain_client.account.address,
                'gasPrice': gas_price,  # Use current gas price from Base
            })
            
            logger.info("Transaction data composed, sending to blockchain...")
            logger.debug(f"Transaction data: {tx_data}")
            
            # Send transaction and return results
            return await self.blockchain_client.send_rebalance_transaction(tx_data)
            
        except Exception as e:
            logger.error(f"Error in rebalance: {str(e)}")
            logger.error(f"User address: {user_address}")
            # logger.error(f"Actions: {[a.__dict__ for a in actions]}")
            raise
