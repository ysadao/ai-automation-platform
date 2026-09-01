from __future__ import annotations

import uuid

from fastapi import APIRouter, HTTPException, status
from sqlalchemy import select

from deps import AuthDep, DbDep
from models import PromptTemplate, utcnow
from schemas import TemplateCreate, TemplateOut, TemplateUpdate

router = APIRouter(prefix="/api/templates", tags=["templates"])


@router.get("")
async def list_templates(auth: AuthDep, db: DbDep) -> dict:
    rows = (
        await db.scalars(
            select(PromptTemplate)
            .where(PromptTemplate.user_id == auth.user.id)
            .order_by(PromptTemplate.created_at.desc())
        )
    ).all()
    return {"items": [TemplateOut.model_validate(t).model_dump(mode="json") for t in rows]}


@router.post("", status_code=201)
async def create_template(body: TemplateCreate, auth: AuthDep, db: DbDep) -> dict:
    row = PromptTemplate(user_id=auth.user.id, name=body.name, body=body.body)
    db.add(row)
    await db.commit()
    await db.refresh(row)
    return TemplateOut.model_validate(row).model_dump(mode="json")


@router.get("/{template_id}")
async def get_template(template_id: uuid.UUID, auth: AuthDep, db: DbDep) -> dict:
    row = await db.get(PromptTemplate, template_id)
    if row is None or row.user_id != auth.user.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="not_found")
    return TemplateOut.model_validate(row).model_dump(mode="json")


@router.put("/{template_id}")
async def update_template(template_id: uuid.UUID, body: TemplateUpdate, auth: AuthDep, db: DbDep) -> dict:
    row = await db.get(PromptTemplate, template_id)
    if row is None or row.user_id != auth.user.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="not_found")
    if body.name is not None:
        row.name = body.name
    if body.body is not None:
        row.body = body.body
    row.updated_at = utcnow()
    await db.commit()
    await db.refresh(row)
    return TemplateOut.model_validate(row).model_dump(mode="json")


@router.delete("/{template_id}", status_code=204)
async def delete_template(template_id: uuid.UUID, auth: AuthDep, db: DbDep) -> None:
    row = await db.get(PromptTemplate, template_id)
    if row is None or row.user_id != auth.user.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="not_found")
    await db.delete(row)
    await db.commit()
