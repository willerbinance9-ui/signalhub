"""Signal ingest and status routes."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth import require_any_key, require_provider_key
from app.db import get_db
from app.models import SignalRow, utcnow
from app.schemas import SignalIn, SignalOut

router = APIRouter(prefix="/v1", tags=["signals"])

_OPEN_ACTIONS = {"open", "add"}
_FOLLOW_ACTIONS = {"close", "breakeven", "modify", "partial_close", "add"}


def _validate_body(body: SignalIn) -> None:
    action = body.action
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
    return SignalOut(
        id=row.id,
        external_id=row.external_id,
        status=row.status,
        payload=row.payload or {},
        result=row.result,
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
    response.status_code = status.HTTP_201_CREATED
    return _row_to_out(row)


@router.get("/signals/{signal_id}", response_model=SignalOut)
def get_signal(
    signal_id: str,
    provider_hash: str | None = Depends(require_any_key),
    db: Session = Depends(get_db),
):
    row = db.get(SignalRow, signal_id)
    if row is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "signal not found")
    if provider_hash and row.provider_key_hash != provider_hash:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "signal not found")
    return _row_to_out(row)
