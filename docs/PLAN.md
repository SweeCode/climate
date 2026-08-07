# Plan: European Multi-Peril Catastrophe Platform — MVP (Underwriting Wedge)

## Context

Building a company: a catastrophe risk modeling platform for the European (re)insurance
market. Rather than compete with Verisk/Moody's-RMS on regulatory-grade portfolio
reporting (where the moat is decades of model validation, not UX), the wedge is
**account-level underwriting decision support** — answer "what does binding this account
do to my accumulation?" in seconds. That's advice, not a regulatory filing, so the
validation bar is low and the things a startup can actually win on — speed and UX —
are what matter.

This plan scopes the first buildable slice and the sequence after it.

**Status (August 2026):** phases 0–4 are built — engine, OED ingestion, the interactive API,
and the React/deck.gl UI, deployable as a single container, against a hosted Neon PostGIS
database. Phase 2 is closed: the real XWS recalibrated footprints for Kyrill, Lothar and Daria
are loaded, replacing the synthetic placeholders. See `docs/GTM.md` for the commercial plan the
demo now feeds. Open: deploy to a public URL, and the Copernicus 1.6 km footprints as the
documented resolution upgrade.

**The calibration anchor already paid for itself.** Checking the v1 windstorm curve against
Kyrill's ~€4.6bn insured market loss showed it was overstating damage by roughly 30–50x: it
saturated near total loss at extreme gusts, which windstorm never does. European vulnerability
decomposes as MDR = MDD × PAA (damage degree × *proportion of buildings affected*), and both
terms stay small — a severe 50 m/s gust means ~1.5% mean damage ratio, not 45%. The curve in
`engine/perils/windstorm.py` is corrected and the order of magnitude is now pinned by a test.
Loss levels remain indicative until fitted to real claims. This is exactly the failure mode
worth catching before a demo rather than during one.

**The same lesson repeated on geography.** The real XWS files turned out to name their
rotated-pole axes plainly `lat`/`lon`, so the converter's rotation check — which looked for
axes named `rlon`/`rlat` — read them as true coordinates and put Kyrill in the South Atlantic.
Nothing raised an error; the gust values stayed entirely plausible. Rotation is now identified
from CF metadata and the unrotation delegated to `pyproj` rather than hand-rolled trigonometry,
whose sign and 180° conventions are exactly where this class of bug lives. The check that
caught it is the one now built into the converter: a catalogued storm that produces no damaging
cell over Europe is a conversion failure, not a quiet event. The three loaded footprints
validate against the historical record independently — Kyrill peaks over the Randstad and the
Ruhr, Lothar over Baden-Württemberg and northern France, Daria over the British Isles and the
Low Countries, and all three leave Madrid alone.

### Decisions locked (from planning discussion)
- **Product:** single focus — European insurance/reinsurance cat platform. Not a consumer app.
- **Lead wedge:** interactive underwriting scenario tool. Portfolio dashboard and
  live-event response are later fall-outs of the same core, not separate builds.
- **Engine architecture:** two-speed. A custom low-latency scenario core for interactive
  "what-if"; the OASIS Platform (batch, `ktools`) behind it for full probabilistic EP/AAL.
- **Deployment:** SaaS-only, multi-tenant, for now. Keeps GPL/AGPL exposure minimal
  (server-side execution ≠ distribution). On-prem deferred.
- **Perils:** European **windstorm → flood → wildfire**, built sequentially (see note).
- **Stack:** Python/FastAPI + React/TypeScript + Postgres/PostGIS + deck.gl/MapLibre.

## The core insight driving the architecture

All three chosen perils reduce to the same computation: **sample a hazard footprint
raster at each exposure location → apply a peril-specific vulnerability (damage) curve →
apply financial terms → aggregate**. So the interactive engine is peril-agnostic; each
peril is a data adapter supplying (a) hazard footprint grids and (b) a damage function.
This is what makes multi-peril tractable for a small team, and it is the shared core
under all three product wedges.

```
                 ┌─────────────────────────────────────────┐
   React/TS UI ──┤ FastAPI  (auth, portfolios, scenarios)   │
   (deck.gl map) └───────────────┬─────────────────────────┘
                                 │ shared exposure DB (Postgres/PostGIS, OED)
              ┌──────────────────┴───────────────────┐
   FAST PATH  │ Scenario core (footprint × exp × vuln)│  ← seconds; the wedge
              │  peril adapters: windstorm|flood|fire │
              └──────────────────┬───────────────────┘
   BATCH PATH │ OASIS Platform (ktools) — probabilistic EP/AAL │ ← later, minutes
              └────────────────────────────────────────────────┘
```

## Data & models (all open, commercially usable)

| Peril | Hazard footprints | Vulnerability | License note |
|---|---|---|---|
| Windstorm | XWS catalogue (50 storms, free); Copernicus C3S Enhanced Windstorm Service (ERA5, downscaled ~1.6 km) | Published high-res European wind damage model (Nature 2020) as v1 curves | Copernicus: free/full/open |
| Flood (fluvial first) | JRC European river flood hazard maps, 100 m, RP 10→500 yr, v3 (2024) | Depth–damage curves (JRC global depth-damage functions) | "Without restriction on use/distribution" |
| Wildfire | EFFIS fire danger + wildfire risk index (Copernicus/GEFF) | EFFIS economic-vulnerability component; refine later | Copernicus: free/full/open |

