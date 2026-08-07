"""Application settings (env-driven). Requires the `[api]` extra."""

from __future__ import annotations

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_prefix="CLIMATE_")

    database_url: str = "postgresql+psycopg2://climate:climate@localhost:5432/climate"
    hazard_dir: str = "data/hazard"

    # Shared code gating the hosted demo. This is a doormat, not a lock — it keeps the demo
    # from being casually crawled, and is NOT authentication. Real client bordereaux must not
    # be uploaded to an environment protected only by this.
    demo_access_code: str = ""

    # Directory holding the built React bundle, mounted at / when present.
    frontend_dist: str = "frontend/dist"


settings = Settings()
