"""Morning Brief consumer — Part 1 of the Chief of Staff design.

Hermes consumes the *future* Mission Control Morning Plan API. This module
defines what Hermes understands about that payload — nothing more:

- Today's Plan
- Biggest Bottleneck
- Executive Recommendation
- AI Responsibilities
- Estimated Operator Time

Interface only. There is deliberately no HTTP client, no URL, and no
dependency on a live Mission Control install. When Mission Control ships the
API, an adapter implements :class:`MorningBriefSource` and everything above
it (conversation mode, escalation, ranking) works unchanged.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any, Protocol, runtime_checkable

from chief_of_staff.contracts import (
    ContractError,
    Recommendation,
    check_schema_version,
    parse_recommendation,
    require,
    require_int,
    require_list,
    require_mapping,
    require_str,
)


class MorningBriefError(ContractError):
    """A Morning Plan payload violates the consumer contract."""


@dataclass(frozen=True, slots=True)
class PlanItem:
    """One line of Today's Plan."""

    id: str
    title: str
    #: Who executes: ``"chad"`` or ``"hermes"``.
    owner: str
    #: 1 = highest. Mission Control emits a total order; ties are a bug there.
    priority: int
    estimated_minutes: int

    OWNERS = ("chad", "hermes")

    def __post_init__(self) -> None:
        if self.owner not in self.OWNERS:
            raise MorningBriefError(
                f"plan item {self.id!r}: owner must be one of {self.OWNERS}, got {self.owner!r}"
            )


@dataclass(frozen=True, slots=True)
class Bottleneck:
    """The single biggest constraint on today's throughput."""

    summary: str
    #: What it costs to leave unresolved (dollars, hours, risk — prose).
    impact: str
    #: The one action that unblocks it.
    unblocking_action: str


@dataclass(frozen=True, slots=True)
class AIResponsibility:
    """Work Hermes owns today without Chad in the loop."""

    id: str
    description: str
    #: True when Hermes may run this end-to-end under the escalation engine.
    autonomous: bool


@dataclass(frozen=True, slots=True)
class MorningBrief:
    """Everything Hermes understands about the Morning Plan payload."""

    schema_version: str
    #: ISO-8601 date the plan was generated for (e.g. ``"2026-07-05"``).
    generated_for: str
    todays_plan: tuple[PlanItem, ...]
    biggest_bottleneck: Bottleneck
    executive_recommendation: Recommendation
    ai_responsibilities: tuple[AIResponsibility, ...]
    #: Total minutes of Chad's hands-on time the plan requires.
    estimated_operator_minutes: int

    def chad_items(self) -> tuple[PlanItem, ...]:
        """Plan items Chad personally executes, in priority order."""
        return tuple(
            sorted(
                (item for item in self.todays_plan if item.owner == "chad"),
                key=lambda item: (item.priority, item.id),
            )
        )

    def hermes_items(self) -> tuple[PlanItem, ...]:
        """Plan items Hermes executes, in priority order."""
        return tuple(
            sorted(
                (item for item in self.todays_plan if item.owner == "hermes"),
                key=lambda item: (item.priority, item.id),
            )
        )


def parse_morning_brief(payload: Mapping[str, Any]) -> MorningBrief:
    """Parse and validate a Morning Plan payload.

    Raises :class:`MorningBriefError` on any contract violation. Hermes never
    acts on a partially valid brief — it is all or nothing.
    """
    if not isinstance(payload, Mapping):
        raise MorningBriefError(f"payload must be an object, got {type(payload).__name__}")

    err = MorningBriefError
    version = check_schema_version(payload, err)

    plan_items = []
    for raw in require_list(payload, "todays_plan", err):
        if not isinstance(raw, Mapping):
            raise err(f"plan item must be an object, got {type(raw).__name__}")
        plan_items.append(
            PlanItem(
                id=require_str(raw, "id", err),
                title=require_str(raw, "title", err),
                owner=require_str(raw, "owner", err),
                priority=require_int(raw, "priority", err),
                estimated_minutes=require_int(raw, "estimated_minutes", err),
            )
        )

    raw_bottleneck = require_mapping(payload, "biggest_bottleneck", err)
    bottleneck = Bottleneck(
        summary=require_str(raw_bottleneck, "summary", err),
        impact=require_str(raw_bottleneck, "impact", err),
        unblocking_action=require_str(raw_bottleneck, "unblocking_action", err),
    )

    responsibilities = []
    for raw in require_list(payload, "ai_responsibilities", err):
        if not isinstance(raw, Mapping):
            raise err(f"ai responsibility must be an object, got {type(raw).__name__}")
        autonomous = require(raw, "autonomous", err)
        if not isinstance(autonomous, bool):
            raise err(f"field 'autonomous' must be a boolean, got {type(autonomous).__name__}")
        responsibilities.append(
            AIResponsibility(
                id=require_str(raw, "id", err),
                description=require_str(raw, "description", err),
                autonomous=autonomous,
            )
        )

    operator_minutes = require_int(payload, "estimated_operator_minutes", err)
    if operator_minutes < 0:
        raise err(f"estimated_operator_minutes must be >= 0, got {operator_minutes}")

    return MorningBrief(
        schema_version=version,
        generated_for=require_str(payload, "generated_for", err),
        todays_plan=tuple(plan_items),
        biggest_bottleneck=bottleneck,
        executive_recommendation=parse_recommendation(
            require_mapping(payload, "executive_recommendation", err), err
        ),
        ai_responsibilities=tuple(responsibilities),
        estimated_operator_minutes=operator_minutes,
    )


@runtime_checkable
class MorningBriefSource(Protocol):
    """Where Hermes gets the Morning Plan from.

    The future Mission Control adapter implements this. Until then, tests and
    dry runs use :class:`StaticMorningBriefSource`.
    """

    def fetch_latest(self) -> MorningBrief | None:
        """Return the most recent brief, or ``None`` when none exists yet."""
        ...  # pragma: no cover - protocol definition


class StaticMorningBriefSource:
    """In-memory :class:`MorningBriefSource` for tests and offline design work."""

    def __init__(self, brief: MorningBrief | None = None) -> None:
        self._brief = brief

    def fetch_latest(self) -> MorningBrief | None:
        return self._brief

