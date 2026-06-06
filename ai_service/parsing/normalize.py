"""Normalize parsed reminder dicts to the chat contract."""

from __future__ import annotations

import os
import sys
from datetime import datetime, timezone
from typing import Optional


def _today_utc() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d")


def _normalize_repeat_value(value) -> Optional[str]:
    try:
        backend_root = os.path.abspath(
            os.path.join(os.path.dirname(__file__), "..", "..", "backend")
        )
        if backend_root not in sys.path:
            sys.path.insert(0, backend_root)
        from services.repeat_schedule import normalize_repeat

        return normalize_repeat(value if value is None else str(value))
    except Exception:
        if value is None:
            return None
        cleaned = str(value).strip().lower()
        return cleaned if cleaned in {"daily", "weekly", "weekdays", "monthly"} else None


def normalize_parsed(raw: dict) -> dict:
    """Fill defaults and normalize flags from parser output."""
    out = dict(raw)
    if "repeat" in out:
        out["repeat"] = _normalize_repeat_value(out.get("repeat"))
    for key in (
        "task",
        "date",
        "time",
        "clarification_question",
        "editable_reminder_id",
    ):
        if out.get(key) == "":
            out[key] = None
    if out.get("time"):
        t = str(out["time"]).strip()
        if len(t) == 5 and t[2] == ":":
            out["time"] = t
        elif len(t) >= 8 and t[2] == ":":
            out["time"] = t[:5]
    if not out.get("date") and out.get("task") and not out.get("needs_clarification"):
        out["date"] = _today_utc()
    has_time = bool(out.get("time"))
    if not has_time:
        out["needs_time"] = True
    elif out.get("needs_time") is True:
        out["needs_time"] = True
    else:
        out["needs_time"] = False
    return out
