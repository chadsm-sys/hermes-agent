"""Market validation pipeline for the Opportunity Scout engine.

An ordered, evidence-based checklist state machine. All evidence is
human-entered — the pipeline never gathers anything on its own (no APIs,
no scraping).
"""

from __future__ import annotations

from .confidence import (
    apply_confidence_event,
    stage_failed_delta,
    stage_passed_delta,
)
from .models import (
    CheckStatus,
    Evidence,
    EvidenceStrength,
    Opportunity,
    ValidationPipelineError,
    ValidationStage,
    ValidationState,
    utc_now_iso,
)

# (stage_id, human name, confidence weight)
DEFAULT_STAGES: tuple[tuple[str, str, float], ...] = (
    ("problem_evidence", "Problem evidence", 0.06),
    ("demand_evidence", "Demand evidence", 0.08),
    ("willingness_to_pay", "Willingness to pay", 0.10),
    ("competition_scan", "Competition scan", 0.05),
    ("regulatory_check", "Regulatory / compliance check", 0.06),
    ("capacity_fit", "Capacity fit", 0.05),
)


def build_default_stages() -> list[ValidationStage]:
    return [
        ValidationStage(stage_id=stage_id, name=name, weight=weight)
        for stage_id, name, weight in DEFAULT_STAGES
    ]


def begin_validation(opportunity: Opportunity) -> ValidationState:
    if opportunity.validation.started:
        raise ValidationPipelineError(
            f"Validation already started for {opportunity.opportunity_id}."
        )
    opportunity.validation = ValidationState(
        started_at=utc_now_iso(), stages=build_default_stages()
    )
    opportunity.touch()
    return opportunity.validation


def _require_started(opportunity: Opportunity) -> ValidationState:
    if not opportunity.validation.started:
        raise ValidationPipelineError(
            f"Validation has not started for {opportunity.opportunity_id}."
        )
    return opportunity.validation


def _require_in_order(state: ValidationState, stage: ValidationStage) -> None:
    for earlier in state.stages:
        if earlier.stage_id == stage.stage_id:
            return
        if earlier.status is CheckStatus.PENDING:
            raise ValidationPipelineError(
                f"Stage {stage.stage_id!r} cannot resolve before earlier "
                f"stage {earlier.stage_id!r} is resolved."
            )


def add_evidence(
    opportunity: Opportunity,
    stage_id: str,
    summary: str,
    source: str,
    strength: EvidenceStrength | str,
) -> Evidence:
    state = _require_started(opportunity)
    stage = state.get_stage(stage_id)
    if stage.status is not CheckStatus.PENDING:
        raise ValidationPipelineError(
            f"Stage {stage_id!r} is already {stage.status.value}; "
            "evidence must be added before resolution."
        )
    evidence = Evidence(
        summary=summary, source=source, strength=EvidenceStrength(strength)
    )
    stage.evidence.append(evidence)
    opportunity.touch()
    return evidence


def _strongest_evidence(stage: ValidationStage) -> EvidenceStrength:
    order = [EvidenceStrength.WEAK, EvidenceStrength.MODERATE, EvidenceStrength.STRONG]
    return max((item.strength for item in stage.evidence), key=order.index)


def pass_stage(opportunity: Opportunity, stage_id: str, note: str = "") -> ValidationStage:
    state = _require_started(opportunity)
    stage = state.get_stage(stage_id)
    _require_in_order(state, stage)
    if stage.status is not CheckStatus.PENDING:
        raise ValidationPipelineError(f"Stage {stage_id!r} is already resolved.")
    if not stage.evidence:
        raise ValidationPipelineError(
            f"Stage {stage_id!r} needs at least one evidence record to pass."
        )
    stage.status = CheckStatus.PASSED
    stage.resolution_note = note.strip()
    stage.resolved_at = utc_now_iso()
    delta = stage_passed_delta(stage.weight, _strongest_evidence(stage))
    apply_confidence_event(
        opportunity, delta, f"Validation stage passed: {stage_id}"
    )
    return stage


def fail_stage(opportunity: Opportunity, stage_id: str, reason: str) -> ValidationStage:
    if not reason.strip():
        raise ValidationPipelineError("Failing a stage requires a reason.")
    state = _require_started(opportunity)
    stage = state.get_stage(stage_id)
    _require_in_order(state, stage)
    if stage.status is not CheckStatus.PENDING:
        raise ValidationPipelineError(f"Stage {stage_id!r} is already resolved.")
    stage.status = CheckStatus.FAILED
    stage.resolution_note = reason.strip()
    stage.resolved_at = utc_now_iso()
    apply_confidence_event(
        opportunity,
        stage_failed_delta(stage.weight),
        f"Validation stage failed: {stage_id}",
    )
    return stage


def skip_stage(
    opportunity: Opportunity, stage_id: str, justification: str
) -> ValidationStage:
    if not justification.strip():
        raise ValidationPipelineError("Skipping a stage requires a justification.")
    state = _require_started(opportunity)
    stage = state.get_stage(stage_id)
    _require_in_order(state, stage)
    if stage.status is not CheckStatus.PENDING:
        raise ValidationPipelineError(f"Stage {stage_id!r} is already resolved.")
    stage.status = CheckStatus.SKIPPED
    stage.resolution_note = justification.strip()
    stage.resolved_at = utc_now_iso()
    opportunity.touch()
    return stage
