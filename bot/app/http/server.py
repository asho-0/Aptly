import logging

from aiohttp import web

from app.core.config import settings
from app.db.services import UserService
from app.db.session import db
from app.realtime import ExtensionGateway
from app.realtime.pairing import PairingStore

logger = logging.getLogger(__name__)


class ApiServer:
    def __init__(
        self, extension_gateway: ExtensionGateway, pairing_store: PairingStore
    ) -> None:
        self._extension_gateway = extension_gateway
        self._pairing_store = pairing_store
        self._user_service = UserService()
        self._app = web.Application()
        self._app.router.add_post("/api/pair", self.pair)
        self._app.router.add_get("/ws/extension", self.extension_socket)
        self._runner: web.AppRunner | None = None
        self._site: web.TCPSite | None = None

    async def start(self) -> None:
        self._runner = web.AppRunner(self._app)
        await self._runner.setup()
        self._site = web.TCPSite(self._runner, settings.API_HOST, settings.API_PORT)
        await self._site.start()
        logger.info(
            "API server listening on http://%s:%s", settings.API_HOST, settings.API_PORT
        )

    async def stop(self) -> None:
        if self._runner is not None:
            await self._runner.cleanup()
            self._runner = None
            self._site = None

    async def pair(self, request: web.Request) -> web.Response:
        payload = await request.json()
        pin = str(payload.get("pin", "")).strip()
        if not pin:
            return web.json_response({"error": "pin is required"}, status=400)

        pairing = await self._pairing_store.consume_pin(pin)
        if pairing is None:
            return web.json_response({"error": "pin is invalid or expired"}, status=404)

        async with db.session_context():
            user = await self._user_service.get_profile(pairing.chat_id)

        return web.json_response(
            {
                "token": pairing.token,
                "chatId": pairing.chat_id,
                "chat_id": pairing.chat_id,
                "profile": self._user_service.serialize_profile(user).model_dump(),
            }
        )

    async def extension_socket(self, request: web.Request) -> web.StreamResponse:
        websocket = web.WebSocketResponse()
        await websocket.prepare(request)
        await self._extension_gateway.handle_socket(websocket)
        return websocket
