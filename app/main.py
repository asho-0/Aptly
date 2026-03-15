import asyncio
import logging
from datetime import datetime

from aiogram import Bot, Dispatcher
from aiogram.fsm.storage.memory import MemoryStorage

import app.seen as seen
from app.bot_commands import UserRegistry, router
from app.config import settings
from app.db.repositories.listing_repo import ListingRepository
from app.db.services import ProcessResult, process_apartment
from app.db.session import db
from app.logging.structured_logger import scrape_logger
from app.parsers.site import ALL_SCRAPERS
from app.telegram.notifier import TelegramNotifier
from app.logging.structured_logger import setup_daily_logging

logger = logging.getLogger(__name__)


async def warm_seen_cache() -> None:
    async with db.session_context():
        uids = await ListingRepository().get_notified_uids()
    added = seen.warm(uids)
    logger.info("Seen-cache warmed: %d UIDs (%d added)", len(uids), added)


async def run_scrape_cycle(
    notifier: TelegramNotifier,
    registry: UserRegistry,
) -> int:
    active_users = registry.all_stores()
    if not active_users:
        return 0

    scrapers_with_tasks = [
        (s := cls(), asyncio.create_task(s.fetch_incremental(), name=s.slug))
        for cls in ALL_SCRAPERS
    ]

    total_notified = 0

    for scraper, task in scrapers_with_tasks:
        try:
            apartments = await task
            if not apartments:
                continue

            logger.info(
                "[%s] %d new listings for evaluation", scraper.slug, len(apartments)
            )

            async with db.session_context():
                notified = 0
                t0 = asyncio.get_event_loop().time()

                for chat_id, store in active_users:
                    if store.is_paused:
                        continue

                    for apt in apartments:
                        outcome: ProcessResult = await process_apartment(
                            apt, store.current_filter, chat_id, notifier
                        )
                        seen.mark_processed(apt.id)

                        if outcome.notified:
                            notified += 1
                            total_notified += 1
                            await asyncio.sleep(0.5)

                elapsed = asyncio.get_event_loop().time() - t0
                logger.info("[%s] done: notified=%d", scraper.slug, notified)

                scrape_logger.log_scrape_run_finished(
                    source_slug=scraper.slug,
                    source_name=scraper.name,
                    duration_seconds=elapsed,
                    listings_found=len(apartments),
                    listings_new=notified,
                )

        except Exception as exc:
            logger.error("[%s] fatal error: %s", scraper.slug, exc)
            continue

    return total_notified


async def scrape_loop(notifier: TelegramNotifier, registry: UserRegistry) -> None:
    cycle = 0
    while True:
        cycle += 1
        logger.info("── Cycle #%d at %s ──", cycle, datetime.now().strftime("%H:%M:%S"))
        t0 = asyncio.get_event_loop().time()
        try:
            new_count = await run_scrape_cycle(notifier, registry)
            logger.info(
                "── Cycle #%d done: %d new in %.1fs ──",
                cycle,
                new_count,
                asyncio.get_event_loop().time() - t0,
            )
        except Exception as exc:
            logger.exception("Cycle #%d error: %s", cycle, exc)

        await asyncio.sleep(settings.CHECK_INTERVAL_SECONDS)


async def main() -> None:
    # settings.setup_logging()
    setup_daily_logging()
    logger.info("=" * 60)
    logger.info(
        "Starting up... DB: %s:%s/%s | Interval: %ds",
        settings.DB_HOST,
        settings.DB_PORT,
        settings.DB_NAME,
        settings.CHECK_INTERVAL_SECONDS,
    )
    logger.info("=" * 60)

    await db.init()
    await warm_seen_cache()

    registry = UserRegistry()
    await registry.get_or_create(settings.TELEGRAM_CHAT_ID)

    bot = Bot(token=settings.TELEGRAM_BOT_TOKEN)
    dp = Dispatcher(storage=MemoryStorage())
    dp.include_router(router)

    notifier = TelegramNotifier(bot)

    await notifier.send_startup_message(
        int(settings.TELEGRAM_CHAT_ID), [cls.name for cls in ALL_SCRAPERS]
    )

    scrape_task = asyncio.create_task(scrape_loop(notifier, registry))

    try:
        await dp.start_polling(
            bot,
            allowed_updates=["message"],
            registry=registry,
            notifier=notifier,
        )
    finally:
        scrape_task.cancel()
        await bot.session.close()
        await db.close()
        logger.info("Stopped.")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        logger.info("Process interrupted.")
