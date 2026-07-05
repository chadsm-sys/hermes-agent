"""Scoring engine for the Opportunity Scout.

Pure, deterministic functions. Given the same opportunity and config, the
score is always identical — no randomness, no network, no clock dependence
except the ``scored_at`` stamp on the breakdown.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field

from .models import Opportunity, OpportunityScoutError, ScoreBreakdown

WEEKS_PER_YEAR = 52.0
_MIN_CHAD_HOURS = 0.25  # avoid divide-by-zero leverage explosions


class ScoringError(OpportunityScoutError):
    pass


def _default_strategic_goals() -> dict[str, float]:
    """Tag → weight map seeded from active goals (fully overridable)."""
    return {
        "income-scaling": 1.0,
        "direct-contracts": 0.9,
        "expert-witness": 0.9,
        "anesthesia": 0.8,
        "recurring-revenue": 0.8,
        "automation": 0.7,
        "s-corp": 0.5,
        "family-time": 0.6,
    }


@dataclass
class ScoringConfig:
    chad_hourly_rate: float = 205.0
    chad_weekly_capacity_hours: float = 5.0
    strategic_goals: dict[str, float] = field(default_factory=_default_strategic_goals)
    weight_roi: float = 0.40
    weight_alignment: float = 0.25
    weight_leverage: float = 0.15
    weight_confidence: float = 0.10
    weight_capacity: float = 0.10

    def __post_init__(self) -> None:
        total = (
            self.weight_roi
            + self.weight_alignment
            + self.weight_leverage
            + self.weight_confidence
            + self.weight_capacity
        )
        if abs(total - 1.0) > 1e-9:
            raise ScoringError(f"Component weights must sum to 1.0, got {total}")
        if self.chad_hourly_rate <= 0:
            raise ScoringError("chad_hourly_rate must be positive.")
        if self.chad_weekly_capacity_hours <= 0:
            raise ScoringError("chad_weekly_capacity_hours must be positive.")


def _roi_component(roi: float) -> float:
    """Map ROI to [0, 1]; saturates near ROI ≈ 3x, punishes negatives."""
    return (math.tanh(roi / 3.0) + 1.0) / 2.0


def _alignment_component(opportunity: Opportunity, config: ScoringConfig) -> float:
    goals = config.strategic_goals
    if not goals:
        return 0.0
    total_weight = sum(goals.values())
    if total_weight <= 0:
        return 0.0
    matched = sum(weight for tag, weight in goals.items() if tag in opportunity.tags)
    return matched / total_weight


def _leverage_component(leverage: float) -> float:
    return min(leverage, 10.0) / 10.0


def _capacity_component(weekly_hours: float, capacity: float) -> float:
    """1.0 when within capacity; linear penalty to 0 at 3x capacity."""
    if weekly_hours <= capacity:
        return 1.0
    overload = (weekly_hours - capacity) / (2.0 * capacity)
    return max(0.0, 1.0 - overload)


def score_opportunity(
    opportunity: Opportunity, config: ScoringConfig | None = None
) -> ScoreBreakdown:
    config = config or ScoringConfig()

    annual_chad_hours = (
        opportunity.chad_hours_upfront
        + WEEKS_PER_YEAR * opportunity.chad_hours_weekly
    )
    annual_ai_hours = (
        opportunity.ai_hours_upfront + WEEKS_PER_YEAR * opportunity.ai_hours_weekly
    )
    chad_time_cost = annual_chad_hours * config.chad_hourly_rate
    total_investment = opportunity.upfront_cost_usd + chad_time_cost
    expected_net = (
        opportunity.expected_revenue_usd * opportunity.confidence
        - opportunity.ongoing_cost_usd_annual
        - total_investment
    )
    expected_roi = expected_net / max(total_investment, 1.0)
    leverage = annual_ai_hours / max(annual_chad_hours, _MIN_CHAD_HOURS)

    roi_component = _roi_component(expected_roi)
    alignment_component = _alignment_component(opportunity, config)
    leverage_component = _leverage_component(leverage)
    confidence_component = opportunity.confidence
    capacity_component = _capacity_component(
        opportunity.chad_hours_weekly, config.chad_weekly_capacity_hours
    )

    composite = 100.0 * (
        config.weight_roi * roi_component
        + config.weight_alignment * alignment_component
        + config.weight_leverage * leverage_component
        + config.weight_confidence * confidence_component
        + config.weight_capacity * capacity_component
    )

    return ScoreBreakdown(
        annual_chad_hours=round(annual_chad_hours, 2),
        annual_ai_hours=round(annual_ai_hours, 2),
        chad_time_cost_usd=round(chad_time_cost, 2),
        total_investment_usd=round(total_investment, 2),
        expected_net_usd=round(expected_net, 2),
        expected_roi=round(expected_roi, 4),
        leverage=round(leverage, 4),
        roi_component=round(roi_component, 4),
        alignment_component=round(alignment_component, 4),
        leverage_component=round(leverage_component, 4),
        confidence_component=round(confidence_component, 4),
        capacity_component=round(capacity_component, 4),
        composite=round(composite, 2),
    )
