import pytest
from bs4 import BeautifulSoup
from app.parsers.site import DegewoScraper, GewobagScraper, WBMScraper
from app.parsers.utils.de_parsing import (
    parse_german_price,
    parse_german_room_count,
    parse_german_sqm,
    detect_social_housing_status,
)
from app.core.enums import SocialStatus
from app.tests.parser.html_consts import (
    DEGEWO_CARD_HTML,
    DEGEWO_MULTIPLE_HTML,
    DEGEWO_WBS_CARD_HTML,
    WBM_CARD_HTML,
    WBM_WBS_CARD_HTML,
    GEWOBAG_WBS_CARD_HTML,
    GEWOBAG_CARD_HTML,
    GEWOBAG_MULTIPLE_HTML,
    GEWOBAG_NO_HREF_HTML,
)


class TestParseGermanPrice:
    def test_parses_standard_format(self):
        assert parse_german_price("850,00 €") == 850.0

    def test_parses_with_dot_thousands(self):
        assert parse_german_price("1.200,00 €") == 1200.0

    def test_parses_integer_price(self):
        assert parse_german_price("750 €") == 750.0

    def test_returns_none_for_empty_string(self):
        assert parse_german_price("") is None

    def test_returns_none_for_no_number(self):
        assert parse_german_price("Preis auf Anfrage") is None

    def test_parses_price_without_currency(self):
        assert parse_german_price("650,00") == 650.0


class TestParseGermanRoomCount:
    def test_parses_integer_rooms(self):
        assert parse_german_room_count("3 Zimmer") == 3.0

    def test_parses_from_mixed_text(self):
        assert parse_german_room_count("3 Zimmer | 75,00 m²") == 3.0

    def test_returns_none_for_empty(self):
        assert parse_german_room_count("") is None

    def test_returns_none_for_no_number(self):
        assert parse_german_room_count("keine Angabe") is None


class TestParseGermanSqm:
    def test_parses_standard_sqm(self):
        assert parse_german_sqm("75,00 m²") == 75.0

    def test_parses_from_mixed_text(self):
        assert parse_german_sqm("3 Zimmer | 75,00 m²") == 75.0

    def test_parses_integer_sqm(self):
        assert parse_german_sqm("60 m²") == 60.0

    def test_returns_none_for_empty(self):
        assert parse_german_sqm("") is None

    def test_returns_none_for_no_number(self):
        assert parse_german_sqm("Fläche unbekannt") is None


class TestDetectSocialHousingStatus:
    def test_detects_wbs_keyword(self):
        assert detect_social_housing_status("WBS erforderlich") == SocialStatus.WBS

    def test_detects_wbs_in_url(self):
        assert (
            detect_social_housing_status("https://gewobag.de/wbs-wohnungen")
            == SocialStatus.WBS
        )

    def test_returns_market_for_no_wbs(self):
        assert (
            detect_social_housing_status("Schöne 3-Zimmer-Wohnung")
            == SocialStatus.MARKET
        )

    def test_returns_market_for_empty(self):
        assert detect_social_housing_status("") == SocialStatus.MARKET

    def test_case_insensitive(self):
        assert detect_social_housing_status("wbs wohnung") == SocialStatus.WBS


