# AI Automation Platform

This is a **portfolio / reference implementation** demonstrating production patterns for an internal AI workflow runner: prompt templates, multi-step workflows, a background worker, simulated token usage, completion webhooks, and a small operator UI.

It does **not** call OpenAI (or any hosted model). Completions come from `MockAIProvider`, which is deterministic. `OPENAI_API_KEY` is reserved for a future provider swap. No git history is faked. The code is original.

## Layout

```
apps/api   FastAPI  ·  port 4108
apps/web   Vite + React  ·  port 3108  (proxies /api → 4108)
```

## Setup

### API

```bash
cd apps/api
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
set DATA_DIR=./data
python -m uvicorn main:app --host 127.0.0.1 --port 4108
```

macOS / Linux activation: `source .venv/bin/activate`.

### Web

```bash
cd apps/web
npm install
npm run dev
```

Open **http://127.0.0.1:3108**. The Vite dev server proxies `/api` to the API.

## What you can do

- `POST /tasks` `{ prompt, workflowId?, templateId?, webhookUrl? }`
- Workflows with steps: `prompt_transform`, `ai_complete`, `webhook`, `delay`
- Prompt template CRUD
- Scheduled tasks (`intervalSeconds`, demo cron-like polling)
- Usage counters (`GET /usage`)
- `GET /health`

## Tests

```bash
cd apps/api
python -m pytest
```

## Docker

```bash
docker compose up --build
```

API is published on 4108. The web service is a Node container running Vite for local compose demos.

## UI

The operator desk uses an **ink / amber** palette (not generic purple SaaS). Tasks, templates, and workflows are first-class screens.
