import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from tests.conftest import make_filter, make_apartment


def make_store(paused=False, lang="en", filter_kwargs=None):
    store = MagicMock()
    store.is_paused = paused
    store.lang = lang
    store.current_filter = make_filter(**(filter_kwargs or {}))
    return store


@pytest.fixture
def engine():
    from app.scrape_engine import ScraperEngine

    notifier = AsyncMock()
    registry = AsyncMock()
    return ScraperEngine(notifier, registry)


class TestRunCycleNoUsers:
    @pytest.mark.asyncio
    async def test_returns_zero_when_no_active_users(self, engine):
        engine.registry.fetch_all_active.return_value = []
        result = await engine.run_cycle()
        assert result == 0


class TestRunCycleKnownIds:
    @pytest.mark.asyncio
    async def test_skips_when_no_new_listings(self, engine):
        engine.registry.fetch_all_active.return_value = [("123", make_store())]
        engine._known_site_ids = {"degewo:1", "degewo:2"}

        mock_scraper = AsyncMock()
        mock_scraper.fetch_all.return_value = [
            make_apartment(id="degewo:1"),
            make_apartment(id="degewo:2"),
        ]
        mock_scraper.slug = "degewo"
        mock_scraper.close_session = AsyncMock()

        mock_svc = AsyncMock()

        with patch("app.scrape_engine.ALL_SCRAPERS", [lambda: mock_scraper]):
            with patch("app.scrape_engine.db") as mock_db:
                mock_db.session_context.return_value.__aenter__ = AsyncMock(
                    return_value=None
                )
                mock_db.session_context.return_value.__aexit__ = AsyncMock(
                    return_value=False
                )
                with patch("app.scrape_engine.ListingService", return_value=mock_svc):
                    result = await engine.run_cycle()

        assert result == 0
        mock_svc.process_apartment.assert_not_called()

    @pytest.mark.asyncio
    async def test_updates_known_ids_after_cycle(self, engine):
        store = make_store()
        engine.registry.fetch_all_active.return_value = [("123", store)]  # не пустой
        engine._known_site_ids = set()

        mock_scraper = AsyncMock()
        mock_scraper.fetch_all.return_value = [
            make_apartment(id="degewo:1"),
            make_apartment(id="degewo:2"),
        ]
        mock_scraper.slug = "degewo"
        mock_scraper.close_session = AsyncMock()

        mock_svc = AsyncMock()
        mock_svc.get_user_history.return_value = set()
        mock_svc.process_apartment.return_value = MagicMock(notified=False)

        with patch("app.scrape_engine.ALL_SCRAPERS", [lambda: mock_scraper]):
            with patch("app.scrape_engine.db") as mock_db:
                mock_db.session_context.return_value.__aenter__ = AsyncMock(
                    return_value=None
                )
                mock_db.session_context.return_value.__aexit__ = AsyncMock(
                    return_value=False
                )
                with patch("app.scrape_engine.ListingService", return_value=mock_svc):
                    await engine.run_cycle()

        assert "degewo:1" in engine._known_site_ids
        assert "degewo:2" in engine._known_site_ids


