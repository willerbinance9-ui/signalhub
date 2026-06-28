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
    sort: str = Query(
        "profit",
        description="profit | win_rate | signals | profit_factor | expectancy",
    ),
    min_closed_trades: int = Query(0, ge=0, le=500),
    limit: int = Query(50, ge=1, le=200),
    provider_hash: str = Depends(require_provider_key),
):
    """Sender leaderboard from Quantum — default sort is net P/L."""
    _require_bridge()
    try:
        data = sender_report(
            days=days,
            sort=sort,
            min_closed_trades=min_closed_trades,
            limit=limit,
        )
    except RuntimeError as exc:
        raise HTTPException(status.HTTP_502_BAD_GATEWAY, str(exc)) from exc
    return SenderReportOut(**data)


@router.get("/senders/profitability", response_model=SenderReportOut)
def get_sender_profitability(
    days: int = Query(90, ge=7, le=365),
    min_closed_trades: int = Query(1, ge=1, le=500),
    limit: int = Query(50, ge=1, le=200),
    provider_hash: str = Depends(require_provider_key),
):
    """Senders with closed trades only, ranked by net profit (rank 1 = best)."""
    _require_bridge()
    try:
        from app.quantum_bridge import sender_profitability
        data = sender_profitability(
            days=days, min_closed_trades=min_closed_trades, limit=limit,
        )
    except RuntimeError as exc:
        raise HTTPException(status.HTTP_502_BAD_GATEWAY, str(exc)) from exc
    return SenderReportOut(**data)


@router.get("/bridge/status")
def quantum_bridge_status(
    provider_hash: str = Depends(require_provider_key),
):
    """
    Verify QUANTUM_BRIDGE_URL reaches your Quantum VPS (MT5 host).

    Use after deploy to confirm Render can pull sender reports and quotes.
    """
    from app.quantum_bridge import ping_quantum
    return ping_quantum()
