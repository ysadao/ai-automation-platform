from __future__ import annotations

import os
import time

import pytest
from fastapi.testclient import TestClient

from provider import MockAIProvider


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("DATA_DIR", str(tmp_path))
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    from main import app

    with TestClient(app) as test_client:
        yield test_client


def wait_for_task(client: TestClient, task_id: str, timeout: float = 5.0) -> dict:
    deadline = time.time() + timeout
    last = None
    while time.time() < deadline:
        response = client.get(f"/tasks/{task_id}")
        last = response.json()
        if last.get("status") in {"completed", "failed"}:
            return last
        time.sleep(0.05)
    raise AssertionError(f"task {task_id} did not finish: {last}")


def test_health(client: TestClient) -> None:
    response = client.get("/health")
    assert response.status_code == 200
    body = response.json()
    assert body["ok"] is True
    assert body["provider"] == "mock-ink-1"
    assert body["openaiConfigured"] is False


def test_mock_provider_is_deterministic() -> None:
    provider = MockAIProvider()
    a = provider.complete("hello ink")
    b = provider.complete("hello ink")
    c = provider.complete("other")
    assert a["text"] == b["text"]
    assert a["digest"] == b["digest"]
    assert c["text"] != a["text"]


def test_create_task_completes(client: TestClient) -> None:
    created = client.post("/tasks", json={"prompt": "Index the amber ledger"})
    assert created.status_code == 202
    task_id = created.json()["id"]
    done = wait_for_task(client, task_id)
    assert done["status"] == "completed"
    assert "mock-" in done["result"]
    assert done["tokensUsed"] > 0

    listed = client.get("/tasks")
    assert any(t["id"] == task_id for t in listed.json()["items"])


def test_workflow_and_template(client: TestClient) -> None:
    workflows = client.get("/workflows").json()["items"]
    assert {w["id"] for w in workflows} >= {"wf_draft", "wf_notify"}

    created = client.post(
        "/tasks",
        json={"prompt": "Ship the crate", "workflowId": "wf_draft"},
    )
    done = wait_for_task(client, created.json()["id"])
    assert done["status"] == "completed"
    assert len(done["steps"]) >= 2

    templates = client.get("/templates").json()["items"]
    assert len(templates) >= 2
    new_tpl = client.post("/templates", json={"name": "echo", "body": "ECHO {{prompt}}"})
    assert new_tpl.status_code == 201
    tpl_id = new_tpl.json()["id"]
    updated = client.put(f"/templates/{tpl_id}", json={"name": "echo-2"})
    assert updated.json()["name"] == "echo-2"
    deleted = client.delete(f"/templates/{tpl_id}")
    assert deleted.status_code == 204


def test_usage_increments(client: TestClient) -> None:
    before = client.get("/usage").json()["totalTokens"]
    created = client.post("/tasks", json={"prompt": "count tokens please"})
    wait_for_task(client, created.json()["id"])
    after = client.get("/usage").json()
    assert after["totalTokens"] > before
    assert after["taskCount"] >= 1


def test_schedule_create(client: TestClient) -> None:
    created = client.post(
        "/schedules",
        json={"prompt": "tick", "intervalSeconds": 60, "enabled": True},
    )
    assert created.status_code == 201
    listed = client.get("/schedules").json()["items"]
    assert listed[0]["intervalSeconds"] == 60


def test_unknown_workflow_404(client: TestClient) -> None:
    response = client.post("/tasks", json={"prompt": "x", "workflowId": "missing"})
    assert response.status_code == 404
