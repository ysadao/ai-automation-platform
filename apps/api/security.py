from __future__ import annotations

import hashlib
import secrets
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any

import jwt
from passlib.context import CryptContext

from config import get_settings

_pwd: CryptContext | None = None


def _ctx() -> CryptContext:
    global _pwd
    if _pwd is None:
        rounds = get_settings().bcrypt_rounds
        _pwd = CryptContext(schemes=["bcrypt"], deprecated="auto", bcrypt__rounds=rounds)
    return _pwd


def hash_password(password: str) -> str:
    return _ctx().hash(password)


def verify_password(password: str, password_hash: str) -> bool:
    return _ctx().verify(password, password_hash)


def new_opaque_token() -> str:
    return secrets.token_urlsafe(48)


def hash_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def access_token(user_id: uuid.UUID, session_id: uuid.UUID, email: str) -> str:
    settings = get_settings()
    now = utcnow()
    payload: dict[str, Any] = {
        "sub": str(user_id),
        "sid": str(session_id),
        "email": email,
        "iat": int(now.timestamp()),
        "exp": int((now + timedelta(seconds=settings.jwt_access_ttl_seconds)).timestamp()),
    }
    return jwt.encode(payload, settings.jwt_secret, algorithm="HS256")


def decode_access(token: str) -> dict[str, Any]:
    settings = get_settings()
    return jwt.decode(token, settings.jwt_secret, algorithms=["HS256"])
