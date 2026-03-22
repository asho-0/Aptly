from app.parsers.site.sites import (
    DegewoScraper,
    GewobagScraper,
    WBMScraper,
    HowogeScraper,
)
from app.parsers.base.base import BaseScraper

ALL_SCRAPERS: list[type[BaseScraper]] = [
    DegewoScraper,
    GewobagScraper,
    WBMScraper,
    HowogeScraper,
]

__all__ = [
    "DegewoScraper",
    "GewobagScraper",
    "WBMScraper",
    "HowogeScraper",
    "ALL_SCRAPERS",
]
