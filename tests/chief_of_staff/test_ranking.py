"""Determinism tests for recommendation ranking (Part 5).

Priority order: Safety > Highest ROI > Lowest Chad effort > Strategic
alignment > Confidence, with a final id tiebreak for a total order.
"""

from __future__ import annotations

import random

from chief_of_staff.contracts import Recommendation, SafetyRisk
from chief_of_staff.ranking import rank_recommendations, ranking_key, top_recommendation


def rec(
    rec_id: str,
    *,
    risk: SafetyRisk = SafetyRisk.LOW,
    roi: float = 1000.0,
    effort: int = 30,
    alignment: float = 0.5,
    confidence: float = 0.5,
) -> Recommendation:
    return Recommendation(
        id=rec_id,
        title=f"Recommendation {rec_id}",
        rationale="test fixture",
        safety_risk=risk,
        expected_roi_usd=roi,
        chad_effort_minutes=effort,
        strategic_alignment=alignment,
        confidence=confidence,
    )


class TestPriorityOrder:
    def test_safety_beats_roi(self):
        safe_low_roi = rec("a", risk=SafetyRisk.NONE, roi=10.0)
        risky_high_roi = rec("b", risk=SafetyRisk.MEDIUM, roi=1_000_000.0)
        assert rank_recommendations([risky_high_roi, safe_low_roi])[0] is safe_low_roi

    def test_roi_beats_effort(self):
        high_roi_high_effort = rec("a", roi=50_000.0, effort=120)
        low_roi_zero_effort = rec("b", roi=100.0, effort=0)
        ranked = rank_recommendations([low_roi_zero_effort, high_roi_high_effort])
        assert ranked[0] is high_roi_high_effort

    def test_effort_beats_alignment(self):
        lazy_misaligned = rec("a", effort=5, alignment=0.1)
        laborious_aligned = rec("b", effort=90, alignment=1.0)
        ranked = rank_recommendations([laborious_aligned, lazy_misaligned])
        assert ranked[0] is lazy_misaligned

    def test_alignment_beats_confidence(self):
        aligned_unsure = rec("a", alignment=0.9, confidence=0.1)
        misaligned_certain = rec("b", alignment=0.2, confidence=1.0)
        ranked = rank_recommendations([misaligned_certain, aligned_unsure])
        assert ranked[0] is aligned_unsure

    def test_confidence_breaks_remaining_ties(self):
        confident = rec("a", confidence=0.9)
        hesitant = rec("b", confidence=0.2)
        assert rank_recommendations([hesitant, confident])[0] is confident

    def test_id_makes_order_total(self):
        twin_a = rec("alpha")
        twin_b = rec("beta")
        assert rank_recommendations([twin_b, twin_a]) == [twin_a, twin_b]
        assert rank_recommendations([twin_a, twin_b]) == [twin_a, twin_b]


class TestDeterminism:
    def test_input_order_never_matters(self):
        pool = [
            rec("r1", risk=SafetyRisk.NONE, roi=500.0, effort=10),
            rec("r2", risk=SafetyRisk.LOW, roi=9000.0, effort=60),
            rec("r3", risk=SafetyRisk.LOW, roi=9000.0, effort=15),
            rec("r4", risk=SafetyRisk.CRITICAL, roi=99999.0, effort=0),
            rec("r5", risk=SafetyRisk.NONE, roi=500.0, effort=10, alignment=0.9),
        ]
        rng = random.Random(205)
        baseline = rank_recommendations(pool)
        for _ in range(25):
            shuffled = pool[:]
            rng.shuffle(shuffled)
            assert rank_recommendations(shuffled) == baseline

    def test_ranking_key_matches_documented_signature(self):
        r = rec("x", risk=SafetyRisk.MEDIUM, roi=750.0, effort=20, alignment=0.4, confidence=0.6)
        assert ranking_key(r) == (2, -750.0, 20, -0.4, -0.6, "x")

    def test_ranking_never_mutates_input(self):
        pool = [rec("b"), rec("a")]
        rank_recommendations(pool)
        assert [r.id for r in pool] == ["b", "a"]


class TestTopRecommendation:
    def test_returns_best(self):
        best = rec("best", risk=SafetyRisk.NONE, roi=10_000.0)
        assert top_recommendation([rec("meh"), best]) is best

    def test_empty_input_returns_none(self):
        assert top_recommendation([]) is None
