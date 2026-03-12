# ============================================================
# main.py — Async scheduler + entry point
#
# Dependency flow:
#   main.py
#     └── services/
#           ├── ListingService   (upsert + notify)
#           ├── ScrapeRunService (health tracking)
#           ├── FilterService    (load saved filter)
#           └── CacheService     (Redis warm-up + cleanup)
#
# main.py never imports from repositories/ or schemas/ directly.
# ============================================================

import asyncio
import logging
import signal
from datetime import datetime

import aiohttp

from bot_commands import CommandHandler, FilterStore
from cache import seen_store
from config import settings
from db.database import db
from telegram.notifier import TelegramNotifier
from scrapers import ALL_SCRAPERS
from db.services import (
    CacheService,
    FilterService,
    ListingService,
    ProcessResult,
    ScrapeRunService,
)

logger = logging.getLogger("main")

CLEANUP_INTERVAL_SECONDS = 60 * 60 * 24   # run Redis cleanup once per day


async def run_check(
    http:          aiohttp.ClientSession,
    notifier:      TelegramNotifier,
    filter_store:  FilterStore,
    listing_svc:   ListingService,
    run_svc:       ScrapeRunService,
) -> int:
    if filter_store.paused:
        logger.info("Notifications paused — skipping check.")
        return 0

    current_filter = filter_store.filter
    scrapers = [cls(http) for cls in ALL_SCRAPERS]
    tasks    = [asyncio.create_task(s.fetch_all(), name=s.slug) for s in scrapers]
    results  = await asyncio.gather(*tasks, return_exceptions=True)

    total_notified = 0

    for scraper, result in zip(scrapers, results):
        if isinstance(result, Exception):
            logger.error("[%s] Scraper error: %s", scraper.slug, result)
            continue

        apartments = result
        logger.info("[%s] %d listings fetched", scraper.slug, len(apartments))

        async with db.session_context():
            run_id     = await run_svc.begin(scraper.slug)
            notified   = 0

            try:
                for apt in apartments:
                    outcome: ProcessResult = await listing_svc.process(
                        apt      = apt,
                        filt     = current_filter,
                        chat_id  = settings.TELEGRAM_CHAT_ID,
                        notifier = notifier,
                    )
                    if outcome.notified:
                        notified       += 1
                        total_notified += 1
                        await asyncio.sleep(0.5)   # stay under Telegram rate limit

                await run_svc.finish(run_id, found=len(apartments), new=notified)

            except Exception as exc:
                logger.exception("[%s] Processing error: %s", scraper.slug, exc)
                await run_svc.finish(run_id, found=len(apartments), new=notified, error=str(exc))
                raise

    return total_notified


async def cleanup_loop(cache_svc: CacheService) -> None:
    """Daily background task — removes stale entries from Redis."""
    while True:
        await asyncio.sleep(CLEANUP_INTERVAL_SECONDS)
        await cache_svc.run_cleanup()


async def main() -> None:
    settings.setup_logging()
    logger.info("=" * 60)
    logger.info("Apartment notifier starting up ...")
    logger.info(
        "DB: %s:%s/%s | Redis: %s:%s/%s | Interval: %ds",
        settings.DB_HOST,    settings.DB_PORT,    settings.DB_NAME,
        settings.REDIS_HOST, settings.REDIS_PORT, settings.REDIS_DB,
        settings.CHECK_INTERVAL_SECONDS,
    )
    logger.info("=" * 60)

    # ── Instantiate services ──────────────────────────────────
    filter_svc   = FilterService()
    listing_svc  = ListingService()
    run_svc      = ScrapeRunService()
    cache_svc    = CacheService()

    # ── Connect infrastructure ────────────────────────────────
    await db.init()
    await seen_store.connect()

    # ── Warm Redis from DB ────────────────────────────────────
    await cache_svc.warm_from_db()

    # ── Load saved filter ─────────────────────────────────────
    saved = await filter_svc.load(settings.TELEGRAM_CHAT_ID)
    if saved:
        initial_filter, initial_paused = saved
    else:
        initial_filter = filter_svc.build_default()
        initial_paused = False

    filter_store = FilterStore(
        initial_filter = initial_filter,
        initial_paused = initial_paused,
    )

    # ── Graceful shutdown ─────────────────────────────────────
    stop_event = asyncio.Event()

    def _shutdown(sig, _frame) -> None:
        logger.info("Signal %s received — shutting down ...", sig.name)
        stop_event.set()

    for sig in (signal.SIGINT, signal.SIGTERM):
        signal.signal(sig, _shutdown)

    # ── Main loop ─────────────────────────────────────────────
    connector = aiohttp.TCPConnector(limit=20, ssl=False)
    async with aiohttp.ClientSession(connector=connector) as http:
        notifier    = TelegramNotifier(http)
        cmd_handler = CommandHandler(http, filter_store)

        bg_tasks = [
            asyncio.create_task(cmd_handler.poll_loop(),        name="cmd_poll"),
            asyncio.create_task(cleanup_loop(cache_svc),        name="redis_cleanup"),
        ]

        await notifier.send_startup_message([cls.name for cls in ALL_SCRAPERS])  # type: ignore

        iteration = 0
        while not stop_event.is_set():
            iteration += 1
            logger.info("── Check #%d at %s ──", iteration, datetime.now().strftime("%H:%M:%S"))
            start = asyncio.get_event_loop().time()
            try:
                new     = await run_check(http, notifier, filter_store, listing_svc, run_svc)
                elapsed = asyncio.get_event_loop().time() - start
                logger.info("── #%d done: %d new listings in %.1fs ──", iteration, new, elapsed)
            except Exception as exc:
                logger.exception("Error during check #%d: %s", iteration, exc)

            try:
                await asyncio.wait_for(
                    stop_event.wait(), timeout=settings.CHECK_INTERVAL_SECONDS
                )
            except asyncio.TimeoutError:
                pass

        for task in bg_tasks:
            task.cancel()

    await seen_store.close()
    await db.close()
    logger.info("Bot stopped. Goodbye.")


if __name__ == "__main__":
    asyncio.run(main())