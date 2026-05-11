import uuid
import json
import datetime
import logging
from typing import AsyncGenerator

import asyncio
import httpx
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, text

from app.core.config import settings
from app.core.embeddings import embed_text, embed_texts
from app.chat.models import ChatSession, ChatMessage
from app.chat.schemas import SourceChunk
from app.chat.prompts import get_prompts

logger = logging.getLogger(__name__)


# ── Sessions ──────────────────────────────────────────────────────────────────

async def create_session(user_email: str, db: AsyncSession) -> ChatSession:
    now = datetime.datetime.now(datetime.timezone.utc)
    session = ChatSession(id=str(uuid.uuid4()), user_email=user_email, title=None, created_at=now, updated_at=now)
    db.add(session)
    await db.commit()
    await db.refresh(session)
    return session


async def list_sessions(user_email: str, db: AsyncSession) -> list[ChatSession]:
    result = await db.execute(
        select(ChatSession).where(ChatSession.user_email == user_email).order_by(ChatSession.updated_at.desc())
    )
    return list(result.scalars().all())


async def get_session(session_id: str, user_email: str, db: AsyncSession) -> ChatSession | None:
    result = await db.execute(
        select(ChatSession).where(ChatSession.id == session_id, ChatSession.user_email == user_email)
    )
    return result.scalar_one_or_none()


async def get_messages(session_id: str, db: AsyncSession) -> list[ChatMessage]:
    result = await db.execute(
        select(ChatMessage).where(ChatMessage.session_id == session_id).order_by(ChatMessage.created_at.asc())
    )
    return list(result.scalars().all())


async def delete_session(session: ChatSession, db: AsyncSession) -> None:
    await db.delete(session)
    await db.commit()


# ── HyDE + Query rewrite ──────────────────────────────────────────────────────

async def _generate_hypothetical_docs(query: str, lang: str = "en") -> list[str]:
    """
    Generate 1 HyDE hypothesis + 3 query rewrites via Ollama (parallel).
    Both run concurrently. Falls back to empty list on failure — the original
    query alone is still used as the primary search vector.
    """
    p = get_prompts(lang)
    hyde_prompt = p["hyde_prompt"].format(query=query)
    rewrite_prompt = p["rewrite_prompt"].format(query=query)

    async def _call(prompt: str, temperature: float, label: str) -> str:
        try:
            async with httpx.AsyncClient(timeout=20.0) as client:
                resp = await client.post(
                    f"{settings.ollama_base_url}/api/generate",
                    json={"model": settings.ollama_model, "prompt": prompt,
                          "stream": False, "options": {"temperature": temperature, "num_predict": 150}},
                )
                resp.raise_for_status()
                result = resp.json().get("response", "").strip()
                logger.info("[%s] %r", label, result[:120])
                return result
        except Exception as e:
            logger.warning("[%s] failed: %s", label, e)
            return ""

    hyde_text, rewrite_text = await asyncio.gather(
        _call(hyde_prompt, 0.3, "HYDE"),
        _call(rewrite_prompt, 0.5, "REWRITE"),
    )

    results: list[str] = []
    if hyde_text:
        results.append(hyde_text)
    if rewrite_text:
        for line in rewrite_text.splitlines():
            line = line.strip().lstrip("0123456789.-) ")
            if line and line.lower() != query.lower():
                results.append(line)

    return results


# ── Vector search helper ───────────────────────────────────────────────────────

async def _vec_search(vec: list[float], user_email: str, db: AsyncSession, limit: int) -> dict[str, dict]:
    rows = await db.execute(
        text("""
            SELECT dc.id, dc.parent_id, dc.content, dc.chunk_index, dc.page_number,
                   d.original_name,
                   1 - (dc.embedding <=> CAST(:vec AS vector)) AS vec_score
            FROM document_chunks dc
            JOIN documents d ON d.id = dc.document_id
            WHERE d.user_email = :user_email
              AND d.status = 'indexed'
              AND dc.parent_id IS NOT NULL
            ORDER BY dc.embedding <=> CAST(:vec AS vector)
            LIMIT :n
        """),
        {"vec": str(vec), "user_email": user_email, "n": limit},
    )
    return {row["id"]: dict(row) for row in rows.mappings()}


