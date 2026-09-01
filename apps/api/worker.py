from __future__ import annotations

import asyncio
from typing import Any

import httpx

from provider import get_provider
from store import Store, interpolate, new_id, utcnow

provider = get_provider()


async def process_task(store: Store, task: dict[str, Any]) -> dict[str, Any]:
    task = {**task, "status": "running", "updatedAt": utcnow()}
    store.upsert_task(task)

    workflow_id = task.get("workflowId")
    workflow = store.get_workflow(workflow_id) if workflow_id else None
    steps = list(workflow["steps"]) if workflow else [{"type": "ai_complete", "model": "mock-ink-1"}]

    prompt = task.get("prompt") or ""
    template_id = task.get("templateId")
    if template_id:
        template = store.get_template(template_id)
        if template:
            prompt = interpolate(template["body"], {"prompt": prompt, **(task.get("data") or {})})

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
                completion = provider.complete(prompt)
                result_text = completion["text"]
                prompt = result_text
                tokens += int(completion["tokensIn"]) + int(completion["tokensOut"])
                record["output"] = result_text
                record["tokens"] = completion["tokensIn"] + completion["tokensOut"]
            elif step_type == "delay":
                ms = float(step.get("ms") or 0)
                if ms > 0:
                    await asyncio.sleep(ms / 1000.0)
                record["ms"] = ms
            elif step_type == "webhook":
                url = step.get("url") or task.get("webhookUrl")
                if url:
                    payload = {
                        "taskId": task["id"],
                        "status": "completed",
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

        task.update(
            {
                "status": "completed",
                "result": result_text,
                "tokensUsed": tokens,
                "steps": history,
                "completedAt": utcnow(),
                "updatedAt": utcnow(),
                "error": None,
            }
        )
        store.upsert_task(task)
        store.add_usage(tokens)
        await maybe_completion_webhook(task, result_text)
        return task
    except Exception as exc:  # noqa: BLE001 — surface worker failures on the task row
        task.update(
            {
                "status": "failed",
                "error": str(exc),
                "steps": history,
                "updatedAt": utcnow(),
            }
        )
        store.upsert_task(task)
        return task


async def maybe_completion_webhook(task: dict[str, Any], result_text: str) -> None:
    url = task.get("webhookUrl")
    if not url:
        return
    steps = task.get("steps") or []
    if any(s.get("type") == "webhook" and not s.get("skipped") for s in steps):
        return
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            await client.post(
                url,
                json={"taskId": task["id"], "status": task.get("status"), "result": result_text},
            )
    except Exception:
        return


async def worker_loop(queue: asyncio.Queue[str], store: Store, stop: asyncio.Event) -> None:
    while not stop.is_set():
        try:
            task_id = await asyncio.wait_for(queue.get(), timeout=0.05)
        except asyncio.TimeoutError:
            await maybe_run_schedules(queue, store)
            continue
        task = store.get_task(task_id)
        if task and task.get("status") in {"queued", "running"}:
            await process_task(store, task)
        queue.task_done()


async def maybe_run_schedules(queue: asyncio.Queue[str], store: Store) -> None:
    now = utcnow()
    from datetime import datetime, timezone

    now_dt = datetime.now(timezone.utc)
    for schedule in store.list_schedules():
        if not schedule.get("enabled", True):
            continue
        interval = int(schedule.get("intervalSeconds") or 0)
        if interval <= 0:
            continue
        last = schedule.get("lastRunAt")
        due = True
        if last:
            try:
                last_dt = datetime.fromisoformat(last)
                due = (now_dt - last_dt).total_seconds() >= interval
            except ValueError:
                due = True
        if not due:
            continue
        task = {
            "id": new_id("tsk"),
            "prompt": schedule.get("prompt") or "",
            "workflowId": schedule.get("workflowId"),
            "templateId": schedule.get("templateId"),
            "webhookUrl": schedule.get("webhookUrl"),
            "status": "queued",
            "result": None,
            "tokensUsed": 0,
            "steps": [],
            "createdAt": now,
            "updatedAt": now,
            "scheduleId": schedule["id"],
        }
        store.upsert_task(task)
        store.update_schedule(schedule["id"], {"lastRunAt": now})
        await queue.put(task["id"])
