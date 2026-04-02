import logging

import aiohttp

from app.core.config import settings

logger = logging.getLogger(__name__)


class GatewayClient:
    def __init__(self) -> None:
        self._base_url = settings.GATEWAY_BASE_URL.rstrip("/")
        self._session: aiohttp.ClientSession | None = None
        self._timeout = aiohttp.ClientTimeout(total=settings.REQUEST_TIMEOUT)

    async def start(self) -> None:
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession(timeout=self._timeout)

    async def stop(self) -> None:
        if self._session is not None and not self._session.closed:
            await self._session.close()
        self._session = None

    async def is_connected(self, chat_id: str) -> bool:
        session = await self._ensure_session()
        url = f"{self._base_url}/api/extension/{chat_id}/connected"
        try:
            async with session.get(url) as response:
                if response.status != 200:
                    return False
                data = await response.json()
                return bool(data.get("connected", False))
        except aiohttp.ClientError:
            return False

    async def push_profile(self, chat_id: str, profile: dict[str, object]) -> bool:
        session = await self._ensure_session()
        url = f"{self._base_url}/api/profile-updated"
        payload = {
            "chatId": chat_id,
            "profile": profile,
        }
        try:
            async with session.post(url, json=payload) as response:
                if response.status != 200:
                    return False
                data = await response.json()
                return bool(data.get("delivered", False))
        except aiohttp.ClientError:
            return False

    async def dispatch_fill(
        self,
        chat_id: str,
        apartment_url: str,
        user_data: dict[str, str],
        message_id: int,
        is_caption_message: bool,
    ) -> str:
        session = await self._ensure_session()
        url = f"{self._base_url}/api/extension/fill-dispatch"
        payload = {
            "chatId": chat_id,
            "apartmentUrl": apartment_url,
            "userData": user_data,
            "messageId": message_id,
            "isCaptionMessage": is_caption_message,
        }
        try:
            async with session.post(url, json=payload) as response:
                if response.status == 409:
                    raise RuntimeError("Extension is not connected")
                if response.status >= 400:
                    text = await response.text()
                    raise RuntimeError(f"Gateway returned {response.status}: {text}")
                data = await response.json()
                return str(data.get("requestId", ""))
        except aiohttp.ClientError as exc:
            logger.error("Failed to dispatch fill via gateway: %s", exc)
            raise RuntimeError("Gateway request failed") from exc

    async def _ensure_session(self) -> aiohttp.ClientSession:
        if self._session is None or self._session.closed:
            await self.start()
        if self._session is None:
            raise RuntimeError("Gateway client session is not available")
        return self._session
