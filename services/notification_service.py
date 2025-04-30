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
            raise ValueError("TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID must be set")
        self.bot = Bot(token=self.telegram_token)

    async def notify_reallocation(self, user_address: str, chain_id: int, actions: List[dict], markets: dict[str, Market], tx_hash: str):
        """Send a notification about a reallocation event."""
        message = f"🔄 [Chain: {chain_id}] Reallocation executed for user:\n`{user_address}`\n\n"

        for action in actions:
            market_id = action['market_id']
            action_type = action['action_type']
            amount_value = action['amount_value']
            symbol = action['symbol']

            market = markets.get(market_id)
            apy_info = ""
            if market and hasattr(market.state, 'supply_apy'):
                # Format APY safely
                try:
                    apy_info = f" (APY: {market.state.supply_apy:.2%})"
                except TypeError:
                    apy_info = " (APY: N/A)"

            message += f"• {action_type.title()}: {amount_value} {symbol}{apy_info}\n"

        try:
             explorer_base_url = get_explorer_url(chain_id)
             message += f"\n🔗 [View Transaction]({explorer_base_url}/tx/{tx_hash})"
        except ValueError as e:
             logger.error(f"Could not get explorer URL for chain {chain_id}: {e}")
             message += f"\nTransaction Hash: `{tx_hash}`"

        await self._send_telegram_message(message)
        logger.info(f"Sent reallocation notification for user {user_address} on chain {chain_id}")

    async def notify_run(self, chain_id: int, reallocations: int, errors: int):
        """Send a notification about a run event."""
        message = f"📊 [Chain: {chain_id}] Automation run completed. Reallocations: {reallocations}, Errors: {errors}"
        await self._send_telegram_message(message)
        logger.info(f"Sent run notification for chain {chain_id}")

    async def notify_error(self, chain_id: int, error_message: str):
        """Send a notification about a critical error during a run."""
        message = f"🚨 [Chain: {chain_id}] Critical error during automation run:\n\n`{error_message}`"
        await self._send_telegram_message(message)
        logger.info(f"Sent error notification for chain {chain_id}")

    async def _send_telegram_message(self, message: str):
        """Helper method to send message via Telegram bot."""
        try:
            await self.bot.send_message(#type: ignore
                chat_id=self.telegram_chat_id,
                text=message,
                parse_mode=ParseMode.MARKDOWN,
                disable_web_page_preview=True
            )
        except Exception as e:
            logger.error(f"Failed to send Telegram message: {str(e)}")