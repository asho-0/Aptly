import logging
import time

import asyncio
from aiogram import Bot, Dispatcher
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import BotCommand

from app.telegram.handlers import UserRegistry
from app.telegram.handlers.commands_handler import setup_router

from app.config import settings
from app.db.repositories.listing_repo import ListingRepository
from app.db.session import db
from app.parsers.site import ALL_SCRAPERS
from app.telegram.notifier import TelegramNotifier
from app.db.services import ListingService
from app.core.apartment import Apartment
from app.parsers.base.base import BaseScraper

logger = logging.getLogger(__name__)


class ScraperEngine:
    def __init__(self, notifier: TelegramNotifier, registry: UserRegistry):
        self.notifier = notifier
        self.registry = registry
        self._known_site_ids: set[str] = set()

    async def run_cycle(self) -> int:
        active_users = await self.registry.fetch_all_active()
        if not active_users:
            return 0

        user_histories: dict[str, set[str]] = {}
        async with db.session_context():
            repo = ListingRepository()
            for chat_id, _ in active_users:
                user_histories[chat_id] = await repo.get_user_notified_uids(chat_id)

        scrapers = [cls() for cls in ALL_SCRAPERS]
        tasks = [asyncio.create_task(s.fetch_all()) for s in scrapers]

        all_results: list[tuple[BaseScraper, list[Apartment]]] = []
        current_site_ids: set[str] = set()

        for scraper, task in zip(scrapers, tasks):
            try:
                apartments = await task
                if not apartments:
                    continue
                all_results.append((scraper, apartments))
                for apt in apartments:
                    current_site_ids.add(apt.id)
            except Exception as exc:
                logger.error("[%s] fetch error: %s", scraper.slug, exc)
            finally:
                await scraper.close_session()

        new_on_site = current_site_ids - self._known_site_ids
        self._known_site_ids = current_site_ids

        if not new_on_site:
            logger.info("No new listings on sites, skipping notification cycle")
            return 0

        logger.info(
            "Found %d new listing(s) on sites, running notification cycle",
            len(new_on_site),
        )

        total_notified = 0
        async with db.session_context():
            svc = ListingService()
            for scraper, apartments in all_results:
                for apt in apartments:
                    for chat_id, store in active_users:
                        if store.is_paused or apt.id in user_histories[chat_id]:
                            continue
                        if not apt.matches(store.current_filter):
                            continue

                        outcome = await svc.process_apartment(
                            apt,
                            store.current_filter,
                            chat_id,
                            self.notifier,
                            lang=store.lang,
                        )

                        if outcome.notified:
                            user_histories[chat_id].add(apt.id)
                            total_notified += 1
                            await asyncio.sleep(settings.NOTIFICATION_DELAY)

                logger.info(
                    "[%s] cycle done: processed %d apartments",
                    scraper.slug,
                    len(apartments),
                )

        return total_notified

    async def start_loop(self) -> None:
        cycle = 0
        while True:
            cycle += 1
            logger.info("── Cycle #%d start ──", cycle)
            t0 = time.perf_counter()
            try:
                new_count = await self.run_cycle()
                duration = time.perf_counter() - t0
                logger.info(
                    "── Cycle #%d end: %d notified in %.1fs ──",
                    cycle,
                    new_count,
                    duration,
                )
            except Exception as exc:
                logger.exception("Cycle #%d failed: %s", cycle, exc)

            await asyncio.sleep(settings.CHECK_INTERVAL_SECONDS)


class Application:
    def __init__(self):
        self.bot = Bot(token=settings.TELEGRAM_BOT_TOKEN)
        self.dp = Dispatcher(storage=MemoryStorage())
        self.registry = UserRegistry()
        self.notifier = TelegramNotifier(self.bot)
        self.engine = ScraperEngine(self.notifier, self.registry)

    async def run(self) -> None:
        settings.setup_logging()
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
