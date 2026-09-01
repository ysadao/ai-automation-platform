from __future__ import annotations

from fastapi import APIRouter
from sqlalchemy import func, select

from deps import AuthDep, DbDep
from models import UsageEvent

router = APIRouter(prefix="/api/usage", tags=["usage"])


@router.get("")
async def get_usage(auth: AuthDep, db: DbDep) -> dict:
    total = await db.scalar(
        select(func.coalesce(func.sum(UsageEvent.tokens), 0)).where(UsageEvent.user_id == auth.user.id)
    )
    count = await db.scalar(select(func.count(UsageEvent.id)).where(UsageEvent.user_id == auth.user.id))
    return {"total_tokens": int(total or 0), "task_count": int(count or 0)}
