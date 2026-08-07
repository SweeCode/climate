"""Seed track-shaped PLACEHOLDER windstorm footprints so the demo runs before real data lands.

These are synthetic. They are shaped along the real tracks of Kyrill, Lothar and Daria so the
geography is right — Kyrill batters the Ruhr and the Randstad, Lothar runs across northern
France into Baden-Württemberg, Daria hammers the UK and Denmark — but the gust values are
constructed, not modelled.

That distinction travels with the data: every row records `source` and `licence` saying so,
and the UI renders them. Nothing here should ever be presented as a real footprint. Replace
with `scripts/prepare_xws_footprints.py` as soon as the XWS files are downloaded.

Run: python scripts/seed_placeholder_storms.py
"""

from __future__ import annotations

import datetime as dt
from itertools import pairwise

import numpy as np

from backend.app.db import SessionLocal, init_db
from backend.app.hazard import upsert_storm

SOURCE = "SYNTHETIC placeholder — track-shaped, not a modelled footprint"
LICENCE = "Internal demo data. Not for pricing. Replace with XWS (CC BY 4.0)."

# Grid covering western Europe and the eastern North Atlantic at XWS's 0.22 deg spacing.
CELL_DEG = 0.22
LON_LEFT, LAT_TOP = -15.0, 62.0
N_COLS, N_ROWS = 182, 118  # -> lon -15..25, lat 36..62


def _swath(track: list[tuple[float, float, float]], width_deg: float) -> np.ndarray:
    """Build a gust field as a decaying swath along a storm track.

    `track` is [(lon, lat, peak_gust_ms), ...]. Gusts fall off as a Gaussian in the distance
    to the track line and are interpolated in strength between consecutive track points —
    the elongated, along-track structure that makes windstorm an accumulation peril.
    """
    lons = LON_LEFT + (np.arange(N_COLS) + 0.5) * CELL_DEG
    lats = LAT_TOP - (np.arange(N_ROWS) + 0.5) * CELL_DEG
    glon, glat = np.meshgrid(lons, lats)

    # Degrees of longitude shrink with latitude; without this the swath fattens northwards.
    cos_lat = np.cos(np.radians(glat))
    field = np.zeros((N_ROWS, N_COLS), dtype=float)

    for (lon0, lat0, peak0), (lon1, lat1, peak1) in pairwise(track):
        dlon = (lon1 - lon0) * np.cos(np.radians((lat0 + lat1) / 2))
        dlat = lat1 - lat0
        seg_len2 = dlon**2 + dlat**2

        # Projection of each grid cell onto this track segment, clamped to the segment.
        px = (glon - lon0) * cos_lat
        py = glat - lat0
        t = np.clip((px * dlon + py * dlat) / seg_len2, 0.0, 1.0)

        perp = np.hypot(px - t * dlon, py - t * dlat)
        peak = peak0 + t * (peak1 - peak0)
        field = np.maximum(field, peak * np.exp(-((perp / width_deg) ** 2)))

    # Storms lose energy over land and gain it over the open sea; a mild land taper keeps the
    # footprint from looking like a painted stripe.
    field *= 1.0 - 0.12 * np.clip((glat - 44.0) / 18.0, 0.0, 1.0)
    return np.where(field < 8.0, 0.0, field)


STORMS = [
    {
        "slug": "kyrill-2007",
        "name": "Kyrill",
        "year": 2007,
        "event_date": dt.date(2007, 1, 18),
        "notes": "Crossed Ireland, northern England and the North Sea into Germany and Poland. "
                 "~EUR 4.5bn insured market loss.",
        # Offset south of the low's centre: an extratropical cyclone does its damage on the
        # southern flank, which for Kyrill meant the Ruhr and the Randstad, not the track line.
        "track": [
            (-11.0, 54.0, 34.0), (-6.0, 54.0, 40.0), (-2.0, 53.6, 44.0),
            (2.0, 52.8, 46.0), (6.5, 51.6, 46.0), (11.0, 51.6, 42.0),
            (16.0, 51.8, 36.0), (21.0, 52.0, 30.0),
        ],
        "width": 2.8,
    },
    {
        "slug": "lothar-1999",
        "name": "Lothar",
        "year": 1999,
        "event_date": dt.date(1999, 12, 26),
        "notes": "Small, violent core across northern France into southern Germany. "
                 "~EUR 6bn insured market loss.",
        "track": [
            (-6.0, 48.5, 32.0), (-2.0, 48.8, 42.0), (1.0, 48.9, 50.0),
            (4.0, 48.8, 48.0), (7.5, 48.7, 44.0), (11.0, 48.6, 38.0),
            (15.0, 48.8, 30.0),
        ],
        "width": 1.7,
    },
    {
        "slug": "daria-1990",
        "name": "Daria (Burns' Day storm)",
        "year": 1990,
        "event_date": dt.date(1990, 1, 25),
        "notes": "Broad, severe swath across the British Isles, the Low Countries and Denmark.",
        "track": [
            (-14.0, 54.5, 33.0), (-9.0, 54.8, 41.0), (-4.0, 54.4, 45.0),
            (0.5, 53.8, 44.0), (5.0, 53.6, 42.0), (9.5, 54.0, 38.0),
            (14.0, 54.6, 32.0),
        ],
        "width": 3.4,
    },
]


def main() -> None:
    init_db()
    with SessionLocal() as session:
        for spec in STORMS:
            grid = _swath(spec["track"], spec["width"])
            upsert_storm(
                session,
                slug=spec["slug"],
                name=spec["name"],
                year=spec["year"],
                event_date=spec["event_date"],
                notes=spec["notes"],
                grid=grid,
                lon_left=LON_LEFT,
                lat_top=LAT_TOP,
                cell_deg=CELL_DEG,
                source=SOURCE,
                licence=LICENCE,
            )
            print(
                f"seeded {spec['slug']:<14} peak gust {grid.max():.0f} m/s, "
                f"{int((grid > 25).sum())} cells above 25 m/s"
            )
        session.commit()
    print("\nPLACEHOLDER data. Run scripts/prepare_xws_footprints.py to replace with real XWS.")


if __name__ == "__main__":
    main()
