"""Scoring math and confidence-tracking tests for the Opportunity Scout."""

from __future__ import annotations

import pytest

from plugins.opportunity_scout.confidence import (
    apply_confidence_event,
    stage_failed_delta,
    stage_passed_delta,
)
from plugins.opportunity_scout.models import (
    CONFIDENCE_CEILING,
    CONFIDENCE_FLOOR,
    EvidenceStrength,
    Opportunity,
    SourceType,
)
from plugins.opportunity_scout.scoring import (
    ScoringConfig,
    ScoringError,
    score_opportunity,
)


def make_opportunity(**overrides) -> Opportunity:
    defaults = {
        "title": "Scoring subject",
        "source_type": SourceType.DIRECT_REQUEST,  # prior 0.60
        "expected_revenue_usd": 100_000,
        "upfront_cost_usd": 1_000,
        "chad_hours_upfront": 10,
        "chad_hours_weekly": 1,
        "ai_hours_weekly": 5,
        "tags": ["income-scaling"],
    }
    defaults.update(overrides)
    return Opportunity(**defaults)


class TestScoringConfig:
    def test_weights_must_sum_to_one(self):
        with pytest.raises(ScoringError):
            ScoringConfig(weight_roi=0.9)

    def test_rate_and_capacity_must_be_positive(self):
        with pytest.raises(ScoringError):
            ScoringConfig(chad_hourly_rate=0)
        with pytest.raises(ScoringError):
            ScoringConfig(chad_weekly_capacity_hours=0)


class TestScoringMath:
    def test_economics_derivations(self):
        opp = make_opportunity()
        breakdown = score_opportunity(opp)
        # 10 upfront + 52 * 1 weekly = 62 Chad hours
        assert breakdown.annual_chad_hours == 62.0
        assert breakdown.annual_ai_hours == 260.0
        assert breakdown.chad_time_cost_usd == pytest.approx(62 * 205.0)
        assert breakdown.total_investment_usd == pytest.approx(1000 + 62 * 205.0)
        expected_net = 100_000 * 0.60 - (1000 + 62 * 205.0)
        assert breakdown.expected_net_usd == pytest.approx(expected_net, abs=0.01)
        assert breakdown.expected_roi == pytest.approx(
            expected_net / (1000 + 62 * 205.0), abs=1e-4
        )
        assert breakdown.leverage == pytest.approx(260 / 62, abs=1e-4)

    def test_determinism(self):
        opp = make_opportunity()
        first = score_opportunity(opp)
        second = score_opportunity(opp)
        assert first.composite == second.composite
        assert first.expected_roi == second.expected_roi

    def test_zero_time_opportunity_does_not_explode(self):
        opp = make_opportunity(
            chad_hours_upfront=0, chad_hours_weekly=0, ai_hours_weekly=0
        )
        breakdown = score_opportunity(opp)
        assert breakdown.leverage == 0.0
        assert 0 <= breakdown.composite <= 100

    def test_alignment_component(self):
        config = ScoringConfig(
            strategic_goals={"income-scaling": 1.0, "automation": 1.0}
        )
        full = make_opportunity(tags=["income-scaling", "automation"])
        half = make_opportunity(tags=["income-scaling"])
        none = make_opportunity(tags=["random"])
        assert score_opportunity(full, config).alignment_component == 1.0
        assert score_opportunity(half, config).alignment_component == 0.5
        assert score_opportunity(none, config).alignment_component == 0.0

    def test_capacity_penalty(self):
        config = ScoringConfig(chad_weekly_capacity_hours=5.0)
        within = make_opportunity(chad_hours_weekly=5)
        double = make_opportunity(chad_hours_weekly=10)
        triple = make_opportunity(chad_hours_weekly=15)
        assert score_opportunity(within, config).capacity_component == 1.0
        assert score_opportunity(double, config).capacity_component == pytest.approx(0.5)
        assert score_opportunity(triple, config).capacity_component == 0.0

    def test_higher_roi_scores_higher(self):
        low = make_opportunity(expected_revenue_usd=20_000)
        high = make_opportunity(expected_revenue_usd=500_000)
        assert (
            score_opportunity(high).composite > score_opportunity(low).composite
        )

    def test_negative_net_still_bounded(self):
        money_pit = make_opportunity(
            expected_revenue_usd=0, upfront_cost_usd=50_000
        )
        breakdown = score_opportunity(money_pit)
        assert breakdown.expected_roi < 0
        assert 0 <= breakdown.composite <= 100
        assert breakdown.roi_component < 0.5


class TestConfidence:
    def test_event_moves_confidence_and_records_audit(self):
        opp = make_opportunity()
        event = apply_confidence_event(opp, 0.1, "Strong demand signal")
        assert opp.confidence == pytest.approx(0.70)
        assert event.resulting == opp.confidence
        assert opp.confidence_events[-1].reason == "Strong demand signal"

    def test_clamped_at_ceiling_and_floor(self):
        opp = make_opportunity()
        apply_confidence_event(opp, 5.0, "absurd optimism")
        assert opp.confidence == CONFIDENCE_CEILING
        apply_confidence_event(opp, -5.0, "absurd pessimism")
        assert opp.confidence == CONFIDENCE_FLOOR

    def test_recorded_delta_reflects_clamping(self):
        opp = make_opportunity()
        event = apply_confidence_event(opp, 5.0, "clamped")
        assert event.delta == pytest.approx(CONFIDENCE_CEILING - 0.60)

    def test_reason_required(self):
        with pytest.raises(ValueError):
            apply_confidence_event(make_opportunity(), 0.1, "   ")

    def test_stage_deltas(self):
        assert stage_passed_delta(0.10, EvidenceStrength.STRONG) == pytest.approx(0.10)
        assert stage_passed_delta(0.10, EvidenceStrength.WEAK) == pytest.approx(0.05)
        assert stage_failed_delta(0.10) == pytest.approx(-0.10)
