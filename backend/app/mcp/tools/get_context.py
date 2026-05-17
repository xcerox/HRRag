from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text

from app.mcp.schemas import ChunkBrief, ContextResult


async def get_context(chunk_id: str, user_email: str, db: AsyncSession) -> ContextResult:
    # Resolve chunk and get parent_id + chunk_index
    row = await db.execute(
        text("""
            SELECT dc.id, dc.parent_id, dc.chunk_index, dc.content
            FROM document_chunks dc
            JOIN documents d ON d.id = dc.document_id
            WHERE dc.id = :chunk_id
              AND d.user_email = :user_email
        """),
        {"chunk_id": chunk_id, "user_email": user_email},
    )
    chunk = row.mappings().one_or_none()
    if chunk is None:
        raise ValueError(f"Chunk no encontrado: {chunk_id}")

    parent_id = chunk["parent_id"]
    if parent_id is None:
        # It's already a parent — return it alone with no siblings
        return ContextResult(
            previous=None,
            current=ChunkBrief(chunk_id=chunk["id"], content=chunk["content"]),
            next=None,
        )

    idx = chunk["chunk_index"]

    siblings_result = await db.execute(
        text("""
            SELECT id, chunk_index, content
            FROM document_chunks
            WHERE parent_id = :parent_id
              AND chunk_index IN (:prev, :curr, :next)
            ORDER BY chunk_index
        """),
        {"parent_id": parent_id, "prev": idx - 1, "curr": idx, "next": idx + 1},
    )
    siblings = {r["chunk_index"]: r for r in siblings_result.mappings()}

    def brief(ci: int) -> ChunkBrief | None:
        r = siblings.get(ci)
        return ChunkBrief(chunk_id=r["id"], content=r["content"]) if r else None

    current = siblings.get(idx)
    if current is None:
        raise ValueError(f"Chunk no encontrado en contexto: {chunk_id}")

    return ContextResult(
        previous=brief(idx - 1),
        current=ChunkBrief(chunk_id=current["id"], content=current["content"]),
        next=brief(idx + 1),
    )
