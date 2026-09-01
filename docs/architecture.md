# Architecture — AI Automation Platform

Portfolio / reference notes for a small workflow engine plus an operator console.

## Request path

```
Vite :3108  --/api-->  FastAPI :4108
                          │
                     POST /tasks
                          │
                    JSON Store (data/*.json)
                          │
                    asyncio.Queue
                          │
                    worker_loop
                          │
          prompt_transform → MockAIProvider → delay → webhook
                          │
                    task.status = completed
                    usage.totalTokens += n
```

## MockAIProvider

`hashlib.sha256(prompt)` seeds a stable completion string and fake token counts (`len // 4`). Same prompt ⇒ same result. No network.

If `OPENAI_API_KEY` is present, `/health` reports `openaiConfigured: true` but the worker still uses the mock. A production port would branch in `get_provider()`.

## Persistence

`Store` is a typed JSON file layer:

| File | Contents |
| --- | --- |
| `tasks.json` | Queue + history |
| `workflows.json` | Step graphs |
| `templates.json` | `{{var}}` prompt templates |
| `schedules.json` | Interval jobs |
| `usage.json` | Simulated token totals |

## Scheduler

The worker poll (`~50ms`) checks due schedules (`now - lastRunAt >= intervalSeconds`) and enqueues tasks. This is a demo stand-in for Celery beat / cloud schedulers.

## Frontend

React + Vite. Distinctive ink/amber desk: left rail wordmark, parchment result panel, template and workflow tiles. Talks to the API only through the `/api` proxy.
