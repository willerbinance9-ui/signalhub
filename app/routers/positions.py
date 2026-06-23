"""Sender-scoped live positions (proxied to Quantum MT5)."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.auth import require_provider_key
from app.quantum_bridge import bridge_configured, close_all_positions, close_position, list_positions
from app.schemas import PositionCloseAllOut, PositionCloseOut, PositionListOut

router = APIRouter(prefix="/v1", tags=["positions"])


def _require_bridge():
    if not bridge_configured():
        raise HTTPException(
            status.HTTP_503_SERVICE_UNAVAILABLE,
            "Position API requires QUANTUM_BRIDGE_URL on Signal Hub (your Quantum VPS URL)",
        )


@router.get("/positions", response_model=PositionListOut)
def get_sender_positions(
    sendername: str = Query(..., min_length=1, max_length=64,
                            description="Required — only positions opened by this sender"),
    provider_hash: str = Depends(require_provider_key),
):
    """List open MT5 positions for one sender (matched by order comment QTE {sendername})."""
    _require_bridge()
    sn = sendername.strip()
    try:
        data = list_positions(sn)
    except RuntimeError as exc:
        raise HTTPException(status.HTTP_502_BAD_GATEWAY, str(exc)) from exc
    return PositionListOut(
        sendername=data.get("sendername") or sn,
        count=data.get("count", 0),
        items=data.get("items") or [],
    )


@router.post("/positions/{ticket}/close", response_model=PositionCloseOut)
def close_sender_position(
    ticket: int,
    sendername: str = Query(..., min_length=1, max_length=64),
    provider_hash: str = Depends(require_provider_key),
):
    """Close one position by MT5 ticket — only if it belongs to this sender."""
    _require_bridge()
    sn = sendername.strip()
    try:
        data = close_position(sn, ticket)
    except RuntimeError as exc:
        msg = str(exc)
        if "404" in msg or "not found" in msg.lower():
            raise HTTPException(status.HTTP_404_NOT_FOUND, f"position {ticket} not found for sender") from exc
        raise HTTPException(status.HTTP_502_BAD_GATEWAY, msg) from exc
    return PositionCloseOut(**data)


@router.post("/positions/close-all", response_model=PositionCloseAllOut)
def close_all_sender_positions(
    sendername: str = Query(..., min_length=1, max_length=64),
    provider_hash: str = Depends(require_provider_key),
):
    """Close all open positions belonging to this sender."""
    _require_bridge()
    sn = sendername.strip()
    try:
        data = close_all_positions(sn)
    except RuntimeError as exc:
        raise HTTPException(status.HTTP_502_BAD_GATEWAY, str(exc)) from exc
    return PositionCloseAllOut(**data)
