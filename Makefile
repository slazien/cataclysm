.PHONY: dev dev-backend dev-frontend dev-db test test-backend test-frontend lint lint-backend lint-frontend build clean

# Development
dev: dev-db dev-backend dev-frontend

dev-db:
	docker compose up -d postgres

dev-backend:
	source .venv/bin/activate && uvicorn backend.api.main:app --reload --port 8000

dev-frontend:
	cd frontend && npm run dev

# Testing
test: test-backend test-frontend test-pipeline

test-pipeline:
	source .venv/bin/activate && pytest tests/ -v

test-backend:
	source .venv/bin/activate && pytest backend/tests/ -v

test-frontend:
	cd frontend && npm test

# Linting
lint: lint-backend lint-frontend

lint-backend:
	source .venv/bin/activate && ruff check cataclysm/ tests/ app.py backend/
	source .venv/bin/activate && ruff format --check cataclysm/ tests/ app.py backend/
	source .venv/bin/activate && mypy cataclysm/ app.py backend/

lint-frontend:
	cd frontend && npm run lint

# Build
build:
	docker compose build

# Clean
clean:
	docker compose down -v
	rm -rf frontend/.next frontend/node_modules
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
