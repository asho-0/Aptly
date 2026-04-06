import logging
import time

import asyncio
from collections.abc import AsyncIterator


from app.db.session import db
from app.core.config import settings
from app.core.apartment import Apartment
from app.parsers.site import InBerlinWohnenScraper
from app.db.services import ListingService
from app.telegram.handlers import UserRegistry
from app.telegram.notifier import TelegramNotifier
from app.telegram.handlers.handlers import FilterStore

ActiveUsers = list[tuple[str, FilterStore]]

logger = logging.getLogger(__name__)


class ScraperEngine:
    def __init__(self, notifier: TelegramNotifier, registry: UserRegistry):
        self.notifier = notifier
        self.registry = registry
        self._known_site_ids: set[str] = set()

    async def _load_user_histories(
        self, svc: ListingService, chat_ids: list[str]
    ) -> dict[str, set[str]]:
        if getattr(type(svc), "preload_user_histories", None) is not None:
            return await svc.preload_user_histories(chat_ids)

        histories: dict[str, set[str]] = {}
        for chat_id in chat_ids:
            histories[chat_id] = await svc.get_user_history(chat_id)
        return histories

    async def _iter_scraper_apartments(self, scraper: InBerlinWohnenScraper) -> AsyncIterator[Apartment]:
        if getattr(type(scraper), "iter_listings", None) is not None:
            async for apartment in scraper.iter_listings():
                yield apartment
            return

        for apartment in await scraper.fetch_all():
            yield apartment

    async def _process_apartment_for_users(
        self,
        apartment: Apartment,
        active_users: ActiveUsers,
        user_histories: dict[str, set[str]],
        svc: ListingService,
    ) -> int:
        total_notified = 0

        for chat_id, store in active_users:
            history = user_histories[chat_id]
            if store.is_paused or apartment.id in history:
                continue
            if not apartment.matches(
                store.current_filter,
                show_special_listings=store.show_special_listings,
            ):
                continue

            outcome = await svc.process_apartment(
                apartment,
                store.current_filter,
                chat_id,
                self.notifier,
                lang=store.lang,
                with_actions=False,
                show_special_listings=store.show_special_listings,
            )
            if not outcome.notified:
                continue

            total_notified += 1
            await asyncio.sleep(settings.NOTIFICATION_DELAY)

        return total_notified

    async def _run_scraper(
        self,
        scraper: InBerlinWohnenScraper,
        active_users: ActiveUsers,
        user_histories: dict[str, set[str]],
        previous_site_ids: set[str],
        current_site_ids: set[str],
        svc: ListingService,
    ) -> int:
        processed_count = 0
        total_notified = 0

        try:
            async for apartment in self._iter_scraper_apartments(scraper):
                processed_count += 1
                current_site_ids.add(apartment.id)

                if apartment.id in previous_site_ids:
                    continue

                total_notified += await self._process_apartment_for_users(
                    apartment,
                    active_users,
                    user_histories,
                    svc,
                )
        except Exception as exc:
            logger.error("[%s] fetch error: %s", scraper.slug, exc)
        finally:
            await scraper.close_session()

        logger.info(
            "[%s] cycle done: processed %d apartments",
            scraper.slug,
            processed_count,
        )
        return total_notified

    async def run_cycle(self) -> int:
        active_users: ActiveUsers = await self.registry.fetch_all_active()
        if not active_users:
            return 0

        svc = ListingService()
        chat_ids = [chat_id for chat_id, _ in active_users]
        async with db.session_context():
            user_histories = await self._load_user_histories(svc, chat_ids)

        scrapers = [InBerlinWohnenScraper()]
        previous_site_ids = set(self._known_site_ids)
        current_site_ids: set[str] = set()
        total_notified = 0

        async with db.session_context():
            for scraper in scrapers:
                total_notified += await self._run_scraper(
                    scraper,
                    active_users,
                    user_histories,
                    previous_site_ids,
                    current_site_ids,
                    svc,
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
