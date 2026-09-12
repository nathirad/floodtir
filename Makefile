.PHONY: install dev lint typecheck migrate migration seed datagen smoke

install:
	uv sync --all-packages
	npm install

dev:
	@echo "Start services: docker compose up -d"
	@echo "Start API:      uv run --package api fastapi dev apps/api/src/api/main.py"
	@echo "Start web:      npm run dev:web"

lint:
	uv run ruff check apps/api/src apps/api/db
	npm run lint:web

lint-fix:
	uv run ruff check --fix apps/api/src apps/api/db

typecheck:
	uv run mypy apps/api/src apps/api/db
	npm run build:web

migrate:
	cd apps/api && uv run alembic upgrade head

migration:
	cd apps/api && uv run alembic revision --autogenerate -m "$(name)"

db-up:
	docker compose up -d

db-down:
	docker compose down

seed:
	uv run --package api python $(CURDIR)/scripts/seed_nodes.py

datagen:
	uv run --package api python $(CURDIR)/scripts/datagen.py

smoke:
	uv run --package api python $(CURDIR)/scripts/smoke_test.py
