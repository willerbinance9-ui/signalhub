"""Consumer queue routes for AARE Quantum."""
from __future__ import annotations

from datetime import timedelta

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth import require_consumer_key
from app.config import get_settings
from app.db import get_db
from app.models import SignalRow, utcnow
from app.schemas import AckIn, AckOut, PendingOut, SignalOut

router = APIRouter(prefix="/v1/queue", tags=["queue"])


def _row_to_out(row: SignalRow) -> SignalOut:
    return SignalOut(
        id=row.id,
        external_id=row.external_id,
        status=row.status,
        payload=row.payload or {},
        result=row.result,
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

    items = [_row_to_out(r) for r in rows]
    return PendingOut(items=items, count=len(items))


@router.post("/{signal_id}/ack", response_model=AckOut)
def ack_signal(
    signal_id: str,
    body: AckIn,
    _: None = Depends(require_consumer_key),
    db: Session = Depends(get_db),
):
    row = db.get(SignalRow, signal_id)
    if row is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "signal not found")

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
    return AckOut(id=signal_id, status=row.status, ok=True)
