from pydantic import BaseModel
import datetime


class MessageRequest(BaseModel):
    content: str
    lang: str = "en"


class SourceChunk(BaseModel):
    document_name: str
    chunk_index: int
    excerpt: str
    page_number: int | None = None


class MessageResponse(BaseModel):
    id: str
    role: str
    content: str
    sources: list[SourceChunk] = []
    created_at: datetime.datetime


class SessionResponse(BaseModel):
    id: str
    user_email: str
    title: str | None
    created_at: datetime.datetime
    updated_at: datetime.datetime


class SessionWithMessages(BaseModel):
    id: str
    user_email: str
    title: str | None
    messages: list[MessageResponse] = []
    created_at: datetime.datetime
    updated_at: datetime.datetime
