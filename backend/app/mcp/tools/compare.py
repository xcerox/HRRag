import asyncio
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text

from app.mcp.schemas import ChunkResult
from app.mcp.tools.search import search


async def compare(query: str, user_email: str, db: AsyncSession) -> dict[str, list[dict]]:
    # Discover which doc_types this user actually has indexed
    rows = await db.execute(
        text("""
            SELECT DISTINCT doc_type
            FROM documents
            WHERE user_email = :user_email
              AND status = 'indexed'
              AND doc_type IS NOT NULL
        """),
        {"user_email": user_email},
    )
    available_types = [r["doc_type"] for r in rows.mappings()]

    if not available_types:
        return {}

    # Run search for every doc_type in parallel
    results_per_type: list[list[ChunkResult]] = await asyncio.gather(
        *[search(query, user_email, db, doc_type=dt) for dt in available_types]
    )

    return {
        dt: [r.model_dump() for r in chunks]
        for dt, chunks in zip(available_types, results_per_type)
    }
