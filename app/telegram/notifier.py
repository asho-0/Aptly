# ============================================================
# notifier.py — Async Telegram notifier
# ============================================================

import asyncio
import logging

import aiohttp

from config import settings
from models import Apartment

logger = logging.getLogger(__name__)

TELEGRAM_API = f"https://api.telegram.org/bot{settings.TELEGRAM_BOT_TOKEN}"


class TelegramNotifier:
    def __init__(self, session: aiohttp.ClientSession):
        self.session   = session
        self.chat_id   = settings.TELEGRAM_CHAT_ID
        self._msg_lock = asyncio.Semaphore(1)   # serialize sends to avoid flood

    async def send_apartment(self, apt: Apartment) -> bool:
        """Send a single apartment notification. Returns True on success."""
        text = apt.to_telegram_message()
        return await self._send_message(text, photo_url=apt.image_url)

    async def send_text(self, text: str) -> bool:
        return await self._send_message(text)

    async def send_startup_message(self, scraper_names: list[str]) -> None:
        names = "\n  • " + "\n  • ".join(scraper_names)
        msg   = (
            "🤖 <b>Apartment Notifier started!</b>\n\n"
            f"Monitoring {len(scraper_names)} sources:{names}\n\n"
            "You will be notified of new listings matching your filters."
        )
        await self.send_text(msg)

    # ── Internal helpers ──────────────────────────────────────

    async def _send_message(
        self,
        text: str,
        photo_url: str | None = None,
        attempt: int = 1,
    ) -> bool:
        async with self._msg_lock:
            try:
                if photo_url:
                    ok = await self._send_photo(photo_url, text)
                    if ok:
                        return True
                # Fallback to plain message (or primary if no photo)
                return await self._send_plain(text)
            except Exception as exc:
                logger.error("Telegram send error (attempt %d): %s", attempt, exc)
                if attempt < 3:
                    await asyncio.sleep(2 ** attempt)
                    return await self._send_message(text, photo_url, attempt + 1)
                return False

    async def _send_plain(self, text: str) -> bool:
        url    = f"{TELEGRAM_API}/sendMessage"
        # Telegram max message length is 4096
        chunks = [text[i:i+4096] for i in range(0, len(text), 4096)]
        for chunk in chunks:
            payload: dict[str, int | str | bool] = {
                "chat_id":    self.chat_id,
                "text":       chunk,
                "parse_mode": "HTML",
                "disable_web_page_preview": False,
            }
            async with self.session.post(
                url,
                json    = payload,
                timeout = aiohttp.ClientTimeout(total=settings.REQUEST_TIMEOUT),
            ) as resp:
                data = await resp.json()
                if not data.get("ok"):
                    logger.warning("Telegram API error: %s", data)
                    return False
            await asyncio.sleep(0.3)   # stay under 30 msg/sec limit
        return True

    async def _send_photo(self, photo_url: str, caption: str) -> bool:
        url     = f"{TELEGRAM_API}/sendPhoto"
        caption = caption[:1024]       # Telegram caption limit
        payload = {
            "chat_id":    self.chat_id,
            "photo":      photo_url,
            "caption":    caption,
            "parse_mode": "HTML",
        }
        try:
            async with self.session.post(
                url,
                json    = payload,
                timeout = aiohttp.ClientTimeout(total=settings.REQUEST_TIMEOUT),
            ) as resp:
                data = await resp.json()
                return bool(data.get("ok"))
        except Exception:
            return False