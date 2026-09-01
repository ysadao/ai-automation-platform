from __future__ import annotations

from provider import MockAIProvider
from tests.helpers import auth_header, register_user, wait_for_task


def _verified(client) -> dict:
    created = register_user(client)
    client.post("/api/auth/verify-email", json={"token": created["verification_token"]})
    return created


def test_mock_provider_is_deterministic() -> None:
    provider = MockAIProvider()
    a = provider.complete("hello ink")
    b = provider.complete("hello ink")
    c = provider.complete("other")
    assert a["text"] == b["text"]
    assert a["digest"] == b["digest"]
    assert c["text"] != a["text"]


def test_unverified_blocked_from_tasks(client) -> None:
    created = register_user(client)
    headers = auth_header(created["access_token"])
    blocked = client.post("/api/tasks", json={"prompt": "night shift brief"}, headers=headers)
    assert blocked.status_code == 403
    assert blocked.json()["detail"] == "email_not_verified"

    client.post("/api/auth/verify-email", json={"token": created["verification_token"]})
    allowed = client.post("/api/tasks", json={"prompt": "night shift brief"}, headers=headers)
    assert allowed.status_code == 202


def test_create_task_mock_provider_succeeds(client) -> None:
    created = _verified(client)
    headers = auth_header(created["access_token"])
    queued = client.post("/api/tasks", json={"prompt": "Index the amber ledger"}, headers=headers)
    assert queued.status_code == 202
    task_id = queued.json()["id"]
    assert queued.json()["status"] == "queued"
    done = wait_for_task(client, created["access_token"], task_id)
    assert done["status"] == "succeeded"
    assert "mock-" in done["result"]
    assert done["tokens_used"] > 0

    listed = client.get("/api/tasks", headers=headers)
    assert any(t["id"] == task_id for t in listed.json()["items"])


def test_task_with_seeded_workflow(client) -> None:
    login = client.post(
        "/api/auth/login",
        json={"email": "demo@inkworks.app", "password": "InkDemo123!"},
    )
    token = login.json()["access_token"]
    headers = auth_header(token)
    workflows = client.get("/api/workflows", headers=headers).json()["items"]
    workflow_id = workflows[0]["id"]
    created = client.post(
        "/api/tasks",
        json={"prompt": "Ship the crate", "workflow_id": workflow_id},
        headers=headers,
    )
    done = wait_for_task(client, token, created.json()["id"])
    assert done["status"] == "succeeded"
    assert len(done["steps"]) >= 2


def test_template_crud(client) -> None:
    created = _verified(client)
    headers = auth_header(created["access_token"])
    made = client.post("/api/templates", json={"name": "echo", "body": "ECHO {{prompt}}"}, headers=headers)
    assert made.status_code == 201
    tpl_id = made.json()["id"]
    updated = client.put(f"/api/templates/{tpl_id}", json={"name": "echo-2"}, headers=headers)
    assert updated.json()["name"] == "echo-2"
    listed = client.get("/api/templates", headers=headers).json()["items"]
    assert any(t["id"] == tpl_id for t in listed)
    deleted = client.delete(f"/api/templates/{tpl_id}", headers=headers)
    assert deleted.status_code == 204


def test_usage_increments(client) -> None:
    created = _verified(client)
    headers = auth_header(created["access_token"])
    before = client.get("/api/usage", headers=headers).json()["total_tokens"]
    queued = client.post("/api/tasks", json={"prompt": "count tokens please"}, headers=headers)
    wait_for_task(client, created["access_token"], queued.json()["id"])
    after = client.get("/api/usage", headers=headers).json()
    assert after["total_tokens"] > before
    assert after["task_count"] >= 1


def test_user_isolation(client) -> None:
    a = _verified(client)
    b = _verified(client)
    created = client.post(
        "/api/tasks",
        json={"prompt": "secret amber crate"},
        headers=auth_header(a["access_token"]),
    )
    task_id = created.json()["id"]
    wait_for_task(client, a["access_token"], task_id)

    tpl = client.post(
        "/api/templates",
        json={"name": "private", "body": "{{prompt}}"},
        headers=auth_header(a["access_token"]),
    )
    tpl_id = tpl.json()["id"]

    other_task = client.get(f"/api/tasks/{task_id}", headers=auth_header(b["access_token"]))
    assert other_task.status_code == 404
    other_list = client.get("/api/tasks", headers=auth_header(b["access_token"])).json()["items"]
    assert all(t["id"] != task_id for t in other_list)
    other_tpl = client.get(f"/api/templates/{tpl_id}", headers=auth_header(b["access_token"]))
    assert other_tpl.status_code == 404


def test_unknown_workflow_404(client) -> None:
    created = _verified(client)
    response = client.post(
        "/api/tasks",
        json={"prompt": "x", "workflow_id": "00000000-0000-0000-0000-000000000001"},
        headers=auth_header(created["access_token"]),
    )
    assert response.status_code == 404


def test_tasks_require_auth(client) -> None:
    response = client.get("/api/tasks")
    assert response.status_code == 401
