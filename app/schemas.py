"""Request/response schemas."""
from __future__ import annotations

import re
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
    sendername: str | None = Field(
        None, max_length=64,
        description="Display name or username of the user who posted the signal (shown in MT5 order comment)",
    )
    callback_url: str | None = Field(
        None, max_length=500,
        description="HTTPS URL to POST when signal reaches done/failed (optional webhook)",
    )
    confidence: float | None = Field(None, ge=0, le=100)
    image_url: str | None = Field(
        None, max_length=2000,
        description="HTTPS URL of chart/screenshot (forwarded to Telegram with the signal)",
    )
    image_base64: str | None = Field(
        None, max_length=7_000_000,
        description="Base64 chart image (or data:image/...;base64,...) — optional alternative to image_url",
    )
    image_mime: str | None = Field(
        None, max_length=64,
        description="MIME type when using image_base64 (default image/jpeg)",
    )

    @field_validator("image_url", mode="before")
    @classmethod
    def norm_image_url(cls, v):
        if v is None:
            return None
        s = str(v).strip()
        return s or None

    @field_validator("image_mime", mode="before")
    @classmethod
    def norm_image_mime(cls, v):
        if v is None:
            return None
        s = str(v).strip().lower()
        return s or None

    @field_validator("sendername", mode="before")
    @classmethod
    def norm_sendername(cls, v):
        if v is None:
            return None
        s = str(v).strip()
        return s or None

    @field_validator("callback_url", mode="before")
    @classmethod
    def norm_callback_url(cls, v):
        if v is None:
            return None
        s = str(v).strip()
        return s or None

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

    @field_validator("order_type", mode="before")
    @classmethod
    def norm_order_type(cls, v):
        """Accept messy UI labels e.g. 'limit (or market / stop)' from mobile apps."""
        if v is None:
            return "market"
        s = str(v).lower().strip()
        if s in ("open", "now", "at market", "market now"):
            return "market"
        if s in ("market", "limit", "stop"):
            return s
        m = re.search(r"\b(market|limit|stop)\b", s)
        if m:
            return m.group(1)
        if any(k in s for k in ("mkt", "at market", "market order")):
            return "market"
        if "limit" in s:
            return "limit"
        if "stop" in s:
            return "stop"
        return "market"

    @field_validator("entry", mode="before")
    @classmethod
    def norm_entry(cls, v):
        """Accept entry ranges like '5160 - 5170' (uses midpoint)."""
        if v is None:
            return None
        if isinstance(v, (int, float)):
            return float(v)
        s = str(v).strip().replace(",", "")
        nums = re.findall(r"[\d.]+", s)
        if len(nums) >= 2:
            return round((float(nums[0]) + float(nums[1])) / 2, 8)
        if len(nums) == 1:
            return float(nums[0])
        return v


class SignalProgress(BaseModel):
    stage: str
    message: str
    executed: bool


class SignalOut(BaseModel):
    id: str
    external_id: str | None
    status: str
    payload: dict
    result: dict | None = None
    progress: SignalProgress | None = None
    created_at: datetime
    acked_at: datetime | None = None
    duplicate: bool = False

    model_config = {"from_attributes": True}


class SignalListOut(BaseModel):
    items: list[SignalOut]
    count: int
    sendername: str | None = None


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


class SignalEventOut(BaseModel):
    id: str
    signal_id: str | None
    sendername: str | None
    event: str
    message: str
    detail: dict | None = None
    created_at: datetime

    model_config = {"from_attributes": True}


class SignalEventListOut(BaseModel):
    items: list[SignalEventOut]
    count: int
    sendername: str | None = None


class PositionOut(BaseModel):
    ticket: int
    symbol: str
    direction: str
    lot: float
    entry: float
    sl: float | None = None
    tp: float | None = None
    profit: float | None = None
    price: float | None = None
    comment: str | None = None
    opened_at: str | None = None
    sendername: str | None = None


class PositionListOut(BaseModel):
    sendername: str
    count: int
    items: list[dict]


class PositionCloseOut(BaseModel):
    ok: bool = True
    ticket: int
    symbol: str | None = None
    profit: float | None = None
    sendername: str | None = None


class PositionCloseItemOut(BaseModel):
    ticket: int
    symbol: str | None = None
    profit: float | None = None
    ok: bool = True
    error: str | None = None


class PositionCloseAllOut(BaseModel):
    ok: bool = True
    closed: int = 0
    count: int = 0
    items: list[dict] = []
    sendername: str | None = None


class QuoteIn(BaseModel):
    symbol: str = Field(..., min_length=1, max_length=64)


class QuoteOut(BaseModel):
    symbol: str
    resolved_symbol: str
    bid: float
    ask: float
    price: float
    mid: float
    spread: float
    digits: int = 5
    point: float = 0.00001
    time: str
    source: str = "mt5"


class SenderStatOut(BaseModel):
    rank: int | None = None
    sender: str
    signals: int = 0
    executed: int = 0
    skipped: int = 0
    failed: int = 0
    closed_trades: int = 0
    wins: int = 0
    losses: int = 0
    profit: float = 0.0
    win_rate: float | None = None
    profit_factor: float = 0.0
    expectancy: float = 0.0
    profitable: bool = False


class SenderReportSummaryOut(BaseModel):
    total_profit: float = 0.0
    total_closed_trades: int = 0
    profitable_senders: int = 0
    unprofitable_senders: int = 0


class SenderReportOut(BaseModel):
    days: int = 90
    sort: str = "profit"
    min_closed_trades: int = 0
    total_senders: int = 0
    returned: int = 0
    generated_at: str | None = None
    summary: SenderReportSummaryOut | None = None
    senders: list[SenderStatOut] = []
