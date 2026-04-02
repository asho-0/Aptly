from app.core.apartment import ApartmentFilter
from app.core.enums import SocialStatus
from app.parsers.site import InBerlinWohnenScraper


def build_raw_card(**overrides):
    payload = {
        "externalId": "15413",
        "title": "2 Zimmer Wohnung im Herzen von Lichtenrade",
        "address": "Bahnhofstraße 7, 12305, Tempelhof-Schöneberg",
        "url": "https://www.degewo.de/de/properties/W1140-00564-0001-0101.html",
        "priceText": "720,65 €",
        "areaText": "67,82 m²",
        "roomText": "2 Zimmer",
        "detailText": "WBS nicht erforderlich",
        "imageUrl": "https://www.inberlinwohnen.de/image.webp",
        "wbs": "nicht erforderlich",
    }
    payload.update(overrides)
    return payload


class TestInBerlinWohnenScraper:
    def test_parse_valid_card(self):
        scraper = InBerlinWohnenScraper()
        listing = scraper._parse_raw_card(build_raw_card())
        assert listing is not None
        assert listing.id == "inberlinwohnen:15413"
        assert listing.price == 720.65
        assert listing.sqm == 67.82
        assert listing.rooms == 2.0
        assert listing.source == "Degewo"
        assert listing.social_status == SocialStatus.MARKET

    def test_parse_wbs_card(self):
        scraper = InBerlinWohnenScraper()
        listing = scraper._parse_raw_card(
            build_raw_card(
                externalId="15412",
                url="https://www.howoge.de/wohnungen-gewerbe/wohnungssuche/detail/1771-12740-23.html?t=ibw",
                title="Die 3-Zimmerwohnung in Lichtenberg",
                wbs="erforderlich",
                detailText="WBS erforderlich",
            )
        )
        assert listing is not None
        assert listing.source == "Howoge"
        assert listing.social_status == SocialStatus.WBS

    def test_short_circuits_invalid_card(self):
        scraper = InBerlinWohnenScraper()
        listing = scraper._parse_raw_card(build_raw_card(priceText="Preis auf Anfrage"))
        assert listing is None

    def test_special_content_filtered_by_default(self):
        listing = InBerlinWohnenScraper()._parse_raw_card(
            build_raw_card(
                title="Studentenwohnung in Berlin",
                detailText="Ideal für Student und Senioren",
            )
        )
        assert listing is not None
        filt = ApartmentFilter(
            min_rooms=1,
            max_rooms=3,
            min_sqm=10,
            max_sqm=100,
            min_price=100,
            max_price=2000,
            social_status=SocialStatus.ANY,
        )
        assert listing.matches(filt, show_special_listings=False) is False
        assert listing.matches(filt, show_special_listings=True) is True
