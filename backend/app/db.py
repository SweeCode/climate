"""Database engine, session, and first-run schema setup. Requires the `[api]` extra.

Deliberately no Alembic yet: there are four tables and no production data, so `create_all`
is the honest amount of machinery. Migrations start earning their keep the day a customer's
portfolio is in here — that is the trigger to add them, not a milestone number.
"""

from __future__ import annotations

from collections.abc import Iterator

from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session, sessionmaker

from backend.app.config import settings
from backend.app.models.oed import Base

engine = create_engine(settings.database_url, pool_pre_ping=True)
SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


def init_db() -> None:
    """Create the PostGIS extension, the tables, and the spatial index. Idempotent."""
    with engine.begin() as conn:
        conn.execute(text("CREATE EXTENSION IF NOT EXISTS postgis"))

    Base.metadata.create_all(engine)

    with engine.begin() as conn:
        conn.execute(
            text("CREATE INDEX IF NOT EXISTS ix_location_geom ON location USING GIST (geom)")
        )


def get_session() -> Iterator[Session]:
    """FastAPI dependency yielding a session per request."""
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()
