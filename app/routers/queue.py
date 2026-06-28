"""Consumer queue routes for AARE Quantum."""
from __future__ import annotations

from datetime import timedelta

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth import require_consumer_key
from app.config import get_settings
from app.db import get_db
from app.events import record_for_signal
from app.models import SignalRow, utcnow
from app.progress import build_progress
from app.schemas import AckIn, AckOut, PendingOut, SignalOut, SignalProgress
from app.webhooks import deliver_webhook, webhook_payload

router = APIRouter(prefix="/v1/queue", tags=["queue"])


def _row_to_out(row: SignalRow) -> SignalOut:
    prog = build_progress(row)
    return SignalOut(
        id=row.id,
        external_id=row.external_id,
        status=row.status,
        payload=row.payload or {},
        result=row.result,
        progress=SignalProgress(**prog),
        created_at=row.created_at,
        acked_at=row.acked_at,
    )


@router.get("/pending", response_model=PendingOut)
def list_pending(
    _: None = Depends(require_consumer_key),
    db: Session = Depends(get_db),
):
    settings = get_settings()
    cutoff = utcnow() - timedelta(seconds=settings.processing_timeout_seconds)

    # Re-queue stale processing rows
    stale = db.execute(
        select(SignalRow).where(
            SignalRow.status == "processing",
            SignalRow.updated_at < cutoff,
        )
    ).scalars().all()
    for row in stale:
        if row.status == "invalidated":
            continue
        if (row.result or {}).get("setup_id"):
            row.status = "done"
            row.updated_at = utcnow()
            continue
        row.status = "pending"
        row.updated_at = utcnow()
    if stale:
        db.commit()

    rows = db.execute(
        select(SignalRow)
        .where(SignalRow.status == "pending")
        .order_by(SignalRow.created_at.asc())
        .limit(settings.queue_batch_size)
    ).scalars().all()

    for row in rows:
        row.status = "processing"
        row.updated_at = utcnow()
    if rows:
        db.commit()
        for row in rows:
            db.refresh(row)
            payload = row.payload or {}
            sym = payload.get("symbol") or "—"
            record_for_signal(
                db, row, "processing",
                f"Quantum picked up: {payload.get('action', 'open')} {sym}",
                detail={"consumer": "quantum"},
                commit=True,
            )

    items = [_row_to_out(r) for r in rows]
    return PendingOut(items=items, count=len(items))


@router.get("/recent", response_model=PendingOut)
def list_recent(
    limit: int = 50,
    _: None = Depends(require_consumer_key),
    db: Session = Depends(get_db),
):
    """Read-only recent signals for Quantum dashboard (does not change status)."""
    lim = max(1, min(limit, 100))
    rows = db.execute(
        select(SignalRow)
        .order_by(SignalRow.created_at.desc())
        .limit(lim)
    ).scalars().all()
    items = [_row_to_out(r) for r in rows]
    return PendingOut(items=items, count=len(items))


@router.get("/invalidations", response_model=PendingOut)
def list_invalidations(
    limit: int = Query(50, ge=1, le=100),
    _: None = Depends(require_consumer_key),
    db: Session = Depends(get_db),
):
    """
    Invalidated signals waiting for Quantum to cancel pending orders.

    Poll every scan cycle; ack each with POST /v1/queue/{id}/invalidate-ack when processed.
    """
    from app.invalidation import needs_invalidation_processing

    rows = db.execute(
        select(SignalRow)
        .where(SignalRow.status == "invalidated")
        .order_by(SignalRow.updated_at.asc())
        .limit(limit * 3)
    ).scalars().all()
    pending = [r for r in rows if needs_invalidation_processing(r)][:limit]
    items = [_row_to_out(r) for r in pending]
    return PendingOut(items=items, count=len(items))


@router.post("/{signal_id}/invalidate-ack", response_model=AckOut)
def ack_invalidation(
    signal_id: str,
    _: None = Depends(require_consumer_key),
    db: Session = Depends(get_db),
):
    """Quantum confirms pending orders were cancelled for an invalidated signal."""
    row = db.get(SignalRow, signal_id)
    if row is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "signal not found")
    if row.status != "invalidated":
        raise HTTPException(status.HTTP_409_CONFLICT, "signal is not invalidated")

    result = dict(row.result or {})
    result["invalidation_applied"] = True
    row.result = result
    row.updated_at = utcnow()
    db.commit()
    record_for_signal(
        db, row, "invalidation_applied",
        "Quantum cancelled pending orders for invalidated setup",
        detail={"setup_id": result.get("setup_id")},
    )
    return AckOut(id=signal_id, status=row.status, ok=True)


@router.post("/{signal_id}/ack", response_model=AckOut)
def ack_signal(
    signal_id: str,
    body: AckIn,
    background_tasks: BackgroundTasks,
    _: None = Depends(require_consumer_key),
    db: Session = Depends(get_db),
):
    row = db.get(SignalRow, signal_id)
    if row is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "signal not found")

    if row.status in ("done", "failed") and row.acked_at:
        if body.log_action in ("executed", "ea_failed") and row.status == "done":
            row.result = {
                "setup_id": body.setup_id or (row.result or {}).get("setup_id"),
                "log_action": body.log_action,
                "error": body.error,
            }
            row.updated_at = utcnow()
            db.commit()
        return AckOut(id=signal_id, status=row.status, ok=True)

    row.status = "done" if body.status == "done" else "failed"
    row.result = {
        "setup_id": body.setup_id,
        "log_action": body.log_action,
        "error": body.error,
    }
    row.error_message = body.error
    row.acked_at = utcnow()
    row.updated_at = utcnow()
    db.commit()
    db.refresh(row)

    evt = "executed" if row.status == "done" else "failed"
    msg = body.error or f"Ack {body.log_action or row.status}"
    if row.status == "done" and body.log_action:
        msg = f"Completed: {body.log_action}"
    record_for_signal(
        db, row, evt, msg,
        detail={
            "setup_id": body.setup_id,
            "log_action": body.log_action,
            "error": body.error,
        },
    )

    callback = (row.payload or {}).get("callback_url")
    if callback:
        event = "signal.done" if row.status == "done" else "signal.failed"
        payload = webhook_payload(row, event=event)
        background_tasks.add_task(deliver_webhook, callback.strip(), payload, signal_id=row.id)

    return AckOut(id=signal_id, status=row.status, ok=True)
