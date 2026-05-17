import logging
import os
from contextlib import asynccontextmanager
from typing import AsyncIterator

from mcp.server.fastmcp import FastMCP, Context
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import AsyncSessionLocal, init_db
from app.mcp.auth import validate_token
from app.mcp.tools import search as _search_mod
from app.mcp.tools import get_chunk as _get_chunk_mod
from app.mcp.tools import get_context as _get_context_mod
from app.mcp.tools import compare as _compare_mod
from app.mcp.tools import references as _references_mod
from app.mcp.tools import documents as _documents_mod

logger = logging.getLogger(__name__)


@asynccontextmanager
async def _lifespan(server: FastMCP) -> AsyncIterator[None]:
    await init_db()
    logger.info("[MCP] servidor iniciado, BD lista")
    yield
    logger.info("[MCP] servidor detenido")


mcp = FastMCP("hrrag", lifespan=_lifespan, streamable_http_path="/")


# ── Auth ───────────────────────────────────────────────────────────────────────

async def _get_session(ctx: Context) -> tuple[AsyncSession, str]:
    """
    Extracts token from wherever it is:
    - HTTP transport: Authorization header of the current request
    - stdio transport: HRRAG_TOKEN environment variable
    """
    token = ""
    request = getattr(ctx.request_context, "request", None)
    if request is not None:
        auth = request.headers.get("authorization", "")
        if auth.lower().startswith("bearer "):
            token = auth[7:]
    else:
        token = os.environ.get("HRRAG_TOKEN", "")

    db = AsyncSessionLocal()
    try:
        user = await validate_token(token, db)
        return db, user.email
    except Exception:
        await db.close()
        raise


# ── Tools ──────────────────────────────────────────────────────────────────────

@mcp.tool()
async def search(query: str, ctx: Context, doc_type: str | None = None, limit: int | None = None) -> list[dict]:
    """
    Búsqueda semántica + texto completo sobre los documentos del usuario.
    Devuelve chunks padre con contenido completo (~2000 palabras) y puntuación.
    doc_type opcional: 'ley', 'contrato', 'politica_interna', 'reglamento'.
    """
    db, email = await _get_session(ctx)
    try:
        return [r.model_dump() for r in await _search_mod.search(query, email, db, doc_type=doc_type, limit=limit)]
    finally:
        await db.close()


@mcp.tool()
async def get_chunk(chunk_id: str, ctx: Context) -> dict:
    """
    Obtiene un chunk por ID directo (sin búsqueda). Si el ID es de un chunk hijo,
    resuelve y devuelve el padre automáticamente.
    """
    db, email = await _get_session(ctx)
    try:
        return (await _get_chunk_mod.get_chunk(chunk_id, email, db)).model_dump()
    finally:
        await db.close()


@mcp.tool()
async def get_context(chunk_id: str, ctx: Context) -> dict:
    """
    Dado un chunk hijo, devuelve el chunk mismo más el anterior y siguiente
    (hermanos por chunk_index dentro del mismo padre). Útil para verificar
    excepciones o condiciones en el contexto inmediato.
    """
    db, email = await _get_session(ctx)
    try:
        return (await _get_context_mod.get_context(chunk_id, email, db)).model_dump()
    finally:
        await db.close()


@mcp.tool()
async def compare(query: str, ctx: Context) -> dict:
    """
    Ejecuta search() en paralelo sobre todos los tipos de documento disponibles
    y agrupa los resultados por doc_type. Ideal para preguntas que requieren
    comparar ley vs política interna vs contrato.
    """
    db, email = await _get_session(ctx)
    try:
        return await _compare_mod.compare(query, email, db)
    finally:
        await db.close()


@mcp.tool()
async def find_references(chunk_id: str, ctx: Context) -> list[dict]:
    """
    Busca todos los chunks que mencionan o referencian al chunk dado —
    por número de artículo, nombre de documento u otras frases clave.
    """
    db, email = await _get_session(ctx)
    try:
        return [r.model_dump() for r in await _references_mod.find_references(chunk_id, email, db)]
    finally:
        await db.close()


@mcp.tool()
async def list_documents(ctx: Context, doc_type: str | None = None) -> list[dict]:
    """
    Lista todos los documentos indexados del usuario.
    Útil para conocer las fuentes disponibles antes de decidir qué herramienta usar.
    doc_type opcional para filtrar por tipo.
    """
    db, email = await _get_session(ctx)
    try:
        return [r.model_dump() for r in await _documents_mod.list_documents(email, db, doc_type=doc_type)]
    finally:
        await db.close()
