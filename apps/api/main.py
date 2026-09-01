from __future__ import annotations

import asyncio
import os
from contextlib import asynccontextmanager
from typing import Any

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from store import Store, new_id, utcnow
from worker import process_task, worker_loop

store: Store
queue: asyncio.Queue[str]
stop_event: asyncio.Event
worker_task: asyncio.Task[None] | None = None


@asynccontextmanager
async def lifespan(_app: FastAPI):
    global store, queue, stop_event, worker_task
    store = Store()
    queue = asyncio.Queue()
    stop_event = asyncio.Event()
    worker_task = asyncio.create_task(worker_loop(queue, store, stop_event))
    yield
    stop_event.set()
    if worker_task:
        worker_task.cancel()
        try:
            await worker_task
        except asyncio.CancelledError:
            pass


app = FastAPI(title="Inkworks Automation", version="1.0.0", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://127.0.0.1:3108",
        "http://localhost:3108",
    ],
    allow_methods=["*"],
    allow_headers=["*"],
)


class TaskCreate(BaseModel):
    prompt: str = Field(min_length=1)
    workflowId: str | None = None
    templateId: str | None = None
    webhookUrl: str | None = None
    data: dict[str, Any] = Field(default_factory=dict)


class WorkflowCreate(BaseModel):
    name: str = Field(min_length=1)
    description: str = ""
    steps: list[dict[str, Any]] = Field(min_length=1)


class TemplateCreate(BaseModel):
    name: str = Field(min_length=1)
    body: str = Field(min_length=1)


class TemplateUpdate(BaseModel):
    name: str | None = None
    body: str | None = None


class ScheduleCreate(BaseModel):
    prompt: str = Field(min_length=1)
    intervalSeconds: int = Field(ge=1)
    workflowId: str | None = None
    templateId: str | None = None
    webhookUrl: str | None = None
    enabled: bool = True


@app.get("/health")
def health() -> dict[str, Any]:
    return {
        "ok": True,
        "service": "ai-automation-platform",
        "provider": "mock-ink-1",
        "openaiConfigured": bool(os.environ.get("OPENAI_API_KEY")),
    }


@app.post("/tasks", status_code=202)
async def create_task(body: TaskCreate) -> dict[str, Any]:
    if body.workflowId and not store.get_workflow(body.workflowId):
        raise HTTPException(status_code=404, detail="workflow_not_found")
    if body.templateId and not store.get_template(body.templateId):
        raise HTTPException(status_code=404, detail="template_not_found")
    now = utcnow()
    task = {
        "id": new_id("tsk"),
        "prompt": body.prompt,
        "workflowId": body.workflowId,
        "templateId": body.templateId,
        "webhookUrl": body.webhookUrl,
        "data": body.data,
        "status": "queued",
        "result": None,
        "tokensUsed": 0,
        "steps": [],
        "createdAt": now,
        "updatedAt": now,
    }
    store.upsert_task(task)
    await queue.put(task["id"])
    return task


@app.get("/tasks")
def list_tasks() -> dict[str, Any]:
    return {"items": store.list_tasks()}


@app.get("/tasks/{task_id}")
def get_task(task_id: str) -> dict[str, Any]:
    task = store.get_task(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="not_found")
    return task


@app.post("/tasks/{task_id}/process")
async def process_now(task_id: str) -> dict[str, Any]:
    """Synchronous helper for tests and demos; still uses the same worker code."""
    task = store.get_task(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="not_found")
    return await process_task(store, task)


@app.get("/workflows")
def list_workflows() -> dict[str, Any]:
    return {"items": store.list_workflows()}


@app.get("/workflows/{workflow_id}")
def get_workflow(workflow_id: str) -> dict[str, Any]:
    workflow = store.get_workflow(workflow_id)
    if not workflow:
        raise HTTPException(status_code=404, detail="not_found")
    return workflow


@app.post("/workflows", status_code=201)
def create_workflow(body: WorkflowCreate) -> dict[str, Any]:
    workflow = {
        "id": new_id("wf"),
        "name": body.name,
        "description": body.description,
        "steps": body.steps,
    }
    return store.insert_workflow(workflow)


@app.get("/templates")
def list_templates() -> dict[str, Any]:
    return {"items": store.list_templates()}


@app.post("/templates", status_code=201)
def create_template(body: TemplateCreate) -> dict[str, Any]:
    template = {
        "id": new_id("tpl"),
        "name": body.name,
        "body": body.body,
        "createdAt": utcnow(),
    }
    return store.insert_template(template)


@app.put("/templates/{template_id}")
def update_template(template_id: str, body: TemplateUpdate) -> dict[str, Any]:
    patch = {k: v for k, v in body.model_dump().items() if v is not None}
    updated = store.update_template(template_id, patch)
    if not updated:
        raise HTTPException(status_code=404, detail="not_found")
    return updated


@app.delete("/templates/{template_id}", status_code=204)
def delete_template(template_id: str) -> None:
    if not store.delete_template(template_id):
        raise HTTPException(status_code=404, detail="not_found")


@app.get("/usage")
def get_usage() -> dict[str, Any]:
    return store.usage()


@app.get("/schedules")
def list_schedules() -> dict[str, Any]:
    return {"items": store.list_schedules()}


@app.post("/schedules", status_code=201)
def create_schedule(body: ScheduleCreate) -> dict[str, Any]:
    schedule = {
        "id": new_id("sch"),
        "prompt": body.prompt,
        "intervalSeconds": body.intervalSeconds,
        "workflowId": body.workflowId,
        "templateId": body.templateId,
        "webhookUrl": body.webhookUrl,
        "enabled": body.enabled,
        "lastRunAt": None,
        "createdAt": utcnow(),
    }
    return store.insert_schedule(schedule)
