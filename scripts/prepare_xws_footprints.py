"""Convert real XWS storm footprints into database rows. Requires the `[geo]` extra.

The XWS catalogue (europeanwindstorms.org) publishes maximum 3-second gust footprints for 50
extreme European windstorms, CC BY 4.0 — free for commercial use with attribution. This is
the script that turns them into something the engine can sample.

Two things make that non-trivial, and both are handled here rather than in the engine:

  1. XWS footprints sit on a ROTATED-POLE grid (0.22 deg spacing, pole at 177.5E/37.5N), not
     a regular lon/lat grid. `engine.perils.windstorm.GriddedFootprint` deliberately assumes a
     regular grid — keeping the runtime sampler trivial is worth more than handling every
     source projection, so the unrotation happens once, offline, here.
  2. The result is stored in Postgres, not on disk, because the deployment target has an
     ephemeral filesystem and hazard rasters are never committed.

Download the footprints first — the repository is an open directory, no login:

    curl -O https://www.europeanwindstorms.org/repository/Kyrill/Kyrill_biasMean.nc

Save them under data/hazard/ (gitignored). Each storm directory offers several products;
take `_biasMean`, the recalibrated footprint. `_rawFoot` is the direct 25 km model output,
which cannot resolve peak gusts and gives 32-40 m/s maxima where the recalibrated field gives
51-77 — using it would understate every loss on the book. `_biasL95`/`_biasU95` are the
recalibration's confidence bounds and are the natural input to an uncertainty band later.

Usage:
    # 1. See what is actually in the file before converting anything
    python scripts/prepare_xws_footprints.py --inspect data/hazard/Kyrill_biasMean.nc

    # 2. Convert and load
    python scripts/prepare_xws_footprints.py data/hazard/Kyrill_biasMean.nc \\
        --slug kyrill-2007 --name Kyrill --year 2007 --date 2007-01-18
"""

from __future__ import annotations

import argparse
import datetime as dt
import sys

import numpy as np

# Target regular grid: western Europe + eastern North Atlantic, at the source's own spacing
# so the regridding neither invents nor discards resolution.
CELL_DEG = 0.22
LON_LEFT, LAT_TOP = -15.0, 62.0
N_COLS, N_ROWS = 182, 118

SOURCE = (
    "XWS catalogue (Roberts et al. 2014), recalibrated footprint — "
    "Met Office / Univ. of Reading / Univ. of Exeter"
)
LICENCE = (
    "Copyright Met Office, University of Reading and University of Exeter. "
    "Licensed under Creative Commons CC BY 4.0 International Licence "
    "(https://creativecommons.org/licenses/by/4.0/)"
)

# Candidate names for the gust variable, most specific first. CF-compliant XWS files should
# carry one of these; --inspect exists for when they do not.
GUST_NAMES = ("max_wind_gust", "wind_gust", "gust", "fg", "wind_speed_of_gust", "max_gust")


def inspect(path: str) -> None:
    """Print the file's structure so the variable names can be confirmed, not guessed."""
    import xarray as xr

    ds = xr.open_dataset(path, decode_timedelta=False)
    print(ds)
    print("\n--- data variables ---")
    for name, var in ds.data_vars.items():
        print(f"  {name}: dims={var.dims} shape={var.shape} units={var.attrs.get('units')}")
    print("\n--- coordinates ---")
    for name, var in ds.coords.items():
        print(f"  {name}: dims={var.dims} shape={var.shape}")
    print("\nPick the gust variable and pass --gust-var if it is not auto-detected.")


def _pick_gust(ds, explicit: str | None):
    import xarray as xr  # noqa: F401 - typing only

    if explicit:
        if explicit not in ds.variables:
            sys.exit(f"variable '{explicit}' not in file; run --inspect to list them")
        return ds[explicit]
    for name in GUST_NAMES:
        if name in ds.variables:
            return ds[name]
    # Fall back to the only 2-D field, if there is exactly one.
    twod = [n for n, v in ds.data_vars.items() if v.ndim == 2]
    if len(twod) == 1:
        print(f"note: assuming '{twod[0]}' is the gust field")
        return ds[twod[0]]
    sys.exit("could not identify the gust variable; run --inspect and pass --gust-var")


