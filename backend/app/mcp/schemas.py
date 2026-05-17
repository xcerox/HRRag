import datetime
from pydantic import BaseModel


class ChunkResult(BaseModel):
    chunk_id: str
    document_name: str
    doc_type: str | None
    page_number: int | None
    content: str
    score: float = 0.0


class ChunkDetail(BaseModel):
    chunk_id: str
    document_name: str
    doc_type: str | None
    page_number: int | None
    content: str


class ChunkBrief(BaseModel):
    chunk_id: str
    content: str


class ContextResult(BaseModel):
    previous: ChunkBrief | None
    current: ChunkBrief
    next: ChunkBrief | None


class ReferenceResult(BaseModel):
    chunk_id: str
    document_name: str
    doc_type: str | None
    excerpt: str
    page_number: int | None


class DocumentInfo(BaseModel):
    id: str
    original_name: str
    doc_type: str | None
    chunks_count: int
    created_at: datetime.datetime
