"""Escalation engine — Part 4 of the Chief of Staff design.

Classifies every unit of Hermes work into exactly one of:

- ``CONTINUE``   — keep going autonomously; Chad never hears about it.
- ``PAUSE``      — stop and hold state; retrying or waiting will resolve it
                   without Chad's input (or the next brief will).
- ``NEEDS_CHAD`` — Chad's judgment or authority is genuinely required.

Design rule: **never ask unnecessary questions.** Chad has a 90-minute daily
computer window; every question spends it. So ``NEEDS_CHAD`` is reserved for
authority Hermes must not exercise (money, irreversibility, external sends,
credentials, policy conflicts, high safety risk) or information only Chad
possesses. Everything else is Hermes's job to figure out.

The rules are an ordered, deterministic table — same signals in, same
decision out, always. When escalation *is* required, the result carries at
most one precise question.
"""

from __future__ import annotations

import enum
from dataclasses import dataclass, field

from chief_of_staff.contracts import SafetyRisk

#: Consecutive failures tolerated before Hermes stops burning cycles.
MAX_AUTONOMOUS_FAILURES = 3


class EscalationDecision(enum.Enum):
    CONTINUE = "continue"
    PAUSE = "pause"
    NEEDS_CHAD = "needs_chad"


@dataclass(frozen=True, slots=True)
class WorkSignals:
    """Observable facts about a unit of work. All default to the safe/quiet case."""

    #: Human-readable identifier of the work unit (job id, lane, task name).
    work_id: str
    #: Acting cannot be undone (deletes, sends, deploys, contract signatures).
    irreversible: bool = False
    #: Acting spends or commits money.
    spends_money: bool = False
    #: Acting is visible outside Chad's systems (emails, posts, PRs to others).
    external_side_effects: bool = False
    #: Acting reads/writes credentials or changes auth configuration.
    touches_credentials: bool = False
    #: Acting conflicts with a standing rule, or two standing rules conflict.
    policy_conflict: bool = False
    #: Worst-case safety grade of proceeding.
    safety_risk: SafetyRisk = SafetyRisk.NONE
    #: Work is blocked on a fact that ONLY Chad can supply.
    requires_chad_knowledge: bool = False
    #: Work is blocked on something that will resolve on its own (rate limit,
    #: upstream outage, scheduled dependency).
    blocked_on_external_event: bool = False
    #: Consecutive failed attempts so far.
    consecutive_failures: int = 0
    #: The single precise question to ask if escalation is required.
    escalation_question: str = field(default="", compare=False)


@dataclass(frozen=True, slots=True)
class EscalationResult:
    decision: EscalationDecision
    #: Which rule fired — stable identifiers so behavior is auditable.
    rule: str
    reason: str
    #: Populated only when ``decision is NEEDS_CHAD`` and a question exists.
    question: str | None = None


def classify_work(signals: WorkSignals) -> EscalationResult:
    """Apply the ordered rule table. First matching rule wins."""

    def needs_chad(rule: str, reason: str) -> EscalationResult:
        return EscalationResult(
            decision=EscalationDecision.NEEDS_CHAD,
            rule=rule,
            reason=reason,
            question=signals.escalation_question or None,
        )

    def pause(rule: str, reason: str) -> EscalationResult:
        # A pause is not a question. Questions are only attached to NEEDS_CHAD.
        return EscalationResult(decision=EscalationDecision.PAUSE, rule=rule, reason=reason)

    # --- Authority Hermes must not exercise → NEEDS_CHAD -------------------
    if signals.irreversible:
        return needs_chad("authority.irreversible", "action cannot be undone")
    if signals.spends_money:
        return needs_chad("authority.money", "action spends or commits money")
    if signals.external_side_effects:
        return needs_chad("authority.external", "action is visible outside Chad's systems")
    if signals.touches_credentials:
        return needs_chad("authority.credentials", "action touches credentials or auth")
    if signals.policy_conflict:
        return needs_chad("authority.policy", "standing rules conflict; Chad arbitrates")
    if signals.safety_risk >= SafetyRisk.HIGH:
        return needs_chad(
            "authority.safety",
            f"safety risk is {signals.safety_risk.name}; above autonomous threshold",
        )

    # --- Information only Chad possesses → NEEDS_CHAD ----------------------
    if signals.requires_chad_knowledge:
        return needs_chad("knowledge.chad_only", "blocked on a fact only Chad can supply")

    # --- Self-resolving blocks and failure ceilings → PAUSE ----------------
    if signals.consecutive_failures >= MAX_AUTONOMOUS_FAILURES:
        return pause(
            "throttle.failure_ceiling",
            f"{signals.consecutive_failures} consecutive failures; "
            "holding state instead of burning cycles",
        )
    if signals.blocked_on_external_event:
        return pause("throttle.external_block", "blocked on an event that resolves itself")

    # --- Default: this is Hermes's job → CONTINUE ---------------------------
    return EscalationResult(
        decision=EscalationDecision.CONTINUE,
        rule="default.autonomous",
        reason="within autonomous authority; no unnecessary questions",
    )
