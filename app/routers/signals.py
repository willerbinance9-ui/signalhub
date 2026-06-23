"""Signal ingest and status routes."""
from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth import require_any_key, require_provider_key
from app.db import get_db
from app.events import record_event, record_for_signal
from app.models import SignalRow
from app.progress import build_progress
from app.schemas import SignalIn, SignalListOut, SignalOut, SignalProgress
from app.signal_query import apply_sendername_filter, assert_sender_access

router = APIRouter(prefix="/v1", tags=["signals"])

_OPEN_ACTIONS = {"open", "add"}
_FOLLOW_ACTIONS = {"close", "breakeven", "modify", "partial_close", "add"}
_VALID_STATUSES = {"pending", "processing", "done", "failed"}


def _validate_body(body: SignalIn) -> None:
    action = body.action
    if body.callback_url:
        url = body.callback_url.strip().lower()
        if not (url.startswith("https://") or url.startswith("http://127.0.0.1")
                or url.startswith("http://localhost")):
            raise HTTPException(
                status.HTTP_422_UNPROCESSABLE_ENTITY,
                "callback_url must be https (or localhost for dev)",
            )
    if action == "close_all":
        return
    if action in _OPEN_ACTIONS:
        if not body.symbol:
            raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "symbol required for open/add")
        if not body.direction:
            raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "direction required for open/add")
    elif action in _FOLLOW_ACTIONS and not body.symbol and not body.ticket:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            "symbol or ticket required for follow-up actions",
        )


def _row_to_out(row: SignalRow, *, duplicate: bool = False) -> SignalOut:
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
        duplicate=duplicate,
    )


@router.post("/signals", response_model=SignalOut)
def create_signal(
    body: SignalIn,
    response: Response,
    provider_hash: str = Depends(require_provider_key),
    db: Session = Depends(get_db),
):
    _validate_body(body)
    ext = (body.external_id or "").strip() or None

    if ext:
        existing = db.execute(
            select(SignalRow).where(
                SignalRow.provider_key_hash == provider_hash,
                SignalRow.external_id == ext,
            )
        ).scalar_one_or_none()
        if existing:
            record_for_signal(
                db, existing, "duplicate",
                f"Duplicate POST for external_id={ext}",
                detail={"external_id": ext},
            )
            response.status_code = status.HTTP_200_OK
            return _row_to_out(existing, duplicate=True)

    payload = body.model_dump(exclude_none=False)
    row = SignalRow(
        provider_key_hash=provider_hash,
        external_id=ext,
        payload=payload,
        status="pending",
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    sym = body.symbol or "—"
    who = body.sendername or "unknown"
    record_for_signal(
        db, row, "created",
        f"Signal queued: {body.action} {sym} by {who}",
        detail={"external_id": ext, "action": body.action, "symbol": body.symbol},
    )
    response.status_code = status.HTTP_201_CREATED
    return _row_to_out(row)


@router.get("/signals", response_model=SignalListOut)
def list_signals(
    sendername: str = Query(..., min_length=1, max_length=64,
                            description="Required — only signals posted by this sender"),
    status_filter: str | None = Query(None, alias="status", max_length=20),
    external_id: str | None = Query(None, max_length=128),
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
    since: datetime | None = Query(None, description="ISO datetime — only signals created after this time"),
    provider_hash: str = Depends(require_provider_key),
    db: Session = Depends(get_db),
):
    """List signals for the authenticated provider, scoped to one sender."""
    sn = sendername.strip()
    q = select(SignalRow).where(SignalRow.provider_key_hash == provider_hash)
    q = apply_sendername_filter(q, sn)

    if status_filter:
        st = status_filter.strip().lower()
        if st not in _VALID_STATUSES:
            raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, f"invalid status: {st}")
        q = q.where(SignalRow.status == st)
    if external_id:
        q = q.where(SignalRow.external_id == external_id.strip())
    if since:
        q = q.where(SignalRow.created_at >= since)

    q = q.order_by(SignalRow.created_at.desc()).offset(offset).limit(limit)
    rows = db.execute(q).scalars().all()
    items = [_row_to_out(r) for r in rows]
    return SignalListOut(items=items, count=len(items), sendername=sn)


@router.get("/signals/external/{external_id}", response_model=SignalOut)
def get_signal_by_external_id(
    external_id: str,
    sendername: str = Query(..., min_length=1, max_length=64),
    provider_hash: str = Depends(require_provider_key),
    db: Session = Depends(get_db),
):
    """Lookup by your platform message ID — sender must match."""
    ext = external_id.strip()
    sn = sendername.strip()
    q = select(SignalRow).where(
        SignalRow.provider_key_hash == provider_hash,
        SignalRow.external_id == ext,
    )
    q = apply_sendername_filter(q, sn)
    row = db.execute(q).scalar_one_or_none()
    if row is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "signal not found")
    return _row_to_out(row)


@router.get("/signals/{signal_id}", response_model=SignalOut)
def get_signal(
    signal_id: str,
    sendername: str | None = Query(None, max_length=64,
                                   description="When set, returns 404 unless signal belongs to this sender"),
    provider_hash: str | None = Depends(require_any_key),
    db: Session = Depends(get_db),
):
    row = db.get(SignalRow, signal_id)
    if row is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "signal not found")
    if provider_hash and row.provider_key_hash != provider_hash:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "signal not found")
    if provider_hash and sendername:
        assert_sender_access(row, sendername)
    return _row_to_out(row)
