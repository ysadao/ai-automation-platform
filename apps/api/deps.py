from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import Depends, Header, HTTPException, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from database import get_db
from models import Session, User, utcnow
from security import decode_access

DbDep = Annotated[AsyncSession, Depends(get_db)]


class AuthContext:
    def __init__(self, user: User, session: Session) -> None:
        self.user = user
        self.session = session


def _bearer(authorization: str | None) -> str:
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="missing_bearer")
    return authorization.split(" ", 1)[1].strip()


async def get_current_auth(
    db: DbDep,
    authorization: Annotated[str | None, Header()] = None,
) -> AuthContext:
    token = _bearer(authorization)
    try:
        payload = decode_access(token)
    except Exception:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="invalid_token") from None
    try:
        user_id = uuid.UUID(str(payload.get("sub")))
        session_id = uuid.UUID(str(payload.get("sid")))
    except (ValueError, TypeError):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="invalid_token") from None

    user = await db.get(User, user_id)
    session = await db.get(Session, session_id)
    if user is None or session is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="invalid_token")
    if session.user_id != user.id:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="invalid_token")
    if session.revoked_at is not None or session.expires_at <= utcnow():
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="session_expired")
    return AuthContext(user=user, session=session)


AuthDep = Annotated[AuthContext, Depends(get_current_auth)]


def client_meta(request: Request) -> tuple[str | None, str | None]:
    ua = request.headers.get("user-agent")
    ip = request.client.host if request.client else None
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        ip = forwarded.split(",")[0].strip()
    return ua, ip


async def require_verified(auth: AuthDep) -> AuthContext:
    if auth.user.email_verified_at is None:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="email_not_verified")
    return auth


VerifiedDep = Annotated[AuthContext, Depends(require_verified)]
