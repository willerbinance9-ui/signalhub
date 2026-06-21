"""AARE Signal Hub — FastAPI entrypoint."""
from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.db import init_db
from app.routers import queue, signals

logging.basicConfig(level=logging.INFO,
                    format="%(asctime)s %(name)s %(levelname)s %(message)s")


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    yield


app = FastAPI(
    title="AARE Signal Hub",
    description="Ingest trading signals from third-party apps; AARE Quantum polls and executes on MT5.",
    version="1.0.0",
    lifespan=lifespan,
)

app.include_router(signals.router)
app.include_router(queue.router)


@app.get("/health")
def health():
    return {"ok": True, "service": "aare-signal-hub"}
