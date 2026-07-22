"""Application settings (env-driven). Requires the `[api]` extra."""

from __future__ import annotations

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_prefix="CLIMATE_")

    database_url: str = "postgresql+psycopg2://climate:climate@localhost:5432/climate"
    hazard_dir: str = "data/hazard"


settings = Settings()
