from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.security import get_current_user
from app.auth.schemas import LoginRequest, TokenResponse, UserResponse
from app.auth.service import login_or_create
from app.auth.models import User

router = APIRouter()


@router.post("/login", response_model=TokenResponse)
async def login(body: LoginRequest, db: AsyncSession = Depends(get_db)):
    token = await login_or_create(body.email, db)
    return TokenResponse(access_token=token)


@router.get("/me", response_model=UserResponse)
async def me(current_user: User = Depends(get_current_user)):
    return UserResponse(
        email=current_user.email,
        created_at=current_user.created_at,
        last_login=current_user.last_login,
    )
