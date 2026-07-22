"""OED (Open Exposure Data) location-file ingestion.

Turns a raw OED location file into engine `Location` objects plus an `IngestionReport`
that surfaces every problem it found instead of silently dropping or mispricing rows.

Scope of v1 (deliberately pragmatic, extended over time):
  * Parse the OED location columns we need for a windstorm scenario.
  * Validate coordinates, TIVs, and financial terms; classify issues by severity.
  * Compute TIV = BuildingTIV + ContentsTIV + BITIV.
  * Map OED occupancy/construction codes to a vulnerability cohort key (v1: single
    'default' cohort; the mapping table is where construction-specific curves plug in).
  * Geocoding is a hook (`geocode` callback) — real address->lat/lon comes later; for now
    rows without coordinates are flagged, not invented.

Works on any iterable of dict-like rows (so it is testable without a file); `from_csv`
reads a real OED CSV using only the standard library.
"""

from __future__ import annotations

import csv
from collections.abc import Callable, Iterable, Mapping
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional

from engine.scenario.core import Location

# OED location columns this pipeline reads (a small, extensible subset of the spec).
TIV_COLUMNS = ("BuildingTIV", "ContentsTIV", "BITIV")

# European country codes we currently model (ISO-3166-1 alpha-2). Rows outside get warned.
KNOWN_COUNTRIES = {
    "GB", "IE", "FR", "DE", "NL", "BE", "LU", "DK", "SE", "NO", "FI", "PL",
    "CZ", "AT", "CH", "ES", "PT", "IT", "SI", "SK", "HU",
}

Geocoder = Callable[[Mapping[str, str]], Optional[tuple[float, float]]]


class Severity(str, Enum):
    ERROR = "error"  # row cannot be used in a scenario
    WARNING = "warning"  # row is usable but suspect


@dataclass
class ValidationIssue:
    row: int  # 1-based row number in the source file
    loc_id: str
    field: str
    severity: Severity
    message: str


@dataclass
class IngestionReport:
    total_rows: int = 0
    loaded: int = 0
    issues: list[ValidationIssue] = field(default_factory=list)

    def add(self, issue: ValidationIssue) -> None:
        self.issues.append(issue)

    @property
    def errors(self) -> list[ValidationIssue]:
        return [i for i in self.issues if i.severity is Severity.ERROR]

    @property
    def warnings(self) -> list[ValidationIssue]:
        return [i for i in self.issues if i.severity is Severity.WARNING]

    def summary(self) -> str:
        return (
            f"{self.loaded}/{self.total_rows} locations loaded, "
            f"{len(self.errors)} errors, {len(self.warnings)} warnings"
        )


def _to_float(value: Optional[str]) -> Optional[float]:
    if value is None:
        return None
    value = value.strip()
    if value == "":
        return None
    try:
        return float(value)
    except ValueError:
        return None


def _vuln_key(row: Mapping[str, str]) -> str:
    """Map OED occupancy/construction to a vulnerability cohort.

    v1 collapses everything to 'default' (single blended windstorm curve). This is the
    seam where construction-code-specific curves get introduced without touching callers.
    """
    return "default"


def ingest_oed_locations(
    rows: Iterable[Mapping[str, str]],
    geocode: Optional[Geocoder] = None,
) -> tuple[list[Location], IngestionReport]:
    """Ingest OED location rows into engine Locations + a validation report.

    A row becomes a usable Location only if it has valid coordinates and a positive TIV;
    otherwise it is recorded as an ERROR and skipped. Suspect-but-usable conditions
    (unknown country, missing deductible) are WARNINGs.
    """
    report = IngestionReport()
    locations: list[Location] = []

    for i, row in enumerate(rows, start=1):
        report.total_rows += 1
        loc_id = (row.get("LocNumber") or row.get("LocID") or f"row{i}").strip()

        # --- coordinates -------------------------------------------------------------
        lat = _to_float(row.get("Latitude"))
        lon = _to_float(row.get("Longitude"))
        if (lat is None or lon is None) and geocode is not None:
            coords = geocode(row)
            if coords is not None:
                lat, lon = coords
        if lat is None or lon is None:
            report.add(ValidationIssue(i, loc_id, "Latitude/Longitude", Severity.ERROR,
                                       "missing coordinates and geocoding failed"))
            continue
        if not (-90 <= lat <= 90) or not (-180 <= lon <= 180):
            report.add(ValidationIssue(i, loc_id, "Latitude/Longitude", Severity.ERROR,
                                       f"coordinates out of range ({lat}, {lon})"))
            continue

        # --- TIV ----------------------------------------------------------------------
        tiv_parts = [_to_float(row.get(col)) or 0.0 for col in TIV_COLUMNS]
        tiv = sum(tiv_parts)
        if tiv <= 0:
            report.add(ValidationIssue(i, loc_id, "TIV", Severity.ERROR,
                                       "total insured value is zero or missing"))
            continue

        # --- country (warn only) ------------------------------------------------------
        country = (row.get("CountryCode") or "").strip().upper()
        if country and country not in KNOWN_COUNTRIES:
            report.add(ValidationIssue(i, loc_id, "CountryCode", Severity.WARNING,
                                       f"country '{country}' outside modelled European set"))

        # --- financial terms ----------------------------------------------------------
        deductible = _to_float(row.get("LocDed")) or 0.0
        limit = _to_float(row.get("LocLimit"))
        if limit is not None and limit <= 0:
            report.add(ValidationIssue(i, loc_id, "LocLimit", Severity.WARNING,
                                       "non-positive limit ignored"))
            limit = None
        if deductible < 0:
            report.add(ValidationIssue(i, loc_id, "LocDed", Severity.WARNING,
                                       "negative deductible clamped to 0"))
            deductible = 0.0

        locations.append(
            Location(
                loc_id=loc_id,
                lon=lon,
                lat=lat,
                tiv=tiv,
                vuln_key=_vuln_key(row),
                deductible=deductible,
                limit=limit,
            )
        )
        report.loaded += 1

    return locations, report


def from_csv(path: str, geocode: Optional[Geocoder] = None):
    """Read an OED location CSV and ingest it. Standard-library only."""
    with open(path, newline="", encoding="utf-8-sig") as fh:
        reader = csv.DictReader(fh)
        return ingest_oed_locations(reader, geocode=geocode)
