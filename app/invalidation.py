"""Signal invalidation — provider marks setup dead; Quantum cancels pending orders."""
from __future__ import annotations

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.events import record_for_signal
from app.models import SignalRow, utcnow

INVALIDATED_STATUS = "invalidated"
_INVALIDATABLE = frozenset({"pending", "processing", "done"})


def invalidate_row(row: SignalRow, db: Session, *, reason: str = "") -> SignalRow:
    """Mark signal invalidated. Idempotent if already invalidated."""
    if row.status == INVALIDATED_STATUS:
        return row
    if row.status not in _INVALIDATABLE:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            f"cannot invalidate signal in status '{row.status}'",
        )

    why = (reason or "setup invalidated by provider").strip()[:500]
    prev = dict(row.result or {})
    setup_id = prev.get("setup_id")

    row.status = INVALIDATED_STATUS
    row.result = {
        **prev,
        "setup_id": setup_id,
        "log_action": "invalidated",
        "error": why,
        "invalidation_applied": False,
    }
    row.error_message = why
    row.updated_at = utcnow()
    db.commit()
    db.refresh(row)

    sym = (row.payload or {}).get("symbol") or "—"
    record_for_signal(
        db, row, "invalidated",
        f"Setup invalidated: {sym} — {why[:120]}",
        detail={"setup_id": setup_id, "reason": why},
    )
    return row


def needs_invalidation_processing(row: SignalRow) -> bool:
    if row.status != INVALIDATED_STATUS:
        return False
    result = row.result or {}
    return not result.get("invalidation_applied")
