import logging

from aiogram import Bot
from aiogram.exceptions import TelegramAPIError

from app.core.apartment import Apartment

logger = logging.getLogger(__name__)

_MAX_CAPTION = 1024
_MAX_MESSAGE = 4096


class TelegramNotifier:
    def __init__(self, bot: Bot) -> None:
        self._bot = bot

    async def send_apartment(
        self, chat_id: int, apartment: Apartment, lang: str = "en"
    ) -> bool:
        text = apartment.to_telegram_message(lang=lang)
        if apartment.image_url:
            try:
                await self._bot.send_photo(
                    chat_id,
                    apartment.image_url,
                    caption=text[:_MAX_CAPTION],
                    parse_mode="HTML",
                )
                return True
            except TelegramAPIError:
                pass
        return await self.send_text(chat_id, text)

    async def send_text(self, chat_id: int, text: str) -> bool:
        try:
            for chunk in [
                text[i : i + _MAX_MESSAGE] for i in range(0, len(text), _MAX_MESSAGE)
            ]:
                await self._bot.send_message(
                    chat_id, chunk, parse_mode="HTML", disable_web_page_preview=False
                )
            return True
        except TelegramAPIError as e:
            logger.error("send_text to %s failed: %s", chat_id, e)
            return False

    async def send_startup_message(
        self, chat_id: int, scraper_names: list[str]
    ) -> None:
        names = "\n  • " + "\n  • ".join(scraper_names)
        await self.send_text(
            chat_id,
            f"🤖 Apartment Notifier started!\n\nMonitoring {len(scraper_names)} sources:{names}\n\nSend /help for commands.",
        )
