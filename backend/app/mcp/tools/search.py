from sqlalchemy.ext.asyncio import AsyncSession

from app.core.retrieval import hybrid_retrieve
from app.core.config import settings
from app.mcp.schemas import ChunkResult


async def search(
    query: str,
    user_email: str,
    db: AsyncSession,
    doc_type: str | None = None,
    limit: int | None = None,
) -> list[ChunkResult]:
    results = await hybrid_retrieve(
        query=query,
        user_email=user_email,
        db=db,
        doc_type=doc_type,
        limit=limit or settings.n_results,
    )
    return [ChunkResult(**r) for r in results]
