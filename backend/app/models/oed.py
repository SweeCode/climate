"""OED-aligned persistence schema (Postgres/PostGIS).

Mirrors the Open Exposure Data account/location hierarchy — the lingua franca of the
(re)insurance market — so portfolios round-trip without lossy remapping. Geometry is a
PostGIS point for fast spatial accumulation queries ("everything within this storm swath").

Requires the `[api]` extra (SQLAlchemy 2.0 + GeoAlchemy2). Table creation / migrations are
wired once the DB service is up (see infra/docker-compose.yml).
"""

from __future__ import annotations

from geoalchemy2 import Geometry
from sqlalchemy import Float, ForeignKey, Integer, String
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


class Portfolio(Base):
    __tablename__ = "portfolio"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(255))
    # Multi-tenant: every portfolio belongs to a tenant (SaaS). Enforced app-side for now.
    tenant_id: Mapped[str] = mapped_column(String(64), index=True)

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
