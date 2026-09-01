from __future__ import annotations

import json
import os
import re
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

DATA_FILES = {
    "tasks": "tasks.json",
    "workflows": "workflows.json",
    "templates": "templates.json",
    "schedules": "schedules.json",
    "usage": "usage.json",
}


def utcnow() -> str:
    return datetime.now(timezone.utc).isoformat()


def new_id(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex[:16]}"


def interpolate(template: str, data: dict[str, Any]) -> str:
    def repl(match: re.Match[str]) -> str:
        key = match.group(1)
        value = data.get(key, "")
        return "" if value is None else str(value)

    return re.sub(r"\{\{\s*([a-zA-Z0-9_]+)\s*\}\}", repl, template)


def default_workflows() -> list[dict[str, Any]]:
    return [
        {
            "id": "wf_draft",
            "name": "Draft and complete",
            "description": "Rewrite the prompt, then run the mock model.",
            "steps": [
                {
                    "type": "prompt_transform",
                    "template": "Rewrite the following as a concise operator brief:\n{{prompt}}",
                },
                {"type": "ai_complete", "model": "mock-ink-1"},
            ],
        },
        {
            "id": "wf_notify",
            "name": "Complete and webhook",
            "description": "Run the model, then POST the result if a webhook URL is present.",
            "steps": [
                {"type": "ai_complete", "model": "mock-ink-1"},
                {"type": "webhook", "url": ""},
            ],
        },
        {
            "id": "wf_delay",
            "name": "Delayed complete",
            "description": "Optional delay step (0ms in demo) then complete.",
            "steps": [
                {"type": "delay", "ms": 0},
                {"type": "ai_complete", "model": "mock-ink-1"},
            ],
        },
    ]


def default_templates() -> list[dict[str, Any]]:
    return [
        {
            "id": "tpl_summarize",
            "name": "summarize",
            "body": "Summarize in one paragraph:\n{{prompt}}",
            "createdAt": utcnow(),
        },
        {
            "id": "tpl_classify",
            "name": "classify",
            "body": "Classify the sentiment (positive, neutral, negative) of:\n{{prompt}}",
            "createdAt": utcnow(),
        },
    ]


class Store:
    """Typed JSON-file persistence for tasks, workflows, templates, schedules, usage."""

    def __init__(self, data_dir: str | None = None) -> None:
        self.data_dir = Path(data_dir or os.environ.get("DATA_DIR", "./data"))
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self._ensure("workflows", default_workflows())
        self._ensure("templates", default_templates())
        self._ensure("tasks", [])
        self._ensure("schedules", [])
        self._ensure_usage()

    def _path(self, name: str) -> Path:
        return self.data_dir / DATA_FILES[name]

    def _load(self, name: str) -> Any:
        path = self._path(name)
        if not path.exists():
            return []
        raw = path.read_text(encoding="utf-8") or "[]"
        return json.loads(raw)

    def _dump(self, name: str, payload: Any) -> None:
        self._path(name).write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")

    def _ensure(self, name: str, default: list[dict[str, Any]]) -> None:
        path = self._path(name)
        if not path.exists() or path.read_text(encoding="utf-8").strip() in ("", "[]"):
            self._dump(name, default)

    def _ensure_usage(self) -> None:
        path = self._path("usage")
        if not path.exists():
            self._dump("usage", {"totalTokens": 0, "taskCount": 0, "updatedAt": utcnow()})

    def list_tasks(self) -> list[dict[str, Any]]:
        items = self._load("tasks")
        return sorted(items, key=lambda t: t.get("createdAt", ""), reverse=True)

    def get_task(self, task_id: str) -> dict[str, Any] | None:
        return next((t for t in self._load("tasks") if t["id"] == task_id), None)

    def upsert_task(self, task: dict[str, Any]) -> dict[str, Any]:
        items = self._load("tasks")
        items = [t for t in items if t["id"] != task["id"]]
        items.append(task)
        self._dump("tasks", items)
        return task

    def list_workflows(self) -> list[dict[str, Any]]:
        return self._load("workflows")

    def get_workflow(self, workflow_id: str) -> dict[str, Any] | None:
        return next((w for w in self._load("workflows") if w["id"] == workflow_id), None)

    def insert_workflow(self, workflow: dict[str, Any]) -> dict[str, Any]:
        items = self._load("workflows")
        items.append(workflow)
        self._dump("workflows", items)
        return workflow

    def list_templates(self) -> list[dict[str, Any]]:
        return self._load("templates")

    def get_template(self, template_id: str) -> dict[str, Any] | None:
        return next((t for t in self._load("templates") if t["id"] == template_id), None)

    def insert_template(self, template: dict[str, Any]) -> dict[str, Any]:
        items = self._load("templates")
        items.append(template)
        self._dump("templates", items)
        return template

    def update_template(self, template_id: str, patch: dict[str, Any]) -> dict[str, Any] | None:
        items = self._load("templates")
        updated = None
        for i, item in enumerate(items):
            if item["id"] == template_id:
                items[i] = {**item, **patch, "id": template_id}
                updated = items[i]
                break
        if updated is None:
            return None
        self._dump("templates", items)
        return updated

    def delete_template(self, template_id: str) -> bool:
        items = self._load("templates")
        next_items = [t for t in items if t["id"] != template_id]
        if len(next_items) == len(items):
            return False
        self._dump("templates", next_items)
        return True

    def list_schedules(self) -> list[dict[str, Any]]:
        return self._load("schedules")

    def get_schedule(self, schedule_id: str) -> dict[str, Any] | None:
        return next((s for s in self._load("schedules") if s["id"] == schedule_id), None)

    def insert_schedule(self, schedule: dict[str, Any]) -> dict[str, Any]:
        items = self._load("schedules")
        items.append(schedule)
        self._dump("schedules", items)
        return schedule

    def update_schedule(self, schedule_id: str, patch: dict[str, Any]) -> dict[str, Any] | None:
        items = self._load("schedules")
        updated = None
        for i, item in enumerate(items):
            if item["id"] == schedule_id:
                items[i] = {**item, **patch, "id": schedule_id}
                updated = items[i]
                break
        if updated is None:
            return None
        self._dump("schedules", items)
        return updated

    def usage(self) -> dict[str, Any]:
        return self._load("usage")

    def add_usage(self, tokens: int) -> dict[str, Any]:
        current = self.usage()
        current["totalTokens"] = int(current.get("totalTokens", 0)) + tokens
        current["taskCount"] = int(current.get("taskCount", 0)) + 1
        current["updatedAt"] = utcnow()
        self._dump("usage", current)
        return current
