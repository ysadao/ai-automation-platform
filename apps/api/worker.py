from __future__ import annotations

import asyncio
import logging
import re
import uuid
from typing import Any

import httpx

from config import get_settings
from database import SessionLocal
from models import PromptTemplate, Task, UsageEvent, Workflow, utcnow
from provider import get_provider

log = logging.getLogger("inkworks.worker")


def interpolate(template: str, data: dict[str, Any]) -> str:
    def repl(match: re.Match[str]) -> str:
        key = match.group(1)
        value = data.get(key, "")
        return "" if value is None else str(value)

    return re.sub(r"\{\{\s*([a-zA-Z0-9_]+)\s*\}\}", repl, template)


async def process_task(task_id: uuid.UUID) -> None:
    provider = get_provider()
    settings = get_settings()
    async with SessionLocal() as db:
        task = await db.get(Task, task_id)
        if task is None:
            return
        task.status = "running"
        task.updated_at = utcnow()
        await db.commit()

        workflow = await db.get(Workflow, task.workflow_id) if task.workflow_id else None
        steps: list[dict[str, Any]] = list(workflow.steps) if workflow else [{"type": "ai_complete"}]

        prompt = task.prompt or ""
        if task.template_id:
            template = await db.get(PromptTemplate, task.template_id)
            if template:
                prompt = interpolate(template.body, {"prompt": prompt})

        result_text = ""
        tokens = 0
        history: list[dict[str, Any]] = []

        try:
            for index, step in enumerate(steps):
                step_type = step.get("type")
                record: dict[str, Any] = {"index": index, "type": step_type, "status": "ok"}
                if step_type == "prompt_transform":
                    prompt = interpolate(step.get("template") or "{{prompt}}", {"prompt": prompt})
                    record["output"] = prompt
                elif step_type == "ai_complete":
                    completion = await asyncio.to_thread(provider.complete, prompt)
                    result_text = completion["text"]
                    prompt = result_text
                    tokens += int(completion["tokensIn"]) + int(completion["tokensOut"])
                    record["output"] = result_text
                    record["tokens"] = int(completion["tokensIn"]) + int(completion["tokensOut"])
                elif step_type == "delay":
                    ms = float(step.get("ms") or 0)
                    ms = min(ms, settings.delay_max_ms)
                    if ms > 0:
                        await db.commit()
                        await asyncio.sleep(ms / 1000.0)
                    record["ms"] = ms
                elif step_type == "webhook":
                    url = step.get("url") or task.webhook_url
                    if url:
                        payload = {
                            "taskId": str(task.id),
                            "status": "succeeded",
                            "result": result_text,
                        }
                        async with httpx.AsyncClient(timeout=5.0) as client:
                            response = await client.post(url, json=payload)
                            record["statusCode"] = response.status_code
                    else:
                        record["skipped"] = True
                else:
                    record["status"] = "unknown_step"
                history.append(record)

            task.status = "succeeded"
            task.result = result_text
            task.tokens_used = tokens
            task.steps = history
            task.error = None
            task.updated_at = utcnow()
            db.add(UsageEvent(user_id=task.user_id, tokens=tokens, task_id=task.id))
            await db.commit()
            await maybe_completion_webhook(task.webhook_url, str(task.id), result_text, history)
        except Exception as exc:  # noqa: BLE001 — persist worker failure on the task row
            log.exception("task %s failed", task_id)
            task.status = "failed"
            task.error = str(exc)
            task.steps = history
            task.updated_at = utcnow()
            await db.commit()


async def maybe_completion_webhook(
    url: str | None,
    task_id: str,
    result_text: str,
    history: list[dict[str, Any]],
) -> None:
    if not url:
        return
    if any(s.get("type") == "webhook" and not s.get("skipped") for s in history):
        return
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            await client.post(url, json={"taskId": task_id, "status": "succeeded", "result": result_text})
    except Exception:
        return


async def worker_loop(queue: asyncio.Queue[uuid.UUID], stop: asyncio.Event) -> None:
    while not stop.is_set():
        try:
            task_id = await asyncio.wait_for(queue.get(), timeout=0.1)
        except asyncio.TimeoutError:
            continue
        try:
            await process_task(task_id)
        except Exception:
            log.exception("worker crashed on %s", task_id)
        finally:
            queue.task_done()
