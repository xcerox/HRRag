.PHONY: help db db-stop backend frontend install setup

# ── Colors ──────────────────────────────────────────────────────────────────
BOLD  := \033[1m
RESET := \033[0m

help: ## Show this help
	@grep -E '^[a-zA-Z_-]+:.*##' $(MAKEFILE_LIST) | \
	  awk 'BEGIN {FS = ":.*##"}; {printf "  $(BOLD)%-12s$(RESET) %s\n", $$1, $$2}'

# ── Services ─────────────────────────────────────────────────────────────────

db: ## Start PostgreSQL + pgvector in background
	docker compose -f backend/docker-compose.yml up -d postgres

db-stop: ## Stop PostgreSQL
	docker compose -f backend/docker-compose.yml stop postgres

backend: ## Run FastAPI backend (requires db running)
	cd backend && uv run uvicorn main:app --reload --port 8000

frontend: ## Run React frontend in dev mode
	cd frontend && pnpm dev

# ── Setup ─────────────────────────────────────────────────────────────────────

install: ## Install backend and frontend dependencies
	cd backend && uv sync
	cd frontend && pnpm install

setup: ## First time: copy .env and install dependencies
	@if [ ! -f backend/.env ]; then \
	  cp backend/.env.example backend/.env; \
	  echo "  Created backend/.env — edit SECRET_KEY before starting"; \
	else \
	  echo "  backend/.env already exists, skipping"; \
	fi
	$(MAKE) install
