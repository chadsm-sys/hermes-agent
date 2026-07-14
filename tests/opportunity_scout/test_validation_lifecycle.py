"""Validation pipeline and lifecycle state-machine tests."""

from __future__ import annotations

import pytest

from plugins.opportunity_scout import validation
from plugins.opportunity_scout.lifecycle import (
    ALLOWED_TRANSITIONS,
    can_transition,
    transition,
)
from plugins.opportunity_scout.models import (
    CheckStatus,
    LifecycleError,
    Opportunity,
    Stage,
    TERMINAL_STAGES,
    ValidationPipelineError,
)
from plugins.opportunity_scout.scoring import score_opportunity


def make_opportunity(**overrides) -> Opportunity:
    defaults = {"title": "Pipeline subject", "expected_revenue_usd": 50_000}
    defaults.update(overrides)
    return Opportunity(**defaults)


class TestValidationPipeline:
    def test_begin_builds_default_stages(self):
        opp = make_opportunity()
        state = validation.begin_validation(opp)
        assert [s.stage_id for s in state.stages] == [
            "problem_evidence",
            "demand_evidence",
            "willingness_to_pay",
            "competition_scan",
            "regulatory_check",
            "capacity_fit",
        ]
        assert all(s.status is CheckStatus.PENDING for s in state.stages)

    def test_cannot_begin_twice(self):
        opp = make_opportunity()
        validation.begin_validation(opp)
        with pytest.raises(ValidationPipelineError):
            validation.begin_validation(opp)

    def test_pass_requires_evidence(self):
        opp = make_opportunity()
        validation.begin_validation(opp)
        with pytest.raises(ValidationPipelineError, match="evidence"):
            validation.pass_stage(opp, "problem_evidence")

    def test_stages_resolve_in_order(self):
        opp = make_opportunity()
        validation.begin_validation(opp)
        validation.add_evidence(
            opp, "demand_evidence", "Someone asked", "conversation", "moderate"
        )
        with pytest.raises(ValidationPipelineError, match="earlier"):
            validation.pass_stage(opp, "demand_evidence")

    def test_pass_moves_confidence_up(self):
        opp = make_opportunity()
        before = opp.confidence
        validation.begin_validation(opp)
        validation.add_evidence(
            opp, "problem_evidence", "Named pain", "client call", "strong"
        )
        validation.pass_stage(opp, "problem_evidence")
        assert opp.confidence > before
        assert "problem_evidence" in opp.confidence_events[-1].reason

    def test_fail_requires_reason_and_moves_confidence_down(self):
        opp = make_opportunity()
        validation.begin_validation(opp)
        with pytest.raises(ValidationPipelineError):
            validation.fail_stage(opp, "problem_evidence", " ")
        before = opp.confidence
        validation.fail_stage(opp, "problem_evidence", "Nobody has this problem")
        assert opp.confidence < before
        assert opp.validation.failed

    def test_skip_requires_justification(self):
        opp = make_opportunity()
        validation.begin_validation(opp)
        with pytest.raises(ValidationPipelineError):
            validation.skip_stage(opp, "problem_evidence", "")
        validation.skip_stage(opp, "problem_evidence", "Known problem — existing client")
        assert opp.validation.stages[0].status is CheckStatus.SKIPPED

    def test_no_double_resolution(self):
        opp = make_opportunity()
        validation.begin_validation(opp)
        validation.skip_stage(opp, "problem_evidence", "known")
        with pytest.raises(ValidationPipelineError, match="already resolved"):
            validation.skip_stage(opp, "problem_evidence", "again")

    def test_evidence_locked_after_resolution(self):
        opp = make_opportunity()
        validation.begin_validation(opp)
        validation.skip_stage(opp, "problem_evidence", "known")
        with pytest.raises(ValidationPipelineError):
            validation.add_evidence(opp, "problem_evidence", "late", "src", "weak")

    def test_complete_when_all_passed_or_skipped(self):
        opp = make_opportunity()
        state = validation.begin_validation(opp)
        for stage in state.stages:
            validation.skip_stage(opp, stage.stage_id, "test skip")
        assert state.complete and not state.failed

    def test_unknown_stage(self):
        opp = make_opportunity()
        validation.begin_validation(opp)
        with pytest.raises(ValidationPipelineError, match="Unknown validation stage"):
            validation.add_evidence(opp, "made_up", "x", "y", "weak")

    def test_requires_started_pipeline(self):
        opp = make_opportunity()
        with pytest.raises(ValidationPipelineError, match="not started"):
            validation.add_evidence(opp, "problem_evidence", "x", "y", "weak")


