# AI Automation Platform (INKWORKS)

Portfolio / reference implementation of an **operator desk** for prompt templates, multi-step workflows, and a background worker. Completions default to a deterministic `MockAIProvider` (no paid API). Persistence is **PostgreSQL**. The FastAPI process serves the Vite SPA on **port 3108**.

`GET /api/ready` pings Postgres. `GET /docs` is FastAPI OpenAPI. Responses include `x-request-id`. This demonstrates workflow/auth patterns; it is not a production LLM platform.

No git history is faked. The code is original.

## Demo login

| | |
| --- | --- |
| Email | `demo@inkworks.app` |
| Password | `InkDemo123!` |

The demo user is seeded **verified**, with a default workflow and prompt templates.

## Layout

```
apps/api    FastAPI + SQLAlchemy 2 + asyncpg
apps/web    Vite + React (ink / amber INKWORKS desk)
Dockerfile  multi-stage: build web, copy dist → /app/static
```

## PostgreSQL

Local / tests:

```
DATABASE_URL=postgresql://app:app@127.0.0.1:55434/inkworks
```

Start the database (container name `ai-pg`):

```bash
docker compose up -d postgres
```

If Postgres is not ready yet, the API waits and retries on startup.

## Setup (local)

```bash
# API
cd apps/api
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
set DATABASE_URL=postgresql://app:app@127.0.0.1:55434/inkworks
set DEMO_EXPOSE_TOKENS=true
python -m uvicorn main:app --host 127.0.0.1 --port 3108

# Web (optional HMR; production is served by the API)
cd apps/web
npm install
npm run build
```

Open **http://127.0.0.1:3108**. After `npm run build`, FastAPI serves `apps/web/dist`. During UI development, `npm run dev` (Vite :5173) proxies `/api` to :3108.

## Auth

JWT **access** tokens expire in 15 minutes. **Refresh** tokens are opaque, stored as SHA-256 hashes, and rotate on each use.

| Method | Path |
| --- | --- |
| POST | `/api/auth/register` |
| POST | `/api/auth/login` |
| POST | `/api/auth/refresh` |
| POST | `/api/auth/logout` |
| POST | `/api/auth/logout-all` |
| POST | `/api/auth/verify-email` |
| POST | `/api/auth/forgot-password` |
| POST | `/api/auth/reset-password` |
| GET | `/api/me` |
| GET | `/api/me/sessions` |
| DELETE | `/api/me/sessions/{id}` |

Unverified users receive **403** `email_not_verified` when creating tasks. Task, template, and workflow routes require `Authorization: Bearer` and are **user-scoped**.

When `DEMO_EXPOSE_TOKENS=true`, register and forgot-password echo verification / reset tokens in JSON (local demo only).

## Mock vs OpenAI

`MockAIProvider` is the default: `sha256(prompt)` seeds a stable completion and fake token counts. Same prompt ⇒ same result. No network.

If `OPENAI_API_KEY` is set, `get_provider()` returns `OpenAIProvider` and **will** call OpenAI chat completions. Leave the key unset for demos and tests.

## Tests

Pytest talks to the **real** Postgres on `55434`.

```bash
cd apps/api
python -m pytest
```

```bash
cd apps/web
npm test          # tsc --noEmit
npm run build
```

## Docker

```bash
docker compose up --build
```

Postgres is published on **55434**. The API serves `/api` and the built UI on **3108**.

## Environment

| Variable | Default | Purpose |
| --- | --- | --- |
| `DATABASE_URL` | `postgresql://app:app@127.0.0.1:55434/inkworks` | SQLAlchemy / psycopg |
| `PORT` | `3108` | Listen port |
| `JWT_ACCESS_SECRET` | demo secret | Access JWT HMAC |
| `DEMO_EXPOSE_TOKENS` | `true` | Echo verify/reset tokens |
| `BCRYPT_ROUNDS` | `10` | Passlib bcrypt cost (`4` in tests) |
| `OPENAI_API_KEY` | unset | Switches provider off mock |
| `STATIC_DIR` | `apps/web/dist` or `/app/static` | SPA files |
| `DELAY_MAX_MS` | `5000` | Cap workflow delay steps |

## License

MIT
