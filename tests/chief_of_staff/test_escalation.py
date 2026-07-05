"""Rule-table tests for the escalation engine (Part 4)."""

from __future__ import annotations

from typing import Any

import pytest

from chief_of_staff.contracts import SafetyRisk
from chief_of_staff.escalation import (
    MAX_AUTONOMOUS_FAILURES,
    EscalationDecision,
    WorkSignals,
    classify_work,
)


class TestNeedsChad:
    @pytest.mark.parametrize(
        ("flag", "rule"),
        [
            ("irreversible", "authority.irreversible"),
            ("spends_money", "authority.money"),
            ("external_side_effects", "authority.external"),
            ("touches_credentials", "authority.credentials"),
            ("policy_conflict", "authority.policy"),
            ("requires_chad_knowledge", "knowledge.chad_only"),
        ],
    )
    def test_authority_flags_escalate(self, flag, rule):
        overrides: dict[str, Any] = {flag: True}
        result = classify_work(WorkSignals(work_id="job-1", **overrides))
        assert result.decision is EscalationDecision.NEEDS_CHAD
        assert result.rule == rule

    @pytest.mark.parametrize("risk", [SafetyRisk.HIGH, SafetyRisk.CRITICAL])
    def test_high_safety_risk_escalates(self, risk):
        result = classify_work(WorkSignals(work_id="job-1", safety_risk=risk))
        assert result.decision is EscalationDecision.NEEDS_CHAD
        assert result.rule == "authority.safety"

    def test_escalation_carries_the_prepared_question(self):
        result = classify_work(
            WorkSignals(
                work_id="job-1",
                spends_money=True,
                escalation_question="Approve the $49/mo Gusto plan?",
            )
        )
        assert result.decision is EscalationDecision.NEEDS_CHAD
        assert result.question == "Approve the $49/mo Gusto plan?"

    def test_escalation_without_prepared_question_asks_nothing_vague(self):
        result = classify_work(WorkSignals(work_id="job-1", irreversible=True))
        assert result.decision is EscalationDecision.NEEDS_CHAD
        assert result.question is None


class TestPause:
    def test_failure_ceiling_pauses(self):
        result = classify_work(
            WorkSignals(work_id="job-1", consecutive_failures=MAX_AUTONOMOUS_FAILURES)
        )
        assert result.decision is EscalationDecision.PAUSE
        assert result.rule == "throttle.failure_ceiling"

    def test_below_failure_ceiling_continues(self):
        result = classify_work(
            WorkSignals(work_id="job-1", consecutive_failures=MAX_AUTONOMOUS_FAILURES - 1)
        )
        assert result.decision is EscalationDecision.CONTINUE

    def test_self_resolving_block_pauses_instead_of_asking(self):
        result = classify_work(
            WorkSignals(
                work_id="job-1",
                blocked_on_external_event=True,
                escalation_question="Should I wait for the rate limit?",
            )
        )
        assert result.decision is EscalationDecision.PAUSE
        # Never ask unnecessary questions: a pause carries no question.
        assert result.question is None


class TestContinue:
    def test_quiet_work_continues_silently(self):
        result = classify_work(WorkSignals(work_id="job-1"))
        assert result.decision is EscalationDecision.CONTINUE
        assert result.question is None

    @pytest.mark.parametrize("risk", [SafetyRisk.NONE, SafetyRisk.LOW, SafetyRisk.MEDIUM])
    def test_medium_and_below_risk_stays_autonomous(self, risk):
        result = classify_work(WorkSignals(work_id="job-1", safety_risk=risk))
        assert result.decision is EscalationDecision.CONTINUE


class TestPrecedence:
    def test_authority_outranks_throttle(self):
        """Money + failures: Chad hears about the money, not the retries."""
        result = classify_work(
            WorkSignals(work_id="job-1", spends_money=True, consecutive_failures=99)
        )
        assert result.decision is EscalationDecision.NEEDS_CHAD
        assert result.rule == "authority.money"

    def test_rule_table_is_deterministic(self):
        signals = WorkSignals(
            work_id="job-1",
            irreversible=True,
            spends_money=True,
            external_side_effects=True,
            safety_risk=SafetyRisk.CRITICAL,
        )
        results = {classify_work(signals).rule for _ in range(10)}
        assert results == {"authority.irreversible"}

    def test_every_result_names_its_rule_and_reason(self):
        for signals in (
            WorkSignals(work_id="a"),
            WorkSignals(work_id="b", blocked_on_external_event=True),
            WorkSignals(work_id="c", policy_conflict=True),
        ):
            result = classify_work(signals)
            assert result.rule
            assert result.reason
