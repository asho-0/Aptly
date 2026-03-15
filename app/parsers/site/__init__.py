from app.parsers.site.sites import DegewoScraper, GewobagScraper, WBMScraper
from app.parsers.base.base import BaseScraper

ALL_SCRAPERS: list[type[BaseScraper]] = [
    DegewoScraper,
    GewobagScraper,
    WBMScraper,
]

__all__ = [
    "DegewoScraper",
    "GewobagScraper",
    "WBMScraper",
    "ALL_SCRAPERS",
]
