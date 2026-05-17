import logging
from contextlib import asynccontextmanager

# Configurar logging ANTES de importar mcp para evitar que rich instale sus handlers
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
for _name in ("mcp", "mcp.server", "mcp.server.fastmcp", "mcp.server.streamable_http_manager"):
    _log = logging.getLogger(_name)
    _log.handlers.clear()
    _log.propagate = True

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.database import init_db
from app.auth.router import router as auth_router
from app.documents.router import router as documents_router
from app.chat.router import router as chat_router
from app.mcp.server import mcp

_mcp_app = mcp.streamable_http_app()
_session_manager = mcp._session_manager


@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()
    async with _session_manager.run():
        yield


app = FastAPI(title="HRRag API", version="1.0.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:80"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth_router, prefix="/auth")
app.include_router(documents_router, prefix="/hr")
app.include_router(chat_router, prefix="/hr")
app.mount("/mcp/", _mcp_app)


@app.get("/health", tags=["meta"])
async def health():
    return {"status": "ok"}


@app.get(
    "/mcp/",
    tags=["mcp"],
    summary="MCP server — Streamable HTTP transport",
    description=(
        "Model Context Protocol endpoint. Not a REST API — handled by FastMCP.\n\n"
        "Use `POST /mcp/` with JSON-RPC 2.0 and `Authorization: Bearer <jwt>`.\n\n"
        "**Tools:** `search`, `get_chunk`, `get_context`, `compare`, `find_references`, `list_documents`\n\n"
        "**Clients:** mcphost (`type: streamable`), OpenAI Responses API, Anthropic API, Claude Code.\n\n"
        "See `docs/mcp.md` for connection examples."
    ),
    include_in_schema=True,
    response_model=None,
)
async def mcp_info():
    return {
        "protocol": "MCP Streamable HTTP",
        "spec_version": "2025-03-26",
        "tools": ["search", "get_chunk", "get_context", "compare", "find_references", "list_documents"],
        "auth": "Authorization: Bearer <jwt>",
        "docs": "/docs#tag/mcp",
    }
