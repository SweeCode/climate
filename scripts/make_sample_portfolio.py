"""Generate the synthetic demo book and candidate account shipped with the app.

Two OED location CSVs land in `data/samples/` and are committed, so a fresh clone can run
the whole demo with no downloads and no client data anywhere near it:

  demo_book_oed.csv          ~500 locations across NW Europe, deliberately dirty
  candidate_account_oed.csv  a logistics account sitting in the Kyrill swath

The dirt is the point. An ingestion report that reads "500/500 loaded, 0 issues" proves
nothing to a broker who knows exactly how bad their bordereaux are; one that catches a
missing geocode and a zero TIV is the product demo.

Deterministic (fixed seed) so the demo tells the same story every time.

Run: python scripts/make_sample_portfolio.py
"""

from __future__ import annotations

import csv
import os

import numpy as np

SEED = 20070118  # Kyrill's landfall date, because why not
OUT_DIR = "data/samples"

COLUMNS = [
    "PortNumber", "AccNumber", "LocNumber", "CountryCode", "PostalCode", "City",
    "Latitude", "Longitude", "BuildingTIV", "ContentsTIV", "BITIV",
    "LocDed", "LocLimit", "OccupancyCode", "ConstructionCode",
]

# (city, lon, lat, country, postal prefix, share of the book)
CITIES = [
    ("Cologne",     6.96, 50.94, "DE", "50", 0.09),
    ("Dusseldorf",  6.78, 51.23, "DE", "40", 0.08),
    ("Dortmund",    7.47, 51.51, "DE", "44", 0.06),
    ("Hamburg",    10.00, 53.55, "DE", "20", 0.06),
    ("Frankfurt",   8.68, 50.11, "DE", "60", 0.06),
    ("Berlin",     13.40, 52.52, "DE", "10", 0.05),
    ("Munich",     11.58, 48.14, "DE", "80", 0.04),
    ("Amsterdam",   4.90, 52.37, "NL", "10", 0.08),
    ("Rotterdam",   4.48, 51.92, "NL", "30", 0.06),
    ("Utrecht",     5.12, 52.09, "NL", "35", 0.04),
    ("Brussels",    4.35, 50.85, "BE", "10", 0.06),
    ("Antwerp",     4.40, 51.22, "BE", "20", 0.04),
    ("Paris",       2.35, 48.86, "FR", "75", 0.06),
    ("Lille",       3.06, 50.63, "FR", "59", 0.04),
    ("Lyon",        4.84, 45.76, "FR", "69", 0.03),
    ("London",     -0.13, 51.51, "GB", "EC", 0.07),
    ("Birmingham", -1.90, 52.48, "GB", "B1", 0.03),
    ("Manchester", -2.24, 53.48, "GB", "M1", 0.03),
    # Outside the NW-European windstorm swath — the control group. If these show meaningful
    # loss under Kyrill, something is wrong with the footprint sampling.
    ("Madrid",     -3.70, 40.42, "ES", "28", 0.01),
    ("Milan",       9.19, 45.46, "IT", "20", 0.01),
]

OCCUPANCY = ["1050", "1100", "1200", "2100", "3000"]  # OED-ish office/retail/industrial
CONSTRUCTION = ["5000", "5100", "5200", "5950"]


def _clean_rows(rng: np.random.Generator, n: int) -> list[dict]:
    rows: list[dict] = []
    weights = np.array([c[5] for c in CITIES], dtype=float)
    weights /= weights.sum()
    picks = rng.choice(len(CITIES), size=n, p=weights)

    for i, ci in enumerate(picks, start=1):
        city, lon, lat, country, postal, _ = CITIES[ci]
        # Scatter within roughly a metro area (~15 km).
        jlon = lon + rng.normal(0, 0.12)
        jlat = lat + rng.normal(0, 0.08)

        # Lognormal TIVs: a few large risks dominating a long tail of small ones, which is
        # what a real commercial book looks like and what makes accumulation interesting.
        building = float(np.exp(rng.normal(14.8, 0.9)))
        rows.append(
            {
                "PortNumber": "DEMO-1",
                "AccNumber": f"ACC{1000 + int(ci)}",
                "LocNumber": f"LOC{i:05d}",
                "CountryCode": country,
                "PostalCode": f"{postal}{rng.integers(100, 999)}",
                "City": city,
                "Latitude": f"{jlat:.5f}",
                "Longitude": f"{jlon:.5f}",
                "BuildingTIV": f"{building:.0f}",
                "ContentsTIV": f"{building * rng.uniform(0.15, 0.45):.0f}",
                "BITIV": f"{building * rng.uniform(0.05, 0.30):.0f}",
                # Modest fixed-ish deductibles, as European windstorm cover actually carries.
                # A percentage-of-TIV deductible would swallow almost every windstorm loss —
                # true, but it would make the book look inert rather than realistic.
                "LocDed": f"{rng.choice([1000, 2500, 5000, 10000, 25000]):.0f}",
                "LocLimit": "" if rng.random() < 0.7 else f"{building * 0.8:.0f}",
                "OccupancyCode": str(rng.choice(OCCUPANCY)),
                "ConstructionCode": str(rng.choice(CONSTRUCTION)),
            }
        )
    return rows


