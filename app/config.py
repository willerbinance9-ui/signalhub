"""Signal Hub configuration from environment."""
from __future__ import annotations

import hashlib
from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    app_name: str = "AARE Signal Hub"
    database_url: str = "sqlite:///./signal_hub.db"
    provider_keys: str = ""   # comma-separated X-Provider-Key values
    consumer_key: str = ""    # X-Consumer-Key for Quantum
    quantum_bridge_url: str = ""  # Quantum VPS URL for live positions (e.g. http://host:8090)
    queue_batch_size: int = 20
    processing_timeout_seconds: int = 300


@lru_cache
def get_settings() -> Settings:
    return Settings()


def hash_key(key: str) -> str:
    return hashlib.sha256(key.strip().encode()).hexdigest()[:32]


def provider_keys_set() -> set[str]:
    raw = get_settings().provider_keys or ""
    return {k.strip() for k in raw.split(",") if k.strip()}


def verify_provider_key(key: str | None) -> str | None:
    """Return key hash if valid, else None."""
    if not key:
        return None
    k = key.strip()
    if k not in provider_keys_set():
        return None
    return hash_key(k)


def verify_consumer_key(key: str | None) -> bool:
    expected = (get_settings().consumer_key or "").strip()
    if not expected:
        return False
    return key is not None and key.strip() == expected
