"""European windstorm adapter.

*The* European accumulation peril: a single extratropical storm (Daria 1990, Lothar 1999,
Kyrill 2007) hits a broad swathe of NW Europe at once, which is exactly the accumulation
question the underwriting wedge answers.

Hazard: gridded gust-speed footprints. Source data is the XWS catalogue
(europeanwindstorms.org, free) and the Copernicus C3S Enhanced Windstorm Service (ERA5,
downscaled to ~1.6 km). Those arrive as rasters (GeoTIFF / NetCDF); `GriddedFootprint`
below samples them. Loading real rasters needs the `[geo]` extra (rasterio/xarray); the
grid math here is dependency-free so the engine and its tests run without it.

Vulnerability: a v1 gust-speed -> mean-damage-ratio curve. Buildings take essentially no
damage below ~20 m/s and damage rises steeply, roughly with a high power of the gust excess
above that threshold.

The values below are SMALL, and that is the point. European windstorm literature (Schwierz
et al. 2010 and the work built on it) decomposes vulnerability as

    MDR = MDD x PAA

where MDD is the mean damage degree among affected buildings and PAA is the proportion of
buildings affected at all. Both are well below 1 even in a severe storm: at ~50 m/s something
like 10-25% of buildings suffer any damage, and those that do lose on the order of 5-10% of
their value — so MDR lands near 1-2%, not near total loss. The numbers here are that product.

Windstorm is an accumulation peril because one event touches an entire region at once, not
because it destroys the buildings it touches. A curve that saturates near 1.0 confuses the two
and overstates losses by one to two orders of magnitude.

Calibration status: these are order-of-magnitude values reasoned from the MDD/PAA
decomposition and cross-checked against European market losses (Kyrill 2007, ~EUR 4.6bn
insured across DE/UK/BE/NL). They are NOT fitted to claims experience, and the level should be
treated as indicative until it is. `tests/test_scenario_core.py` pins the order of magnitude
so a future edit cannot quietly restore an implausible curve. Fitting per construction and
occupancy cohort is the proprietary-refinement layer.
"""

from __future__ import annotations

import numpy as np

from engine.scenario.core import Vulnerability

PERIL = "windstorm"

# v1 European windstorm vulnerability (residential/commercial blended).
# Gust speed (m/s, 3-second gust at 10 m) -> mean damage ratio (MDD x PAA), see module docstring.
_GUST_MS = np.array([0, 20, 25, 30, 35, 40, 45, 50, 60, 70], dtype=float)
_MDR = np.array(
    [0.0, 0.0, 0.00005, 0.0003, 0.0012, 0.0035, 0.008, 0.015, 0.040, 0.075], dtype=float
)

DEFAULT_VULNERABILITY = Vulnerability(
    name="eu_windstorm_v1_blended",
    intensities=_GUST_MS,
    damage_ratios=_MDR,
)


def default_vulnerabilities() -> dict[str, Vulnerability]:
    """Vulnerability set keyed by cohort. v1 uses a single blended curve for 'default'."""
    return {"default": DEFAULT_VULNERABILITY}


class GriddedFootprint:
    """A gust-speed footprint on a regular lon/lat grid, sampled by nearest cell.

    `grid` is a 2-D array indexed [row, col] where rows run north->south (row 0 at
    `lat_top`) and cols run west->east (col 0 at `lon_left`) — the standard raster
    orientation of the source products. Cells are `cell_deg` degrees square. Locations
    outside the grid extent sample as 0.0 (outside the storm footprint).

    Real XWS / Copernicus rasters are loaded via `GriddedFootprint.from_geotiff` (requires
    the `[geo]` extra); constructing directly from an array keeps tests infra-free.
    """

    peril = PERIL

    def __init__(
        self,
        grid: np.ndarray,
        lon_left: float,
        lat_top: float,
        cell_deg: float,
    ) -> None:
        if grid.ndim != 2:
            raise ValueError("footprint grid must be 2-D [row, col]")
        self.grid = np.asarray(grid, dtype=float)
        self.lon_left = float(lon_left)
        self.lat_top = float(lat_top)
        self.cell_deg = float(cell_deg)
        self.n_rows, self.n_cols = self.grid.shape

    def sample(self, lons: np.ndarray, lats: np.ndarray) -> np.ndarray:
        lons = np.asarray(lons, dtype=float)
        lats = np.asarray(lats, dtype=float)
        cols = np.floor((lons - self.lon_left) / self.cell_deg).astype(int)
        rows = np.floor((self.lat_top - lats) / self.cell_deg).astype(int)

        inside = (
            (cols >= 0) & (cols < self.n_cols) & (rows >= 0) & (rows < self.n_rows)
        )
        out = np.zeros(lons.shape, dtype=float)
        out[inside] = self.grid[rows[inside], cols[inside]]
        return out

    @classmethod
    def from_geotiff(cls, path: str) -> "GriddedFootprint":  # pragma: no cover - needs [geo]
        """Load a gust footprint from a GeoTIFF (XWS / Copernicus product).

        Deferred import so the core engine has no geospatial dependency.
        """
        import rasterio  # type: ignore

        with rasterio.open(path) as src:
            band = src.read(1).astype(float)
            transform = src.transform
            cell_deg = abs(transform.a)
            lon_left = transform.c
            lat_top = transform.f
        return cls(grid=band, lon_left=lon_left, lat_top=lat_top, cell_deg=cell_deg)
