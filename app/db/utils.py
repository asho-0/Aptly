import logging
from sqlalchemy import text, create_engine
from sqlalchemy.exc import ProgrammingError
from app.config import settings

logger = logging.getLogger(__name__)


def create_database(db_name: str) -> None:
    try:
        with create_engine(
            settings.DATABASE_URL, isolation_level="AUTOCOMMIT"
        ).begin() as conn:
            conn.execute(text(f"CREATE DATABASE {db_name};"))
    except ProgrammingError:
        logger.error("Database %s already exists", db_name)
    else:
        logger.info("Database %s created", db_name)


def drop_database(db_name: str) -> None:
    try:
        with create_engine(
            settings.DATABASE_URL, isolation_level="AUTOCOMMIT"
        ).begin() as conn:
            conn.execute(text(f"DROP DATABASE {db_name} WITH (FORCE);"))
    except ProgrammingError:
        logger.error("Database %s does not exist", db_name)
    else:
        logger.info("Database %s dropped", db_name)


def run_migrations(db_url: str) -> None:
    import alembic.config
    import alembic.command

    alembic_config = alembic.config.Config("alembic.ini")
    alembic_config.set_main_option("sqlalchemy.url", db_url)
    alembic.command.upgrade(alembic_config, "head")
    logger.info("Alembic upgrade completed for: %s", db_url)
