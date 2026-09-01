# Architecture — INKWORKS automation desk

Portfolio notes for a user-scoped workflow runner with real Postgres and JWT sessions.

## Request path

```
Browser :3108
    │  SPA (Vite dist) served by FastAPI
    │  /api/* JSON
    ▼
FastAPI
    │  Bearer access JWT (15m) + opaque refresh (hashed)
    ▼
PostgreSQL  (users, sessions, templates, workflows, tasks, usage_events)
    │
asyncio.Queue
    │
worker_loop
    │
prompt_transform → Provider.complete → delay → webhook
    │
task.status = succeeded | failed
usage_events += tokens
```

## Auth

Access tokens are HS256 JWTs (`sub`, `sid`, `email`, `exp`). Refresh tokens are `secrets.token_urlsafe` values; only SHA-256 hashes are stored on `sessions`. Refresh **rotates**: the presented session is revoked and a new pair is issued.

Email verification and password reset tokens are also hashed. `DEMO_EXPOSE_TOKENS=true` returns the raw token in demo responses so the UI can complete the flow without mail.

Unverified accounts may sign in and read their data. `POST /api/tasks` requires `email_verified_at`.

## Provider protocol

`Provider` requires `complete(prompt) -> { text, tokensIn, tokensOut, model }`.

- `MockAIProvider` — default, deterministic, offline.
- `OpenAIProvider` — constructed only when `OPENAI_API_KEY` is set.

## Persistence

SQLAlchemy 2 with **asyncpg** (Postgres). Connection URLs of the form `postgresql://…` are rewritten to `postgresql+asyncpg://`.

| Table | Role |
| --- | --- |
| `users` | Email (unique), bcrypt hash, name, `email_verified_at` |
| `sessions` | Refresh hash, expiry, revoke, UA, IP |
| `email_verification_tokens` / `password_reset_tokens` | One-time hashed tokens |
| `prompt_templates` | User-owned `{{var}}` bodies |
| `workflows` | JSONB step graphs |
| `tasks` | Queue + result (`queued\|running\|succeeded\|failed`) |
| `usage_events` | Per-task token rows |

## Worker

Lifespan starts an asyncio consumer. Steps: `prompt_transform`, `ai_complete`, `delay` (capped by `DELAY_MAX_MS` so tests stay short), `webhook` (skipped when no URL).

## Frontend

React + Vite. Ink/amber desk: left rail wordmark, parchment result panel, template CRUD, workflow tiles, session revoke. Talks only to `/api`.
