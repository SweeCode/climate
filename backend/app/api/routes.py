"""The underwriting wedge over HTTP.

Four things a prospect clicks through: list storms, upload a book, run a storm over it, and
ask what binding one more account does. Everything numeric comes from `engine.scenario.core`
and `data.ingest.oed_pipeline` unchanged — this module only moves data across the wire.
"""

from __future__ import annotations

import csv
import io
import os
import time

import numpy as np
from fastapi import APIRouter, Depends, File, Form, Header, HTTPException, UploadFile
from fastapi.responses import Response
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from backend.app.api.schemas import (
    LocationLossOut,
    LocationOut,
    PortfolioOut,
    ReportOut,
    ScenarioOut,
    ScenarioRequest,
    StormOut,
    WhatIfOut,
    WhatIfRequest,
)
from backend.app.config import settings
from backend.app.db import get_session
from backend.app.hazard import bounds, get_storm, render_png, to_footprint
from backend.app.models.oed import LocationRow, Portfolio, ScenarioRun, StormFootprint
from data.ingest.oed_pipeline import IngestionReport, ingest_oed_locations
from engine.perils import windstorm
from engine.scenario.core import (
    Exposure,
    Location,
    ScenarioResult,
    compute_scenario_loss,
    marginal_impact,
)

router = APIRouter(prefix="/api")

MAX_UPLOAD_BYTES = 25 * 1024 * 1024
SAMPLE_FILES = {"demo_book_oed.csv", "candidate_account_oed.csv"}


def require_access(x_access_code: str | None = Header(default=None)) -> None:
    """Gate the hosted demo behind a shared code.

    Not authentication — see the note on `Settings.demo_access_code`. An unset code means
    open, which is what local development wants.
    """
    if settings.demo_access_code and x_access_code != settings.demo_access_code:
        raise HTTPException(status_code=401, detail="Invalid or missing access code")


def tenant_id(x_tenant_id: str | None = Header(default=None)) -> str:
    """Per-browser tenant so two prospects on the same demo never see each other's uploads."""
    tid = (x_tenant_id or "demo").strip()[:64]
    return tid or "demo"


# ---------------------------------------------------------------------------------------
# Storm catalogue
# ---------------------------------------------------------------------------------------


# Gated: this is the frontend's first call, so it is where the access gate surfaces. The
# footprint PNG and the sample CSVs below stay open deliberately — deck.gl and plain <fetch>
# load them without our headers, and neither is sensitive.
@router.get("/storms", response_model=list[StormOut], dependencies=[Depends(require_access)])
def list_storms(session: Session = Depends(get_session)) -> list[StormOut]:
    storms = session.scalars(select(StormFootprint).order_by(StormFootprint.year.desc())).all()
    return [
        StormOut(
            slug=s.slug,
            name=s.name,
            year=s.year,
            event_date=s.event_date,
            notes=s.notes,
            bounds=bounds(s),
            source=s.source,
            licence=s.licence,
        )
        for s in storms
    ]


@router.get("/samples/{filename}")
def sample_file(filename: str) -> Response:
    """Serve the committed synthetic demo files.

    Whitelisted by name: this reads from disk by user-supplied path, and `data/` also holds
    the directory client portfolios would land in.
    """
    if filename not in SAMPLE_FILES:
        raise HTTPException(status_code=404, detail="Unknown sample")
    with open(os.path.join("data", "samples", filename), "rb") as fh:
        return Response(content=fh.read(), media_type="text/csv")


@router.get("/storms/{slug}/footprint.png")
def storm_footprint_png(slug: str, session: Session = Depends(get_session)) -> Response:
    storm = _require_storm(session, slug)
    return Response(
        content=render_png(storm),
        media_type="image/png",
        headers={"Cache-Control": "public, max-age=86400"},
    )


# ---------------------------------------------------------------------------------------
# Portfolios
# ---------------------------------------------------------------------------------------


