import os
import logging
from typing import List, Any
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
        
        # Type annotation to help the linter understand bot methods have their own self
        self.send_message: Any = self.bot.send_message

    async def notify_reallocation(self, user_address: str, actions: List[dict], markets: dict[str, Market], tx_hash: str):
        """Send a notification about a reallocation event"""
        message = f"🔄 Reallocation executed for user:\n`{user_address}`\n\n"
        
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
        
        # Add transaction link
        message += f"\n🔗 [View Transaction](https://explorer.base.org/tx/{tx_hash})"

        try:
            # Use the bot directly - ignore the linter error about missing self
            await self.bot.send_message(  # type: ignore
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
            # Use the bot directly - ignore the linter error about missing self
            await self.bot.send_message(  # type: ignore
                chat_id=self.telegram_chat_id,
                text=message,
                parse_mode=ParseMode.MARKDOWN,
                disable_web_page_preview=True
            )
            logger.info("Sent run notification")
        except Exception as e:
            logger.error(f"Failed to send Telegram notification: {str(e)}")