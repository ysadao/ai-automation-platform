from __future__ import annotations

from tests.helpers import auth_header, register_user


def test_health_mock_provider(client) -> None:
    response = client.get("/api/health")
    assert response.status_code == 200
    body = response.json()
    assert body["ok"] is True
    assert body["provider"] == "mock-ink-1"
    assert body["openaiConfigured"] is False


def test_ready_and_request_id(client) -> None:
    ready = client.get("/api/ready")
    assert ready.status_code == 200
    assert ready.json()["status"] == "ready"
    health = client.get("/api/health", headers={"x-request-id": "ink-review-1"})
    assert health.headers["x-request-id"] == "ink-review-1"


def test_register_login_me(client) -> None:
    created = register_user(client)
    assert created["access_token"]
    assert created["refresh_token"]
    assert created["verification_token"]
    assert created["user"]["email_verified_at"] is None

    me = client.get("/api/me", headers=auth_header(created["access_token"]))
    assert me.status_code == 200
    assert me.json()["email"] == created["_email"]

    login = client.post(
        "/api/auth/login",
        json={"email": created["_email"], "password": created["_password"]},
    )
    assert login.status_code == 200
    assert login.json()["access_token"]


def test_verify_email(client) -> None:
    created = register_user(client)
    token = created["verification_token"]
    verified = client.post("/api/auth/verify-email", json={"token": token})
    assert verified.status_code == 200
    assert verified.json()["user"]["email_verified_at"] is not None

    again = client.post("/api/auth/verify-email", json={"token": token})
    assert again.status_code == 400


def test_forgot_and_reset_password(client) -> None:
    created = register_user(client)
    forgot = client.post("/api/auth/forgot-password", json={"email": created["_email"]})
    assert forgot.status_code == 200
    reset_token = forgot.json()["reset_token"]

    reset = client.post(
        "/api/auth/reset-password",
        json={"token": reset_token, "password": "NewPass123!"},
    )
    assert reset.status_code == 200

    old = client.post(
        "/api/auth/login",
        json={"email": created["_email"], "password": created["_password"]},
    )
    assert old.status_code == 401

    fresh = client.post(
        "/api/auth/login",
        json={"email": created["_email"], "password": "NewPass123!"},
    )
    assert fresh.status_code == 200

    stale = client.get("/api/me", headers=auth_header(created["access_token"]))
    assert stale.status_code == 401


def test_refresh_rotation(client) -> None:
    created = register_user(client)
    first = created["refresh_token"]
    rotated = client.post("/api/auth/refresh", json={"refresh_token": first})
    assert rotated.status_code == 200
    second = rotated.json()["refresh_token"]
    assert second != first

    reuse = client.post("/api/auth/refresh", json={"refresh_token": first})
    assert reuse.status_code == 401

    again = client.post("/api/auth/refresh", json={"refresh_token": second})
    assert again.status_code == 200


def test_logout_and_logout_all(client) -> None:
    created = register_user(client)
    login2 = client.post(
        "/api/auth/login",
        json={"email": created["_email"], "password": created["_password"]},
    )
    token_a = created["access_token"]
    token_b = login2.json()["access_token"]
    refresh_b = login2.json()["refresh_token"]

    logged = client.post(
        "/api/auth/logout",
        json={"refresh_token": refresh_b},
        headers=auth_header(token_b),
    )
    assert logged.status_code == 200
    assert client.get("/api/me", headers=auth_header(token_b)).status_code == 401
    assert client.get("/api/me", headers=auth_header(token_a)).status_code == 200

    all_out = client.post("/api/auth/logout-all", headers=auth_header(token_a))
    assert all_out.status_code == 200
    assert client.get("/api/me", headers=auth_header(token_a)).status_code == 401


def test_sessions_list_and_revoke(client) -> None:
    created = register_user(client)
    listed = client.get("/api/me/sessions", headers=auth_header(created["access_token"]))
    assert listed.status_code == 200
    items = listed.json()["items"]
    assert len(items) >= 1
    assert any(s["current"] for s in items)

    extra = client.post(
        "/api/auth/login",
        json={"email": created["_email"], "password": created["_password"]},
    )
    other_id = None
    sessions = client.get("/api/me/sessions", headers=auth_header(created["access_token"])).json()["items"]
    for row in sessions:
        if not row["current"]:
            other_id = row["id"]
            break
    assert other_id
    deleted = client.delete(f"/api/me/sessions/{other_id}", headers=auth_header(created["access_token"]))
    assert deleted.status_code == 204
    assert client.get("/api/me", headers=auth_header(extra.json()["access_token"])).status_code == 401


def test_demo_user_seeded(client) -> None:
    login = client.post(
        "/api/auth/login",
        json={"email": "demo@inkworks.app", "password": "InkDemo123!"},
    )
    assert login.status_code == 200
    user = login.json()["user"]
    assert user["email_verified_at"] is not None
    token = login.json()["access_token"]
    workflows = client.get("/api/workflows", headers=auth_header(token)).json()["items"]
    templates = client.get("/api/templates", headers=auth_header(token)).json()["items"]
    assert len(workflows) >= 1
    assert len(templates) >= 1