class TestDegewoScraper:
    @pytest.fixture
    def scraper(self):
        return DegewoScraper()

    def test_parse_single_listing(self, scraper):
        soup = BeautifulSoup(DEGEWO_CARD_HTML, "lxml")
        assert len(scraper.parse_listings(soup, "https://degewo.de")) == 1

    def test_parse_multiple_listings(self, scraper):
        soup = BeautifulSoup(DEGEWO_MULTIPLE_HTML, "lxml")
        assert len(scraper.parse_listings(soup, "https://degewo.de")) == 2

    def test_parsed_id_contains_slug(self, scraper):
        soup = BeautifulSoup(DEGEWO_CARD_HTML, "lxml")
        assert scraper.parse_listings(soup, "https://degewo.de")[0].id.startswith(
            "degewo:"
        )

    def test_parsed_id_contains_external_id(self, scraper):
        soup = BeautifulSoup(DEGEWO_CARD_HTML, "lxml")
        assert scraper.parse_listings(soup, "https://degewo.de")[0].id == "degewo:25566"

    def test_parsed_title(self, scraper):
        soup = BeautifulSoup(DEGEWO_CARD_HTML, "lxml")
        assert (
            scraper.parse_listings(soup, "https://degewo.de")[0].title
            == "3-Zimmer-Wohnung"
        )

    def test_parsed_price(self, scraper):
        soup = BeautifulSoup(DEGEWO_CARD_HTML, "lxml")
        assert scraper.parse_listings(soup, "https://degewo.de")[0].price == 850.0

    def test_parsed_rooms(self, scraper):
        soup = BeautifulSoup(DEGEWO_CARD_HTML, "lxml")
        assert scraper.parse_listings(soup, "https://degewo.de")[0].rooms == 3.0

    def test_parsed_sqm(self, scraper):
        soup = BeautifulSoup(DEGEWO_CARD_HTML, "lxml")
        assert scraper.parse_listings(soup, "https://degewo.de")[0].sqm == 75.0

    def test_parsed_address(self, scraper):
        soup = BeautifulSoup(DEGEWO_CARD_HTML, "lxml")
        assert (
            scraper.parse_listings(soup, "https://degewo.de")[0].address
            == "Musterstraße 1"
        )

    def test_parsed_district(self, scraper):
        soup = BeautifulSoup(DEGEWO_CARD_HTML, "lxml")
        assert scraper.parse_listings(soup, "https://degewo.de")[0].district == "Mitte"

    def test_parsed_source(self, scraper):
        soup = BeautifulSoup(DEGEWO_CARD_HTML, "lxml")
        assert scraper.parse_listings(soup, "https://degewo.de")[0].source == "Degewo"

    def test_wbs_detected_from_tags(self, scraper):
        soup = BeautifulSoup(DEGEWO_WBS_CARD_HTML, "lxml")
        assert (
            scraper.parse_listings(soup, "https://degewo.de")[0].social_status
            == SocialStatus.WBS
        )

    def test_market_status_for_normal_apt(self, scraper):
        soup = BeautifulSoup(DEGEWO_CARD_HTML, "lxml")
        assert (
            scraper.parse_listings(soup, "https://degewo.de")[0].social_status
            == SocialStatus.MARKET
        )

    def test_url_is_absolute(self, scraper):
        soup = BeautifulSoup(DEGEWO_CARD_HTML, "lxml")
        assert scraper.parse_listings(soup, "https://degewo.de")[0].url.startswith(
            "https://"
        )

    def test_empty_soup_returns_empty_list(self, scraper):
        soup = BeautifulSoup("<html></html>", "lxml")
        assert scraper.parse_listings(soup, "https://degewo.de") == []

    def test_make_id_format(self, scraper):
        assert scraper.make_id("12345") == "degewo:12345"

    def test_slug(self, scraper):
        assert scraper.slug == "degewo"


class TestGewobagScraper:
    @pytest.fixture
    def scraper(self):
        return GewobagScraper()

    def test_parse_single_listing(self, scraper):
        soup = BeautifulSoup(GEWOBAG_CARD_HTML, "lxml")
        assert len(scraper.parse_listings(soup, "https://gewobag.de")) == 1

    def test_parse_multiple_listings(self, scraper):
        soup = BeautifulSoup(GEWOBAG_MULTIPLE_HTML, "lxml")
        assert len(scraper.parse_listings(soup, "https://gewobag.de")) == 2

    def test_parsed_id_contains_slug(self, scraper):
        soup = BeautifulSoup(GEWOBAG_CARD_HTML, "lxml")
        assert scraper.parse_listings(soup, "https://gewobag.de")[0].id.startswith(
            "gewobag:"
        )

    def test_parsed_title(self, scraper):
        soup = BeautifulSoup(GEWOBAG_CARD_HTML, "lxml")
        result = scraper.parse_listings(soup, "https://gewobag.de")[0]
        assert "Mitte" in result.title

    def test_parsed_price(self, scraper):
        soup = BeautifulSoup(GEWOBAG_CARD_HTML, "lxml")
        assert scraper.parse_listings(soup, "https://gewobag.de")[0].price == 750.0

    def test_parsed_rooms(self, scraper):
        soup = BeautifulSoup(GEWOBAG_CARD_HTML, "lxml")
        assert scraper.parse_listings(soup, "https://gewobag.de")[0].rooms == 2.0

    def test_parsed_sqm(self, scraper):
        soup = BeautifulSoup(GEWOBAG_CARD_HTML, "lxml")
        assert scraper.parse_listings(soup, "https://gewobag.de")[0].sqm == 55.0

    def test_parsed_address(self, scraper):
        soup = BeautifulSoup(GEWOBAG_CARD_HTML, "lxml")
        result = scraper.parse_listings(soup, "https://gewobag.de")[0]
        assert "Unter den Linden" in result.address

    def test_district_bezirk_removed(self, scraper):
        soup = BeautifulSoup(GEWOBAG_CARD_HTML, "lxml")
        result = scraper.parse_listings(soup, "https://gewobag.de")[0]
        assert result.district == "Mitte"
        assert "Bezirk" not in result.district

    def test_parsed_source(self, scraper):
        soup = BeautifulSoup(GEWOBAG_CARD_HTML, "lxml")
        assert scraper.parse_listings(soup, "https://gewobag.de")[0].source == "Gewobag"

    def test_wbs_detected_from_url(self, scraper):
        soup = BeautifulSoup(GEWOBAG_WBS_CARD_HTML, "lxml")
        result = scraper.parse_listings(soup, "https://gewobag.de")[0]
        assert result.social_status == SocialStatus.WBS

    def test_market_status_for_normal_apt(self, scraper):
        soup = BeautifulSoup(GEWOBAG_CARD_HTML, "lxml")
        result = scraper.parse_listings(soup, "https://gewobag.de")[0]
        assert result.social_status == SocialStatus.MARKET

    def test_card_without_href_is_skipped(self, scraper):
        soup = BeautifulSoup(GEWOBAG_NO_HREF_HTML, "lxml")
        assert scraper.parse_listings(soup, "https://gewobag.de") == []

    def test_empty_soup_returns_empty_list(self, scraper):
        soup = BeautifulSoup("<html></html>", "lxml")
        assert scraper.parse_listings(soup, "https://gewobag.de") == []

    def test_url_is_absolute(self, scraper):
        soup = BeautifulSoup(GEWOBAG_CARD_HTML, "lxml")
        result = scraper.parse_listings(soup, "https://gewobag.de")[0]
        assert result.url.startswith("https://")

    def test_slug(self, scraper):
        assert scraper.slug == "gewobag"

    def test_make_id_format(self, scraper):
        assert scraper.make_id("test-uid") == "gewobag:test-uid"


