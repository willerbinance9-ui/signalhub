"""Market quote routes — proxied to Quantum MT5 feed."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.auth import require_provider_key
from app.quantum_bridge import bridge_configured, get_quote, post_quote
from app.schemas import QuoteIn, QuoteOut

router = APIRouter(prefix="/v1", tags=["market"])


def _require_bridge():
    if not bridge_configured():
        raise HTTPException(
            status.HTTP_503_SERVICE_UNAVAILABLE,
            "Quote API requires QUANTUM_BRIDGE_URL on Signal Hub (your Quantum VPS URL)",
        )


@router.get("/quote", response_model=QuoteOut)
def quote_get(
    symbol: str = Query(..., min_length=1, max_length=64, description="e.g. XAUUSD, VIX75"),
    provider_hash: str = Depends(require_provider_key),
):
    """Current bid/ask/mid for a symbol from your MT5 terminal."""
    _require_bridge()
    try:
        data = get_quote(symbol.strip())
    except RuntimeError as exc:
        msg = str(exc)
        if "404" in msg or "no live price" in msg.lower() or "no price" in msg.lower():
            raise HTTPException(status.HTTP_404_NOT_FOUND, msg) from exc
        raise HTTPException(status.HTTP_502_BAD_GATEWAY, msg) from exc
    return QuoteOut(**data)


@router.post("/quote", response_model=QuoteOut)
def quote_post(
    body: QuoteIn,
    provider_hash: str = Depends(require_provider_key),
):
    """POST `{\"symbol\": \"XAUUSD\"}` — returns live price from Quantum/MT5."""
    _require_bridge()
    try:
        data = post_quote(body.symbol.strip())
    except RuntimeError as exc:
        msg = str(exc)
        if "404" in msg or "no live price" in msg.lower() or "no price" in msg.lower():
            raise HTTPException(status.HTTP_404_NOT_FOUND, msg) from exc
        raise HTTPException(status.HTTP_502_BAD_GATEWAY, msg) from exc
    return QuoteOut(**data)
