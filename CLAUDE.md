# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

A catastrophe risk-modeling platform for the **European (re)insurance market**. The product
wedge is **account-level underwriting decision support** — "what does binding this account do
to my accumulation?" answered in seconds — deliberately *not* regulatory-grade capital/PML
reporting (that's the incumbent Verisk/Moody's-RMS moat). Read `docs/PLAN.md` for the locked
strategic decisions before making architectural changes; they are load-bearing, not defaults.

## Commands

```bash
# Setup (engine + tests need only numpy; geo/api extras are optional layers)
python3 -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"          # engine + tests + ruff
pip install -e ".[dev,geo,api]"  # + rasterio/shapely (rasters) + fastapi/sqlalchemy (DB/API)

pytest                                             # all tests (no infra needed)
pytest tests/test_scenario_core.py                 # one file
pytest tests/test_scenario_core.py::test_marginal_impact_is_additive  # one test
pytest -q -k windstorm                             # by keyword

ruff check engine data backend                     # lint
python scripts/demo_scenario.py                    # end-to-end sanity anchor (see below)

uvicorn backend.app.main:app --reload              # API (needs [api] extra)
docker compose -f infra/docker-compose.yml up      # PostGIS
cd frontend && npm install && npm run dev          # UI (Vite, proxies /api -> :8000)
```

## Architecture: the two-speed design

Two compute paths share one exposure database:

- **Fast path** (`engine/`) — the interactive scenario core behind the wedge. Pure
  Python/numpy, no I/O.
- **Batch path** (later) — OASIS Platform / `ktools` for full probabilistic EP/AAL curves.

### The core abstraction that makes multi-peril tractable

Every peril reduces to the same pipeline: **sample a hazard footprint at each exposure
location → apply a vulnerability (damage) curve → apply financial terms → aggregate**. So
`engine/scenario/core.py` is entirely peril-agnostic, and each peril is a thin *adapter* in
`engine/perils/` that supplies only two things: a `Footprint` (implements `.sample(lons, lats)`,
returns intensity, 0.0 outside its extent) and one or more `Vulnerability` curves. When adding
a peril (roadmap: windstorm → flood → wildfire), you write an adapter — you do not touch the
core. `windstorm.py` is the reference adapter.

### Non-obvious invariants

- **Scenario loss is additive across locations**, which is *why* the underwriting wedge is
  cheap: `marginal_impact()` computes a new account's own loss instead of re-running the whole
  portfolio. Preserve additivity — don't introduce cross-location terms in the fast path
  without revisiting that function.
- **Missing vulnerability cohort fails loud** (`compute_scenario_loss` raises `KeyError`).
  This is deliberate: silently pricing an unmatched location at zero damage is a mispricing
  bug, not a warning. `Location.vuln_key` is the seam where construction/occupancy-specific
  curves plug in; v1 collapses everything to `"default"`.
- **The engine core depends only on numpy**, so `pytest` runs with zero infra. Raster loading
  (`GriddedFootprint.from_geotiff`) and the DB/API layer are behind the `[geo]`/`[api]` extras
  and deferred imports — keep it that way so the core stays fast and testable.

### Ingestion is the real work (`data/ingest/`)

`ingest_oed_locations()` turns raw **OED** (Open Exposure Data — the industry exposure
standard) rows into engine `Location`s plus an `IngestionReport` that classifies every problem
as ERROR (row unusable, skipped) or WARNING (usable but suspect) rather than dropping rows
silently. It operates on any iterable of dict rows (testable without a file). Real bordereaux
are dirty — this pipeline is shared across every peril and is itself a competitive advantage;
under-scoping it is how the schedule slips.

### Persistence (`backend/app/models/oed.py`)

Postgres schema mirrors the OED account/location hierarchy so portfolios round-trip losslessly;
`geom` is a PostGIS point for spatial accumulation queries. Multi-tenant (SaaS) — every
portfolio carries a `tenant_id`. Not yet wired to the API.

## The sanity anchor

`scripts/demo_scenario.py` is the end-to-end validation to keep green when changing the engine:
a Kyrill-like storm over a European portfolio must concentrate losses in the swath
(Cologne/Amsterdam highest) and produce ~zero at Madrid (far south of the track). If Madrid
shows loss or the swath doesn't dominate, the footprint sampling or vulnerability curve broke.

## Constraints to respect

- **SaaS-only deployment** keeps licensing simple. **OpenQuake is AGPLv3** — its §13 network
  clause triggers source disclosure for a hosted service; do not self-host it in the SaaS. Use
  OASIS-based earthquake models or GEM's commercial license if EQ is added. CLIMADA (GPLv3),
  Copernicus, and JRC data are fine server-side.
- Hazard rasters and client portfolios are **never committed** (`.gitignore`); `data/hazard`
  and `data/portfolios` hold only `.gitkeep`.

## Working principles

### 1. Think Before Coding
Don't assume. Don't hide confusion. Surface tradeoffs.

Before implementing:

- State your assumptions explicitly. If uncertain, ask.
- If multiple interpretations exist, present them - don't pick silently.
- If a simpler approach exists, say so. Push back when warranted.
- If something is unclear, stop. Name what's confusing. Ask.

### 2. Simplicity First
Minimum code that solves the problem. Nothing speculative.

- No features beyond what was asked.
- No abstractions for single-use code.
- No "flexibility" or "configurability" that wasn't requested.
- No error handling for impossible scenarios.
- If you write 200 lines and it could be 50, rewrite it.

Ask yourself: "Would a senior engineer say this is overcomplicated?" If yes, simplify.

### 3. Surgical Changes
Touch only what you must. Clean up only your own mess.

When editing existing code:

- Don't "improve" adjacent code, comments, or formatting.
- Don't refactor things that aren't broken.
- Match existing style, even if you'd do it differently.
- If you notice unrelated dead code, mention it - don't delete it.

When your changes create orphans:

- Remove imports/variables/functions that YOUR changes made unused.
- Don't remove pre-existing dead code unless asked.

The test: Every changed line should trace directly to the user's request.

### 4. Goal-Driven Execution
Define success criteria. Loop until verified.

Transform tasks into verifiable goals:

- "Add validation" → "Write tests for invalid inputs, then make them pass"
- "Fix the bug" → "Write a test that reproduces it, then make it pass"
- "Refactor X" → "Ensure tests pass before and after"

For multi-step tasks, state a brief plan:

1. [Step] → verify: [check]
2. [Step] → verify: [check]
3. [Step] → verify: [check]

Strong success criteria let you loop independently. Weak criteria ("make it work") require constant clarification.
