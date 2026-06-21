"""Optional provider webhooks when a signal finishes processing."""
from __future__ import annotations

import logging

import httpx

from app.models import SignalRow
from app.progress import build_progress

log = logging.getLogger("signal_hub.webhooks")


def webhook_payload(row: SignalRow, *, event: str) -> dict:
    payload = row.payload or {}
    return {
        "event": event,
        "id": row.id,
        "external_id": row.external_id,
        "status": row.status,
        "sendername": payload.get("sendername"),
        "action": payload.get("action"),
        "symbol": payload.get("symbol"),
        "direction": payload.get("direction"),
        "progress": build_progress(row),
        "result": row.result,
        "created_at": row.created_at.isoformat() if row.created_at else None,
        "acked_at": row.acked_at.isoformat() if row.acked_at else None,
    }


def deliver_webhook(url: str, body: dict) -> None:
    """POST completion event to provider callback (best-effort)."""
    try:
        r = httpx.post(url.strip(), json=body, timeout=15)
        if r.status_code >= 400:
            log.warning("webhook %s returned %s", url[:80], r.status_code)
        else:
            log.info("webhook delivered to %s event=%s", url[:80], body.get("event"))
    except Exception as exc:
        log.warning("webhook delivery failed %s: %s", url[:80], exc)
