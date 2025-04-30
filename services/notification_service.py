import os
import logging
from typing import List, Any
from telegram import Bot
from telegram.constants import ParseMode
from models.morpho_data import Market
from config.networks import get_explorer_url

logger = logging.getLogger(__name__)

class NotificationService:
    def __init__(self):
        self.telegram_token = os.getenv('TELEGRAM_BOT_TOKEN')
        self.telegram_chat_id = os.getenv('TELEGRAM_CHAT_ID')
        if not self.telegram_token or not self.telegram_chat_id:
            raise ValueError("TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID must be set in environment variables")
        self.bot = Bot(token=self.telegram_token)
        
        # Type annotation to help the linter understand bot methods have their own self
        self.send_message: Any = self.bot.send_message

    async def notify_reallocation(self, user_address: str, chain_id: int, actions: List[dict], markets: dict[str, Market], tx_hash: str):
        """Send a notification about a reallocation event"""
        message = f"🔄 [Chain: {chain_id}] Reallocation executed for user:\n`{user_address}`\n\n"
        
        # Add details for each action
        for action in actions:
            market_id = action['market_id']
            action_type = action['action_type']
            amount_value = action['amount_value']
            symbol = action['symbol']
            
            market = markets.get(market_id)
            if market and hasattr(market.state, 'supply_apy'):
                apy_info = f" (APY: {market.state.supply_apy:.2%})"
            else:
                apy_info = ""
            
            message += f"• {action_type.title()}: {amount_value} {symbol}\n"
            message += f"  Market: {market_id[:8]}{apy_info}\n"
        
        # Add transaction link using chain-specific explorer
        try:
            explorer_base_url = get_explorer_url(chain_id)
            message += f"\n🔗 [View Transaction]({explorer_base_url}/tx/{tx_hash})"
        except ValueError as e:
            logger.error(f"Could not get explorer URL for chain {chain_id}: {e}")
            message += f"\nTransaction Hash: `{tx_hash}`"

        try:
            # Use the bot directly - ignore the linter error about missing self
            await self.bot.send_message(  # type: ignore
                chat_id=self.telegram_chat_id,
                text=message,
                parse_mode=ParseMode.MARKDOWN,
                disable_web_page_preview=True
            )
            logger.info(f"Sent reallocation notification for user {user_address} on chain {chain_id}")
        except Exception as e:
            logger.error(f"Failed to send Telegram notification: {str(e)}")

    async def notify_run(self, chain_id: int, reallocations: int, errors: int):
        """Send a notification about a run event"""
        message = f"📊 [Chain: {chain_id}] Automation run completed. Reallocations: {reallocations}, Errors: {errors}"
        try:
            # Use the bot directly - ignore the linter error about missing self
            await self.bot.send_message(  # type: ignore
                chat_id=self.telegram_chat_id,
                text=message,
                parse_mode=ParseMode.MARKDOWN,
                disable_web_page_preview=True
            )
            logger.info(f"Sent run notification for chain {chain_id}")
        except Exception as e:
            logger.error(f"Failed to send Telegram notification: {str(e)}")

    async def notify_error(self, chain_id: int, error_message: str):
        """Send a notification about a critical error during a run"""
        message = f"🚨 [Chain: {chain_id}] Critical error during automation run:\n\n`{error_message}`"
        try:
            await self.bot.send_message( # type: ignore
                chat_id=self.telegram_chat_id,
                text=message,
                parse_mode=ParseMode.MARKDOWN,
                disable_web_page_preview=True
            )
            logger.info(f"Sent error notification for chain {chain_id}")
        except Exception as e:
            logger.error(f"Failed to send Telegram error notification: {str(e)}")