"""Shared types for the hybrid reminder parser."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Optional


@dataclass
class ParseResult:
    """Structured reminder parse with confidence metadata."""

    intent: str = "create"
    task: Optional[str] = None
    date: Optional[str] = None
    time: Optional[str] = None
    repeat: Optional[str] = None
    needs_time: bool = False
    needs_clarification: bool = False
    clarification_question: Optional[str] = None
    editable_reminder_id: Optional[str] = None
    confidence: float = 0.0
    parser_layer: str = "none"
    ambiguities: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "intent": self.intent,
            "task": self.task,
            "date": self.date,
            "time": self.time,
            "repeat": self.repeat,
            "needs_time": self.needs_time,
            "needs_clarification": self.needs_clarification,
            "clarification_question": self.clarification_question,
            "editable_reminder_id": self.editable_reminder_id,
        }

    @classmethod
    def from_dict(cls, raw: dict[str, Any], *, layer: str = "merged") -> "ParseResult":
        return cls(
            intent=str(raw.get("intent") or "create"),
            task=raw.get("task"),
            date=raw.get("date"),
            time=raw.get("time"),
            repeat=raw.get("repeat"),
            needs_time=bool(raw.get("needs_time")),
            needs_clarification=bool(raw.get("needs_clarification")),
            clarification_question=raw.get("clarification_question"),
            editable_reminder_id=raw.get("editable_reminder_id"),
            parser_layer=layer,
        )
