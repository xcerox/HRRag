import re
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text

from app.mcp.schemas import ReferenceResult


async def find_references(chunk_id: str, user_email: str, db: AsyncSession) -> list[ReferenceResult]:
    # Fetch the source chunk
    row = await db.execute(
        text("""
            SELECT dc.content, d.original_name
            FROM document_chunks dc
            JOIN documents d ON d.id = dc.document_id
            WHERE dc.id = :chunk_id
              AND d.user_email = :user_email
        """),
        {"chunk_id": chunk_id, "user_email": user_email},
    )
    source = row.mappings().one_or_none()
    if source is None:
        raise ValueError(f"Chunk no encontrado: {chunk_id}")

    # Extract key identifiers: article numbers and document name stem
    content = source["content"]
    doc_stem = re.sub(r"\.[^.]+$", "", source["original_name"])

    identifiers: list[str] = []
    article_matches = re.findall(r"(?:art[íi]culo|art\.?)\s*\d+[°º]?", content, re.IGNORECASE)
    identifiers.extend(article_matches[:3])
    identifiers.append(doc_stem)

    search_query = " OR ".join(f'"{t}"' for t in identifiers if t.strip())
    if not search_query:
        return []

    refs_result = await db.execute(
        text("""
            SELECT dc.id, dc.content, dc.page_number,
                   d.original_name, d.doc_type
            FROM document_chunks dc
            JOIN documents d ON d.id = dc.document_id
            WHERE d.user_email = :user_email
              AND d.status = 'indexed'
              AND dc.id != :chunk_id
              AND to_tsvector('simple', dc.content) @@ websearch_to_tsquery('simple', :query)
            ORDER BY ts_rank_cd(to_tsvector('simple', dc.content),
                                 websearch_to_tsquery('simple', :query)) DESC
            LIMIT 10
        """),
        {"user_email": user_email, "chunk_id": chunk_id, "query": search_query},
    )

    results: list[ReferenceResult] = []
    for r in refs_result.mappings():
        excerpt = r["content"][:300]
        results.append(ReferenceResult(
            chunk_id=r["id"],
            document_name=r["original_name"],
            doc_type=r["doc_type"],
            excerpt=excerpt,
            page_number=r["page_number"],
        ))
    return results
