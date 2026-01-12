"""Telegram bot integration"""

from typing import Optional
import asyncio
from telegram import Bot
from telegram.constants import ParseMode
from telegram.error import TelegramError
from app.core.config import settings
from app.core.logging import get_logger

logger = get_logger(__name__)


class TelegramClient:
    """Client for Telegram Bot API"""

    def __init__(self):
        self.enabled = bool(settings.telegram_bot_token and settings.telegram_chat_id)
        if self.enabled:
            self.bot = Bot(token=settings.telegram_bot_token)
            self.chat_id = settings.telegram_chat_id
            logger.info("Telegram bot initialized", chat_id=self.chat_id)
        else:
            self.bot = None
            logger.info("Telegram bot disabled (missing token or chat_id)")

    async def send_message(
        self,
        text: str,
        parse_mode: str = ParseMode.MARKDOWN,
        disable_web_page_preview: bool = False,
    ) -> bool:
        """Send text message to Telegram
        
        Args:
            text: Message text
            parse_mode: Parse mode (Markdown, HTML, or None)
            disable_web_page_preview: Disable link previews
            
        Returns:
            True if sent successfully
        """
        if not self.enabled:
            logger.warning("Telegram not enabled, message not sent")
            return False

        try:
            await self.bot.send_message(
                chat_id=self.chat_id,
                text=text,
                parse_mode=parse_mode,
                disable_web_page_preview=disable_web_page_preview,
            )
            logger.info("Telegram message sent", text_length=len(text))
            return True

        except TelegramError as e:
            logger.error("Failed to send Telegram message", error=str(e))
            return False

        except Exception as e:
            logger.error("Unexpected error sending Telegram message", error=str(e))
            return False

    async def send_notification(
        self,
        title: str,
        message: str,
        priority: str = "normal",
    ) -> bool:
        """Send formatted notification
        
        Args:
            title: Notification title
            message: Notification message
            priority: Priority level (low, normal, high, urgent)
            
        Returns:
            True if sent successfully
        """
        # Format with emoji based on priority
        emoji_map = {
            "low": "ℹ️",
            "normal": "📢",
            "high": "⚠️",
            "urgent": "🚨",
        }
        emoji = emoji_map.get(priority, "📢")

        text = f"{emoji} *{title}*\n\n{message}"
        return await self.send_message(text)

    async def send_action_log(
        self,
        user_id: str,
        intent: str,
        actions: list,
        success: bool,
        error: Optional[str] = None,
    ) -> bool:
        """Send action execution log
        
        Args:
            user_id: User identifier
            intent: Action intent
            actions: List of actions
            success: Whether execution succeeded
            error: Optional error message
            
        Returns:
            True if sent successfully
        """
        status_emoji = "✅" if success else "❌"
        status_text = "успешно" if success else "с ошибкой"

        text = f"{status_emoji} *Действие выполнено {status_text}*\n\n"
        text += f"👤 Пользователь: `{user_id}`\n"
        text += f"🎯 Намерение: `{intent}`\n"
        text += f"📋 Действия: `{len(actions)}`\n"

        if error:
            text += f"\n❌ Ошибка: `{error}`"

        return await self.send_message(text)

    async def send_search_results(
        self,
        query: str,
        results_text: str,
        source: str = "web",
    ) -> bool:
        """Send search results
        
        Args:
            query: Search query
            results_text: Formatted results
            source: Search source (web, habr, etc.)
            
        Returns:
            True if sent successfully
        """
        source_emoji = {
            "web": "🌐",
            "habr": "📚",
            "perplexity": "🔍",
        }.get(source, "🔍")

        text = f"{source_emoji} *Результаты поиска*\n\n"
        text += f"Запрос: _{query}_\n\n"
        text += results_text

        return await self.send_message(
            text,
            disable_web_page_preview=True,
        )

    async def send_daily_digest(
        self,
        summaries: dict,
    ) -> bool:
        """Send daily digest
        
        Args:
            summaries: Dictionary of summaries by category
            
        Returns:
            True if sent successfully
        """
        text = "📊 *Ежедневный дайджест*\n\n"

        if "home_events" in summaries:
            text += f"🏠 *Дом*\n{summaries['home_events']}\n\n"

        if "news" in summaries:
            text += f"📰 *Новости*\n{summaries['news']}\n\n"

        if "tech" in summaries:
            text += f"💻 *Технологии*\n{summaries['tech']}\n\n"

        return await self.send_message(text)

    async def close(self):
        """Close bot session"""
        if self.bot:
            # Telegram bot doesn't require explicit close in newer versions
            pass


# Global client instance
telegram_client = TelegramClient()


