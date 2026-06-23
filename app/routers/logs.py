"""Provider-facing API activity log routes."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth import require_provider_key
from app.db import get_db
from app.event_log import SignalEventRow
from app.schemas import SignalEventOut, SignalEventListOut

router = APIRouter(prefix="/v1", tags=["logs"])


@router.get("/logs", response_model=SignalEventListOut)
def list_api_logs(
    sendername: str = Query(..., min_length=1, max_length=64,
                            description="Required — only events for this sender"),
    signal_id: str | None = Query(None, max_length=36),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    provider_hash: str = Depends(require_provider_key),
    db: Session = Depends(get_db),
):
    """Activity log for signals submitted by one sender (POST, poll, ack, webhook)."""
    sn = sendername.strip()
    q = select(SignalEventRow).where(
        SignalEventRow.provider_key_hash == provider_hash,
        SignalEventRow.sendername == sn,
    )
    if signal_id:
        q = q.where(SignalEventRow.signal_id == signal_id.strip())
    q = q.order_by(SignalEventRow.created_at.desc()).offset(offset).limit(limit)
    rows = db.execute(q).scalars().all()
    items = [
        SignalEventOut(
            id=r.id,
            signal_id=r.signal_id,
            sendername=r.sendername,
            event=r.event,
            message=r.message,
            detail=r.detail,
            created_at=r.created_at,
        )
        for r in rows
    ]
    return SignalEventListOut(items=items, count=len(items), sendername=sn)
