import datetime
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.auth.models import User
from app.core.security import create_token


async def login_or_create(email: str, db: AsyncSession) -> str:
    result = await db.execute(select(User).where(User.email == email))
    user = result.scalar_one_or_none()
    now = datetime.datetime.now(datetime.timezone.utc)

    if user is None:
        user = User(email=email, created_at=now, last_login=now)
        db.add(user)
    else:
        user.last_login = now

    await db.commit()
    return create_token(email)