@router.post("/portfolios", response_model=PortfolioOut, dependencies=[Depends(require_access)])
async def upload_portfolio(
    file: UploadFile = File(...),
    name: str = Form(default=""),
    session: Session = Depends(get_session),
    tenant: str = Depends(tenant_id),
) -> PortfolioOut:
    """Ingest an OED location CSV and store it. Returns the validation report with the book."""
    raw = await file.read()
    if len(raw) > MAX_UPLOAD_BYTES:
        raise HTTPException(status_code=413, detail="File exceeds 25 MB")

    locations, report = _ingest_csv_text(raw.decode("utf-8-sig", errors="replace"))
    if not locations:
        raise HTTPException(
            status_code=422,
            detail=f"No usable locations. {report.summary()}",
        )

    portfolio = Portfolio(
        name=name.strip() or (file.filename or "Untitled book"),
        tenant_id=tenant,
        ingestion_report=ReportOut.from_report(report).model_dump(),
    )
    portfolio.locations = [
        LocationRow(
            loc_number=loc.loc_id,
            geom=f"SRID=4326;POINT({loc.lon} {loc.lat})",
            # KNOWN GAP: the ingestion pipeline returns a summed TIV, so the building/contents/BI
            # split does not survive the round trip. The total — all the engine uses — is exact.
            # Restoring the split means widening `ingest_oed_locations`' return value; it matters
            # when coverage-specific terms or curves arrive, not before.
            building_tiv=loc.tiv,
            contents_tiv=0.0,
            bi_tiv=0.0,
            vuln_key=loc.vuln_key,
            loc_ded=loc.deductible,
            loc_limit=loc.limit,
        )
        for loc in locations
    ]
    session.add(portfolio)
    session.commit()

    return PortfolioOut(
        id=portfolio.id,
        name=portfolio.name,
        n_locations=len(locations),
        total_tiv=float(sum(loc.tiv for loc in locations)),
        report=ReportOut.from_report(report),
        locations=[
            LocationOut(loc_id=loc.loc_id, lon=loc.lon, lat=loc.lat, tiv=loc.tiv)
            for loc in locations
        ],
    )


@router.get("/portfolios/{portfolio_id}", response_model=PortfolioOut,
            dependencies=[Depends(require_access)])
def get_portfolio(
    portfolio_id: int,
    session: Session = Depends(get_session),
    tenant: str = Depends(tenant_id),
) -> PortfolioOut:
    portfolio = _require_portfolio(session, portfolio_id, tenant)
    locations = _load_locations(session, portfolio_id)
    return PortfolioOut(
        id=portfolio.id,
        name=portfolio.name,
        n_locations=len(locations),
        total_tiv=float(sum(loc.tiv for loc in locations)),
        report=ReportOut.model_validate(portfolio.ingestion_report or _empty_report()),
        locations=[
            LocationOut(loc_id=loc.loc_id, lon=loc.lon, lat=loc.lat, tiv=loc.tiv)
            for loc in locations
        ],
    )


# ---------------------------------------------------------------------------------------
# Scenario + the wedge
# ---------------------------------------------------------------------------------------


@router.post("/portfolios/{portfolio_id}/scenario", response_model=ScenarioOut,
             dependencies=[Depends(require_access)])
def run_scenario(
    portfolio_id: int,
    body: ScenarioRequest,
    session: Session = Depends(get_session),
    tenant: str = Depends(tenant_id),
) -> ScenarioOut:
    """Place a historical storm on the whole book."""
    _require_portfolio(session, portfolio_id, tenant)
    storm = _require_storm(session, body.storm_slug)
    locations = _load_locations(session, portfolio_id)
    if not locations:
        raise HTTPException(status_code=422, detail="Portfolio has no locations")

    footprint = to_footprint(storm)
    started = time.perf_counter()
    result = compute_scenario_loss(
        Exposure.from_locations(locations), footprint, windstorm.default_vulnerabilities()
    )
    compute_ms = (time.perf_counter() - started) * 1000

    # Persist the baseline the what-if measures against.
    session.execute(
        ScenarioRun.__table__.delete().where(
            (ScenarioRun.portfolio_id == portfolio_id)
            & (ScenarioRun.storm_slug == body.storm_slug)
        )
    )
    session.add(
        ScenarioRun(
            portfolio_id=portfolio_id,
            storm_slug=body.storm_slug,
            n_locations=len(locations),
            total_ground_up=result.total_ground_up,
            total_net=result.total_net,
        )
    )
    session.commit()

    return ScenarioOut(
        storm_slug=storm.slug,
        storm_name=storm.name,
        n_locations=len(locations),
        total_tiv=float(sum(loc.tiv for loc in locations)),
        total_ground_up=result.total_ground_up,
        total_net=result.total_net,
        locations=_loss_rows(locations, result),
        compute_ms=compute_ms,
    )


@router.post("/portfolios/{portfolio_id}/what-if", response_model=WhatIfOut,
             dependencies=[Depends(require_access)])
