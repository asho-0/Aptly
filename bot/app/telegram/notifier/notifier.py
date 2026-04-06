import asyncio
import logging
import time
from typing import cast
from collections import defaultdict
from collections.abc import Awaitable, Callable

from aiogram import Bot
from aiogram.exceptions import TelegramAPIError
from aiogram.types import InlineKeyboardMarkup, Message

from app.core.apartment import Apartment
from app.telegram.interface.keyboards import listing_link_keyboard

logger = logging.getLogger(__name__)

_MAX_CAPTION = 1024
_MAX_MESSAGE = 4096
_MIN_CHAT_INTERVAL_SECONDS = 1.2


class TelegramNotifier:
    def __init__(self, bot: Bot) -> None:
        self._bot = bot
        self._chat_locks: dict[int, asyncio.Lock] = defaultdict(asyncio.Lock)
        self._next_send_at: dict[int, float] = {}

    async def _wait_for_chat_slot(self, chat_id: int) -> None:
        delay = self._next_send_at.get(chat_id, 0.0) - time.monotonic()
        if delay > 0:
            await asyncio.sleep(delay)

    def _reserve_chat_slot(self, chat_id: int, delay_seconds: float) -> None:
        self._next_send_at[chat_id] = max(
            self._next_send_at.get(chat_id, 0.0), time.monotonic()
        ) + max(delay_seconds, 0.0)

    def _handle_send_error(
        self, action_name: str, chat_id: int, exc: TelegramAPIError
    ) -> None:
        logger.error("%s to %s failed: %s", action_name, chat_id, exc)

    def _handle_retry_error(
        self, action_name: str, chat_id: int, exc: TelegramAPIError
    ) -> None:
        logger.error("%s to %s failed after retry: %s", action_name, chat_id, exc)

    def _handle_flood_control(
        self, action_name: str, chat_id: int, retry_after: float
    ) -> None:
        logger.warning(
            "%s to %s hit Telegram flood control, waiting %ss",
            action_name,
            chat_id,
            retry_after,
        )

    async def _run_action_once(
        self,
        action: Callable[[], Awaitable[Message | bool | None]],
    ) -> Message | bool | None:
        return await action()

    async def _retry_after_flood_control(
        self,
        chat_id: int,
        action_name: str,
        action: Callable[[], Awaitable[Message | bool | None]],
        retry_after: float,
    ) -> Message | bool | None:
        self._handle_flood_control(action_name, chat_id, retry_after)
        self._reserve_chat_slot(chat_id, retry_after)
        await self._wait_for_chat_slot(chat_id)
        try:
            result = await self._run_action_once(action)
        except TelegramAPIError as exc:
            self._handle_retry_error(action_name, chat_id, exc)
            return None

        self._reserve_chat_slot(chat_id, _MIN_CHAT_INTERVAL_SECONDS)
        return result

    async def _run_with_rate_limit(
        self,
        chat_id: int,
        action_name: str,
        action: Callable[[], Awaitable[Message | bool | None]],
    ) -> Message | bool | None:
        async with self._chat_locks[chat_id]:
            await self._wait_for_chat_slot(chat_id)
            try:
                result = await self._run_action_once(action)
            except TelegramAPIError as exc:
                retry_after = getattr(exc, "retry_after", 0)
                if retry_after:
                    return await self._retry_after_flood_control(
                        chat_id, action_name, action, float(retry_after)
                    )
                self._handle_send_error(action_name, chat_id, exc)
                return None

            self._reserve_chat_slot(chat_id, _MIN_CHAT_INTERVAL_SECONDS)
            return result

    async def _send_photo(
        self,
        chat_id: int,
        image_url: str,
        caption: str,
        reply_markup: InlineKeyboardMarkup,
    ) -> Message | bool | None:
        return await self._run_with_rate_limit(
            chat_id,
            "send_photo",
            lambda: self._bot.send_photo(
                chat_id,
                image_url,
                caption=caption[:_MAX_CAPTION],
                parse_mode="HTML",
                reply_markup=reply_markup,
            ),
        )

    async def _send_message(
        self,
        chat_id: int,
        action_name: str,
        text: str,
        reply_markup: InlineKeyboardMarkup | None = None,
    ) -> Message | bool | None:
        return await self._run_with_rate_limit(
            chat_id,
            action_name,
            lambda: self._bot.send_message(
                chat_id,
                text[:_MAX_MESSAGE],
                parse_mode="HTML",
                disable_web_page_preview=False,
                reply_markup=reply_markup,
            ),
        )

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
            result = await self._send_photo(
                chat_id,
                apartment.image_url,
                text,
                reply_markup,
            )
            if result is not None:
                return True
        return (
            await self.send_listing_text(chat_id, text, reply_markup=reply_markup)
        ) is not None

    async def send_listing_text(
        self,
        chat_id: int,
        text: str,
        reply_markup: InlineKeyboardMarkup | None = None,
    ) -> Message | None:
        result = await self._send_message(
            chat_id,
            "send_listing_text",
            text,
            reply_markup,
        )
        return cast(Message | None, result)

    async def send_text(self, chat_id: int, text: str) -> bool:
        chunks = [text[i : i + _MAX_MESSAGE] for i in range(0, len(text), _MAX_MESSAGE)]
        for chunk in chunks:
            result = await self._send_message(chat_id, "send_text", chunk)
            if result is None:
                return False
        return True

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
