from __future__ import annotations

import asyncio

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase

from config import get_settings


class Base(DeclarativeBase):
    pass


engine = create_async_engine(
    get_settings().database_url,
    pool_pre_ping=True,
    pool_size=5,
    max_overflow=10,
)
SessionLocal = async_sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


async def wait_for_db(attempts: int = 30, delay: float = 1.0) -> None:
    last: Exception | None = None
    for _ in range(attempts):
        try:
            async with engine.connect() as conn:
                await conn.execute(text("SELECT 1"))
            return
        except Exception as exc:  # noqa: BLE001 — retry until Postgres accepts connections
            last = exc
            await asyncio.sleep(delay)
    raise RuntimeError(f"postgres is not ready after {attempts} attempts") from last


async def init_db() -> None:
    from models import (  # noqa: F401 — register metadata
        EmailVerificationToken,
        PasswordResetToken,
        PromptTemplate,
        Session,
        Task,
        UsageEvent,
        User,
        Workflow,
    )

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


async def get_db():
    async with SessionLocal() as db:
        yield db
