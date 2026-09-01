from __future__ import annotations

import asyncio
import os
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from config import get_settings
from database import init_db, wait_for_db
from provider import get_provider
from routers import auth, tasks, templates, usage, workflows
from seed import ensure_demo_user
from worker import worker_loop


@asynccontextmanager
async def lifespan(app: FastAPI):
    await wait_for_db()
    await init_db()
    await ensure_demo_user()
    app.state.queue = asyncio.Queue()
    app.state.stop = asyncio.Event()
    worker = asyncio.create_task(worker_loop(app.state.queue, app.state.stop))
    yield
    app.state.stop.set()
    worker.cancel()
    try:
        await worker
    except asyncio.CancelledError:
        pass


app = FastAPI(title="INKWORKS Automation", version="2.0.0", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://127.0.0.1:3108",
        "http://localhost:3108",
        "http://127.0.0.1:5173",
        "http://localhost:5173",
    ],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router)
app.include_router(tasks.router)
app.include_router(templates.router)
app.include_router(workflows.router)
app.include_router(usage.router)


@app.get("/api/health")
def health() -> dict[str, Any]:
    provider = get_provider()
    return {
        "ok": True,
        "service": "ai-automation-platform",
        "provider": provider.model,
        "openaiConfigured": bool(os.environ.get("OPENAI_API_KEY")),
    }


def _static_dir() -> Path:
    settings = get_settings()
    if settings.static_dir:
        return Path(settings.static_dir)
    docker = Path("/app/static")
    if docker.exists():
        return docker
    return Path(__file__).resolve().parent.parent / "web" / "dist"


_STATIC = _static_dir()
_ASSETS = _STATIC / "assets"
if _ASSETS.is_dir():
    app.mount("/assets", StaticFiles(directory=_ASSETS), name="assets")


@app.get("/{full_path:path}")
def spa(full_path: str):
    if full_path.startswith("api/") or full_path == "api":
        raise HTTPException(status_code=404, detail="not_found")
    if not _STATIC.is_dir():
        raise HTTPException(status_code=404, detail="ui_not_built")
    candidate = _STATIC / full_path
    if full_path and candidate.is_file():
        return FileResponse(candidate)
    index = _STATIC / "index.html"
    if index.is_file():
        return FileResponse(index)
    raise HTTPException(status_code=404, detail="ui_not_built")