Sources: oasislmf.org, europeanwindstorms.org, cds.climate.copernicus.eu,
data.jrc.ec.europa.eu (floods), forest-fire.emergency.copernicus.eu (EFFIS).

These give a working product now; the stated goal of **refining with proprietary models**
(better vulnerability curves, higher-res downscaling, own stochastic event sets) is a
later differentiation layer that plugs into the same adapter interface.

## Peril sequence

Recommend **windstorm → flood → wildfire** (note: this reorders the perils as listed —
windstorm first because it is *the* European accumulation peril: one storm hits NW Europe
simultaneously, which is exactly the accumulation story the wedge sells; it also has the
most mature open footprint catalogues and vulnerability functions). Trivial to reorder at
kickoff if you'd rather lead with wildfire — the engine is peril-agnostic, only the
adapter changes.

## Build phases (MVP = phases 0–4)

**Phase 0 — Scaffold.** Monorepo: `backend/` (FastAPI), `frontend/` (React+Vite+TS),
`engine/` (Python package: footprint scenario core), `data/` (ingestion pipelines),
`infra/` (docker-compose: Postgres+PostGIS, backend, frontend), `docs/`. Postgres schema
modeled on **OED** (Open Exposure Data) — the location + account tables.

**Phase 1 — OED ingestion (the real work; ~most of the schedule).** Parse OED location
files; validate; geocode (address → lat/lon); map construction/occupancy code schemes;
handle missing TIVs and bespoke client Excel. This pipeline is shared across every peril
and every future wedge, and "ingest your messy bordereaux without a 3-week onboarding" is
itself a selling point. Build a normalization + validation-report layer, not just a parser.

**Phase 2 — Windstorm scenario core (deterministic).** Load XWS/Copernicus gust footprints
as rasters (rasterio/xarray + PostGIS); sample gust at each exposure point; apply wind
damage curve → ground-up loss; apply financial module (site/policy deductible, limit);
aggregate. Deterministic "place storm X on this portfolio" run.

**Phase 3 — Interactive underwriting API (the wedge).** Precompute/cache portfolio
accumulation; on "add this account," compute the **marginal** accumulation impact fast
(reuse cached footprint samples). Target: sub-second for a single account against a held
portfolio. This is the demo that wins.

**Phase 4 — Frontend.** Portfolio upload + ingestion-report view; accumulation heatmap
(deck.gl/MapLibre); scenario picker; account "what-if" panel showing marginal PML/AAL delta
and where the exposure concentrates.

**Phase 5+ (post-MVP).** OASIS Platform integration (batch probabilistic EP/AAL, same
exposure DB) → flood adapter (JRC depth grids + depth-damage curves; fluvial, then
pluvial/coastal) → wildfire adapter (EFFIS) → portfolio dashboard (option 1) and
live-event response (option 3) as additions on the existing core.

## Files / structure to create (greenfield)

Nothing to modify — initial creation. Representative layout:
- `infra/docker-compose.yml` — Postgres+PostGIS, backend, frontend
- `backend/app/models/oed.py` — OED-aligned SQLAlchemy schema (location, account, policy)
- `backend/app/api/` — portfolios, ingestion, scenarios endpoints
- `data/ingest/oed_pipeline.py` — parse → validate → geocode → code-map → load
- `engine/scenario/core.py` — footprint × exposure × vulnerability + financial module
- `engine/perils/windstorm.py` — first peril adapter (hazard loader + damage curve)
- `frontend/src/` — upload, accumulation map, scenario/what-if panels

## Verification (end-to-end)

- **Unit:** footprint raster sampling; vulnerability curve monotonicity; financial module
  (deductible/limit) tested against known `ktools` outputs.
- **Ingestion:** load a synthetic OED portfolio spanning DE/FR/UK with deliberately dirty
  rows (missing geocodes, bad codes); assert the validation report flags them and clean
  rows load correctly.
- **Scenario E2E + sanity anchor:** run a historical footprint (e.g. Kyrill 2007, Lothar
  1999) on the synthetic portfolio; assert losses concentrate inside the storm swath and
  the aggregate is order-of-magnitude sane against the known market loss (Kyrill ≈ €4.5bn
  insured, scaled to the test portfolio's share). This is a real validation anchor, not
  just a smoke test.
- **Interactive:** measure marginal-impact latency on a realistic portfolio (target < 1s).
- **Batch (phase 5):** validate OASIS EP curve against a reference model output.

## Licensing (confirm with a lawyer — I am not one)
- **CLIMADA GPLv3:** benign for SaaS (no network clause; server-side execution isn't
  distribution). Would become a live concern only if you ever ship on-prem.
- **OpenQuake AGPLv3:** §13 network clause *does* trigger source-disclosure for a hosted
  service. If earthquake is added later, prefer OASIS-based EQ models or GEM's commercial
  license rather than self-hosting OpenQuake in the SaaS.
- Copernicus (windstorm, wildfire) and JRC flood maps are free/open and commercial-safe.

## Non-goals / risks to watch
- **Not** regulatory-grade capital/Solvency-II reporting in the MVP — that's the incumbent
  moat; avoid it until validated.
- Correlation/accumulation is the whole point — do not model policies as independent.
- Ingestion data quality (geocoding, code mapping) dominates accuracy; under-scoping it is
  the classic way this schedule slips.
