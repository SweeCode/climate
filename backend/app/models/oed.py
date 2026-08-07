"""OED-aligned persistence schema (Postgres/PostGIS).

Mirrors the Open Exposure Data account/location hierarchy — the lingua franca of the
(re)insurance market — so portfolios round-trip without lossy remapping. Geometry is a
PostGIS point for fast spatial accumulation queries ("everything within this storm swath").

Requires the `[api]` extra (SQLAlchemy 2.0 + GeoAlchemy2). Table creation / migrations are
wired once the DB service is up (see infra/docker-compose.yml).
"""

from __future__ import annotations

from datetime import date, datetime

from geoalchemy2 import Geometry
from sqlalchemy import (
    DateTime,
    Float,
    ForeignKey,
    Integer,
    LargeBinary,
    String,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


class Portfolio(Base):
    __tablename__ = "portfolio"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(255))
    # Multi-tenant: every portfolio belongs to a tenant (SaaS). Enforced app-side for now.
    tenant_id: Mapped[str] = mapped_column(String(64), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    # The IngestionReport as returned at upload time, kept so the validation view survives a
    # page reload. Serialised shape mirrors data.ingest.oed_pipeline.IngestionReport.
    ingestion_report: Mapped[dict | None] = mapped_column(JSONB, nullable=True)

    locations: Mapped[list["LocationRow"]] = relationship(
        back_populates="portfolio", cascade="all, delete-orphan"
    )


class LocationRow(Base):
    """One insured location. Column names track OED where practical."""

    __tablename__ = "location"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    portfolio_id: Mapped[int] = mapped_column(ForeignKey("portfolio.id"), index=True)

    loc_number: Mapped[str] = mapped_column(String(64))  # OED LocNumber
    acc_number: Mapped[str | None] = mapped_column(String(64), nullable=True)  # OED AccNumber
    country_code: Mapped[str | None] = mapped_column(String(2), nullable=True)
    postal_code: Mapped[str | None] = mapped_column(String(16), nullable=True)

    # WGS84 point; SRID 4326. Spatial index created via GiST in migrations.
    geom: Mapped[object] = mapped_column(Geometry("POINT", srid=4326))

    building_tiv: Mapped[float] = mapped_column(Float, default=0.0)
    contents_tiv: Mapped[float] = mapped_column(Float, default=0.0)
    bi_tiv: Mapped[float] = mapped_column(Float, default=0.0)

    occupancy_code: Mapped[str | None] = mapped_column(String(16), nullable=True)
    construction_code: Mapped[str | None] = mapped_column(String(16), nullable=True)
    vuln_key: Mapped[str] = mapped_column(String(32), default="default")

    loc_ded: Mapped[float] = mapped_column(Float, default=0.0)
    loc_limit: Mapped[float | None] = mapped_column(Float, nullable=True)

    portfolio: Mapped[Portfolio] = relationship(back_populates="locations")

    @property
    def tiv(self) -> float:
        return (self.building_tiv or 0.0) + (self.contents_tiv or 0.0) + (self.bi_tiv or 0.0)


class StormFootprint(Base):
    """A historical windstorm gust footprint, stored as a raw grid blob.

    The grid lives here rather than on disk because the deployment target has an ephemeral
    filesystem (anything written to disk is lost on restart), and because hazard rasters are
    never committed to git. At the XWS catalogue's ~25 km resolution a European footprint is
    ~120 KB as float32, so the database is the simplest durable home for it. Higher-resolution
    products (Copernicus EWS at ~1.6 km) will outgrow this and want object storage.

    Grid geometry fields map 1:1 onto `engine.perils.windstorm.GriddedFootprint`.
    """

    __tablename__ = "storm_footprint"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    slug: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(128))
    year: Mapped[int] = mapped_column(Integer)
    event_date: Mapped[date | None] = mapped_column(nullable=True)
    notes: Mapped[str | None] = mapped_column(String(512), nullable=True)

    # float32, C-order, shape (n_rows, n_cols); row 0 at lat_top, col 0 at lon_left.
    grid: Mapped[bytes] = mapped_column(LargeBinary)
    n_rows: Mapped[int] = mapped_column(Integer)
    n_cols: Mapped[int] = mapped_column(Integer)
    lon_left: Mapped[float] = mapped_column(Float)
    lat_top: Mapped[float] = mapped_column(Float)
    cell_deg: Mapped[float] = mapped_column(Float)

    # CC BY 4.0 obliges attribution wherever the footprint is shown.
    source: Mapped[str] = mapped_column(String(255))
    licence: Mapped[str] = mapped_column(String(255))


class ScenarioRun(Base):
    """A portfolio's aggregate loss under one storm — the baseline a what-if is measured from.

    Persisting the total is what makes the underwriting wedge cheap *and* stateless: because
    scenario loss is additive across locations, a marginal-impact request only needs this
    number plus the candidate account's own loss. It never re-runs the book, and unlike an
    in-process cache it survives the container restarts a free-tier host guarantees.
    """

    __tablename__ = "scenario_run"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    portfolio_id: Mapped[int] = mapped_column(ForeignKey("portfolio.id"), index=True)
    storm_slug: Mapped[str] = mapped_column(String(64), index=True)

    n_locations: Mapped[int] = mapped_column(Integer)
    total_ground_up: Mapped[float] = mapped_column(Float)
    total_net: Mapped[float] = mapped_column(Float)
    computed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
