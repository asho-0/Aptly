import logging

import asyncio
from aiogram import Bot, Dispatcher
from aiogram.types import BotCommand
from aiogram.fsm.storage.memory import MemoryStorage

from app.telegram.handlers import UserRegistry
from app.telegram.handlers.commands_handler import setup_router

from app.db.session import db
from app.core.config import settings
from app.scrape_engine import ScraperEngine
from app.telegram.notifier import TelegramNotifier
from app.core.logging.structured_logger import setup_daily_logging

logger = logging.getLogger(__name__)


class Application:
    def __init__(self):
        self.bot = Bot(token=settings.TELEGRAM_BOT_TOKEN)
        self.dp = Dispatcher(storage=MemoryStorage())
        self.registry = UserRegistry()
        self.notifier = TelegramNotifier(self.bot)
        self.engine = ScraperEngine(self.notifier, self.registry)

    async def run(self) -> None:
        setup_daily_logging()
        logger.info("Starting up multi-user scraper...")

        await db.init()

        await self.bot.set_my_commands(
            [
                BotCommand(command="start", description="Open menu"),
                BotCommand(command="menu", description="Open menu"),
            ]
        )

        main_router = setup_router(self.registry, self.notifier)
        self.dp.include_router(main_router)
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
            await self.bot.session.close()
            await db.close()
            logger.info("Shutdown complete.")


if __name__ == "__main__":
    app = Application()
    try:
        asyncio.run(app.run())
    except (KeyboardInterrupt, SystemExit):
        pass
