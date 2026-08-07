"""Load storm footprints out of the database into the engine's `GriddedFootprint`.

The engine owns all footprint *sampling*; this module only rehydrates a stored grid and
renders it for display. Nothing peril-specific is reimplemented here.
"""

from __future__ import annotations

import io

import numpy as np
from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.app.models.oed import StormFootprint
from engine.perils.windstorm import GriddedFootprint

# Gust speeds below this do essentially no damage (see the v1 vulnerability curve), so the
# overlay renders them fully transparent — an underwriter should see the damaging swath, not
# a wash of blue over the whole continent.
RENDER_MIN_MS = 20.0
RENDER_MAX_MS = 50.0

# Yellow -> orange -> red -> magenta. Reads as "hotter = worse" without a legend.
_RAMP = np.array(
    [
        [255, 237, 160],
        [254, 178, 76],
        [252, 78, 42],
        [189, 0, 38],
        [128, 0, 90],
    ],
    dtype=float,
)


def get_storm(session: Session, slug: str) -> StormFootprint | None:
    return session.scalar(select(StormFootprint).where(StormFootprint.slug == slug))


def upsert_storm(
    session: Session,
    *,
    slug: str,
    name: str,
    year: int,
    grid: np.ndarray,
    lon_left: float,
    lat_top: float,
    cell_deg: float,
    source: str,
    licence: str,
    event_date=None,
    notes: str | None = None,
) -> StormFootprint:
    """Insert or replace a storm footprint. Used by both hazard-loading scripts.

    `source` and `licence` are not decoration: CC BY 4.0 obliges attribution wherever the
    footprint is shown, and they are also how a placeholder footprint stays visibly labelled
    as one all the way through to the UI.
    """
    grid = np.ascontiguousarray(grid, dtype=np.float32)
    storm = get_storm(session, slug) or StormFootprint(slug=slug)
    storm.name = name
    storm.year = year
    storm.event_date = event_date
    storm.notes = notes
    storm.grid = grid.tobytes()
    storm.n_rows, storm.n_cols = grid.shape
    storm.lon_left = float(lon_left)
    storm.lat_top = float(lat_top)
    storm.cell_deg = float(cell_deg)
    storm.source = source
    storm.licence = licence
    session.add(storm)
    return storm


def to_footprint(storm: StormFootprint) -> GriddedFootprint:
    """Rehydrate the stored blob into the engine's footprint type."""
    grid = np.frombuffer(storm.grid, dtype=np.float32).reshape(storm.n_rows, storm.n_cols)
    return GriddedFootprint(
        grid=grid.astype(float),
        lon_left=storm.lon_left,
        lat_top=storm.lat_top,
        cell_deg=storm.cell_deg,
    )


def bounds(storm: StormFootprint) -> list[float]:
    """[west, south, east, north] — the extent deck.gl's BitmapLayer needs."""
    west = storm.lon_left
    north = storm.lat_top
    east = west + storm.n_cols * storm.cell_deg
    south = north - storm.n_rows * storm.cell_deg
    return [west, south, east, north]


def render_png(storm: StormFootprint) -> bytes:
    """Render the gust grid to an RGBA PNG for map overlay.

    Sending ~30k grid cells as JSON and colouring them client-side would work but costs a
    layer of frontend code for no visual gain; a PNG on a BitmapLayer is the cheap path.
    """
    from PIL import Image  # deferred: only the API layer needs Pillow

    grid = np.frombuffer(storm.grid, dtype=np.float32).reshape(storm.n_rows, storm.n_cols)

    t = np.clip((grid - RENDER_MIN_MS) / (RENDER_MAX_MS - RENDER_MIN_MS), 0.0, 1.0)
    idx = t * (len(_RAMP) - 1)
    lo = np.floor(idx).astype(int)
    hi = np.minimum(lo + 1, len(_RAMP) - 1)
    frac = (idx - lo)[..., None]

    rgb = _RAMP[lo] * (1 - frac) + _RAMP[hi] * frac
    alpha = np.where(grid < RENDER_MIN_MS, 0.0, 60 + 175 * t)

    rgba = np.dstack([rgb, alpha]).astype(np.uint8)
    buf = io.BytesIO()
    Image.fromarray(rgba, mode="RGBA").save(buf, format="PNG", optimize=True)
    return buf.getvalue()
