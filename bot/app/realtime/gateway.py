import asyncio
import json
import logging
from dataclasses import dataclass
from uuid import uuid4

from aiohttp import WSMsgType, web

from app.telegram.notifier import TelegramNotifier
from app.realtime.pairing import PairingStore

logger = logging.getLogger(__name__)


@dataclass
class PendingFillRequest:
    chat_id: int
    message_id: int
    is_caption_message: bool


class ExtensionGateway:
    def __init__(self, notifier: TelegramNotifier, pairing_store: PairingStore) -> None:
        self._notifier = notifier
        self._pairing_store = pairing_store
        self._connections: dict[str, web.WebSocketResponse] = {}
        self._pending: dict[str, PendingFillRequest] = {}
        self._lock = asyncio.Lock()

    async def start(self) -> None:
        return None

    async def stop(self) -> None:
        async with self._lock:
            sockets = list(self._connections.values())
            self._connections.clear()
            self._pending.clear()

        for socket in sockets:
            await socket.close()

    async def is_connected(self, chat_id: str) -> bool:
        async with self._lock:
            websocket = self._connections.get(chat_id)
            return websocket is not None and not websocket.closed

    async def dispatch_fill(
        self,
        chat_id: str,
        apartment_url: str,
        user_data: dict[str, object],
        message_id: int,
        is_caption_message: bool,
    ) -> str:
        async with self._lock:
            websocket = self._connections.get(chat_id)
            if websocket is None:
                raise RuntimeError("No Chrome extension connected for this user")

            request_id = uuid4().hex
            self._pending[request_id] = PendingFillRequest(
                chat_id=int(chat_id),
                message_id=message_id,
                is_caption_message=is_caption_message,
            )

        await websocket.send_json(
            {
                "type": "execute_fill",
                "requestId": request_id,
                "payload": {
                    "apartmentUrl": apartment_url,
                    "userData": user_data,
                },
            }
        )
        return request_id

    async def push_profile(self, chat_id: str, profile: dict[str, object]) -> bool:
        async with self._lock:
            websocket = self._connections.get(chat_id)
            if websocket is None or websocket.closed:
                return False

        await websocket.send_json(
            {
                "type": "profile_updated",
                "payload": {
                    "profile": profile,
                },
            }
        )
        return True

    async def handle_socket(self, websocket: web.WebSocketResponse) -> None:
        chat_id = await self._authenticate(websocket)
        if chat_id is None:
            return

        try:
            async for message in websocket:
                if message.type != WSMsgType.TEXT:
                    continue

                payload = json.loads(message.data)
                message_type = str(payload.get("type", ""))
                if message_type == "fill_result":
                    await self._handle_fill_result(payload)
                    continue

                await websocket.send_json(
                    {"type": "error", "error": "unsupported message type"}
                )
        finally:
            async with self._lock:
                current = self._connections.get(chat_id)
                if current is websocket:
                    self._connections.pop(chat_id, None)

    async def _authenticate(self, websocket: web.WebSocketResponse) -> str | None:
        message = await websocket.receive()
        if message.type != WSMsgType.TEXT:
            await websocket.close()
            return None

        payload = json.loads(message.data)
        if str(payload.get("type", "")) != "authenticate":
            await websocket.send_json(
                {"type": "auth_error", "error": "authentication required"}
            )
            await websocket.close()
            return None

        token = str(payload.get("token", "")).strip()
        chat_id = await self._pairing_store.resolve_token(token)
        if chat_id is None:
            await websocket.send_json({"type": "auth_error", "error": "invalid token"})
            await websocket.close()
            return None

        async with self._lock:
            previous = self._connections.get(chat_id)
            self._connections[chat_id] = websocket

        if previous is not None and previous is not websocket:
            await previous.close()

        await websocket.send_json({"type": "auth_ok"})
        logger.info("Extension authenticated for chat_id=%s", chat_id)
        return chat_id

    async def _handle_fill_result(self, payload: dict[str, object]) -> None:
        request_id = str(payload.get("requestId", "")).strip()
        status = str(payload.get("status", "error")).strip()
        error = str(payload.get("error", "")).strip()

        if not request_id:
            return

        async with self._lock:
            pending = self._pending.pop(request_id, None)

        if pending is None:
            return

        if status != "success" and error:
            logger.error("Fill failed for request %s: %s", request_id, error)
            return

        await self._notifier.edit_listing_status(
            chat_id=pending.chat_id,
            message_id=pending.message_id,
            text="✅ Submitted",
            is_caption_message=pending.is_caption_message,
        )
