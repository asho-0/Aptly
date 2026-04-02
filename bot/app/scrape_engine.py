import logging
import time

import asyncio


from app.db.session import db
from app.core.config import settings
from app.parsers.site import ALL_SCRAPERS
from app.db.services import ListingService
from app.telegram.handlers import UserRegistry
from app.telegram.notifier import TelegramNotifier

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
            svc = ListingService()
            for chat_id, _ in active_users:
                user_histories[chat_id] = await svc.get_user_history(chat_id)

        scrapers = [cls() for cls in ALL_SCRAPERS]
        previous_site_ids = set(self._known_site_ids)
        current_site_ids: set[str] = set()
        total_notified = 0

        async with db.session_context():
            svc = ListingService()
            for scraper in scrapers:
                processed_count = 0
                try:
                    iterator = (
                        scraper.iter_listings()
                        if getattr(type(scraper), "iter_listings", None) is not None
                        else None
                    )
                    if iterator is None:
                        apartments = await scraper.fetch_all()

                        async def _fallback_iterator():
                            for apartment in apartments:
                                yield apartment

                        iterator = _fallback_iterator()

                    async for apt in iterator:
                        processed_count += 1
                        current_site_ids.add(apt.id)

                        if apt.id in previous_site_ids:
                            continue

                        for chat_id, store in active_users:
                            if store.is_paused or apt.id in user_histories[chat_id]:
                                continue
                            if not apt.matches(
                                store.current_filter,
                                show_special_listings=store.show_special_listings,
                            ):
                                continue

                            outcome = await svc.process_apartment(
                                apt,
                                store.current_filter,
                                chat_id,
                                self.notifier,
                                lang=store.lang,
                                with_actions=False,
                                show_special_listings=store.show_special_listings,
                            )

                            if outcome.notified:
                                user_histories[chat_id].add(apt.id)
                                total_notified += 1
                                await asyncio.sleep(settings.NOTIFICATION_DELAY)
                except Exception as exc:
                    logger.error("[%s] fetch error: %s", scraper.slug, exc)
                finally:
                    await scraper.close_session()

                logger.info(
                    "[%s] cycle done: processed %d apartments",
                    scraper.slug,
                    processed_count,
                )

        self._known_site_ids = current_site_ids
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
