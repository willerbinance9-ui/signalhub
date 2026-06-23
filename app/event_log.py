"""Signal Hub API event log (persisted)."""
from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import DateTime, Index, String, Text
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.types import JSON

from app.db import Base
from app.models import utcnow


class SignalEventRow(Base):
    __tablename__ = "signal_events"
    __table_args__ = (
        Index("ix_signal_events_provider_created", "provider_key_hash", "created_at"),
        Index("ix_signal_events_signal_id", "signal_id"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    signal_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    provider_key_hash: Mapped[str] = mapped_column(String(32), index=True)
    sendername: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    event: Mapped[str] = mapped_column(String(40))
    message: Mapped[str] = mapped_column(Text, default="")
    detail: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
