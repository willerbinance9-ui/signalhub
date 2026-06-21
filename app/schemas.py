"""Request/response schemas."""
from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field, field_validator

ActionType = Literal[
    "open", "add", "close", "breakeven", "modify",
    "partial_close", "close_all", "ignore",
]
DirectionType = Literal["buy", "sell"]
OrderType = Literal["market", "limit", "stop"]


class SignalIn(BaseModel):
    external_id: str | None = Field(None, max_length=128)
    action: ActionType = "open"
    symbol: str | None = Field(None, max_length=64)
    direction: DirectionType | None = None
    order_type: OrderType = "market"
    entry: float | None = None
    sl: float | None = None
    tp: float | None = None
    lot: float | None = None
    lot_scale: float | None = Field(None, ge=0.01, le=10.0)
    ticket: int | None = None
    message: str | None = Field(None, max_length=4000)
    provider_name: str | None = Field(None, max_length=120)
    confidence: float | None = Field(None, ge=0, le=100)

    @field_validator("symbol")
    @classmethod
    def strip_symbol(cls, v: str | None) -> str | None:
        return v.strip().upper() if v else None

    @field_validator("direction", mode="before")
    @classmethod
    def norm_direction(cls, v):
        if v is None:
            return None
        s = str(v).lower().strip()
        if s in ("buy", "long", "bullish"):
            return "buy"
        if s in ("sell", "short", "bearish"):
            return "sell"
        return v


class SignalOut(BaseModel):
    id: str
    external_id: str | None
    status: str
    payload: dict
    result: dict | None = None
    created_at: datetime
    acked_at: datetime | None = None
    duplicate: bool = False

    model_config = {"from_attributes": True}


class AckIn(BaseModel):
    status: Literal["done", "failed"] = "done"
    setup_id: str | None = None
    log_action: str | None = None
    error: str | None = Field(None, max_length=500)


class AckOut(BaseModel):
    id: str
    status: str
    ok: bool = True


class PendingOut(BaseModel):
    items: list[SignalOut]
    count: int
