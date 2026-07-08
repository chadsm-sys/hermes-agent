"""Shared contract primitives for the Chief of Staff layer.

These are the vocabulary types shared by the Morning Brief and Evening
Report consumer contracts, the escalation engine, and the recommendation
ranker. Everything here is a frozen value object — no I/O, no runtime state.
"""

from __future__ import annotations

import enum
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any

#: Contract version spoken by this consumer. Mission Control payloads carry a
#: ``schema_version`` of the form ``"<major>.<minor>"``; consumers accept any
#: payload whose *major* version matches and reject everything else.
SCHEMA_VERSION = "1.0"


class ContractError(ValueError):
    """A Mission Control payload violates the consumer contract."""


class SafetyRisk(enum.IntEnum):
    """Risk grade attached to a recommendation or unit of work.

    ``IntEnum`` so grades are totally ordered: lower value == safer. This
    ordering is load-bearing for both ranking (safety sorts first) and
    escalation (HIGH and above always needs Chad).
    """

    NONE = 0
    LOW = 1
    MEDIUM = 2
    HIGH = 3
    CRITICAL = 4

    @classmethod
    def parse(cls, value: str) -> SafetyRisk:
        try:
            return cls[value.strip().upper()]
        except KeyError:
            raise ContractError(f"unknown safety risk: {value!r}") from None


@dataclass(frozen=True, slots=True)
class Recommendation:
    """A single executive recommendation.

    Every field the deterministic ranker needs is explicit here — ranking
    never depends on hidden model state, only on these numbers.
    """

    id: str
    title: str
    rationale: str
    #: Safety grade of acting on the recommendation (safer ranks first).
    safety_risk: SafetyRisk
    #: Expected return in dollars (or dollar-equivalent) if acted on.
    expected_roi_usd: float
    #: Minutes of Chad's personal time required (less ranks first).
    chad_effort_minutes: int
    #: Alignment with active strategic goals, 0.0 (none) to 1.0 (direct hit).
    strategic_alignment: float
    #: Confidence that the projected outcome materializes, 0.0 to 1.0.
    confidence: float

    def __post_init__(self) -> None:
        if not self.id:
            raise ContractError("recommendation id must be non-empty")
        if not 0.0 <= self.strategic_alignment <= 1.0:
            raise ContractError(
                f"strategic_alignment must be within [0, 1], got {self.strategic_alignment!r}"
            )
        if not 0.0 <= self.confidence <= 1.0:
            raise ContractError(f"confidence must be within [0, 1], got {self.confidence!r}")
        if self.chad_effort_minutes < 0:
            raise ContractError(
                f"chad_effort_minutes must be >= 0, got {self.chad_effort_minutes!r}"
            )


# ---------------------------------------------------------------------------
# Parsing helpers (shared by morning_brief / evening_report)
# ---------------------------------------------------------------------------


def check_schema_version(payload: Mapping[str, Any], error: type[ContractError]) -> str:
    """Validate ``payload["schema_version"]`` against :data:`SCHEMA_VERSION`."""
    version = require_str(payload, "schema_version", error)
    major = version.split(".", 1)[0]
    expected_major = SCHEMA_VERSION.split(".", 1)[0]
    if major != expected_major:
        raise error(
            f"unsupported schema_version {version!r}; this consumer speaks major "
            f"version {expected_major}"
        )
    return version


def require(payload: Mapping[str, Any], key: str, error: type[ContractError]) -> Any:
    if key not in payload:
        raise error(f"missing required field: {key!r}")
    return payload[key]


def require_str(payload: Mapping[str, Any], key: str, error: type[ContractError]) -> str:
    value = require(payload, key, error)
    if not isinstance(value, str):
        raise error(f"field {key!r} must be a string, got {type(value).__name__}")
    return value


def require_int(payload: Mapping[str, Any], key: str, error: type[ContractError]) -> int:
    value = require(payload, key, error)
    # bool is an int subclass; a True where a count belongs is a contract bug.
    if isinstance(value, bool) or not isinstance(value, int):
        raise error(f"field {key!r} must be an integer, got {type(value).__name__}")
    return value


def require_number(payload: Mapping[str, Any], key: str, error: type[ContractError]) -> float:
    value = require(payload, key, error)
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise error(f"field {key!r} must be a number, got {type(value).__name__}")
    return float(value)


def require_list(
    payload: Mapping[str, Any], key: str, error: type[ContractError]
) -> Sequence[Any]:
    value = require(payload, key, error)
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes)):
        raise error(f"field {key!r} must be a list, got {type(value).__name__}")
    return value


def require_mapping(
    payload: Mapping[str, Any], key: str, error: type[ContractError]
) -> Mapping[str, Any]:
    value = require(payload, key, error)
    if not isinstance(value, Mapping):
        raise error(f"field {key!r} must be an object, got {type(value).__name__}")
    return value


def parse_recommendation(payload: Mapping[str, Any], error: type[ContractError]) -> Recommendation:
    """Parse one recommendation object out of a Mission Control payload."""
    if not isinstance(payload, Mapping):
        raise error(f"recommendation must be an object, got {type(payload).__name__}")
    try:
        return Recommendation(
            id=require_str(payload, "id", error),
            title=require_str(payload, "title", error),
            rationale=require_str(payload, "rationale", error),
            safety_risk=SafetyRisk.parse(require_str(payload, "safety_risk", error)),
            expected_roi_usd=require_number(payload, "expected_roi_usd", error),
            chad_effort_minutes=require_int(payload, "chad_effort_minutes", error),
            strategic_alignment=require_number(payload, "strategic_alignment", error),
            confidence=require_number(payload, "confidence", error),
        )
    except ContractError as exc:
        # Re-raise value-object validation failures as the caller's error type.
        raise error(str(exc)) from None
