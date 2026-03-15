import argparse
from argparse import Namespace

from app.config import settings
from app.db.utils import create_database, drop_database, run_migrations


def parser() -> Namespace:
    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers(dest="action", required=True)

    subparsers.add_parser("create", help="Create the database")
    subparsers.add_parser("drop", help="Drop the database")
    subparsers.add_parser("recreate", help="Recreate the database")
    subparsers.add_parser("migration", help="Run migrations")

    return parser.parse_args()


def main() -> None:
    args = parser()

    if args.action == "drop":
        drop_database(db_name=settings.DB_NAME)
    if args.action == "create":
        create_database(db_name=settings.DB_NAME)
    if args.action == "recreate":
        drop_database(db_name=settings.DB_NAME)
        create_database(db_name=settings.DB_NAME)
    if args.action == "migration":
        run_migrations(db_url=settings.DATABASE_URL_psycopg)


if __name__ == "__main__":
    main()
