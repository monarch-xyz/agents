import os
import logging
from typing import List
from telegram import Bot
from telegram.constants import ParseMode
from models.morpho_data import Market

logger = logging.getLogger(__name__)

class NotificationService:
    def __init__(self):
        self.telegram_token = os.getenv('TELEGRAM_BOT_TOKEN')
        self.telegram_chat_id = os.getenv('TELEGRAM_CHAT_ID')
        if not self.telegram_token or not self.telegram_chat_id:
            raise ValueError("TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID must be set in environment variables")
        self.bot = Bot(token=self.telegram_token)

    async def notify_reallocation(self, user_address: str, actions: List[dict], markets: dict[str, Market], tx_hash: str):
        """Send a notification about a reallocation event"""
        message = f"🔄 Reallocation executed for user:\n`{user_address}`\n\n"
        
        # Add details for each action
        for action in actions:
            market = markets.get(action.market_id)
            if market:
                symbol = market.loan_asset['symbol']
                apy = market.state['supplyApy']
                message += (
                    f"• {action.action_type.title()}: {action.amount.to_units()} {symbol}\n"
                    f"  Market: {action.market_id[:8]} (APY: {apy:.2%})\n"
                )
        
        # Add transaction link
        message += f"\n🔗 [View Transaction](https://explorer.base.org/tx/{tx_hash})"

        try:
            await self.bot.send_message(
                chat_id=self.telegram_chat_id,
                text=message,
                parse_mode=ParseMode.MARKDOWN,
                disable_web_page_preview=True
            )
            logger.info(f"Sent reallocation notification for user {user_address}")
        except Exception as e:
            logger.error(f"Failed to send Telegram notification: {str(e)}")


    async def notify_run(self, reallocations: int, errors: int):
        """Send a notification about a run event"""
        message = f"🔄 Automation run completed with {reallocations} reallocations and {errors} errors"
        try:
            await self.bot.send_message(
                chat_id=self.telegram_chat_id,
                text=message,
                parse_mode=ParseMode.MARKDOWN,
                disable_web_page_preview=True
            )
            logger.info("Sent run notification")
        except Exception as e:
            logger.error(f"Failed to send Telegram notification: {str(e)}")