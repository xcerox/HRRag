import uuid
import datetime
import logging
from pathlib import Path

from fastapi import BackgroundTasks, UploadFile, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, delete

from app.core.config import settings
from app.core.embeddings import embed_texts
from app.documents.models import Document, DocumentChunk

logger = logging.getLogger(__name__)

ALLOWED_EXTENSIONS = {".pdf", ".docx", ".txt", ".md"}
ALLOWED_MIME_TYPES = {
    "application/pdf",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "text/plain",
    "text/markdown",
    "text/x-markdown",
}

# Parent chunks: large context windows for the LLM
PARENT_SIZE = 2000   # words
PARENT_OVERLAP = 100  # words

# Child chunks: small slices for embedding and retrieval
CHILD_SIZE = 400    # words
CHILD_OVERLAP = 50  # words


def _split_words(text: str, size: int, overlap: int) -> list[str]:
    words = text.split()
    chunks, i = [], 0
    while i < len(words):
        chunk = " ".join(words[i : i + size])
        if chunk.strip():
            chunks.append(chunk)
        i += size - overlap
    return chunks


def _build_parent_child(text: str, doc_id: str, user_email: str) -> tuple[list[dict], list[dict]]:
    """
    Split text into parents (~2000 words) and children (~400 words).

    Each child belongs to exactly one parent. Only children are embedded.
    At retrieval time, the child's embedding identifies the relevant passage,
    and the parent text is returned as context so the LLM sees the full window.
    """
    parents: list[dict] = []
    children: list[dict] = []

    parent_texts = _split_words(text, PARENT_SIZE, PARENT_OVERLAP)
    child_global = 0

    for p_idx, parent_text in enumerate(parent_texts):
        parent_id = f"{doc_id}_p{p_idx}"
        parents.append({
            "id": parent_id,
            "document_id": doc_id,
            "user_email": user_email,
            "parent_id": None,
            "content": parent_text,
            "embedding": None,
            "chunk_index": p_idx,
        })

        child_texts = _split_words(parent_text, CHILD_SIZE, CHILD_OVERLAP)
        for c_idx, child_text in enumerate(child_texts):
            children.append({
                "id": f"{doc_id}_c{child_global}",
                "document_id": doc_id,
                "user_email": user_email,
                "parent_id": parent_id,
                "content": child_text,
                "embedding": None,   # filled in _store_chunks
                "chunk_index": child_global,
            })
            child_global += 1

    logger.info("[INDEX] doc=%s  parents=%d  children=%d", doc_id, len(parents), len(children))
    return parents, children


# ── Upload ────────────────────────────────────────────────────────────────────

async def upload(user_email: str, file: UploadFile, db: AsyncSession, bg: BackgroundTasks) -> Document:
    ext = Path(file.filename or "").suffix.lower()
    if file.content_type not in ALLOWED_MIME_TYPES and ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(status_code=400, detail="Tipo de archivo no soportado")

    data = await file.read()
    if len(data) > settings.max_file_size_mb * 1024 * 1024:
        raise HTTPException(status_code=400, detail=f"Archivo muy grande (máx {settings.max_file_size_mb} MB)")

    doc_id = str(uuid.uuid4())
    saved_name = f"{doc_id}{ext}"
    dest = Path(settings.upload_dir) / user_email
    dest.mkdir(parents=True, exist_ok=True)
    (dest / saved_name).write_bytes(data)

    doc = Document(
        id=doc_id,
        user_email=user_email,
        filename=saved_name,
        original_name=file.filename or saved_name,
        file_size=len(data),
        mime_type=file.content_type,
        chunks_count=0,
        status="indexing",
        created_at=datetime.datetime.now(datetime.timezone.utc),
    )
    db.add(doc)
    await db.commit()
    await db.refresh(doc)

    bg.add_task(_index_document, doc_id, user_email, data, file.filename or "", file.content_type or "")
    return doc


# ── Indexing (background) ─────────────────────────────────────────────────────

async def _index_document(doc_id: str, user_email: str, data: bytes, filename: str, mime_type: str) -> None:
    ext = Path(filename).suffix.lower()
    try:
        if ext == ".pdf" or mime_type == "application/pdf":
            from app.documents.processors.pdf import extract_text
        elif ext == ".docx":
            from app.documents.processors.docx import extract_text
        else:
            from app.documents.processors.text import extract_text

        text = extract_text(data)
        parents, children = _build_parent_child(text, doc_id, user_email)

        if not children:
            logger.warning("[INDEX] doc=%s produced no chunks", doc_id)
            await _set_status(doc_id, "indexed", 0)
            return

        await _store_chunks(parents, children)
        await _set_status(doc_id, "indexed", len(children))

    except Exception as exc:
        logger.exception("[INDEX] doc=%s failed: %s", doc_id, exc)
        await _set_status(doc_id, "error", 0)


async def _store_chunks(parents: list[dict], children: list[dict], batch: int = 32) -> None:
    from app.core.database import AsyncSessionLocal

    async with AsyncSessionLocal() as db:
        # Insert parents first (children FK → parent)
        for p in parents:
            db.add(DocumentChunk(**p))
        await db.commit()

        # Insert children in batches, embedding only child content
        for i in range(0, len(children), batch):
            slice_ = children[i : i + batch]
            embeddings = await embed_texts([c["content"] for c in slice_])
            for record, vec in zip(slice_, embeddings):
                db.add(DocumentChunk(**{**record, "embedding": vec}))
            await db.commit()
            logger.info("[INDEX] stored children %d-%d", i, i + len(slice_) - 1)


async def _set_status(doc_id: str, status: str, chunks_count: int) -> None:
    from app.core.database import AsyncSessionLocal

    async with AsyncSessionLocal() as db:
        result = await db.execute(select(Document).where(Document.id == doc_id))
        doc = result.scalar_one_or_none()
        if doc:
            doc.status = status
            doc.chunks_count = chunks_count
            await db.commit()


# ── CRUD ──────────────────────────────────────────────────────────────────────

async def list_documents(user_email: str, db: AsyncSession) -> list[Document]:
    result = await db.execute(
        select(Document).where(Document.user_email == user_email).order_by(Document.created_at.desc())
    )
    return list(result.scalars().all())


async def delete_document(doc: Document, db: AsyncSession) -> None:
    # Cascade deletes children first (FK), then parents
    await db.execute(delete(DocumentChunk).where(DocumentChunk.document_id == doc.id))
    try:
        path = Path(settings.upload_dir) / doc.user_email / doc.filename
        if path.exists():
            path.unlink()
    except Exception as exc:
        logger.warning("[DELETE] file error: %s", exc)
    await db.delete(doc)
    await db.commit()
