import asyncio
import logging

from aiogram import Bot, Dispatcher
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import BotCommand

from app.core.config import settings
from app.core.logging.structured_logger import setup_daily_logging
from app.db.session import db
from app.http import ApiServer
from app.realtime import ExtensionGateway, PairingStore
from app.scrape_engine import ScraperEngine
from app.telegram.handlers import UserRegistry
from app.telegram.handlers.commands_handler import setup_router
from app.telegram.notifier import TelegramNotifier

logger = logging.getLogger(__name__)


class Application:
    def __init__(self):
        self.bot = Bot(token=settings.TELEGRAM_BOT_TOKEN)
        self.dp = Dispatcher(storage=MemoryStorage())
        self.registry = UserRegistry()
        self.notifier = TelegramNotifier(self.bot)
        self.pairing_store = PairingStore()
        self.extension_gateway = ExtensionGateway(self.notifier, self.pairing_store)
        self.registry.extension_gateway = self.extension_gateway
        self.api_server = ApiServer(self.extension_gateway, self.pairing_store)
        self.engine = ScraperEngine(self.notifier, self.registry)

    async def run(self) -> None:
        setup_daily_logging()
        logger.info("Starting bot microservice")
        await db.init()
        await self.bot.set_my_commands(
            [
                BotCommand(command="start", description="Open menu"),
                BotCommand(command="menu", description="Open menu"),
            ]
        )
        await self.extension_gateway.start()
        await self.api_server.start()
        self.dp.include_router(
            setup_router(
                self.registry, self.notifier, self.extension_gateway, self.pairing_store
            )
        )
        scrape_task = asyncio.create_task(self.engine.start_loop())

        try:
            await self.dp.start_polling(
                self.bot,
                allowed_updates=["message", "callback_query"],
                registry=self.registry,
                notifier=self.notifier,
            )
        finally:
            scrape_task.cancel()
            await self.api_server.stop()
            await self.extension_gateway.stop()
            await self.bot.session.close()
            await db.close()
            logger.info("Bot microservice stopped")


if __name__ == "__main__":
    try:
        asyncio.run(Application().run())
    except (KeyboardInterrupt, SystemExit):
        pass
