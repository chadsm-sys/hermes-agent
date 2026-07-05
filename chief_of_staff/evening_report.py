"""Evening Report consumer — Part 2 of the Chief of Staff design.

Hermes consumes the *future* Mission Control Evening Report API:

- Evening Report (the day's outcome summary)
- AI Improvements (what the AI layer got permanently better at today)
- Compound Engine (capabilities whose value compounds with reuse)
- Opportunity Summary (what surfaced today that is worth money or time)

Interface only — same rules as :mod:`chief_of_staff.morning_brief`: no HTTP,
no live Mission Control dependency. The adapter comes later and implements
:class:`EveningReportSource`.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any, Protocol, runtime_checkable

from chief_of_staff.contracts import (
    ContractError,
    check_schema_version,
    require_int,
    require_list,
    require_number,
    require_str,
)


class EveningReportError(ContractError):
    """An Evening Report payload violates the consumer contract."""


@dataclass(frozen=True, slots=True)
class AIImprovement:
    """One thing the AI layer permanently improved today."""

    id: str
    description: str
    #: e.g. ``"reliability"``, ``"speed"``, ``"coverage"``, ``"judgment"``.
    category: str


@dataclass(frozen=True, slots=True)
class CompoundEntry:
    """A capability whose value compounds every time it is reused."""

    id: str
    capability: str
    reuse_count: int
    #: Cumulative operator minutes this capability has eliminated.
    minutes_saved_total: int


@dataclass(frozen=True, slots=True)
class Opportunity:
    """Something that surfaced today that is worth money or time."""

    id: str
    title: str
    expected_roi_usd: float
    #: ``"low"``, ``"medium"``, or ``"high"`` — Chad-effort, not AI-effort.
    effort: str

    EFFORTS = ("low", "medium", "high")

    def __post_init__(self) -> None:
        if self.effort not in self.EFFORTS:
            raise EveningReportError(
                f"opportunity {self.id!r}: effort must be one of {self.EFFORTS}, "
                f"got {self.effort!r}"
            )


@dataclass(frozen=True, slots=True)
class EveningReport:
    """Everything Hermes understands about the Evening Report payload."""

    schema_version: str
    #: ISO-8601 date the report covers.
    generated_for: str
    #: The day's outcome in prose — what shipped, what slipped, what broke.
    summary: str
    ai_improvements: tuple[AIImprovement, ...]
    compound_engine: tuple[CompoundEntry, ...]
    opportunity_summary: tuple[Opportunity, ...]

    def top_opportunities(self, limit: int = 3) -> tuple[Opportunity, ...]:
        """Highest-ROI opportunities first; id breaks ties deterministically."""
        ranked = sorted(
            self.opportunity_summary,
            key=lambda opp: (-opp.expected_roi_usd, opp.id),
        )
        return tuple(ranked[:limit])


def _parse_items(
    payload: Mapping[str, Any], key: str, parse_one: Any
) -> tuple[Any, ...]:
    items = []
    for raw in require_list(payload, key, EveningReportError):
        if not isinstance(raw, Mapping):
            raise EveningReportError(
                f"entries of {key!r} must be objects, got {type(raw).__name__}"
            )
        items.append(parse_one(raw))
    return tuple(items)


def parse_evening_report(payload: Mapping[str, Any]) -> EveningReport:
    """Parse and validate an Evening Report payload.

    Raises :class:`EveningReportError` on any contract violation.
    """
    if not isinstance(payload, Mapping):
        raise EveningReportError(f"payload must be an object, got {type(payload).__name__}")

    err = EveningReportError
    version = check_schema_version(payload, err)

    def parse_improvement(raw: Mapping[str, Any]) -> AIImprovement:
        return AIImprovement(
            id=require_str(raw, "id", err),
            description=require_str(raw, "description", err),
            category=require_str(raw, "category", err),
        )

    def parse_compound(raw: Mapping[str, Any]) -> CompoundEntry:
        entry = CompoundEntry(
            id=require_str(raw, "id", err),
            capability=require_str(raw, "capability", err),
            reuse_count=require_int(raw, "reuse_count", err),
            minutes_saved_total=require_int(raw, "minutes_saved_total", err),
        )
        if entry.reuse_count < 0 or entry.minutes_saved_total < 0:
            raise err(f"compound entry {entry.id!r}: counts must be >= 0")
        return entry

    def parse_opportunity(raw: Mapping[str, Any]) -> Opportunity:
        return Opportunity(
            id=require_str(raw, "id", err),
            title=require_str(raw, "title", err),
            expected_roi_usd=require_number(raw, "expected_roi_usd", err),
            effort=require_str(raw, "effort", err),
        )

    return EveningReport(
        schema_version=version,
        generated_for=require_str(payload, "generated_for", err),
        summary=require_str(payload, "summary", err),
        ai_improvements=_parse_items(payload, "ai_improvements", parse_improvement),
        compound_engine=_parse_items(payload, "compound_engine", parse_compound),
        opportunity_summary=_parse_items(payload, "opportunity_summary", parse_opportunity),
    )


@runtime_checkable
class EveningReportSource(Protocol):
    """Where Hermes gets the Evening Report from (future Mission Control adapter)."""

    def fetch_latest(self) -> EveningReport | None:
        """Return the most recent report, or ``None`` when none exists yet."""
        ...  # pragma: no cover - protocol definition


class StaticEveningReportSource:
    """In-memory :class:`EveningReportSource` for tests and offline design work."""

    def __init__(self, report: EveningReport | None = None) -> None:
        self._report = report

    def fetch_latest(self) -> EveningReport | None:
        return self._report
