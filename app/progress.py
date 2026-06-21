"""Human-readable execution progress for provider status queries."""
from __future__ import annotations

from app.models import SignalRow

_EXECUTED_ACTIONS = {"executed", "queued", "parsed", "added", "closed", "modified", "breakeven", "partial"}
_SKIP_ACTIONS = {"trust_miss", "brain_skip", "skipped", "be_miss", "close_miss", "modify_miss", "partial_miss", "add_miss", "filtered"}


def build_progress(row: SignalRow) -> dict:
    """Map hub row status + Quantum ack result to a provider-friendly progress object."""
    status = row.status or "pending"
    result = row.result or {}
    log_action = (result.get("log_action") or "").lower()
    error = result.get("error")

    if status == "pending":
        return {
            "stage": "queued",
            "message": "Signal received — waiting for Quantum to pick it up",
            "executed": False,
        }
    if status == "processing":
        return {
            "stage": "processing",
            "message": "Quantum is executing this signal on MT5",
            "executed": False,
        }
    if status == "failed":
        msg = error or "Signal could not be executed"
        return {"stage": "failed", "message": msg, "executed": False}
    if status == "done":
        if log_action in _EXECUTED_ACTIONS or result.get("setup_id"):
            return {
                "stage": "executed",
                "message": "Trade executed on MT5",
                "executed": True,
            }
        if log_action in _SKIP_ACTIONS:
            return {
                "stage": "skipped",
                "message": error or f"Signal was not taken ({log_action})",
                "executed": False,
            }
        return {
            "stage": "done",
            "message": error or f"Completed ({log_action or 'ok'})",
            "executed": bool(result.get("setup_id")),
        }
    return {"stage": status, "message": status, "executed": False}
