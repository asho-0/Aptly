import pytest
from app.core.enums import SocialStatus
from app.tests.conftest import make_filter, make_apartment


class TestApartmentMatches:

    # ── incomplete filter ─────────────────────────────────────

    def test_incomplete_filter_always_returns_false(self, incomplete_filter):
        apt = make_apartment()
        assert apt.matches(incomplete_filter) is False

    # ── price ─────────────────────────────────────────────────

    def test_price_within_range_passes(self):
        apt = make_apartment(price=600)
        assert apt.matches(make_filter(min_price=500, max_price=700)) is True

    def test_price_at_min_boundary_passes(self):
        apt = make_apartment(price=500)
        assert apt.matches(make_filter(min_price=500, max_price=700)) is True

    def test_price_at_max_boundary_passes(self):
        apt = make_apartment(price=700)
        assert apt.matches(make_filter(min_price=500, max_price=700)) is True

    def test_price_below_min_fails(self):
        apt = make_apartment(price=400)
        assert apt.matches(make_filter(min_price=500, max_price=700)) is False

    def test_price_above_max_fails(self):
        apt = make_apartment(price=800)
        assert apt.matches(make_filter(min_price=500, max_price=700)) is False

    def test_none_price_always_fails(self):
        apt = make_apartment(price=None)
        assert apt.matches(make_filter()) is False

    # ── rooms ─────────────────────────────────────────────────

    def test_rooms_within_range_passes(self):
        apt = make_apartment(rooms=2)
        assert apt.matches(make_filter(min_rooms=1, max_rooms=3)) is True

    def test_rooms_below_min_fails(self):
        apt = make_apartment(rooms=1)
        assert apt.matches(make_filter(min_rooms=2, max_rooms=4)) is False

    def test_rooms_above_max_fails(self):
        apt = make_apartment(rooms=5)
        assert apt.matches(make_filter(min_rooms=1, max_rooms=3)) is False

    def test_none_rooms_skips_rooms_check(self):
        apt = make_apartment(rooms=None)
        assert apt.matches(make_filter()) is True

    # ── area ──────────────────────────────────────────────────

    def test_sqm_within_range_passes(self):
        apt = make_apartment(sqm=50)
        assert apt.matches(make_filter(min_sqm=30, max_sqm=70)) is True

    def test_sqm_below_min_fails(self):
        apt = make_apartment(sqm=20)
        assert apt.matches(make_filter(min_sqm=30, max_sqm=70)) is False

    def test_sqm_above_max_fails(self):
        apt = make_apartment(sqm=90)
        assert apt.matches(make_filter(min_sqm=30, max_sqm=70)) is False

    def test_none_sqm_skips_sqm_check(self):
        apt = make_apartment(sqm=None)
        assert apt.matches(make_filter()) is True

    # ── social status ─────────────────────────────────────────

    def test_any_filter_accepts_market_apt(self):
        apt = make_apartment(social_status=SocialStatus.MARKET)
        assert apt.matches(make_filter(social_status=SocialStatus.ANY)) is True

    def test_any_filter_accepts_wbs_apt(self):
        apt = make_apartment(social_status=SocialStatus.WBS)
        assert apt.matches(make_filter(social_status=SocialStatus.ANY)) is True

    def test_market_filter_blocks_wbs_apt(self):
        apt = make_apartment(social_status=SocialStatus.WBS)
        assert apt.matches(make_filter(social_status=SocialStatus.MARKET)) is False

    def test_market_filter_blocks_wbs_in_title(self):
        apt = make_apartment(
            title="3 Zimmer WBS Wohnung", social_status=SocialStatus.ANY
        )
        assert apt.matches(make_filter(social_status=SocialStatus.MARKET)) is False

    def test_market_filter_blocks_berechtigungsschein_in_title(self):
        apt = make_apartment(
            title="Wohnung mit Berechtigungsschein", social_status=SocialStatus.ANY
        )
        assert apt.matches(make_filter(social_status=SocialStatus.MARKET)) is False

    def test_wbs_filter_blocks_market_apt(self):
        apt = make_apartment(social_status=SocialStatus.MARKET)
        assert apt.matches(make_filter(social_status=SocialStatus.WBS)) is False

    def test_wbs_filter_accepts_wbs_apt(self):
        apt = make_apartment(social_status=SocialStatus.WBS)
        assert apt.matches(make_filter(social_status=SocialStatus.WBS)) is True

    def test_wbs_filter_accepts_wbs_in_title(self):
        apt = make_apartment(title="WBS Wohnung Berlin", social_status=SocialStatus.ANY)
        assert apt.matches(make_filter(social_status=SocialStatus.WBS)) is True

    def test_market_filter_accepts_market_apt(self):
        apt = make_apartment(social_status=SocialStatus.MARKET)
        assert apt.matches(make_filter(social_status=SocialStatus.MARKET)) is True


class TestApartmentToTelegramMessage:

    def test_contains_title(self):
        apt = make_apartment(title="Schöne Wohnung")
        msg = apt.to_telegram_message("en")
        assert "Schöne Wohnung" in msg

    def test_contains_url(self):
        apt = make_apartment(url="https://example.com/apt/123")
        msg = apt.to_telegram_message("en")
        assert "https://example.com/apt/123" in msg

    def test_contains_source(self):
        apt = make_apartment(source="Degewo")
        msg = apt.to_telegram_message("en")
        assert "Degewo" in msg

    def test_contains_price(self):
        apt = make_apartment(price=750.0)
        msg = apt.to_telegram_message("en")
        assert "750" in msg

    def test_contains_rooms(self):
        apt = make_apartment(rooms=2)
        msg = apt.to_telegram_message("en")
        assert "2" in msg

    def test_contains_sqm(self):
        apt = make_apartment(sqm=55.0)
        msg = apt.to_telegram_message("en")
        assert "55" in msg

    def test_contains_address(self):
        apt = make_apartment(address="Musterstraße 1", district="Mitte")
        msg = apt.to_telegram_message("en")
        assert "Musterstraße 1" in msg
        assert "Mitte" in msg

    def test_wbs_required_shown_for_wbs_apt(self):
        apt = make_apartment(social_status=SocialStatus.WBS)
        msg = apt.to_telegram_message("en")
        assert "required" in msg

    def test_wbs_not_required_shown_for_market_apt(self):
        apt = make_apartment(social_status=SocialStatus.MARKET)
        msg = apt.to_telegram_message("en")
        assert "not required" in msg

    def test_ru_lang_uses_russian_labels(self):
        apt = make_apartment()
        msg = apt.to_telegram_message("ru")
        assert "Комнат" in msg or "Адрес" in msg or "Площадь" in msg

    def test_en_lang_uses_english_labels(self):
        apt = make_apartment()
        msg = apt.to_telegram_message("en")
        assert "Rooms" in msg or "Address" in msg or "Area" in msg

    def test_optional_fields_omitted_when_none(self):
        apt = make_apartment(address=None, district=None, floor=None, published_at=None)
        msg = apt.to_telegram_message("en")
        assert "Floor" not in msg
        assert "Published" not in msg

    def test_cold_rent_shown_when_present(self):
        apt = make_apartment(cold_rent=500.0)
        msg = apt.to_telegram_message("en")
        assert "Cold rent" in msg

    def test_extra_costs_shown_when_present(self):
        apt = make_apartment(extra_costs=150.0)
        msg = apt.to_telegram_message("en")
        assert "Extra costs" in msg

    def test_fallback_to_en_for_unknown_lang(self):
        apt = make_apartment()
        msg = apt.to_telegram_message("de")
        assert apt.title in msg
