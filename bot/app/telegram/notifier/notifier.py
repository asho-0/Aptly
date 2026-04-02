import logging

from aiogram import Bot
from aiogram.exceptions import TelegramAPIError
from aiogram.types import InlineKeyboardMarkup, Message

from app.core.apartment import Apartment
from app.telegram.interface.keyboards import listing_link_keyboard

logger = logging.getLogger(__name__)

_MAX_CAPTION = 1024
_MAX_MESSAGE = 4096


class TelegramNotifier:
    def __init__(self, bot: Bot) -> None:
        self._bot = bot

    async def send_apartment(
        self,
        chat_id: int,
        apartment: Apartment,
        listing_id: int = 0,
        lang: str = "en",
        with_actions: bool = False,
    ) -> bool:
        text = apartment.to_telegram_message(lang=lang)
        reply_markup = listing_link_keyboard(apartment.url)
        if apartment.image_url:
            try:
                await self._bot.send_photo(
                    chat_id,
                    apartment.image_url,
                    caption=text[:_MAX_CAPTION],
                    parse_mode="HTML",
                    reply_markup=reply_markup,
                )
                return True
            except TelegramAPIError:
                pass
        return (
            await self.send_listing_text(chat_id, text, reply_markup=reply_markup)
        ) is not None

    async def send_listing_text(
        self,
        chat_id: int,
        text: str,
        reply_markup: InlineKeyboardMarkup | None = None,
    ) -> Message | None:
        try:
            return await self._bot.send_message(
                chat_id,
                text[:_MAX_MESSAGE],
                parse_mode="HTML",
                disable_web_page_preview=False,
                reply_markup=reply_markup,
            )
        except TelegramAPIError as e:
            logger.error("send_listing_text to %s failed: %s", chat_id, e)
            return None

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

    async def clear_listing_actions(self, chat_id: int, message_id: int) -> bool:
        try:
            await self._bot.edit_message_reply_markup(
                chat_id=chat_id,
                message_id=message_id,
                reply_markup=None,
            )
            return True
        except TelegramAPIError as e:
            logger.error(
                "clear_listing_actions for %s/%s failed: %s", chat_id, message_id, e
            )
            return False

    async def edit_listing_status(
        self,
        chat_id: int,
        message_id: int,
        text: str,
        is_caption_message: bool,
    ) -> bool:
        try:
            if is_caption_message:
                await self._bot.edit_message_caption(
                    chat_id=chat_id,
                    message_id=message_id,
                    caption=text[:_MAX_CAPTION],
                    reply_markup=None,
                )
            else:
                await self._bot.edit_message_text(
                    text=text[:_MAX_MESSAGE],
                    chat_id=chat_id,
                    message_id=message_id,
                    reply_markup=None,
                )
            return True
        except TelegramAPIError as e:
            logger.error(
                "edit_listing_status for %s/%s failed: %s", chat_id, message_id, e
            )
            return False

    async def send_startup_message(
        self, chat_id: int, scraper_names: list[str]
    ) -> None:
        names = "\n  • " + "\n  • ".join(scraper_names)
        await self.send_text(
            chat_id,
            f"🤖 Apartment Notifier started!\n\nMonitoring {len(scraper_names)} sources:{names}\n\nSend /help for commands.",
        )