class TestRunCycleNotifications:
    @pytest.mark.asyncio
    async def test_skips_paused_users(self, engine):
        store = make_store(paused=True)
        engine.registry.fetch_all_active.return_value = [("123", store)]

        apt = make_apartment(id="degewo:99")
        mock_scraper = AsyncMock()
        mock_scraper.fetch_all.return_value = [apt]
        mock_scraper.slug = "degewo"
        mock_scraper.close_session = AsyncMock()

        mock_svc = AsyncMock()
        mock_svc.get_user_history.return_value = set()

        with patch("app.scrape_engine.ALL_SCRAPERS", [lambda: mock_scraper]):
            with patch("app.scrape_engine.db") as mock_db:
                mock_db.session_context.return_value.__aenter__ = AsyncMock(
                    return_value=None
                )
                mock_db.session_context.return_value.__aexit__ = AsyncMock(
                    return_value=False
                )
                with patch("app.scrape_engine.ListingService", return_value=mock_svc):
                    result = await engine.run_cycle()

        assert result == 0
        mock_svc.process_apartment.assert_not_called()

    @pytest.mark.asyncio
    async def test_skips_already_notified_apartments(self, engine):
        store = make_store()
        engine.registry.fetch_all_active.return_value = [("123", store)]

        apt = make_apartment(id="degewo:99")
        mock_scraper = AsyncMock()
        mock_scraper.fetch_all.return_value = [apt]
        mock_scraper.slug = "degewo"
        mock_scraper.close_session = AsyncMock()

        mock_svc = AsyncMock()
        mock_svc.get_user_history.return_value = {"degewo:99"}  # уже уведомлён

        with patch("app.scrape_engine.ALL_SCRAPERS", [lambda: mock_scraper]):
            with patch("app.scrape_engine.db") as mock_db:
                mock_db.session_context.return_value.__aenter__ = AsyncMock(
                    return_value=None
                )
                mock_db.session_context.return_value.__aexit__ = AsyncMock(
                    return_value=False
                )
                with patch("app.scrape_engine.ListingService", return_value=mock_svc):
                    result = await engine.run_cycle()

        assert result == 0
        mock_svc.process_apartment.assert_not_called()

    @pytest.mark.asyncio
    async def test_skips_apartments_not_matching_filter(self, engine):
        store = make_store(filter_kwargs={"min_price": 500, "max_price": 700})
        engine.registry.fetch_all_active.return_value = [("123", store)]

        apt = make_apartment(id="degewo:99", price=1500.0)  # не подходит
        mock_scraper = AsyncMock()
        mock_scraper.fetch_all.return_value = [apt]
        mock_scraper.slug = "degewo"
        mock_scraper.close_session = AsyncMock()

        mock_svc = AsyncMock()
        mock_svc.get_user_history.return_value = set()

        with patch("app.scrape_engine.ALL_SCRAPERS", [lambda: mock_scraper]):
            with patch("app.scrape_engine.db") as mock_db:
                mock_db.session_context.return_value.__aenter__ = AsyncMock(
                    return_value=None
                )
                mock_db.session_context.return_value.__aexit__ = AsyncMock(
                    return_value=False
                )
                with patch("app.scrape_engine.ListingService", return_value=mock_svc):
                    result = await engine.run_cycle()

        assert result == 0
        mock_svc.process_apartment.assert_not_called()

    @pytest.mark.asyncio
    async def test_notifies_matching_new_apartment(self, engine):
        store = make_store()
        engine.registry.fetch_all_active.return_value = [("123", store)]

        apt = make_apartment(id="degewo:99")
        mock_scraper = AsyncMock()
        mock_scraper.fetch_all.return_value = [apt]
        mock_scraper.slug = "degewo"
        mock_scraper.close_session = AsyncMock()

        outcome = MagicMock()
        outcome.notified = True

        mock_svc = AsyncMock()
        mock_svc.get_user_history.return_value = set()
        mock_svc.process_apartment.return_value = outcome

        with patch("app.scrape_engine.ALL_SCRAPERS", [lambda: mock_scraper]):
            with patch("app.scrape_engine.db") as mock_db:
                mock_db.session_context.return_value.__aenter__ = AsyncMock(
                    return_value=None
                )
                mock_db.session_context.return_value.__aexit__ = AsyncMock(
                    return_value=False
                )
                with patch("app.scrape_engine.ListingService", return_value=mock_svc):
                    with patch("asyncio.sleep", new_callable=AsyncMock):
                        result = await engine.run_cycle()

        assert result == 1
        mock_svc.process_apartment.assert_called_once()

    @pytest.mark.asyncio
    async def test_passes_lang_to_process_apartment(self, engine):
        store = make_store(lang="ru")
        engine.registry.fetch_all_active.return_value = [("123", store)]

        apt = make_apartment(id="degewo:99")
        mock_scraper = AsyncMock()
        mock_scraper.fetch_all.return_value = [apt]
        mock_scraper.slug = "degewo"
        mock_scraper.close_session = AsyncMock()

        outcome = MagicMock()
        outcome.notified = True

        mock_svc = AsyncMock()
        mock_svc.get_user_history.return_value = set()
        mock_svc.process_apartment.return_value = outcome

        with patch("app.scrape_engine.ALL_SCRAPERS", [lambda: mock_scraper]):
            with patch("app.scrape_engine.db") as mock_db:
                mock_db.session_context.return_value.__aenter__ = AsyncMock(
                    return_value=None
                )
                mock_db.session_context.return_value.__aexit__ = AsyncMock(
                    return_value=False
                )
                with patch("app.scrape_engine.ListingService", return_value=mock_svc):
                    with patch("asyncio.sleep", new_callable=AsyncMock):
                        await engine.run_cycle()

        _, kwargs = mock_svc.process_apartment.call_args
        assert kwargs.get("lang") == "ru"

    @pytest.mark.asyncio
    async def test_handles_scraper_exception_gracefully(self, engine):
        store = make_store()
        engine.registry.fetch_all_active.return_value = [("123", store)]

        mock_scraper = AsyncMock()
        mock_scraper.fetch_all.side_effect = Exception("network error")
        mock_scraper.slug = "degewo"
        mock_scraper.close_session = AsyncMock()

        mock_svc = AsyncMock()
        mock_svc.get_user_history.return_value = set()

        with patch("app.scrape_engine.ALL_SCRAPERS", [lambda: mock_scraper]):
            with patch("app.scrape_engine.db") as mock_db:
                mock_db.session_context.return_value.__aenter__ = AsyncMock(
                    return_value=None
                )
                mock_db.session_context.return_value.__aexit__ = AsyncMock(
                    return_value=False
                )
                with patch("app.scrape_engine.ListingService", return_value=mock_svc):
                    result = await engine.run_cycle()

        assert result == 0
