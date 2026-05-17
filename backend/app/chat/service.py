import uuid
import json
import datetime
import logging
from typing import AsyncGenerator

import asyncio
import httpx
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.core.config import settings
from app.core.embeddings import embed_texts
from app.core.retrieval import hybrid_retrieve
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


# ── Retrieval ─────────────────────────────────────────────────────────────────

async def _retrieve(query: str, user_email: str, db: AsyncSession, lang: str = "en") -> tuple[str, list[SourceChunk]]:
    hypotheses = await _generate_hypothetical_docs(query, lang=lang)
    logger.info("[HYDE] query=%r  lang=%s  variants=%d", query[:60], lang, len(hypotheses))

    results = await hybrid_retrieve(query, user_email, db, hypotheses=hypotheses)

    if not results:
        logger.info("[RETRIEVAL] query=%r  user=%s  no results", query[:60], user_email)
        return "", []

    logger.info("[RETRIEVAL] query=%r  user=%s  top=%d", query[:60], user_email, len(results))

    sources: list[SourceChunk] = []
    context_parts: list[str] = []
    for r in results:
        sources.append(SourceChunk(
            document_name=r["document_name"],
            chunk_index=0,
            excerpt=r["content"][:300],
            page_number=r["page_number"],
        ))
        page_label = f", pág. {r['page_number']}" if r["page_number"] else ""
        context_parts.append(f"[Fuente: {r['document_name']}{page_label}]\n{r['content']}")

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
