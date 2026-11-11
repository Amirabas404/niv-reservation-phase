import secrets
from collections.abc import AsyncIterator

from fastapi import Header, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.db.session import SessionLocal


def require_service_token(x_service_token: str = Header(default="")) -> None:
    """Only the bots and worker hold this token. Role checks (RBAC) are added in Phase 4."""
    expected = get_settings().internal_service_token.get_secret_value()
    if not secrets.compare_digest(x_service_token, expected):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="unauthorized")


async def get_session() -> AsyncIterator[AsyncSession]:
    async with SessionLocal() as session:
        yield session
