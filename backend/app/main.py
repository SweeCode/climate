"""FastAPI entrypoint (skeleton).

Thin HTTP layer over the ingestion pipeline and scenario engine. Endpoints fill in as the
DB (Postgres/PostGIS, OED schema) and OASIS batch path come online; for now it exposes
health plus a stateless scenario run so the engine is reachable end-to-end.

Run: uvicorn backend.app.main:app --reload  (needs the `[api]` extra)
"""

from __future__ import annotations

from fastapi import FastAPI

app = FastAPI(title="Climate — European Cat Platform", version="0.0.1")


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


# TODO(phase 1-3): POST /portfolios (OED upload -> ingest -> store),
# GET /portfolios/{id}/accumulation, POST /portfolios/{id}/what-if (marginal impact).