def _true_coords(ds, gust):
    """Get true lon/lat for every source cell, unrotating the pole if necessary.

    CF-compliant rotated-pole files usually carry 2-D auxiliary `longitude`/`latitude`
    coordinates, in which case no trigonometry is needed. If they do not, unrotate from the
    grid_mapping attributes.

    Whether a grid is rotated is decided from CF metadata, never from the coordinate variable
    names. The real XWS files name their rotated axes plainly `lat`/`lon` — reading those as
    true coordinates puts Kyrill in the Atlantic off West Africa, and every downstream number
    still looks perfectly reasonable.
    """
    for lon_name, lat_name in (("longitude", "latitude"), ("lon", "lat")):
        if lon_name in ds.variables and ds[lon_name].ndim == 2:
            return np.asarray(ds[lon_name]), np.asarray(ds[lat_name])

    lon1d, lat1d = _horizontal_axes(ds)
    lon2d, lat2d = np.meshgrid(lon1d, lat1d)

    pole = _pole(ds, gust)
    if pole is None:
        return lon2d, lat2d  # genuinely a regular lon/lat grid
    return _unrotate(lon2d, lat2d, *pole)


def _unrotate(rlon, rlat, pole_lon, pole_lat):
    """Rotated-pole grid coordinates -> true lon/lat, in degrees.

    Delegated to pyproj rather than hand-rolled. Rotated-pole formulations differ in whether
    the prime meridian is offset by 180 degrees and in the sign of the longitude term, and
    picking the wrong variant produces a footprint that is smoothly, confidently wrong — it
    lands in the southern hemisphere while every value in it stays perfectly plausible.
    """
    from pyproj import CRS, Transformer

    rotated = CRS.from_cf(
        {
            "grid_mapping_name": "rotated_latitude_longitude",
            "grid_north_pole_latitude": pole_lat,
            "grid_north_pole_longitude": pole_lon,
        }
    )
    transformer = Transformer.from_crs(rotated, "EPSG:4326", always_xy=True)
    return transformer.transform(rlon, rlat)


def _horizontal_axes(ds):
    """The 1-D x/y coordinate arrays, whatever this file calls them."""
    for lon_name, lat_name in (("rlon", "rlat"), ("lon", "lat"), ("longitude", "latitude")):
        if lon_name in ds.variables and lat_name in ds.variables:
            return np.asarray(ds[lon_name]), np.asarray(ds[lat_name])
    sys.exit("could not find horizontal coordinates; run --inspect to list them")


def _pole(ds, gust) -> tuple[float, float] | None:
    """Rotated pole position, or None if this grid is not rotated.

    Follows the CF chain: the data variable's `grid_mapping` attribute names the variable
    holding the projection, and `grid_mapping_name` says which projection it is.
    """
    candidates = [gust.attrs.get("grid_mapping")]
    candidates += ["rotated_pole", "rotated_latitude_longitude", "crs"]

    for name in candidates:
        if not name or name not in ds.variables:
            continue
        attrs = ds[name].attrs
        if attrs.get("grid_mapping_name") not in (None, "rotated_latitude_longitude"):
            continue  # some other projection — not ours to unrotate
        lon = attrs.get("grid_north_pole_longitude")
        lat = attrs.get("grid_north_pole_latitude")
        if lon is not None and lat is not None:
            return float(lon), float(lat)

    # No grid mapping. Fall back on the axes' own standard_name before trusting them: a file
    # can carry grid_latitude/grid_longitude axes with the projection variable missing.
    for axis in ("lat", "rlat", "latitude"):
        if axis in ds.variables and ds[axis].attrs.get("standard_name") == "grid_latitude":
            print("note: rotated axes but no grid_mapping; using the XWS pole (177.5E, 37.5N)")
            return 177.5, 37.5
    return None


