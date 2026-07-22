"""Peril-agnostic catastrophe scenario engine.

The fast path behind the underwriting wedge. Every peril reduces to the same pipeline:
sample a hazard footprint at each exposure location, apply a vulnerability (damage)
curve, apply financial terms, aggregate. Perils differ only in their data adapter
(hazard grids + damage function) under `engine.perils`.
"""

from engine.scenario.core import (
    Exposure,
    Location,
    ScenarioResult,
    Vulnerability,
    compute_scenario_loss,
    marginal_impact,
)

__all__ = [
    "Exposure",
    "Location",
    "ScenarioResult",
    "Vulnerability",
    "compute_scenario_loss",
    "marginal_impact",
]
