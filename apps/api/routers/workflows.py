from __future__ import annotations

import uuid

from fastapi import APIRouter, HTTPException, status
from sqlalchemy import select

from deps import AuthDep, DbDep
from models import Workflow
from schemas import WorkflowCreate, WorkflowOut

router = APIRouter(prefix="/api/workflows", tags=["workflows"])


@router.get("")
async def list_workflows(auth: AuthDep, db: DbDep) -> dict:
    rows = (
        await db.scalars(select(Workflow).where(Workflow.user_id == auth.user.id).order_by(Workflow.created_at.asc()))
    ).all()
    return {"items": [WorkflowOut.model_validate(w).model_dump(mode="json") for w in rows]}


@router.get("/{workflow_id}")
async def get_workflow(workflow_id: uuid.UUID, auth: AuthDep, db: DbDep) -> dict:
    row = await db.get(Workflow, workflow_id)
    if row is None or row.user_id != auth.user.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="not_found")
    return WorkflowOut.model_validate(row).model_dump(mode="json")


@router.post("", status_code=201)
async def create_workflow(body: WorkflowCreate, auth: AuthDep, db: DbDep) -> dict:
    row = Workflow(
        user_id=auth.user.id,
        name=body.name,
        description=body.description,
        steps=body.steps,
    )
    db.add(row)
    await db.commit()
    await db.refresh(row)
    return WorkflowOut.model_validate(row).model_dump(mode="json")