class TestLifecycle:
    def test_happy_path(self):
        opp = make_opportunity()
        transition(opp, Stage.TRIAGED, "triage")
        opp.score = score_opportunity(opp)
        transition(opp, Stage.SCORED, "scored")
        transition(opp, Stage.VALIDATING, "validating")
        state = validation.begin_validation(opp)
        for stage in state.stages:
            validation.skip_stage(opp, stage.stage_id, "test")
        transition(opp, Stage.VALIDATED, "validated")
        transition(opp, Stage.ACTIVE, "go")
        transition(opp, Stage.REALIZED, "money in the bank")
        assert opp.stage is Stage.REALIZED
        assert len(opp.transitions) == 6
        assert [event.to_stage for event in opp.transitions] == [
            "triaged",
            "scored",
            "validating",
            "validated",
            "active",
            "realized",
        ]

    def test_illegal_transition_raises(self):
        opp = make_opportunity()
        with pytest.raises(LifecycleError, match="Illegal transition"):
            transition(opp, Stage.ACTIVE, "skipping everything")

    def test_scored_guard_requires_score(self):
        opp = make_opportunity()
        transition(opp, Stage.TRIAGED, "triage")
        with pytest.raises(LifecycleError, match="without a score"):
            transition(opp, Stage.SCORED, "no score yet")

    def test_validated_guard_requires_complete_pipeline(self):
        opp = make_opportunity()
        transition(opp, Stage.TRIAGED, "t")
        opp.score = score_opportunity(opp)
        transition(opp, Stage.SCORED, "s")
        transition(opp, Stage.VALIDATING, "v")
        with pytest.raises(LifecycleError, match="never started"):
            transition(opp, Stage.VALIDATED, "too soon")
        validation.begin_validation(opp)
        with pytest.raises(LifecycleError, match="pending"):
            transition(opp, Stage.VALIDATED, "still too soon")

    def test_validated_guard_blocks_failed_pipeline(self):
        opp = make_opportunity()
        transition(opp, Stage.TRIAGED, "t")
        opp.score = score_opportunity(opp)
        transition(opp, Stage.SCORED, "s")
        transition(opp, Stage.VALIDATING, "v")
        validation.begin_validation(opp)
        validation.fail_stage(opp, "problem_evidence", "no real problem")
        with pytest.raises(LifecycleError, match="FAILED"):
            transition(opp, Stage.VALIDATED, "nope")

    def test_park_and_revive(self):
        opp = make_opportunity()
        transition(opp, Stage.TRIAGED, "t")
        transition(opp, Stage.PARKED, "not now")
        transition(opp, Stage.TRIAGED, "reactivated explicitly")
        assert opp.stage is Stage.TRIAGED

    def test_terminal_stages_have_no_exits(self):
        for stage in TERMINAL_STAGES:
            assert ALLOWED_TRANSITIONS[stage] == frozenset()

    def test_reason_required(self):
        opp = make_opportunity()
        with pytest.raises(LifecycleError, match="reason"):
            transition(opp, Stage.TRIAGED, "  ")

    def test_same_stage_rejected(self):
        opp = make_opportunity()
        with pytest.raises(LifecycleError, match="already"):
            transition(opp, Stage.CAPTURED, "noop")

    def test_can_transition_matrix_consistency(self):
        assert can_transition(Stage.CAPTURED, Stage.TRIAGED)
        assert not can_transition(Stage.REALIZED, Stage.ACTIVE)
        assert not can_transition(Stage.CAPTURED, Stage.ACTIVE)
        # every stage appears in the map
        assert set(ALLOWED_TRANSITIONS) == set(Stage)