class TestWBMScraper:
    @pytest.fixture
    def scraper(self):
        return WBMScraper()

    def test_parse_single_listing(self, scraper):
        soup = BeautifulSoup(WBM_CARD_HTML, "lxml")
        assert len(scraper.parse_listings(soup, "https://wbm.de")) == 1

    def test_parsed_id_contains_slug(self, scraper):
        soup = BeautifulSoup(WBM_CARD_HTML, "lxml")
        assert scraper.parse_listings(soup, "https://wbm.de")[0].id.startswith("wbm:")

    def test_parsed_title(self, scraper):
        soup = BeautifulSoup(WBM_CARD_HTML, "lxml")
        assert "Spandau" in scraper.parse_listings(soup, "https://wbm.de")[0].title

    def test_parsed_price(self, scraper):
        soup = BeautifulSoup(WBM_CARD_HTML, "lxml")
        assert scraper.parse_listings(soup, "https://wbm.de")[0].price == 950.0

    def test_parsed_rooms(self, scraper):
        soup = BeautifulSoup(WBM_CARD_HTML, "lxml")
        assert scraper.parse_listings(soup, "https://wbm.de")[0].rooms == 3.0

    def test_parsed_sqm(self, scraper):
        soup = BeautifulSoup(WBM_CARD_HTML, "lxml")
        assert scraper.parse_listings(soup, "https://wbm.de")[0].sqm == 72.0

    def test_parsed_source(self, scraper):
        soup = BeautifulSoup(WBM_CARD_HTML, "lxml")
        assert scraper.parse_listings(soup, "https://wbm.de")[0].source == "WBM"

    def test_wbs_detected_from_title(self, scraper):
        soup = BeautifulSoup(WBM_WBS_CARD_HTML, "lxml")
        assert (
            scraper.parse_listings(soup, "https://wbm.de")[0].social_status
            == SocialStatus.WBS
        )

    def test_market_status_for_normal_apt(self, scraper):
        soup = BeautifulSoup(WBM_CARD_HTML, "lxml")
        assert (
            scraper.parse_listings(soup, "https://wbm.de")[0].social_status
            == SocialStatus.MARKET
        )

    def test_empty_soup_returns_empty_list(self, scraper):
        soup = BeautifulSoup("<html></html>", "lxml")
        assert scraper.parse_listings(soup, "https://wbm.de") == []

    def test_card_without_href_is_skipped(self, scraper):
        html = '<div class="immo-teaser"><h3>No link</h3></div>'
        soup = BeautifulSoup(html, "lxml")
        assert scraper.parse_listings(soup, "https://wbm.de") == []

    def test_slug(self, scraper):
        assert scraper.slug == "wbm"

    def test_make_id_format(self, scraper):
        assert scraper.make_id("3-zimmer-wohnung") == "wbm:3-zimmer-wohnung"
