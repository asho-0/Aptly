# ============================================================
# config.py — Pydantic-settings based configuration
# ============================================================

import sys
import logging
from functools import lru_cache
from pydantic import field_validator, computed_field
from pydantic_settings import BaseSettings, SettingsConfigDict


def _get_env_file() -> str:
    if any("pytest" in arg for arg in sys.argv):
        return ".env.test"
    return ".env"


class Settings(BaseSettings):

    # ── Database ──────────────────────────────────────────────
    DB_NAME: str
    DB_USER: str
    DB_PASS: str
    DB_HOST: str
    DB_PORT: int = 5432

    # ── Telegram ──────────────────────────────────────────────
    TELEGRAM_BOT_TOKEN: str
    TELEGRAM_CHAT_ID:   str

    # ── Scraping ──────────────────────────────────────────────
    CHECK_INTERVAL_SECONDS: int   = 60
    REQUEST_TIMEOUT:        int   = 15
    REQUEST_DELAY:          float = 2.0
    MAX_RETRIES:            int   = 3
    BOT_LANGUAGE:           str   = "en"   # "en" | "ru"

    # ── Redis ─────────────────────────────────────────────────
    REDIS_HOST: str = "localhost"
    REDIS_PORT: int = 6379
    REDIS_DB:   int = 0
    REDIS_PASSWORD: str | None = None

    # TTL for seen-IDs in Redis (seconds). Default: 30 days.
    # Listings older than this are assumed irrelevant and removed automatically.
    REDIS_SEEN_TTL: int = 60 * 60 * 24 * 30

    # ── App ───────────────────────────────────────────────────
    ENGINE_DEBUG:       bool  = False
    LOG_LEVEL:          str   = "INFO"

    # ── Default apartment filters ─────────────────────────────
    FILTER_MIN_ROOMS:     int   | None = None
    FILTER_MAX_ROOMS:     int   | None = None
    FILTER_MIN_SQM:       float | None = None
    FILTER_MAX_SQM:       float | None = None
    FILTER_MIN_PRICE:     float | None = None
    FILTER_MAX_PRICE:     float | None = None
    FILTER_SOCIAL_STATUS: str          = "any"
    FILTER_EXCLUDE_KEYWORDS: str = "gewerbe,büro,garage,lager,praxis"
    FILTER_INCLUDE_KEYWORDS: str = ""

    model_config = SettingsConfigDict(
        env_file        = _get_env_file(),
        env_file_encoding = "utf-8",
        case_sensitive  = False,
        extra           = "ignore",
    )

    # ── Validators ────────────────────────────────────────────

    @field_validator("LOG_LEVEL")
    @classmethod
    def validate_log_level(cls, v: str) -> str:
        allowed = {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}
        upper   = v.upper()
        if upper not in allowed:
            raise ValueError(f"LOG_LEVEL must be one of {allowed}")
        return upper

    @field_validator("BOT_LANGUAGE")
    @classmethod
    def validate_language(cls, v: str) -> str:
        if v.lower() not in {"en", "ru"}:
            raise ValueError("BOT_LANGUAGE must be 'en' or 'ru'")
        return v.lower()

    # ── Computed properties ───────────────────────────────────

    @computed_field
    @property
    def DATABASE_URL_asyncpg(self) -> str:
        return (
            f"postgresql+asyncpg://"
            f"{self.DB_USER}:{self.DB_PASS}"
            f"@{self.DB_HOST}:{self.DB_PORT}/{self.DB_NAME}"
        )

    @computed_field
    @property
    def DATABASE_URL_psycopg(self) -> str:
        """Sync URL — used for Alembic migrations."""
        return (
            f"postgresql+psycopg2://"
            f"{self.DB_USER}:{self.DB_PASS}"
            f"@{self.DB_HOST}:{self.DB_PORT}/{self.DB_NAME}"
        )
    
    @computed_field
    @property
    def REDIS_URL(self) -> str:
        auth = f":{self.REDIS_PASSWORD}@" if self.REDIS_PASSWORD else ""
        return f"redis://{auth}{self.REDIS_HOST}:{self.REDIS_PORT}/{self.REDIS_DB}"

    @property
    def engine_options(self) -> dict[str, bool | int]:
        return {
            "echo":           self.ENGINE_DEBUG,
            "pool_size":      10,
            "max_overflow":   20,
            "pool_timeout":   30,
            "pool_recycle":   1800,
            "pool_pre_ping":  True,
        }

    @property
    def exclude_keywords_list(self) -> list[str]:
        return [k.strip() for k in self.FILTER_EXCLUDE_KEYWORDS.split(",") if k.strip()]

    @property
    def include_keywords_list(self) -> list[str]:
        return [k.strip() for k in self.FILTER_INCLUDE_KEYWORDS.split(",") if k.strip()]

    # ── Helpers ───────────────────────────────────────────────

    def setup_logging(self) -> None:
        logging.basicConfig(
            level   = self.LOG_LEVEL,
            format  = "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
            datefmt = "%Y-%m-%d %H:%M:%S",
            handlers=[
                logging.StreamHandler(sys.stdout),
                logging.FileHandler("notifier.log", encoding="utf-8"),
            ],
        )


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Return a cached singleton — safe to call from anywhere."""
    return Settings()  # type: ignore[call-arg]


# Module-level singleton for direct imports:  from config import settings
settings = get_settings()