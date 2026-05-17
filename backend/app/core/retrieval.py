import logging
import asyncio

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text

from app.core.config import settings
from app.core.embeddings import embed_texts

logger = logging.getLogger(__name__)


async def vec_search(
    vec: list[float],
    user_email: str,
    db: AsyncSession,
    limit: int,
    doc_type: str | None = None,
) -> dict[str, dict]:
    doc_type_filter = "AND d.doc_type = :doc_type" if doc_type else ""
    rows = await db.execute(
        text(f"""
            SELECT dc.id, dc.parent_id, dc.content, dc.chunk_index, dc.page_number,
                   d.original_name, d.doc_type,
                   1 - (dc.embedding <=> CAST(:vec AS vector)) AS vec_score
            FROM document_chunks dc
            JOIN documents d ON d.id = dc.document_id
            WHERE d.user_email = :user_email
              AND d.status = 'indexed'
              AND dc.parent_id IS NOT NULL
              {doc_type_filter}
            ORDER BY dc.embedding <=> CAST(:vec AS vector)
            LIMIT :n
        """),
        {"vec": str(vec), "user_email": user_email, "n": limit, "doc_type": doc_type},
    )
    return {row["id"]: dict(row) for row in rows.mappings()}


async def fts_search(
    texts: list[str],
    user_email: str,
    db: AsyncSession,
    limit: int,
    doc_type: str | None = None,
) -> dict[str, float]:
    doc_type_filter = "AND d.doc_type = :doc_type" if doc_type else ""
    fts_map: dict[str, float] = {}
    for fts_text in texts:
        if not fts_text.strip():
            continue
        rows = await db.execute(
            text(f"""
                SELECT dc.id,
                       ts_rank_cd(to_tsvector('simple', dc.content),
                                   websearch_to_tsquery('simple', :query)) AS fts_raw
                FROM document_chunks dc
                JOIN documents d ON d.id = dc.document_id
                WHERE d.user_email = :user_email
                  AND d.status = 'indexed'
                  AND dc.parent_id IS NOT NULL
                  AND to_tsvector('simple', dc.content) @@ websearch_to_tsquery('simple', :query)
                  {doc_type_filter}
                ORDER BY fts_raw DESC
                LIMIT :n
            """),
            {"query": fts_text, "user_email": user_email, "n": limit, "doc_type": doc_type},
        )
        for r in rows.mappings():
            chunk_id = r["id"]
            if chunk_id not in fts_map or r["fts_raw"] > fts_map[chunk_id]:
                fts_map[chunk_id] = r["fts_raw"]
    return fts_map


async def hybrid_retrieve(
    query: str,
    user_email: str,
    db: AsyncSession,
    hypotheses: list[str] | None = None,
    doc_type: str | None = None,
    limit: int | None = None,
) -> list[dict]:
    """
    Hybrid vector + FTS retrieval with optional HyDE hypotheses.
    Returns a list of parent chunk dicts with scores.
    Does NOT build prompts — callers handle that.
    """
    n = limit or settings.n_results
    candidate_limit = max(n * 10, 50)
    hyps = hypotheses or []

    all_texts = [query] + hyps
    all_vecs = await embed_texts(all_texts, is_query=True)

    search_results: list[dict[str, dict]] = await asyncio.gather(
        *[vec_search(vec, user_email, db, candidate_limit, doc_type=doc_type) for vec in all_vecs]
    )

    hit_count: dict[str, int] = {}
    best_vec: dict[str, dict] = {}
    for result_set in search_results:
        for chunk_id, row in result_set.items():
            hit_count[chunk_id] = hit_count.get(chunk_id, 0) + 1
            if chunk_id not in best_vec or row["vec_score"] > best_vec[chunk_id]["vec_score"]:
                best_vec[chunk_id] = row

    fts_map = await fts_search(all_texts, user_email, db, candidate_limit, doc_type=doc_type)
    logger.info("[FTS] queries=%d  unique_hits=%d", len(all_texts), len(fts_map))
    max_fts = max(fts_map.values(), default=1.0) or 1.0

    all_ids = set(best_vec) | set(fts_map)
    scored: list[dict] = []
    for chunk_id in all_ids:
        row = best_vec.get(chunk_id)
        vec_score = row["vec_score"] if row else 0.0
        hits = hit_count.get(chunk_id, 0)
        fts_norm = fts_map.get(chunk_id, 0.0) / max_fts
        hit_norm = hits / len(all_texts)
        final_score = hit_norm * 0.5 + vec_score * 0.3 + fts_norm * 0.2

        if row is None:
            meta_row = await db.execute(
                text("""
                    SELECT dc.id, dc.parent_id, dc.content, dc.chunk_index,
                           dc.page_number, d.original_name, d.doc_type
                    FROM document_chunks dc
                    JOIN documents d ON d.id = dc.document_id
                    WHERE dc.id = :id AND d.user_email = :user_email
                """),
                {"id": chunk_id, "user_email": user_email},
            )
            meta = meta_row.mappings().one_or_none()
            if meta is None:
                continue
            row = dict(meta)

        scored.append({**row, "vec_score": vec_score, "fts_norm": fts_norm,
                       "hit_count": hits, "final_score": final_score})

    scored.sort(key=lambda r: r["final_score"], reverse=True)

    if scored:
        scores = [r["final_score"] for r in scored]
        mean_s = sum(scores) / len(scores)
        std_s = (sum((s - mean_s) ** 2 for s in scores) / len(scores)) ** 0.5
        dyn_threshold = max(settings.min_similarity * 0.5, mean_s - 1.5 * std_s)
    else:
        dyn_threshold = 0.0

    top_children = [
        r for r in scored
        if r["final_score"] >= dyn_threshold or r["hit_count"] >= 2 or r["fts_norm"] > 0.0
    ][:n]

    if not top_children:
        return []

    parent_ids = list({c["parent_id"] for c in top_children if c["parent_id"]})
    parent_rows = await db.execute(
        text("SELECT id, content FROM document_chunks WHERE id = ANY(:ids)"),
        {"ids": parent_ids},
    )
    parent_map: dict[str, str] = {r["id"]: r["content"] for r in parent_rows.mappings()}

    seen_parents: set[str] = set()
    results: list[dict] = []
    for child in top_children:
        pid = child["parent_id"]
        if pid in seen_parents:
            continue
        seen_parents.add(pid)
        results.append({
            "chunk_id": pid,
            "document_name": child["original_name"],
            "doc_type": child.get("doc_type"),
            "page_number": child["page_number"],
            "content": parent_map.get(pid, child["content"]),
            "score": round(child["final_score"], 4),
        })

    return results
