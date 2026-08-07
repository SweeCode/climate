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
| `scripts/` | Sample-data generator, hazard loaders, the demo sanity anchor |
| `docs/` | `PLAN.md` — plan and locked decisions · `GTM.md` — ICP, pricing, demo script |
| `tests/` | Engine, ingestion, and interactive-latency tests |

## Perils (built sequentially)

1. **Windstorm** — XWS catalogue + Copernicus C3S footprints. *The* European accumulation peril.
2. **Flood (fluvial)** — JRC European river flood hazard maps (100 m, RP 10→500 yr).
3. **Wildfire** — EFFIS (Copernicus) fire danger + risk index.

## Quick start (engine core — no infra)

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
pytest                              # engine, ingestion, latency
python scripts/demo_scenario.py     # end-to-end sanity anchor
```

## Running the full demo

Needs a Postgres with PostGIS. Hosted, the free tier at [neon.tech](https://neon.tech) works,
does not expire, and needs no card. Locally, either `infra/docker-compose.yml`, or without
Docker:

```bash
brew install postgresql@17 postgis   # postgis builds against 17/18, not 16
export PGBIN=/opt/homebrew/opt/postgresql@17/bin PGDATA=/tmp/climate-pg
$PGBIN/initdb -D "$PGDATA" -U climate --auth=trust
$PGBIN/pg_ctl -D "$PGDATA" -o "-p 55432 -k /tmp" -l "$PGDATA/server.log" start
$PGBIN/createdb -h 127.0.0.1 -p 55432 -U climate climate
```


```bash
pip install -e ".[dev,api]"
export CLIMATE_DATABASE_URL="postgresql://...."      # Neon, or the local compose DB

python scripts/make_sample_portfolio.py              # synthetic book + candidate account
python scripts/seed_placeholder_storms.py            # placeholder footprints (see below)
uvicorn backend.app.main:app --reload                # API on :8000

cd frontend && npm install && npm run dev            # UI on :5173, proxies /api
```

### Hazard data

Real footprints come from the [XWS catalogue](https://www.europeanwindstorms.org/) — 50
extreme European windstorms, CC BY 4.0, commercial use permitted with attribution. The
repository is an open directory, so no registration is needed:

```bash
pip install -e ".[geo]"
cd data/hazard
for s in Kyrill Lothar Daria; do
    curl -O "https://www.europeanwindstorms.org/repository/$s/${s}_biasMean.nc"
done
cd ../..

python scripts/prepare_xws_footprints.py data/hazard/Kyrill_biasMean.nc \
    --slug kyrill-2007 --name Kyrill --year 2007 --date 2007-01-18
```

Take the `_biasMean` product — the footprint recalibrated against station observations.
`_rawFoot` is the direct 25 km model output, which cannot resolve peak gusts: it maxes out at
32–40 m/s where the recalibrated field reaches 51–77, so it understates every loss on the
book.

XWS footprints sit on a rotated-pole grid, and the axes are named plainly `lat`/`lon` despite
being rotated — the converter identifies the rotation from CF metadata and delegates the
unrotation to `pyproj`, offline, so the runtime sampler stays a regular-grid lookup. It
refuses to load a footprint with no damaging cell in the European domain, which is what a
misread projection produces.

`scripts/seed_placeholder_storms.py` seeds **synthetic** track-shaped footprints instead, for
running the app before any download. They are labelled as placeholders in the database and
that label renders in the UI — never present them as modelled footprints.

## Deploying

One Docker image serves the API and the built UI from the same origin. `render.yaml` is a
ready blueprint for Render's free tier; set `CLIMATE_DATABASE_URL` and
`CLIMATE_DEMO_ACCESS_CODE` in the dashboard.

---

See `docs/PLAN.md` for the technical plan and licensing notes, and `docs/GTM.md` for who this
is sold to, at what price, and the demo script.
