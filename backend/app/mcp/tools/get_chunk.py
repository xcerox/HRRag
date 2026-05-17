from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text

from app.mcp.schemas import ChunkDetail


async def get_chunk(chunk_id: str, user_email: str, db: AsyncSession) -> ChunkDetail:
    row = await _fetch(chunk_id, user_email, db)
    if row is None:
        raise ValueError(f"Chunk no encontrado: {chunk_id}")

    # If it's a child, resolve to its parent
    if row["parent_id"] is not None:
        parent = await _fetch(row["parent_id"], user_email, db)
        if parent is None:
            raise ValueError(f"Chunk padre no encontrado: {row['parent_id']}")
        row = parent

    return ChunkDetail(
        chunk_id=row["id"],
        document_name=row["original_name"],
        doc_type=row.get("doc_type"),
        page_number=row["page_number"],
        content=row["content"],
    )


async def _fetch(chunk_id: str, user_email: str, db: AsyncSession) -> dict | None:
    result = await db.execute(
        text("""
            SELECT dc.id, dc.parent_id, dc.content, dc.page_number,
                   d.original_name, d.doc_type
            FROM document_chunks dc
            JOIN documents d ON d.id = dc.document_id
            WHERE dc.id = :chunk_id
              AND d.user_email = :user_email
        """),
        {"chunk_id": chunk_id, "user_email": user_email},
    )
    row = result.mappings().one_or_none()
    return dict(row) if row else None
