import pytest
from app.db.services.listing_svc import ListingService
from tests.conftest import make_filter, make_apartment


@pytest.fixture
def listing_svc(mocker):
    svc = ListingService()
    svc.repo = mocker.MagicMock()
    svc.repo.exists = mocker.AsyncMock(return_value=False)
    svc.repo.add_log = mocker.AsyncMock()
    svc.repo.upsert = mocker.AsyncMock(
        return_value=mocker.MagicMock(listing_db_id=1, is_new=True)
    )
    svc.repo.mark_notified = mocker.AsyncMock()
    svc.repo.get_user_notified_uids = mocker.AsyncMock(return_value=set())
    svc.repo.delete_user_notification_history = mocker.AsyncMock()
    return svc


@pytest.fixture
def notifier(mocker):
    n = mocker.AsyncMock()
    n.send_apartment = mocker.AsyncMock(return_value=True)
    return n


class TestProcessApartment:

    @pytest.mark.asyncio
    async def test_skips_if_already_notified(self, listing_svc, notifier):
        listing_svc.repo.exists.return_value = True
        result = await listing_svc.process_apartment(
            make_apartment(), make_filter(), "123", notifier
        )
        assert result.notified is False
        notifier.send_apartment.assert_not_called()

    @pytest.mark.asyncio
    async def test_skips_if_filter_not_matched(self, listing_svc, notifier):
        result = await listing_svc.process_apartment(
            make_apartment(price=9999.0), make_filter(max_price=1000), "123", notifier
        )
        assert result.passed_filter is False
        assert result.notified is False

    @pytest.mark.asyncio
    async def test_notifies_on_match(self, listing_svc, notifier):
        result = await listing_svc.process_apartment(
            make_apartment(), make_filter(), "123", notifier
        )
        assert result.notified is True
        notifier.send_apartment.assert_called_once()

    @pytest.mark.asyncio
    async def test_marks_as_seen_after_notification(self, listing_svc, notifier):
        apt = make_apartment()
        await listing_svc.process_apartment(apt, make_filter(), "123", notifier)
        listing_svc.repo.add_log.assert_called_once_with(apt.id, "123")

    @pytest.mark.asyncio
    async def test_passes_lang_to_notifier(self, listing_svc, notifier):
        await listing_svc.process_apartment(
            make_apartment(), make_filter(), "123", notifier, lang="ru"
        )
        _, kwargs = notifier.send_apartment.call_args
        assert kwargs.get("lang") == "ru"

    @pytest.mark.asyncio
    async def test_result_uid_matches_apartment(self, listing_svc, notifier):
        apt = make_apartment(id="degewo:999")
        result = await listing_svc.process_apartment(
            apt, make_filter(), "123", notifier
        )
        assert result.uid == "degewo:999"

    @pytest.mark.asyncio
    async def test_upserts_before_notification(self, listing_svc, notifier):
        await listing_svc.process_apartment(
            make_apartment(), make_filter(), "123", notifier
        )
        listing_svc.repo.upsert.assert_called_once()

    @pytest.mark.asyncio
    async def test_result_is_new_in_db_reflects_upsert(self, listing_svc, notifier):
        listing_svc.repo.upsert.return_value = mocker_result = (
            listing_svc.repo.upsert.return_value
        )
        result = await listing_svc.process_apartment(
            make_apartment(), make_filter(), "123", notifier
        )
        assert result.is_new_in_db is True


class TestPreviewApartment:

    @pytest.mark.asyncio
    async def test_returns_false_if_not_matching(self, listing_svc, notifier):
        result = await listing_svc.preview_apartment(
            make_apartment(price=9999.0), make_filter(max_price=1000), notifier, 123
        )
        assert result is False

    @pytest.mark.asyncio
    async def test_returns_false_if_already_notified(self, listing_svc, notifier):
        listing_svc.repo.exists.return_value = True
        result = await listing_svc.preview_apartment(
            make_apartment(), make_filter(), notifier, 123
        )
        assert result is False

    @pytest.mark.asyncio
    async def test_returns_true_on_successful_send(self, listing_svc, notifier):
        result = await listing_svc.preview_apartment(
            make_apartment(), make_filter(), notifier, 123
        )
        assert result is True
        notifier.send_apartment.assert_called_once()

    @pytest.mark.asyncio
    async def test_upserts_before_send(self, listing_svc, notifier):
        await listing_svc.preview_apartment(
            make_apartment(), make_filter(), notifier, 123
        )
        listing_svc.repo.upsert.assert_called_once()

    @pytest.mark.asyncio
    async def test_marks_as_seen_on_success(self, listing_svc, notifier):
        apt = make_apartment()
        await listing_svc.preview_apartment(apt, make_filter(), notifier, 123)
        listing_svc.repo.add_log.assert_called_once_with(apt.id, "123")

    @pytest.mark.asyncio
    async def test_passes_lang_to_notifier(self, listing_svc, notifier):
        await listing_svc.preview_apartment(
            make_apartment(), make_filter(), notifier, 123, lang="ru"
        )
        _, kwargs = notifier.send_apartment.call_args
        assert kwargs.get("lang") == "ru"

    @pytest.mark.asyncio
    async def test_returns_false_when_send_fails(self, listing_svc, notifier):
        notifier.send_apartment.return_value = False
        result = await listing_svc.preview_apartment(
            make_apartment(), make_filter(), notifier, 123
        )
        assert result is False


class TestGetUserHistory:

    @pytest.mark.asyncio
    async def test_returns_set_from_repo(self, listing_svc):
        listing_svc.repo.get_user_notified_uids.return_value = {"degewo:1", "wbm:2"}
        result = await listing_svc.get_user_history("123")
        assert result == {"degewo:1", "wbm:2"}

    @pytest.mark.asyncio
    async def test_returns_empty_set_when_no_history(self, listing_svc):
        listing_svc.repo.get_user_notified_uids.return_value = set()
        result = await listing_svc.get_user_history("123")
        assert result == set()


class TestResetUserHistory:

    @pytest.mark.asyncio
    async def test_calls_repo_delete(self, listing_svc):
        await listing_svc.reset_user_history("123")
        listing_svc.repo.delete_user_notification_history.assert_called_once_with("123")
