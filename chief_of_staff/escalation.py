"""Escalation decision contract for chief-of-staff integrations."""

from __future__ import annotations

from enum import Enum
from typing import Any, Mapping


class Decision(str, Enum):
    CONTINUE = "CONTINUE"
    PAUSE = "PAUSE"
    NEEDS_CHAD = "NEEDS_CHAD"


def classify_escalation(payload: Mapping[str, Any]) -> Decision:
    """Parse a payload decision into the stable escalation enum."""

    value = str(payload.get("decision", "PAUSE"))
    try:
        return Decision(value)
    except ValueError as exc:
        raise ValueError(f"unsupported escalation decision: {value}") from exc


__all__ = ["Decision", "classify_escalation"]
