.PHONY: up down build logs restart cli-create cli-drop cli-recreate cli-migrate make-migration lint format


up:
	docker compose up -d

down:
	docker compose down -v

build:
	docker compose build

logs:
	docker compose logs -f bot

restart:
	docker compose restart bot

db-create:
	python3 -m app.db.cli create

db-drop:
	python3 -m app.db.cli drop

db-recreate:
	python3 -m app.db.cli recreate

db-migrate:
	python3 -m app.db.cli migration

make-migration:
	alembic revision --autogenerate -m "$(m)"
