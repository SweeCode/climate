"""Order-of-magnitude calibration of the windstorm model.

`docs/PLAN.md` asks for a real validation anchor rather than a smoke test: a historical storm
on a portfolio, checked against the known market loss. This is that check, at the only
precision the v1 model can honestly support — order of magnitude.

It exists because the v1 curve was originally wrong by 30-50x (it saturated near total loss at
extreme gusts, which European windstorm never does) and every unit test still passed. Curve
shape and monotonicity were correct; only the *level* was absurd, and nothing was watching the
level. These tests watch the level.

Deliberately infra-free: reads the committed synthetic book, no database, no hazard download.
"""

from __future__ import annotations

import os

import numpy as np
import pytest

from data.ingest.oed_pipeline import from_csv
from engine.perils.windstorm import DEFAULT_VULNERABILITY, GriddedFootprint, default_vulnerabilities
from engine.scenario.core import Exposure, compute_scenario_loss

BOOK = os.path.join(os.path.dirname(__file__), "..", "data", "samples", "demo_book_oed.csv")

# Kyrill, 18 January 2007: roughly EUR 4.6bn insured across DE/UK/BE/NL (Munich Re put the
# market at EUR 5-7bn). The single best-documented anchor available for European windstorm.
KYRILL_INSURED_EUR = 4.6e9

# Very roughly the insured property value lying under Kyrill's damaging swath. This is a
# coarse estimate, which is exactly why the assertion below is an order-of-magnitude band and
# not a tolerance.
EXPOSED_VALUE_EUR = 1.0e13

# Population-weighted gust over that area — the damaging band, not the peak.
CHARACTERISTIC_GUST_MS = 35.0


@pytest.fixture(scope="module")
def book() -> Exposure:
    locations, report = from_csv(os.path.normpath(BOOK))
    assert report.loaded > 400, "sample book should load; regenerate it if this fails"
    return Exposure.from_locations(locations)


def _uniform_swath(gust_ms: float) -> GriddedFootprint:
    """A flat band of one gust speed across NW Europe, zero elsewhere.

    Cruder than a real footprint on purpose: it isolates the vulnerability level from any
    question about footprint shape.
    """
    grid = np.zeros((120, 200), dtype=float)
    # Rows run north->south from lat_top=62 at 0.22 deg: rows 27..59 span ~55.1N to 49.0N.
    grid[27:59, :] = gust_ms
    return GriddedFootprint(grid=grid, lon_left=-15.0, lat_top=62.0, cell_deg=0.22)


def test_implied_market_loss_is_the_right_order_of_magnitude():
    """The curve at Kyrill's characteristic gust must imply a Kyrill-scale market loss.

    Ground-up necessarily exceeds the insured figure — deductibles absorb the small claims
    that dominate windstorm, and not all property carries windstorm cover — but it cannot
    exceed it by orders of magnitude. A curve overstating damage by 30x lands at ~EUR 400bn
    here and fails loudly.
    """
    mdr = float(DEFAULT_VULNERABILITY.mdr(np.array([CHARACTERISTIC_GUST_MS]))[0])
    implied_ground_up = EXPOSED_VALUE_EUR * mdr

    ratio = implied_ground_up / KYRILL_INSURED_EUR
    assert 0.5 < ratio < 10.0, (
        f"implied ground-up market loss EUR {implied_ground_up / 1e9:.1f}bn is "
        f"{ratio:.1f}x the ~EUR {KYRILL_INSURED_EUR / 1e9:.1f}bn insured actual — "
        "the vulnerability level is out by an order of magnitude"
    )


def test_a_book_inside_a_severe_swath_loses_a_plausible_share_of_tiv(book: Exposure):
    """A whole portfolio sitting under a severe gust loses low single-digit percent at most.

    European windstorm damages roofs; it does not write buildings off. Anything approaching a
    double-digit portfolio loss ratio means the vulnerability curve has drifted again.
    """
    result = compute_scenario_loss(book, _uniform_swath(45.0), default_vulnerabilities())
    loss_ratio = result.total_net / float(book.tivs.sum())

    assert 0.0005 < loss_ratio < 0.05, (
        f"portfolio loss ratio {loss_ratio * 100:.3f}% under a uniform 45 m/s gust is outside "
        "the plausible 0.05%-5% band for European windstorm"
    )


def test_deductibles_absorb_part_of_the_loss(book: Exposure):
    """Sanity on the financial module: net must sit below ground-up but not vanish.

    If net equals ground-up the deductibles are not being applied; if net is zero the book's
    terms are swallowing everything, which was the symptom when the curve was corrected but
    the sample deductibles were still percentage-of-TIV.
    """
    result = compute_scenario_loss(book, _uniform_swath(45.0), default_vulnerabilities())

    assert result.total_net < result.total_ground_up
    assert result.total_net > 0.4 * result.total_ground_up


def test_no_single_location_is_written_off_by_wind(book: Exposure):
    """Even the worst-hit location keeps most of its value at an extreme gust."""
    result = compute_scenario_loss(book, _uniform_swath(60.0), default_vulnerabilities())
    worst = float(np.max(result.ground_up_loss / np.maximum(book.tivs, 1.0)))

    assert worst < 0.15, f"worst location loses {worst * 100:.1f}% of TIV at 60 m/s"
