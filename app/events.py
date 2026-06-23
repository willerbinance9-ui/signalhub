"""Record and query Signal Hub API activity."""
from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.event_log import SignalEventRow
from app.models import SignalRow


def _sender_from_payload(payload: dict | None) -> str | None:
    if not payload:
        return None
    sn = payload.get("sendername")
    return str(sn).strip() if sn else None


def record_event(
    db: Session,
    *,
    provider_key_hash: str,
    event: str,
    message: str,
    signal_id: str | None = None,
    sendername: str | None = None,
    detail: dict | None = None,
    commit: bool = True,
) -> None:
    row = SignalEventRow(
        signal_id=signal_id,
        provider_key_hash=provider_key_hash,
        sendername=(sendername or "").strip() or None,
        event=event,
        message=message[:2000],
        detail=detail,
    )
    db.add(row)
    if commit:
        db.commit()


def record_for_signal(
    db: Session,
    row: SignalRow,
    event: str,
    message: str,
    *,
    detail: dict | None = None,
    commit: bool = True,
) -> None:
    record_event(
        db,
        provider_key_hash=row.provider_key_hash,
        event=event,
        message=message,
        signal_id=row.id,
        sendername=_sender_from_payload(row.payload),
        detail=detail,
        commit=commit,
    )
