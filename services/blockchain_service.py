import os
import json
import logging
from typing import List, Dict, Optional, Tuple
from web3 import Web3
from web3.contract import Contract
from web3.types import TxReceipt
from eth_typing import Address
from models.morpho_data import Market, MarketPosition
from models.user_data import MarketCap
from strategies.base import MarketAction
from utils.token_amount import TokenAmount
from clients.blockchain_client import BlockchainClient

logger = logging.getLogger(__name__)

class BlockchainService:
    """Service for composing blockchain transactions"""
    
    def __init__(self, blockchain_client: BlockchainClient):
        self.blockchain_client = blockchain_client
    
    def _build_market_params(self, market: Market) -> tuple:
        """Build market params struct for contract call"""
        return (
            Web3.to_checksum_address(market.loan_asset['address']),
            Web3.to_checksum_address(market.collateral_asset['address']),
            Web3.to_checksum_address(market.oracle),
            Web3.to_checksum_address(market.irm),
            int(market.lltv)
        )
    
    def _build_rebalance_params(
        self,
        market: Market,
        action: MarketAction
    ) -> tuple:
        """Build rebalance market params struct for contract call"""
        return (
            self._build_market_params(market),  # market params tuple
            action.amount.to_wei() if action.amount else 0,  # assets
            action.shares.to_wei() if action.shares else 0  # shares
        )
    
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
        logger.info(f"Composing rebalance transaction for user: {user_address}")
        
        # Split actions into from (withdrawals) and to (supplies)
        from_markets = []
        to_markets = []
        
        # Track total amounts for logging
        total_withdrawal = TokenAmount.from_wei(0)
        total_supply = TokenAmount.from_wei(0)
        
        for action in actions:
            market = markets.get(action.market_id)
            if not market:
                logger.warning(f"Market not found for action: {action.market_id}")
                continue
                
            params = self._build_rebalance_params(market, action)
            
            if action.action_type == 'withdraw':
                from_markets.append(params)
                if action.amount:
                    total_withdrawal += action.amount
                logger.info(
                    f"Withdrawal from {market.unique_key[:10]}: "
                    f"assets={action.amount.to_units() if action.amount else 0}, "
                    f"shares={action.shares.to_units() if action.shares else 0}"
                )
            else:
                to_markets.append(params)
                if action.amount:
                    total_supply += action.amount
                logger.info(
                    f"Supply to {market.unique_key[:10]}: "
                    f"assets={action.amount.to_units() if action.amount else 0}"
                )
        
        if not from_markets:
            raise ValueError("No withdrawal actions found")
            
        logger.info(
            f"Total rebalance amounts - "
            f"Withdrawals: {total_withdrawal.to_units()}, "
            f"Supplies: {total_supply.to_units()}"
        )
        
        # Get token address from first market (all markets should have same token)
        token_address = Web3.to_checksum_address(
            markets[actions[0].market_id].loan_asset['address']
        )
        
        # Build transaction data
        tx_data = self.blockchain_client.agent_contract.functions.rebalance(
            Web3.to_checksum_address(user_address),  # onBehalf
            token_address,  # token
            from_markets,  # fromMarkets
            to_markets  # toMarkets
        ).build_transaction({
            'from': self.blockchain_client.account.address,
        })
        
        logger.info("Transaction data composed, sending to blockchain...")
        
        # Send transaction and return results
        return await self.blockchain_client.send_rebalance_transaction(tx_data)
