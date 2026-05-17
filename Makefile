.PHONY: help db db-stop backend frontend mcp-stdio mcp-token install setup

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

backend: ## Run FastAPI backend with MCP at /mcp/ (requires db running)
	cd backend && uv run uvicorn main:app --reload --port 8000

frontend: ## Run React frontend in dev mode
	cd frontend && pnpm dev

mcp-stdio: ## Run MCP server via stdio — for Claude Code / Claude Desktop
	cd backend && HRRAG_TOKEN=$$(uv run python -c "from app.core.security import create_token; print(create_token('$$MCP_USER'))") uv run mcp_server.py

mcp-token: ## Print a fresh JWT for use in ~/.mcphost.json or .mcp.json
	@cd backend && uv run python -c "from app.core.security import create_token; print(create_token('$(or $(MCP_USER),admin@local.com)'))"

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
