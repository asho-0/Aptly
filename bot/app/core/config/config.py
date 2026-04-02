import sys
from functools import lru_cache

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
    DB_PORT: int
    DB_POSTGRES: str
    TELEGRAM_BOT_TOKEN: str
    CHECK_INTERVAL_SECONDS: int
    NOTIFICATION_DELAY: float
    ENGINE_DEBUG: bool = False
    API_HOST: str = "0.0.0.0"
    API_PORT: int = 8080
    REQUEST_TIMEOUT: int
    REQUEST_DELAY: float
    GATEWAY_BASE_URL: str = API_HOST + ":" + str(API_PORT)
    MAX_RETRIES: int
    PAIRING_PIN_TTL_SECONDS: int = 300
    EXTENSION_TOKEN_TTL_SECONDS: int = 2592000
    HEADERS: dict[str, str] = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
        "Accept-Language": "de-DE,de;q=0.9,en-US;q=0.8,en;q=0.7",
    }

    model_config = SettingsConfigDict(
        env_file=_get_env_file(),
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    @property
    def DATABASE_URL_asyncpg(self) -> str:
        return (
            f"postgresql+asyncpg://{self.DB_USER}:{self.DB_PASS}"
            f"@{self.DB_HOST}:{self.DB_PORT}/{self.DB_NAME}"
        )

    @property
    def DATABASE_URL_psycopg(self) -> str:
        return (
            f"postgresql+psycopg2://{self.DB_USER}:{self.DB_PASS}"
            f"@{self.DB_HOST}:{self.DB_PORT}/{self.DB_NAME}"
        )

    @property
    def DATABASE_URL(self) -> str:
        return (
            f"postgresql+psycopg2://{self.DB_USER}:{self.DB_PASS}"
            f"@{self.DB_HOST}:{self.DB_PORT}/{self.DB_POSTGRES}"
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


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()  # type: ignore[call-arg]


settings = get_settings()
