from __future__ import annotations

import uuid
from datetime import timedelta

from fastapi import APIRouter, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from config import get_settings
from deps import AuthDep, DbDep, client_meta
from models import (
    EmailVerificationToken,
    PasswordResetToken,
    Session,
    User,
    utcnow,
)
from schemas import (
    ForgotPasswordIn,
    LoginIn,
    LogoutIn,
    RefreshIn,
    RegisterIn,
    ResetPasswordIn,
    SessionOut,
    TokenPair,
    UserOut,
    VerifyEmailIn,
)
from security import (
    access_token,
    hash_password,
    hash_token,
    new_opaque_token,
    verify_password,
)

router = APIRouter(prefix="/api")


async def _issue_session(
    db: AsyncSession, user: User, user_agent: str | None, ip: str | None
) -> tuple[str, str, Session]:
    settings = get_settings()
    refresh = new_opaque_token()
    row = Session(
        user_id=user.id,
        refresh_token_hash=hash_token(refresh),
        expires_at=utcnow() + timedelta(seconds=settings.refresh_ttl_seconds),
        user_agent=user_agent,
        ip=ip,
    )
    db.add(row)
    await db.flush()
    token = access_token(user.id, row.id, user.email)
    return token, refresh, row


def _pair(user: User, access: str, refresh: str, verification: str | None = None) -> dict:
    payload = TokenPair(
        access_token=access,
        refresh_token=refresh,
        user=UserOut.model_validate(user),
        verification_token=verification,
    )
    data = payload.model_dump(mode="json")
    if verification is None:
        data.pop("verification_token", None)
    return data


@router.post("/auth/register", status_code=201)
async def register(body: RegisterIn, request: Request, db: DbDep) -> dict:
    existing = await db.scalar(select(User).where(User.email == str(body.email).lower()))
    if existing:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="email_taken")
    settings = get_settings()
    user = User(
        email=str(body.email).lower(),
        password_hash=hash_password(body.password),
        first_name=body.first_name,
        last_name=body.last_name,
    )
    db.add(user)
    await db.flush()
    raw_verify = new_opaque_token()
    db.add(
        EmailVerificationToken(
            user_id=user.id,
            token_hash=hash_token(raw_verify),
            expires_at=utcnow() + timedelta(seconds=settings.verify_ttl_seconds),
        )
    )
    ua, ip = client_meta(request)
    access, refresh, _ = await _issue_session(db, user, ua, ip)
    await db.commit()
    await db.refresh(user)
    verification = raw_verify if settings.demo_expose_tokens else None
    return _pair(user, access, refresh, verification)


@router.post("/auth/login")
async def login(body: LoginIn, request: Request, db: DbDep) -> dict:
    user = await db.scalar(select(User).where(User.email == str(body.email).lower()))
    if user is None or not verify_password(body.password, user.password_hash):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="invalid_credentials")
    ua, ip = client_meta(request)
    access, refresh, _ = await _issue_session(db, user, ua, ip)
    await db.commit()
    await db.refresh(user)
    return _pair(user, access, refresh)


@router.post("/auth/refresh")
async def refresh(body: RefreshIn, request: Request, db: DbDep) -> dict:
    hashed = hash_token(body.refresh_token)
    row = await db.scalar(select(Session).where(Session.refresh_token_hash == hashed))
    now = utcnow()
    if row is None or row.revoked_at is not None or row.expires_at <= now:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="invalid_refresh")
    user = await db.get(User, row.user_id)
    if user is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="invalid_refresh")
    row.revoked_at = now
    ua, ip = client_meta(request)
    access, refresh_token, _ = await _issue_session(db, user, ua or row.user_agent, ip or row.ip)
    await db.commit()
    await db.refresh(user)
    return _pair(user, access, refresh_token)


@router.post("/auth/logout")
async def logout(body: LogoutIn, auth: AuthDep, db: DbDep) -> dict:
    now = utcnow()
    if body.refresh_token:
        hashed = hash_token(body.refresh_token)
        row = await db.scalar(
            select(Session).where(Session.refresh_token_hash == hashed, Session.user_id == auth.user.id)
        )
        if row and row.revoked_at is None:
            row.revoked_at = now
    if auth.session.revoked_at is None:
        auth.session.revoked_at = now
    await db.commit()
    return {"ok": True}


@router.post("/auth/logout-all")
async def logout_all(auth: AuthDep, db: DbDep) -> dict:
    now = utcnow()
    rows = (await db.scalars(select(Session).where(Session.user_id == auth.user.id, Session.revoked_at.is_(None)))).all()
    for row in rows:
        row.revoked_at = now
    await db.commit()
    return {"ok": True, "revoked": len(rows)}


@router.post("/auth/verify-email")
async def verify_email(body: VerifyEmailIn, db: DbDep) -> dict:
    hashed = hash_token(body.token)
    row = await db.scalar(select(EmailVerificationToken).where(EmailVerificationToken.token_hash == hashed))
    now = utcnow()
    if row is None or row.used_at is not None or row.expires_at <= now:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="invalid_token")
    user = await db.get(User, row.user_id)
    if user is None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="invalid_token")
    row.used_at = now
    user.email_verified_at = now
    await db.commit()
    await db.refresh(user)
    return {"ok": True, "user": UserOut.model_validate(user).model_dump(mode="json")}


@router.post("/auth/forgot-password")
async def forgot_password(body: ForgotPasswordIn, db: DbDep) -> dict:
    settings = get_settings()
    user = await db.scalar(select(User).where(User.email == str(body.email).lower()))
    payload: dict = {"ok": True}
    if user is not None:
        raw = new_opaque_token()
        db.add(
            PasswordResetToken(
                user_id=user.id,
                token_hash=hash_token(raw),
                expires_at=utcnow() + timedelta(seconds=settings.reset_ttl_seconds),
            )
        )
        await db.commit()
        if settings.demo_expose_tokens:
            payload["reset_token"] = raw
    return payload


@router.post("/auth/reset-password")
async def reset_password(body: ResetPasswordIn, db: DbDep) -> dict:
    hashed = hash_token(body.token)
    row = await db.scalar(select(PasswordResetToken).where(PasswordResetToken.token_hash == hashed))
    now = utcnow()
    if row is None or row.used_at is not None or row.expires_at <= now:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="invalid_token")
    user = await db.get(User, row.user_id)
    if user is None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="invalid_token")
    row.used_at = now
    user.password_hash = hash_password(body.password)
    sessions = (await db.scalars(select(Session).where(Session.user_id == user.id, Session.revoked_at.is_(None)))).all()
    for session in sessions:
        session.revoked_at = now
    await db.commit()
    return {"ok": True}


@router.get("/me")
async def me(auth: AuthDep) -> dict:
    return UserOut.model_validate(auth.user).model_dump(mode="json")


@router.get("/me/sessions")
async def list_sessions(auth: AuthDep, db: DbDep) -> dict:
    rows = (
        await db.scalars(select(Session).where(Session.user_id == auth.user.id).order_by(Session.created_at.desc()))
    ).all()
    items = []
    for row in rows:
        item = SessionOut.model_validate(row)
        item.current = row.id == auth.session.id
        items.append(item.model_dump(mode="json"))
    return {"items": items}


@router.delete("/me/sessions/{session_id}", status_code=204)
async def revoke_session(session_id: uuid.UUID, auth: AuthDep, db: DbDep) -> None:
    row = await db.get(Session, session_id)
    if row is None or row.user_id != auth.user.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="not_found")
    if row.revoked_at is None:
        row.revoked_at = utcnow()
        await db.commit()
