"""Latency budget for the interactive path.

`docs/PLAN.md` states a sub-second target for marginal impact on a realistic portfolio. That
claim gets made on sales calls, so it is checked here rather than asserted.

Two different numbers, and the difference between them is the whole architecture:

  * A full book run scales with portfolio size — it samples the footprint at every location.
  * A marginal impact does NOT, because scenario loss is additive across locations, so adding
    an account costs only that account's own locations regardless of how big the book is.

Thresholds are deliberately loose (CI machines are slow and shared); they are regression
guards against an accidental Python-level loop creeping into the fast path, not benchmarks.
"""

from __future__ import annotations

import time

import numpy as np
import pytest

from engine.perils.windstorm import GriddedFootprint, default_vulnerabilities
from engine.scenario.core import Exposure, Location, compute_scenario_loss, marginal_impact

BOOK_SIZE = 100_000
ACCOUNT_SIZE = 25


def _footprint() -> GriddedFootprint:
    """A Europe-sized grid at roughly XWS resolution (~0.22 deg)."""
    rng = np.random.default_rng(1)
    grid = rng.uniform(15.0, 45.0, size=(170, 230))
    return GriddedFootprint(grid=grid, lon_left=-15.0, lat_top=72.0, cell_deg=0.22)


def _exposure(n: int, seed: int) -> Exposure:
    rng = np.random.default_rng(seed)
    lons = rng.uniform(-10.0, 25.0, size=n)
    lats = rng.uniform(43.0, 60.0, size=n)
    tivs = np.exp(rng.normal(14.5, 1.0, size=n))
    return Exposure.from_locations(
        [
            Location(loc_id=f"L{i}", lon=float(lons[i]), lat=float(lats[i]), tiv=float(tivs[i]))
            for i in range(n)
        ]
    )


@pytest.fixture(scope="module")
def scenario_inputs():
    footprint = _footprint()
    vulns = default_vulnerabilities()
    book = _exposure(BOOK_SIZE, seed=42)
    return footprint, vulns, book


def test_full_book_run_is_interactive(scenario_inputs):
    """A 100k-location book under one storm, fast enough to feel immediate."""
    footprint, vulns, book = scenario_inputs

    started = time.perf_counter()
    result = compute_scenario_loss(book, footprint, vulns)
    elapsed = time.perf_counter() - started

    assert result.total_net > 0
    assert elapsed < 1.0, f"full book run took {elapsed * 1000:.0f} ms for {BOOK_SIZE} locations"


def test_marginal_impact_is_subsecond_against_a_large_book(scenario_inputs):
    """The wedge: binding one account against a 100k-location book, in well under a second."""
    footprint, vulns, book = scenario_inputs
    portfolio_result = compute_scenario_loss(book, footprint, vulns)
    candidate = _exposure(ACCOUNT_SIZE, seed=7)

    started = time.perf_counter()
    impact = marginal_impact(portfolio_result, candidate, footprint, vulns)
    elapsed = time.perf_counter() - started

    assert impact["delta_net"] > 0
    assert impact["portfolio_net_after"] > impact["portfolio_net_before"]
    assert elapsed < 1.0, f"marginal impact took {elapsed * 1000:.1f} ms"


def test_marginal_cost_does_not_grow_with_book_size(scenario_inputs):
    """Additivity, measured: a 40x bigger book must not make binding an account slower.

    If this fails, someone has introduced a cross-location term into the fast path and the
    economics of the whole wedge have changed — see the invariant note in CLAUDE.md.
    """
    footprint, vulns, big_book = scenario_inputs
    small_book = _exposure(2_500, seed=43)
    candidate = _exposure(ACCOUNT_SIZE, seed=7)

    def timed(book: Exposure) -> float:
        result = compute_scenario_loss(book, footprint, vulns)
        best = float("inf")
        for _ in range(5):
            started = time.perf_counter()
            marginal_impact(result, candidate, footprint, vulns)
            best = min(best, time.perf_counter() - started)
        return best

    small = timed(small_book)
    big = timed(big_book)

    assert big < small * 5 + 5e-3, (
        f"marginal impact scaled with book size: {small * 1000:.2f} ms at 2.5k locations "
        f"vs {big * 1000:.2f} ms at {BOOK_SIZE}"
    )
