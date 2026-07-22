# Climate — European Multi-Peril Catastrophe Platform

Underwriting-first catastrophe risk platform for the European (re)insurance market.

The wedge: answer **"what does binding this account do to my accumulation?"** in seconds —
decision support for underwriters, not regulatory capital reporting.

## Architecture (two-speed)

```
React/TS UI ──> FastAPI ──> shared exposure DB (Postgres/PostGIS, OED schema)
                              │
             FAST PATH  ┌─────┴──────────────────────────────┐
             (seconds)  │ engine/ : footprint × exp × vuln    │  ← the wedge
                        │  peril adapters: windstorm|flood|fire│
             BATCH PATH └─ OASIS Platform (ktools) EP/AAL ─────┘  ← later
```

All perils reduce to: **sample a hazard footprint at each exposure location → apply a
vulnerability curve → apply financial terms → aggregate**. The engine is peril-agnostic;
each peril is a data adapter (`engine/perils/`).

## Layout

| Path | What |
|---|---|
| `engine/` | Peril-agnostic scenario core + peril adapters (pure Python/numpy) |
| `data/ingest/` | OED exposure ingestion: parse → validate → geocode → code-map → load |
| `backend/` | FastAPI: portfolios, ingestion, scenarios endpoints |
| `frontend/` | React + Vite + TypeScript UI (upload, accumulation map, what-if) |
| `infra/` | docker-compose (Postgres+PostGIS, backend, frontend) |
| `docs/` | `PLAN.md` — full plan and locked decisions |
| `tests/` | Engine + ingestion tests |

## Perils (built sequentially)

1. **Windstorm** — XWS catalogue + Copernicus C3S footprints. *The* European accumulation peril.
2. **Flood (fluvial)** — JRC European river flood hazard maps (100 m, RP 10→500 yr).
3. **Wildfire** — EFFIS (Copernicus) fire danger + risk index.

## Quick start (engine core)

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
pytest              # runs the scenario-engine tests (no infra needed)
```

See `docs/PLAN.md` for the full plan, licensing notes, and roadmap.
