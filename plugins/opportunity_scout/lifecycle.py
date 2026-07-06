"""Lifecycle state machine for the Opportunity Scout engine.

The transition map is explicit data; anything not listed raises
``LifecycleError``. Every transition appends an audited
``TransitionEvent``.
"""

from __future__ import annotations

from .models import (
    CheckStatus,
    LifecycleError,
    Opportunity,
    Stage,
    TransitionEvent,
    utc_now_iso,
)

ALLOWED_TRANSITIONS: dict[Stage, frozenset[Stage]] = {
    Stage.CAPTURED: frozenset(
        {Stage.TRIAGED, Stage.REJECTED, Stage.EXPIRED, Stage.PARKED}
    ),
    Stage.TRIAGED: frozenset(
        {Stage.SCORED, Stage.REJECTED, Stage.EXPIRED, Stage.PARKED}
    ),
    Stage.SCORED: frozenset(
        {Stage.VALIDATING, Stage.REJECTED, Stage.EXPIRED, Stage.PARKED}
    ),
    Stage.VALIDATING: frozenset(
        {Stage.VALIDATED, Stage.REJECTED, Stage.EXPIRED, Stage.PARKED}
    ),
    Stage.VALIDATED: frozenset(
        {Stage.ACTIVE, Stage.REJECTED, Stage.EXPIRED, Stage.PARKED}
    ),
    Stage.ACTIVE: frozenset({Stage.REALIZED, Stage.PARKED, Stage.REJECTED}),
    Stage.PARKED: frozenset({Stage.TRIAGED, Stage.EXPIRED, Stage.REJECTED}),
    Stage.REALIZED: frozenset(),
    Stage.REJECTED: frozenset(),
    Stage.EXPIRED: frozenset(),
}


def can_transition(current: Stage, target: Stage) -> bool:
    return target in ALLOWED_TRANSITIONS.get(current, frozenset())


def _check_guards(opportunity: Opportunity, target: Stage) -> None:
    if target is Stage.SCORED and opportunity.score is None:
        raise LifecycleError(
            "Cannot enter SCORED without a score on record. Run scoring first."
        )
    if target is Stage.VALIDATED:
        state = opportunity.validation
        if not state.started:
            raise LifecycleError("Cannot enter VALIDATED: validation never started.")
        if state.failed:
            raise LifecycleError(
                "Cannot enter VALIDATED: one or more stages FAILED."
            )
        if not state.complete:
            pending = [
                stage.stage_id
                for stage in state.stages
                if stage.status is CheckStatus.PENDING
            ]
            raise LifecycleError(
                f"Cannot enter VALIDATED: stages still pending: {pending}"
            )


def transition(opportunity: Opportunity, target: Stage, reason: str) -> TransitionEvent:
    target = Stage(target)
    if not reason.strip():
        raise LifecycleError("Lifecycle transitions require a reason.")
    current = opportunity.stage
    if current == target:
        raise LifecycleError(f"Opportunity is already in stage {target.value!r}.")
    if not can_transition(current, target):
        raise LifecycleError(
            f"Illegal transition {current.value!r} -> {target.value!r}."
        )
    _check_guards(opportunity, target)
    event = TransitionEvent(
        from_stage=current.value,
        to_stage=target.value,
        timestamp=utc_now_iso(),
        reason=reason.strip(),
    )
    opportunity.stage = target
    opportunity.transitions.append(event)
    opportunity.touch()
    return event
