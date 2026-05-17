from mcp.server.fastmcp import Context
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.core.security import decode_token
from app.auth.models import User


async def validate_token(token: str, db: AsyncSession) -> User:
    """
    Decode JWT, verify signature + expiry, check user exists.
    Raises ValueError on any failure — MCP server catches and returns an error.
    """
    if not token:
        raise ValueError("Token no proporcionado")

    payload = decode_token(token)
    if not payload:
        raise ValueError("Token inválido o expirado")

    email = payload.get("sub")
    if not email:
        raise ValueError("Token inválido: sin sujeto")

    result = await db.execute(select(User).where(User.email == email))
    user = result.scalar_one_or_none()
    if user is None:
        raise ValueError("Usuario no encontrado")

    return user


def get_token_from_env() -> str:
    """Read the JWT from the HRRAG_TOKEN environment variable (stdio transport)."""
    import os
    token = os.environ.get("HRRAG_TOKEN", "")
    if not token:
        raise RuntimeError("Variable de entorno HRRAG_TOKEN no configurada")
    return token
