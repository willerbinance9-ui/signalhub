"""Proxy calls to Quantum VPS for sender-scoped positions."""
from __future__ import annotations

import logging

import httpx

from app.config import get_settings

log = logging.getLogger("signal_hub.quantum_bridge")


def _bridge_config() -> tuple[str, str]:
    settings = get_settings()
    url = (settings.quantum_bridge_url or "").strip().rstrip("/")
    key = (settings.consumer_key or "").strip()
    return url, key


def bridge_configured() -> bool:
    url, key = _bridge_config()
    return bool(url and key)


def _headers() -> dict[str, str]:
    _, key = _bridge_config()
    return {"X-Consumer-Key": key}


def _request(method: str, path: str, *, params: dict | None = None) -> dict:
    url, key = _bridge_config()
    if not url or not key:
        raise RuntimeError("QUANTUM_BRIDGE_URL and CONSUMER_KEY must be set on Signal Hub")
    full = f"{url}{path}"
    try:
        r = httpx.request(method, full, headers=_headers(), params=params, timeout=30)
        r.raise_for_status()
        return r.json()
    except httpx.HTTPStatusError as exc:
        detail = exc.response.text[:300] if exc.response else str(exc)
        log.warning("quantum bridge %s %s -> %s", method, path, detail)
        raise RuntimeError(detail or f"Quantum bridge HTTP {exc.response.status_code}") from exc
    except Exception as exc:
        log.warning("quantum bridge %s %s failed: %s", method, path, exc)
        raise RuntimeError(str(exc)[:300]) from exc


def list_positions(sendername: str) -> dict:
    return _request("GET", "/v1/hub/positions", params={"sendername": sendername})


def close_position(sendername: str, ticket: int) -> dict:
    return _request(
        "POST",
        f"/v1/hub/positions/{ticket}/close",
        params={"sendername": sendername},
    )


def close_all_positions(sendername: str) -> dict:
    return _request(
        "POST",
        "/v1/hub/positions/close-all",
        params={"sendername": sendername},
    )
