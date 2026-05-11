import datetime
from sqlalchemy import String, DateTime, Integer, ForeignKey, func, Text
from sqlalchemy.orm import Mapped, mapped_column
from pgvector.sqlalchemy import Vector

from app.core.database import Base
from app.core.config import settings


class Document(Base):
    __tablename__ = "documents"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    user_email: Mapped[str] = mapped_column(String, ForeignKey("users.email", ondelete="CASCADE"))
    filename: Mapped[str] = mapped_column(String, nullable=False)
    original_name: Mapped[str] = mapped_column(String, nullable=False)
    file_size: Mapped[int | None] = mapped_column(Integer, nullable=True)
    mime_type: Mapped[str | None] = mapped_column(String, nullable=True)
    chunks_count: Mapped[int] = mapped_column(Integer, default=0)
    status: Mapped[str] = mapped_column(String, default="pending")
    created_at: Mapped[datetime.datetime] = mapped_column(DateTime(timezone=True), default=func.now())


class DocumentChunk(Base):
    """
    Stores both parent and child chunks for the same document.

    Parents (parent_id IS NULL):
        Large context windows (~2000 chars). Never embedded.
        Fetched after retrieval to give the LLM full context.

    Children (parent_id IS NOT NULL):
        Small overlapping slices (~500 chars) of a parent.
        Always embedded. Used for vector + FTS retrieval.
        Each child references its parent via parent_id.
    """
    __tablename__ = "document_chunks"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    document_id: Mapped[str] = mapped_column(String, ForeignKey("documents.id", ondelete="CASCADE"))
    user_email: Mapped[str] = mapped_column(String)
    parent_id: Mapped[str | None] = mapped_column(String, ForeignKey("document_chunks.id", ondelete="CASCADE"), nullable=True)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    embedding: Mapped[list[float] | None] = mapped_column(Vector(settings.embedding_dim), nullable=True)
    chunk_index: Mapped[int] = mapped_column(Integer, default=0)
    page_number: Mapped[int | None] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime.datetime] = mapped_column(DateTime(timezone=True), default=func.now())
