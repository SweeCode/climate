"""Request/response shapes for the underwriting API.

Deliberately thin: these mirror the engine and ingestion dataclasses rather than introducing
a second vocabulary for the same concepts.
"""

from __future__ import annotations

from datetime import date

from pydantic import BaseModel, Field

from data.ingest.oed_pipeline import IngestionReport


class StormOut(BaseModel):
    slug: str
    name: str
    year: int
    event_date: date | None
    notes: str | None
    bounds: list[float]  # [west, south, east, north]
    source: str
    licence: str


class IssueOut(BaseModel):
    row: int
    loc_id: str
    field: str
    severity: str
    message: str


class ReportOut(BaseModel):
    total_rows: int
    loaded: int
    n_errors: int
    n_warnings: int
    issues: list[IssueOut]

    @classmethod
    def from_report(cls, report: IngestionReport, max_issues: int = 200) -> "ReportOut":
        return cls(
            total_rows=report.total_rows,
            loaded=report.loaded,
            n_errors=len(report.errors),
            n_warnings=len(report.warnings),
            # Errors first: a broker looking at a rejected bordereau wants the blockers, and
            # a 50k-row file with 8k warnings should not ship 8k rows to the browser.
            issues=[
                IssueOut(
                    row=i.row,
                    loc_id=i.loc_id,
                    field=i.field,
                    severity=i.severity.value,
                    message=i.message,
                )
                for i in (report.errors + report.warnings)[:max_issues]
            ],
        )


class LocationOut(BaseModel):
    loc_id: str
    lon: float
    lat: float
    tiv: float


class PortfolioOut(BaseModel):
    id: int
    name: str
    n_locations: int
    total_tiv: float
    report: ReportOut
    locations: list[LocationOut]


class ScenarioRequest(BaseModel):
    storm_slug: str


class LocationLossOut(BaseModel):
    loc_id: str
    lon: float
    lat: float
    tiv: float
    gust_ms: float
    ground_up: float
    net: float


class ScenarioOut(BaseModel):
    storm_slug: str
    storm_name: str
    n_locations: int
    total_tiv: float
    total_ground_up: float
    total_net: float
    locations: list[LocationLossOut]
    compute_ms: float


class WhatIfRequest(BaseModel):
    storm_slug: str
    # Raw OED CSV text. Same pipeline as a portfolio upload, so a messy candidate account is
    # validated exactly like a messy book — pasted or dropped, one code path.
    csv_text: str = Field(min_length=1)
    account_name: str = "Candidate account"


class WhatIfOut(BaseModel):
    account_name: str
    storm_slug: str
    report: ReportOut
    candidate_tiv: float
    delta_ground_up: float
    delta_net: float
    portfolio_net_before: float
    portfolio_net_after: float
    pct_increase: float
    locations: list[LocationLossOut]
    compute_ms: float
