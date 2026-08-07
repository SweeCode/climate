"""FastAPI entrypoint.

Serves the underwriting API under /api and, when a built React bundle is present, the SPA
itself from the same origin. One service, one URL, no CORS — which is also the cheapest
thing to deploy on a free tier.

Run: uvicorn backend.app.main:app --reload  (needs the `[api]` extra)
"""

from __future__ import annotations

import logging
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from backend.app.api.routes import router as api_router
from backend.app.config import settings

log = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    from backend.app.db import init_db

    try:
        init_db()
    except Exception:  # noqa: BLE001 - the app must still serve /health for the platform probe
        log.exception("Database init failed; API endpoints will error until the DB is reachable")
    yield


app = FastAPI(title="Climate — European Cat Platform", version="0.1.0", lifespan=lifespan)
app.include_router(api_router)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


def _mount_frontend() -> None:
    """Serve the built SPA if it exists. Absent in dev, where Vite proxies /api instead."""
    dist = settings.frontend_dist
    index = os.path.join(dist, "index.html")
    if not os.path.isfile(index):
        return

    app.mount("/assets", StaticFiles(directory=os.path.join(dist, "assets")), name="assets")

    root = os.path.realpath(dist)

    @app.get("/{path:path}", include_in_schema=False)
    def spa(path: str) -> FileResponse:
        # Client-side routing: every non-API path resolves to the app shell.
        # Resolve before serving — `path` is user-supplied and may contain traversal segments,
        # and this process's working directory also holds portfolios and hazard data.
        candidate = os.path.realpath(os.path.join(dist, path))
        inside = candidate == root or candidate.startswith(root + os.sep)
        if path and inside and os.path.isfile(candidate):
            return FileResponse(candidate)
        return FileResponse(index)


_mount_frontend()
