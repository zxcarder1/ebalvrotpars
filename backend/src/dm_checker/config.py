"""Application configuration models."""

from __future__ import annotations

from pathlib import Path
from typing import List, Optional

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class DatabaseSettings(BaseSettings):
    """Database connectivity settings."""

    dsn: str = Field(
        default="sqlite+aiosqlite:///./dm_checker.db",
        description="SQLAlchemy DSN for the metadata store.",
    )
    echo: bool = False
    migrations_path: Path = Field(default=Path("backend/alembic"))

    model_config = SettingsConfigDict(env_prefix="DM_DB_")


class ConcurrencySettings(BaseSettings):
    """Controls worker parallelism limits."""

    global_limit: int = Field(default=200)
    per_token_limit: int = Field(default=2)
    per_proxy_limit: int = Field(default=8)
    request_timeout: float = Field(default=30.0)
    connect_timeout: float = Field(default=10.0)
    retry_attempts: int = Field(default=5)
    retry_backoff_base: float = Field(default=1.5)
    retry_backoff_max: float = Field(default=300.0)

    model_config = SettingsConfigDict(env_prefix="DM_CONC_")


class RatePlan(BaseSettings):
    """Per-token dynamic rate plan defaults."""

    initial_rps: float = Field(default=1 / 60)
    min_rps: float = Field(default=1 / 600)
    max_rps: float = Field(default=5.0)
    cooldown_seconds: float = Field(default=300.0)
    burst_capacity: int = Field(default=4)

    model_config = SettingsConfigDict(env_prefix="DM_RATE_")


class ProxySettings(BaseSettings):
    """Proxy system configuration."""

    rotation_strategy: str = Field(default="round_robin")
    healthcheck_interval: float = Field(default=300.0)

    model_config = SettingsConfigDict(env_prefix="DM_PROXY_")


class MetricsSettings(BaseSettings):
    """Metrics and observability configuration."""

    enable_prometheus: bool = Field(default=True)
    prometheus_host: str = Field(default="0.0.0.0")
    prometheus_port: int = Field(default=9310)

    model_config = SettingsConfigDict(env_prefix="DM_METRICS_")


class AppSettings(BaseSettings):
    """Top level configuration."""

    database: DatabaseSettings = DatabaseSettings()
    concurrency: ConcurrencySettings = ConcurrencySettings()
    rate_plan: RatePlan = RatePlan()
    proxies: ProxySettings = ProxySettings()
    metrics: MetricsSettings = MetricsSettings()
    data_dir: Path = Field(default=Path("./data"))
    export_dir: Path = Field(default=Path("./exports"))
    resume_on_start: bool = Field(default=True)
    skip_duplicates: bool = Field(default=True)
    daily_target: int = Field(default=300_000)

    account_ttl_hours: int = Field(default=24)
    log_level: str = Field(default="INFO")
    ui_allowed_origins: List[str] = Field(default_factory=lambda: ["http://localhost:1420"])

    model_config = SettingsConfigDict(env_prefix="DM_APP_", env_nested_delimiter="__")


def load_settings(env_file: Optional[Path] = None) -> AppSettings:
    """Load settings, optionally from a .env file."""

    if env_file:
        return AppSettings(_env_file=str(env_file))
    return AppSettings()
