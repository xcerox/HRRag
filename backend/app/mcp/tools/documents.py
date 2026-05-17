from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text

from app.mcp.schemas import DocumentInfo


async def list_documents(user_email: str, db: AsyncSession, doc_type: str | None = None) -> list[DocumentInfo]:
    doc_type_filter = "AND doc_type = :doc_type" if doc_type else ""
    rows = await db.execute(
        text(f"""
            SELECT id, original_name, doc_type, chunks_count, created_at
            FROM documents
            WHERE user_email = :user_email
              AND status = 'indexed'
              {doc_type_filter}
            ORDER BY created_at DESC
        """),
        {"user_email": user_email, "doc_type": doc_type},
    )
    return [DocumentInfo(**dict(r)) for r in rows.mappings()]
