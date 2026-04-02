import pytest
from app.telegram.handlers.handlers import FilterStore, UserRegistry
from app.core.apartment import ApartmentFilter
from app.core.enums import SocialStatus
from tests.conftest import make_filter


@pytest.fixture
def store(mocker):
    filt = make_filter()
    s = FilterStore("123", filt, False, "en")
    s._filter_svc = mocker.MagicMock()
    s._filter_svc.save_filter = mocker.AsyncMock()
    s._filter_svc.build_default_filter.return_value = ApartmentFilter(
        min_rooms=None,
        max_rooms=None,
        min_sqm=None,
        max_sqm=None,
        min_price=None,
        max_price=None,
        social_status=SocialStatus.ANY,
    )
    return s


class TestFilterStore:
    def test_initial_lang_is_set(self):
        filt = make_filter()
        s = FilterStore("123", filt, False, "ru")
        assert s.lang == "ru"

    def test_default_lang_is_en(self):
        filt = make_filter()
        s = FilterStore("123", filt, False)
        assert s.lang == "en"

    def test_initial_paused_true(self):
        filt = make_filter()
        s = FilterStore("123", filt, True)
        assert s.is_paused is True

    def test_initial_paused_false(self):
        assert FilterStore("123", make_filter(), False).is_paused is False

    def test_initial_filter_type(self, store):
        assert isinstance(store.current_filter, ApartmentFilter)

    def test_set_paused_true(self, store, mocker):
        mocker.patch("asyncio.create_task")
        store.set_paused(True)
        assert store.is_paused is True

    def test_set_paused_false(self, mocker):
        filt = make_filter()
        s = FilterStore("123", filt, True, "en")
        s._filter_svc = mocker.MagicMock()
        s._filter_svc.save_filter = mocker.AsyncMock()
        mocker.patch("asyncio.create_task")
        s.set_paused(False)
        assert s.is_paused is False

    def test_set_paused_schedules_persist(self, store, mocker):
        mock_task = mocker.patch("asyncio.create_task")
        store.set_paused(True)
        mock_task.assert_called_once()

    def test_set_lang_updates_value(self, store, mocker):
        mocker.patch("asyncio.create_task")
        store.set_lang("ru")
        assert store.lang == "ru"

    def test_set_lang_schedules_persist(self, store, mocker):
        mock_task = mocker.patch("asyncio.create_task")
        store.set_lang("ru")
        mock_task.assert_called_once()

    def test_reset_to_defaults_clears_filter(self, store, mocker):
        store._filter.min_rooms = 3
        mocker.patch("asyncio.create_task")
        store.reset_to_defaults()
        assert store.current_filter.min_rooms is None

    def test_reset_to_defaults_schedules_persist(self, store, mocker):
        mock_task = mocker.patch("asyncio.create_task")
        store.reset_to_defaults()
        mock_task.assert_called_once()

    def test_reset_sets_status_to_any(self, store, mocker):
        store._filter.social_status = SocialStatus.WBS
        mocker.patch("asyncio.create_task")
        store.reset_to_defaults()
        assert store.current_filter.social_status == SocialStatus.ANY


def make_mock_user(mocker, lang="en", paused=False):
    mock_filter = mocker.MagicMock()
    mock_filter.paused = paused
    mock_filter.lang = lang
    mock_filter.social_status = SocialStatus.ANY.value
    mock_user = mocker.MagicMock()
    mock_user.filters = mock_filter
    return mock_user


def patch_registry_deps(mocker, mock_user):
    mock_svc = mocker.MagicMock()
    mock_svc.get_or_register_user = mocker.AsyncMock(return_value=mock_user)
    mock_svc.convert_to_domain.return_value = make_filter()

    mock_db = mocker.patch("app.telegram.handlers.handlers.db")
    mock_db.session_context.return_value.__aenter__ = mocker.AsyncMock(
        return_value=None
    )
    mock_db.session_context.return_value.__aexit__ = mocker.AsyncMock(
        return_value=False
    )

    mocker.patch("app.telegram.handlers.handlers.UserService", return_value=mock_svc)
    return mock_svc


class TestUserRegistry:
    @pytest.mark.asyncio
    async def test_get_or_create_returns_filter_store(self, mocker):
        user = make_mock_user(mocker)
        patch_registry_deps(mocker, user)
        store = await UserRegistry().get_or_create("123")
        assert isinstance(store, FilterStore)

    @pytest.mark.asyncio
    async def test_get_or_create_caches_store(self, mocker):
        user = make_mock_user(mocker)
        svc = patch_registry_deps(mocker, user)
        registry = UserRegistry()
        s1 = await registry.get_or_create("123")
        s2 = await registry.get_or_create("123")
        assert s1 is s2
        svc.get_or_register_user.assert_called_once()

    @pytest.mark.asyncio
    async def test_different_users_get_different_stores(self, mocker):
        user = make_mock_user(mocker)
        patch_registry_deps(mocker, user)
        registry = UserRegistry()
        s1 = await registry.get_or_create("111")
        s2 = await registry.get_or_create("222")
        assert s1 is not s2

    @pytest.mark.asyncio
    async def test_lang_loaded_from_db(self, mocker):
        user = make_mock_user(mocker, lang="ru")
        patch_registry_deps(mocker, user)
        store = await UserRegistry().get_or_create("123")
        assert store.lang == "ru"

    @pytest.mark.asyncio
    async def test_none_lang_defaults_to_en(self, mocker):
        user = make_mock_user(mocker, lang=None)
        patch_registry_deps(mocker, user)
        store = await UserRegistry().get_or_create("123")
        assert store.lang == "en"

    @pytest.mark.asyncio
    async def test_paused_state_loaded_from_db(self, mocker):
        user = make_mock_user(mocker, paused=True)
        patch_registry_deps(mocker, user)
        store = await UserRegistry().get_or_create("123")
        assert store.is_paused is True
