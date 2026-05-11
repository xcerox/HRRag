import json
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.security import get_current_user
from app.auth.models import User
from app.chat.schemas import MessageRequest, MessageResponse, SessionResponse, SessionWithMessages, SourceChunk
from app.chat import service

router = APIRouter(prefix="/sessions", tags=["chat"])


@router.get("", response_model=list[SessionResponse])
async def list_sessions(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    return await service.list_sessions(current_user.email, db)


@router.post("", response_model=SessionResponse, status_code=status.HTTP_201_CREATED)
async def create_session(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    return await service.create_session(current_user.email, db)


@router.get("/{session_id}", response_model=SessionWithMessages)
async def get_session(
    session_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    session = await service.get_session(session_id, current_user.email, db)
    if not session:
        raise HTTPException(status_code=404, detail="Sesión no encontrada")

    messages = await service.get_messages(session_id, db)
    msg_list = []
    for m in messages:
        sources = []
        if m.sources:
            try:
                sources = [SourceChunk(**s) for s in json.loads(m.sources)]
            except Exception:
                pass
        msg_list.append(MessageResponse(id=m.id, role=m.role, content=m.content, sources=sources, created_at=m.created_at))

    return SessionWithMessages(
        id=session.id, user_email=session.user_email, title=session.title,
        messages=msg_list, created_at=session.created_at, updated_at=session.updated_at,
    )


@router.delete("/{session_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_session(
    session_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    session = await service.get_session(session_id, current_user.email, db)
    if not session:
        raise HTTPException(status_code=404, detail="Sesión no encontrada")
    await service.delete_session(session, db)


@router.post("/{session_id}/messages/stream")
async def stream_message(
    session_id: str,
    body: MessageRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    session = await service.get_session(session_id, current_user.email, db)
    if not session:
        raise HTTPException(status_code=404, detail="Sesión no encontrada")

    return StreamingResponse(
        service.stream_message(session, body.content, db, lang=body.lang),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