# ── Retrieval ─────────────────────────────────────────────────────────────────

async def _retrieve(query: str, user_email: str, db: AsyncSession, lang: str = "en") -> tuple[str, list[SourceChunk]]:
    """
    HyDE + Hybrid retrieval pipeline:

    Step 1 — HyDE (Hypothetical Document Embeddings)
        Generate 3 hypothetical document excerpts via Ollama (parallel).
        Embed each hypothesis + the original query → 4 vectors total.

    Step 2 — Vector search per vector (parallel)
        Run pgvector cosine search for each of the 4 vectors, candidate_limit each.
        Merge results: a chunk appearing in multiple searches gets a higher hit_count.

    Step 3 — Rerank by hit count + best vec_score
        hit_count: how many of the 4 searches returned this chunk (0–4).
        final_score = hit_count * 0.5 + best_vec_score * 0.5
        This promotes chunks consistently found across hypotheses.

    Step 4 — Full-text search (FTS) on original query
        tsvector + plainto_tsquery('spanish') for exact term matching.
        Merge into scored set, boosting chunks also found by FTS.

    Step 5 — Final ranking + filter
        Sort by final_score DESC, filter vec_score >= MIN_SIMILARITY or fts_norm >= 0.3.
        Take top N_RESULTS.

    Step 6 — Parent fetch
        For each selected child, fetch its parent (~2000-word context) for the LLM.
        Dedup by parent_id (one context block per parent).
    """
    # With HyDE each of the 4 vectors runs its own search — use a wider per-search
    # limit so that chunks with lower individual scores but consistent multi-hit
    # presence still make it into the merge pool.
    candidate_limit = max(settings.n_results * 10, 50)

    # ── Step 1: HyDE + query rewrite ─────────────────────────────────────────
    hypotheses = await _generate_hypothetical_docs(query, lang=lang)
    logger.info("[HYDE] query=%r  lang=%s  variants=%d  %r", query[:60], lang, len(hypotheses), [h[:60] for h in hypotheses])

    # ── Step 2: embed query + hypotheses, run vector searches in parallel ─────
    all_texts = [query] + hypotheses
    # query + hypotheses all use search_query: prefix — nomic-embed-text is asymmetric
    all_vecs = await embed_texts(all_texts, is_query=True)

    search_results: list[dict[str, dict]] = await asyncio.gather(
        *[_vec_search(vec, user_email, db, candidate_limit) for vec in all_vecs]
    )

    # Merge: track hit_count and best vec_score per chunk
    hit_count: dict[str, int] = {}
    best_vec: dict[str, dict] = {}
    for result_set in search_results:
        for chunk_id, row in result_set.items():
            hit_count[chunk_id] = hit_count.get(chunk_id, 0) + 1
            if chunk_id not in best_vec or row["vec_score"] > best_vec[chunk_id]["vec_score"]:
                best_vec[chunk_id] = row

    logger.info(
        "[HYDE] user=%s  unique_chunks=%d  multi_hit=%d",
        user_email,
        len(best_vec),
        sum(1 for c in hit_count.values() if c > 1),
    )

    # ── Step 3: FTS — query + all hypotheses/rewrites ────────────────────────
    # Run FTS for each text variant. Hypotheses use formal vocabulary that matches
    # document text better than the original colloquial query.
    fts_texts = [query] + hypotheses
    fts_map: dict[str, float] = {}

    for fts_text in fts_texts:
        if not fts_text.strip():
            continue
        fts_rows = await db.execute(
            text("""
                SELECT dc.id,
                       ts_rank_cd(to_tsvector('simple', dc.content),
                                   websearch_to_tsquery('simple', :query)) AS fts_raw
                FROM document_chunks dc
                JOIN documents d ON d.id = dc.document_id
                WHERE d.user_email = :user_email
                  AND d.status = 'indexed'
                  AND dc.parent_id IS NOT NULL
                  AND to_tsvector('simple', dc.content) @@ websearch_to_tsquery('simple', :query)
                ORDER BY fts_raw DESC
                LIMIT :n
            """),
            {"query": fts_text, "user_email": user_email, "n": candidate_limit},
        )
        for r in fts_rows.mappings():
            chunk_id = r["id"]
            if chunk_id not in fts_map or r["fts_raw"] > fts_map[chunk_id]:
                fts_map[chunk_id] = r["fts_raw"]

    logger.info("[FTS] queries=%d  unique_hits=%d", len(fts_texts), len(fts_map))
    max_fts = max(fts_map.values(), default=1.0) or 1.0

    # ── Step 4: unified scoring ───────────────────────────────────────────────
    all_ids = set(best_vec) | set(fts_map)
    scored: list[dict] = []
    for chunk_id in all_ids:
        row = best_vec.get(chunk_id)
        vec_score = row["vec_score"] if row else 0.0
        hits = hit_count.get(chunk_id, 0)
        fts_norm = fts_map.get(chunk_id, 0.0) / max_fts

        # Normalize hit_count to [0,1]: max possible hits = len(all_texts) = 4
        hit_norm = hits / len(all_texts)
        final_score = hit_norm * 0.5 + vec_score * 0.3 + fts_norm * 0.2

        if row is None:
            # FTS-only chunk: fetch its metadata
            meta_row = await db.execute(
                text("""
                    SELECT dc.id, dc.parent_id, dc.content, dc.chunk_index,
                           dc.page_number, d.original_name
                    FROM document_chunks dc
                    JOIN documents d ON d.id = dc.document_id
                    WHERE dc.id = :id
                """),
                {"id": chunk_id},
            )
            meta = meta_row.mappings().one_or_none()
            if meta is None:
                continue
            row = dict(meta)

        scored.append({**row, "vec_score": vec_score, "fts_norm": fts_norm,
                       "hit_count": hits, "final_score": final_score})

    scored.sort(key=lambda r: r["final_score"], reverse=True)

    # Dynamic threshold — mean - 1.5*std, never below min_similarity
    # Avoids cutting chunks that are relevant but slightly below a fixed cutoff.
    if scored:
        scores = [r["final_score"] for r in scored]
        mean_s = sum(scores) / len(scores)
        std_s = (sum((s - mean_s) ** 2 for s in scores) / len(scores)) ** 0.5
        dyn_threshold = max(settings.min_similarity * 0.5, mean_s - 1.5 * std_s)
        logger.info("[THRESHOLD] mean=%.3f std=%.3f dyn=%.3f", mean_s, std_s, dyn_threshold)
    else:
        dyn_threshold = 0.0

    top_children = [
        r for r in scored
        if r["final_score"] >= dyn_threshold or r["hit_count"] >= 2 or r["fts_norm"] > 0.0
    ][:settings.n_results]

    if not top_children:
        logger.info("[RETRIEVAL] query=%r  user=%s  no results after rerank", query[:60], user_email)
        return "", []

    logger.info(
        "[RETRIEVAL] query=%r  user=%s  top=%d  scores=%s",
        query[:60], user_email, len(top_children),
        [(r["hit_count"], f"{r['final_score']:.3f}") for r in top_children],
    )

    # ── Step 5: fetch parents for full context ────────────────────────────────
    parent_ids = list({c["parent_id"] for c in top_children if c["parent_id"]})
    parent_rows = await db.execute(
        text("SELECT id, content FROM document_chunks WHERE id = ANY(:ids)"),
        {"ids": parent_ids},
    )
    parent_map: dict[str, str] = {r["id"]: r["content"] for r in parent_rows.mappings()}

    seen_parents: set[str] = set()
    sources: list[SourceChunk] = []
    context_parts: list[str] = []

    for child in top_children:
        pid = child["parent_id"]
        if pid in seen_parents:
            continue
        seen_parents.add(pid)

        parent_text = parent_map.get(pid, child["content"])
        sources.append(SourceChunk(
            document_name=child["original_name"],
            chunk_index=child["chunk_index"],
            excerpt=child["content"][:300],
            page_number=child["page_number"],
        ))
        page_label = f", pág. {child['page_number']}" if child["page_number"] else ""
        context_parts.append(f"[Fuente: {child['original_name']}{page_label}]\n{parent_text}")

    return "\n\n".join(context_parts), sources


