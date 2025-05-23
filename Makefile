# Makefile

# Default to your local Postgres URL; override by exporting DATABASE_URL first
DATABASE_URL ?= postgresql://bf_local:secret@localhost:5432/blunderfixer_local

.PHONY: dev dbshell

dev:
	dotenv run -- uvicorn app.main:app --reload


# opens pgcli against your configured DATABASE_URL
dbshell:
	pgcli $(DATABASE_URL)

# run the background drill worker locally
worker:
	dotenv run -- python worker.py