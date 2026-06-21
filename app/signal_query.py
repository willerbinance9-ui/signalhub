"""Query helpers for signal listing."""
from __future__ import annotations

from sqlalchemy import Select, func

from app.config import get_settings
from app.models import SignalRow


def _payload_sendername_expr():
    url = get_settings().database_url
    if url.startswith("sqlite"):
        return func.json_extract(SignalRow.payload, "$.sendername")
    return SignalRow.payload["sendername"].astext


def apply_sendername_filter(q: Select, sendername: str) -> Select:
    sn = sendername.strip()
    return q.where(_payload_sendername_expr() == sn)


def row_sendername(row: SignalRow) -> str | None:
    payload = row.payload or {}
    sn = payload.get("sendername")
    return str(sn).strip() if sn else None


def assert_sender_access(row: SignalRow, sendername: str | None) -> None:
    """404 if sendername filter does not match this row."""
    if not sendername:
        return
    expected = sendername.strip()
    actual = row_sendername(row)
    if actual != expected:
        from fastapi import HTTPException, status
        raise HTTPException(status.HTTP_404_NOT_FOUND, "signal not found")
