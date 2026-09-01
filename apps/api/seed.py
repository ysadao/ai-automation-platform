from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from config import get_settings
from models import PromptTemplate, User, Workflow, utcnow
from security import hash_password


DEFAULT_WORKFLOW_STEPS = [
    {
        "type": "prompt_transform",
        "template": "Rewrite the following as a concise operator brief:\n{{prompt}}",
    },
    {"type": "delay", "ms": 5},
    {"type": "ai_complete", "model": "mock-ink-1"},
]

DEFAULT_WEBHOOK_STEPS = [
    {"type": "ai_complete", "model": "mock-ink-1"},
    {"type": "webhook", "url": ""},
]


async def seed_demo(db: AsyncSession) -> User:
    settings = get_settings()
    user = await db.scalar(select(User).where(User.email == settings.demo_email))
    if user is None:
        user = User(
            email=settings.demo_email,
            password_hash=hash_password(settings.demo_password),
            first_name="Ink",
            last_name="Operator",
            email_verified_at=utcnow(),
        )
        db.add(user)
        await db.flush()

    if user.email_verified_at is None:
        user.email_verified_at = utcnow()

    if await db.scalar(select(Workflow).where(Workflow.user_id == user.id)) is None:
        db.add(
            Workflow(
                user_id=user.id,
                name="Draft and complete",
                description="Rewrite the prompt, wait a beat, then run the mock model.",
                steps=DEFAULT_WORKFLOW_STEPS,
            )
        )
        db.add(
            Workflow(
                user_id=user.id,
                name="Complete and webhook",
                description="Run the model, then POST the result if a webhook URL is present.",
                steps=DEFAULT_WEBHOOK_STEPS,
            )
        )

    if await db.scalar(select(PromptTemplate).where(PromptTemplate.user_id == user.id)) is None:
        db.add(
            PromptTemplate(
                user_id=user.id,
                name="summarize",
                body="Summarize in one paragraph:\n{{prompt}}",
            )
        )
        db.add(
            PromptTemplate(
                user_id=user.id,
                name="classify",
                body="Classify the sentiment (positive, neutral, negative) of:\n{{prompt}}",
            )
        )

    await db.commit()
    await db.refresh(user)
    return user


async def ensure_demo_user() -> None:
    from database import SessionLocal

    async with SessionLocal() as db:
        await seed_demo(db)
