"""Sender performance report — proxied from Quantum."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.auth import require_provider_key
from app.quantum_bridge import bridge_configured, sender_report
from app.schemas import SenderReportOut

router = APIRouter(prefix="/v1", tags=["analytics"])


def _require_bridge():
    if not bridge_configured():
        raise HTTPException(
            status.HTTP_503_SERVICE_UNAVAILABLE,
            "Sender report requires QUANTUM_BRIDGE_URL on Signal Hub",
        )


@router.get("/senders/report", response_model=SenderReportOut)
def get_sender_report(
    days: int = Query(90, ge=7, le=365),
    provider_hash: str = Depends(require_provider_key),
):
    """Rank signal senders by volume with win rate on closed trades (MT5 comment QTE {sender})."""
    _require_bridge()
    try:
        data = sender_report(days=days)
    except RuntimeError as exc:
        raise HTTPException(status.HTTP_502_BAD_GATEWAY, str(exc)) from exc
    return SenderReportOut(**data)