# ── Prompt ────────────────────────────────────────────────────────────────────

def _build_prompt(question: str, context: str, history: list[ChatMessage], lang: str = "en") -> str:
    p = get_prompts(lang)
    history_text = "".join(
        f"{p['history_user'] if m.role == 'user' else p['history_assistant']}: {m.content}\n"
        for m in history[-6:]
    )
    history_block = f"{p['history_prefix']}{history_text}" if history_text else ""
    if context:
        return p["system_with_context"].format(
            context=context, history=history_block, question=question
        )
    return p["system_no_context"].format(history=history_block, question=question)


# ── Streaming ─────────────────────────────────────────────────────────────────

async def stream_message(session: ChatSession, content: str, db: AsyncSession, lang: str = "en") -> AsyncGenerator[str, None]:
    now = datetime.datetime.now(datetime.timezone.utc)

    db.add(ChatMessage(id=str(uuid.uuid4()), session_id=session.id, role="user", content=content, created_at=now))
    await db.commit()

    history_result = await db.execute(
        select(ChatMessage).where(ChatMessage.session_id == session.id).order_by(ChatMessage.created_at.asc()).limit(10)
    )
    history = [m for m in history_result.scalars().all() if m.role != "user" or m.content != content]

    context, sources = await _retrieve(content, session.user_email, db, lang=lang)
    prompt = _build_prompt(content, context, history, lang=lang)

    assistant_id = str(uuid.uuid4())
    full_response = ""

    try:
        async with httpx.AsyncClient(timeout=settings.ollama_timeout) as client:
            async with client.stream(
                "POST",
                f"{settings.ollama_base_url}/api/generate",
                json={"model": settings.ollama_model, "prompt": prompt, "stream": True,
                      "options": {"temperature": settings.ollama_temperature}},
            ) as resp:
                resp.raise_for_status()
                async for line in resp.aiter_lines():
                    if not line:
                        continue
                    try:
                        event = json.loads(line)
                    except json.JSONDecodeError:
                        continue
                    token = event.get("response", "")
                    if token:
                        full_response += token
                        yield f"data: {json.dumps({'type': 'token', 'token': token})}\n\n"
                    if event.get("done"):
                        break

    except Exception as exc:
        logger.exception("[OLLAMA] stream error: %s", exc)
        yield f"data: {json.dumps({'type': 'error', 'error': str(exc)})}\n\n"
        full_response = full_response or f"Error al conectar con el modelo: {exc}"

    db.add(ChatMessage(
        id=assistant_id,
        session_id=session.id,
        role="assistant",
        content=full_response,
        sources=json.dumps([s.model_dump() for s in sources]) if sources else None,
        created_at=datetime.datetime.now(datetime.timezone.utc),
    ))

    if not session.title:
        session.title = content[:60] + ("..." if len(content) > 60 else "")
    session.updated_at = datetime.datetime.now(datetime.timezone.utc)
    await db.commit()

    yield f"data: {json.dumps({'type': 'done', 'message_id': assistant_id, 'sources': [s.model_dump() for s in sources]})}\n\n"
