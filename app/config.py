import sys
import logging
from functools import lru_cache

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


def _get_env_file() -> str:
    if any("pytest" in arg for arg in sys.argv):
        return ".env.test"
    return ".env"


class Settings(BaseSettings):
    DB_NAME: str
    DB_USER: str
    DB_PASS: str
    DB_HOST: str
    DB_PORT: int = 5432
    DB_POSTGRES: str
    TELEGRAM_BOT_TOKEN: str
    TELEGRAM_CHAT_ID: str
    CHECK_INTERVAL_SECONDS: int = 60
    REQUEST_TIMEOUT: int = 15
    REQUEST_DELAY: float = 2.0
    MAX_RETRIES: int = 3
    BOT_LANGUAGE: str = "en"
    HEADERS: dict[str, str] = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
        "Accept-Language": "de-DE,de;q=0.9,en-US;q=0.8,en;q=0.7",
    }
    ENGINE_DEBUG: bool = False
    LOG_LEVEL: str = "INFO"
    FILTER_MIN_ROOMS: int | None = None
    FILTER_MAX_ROOMS: int | None = None
    FILTER_MIN_SQM: float | None = None
    FILTER_MAX_SQM: float | None = None
    FILTER_MIN_PRICE: float | None = None
    FILTER_MAX_PRICE: float | None = None
    FILTER_SOCIAL_STATUS: str = "any"

    model_config = SettingsConfigDict(
        env_file=_get_env_file(),
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    @field_validator("LOG_LEVEL")
    @classmethod
    def validate_log_level(cls, v: str) -> str:
        allowed = {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}
        upper = v.upper()
        if upper not in allowed:
            raise ValueError(f"LOG_LEVEL must be one of {allowed}")
        return upper

    @field_validator("BOT_LANGUAGE")
    @classmethod
    def validate_language(cls, v: str) -> str:
        if v.lower() not in {"en", "ru"}:
            raise ValueError("BOT_LANGUAGE must be 'en' or 'ru'")
        return v.lower()

    @property
    def DATABASE_URL_asyncpg(self) -> str:
        return (
            f"postgresql+asyncpg://"
            f"{self.DB_USER}:{self.DB_PASS}"
            f"@{self.DB_HOST}:{self.DB_PORT}/{self.DB_NAME}"
        )

    @property
    def DATABASE_URL_psycopg(self) -> str:
        return (
            f"postgresql+psycopg2://"
            f"{self.DB_USER}:{self.DB_PASS}"
            f"@{self.DB_HOST}:{self.DB_PORT}/{self.DB_NAME}"
        )

    @property
    def DATABASE_URL(self) -> str:
        return (
            f"postgresql+psycopg2://"
            f"{self.DB_USER}:{self.DB_PASS}@{self.DB_HOST}:"
            f"{self.DB_PORT}/{self.DB_POSTGRES}"
        )

    @property
    def engine_options(self) -> dict[str, bool | int]:
        return {
            "echo": self.ENGINE_DEBUG,
            "pool_size": 10,
            "max_overflow": 20,
            "pool_timeout": 30,
            "pool_recycle": 1800,
            "pool_pre_ping": True,
        }

    def setup_logging(self) -> None:
        logging.basicConfig(
            level=self.LOG_LEVEL,
            format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
            handlers=[logging.StreamHandler(sys.stdout)],
        )


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()  # type: ignore[call-arg]


settings = get_settings()
