from app.parsers.base.base import BaseScraper
from app.parsers.site.inberlinwohnen import InBerlinWohnenScraper

ALL_SCRAPERS: list[type[BaseScraper]] = [InBerlinWohnenScraper]

__all__ = ["InBerlinWohnenScraper", "ALL_SCRAPERS"]
