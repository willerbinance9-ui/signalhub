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


def deliver_webhook(url: str, body: dict, *, signal_id: str | None = None) -> None:
    """POST completion event to provider callback (best-effort)."""
    ok = False
    err = None
    try:
        r = httpx.post(url.strip(), json=body, timeout=15)
        if r.status_code >= 400:
            log.warning("webhook %s returned %s", url[:80], r.status_code)
            err = f"HTTP {r.status_code}"
        else:
            ok = True
            log.info("webhook delivered to %s event=%s", url[:80], body.get("event"))
    except Exception as exc:
        err = str(exc)[:200]
        log.warning("webhook delivery failed %s: %s", url[:80], exc)

    if signal_id:
        from app.db import SessionLocal
        from app.events import record_for_signal
        from app.models import SignalRow
        with SessionLocal() as db:
            row = db.get(SignalRow, signal_id)
            if row:
                record_for_signal(
                    db, row,
                    "webhook_sent" if ok else "webhook_failed",
                    f"Webhook {'delivered' if ok else 'failed'} to {url[:80]}",
                    detail={"callback_url": url[:200], "error": err, "event": body.get("event")},
                )
