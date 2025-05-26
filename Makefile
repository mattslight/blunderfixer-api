# Default to your local Postgres URL; override by exporting DATABASE_URL first
DATABASE_URL ?= postgresql://bf_local:secret@localhost:5432/blunderfixer_local

.PHONY: dev dbshell destroy-db worker

dev:
	dotenv run -- uvicorn app.main:app --reload

# NUKES the database and regenerates the tables from the models
# This is useful for development, but be careful with production!
destroy-db:
	@echo "Dropping & recreating public schema…"
	dotenv run -- psql $(DATABASE_URL) -c "DROP SCHEMA public CASCADE; CREATE SCHEMA public;"
	@echo "Recreating tables from models…"
	dotenv run -- python scripts/reset_db.py

# opens pgcli against your configured DATABASE_URL
dbshell:
	pgcli $(DATABASE_URL)

# run the background drill worker locally
worker:
	@echo "📢 Starting drill worker…"
	dotenv run -- bash -lc "/usr/bin/time -l python -m app.worker --once"
