"""End-to-end API tests. Skipped unless a PostGIS database is available.

The engine and ingestion suites deliberately need no infrastructure; this one does, because
the things worth testing here are exactly the things that only break against a real database
— PostGIS geometry round-tripping, JSONB report storage, tenant isolation.

Point it at a scratch database (a Neon branch is ideal — free, and disposable):

    CLIMATE_TEST_DATABASE_URL=postgresql://... pytest tests/test_api.py
"""

from __future__ import annotations

import os

import numpy as np
import pytest

TEST_DB = os.environ.get("CLIMATE_TEST_DATABASE_URL")

pytestmark = pytest.mark.skipif(
    not TEST_DB, reason="set CLIMATE_TEST_DATABASE_URL to run API tests"
)

BOOK = "data/samples/demo_book_oed.csv"
ACCOUNT = "data/samples/candidate_account_oed.csv"
STORM = "test-storm"


@pytest.fixture(scope="module")
def client():
    # Settings are read at import time, so the env var must be set before the app loads.
    os.environ["CLIMATE_DATABASE_URL"] = TEST_DB
    os.environ["CLIMATE_DEMO_ACCESS_CODE"] = ""

    from fastapi.testclient import TestClient
    from sqlalchemy import select

    from backend.app.db import SessionLocal, init_db
    from backend.app.hazard import get_storm, upsert_storm
    from backend.app.main import app
    from backend.app.models.oed import Portfolio, ScenarioRun

    init_db()

    # A blunt uniform footprint over NW Europe: every location north of ~48N sees 45 m/s and
    # everything else sees nothing, which makes the expected losses easy to reason about.
    grid = np.zeros((60, 120), dtype=np.float32)
    grid[:55, :] = 45.0
    with SessionLocal() as session:
        upsert_storm(
            session,
            slug=STORM,
            name="Test storm",
            year=2000,
            grid=grid,
            lon_left=-15.0,
            lat_top=60.0,
            cell_deg=0.22,
            source="synthetic test fixture",
            licence="n/a",
        )
        session.commit()

    with TestClient(app) as c:
        yield c

    # Clean up after ourselves: this may well be pointed at a development database, and a
    # leftover "Test storm" showing up in the demo's storm picker is exactly the kind of
    # confusion that wastes ten minutes later.
    with SessionLocal() as session:
        storm = get_storm(session, STORM)
        if storm is not None:
            session.delete(storm)
        for portfolio in session.scalars(
            select(Portfolio).where(Portfolio.tenant_id.in_(["t-alpha", "t-bravo"]))
        ).all():
            session.execute(
                ScenarioRun.__table__.delete().where(ScenarioRun.portfolio_id == portfolio.id)
            )
            session.delete(portfolio)
        session.commit()


def _upload(client, tenant: str = "t-alpha", path: str = BOOK):
    with open(path, "rb") as fh:
        return client.post(
            "/api/portfolios",
            files={"file": ("book.csv", fh, "text/csv")},
            data={"name": "Test book"},
            headers={"X-Tenant-Id": tenant},
        )


def test_storm_catalogue_and_footprint_png(client):
    storms = client.get("/api/storms").json()
    assert any(s["slug"] == STORM for s in storms)

    png = client.get(f"/api/storms/{STORM}/footprint.png")
    assert png.status_code == 200
    assert png.headers["content-type"] == "image/png"
    assert png.content[:8] == b"\x89PNG\r\n\x1a\n"


def test_upload_reports_dirty_rows_rather_than_dropping_them(client):
    body = _upload(client).json()

    assert body["n_locations"] == body["report"]["loaded"]
    assert body["report"]["total_rows"] == 500
    # The sample book is seeded with known defects; silently loading all 500 would mean the
    # validation layer had stopped working.
    assert body["report"]["n_errors"] > 0
    assert body["report"]["n_warnings"] > 0
    assert body["report"]["loaded"] < body["report"]["total_rows"]
    assert body["total_tiv"] > 0


def test_scenario_loss_lands_only_inside_the_footprint(client):
    portfolio = _upload(client).json()
    result = client.post(
        f"/api/portfolios/{portfolio['id']}/scenario",
        json={"storm_slug": STORM},
        headers={"X-Tenant-Id": "t-alpha"},
    ).json()

    assert result["total_net"] > 0
    assert result["total_ground_up"] >= result["total_net"]

    # The fixture footprint stops at ~48N, so Madrid (40.4N) must be untouched. This is the
    # geometry round-trip check: if lon/lat were swapped on the way into PostGIS, it fails.
    southern = [loc for loc in result["locations"] if loc["lat"] < 44.0]
    assert southern, "sample book should contain southern European locations"
    assert all(loc["net"] == 0.0 for loc in southern)


def test_what_if_is_additive_on_top_of_the_stored_baseline(client):
    portfolio = _upload(client).json()
    headers = {"X-Tenant-Id": "t-alpha"}
    scenario = client.post(
        f"/api/portfolios/{portfolio['id']}/scenario",
        json={"storm_slug": STORM},
        headers=headers,
    ).json()

    with open(ACCOUNT, encoding="utf-8") as fh:
        csv_text = fh.read()

    impact = client.post(
        f"/api/portfolios/{portfolio['id']}/what-if",
        json={"storm_slug": STORM, "csv_text": csv_text, "account_name": "Newco"},
        headers=headers,
    ).json()

    assert impact["delta_net"] > 0
    assert impact["portfolio_net_before"] == pytest.approx(scenario["total_net"])
    # The whole economic claim of the wedge: after == before + the account's own loss.
    assert impact["portfolio_net_after"] == pytest.approx(
        impact["portfolio_net_before"] + impact["delta_net"]
    )


def test_what_if_refuses_without_a_baseline(client):
    portfolio = _upload(client).json()
    res = client.post(
        f"/api/portfolios/{portfolio['id']}/what-if",
        json={"storm_slug": STORM, "csv_text": "LocNumber,Latitude\n1,50"},
        headers={"X-Tenant-Id": "t-alpha"},
    )
    assert res.status_code == 409


def test_a_tenant_cannot_read_another_tenants_book(client):
    portfolio = _upload(client, tenant="t-alpha").json()
    res = client.get(
        f"/api/portfolios/{portfolio['id']}", headers={"X-Tenant-Id": "t-bravo"}
    )
    assert res.status_code == 404


def test_upload_rejects_a_file_with_no_usable_rows(client):
    res = client.post(
        "/api/portfolios",
        files={"file": ("junk.csv", b"LocNumber,Latitude\nL1,\nL2,\n", "text/csv")},
        headers={"X-Tenant-Id": "t-alpha"},
    )
    assert res.status_code == 422