def _dirty_rows(base: list[dict]) -> list[dict]:
    """Seed the specific problems the ingestion report is built to catch.

    Each corresponds to a branch in `data.ingest.oed_pipeline.ingest_oed_locations`.
    """
    d = [dict(r) for r in base[:12]]

    # ERROR: no coordinates and no geocoder wired yet — flagged, never invented.
    for r in d[0:2]:
        r["Latitude"] = r["Longitude"] = ""
    # ERROR: transposed lat/lon, a classic bordereau defect.
    d[2]["Latitude"] = "651.2"
    # ERROR: no insured value at all.
    for r in d[3:6]:
        r["BuildingTIV"] = r["ContentsTIV"] = r["BITIV"] = "0"
    # WARNING: outside the modelled European set — usable, but say so.
    d[6]["CountryCode"] = "US"
    d[7]["CountryCode"] = "ZZ"
    # WARNING: negative deductible, clamped.
    d[8]["LocDed"] = "-50000"
    d[9]["LocDed"] = "-1"
    # WARNING: non-positive limit, ignored.
    d[10]["LocLimit"] = "0"
    # ERROR: unparseable TIV — text where a number belongs.
    d[11]["BuildingTIV"] = "n/a"
    d[11]["ContentsTIV"] = d[11]["BITIV"] = ""

    for i, r in enumerate(d, start=1):
        r["LocNumber"] = f"DIRTY{i:03d}"
    return d


def _candidate_account() -> list[dict]:
    """A logistics portfolio squarely in the Kyrill swath — the what-if that lands hard."""
    rng = np.random.default_rng(SEED + 1)
    sites = [
        ("Duisburg",   6.76, 51.43),
        ("Essen",      7.01, 51.46),
        ("Cologne",    6.96, 50.94),
        ("Venlo",      6.17, 51.37),
        ("Eindhoven",  5.48, 51.44),
        ("Rotterdam",  4.48, 51.92),
        ("Antwerp",    4.40, 51.22),
        ("Ghent",      3.72, 51.05),
        ("Lille",      3.06, 50.63),
        ("Dover",      1.31, 51.13),
        ("Felixstowe", 1.35, 51.96),
        ("Hamburg",   10.00, 53.55),
    ]
    rows = []
    for i, (city, lon, lat) in enumerate(sites, start=1):
        country = (
            "NL" if city in {"Venlo", "Eindhoven", "Rotterdam"}
            else "BE" if city in {"Antwerp", "Ghent"}
            else "FR" if city == "Lille"
            else "GB" if city in {"Dover", "Felixstowe"}
            else "DE"
        )
        building = float(np.exp(rng.normal(16.6, 0.4)))  # big distribution sheds
        rows.append(
            {
                "PortNumber": "CAND-1",
                "AccNumber": "ACC-NEWCO-LOGISTICS",
                "LocNumber": f"CAND{i:03d}",
                "CountryCode": country,
                "PostalCode": "",
                "City": city,
                "Latitude": f"{lat:.5f}",
                "Longitude": f"{lon:.5f}",
                "BuildingTIV": f"{building:.0f}",
                "ContentsTIV": f"{building * 0.6:.0f}",
                "BITIV": f"{building * 0.35:.0f}",
                "LocDed": "25000",
                "LocLimit": "",
                "OccupancyCode": "3000",
                "ConstructionCode": "5200",
            }
        )
    return rows


def _write(path: str, rows: list[dict]) -> None:
    with open(path, "w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=COLUMNS)
        writer.writeheader()
        writer.writerows(rows)
    print(f"wrote {len(rows):>4} rows -> {path}")


def main() -> None:
    os.makedirs(OUT_DIR, exist_ok=True)
    rng = np.random.default_rng(SEED)

    clean = _clean_rows(rng, 488)
    book = clean + _dirty_rows(clean)
    # Scatter the bad rows through the file, as they arrive in reality.
    book = [book[i] for i in rng.permutation(len(book))]

    _write(os.path.join(OUT_DIR, "demo_book_oed.csv"), book)
    _write(os.path.join(OUT_DIR, "candidate_account_oed.csv"), _candidate_account())


if __name__ == "__main__":
    main()
