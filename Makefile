.PHONY: install dev dev-api dev-web test lint build up seed reset reset-docker types

VENV := backend/.venv
PY := $(VENV)/bin/python

$(PY):
	python3.11 -m venv $(VENV)
	$(PY) -m pip install -q -r backend/requirements-dev.txt

install: $(PY) ## install backend + frontend deps
	cd frontend && npm ci

dev: install ## API on :8000 and Vite on :5173 with hot reload
	$(MAKE) -j2 dev-api dev-web

dev-api:
	cd backend && .venv/bin/uvicorn app.main:app --reload --port 8000

dev-web:
	cd frontend && npm run dev

test: install ## backend and frontend tests
	cd backend && .venv/bin/pytest -q
	cd frontend && npm test

lint: install ## ruff, mypy, eslint, tsc
	cd backend && .venv/bin/ruff check . && .venv/bin/ruff format --check . && .venv/bin/mypy app tests conftest.py
	cd frontend && npm run lint && npm run typecheck

types: $(PY) ## regenerate frontend API types from the backend schema
	cd backend && .venv/bin/python -m app.export_openapi ../frontend/src/shared/api/openapi.json
	cd frontend && npm run gen:api

build: ## build the Docker image
	docker compose build

up: ## the judges' path
	docker compose up --build

seed: $(PY) ## seed the local database if it is empty
	cd backend && .venv/bin/python -m app.modules.demo.cli seed

reset: $(PY) ## restore demo data in the local database
	cd backend && .venv/bin/python -m app.modules.demo.cli reset

reset-docker: ## restore demo data inside the running container
	docker compose exec app python -m app.modules.demo.cli reset
