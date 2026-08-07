"""Core scenario engine: footprint x exposure x vulnerability -> loss.

Pure Python/numpy. No I/O, no infra, no peril-specific knowledge — that lives in
`engine.perils`. This is what runs on the interactive fast path (the underwriting wedge),
so it is written to vectorize over a whole portfolio and to make the *marginal* impact of
a single new account cheap once the portfolio footprint samples are cached.

Money is handled in float currency units; damage ratios are dimensionless in [0, 1].
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Protocol

import numpy as np

# --------------------------------------------------------------------------------------
# Hazard footprint
# --------------------------------------------------------------------------------------


class Footprint(Protocol):
    """A hazard footprint: intensity as a function of location.

    Intensity units are peril-specific (m/s gust, metres flood depth, fire index, ...).
    Implementations must be vectorized: given equal-length lon/lat arrays, return an
    intensity array of the same length. Locations outside the footprint return 0.0.
    """

    peril: str

    def sample(self, lons: np.ndarray, lats: np.ndarray) -> np.ndarray: ...


# --------------------------------------------------------------------------------------
# Vulnerability
# --------------------------------------------------------------------------------------


@dataclass(frozen=True)
class Vulnerability:
    """Damage function: hazard intensity -> mean damage ratio (MDR) in [0, 1].

    Represented as a monotonic lookup table interpolated linearly and clipped to [0, 1].
    A curve is peril- and (later) construction/occupancy-specific; adapters in
    `engine.perils` supply the right curve per location cohort.

    `intensities` must be sorted ascending. Below the first knot MDR is 0; above the last
    knot MDR is held at the last value (curves should saturate near 1.0).
    """

    name: str
    intensities: np.ndarray  # shape (n,), ascending
    damage_ratios: np.ndarray  # shape (n,), in [0, 1]

    def __post_init__(self) -> None:
        x = np.asarray(self.intensities, dtype=float)
        y = np.asarray(self.damage_ratios, dtype=float)
        if x.ndim != 1 or x.shape != y.shape:
            raise ValueError("intensities and damage_ratios must be 1-D and equal length")
        if np.any(np.diff(x) < 0):
            raise ValueError(f"vulnerability '{self.name}': intensities must be ascending")
        if np.any(y < 0) or np.any(y > 1):
            raise ValueError(f"vulnerability '{self.name}': damage_ratios must be in [0, 1]")
        object.__setattr__(self, "intensities", x)
        object.__setattr__(self, "damage_ratios", y)

    def mdr(self, intensity: np.ndarray) -> np.ndarray:
        """Mean damage ratio at the given intensities (vectorized)."""
        intensity = np.asarray(intensity, dtype=float)
        # np.interp holds endpoints flat outside the knot range, which is what we want.
        return np.clip(
            np.interp(intensity, self.intensities, self.damage_ratios), 0.0, 1.0
        )


# --------------------------------------------------------------------------------------
# Exposure
# --------------------------------------------------------------------------------------


@dataclass(frozen=True)
class Location:
    """One insured location. TIV is total insured value (sum of coverages).

    Financial terms are per-location (site) here; policy/account layers are applied on top
    by the caller. `deductible` and `limit` are in currency units; `limit=None` means no
    site limit. `vuln_key` selects the vulnerability curve cohort for this location.
    """

    loc_id: str
    lon: float
    lat: float
    tiv: float
    vuln_key: str = "default"
    deductible: float = 0.0
    limit: float | None = None


@dataclass
class Exposure:
    """A portfolio of locations, stored column-wise for vectorized scenario runs."""

    loc_ids: list[str]
    lons: np.ndarray
    lats: np.ndarray
    tivs: np.ndarray
    vuln_keys: list[str]
    deductibles: np.ndarray
    limits: np.ndarray  # inf where no limit

    @classmethod
    def from_locations(cls, locations: list[Location]) -> Exposure:
        if not locations:
            raise ValueError("exposure must contain at least one location")
        return cls(
            loc_ids=[loc.loc_id for loc in locations],
            lons=np.array([loc.lon for loc in locations], dtype=float),
            lats=np.array([loc.lat for loc in locations], dtype=float),
            tivs=np.array([loc.tiv for loc in locations], dtype=float),
            vuln_keys=[loc.vuln_key for loc in locations],
            deductibles=np.array([loc.deductible for loc in locations], dtype=float),
            limits=np.array(
                [np.inf if loc.limit is None else loc.limit for loc in locations],
                dtype=float,
            ),
        )

    def __len__(self) -> int:
        return len(self.loc_ids)


# --------------------------------------------------------------------------------------
# Scenario computation
# --------------------------------------------------------------------------------------


@dataclass
class ScenarioResult:
    """Per-location and aggregate losses for a single deterministic scenario."""

    peril: str
    loc_ids: list[str]
    intensities: np.ndarray  # sampled hazard intensity per location
    ground_up_loss: np.ndarray  # TIV * MDR, before financial terms
    net_loss: np.ndarray  # after site deductible & limit
    total_ground_up: float = field(init=False)
    total_net: float = field(init=False)

    def __post_init__(self) -> None:
        self.total_ground_up = float(self.ground_up_loss.sum())
        self.total_net = float(self.net_loss.sum())


def _apply_financial(
    ground_up: np.ndarray, deductibles: np.ndarray, limits: np.ndarray
) -> np.ndarray:
    """Apply per-location deductible then limit: net = min(max(GU - ded, 0), limit)."""
    after_ded = np.maximum(ground_up - deductibles, 0.0)
    return np.minimum(after_ded, limits)


def compute_scenario_loss(
    exposure: Exposure,
    footprint: Footprint,
    vulnerabilities: dict[str, Vulnerability],
) -> ScenarioResult:
    """Run one deterministic scenario (a single event footprint) over a portfolio.

    `vulnerabilities` maps each distinct `vuln_key` present in the exposure to a curve.
    Raises KeyError if a location references a missing curve — fail loud rather than
    silently pricing risk at zero damage.
    """
    intensities = footprint.sample(exposure.lons, exposure.lats)

    mdr = np.zeros(len(exposure), dtype=float)
    for key in set(exposure.vuln_keys):
        if key not in vulnerabilities:
            raise KeyError(
                f"no vulnerability curve for cohort '{key}' "
                f"(peril '{footprint.peril}'); locations would be mispriced at 0 damage"
            )
        mask = np.array([vk == key for vk in exposure.vuln_keys])
        mdr[mask] = vulnerabilities[key].mdr(intensities[mask])

    ground_up = exposure.tivs * mdr
    net = _apply_financial(ground_up, exposure.deductibles, exposure.limits)

    return ScenarioResult(
        peril=footprint.peril,
        loc_ids=list(exposure.loc_ids),
        intensities=intensities,
        ground_up_loss=ground_up,
        net_loss=net,
    )


def marginal_impact(
    portfolio_result: ScenarioResult,
    candidate: Exposure,
    footprint: Footprint,
    vulnerabilities: dict[str, Vulnerability],
) -> dict[str, float]:
    """The underwriting wedge: what a candidate account adds to portfolio scenario loss.

    Because scenario loss is additive across locations, the marginal impact of binding a
    new account is just that account's own loss under the same footprint — no need to
    re-run the whole portfolio. Returns the deltas and the resulting totals.
    """
    candidate_result = compute_scenario_loss(candidate, footprint, vulnerabilities)
    return {
        "delta_ground_up": candidate_result.total_ground_up,
        "delta_net": candidate_result.total_net,
        "portfolio_net_before": portfolio_result.total_net,
        "portfolio_net_after": portfolio_result.total_net + candidate_result.total_net,
    }
