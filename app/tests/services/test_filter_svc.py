import pytest
from app.db.services.filter_svc import FilterService
from app.core.apartment import ApartmentFilter
from app.core.enums import SocialStatus
from app.tests.conftest import make_filter


@pytest.fixture
def filter_svc(mocker):
    svc = FilterService()
    svc.repo = mocker.MagicMock()
    svc.repo.save = mocker.AsyncMock()
    svc.repo.load = mocker.AsyncMock(return_value=None)
    return svc


class TestBuildDefaultFilter:
    def test_returns_apartment_filter(self, filter_svc):
        assert isinstance(filter_svc.build_default_filter(), ApartmentFilter)

    def test_all_numeric_fields_are_none(self, filter_svc):
        f = filter_svc.build_default_filter()
        assert f.min_rooms is None
        assert f.max_rooms is None
        assert f.min_sqm is None
        assert f.max_sqm is None
        assert f.min_price is None
        assert f.max_price is None

    def test_status_is_any(self, filter_svc):
        assert filter_svc.build_default_filter().social_status == SocialStatus.ANY

    def test_is_not_complete(self, filter_svc):
        assert filter_svc.build_default_filter().is_complete() is False


class TestApplyRangeUpdate:

    @pytest.mark.asyncio
    async def test_sets_min_and_max_rooms(self, filter_svc):
        filt = make_filter()
        ok = await filter_svc.apply_range_update(
            filt, "chat1", "rooms", ["1", "3"], int
        )
        assert ok is True
        assert filt.min_rooms == 1
        assert filt.max_rooms == 3

    @pytest.mark.asyncio
    async def test_sets_min_and_max_price(self, filter_svc):
        filt = make_filter()
        ok = await filter_svc.apply_range_update(
            filt, "chat1", "price", ["500", "1200"], float
        )
        assert ok is True
        assert filt.min_price == 500.0
        assert filt.max_price == 1200.0

    @pytest.mark.asyncio
    async def test_sets_min_and_max_area(self, filter_svc):
        filt = make_filter()
        ok = await filter_svc.apply_range_update(
            filt, "chat1", "area", ["30", "80"], float
        )
        assert ok is True
        assert filt.min_sqm == 30.0
        assert filt.max_sqm == 80.0

    @pytest.mark.asyncio
    async def test_single_arg_sets_min_clears_max(self, filter_svc):
        filt = make_filter()
        ok = await filter_svc.apply_range_update(filt, "chat1", "rooms", ["2"], int)
        assert ok is True
        assert filt.min_rooms == 2
        assert filt.max_rooms is None

    @pytest.mark.asyncio
    async def test_empty_args_returns_false(self, filter_svc):
        ok = await filter_svc.apply_range_update(
            make_filter(), "chat1", "rooms", [], int
        )
        assert ok is False

    @pytest.mark.asyncio
    async def test_unknown_field_returns_false(self, filter_svc):
        ok = await filter_svc.apply_range_update(
            make_filter(), "chat1", "unknown", ["1", "3"], int
        )
        assert ok is False

    @pytest.mark.asyncio
    async def test_non_numeric_args_returns_false(self, filter_svc):
        ok = await filter_svc.apply_range_update(
            make_filter(), "chat1", "rooms", ["abc", "xyz"], int
        )
        assert ok is False

    @pytest.mark.asyncio
    async def test_saves_filter_on_success(self, filter_svc):
        await filter_svc.apply_range_update(
            make_filter(), "chat1", "rooms", ["1", "3"], int
        )
        filter_svc.repo.save.assert_called_once()

    @pytest.mark.asyncio
    async def test_does_not_save_on_failure(self, filter_svc):
        await filter_svc.apply_range_update(make_filter(), "chat1", "rooms", [], int)
        filter_svc.repo.save.assert_not_called()


class TestApplyStatusUpdate:

    @pytest.mark.asyncio
    async def test_sets_wbs_status(self, filter_svc):
        filt = make_filter()
        ok = await filter_svc.apply_status_update(filt, "chat1", SocialStatus.WBS)
        assert ok is True
        assert filt.social_status == SocialStatus.WBS

    @pytest.mark.asyncio
    async def test_sets_market_status(self, filter_svc):
        filt = make_filter()
        ok = await filter_svc.apply_status_update(filt, "chat1", SocialStatus.MARKET)
        assert ok is True
        assert filt.social_status == SocialStatus.MARKET

    @pytest.mark.asyncio
    async def test_sets_any_status(self, filter_svc):
        filt = make_filter(social_status=SocialStatus.WBS)
        ok = await filter_svc.apply_status_update(filt, "chat1", SocialStatus.ANY)
        assert ok is True
        assert filt.social_status == SocialStatus.ANY

    @pytest.mark.asyncio
    async def test_saves_filter_on_update(self, filter_svc):
        await filter_svc.apply_status_update(make_filter(), "chat1", SocialStatus.WBS)
        filter_svc.repo.save.assert_called_once()
