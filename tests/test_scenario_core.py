"""Tests for the peril-agnostic scenario engine and the windstorm adapter.

These run with no infra (numpy + pytest only) and pin the core money math:
vulnerability interpolation, financial terms, aggregation, and marginal impact.
"""

import numpy as np
import pytest

from engine.scenario.core import (
    Exposure,
    Location,
    Vulnerability,
    compute_scenario_loss,
    marginal_impact,
)
from engine.perils import windstorm


class ConstantFootprint:
    """A footprint returning the same intensity everywhere — handy for exact assertions."""

    peril = "windstorm"

    def __init__(self, value: float) -> None:
        self.value = value

    def sample(self, lons, lats):
        return np.full(np.asarray(lons).shape, self.value, dtype=float)


def test_vulnerability_interpolates_and_clips():
    v = Vulnerability("t", np.array([0.0, 10.0, 20.0]), np.array([0.0, 0.5, 1.0]))
    got = v.mdr(np.array([-5.0, 0.0, 5.0, 15.0, 25.0]))
    # below-range -> 0, midpoints interpolate, above-range holds at last knot (1.0)
    np.testing.assert_allclose(got, [0.0, 0.0, 0.25, 0.75, 1.0])


def test_vulnerability_rejects_bad_curves():
    with pytest.raises(ValueError):
        Vulnerability("bad", np.array([10.0, 0.0]), np.array([0.0, 1.0]))  # not ascending
    with pytest.raises(ValueError):
        Vulnerability("bad", np.array([0.0, 1.0]), np.array([0.0, 2.0]))  # MDR > 1


def test_scenario_loss_applies_deductible_and_limit():
    # Two locations, constant 30% damage. TIV 1,000,000 -> ground-up 300,000 each.
    locs = [
        Location("A", 0.0, 0.0, tiv=1_000_000, deductible=50_000),
        Location("B", 1.0, 1.0, tiv=1_000_000, limit=100_000),
    ]
    exposure = Exposure.from_locations(locs)
    vuln = {"default": Vulnerability("flat30", np.array([0.0, 1.0]), np.array([0.30, 0.30]))}

    res = compute_scenario_loss(exposure, ConstantFootprint(0.5), vuln)

    np.testing.assert_allclose(res.ground_up_loss, [300_000, 300_000])
    # A: 300k - 50k deductible = 250k ; B: min(300k, 100k limit) = 100k
    np.testing.assert_allclose(res.net_loss, [250_000, 100_000])
    assert res.total_ground_up == 600_000
    assert res.total_net == 350_000


def test_missing_vulnerability_cohort_fails_loud():
    exposure = Exposure.from_locations([Location("A", 0.0, 0.0, 1_000_000, vuln_key="masonry")])
    with pytest.raises(KeyError):
        compute_scenario_loss(exposure, ConstantFootprint(0.5), {"default": _flat()})


def test_marginal_impact_is_additive():
    vuln = {"default": _flat()}
    portfolio = Exposure.from_locations(
        [Location(f"P{i}", 0.0, 0.0, 1_000_000) for i in range(3)]
    )
    port_res = compute_scenario_loss(portfolio, ConstantFootprint(0.5), vuln)

    candidate = Exposure.from_locations([Location("NEW", 0.0, 0.0, 2_000_000)])
    impact = marginal_impact(port_res, candidate, ConstantFootprint(0.5), vuln)

    assert impact["delta_net"] == 2_000_000 * 0.10
    assert impact["portfolio_net_after"] == port_res.total_net + impact["delta_net"]


def test_windstorm_gridded_footprint_samples_and_zeroes_outside():
    # 2x2 grid, top-left cell at (lon 0, lat 2), 1-degree cells.
    grid = np.array([[40.0, 30.0], [20.0, 10.0]])
    fp = windstorm.GriddedFootprint(grid, lon_left=0.0, lat_top=2.0, cell_deg=1.0)

    # point in top-left cell, point in bottom-right cell, point far outside
    got = fp.sample(np.array([0.5, 1.5, 99.0]), np.array([1.5, 0.5, 0.0]))
    np.testing.assert_allclose(got, [40.0, 10.0, 0.0])


def test_windstorm_vulnerability_shape_is_sane():
    v = windstorm.DEFAULT_VULNERABILITY
    # calm -> no damage; rises with gust; monotonic throughout
    assert v.mdr(np.array([15.0]))[0] == 0.0
    assert 0.0 < v.mdr(np.array([35.0]))[0] < v.mdr(np.array([50.0]))[0] < 1.0
    xs = np.linspace(0, 80, 50)
    assert np.all(np.diff(v.mdr(xs)) >= 0)


def test_windstorm_damage_ratios_stay_in_the_right_order_of_magnitude():
    """European windstorm does not destroy the buildings it touches.

    MDR is the product of mean damage degree and proportion of assets affected, and both are
    small even in a severe storm — a curve approaching total loss overstates the answer by one
    to two orders of magnitude. Pinned here because it is the kind of error that is invisible
    in a unit test of the engine and obvious to an underwriter reading the output.
    """
    v = windstorm.DEFAULT_VULNERABILITY

    # A strong gale: damaging, but a small fraction of insured value.
    assert 1e-4 < v.mdr(np.array([40.0]))[0] < 1e-2
    # A severe European windstorm gust — roofs, not write-offs.
    assert 1e-3 < v.mdr(np.array([50.0]))[0] < 5e-2
    # Even at an extreme gust the mean damage ratio stays well away from total loss.
    assert v.mdr(np.array([70.0]))[0] < 0.20


def _flat():
    return Vulnerability("flat10", np.array([0.0, 1.0]), np.array([0.10, 0.10]))
