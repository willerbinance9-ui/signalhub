"""API key authentication."""
from __future__ import annotations

from fastapi import Header, HTTPException, status

from app.config import verify_consumer_key, verify_provider_key


def require_provider_key(x_provider_key: str | None = Header(None)) -> str:
    h = verify_provider_key(x_provider_key)
    if not h:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid or missing X-Provider-Key")
    return h


def require_consumer_key(x_consumer_key: str | None = Header(None)) -> None:
    if not verify_consumer_key(x_consumer_key):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid or missing X-Consumer-Key")


def require_any_key(
    x_provider_key: str | None = Header(None),
    x_consumer_key: str | None = Header(None),
) -> str | None:
    """Provider hash or consumer access for read endpoints."""
    if verify_consumer_key(x_consumer_key):
        return None
    h = verify_provider_key(x_provider_key)
    if h:
        return h
    raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid API key")
