from __future__ import annotations

import uuid

from fastapi import APIRouter, HTTPException, Request, status
from sqlalchemy import select

from deps import AuthDep, DbDep, VerifiedDep
from models import PromptTemplate, Task, Workflow, utcnow
from schemas import TaskCreate, TaskOut

router = APIRouter(prefix="/api/tasks", tags=["tasks"])


@router.post("", status_code=202)
async def create_task(body: TaskCreate, auth: VerifiedDep, db: DbDep, request: Request) -> dict:
    if body.workflow_id:
        workflow = await db.get(Workflow, body.workflow_id)
        if workflow is None or workflow.user_id != auth.user.id:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="workflow_not_found")
    if body.template_id:
        template = await db.get(PromptTemplate, body.template_id)
        if template is None or template.user_id != auth.user.id:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="template_not_found")
    task = Task(
        user_id=auth.user.id,
        prompt=body.prompt,
        workflow_id=body.workflow_id,
        template_id=body.template_id,
        webhook_url=body.webhook_url,
        status="queued",
        steps=[],
        updated_at=utcnow(),
    )
    db.add(task)
    await db.commit()
    await db.refresh(task)
    await request.app.state.queue.put(task.id)
    return TaskOut.model_validate(task).model_dump(mode="json")


@router.get("")
async def list_tasks(auth: AuthDep, db: DbDep) -> dict:
    rows = (await db.scalars(select(Task).where(Task.user_id == auth.user.id).order_by(Task.created_at.desc()))).all()
    return {"items": [TaskOut.model_validate(t).model_dump(mode="json") for t in rows]}


@router.get("/{task_id}")
async def get_task(task_id: uuid.UUID, auth: AuthDep, db: DbDep) -> dict:
    task = await db.get(Task, task_id)
    if task is None or task.user_id != auth.user.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="not_found")
    return TaskOut.model_validate(task).model_dump(mode="json")