def _regrid(lons, lats, values) -> np.ndarray:
    """Interpolate scattered true-coordinate gusts onto the regular target grid."""
    from scipy.interpolate import griddata

    finite = np.isfinite(values) & np.isfinite(lons) & np.isfinite(lats)
    pts = np.column_stack([lons[finite].ravel(), lats[finite].ravel()])
    vals = values[finite].ravel()
    if pts.size == 0:
        sys.exit("no finite gust values in the source file")

    tlon = LON_LEFT + (np.arange(N_COLS) + 0.5) * CELL_DEG
    tlat = LAT_TOP - (np.arange(N_ROWS) + 0.5) * CELL_DEG
    tlon2d, tlat2d = np.meshgrid(tlon, tlat)

    out = griddata(pts, vals, (tlon2d, tlat2d), method="linear")
    # XWS blanks gusts outside a 1000 km radius of the track; those and any off-domain cells
    # are genuinely "not part of this event" -> 0.0, which is what Footprint.sample promises.
    return np.nan_to_num(out, nan=0.0)


def convert(args: argparse.Namespace) -> None:
    import xarray as xr

    from backend.app.db import SessionLocal, init_db
    from backend.app.hazard import upsert_storm

    ds = xr.open_dataset(args.path, decode_timedelta=False)
    gust = _pick_gust(ds, args.gust_var)
    values = np.asarray(gust.squeeze())
    if values.ndim != 2:
        sys.exit(f"gust field has shape {values.shape}; expected 2-D after squeeze")

    lons, lats = _true_coords(ds, gust)
    grid = _regrid(lons, lats, values)

    print(
        f"regridded {values.shape} -> {grid.shape}; "
        f"peak gust {grid.max():.1f} m/s, {int((grid > 25).sum())} cells above 25 m/s"
    )
    if grid.max() > 120:
        print("WARNING: peak gust looks too high — is the source in km/h rather than m/s?")

    # Refuse a footprint that missed Europe. A mis-read projection does not produce an obvious
    # error — it lands the source grid outside the target domain, every cell interpolates to
    # NaN, and the zeros that replace them look exactly like "this storm spared your book".
    # An XWS storm is in the catalogue *because* it was damaging, so an empty domain is a
    # conversion failure, not a quiet event.
    if not (grid > 25.0).any():
        sys.exit(
            "no cell above 25 m/s anywhere in the target domain — the source grid did not "
            "land on Europe. Check the projection with --inspect; do not load this."
        )

    init_db()
    with SessionLocal() as session:
        upsert_storm(
            session,
            slug=args.slug,
            name=args.name,
            year=args.year,
            event_date=dt.date.fromisoformat(args.date) if args.date else None,
            notes=args.notes,
            grid=grid,
            lon_left=LON_LEFT,
            lat_top=LAT_TOP,
            cell_deg=CELL_DEG,
            source=SOURCE,
            licence=LICENCE,
        )
        session.commit()
    print(f"loaded '{args.slug}' into the database")


def main() -> None:
    p = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    p.add_argument("path", help="path to an XWS footprint NetCDF under data/hazard/")
    p.add_argument("--inspect", action="store_true", help="print file structure and exit")
    p.add_argument("--gust-var", help="name of the gust variable, if auto-detection fails")
    p.add_argument("--slug", help="catalogue id, e.g. kyrill-2007")
    p.add_argument("--name", help="display name, e.g. Kyrill")
    p.add_argument("--year", type=int)
    p.add_argument("--date", help="ISO event date, e.g. 2007-01-18")
    p.add_argument("--notes", default=None)
    args = p.parse_args()

    if args.inspect:
        inspect(args.path)
        return
    for required in ("slug", "name", "year"):
        if getattr(args, required) is None:
            p.error(f"--{required} is required when converting")
    convert(args)


if __name__ == "__main__":
    main()
