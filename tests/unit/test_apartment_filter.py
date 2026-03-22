import pytest
from app.core.apartment import ApartmentFilter
from app.core.enums import SocialStatus
from tests.conftest import make_filter


class TestApartmentFilterIsComplete:
    def test_complete_filter_returns_true(self):
        f = make_filter()
        assert f.is_complete() is True

    def test_missing_min_rooms_returns_false(self):
        f = make_filter(min_rooms=None)
        assert f.is_complete() is False

    def test_missing_max_rooms_returns_false(self):
        f = make_filter(max_rooms=None)
        assert f.is_complete() is False

    def test_missing_min_sqm_returns_false(self):
        f = make_filter(min_sqm=None)
        assert f.is_complete() is False

    def test_missing_max_sqm_returns_false(self):
        f = make_filter(max_sqm=None)
        assert f.is_complete() is False

    def test_missing_min_price_returns_false(self):
        f = make_filter(min_price=None)
        assert f.is_complete() is False

    def test_missing_max_price_returns_false(self):
        f = make_filter(max_price=None)
        assert f.is_complete() is False

    def test_all_none_returns_false(self):
        f = ApartmentFilter(
            min_rooms=None,
            max_rooms=None,
            min_sqm=None,
            max_sqm=None,
            min_price=None,
            max_price=None,
            social_status=SocialStatus.ANY,
        )
        assert f.is_complete() is False


class TestApartmentFilterSummary:
    def test_summary_en_contains_header(self):
        f = make_filter()
        summary = f.summary("en")
        assert "Active filters" in summary

    def test_summary_ru_contains_header(self):
        f = make_filter()
        summary = f.summary("ru")
        assert "фильтры" in summary

    def test_summary_shows_none_placeholder_for_missing_values(self):
        f = make_filter(min_rooms=None, max_rooms=None)
        summary = f.summary("en")
        assert "–-–" in summary

    def test_summary_shows_range_values(self):
        f = make_filter(min_price=500, max_price=1200)
        summary = f.summary("en")
        assert "500" in summary
        assert "1200" in summary

    def test_summary_shows_status(self):
        f = make_filter(social_status=SocialStatus.WBS)
        summary = f.summary("en")
        assert "wbs" in summary.lower()

    def test_summary_fallback_to_en_for_unknown_lang(self):
        f = make_filter()
        summary = f.summary("de")
        assert "Active filters" in summary