def what_if(
    portfolio_id: int,
    body: WhatIfRequest,
    session: Session = Depends(get_session),
    tenant: str = Depends(tenant_id),
) -> WhatIfOut:
    """What binding this account does to the accumulation.

    Reads the stored portfolio total rather than re-running the book — valid because scenario
    loss is additive across locations, which is the whole reason this is fast.
    """
    _require_portfolio(session, portfolio_id, tenant)
    storm = _require_storm(session, body.storm_slug)

    baseline = session.scalar(
        select(ScenarioRun)
        .where(ScenarioRun.portfolio_id == portfolio_id)
        .where(ScenarioRun.storm_slug == body.storm_slug)
    )
    if baseline is None:
        raise HTTPException(
            status_code=409,
            detail="Run the storm over the portfolio before asking for a marginal impact",
        )

    candidate_locs, report = _ingest_csv_text(body.csv_text)
    if not candidate_locs:
        raise HTTPException(status_code=422, detail=f"No usable locations. {report.summary()}")

    footprint = to_footprint(storm)
    vulns = windstorm.default_vulnerabilities()
    candidate_exposure = Exposure.from_locations(candidate_locs)

    started = time.perf_counter()
    # marginal_impact() is the canonical wedge computation and the guardian of the additivity
    # invariant, so the headline numbers come from it rather than being re-derived here. The
    # second pass supplies per-location detail for the map; on an account-sized exposure that
    # costs microseconds.
    impact = marginal_impact(_baseline_result(baseline), candidate_exposure, footprint, vulns)
    candidate_result = compute_scenario_loss(candidate_exposure, footprint, vulns)
    compute_ms = (time.perf_counter() - started) * 1000

    before = impact["portfolio_net_before"]
    return WhatIfOut(
        account_name=body.account_name,
        storm_slug=storm.slug,
        report=ReportOut.from_report(report),
        candidate_tiv=float(sum(loc.tiv for loc in candidate_locs)),
        delta_ground_up=impact["delta_ground_up"],
        delta_net=impact["delta_net"],
        portfolio_net_before=before,
        portfolio_net_after=impact["portfolio_net_after"],
        pct_increase=(impact["delta_net"] / before * 100.0) if before > 0 else 0.0,
        locations=_loss_rows(candidate_locs, candidate_result),
        compute_ms=compute_ms,
    )


# ---------------------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------------------


def _ingest_csv_text(text: str) -> tuple[list[Location], IngestionReport]:
    return ingest_oed_locations(csv.DictReader(io.StringIO(text)))


def _require_portfolio(session: Session, portfolio_id: int, tenant: str) -> Portfolio:
    portfolio = session.get(Portfolio, portfolio_id)
    # Same 404 for "missing" and "someone else's" — do not confirm existence across tenants.
    if portfolio is None or portfolio.tenant_id != tenant:
        raise HTTPException(status_code=404, detail="Portfolio not found")
    return portfolio


def _require_storm(session: Session, slug: str) -> StormFootprint:
    storm = get_storm(session, slug)
    if storm is None:
        raise HTTPException(status_code=404, detail=f"Unknown storm '{slug}'")
    return storm


def _load_locations(session: Session, portfolio_id: int) -> list[Location]:
    """Read stored rows back as engine Locations."""
    rows = session.execute(
        select(
            LocationRow.loc_number,
            func.ST_X(LocationRow.geom),
            func.ST_Y(LocationRow.geom),
            LocationRow.building_tiv + LocationRow.contents_tiv + LocationRow.bi_tiv,
            LocationRow.vuln_key,
            LocationRow.loc_ded,
            LocationRow.loc_limit,
        ).where(LocationRow.portfolio_id == portfolio_id)
    ).all()
    return [
        Location(
            loc_id=loc_number,
            lon=float(lon),
            lat=float(lat),
            tiv=float(tiv),
            vuln_key=vuln_key,
            deductible=float(ded or 0.0),
            limit=None if limit is None else float(limit),
        )
        for loc_number, lon, lat, tiv, vuln_key, ded, limit in rows
    ]


def _baseline_result(run: ScenarioRun) -> ScenarioResult:
    """Minimal ScenarioResult carrying only the totals `marginal_impact` reads."""
    empty = np.zeros(0, dtype=float)
    result = ScenarioResult(
        peril=windstorm.PERIL,
        loc_ids=[],
        intensities=empty,
        ground_up_loss=empty,
        net_loss=empty,
    )
    result.total_ground_up = run.total_ground_up
    result.total_net = run.total_net
    return result


def _loss_rows(locations: list[Location], result: ScenarioResult) -> list[LocationLossOut]:
    return [
        LocationLossOut(
            loc_id=loc.loc_id,
            lon=loc.lon,
            lat=loc.lat,
            tiv=loc.tiv,
            gust_ms=float(result.intensities[i]),
            ground_up=float(result.ground_up_loss[i]),
            net=float(result.net_loss[i]),
        )
        for i, loc in enumerate(locations)
    ]


def _empty_report() -> dict:
    return {"total_rows": 0, "loaded": 0, "n_errors": 0, "n_warnings": 0, "issues": []}
