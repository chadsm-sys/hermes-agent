"""Confidence tracking for the Opportunity Scout engine.

Confidence starts at a prior determined by source type (set in
``Opportunity.__post_init__``) and only ever changes through
``apply_confidence_event`` so that every movement is audited.
"""

from __future__ import annotations

from .models import (
    EVIDENCE_STRENGTH_FACTOR,
    ConfidenceEvent,
    EvidenceStrength,
    Opportunity,
    clamp_confidence,
    utc_now_iso,
)


def apply_confidence_event(
    opportunity: Opportunity, delta: float, reason: str
) -> ConfidenceEvent:
    """Apply a bounded confidence change and record the audit event."""
    if not reason.strip():
        raise ValueError("Confidence events require a reason.")
    previous = opportunity.confidence
    resulting = clamp_confidence(previous + delta)
    event = ConfidenceEvent(
        timestamp=utc_now_iso(),
        delta=round(resulting - previous, 6),
        reason=reason.strip(),
        resulting=resulting,
    )
    opportunity.confidence = resulting
    opportunity.confidence_events.append(event)
    opportunity.touch()
    return event


def stage_passed_delta(stage_weight: float, strength: EvidenceStrength) -> float:
    return stage_weight * EVIDENCE_STRENGTH_FACTOR[EvidenceStrength(strength)]


def stage_failed_delta(stage_weight: float) -> float:
    return -stage_weight
