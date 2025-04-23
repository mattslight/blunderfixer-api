.PHONY: dev

dev:
	uvicorn app.main:app --reload
