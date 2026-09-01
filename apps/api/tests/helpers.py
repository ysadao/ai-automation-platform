from __future__ import annotations

import time
import uuid

from fastapi.testclient import TestClient


def unique_email() -> str:
    return f"op-{uuid.uuid4().hex[:12]}@inkworks.app"


def auth_header(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def register_user(client: TestClient, **overrides) -> dict:
    payload = {
        "email": unique_email(),
        "password": "TestPass123!",
        "first_name": "Ada",
        "last_name": "Ink",
        **overrides,
    }
    response = client.post("/api/auth/register", json=payload)
    assert response.status_code == 201, response.text
    body = response.json()
    body["_password"] = payload["password"]
    body["_email"] = payload["email"]
    return body


def wait_for_task(client: TestClient, token: str, task_id: str, timeout: float = 12.0) -> dict:
    deadline = time.time() + timeout
    last = None
    while time.time() < deadline:
        response = client.get(f"/api/tasks/{task_id}", headers=auth_header(token))
        last = response.json()
        if response.status_code == 200 and last.get("status") in {"succeeded", "failed"}:
            return last
        time.sleep(0.08)
    raise AssertionError(f"task {task_id} did not finish: {last}")
