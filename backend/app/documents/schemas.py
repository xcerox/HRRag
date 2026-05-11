from pydantic import BaseModel
import datetime


class DocumentResponse(BaseModel):
    id: str
    user_email: str
    original_name: str
    file_size: int | None
    mime_type: str | None
    chunks_count: int
    status: str
    created_at: datetime.datetime

    model_config = {"from_attributes": True}
