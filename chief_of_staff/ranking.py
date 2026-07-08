"""Deterministic recommendation ranking — Part 5 of the Chief of Staff design.

Priority order, strictly lexicographic (each criterion only breaks ties left
by every criterion before it):

1. **Safety**              — lower :class:`~chief_of_staff.contracts.SafetyRisk` first.
2. **Highest ROI**         — larger ``expected_roi_usd`` first.
3. **Lowest Chad effort**  — fewer ``chad_effort_minutes`` first.
4. **Strategic alignment** — larger ``strategic_alignment`` first.
5. **Confidence**          — larger ``confidence`` first.

A final tiebreak on ``id`` (lexicographic) makes the order *total*: the same
input set always produces the same output order, regardless of input order.
No randomness, no model temperature, no hidden state — an executive assistant
whose priorities change between identical mornings is not trustworthy.
"""

from __future__ import annotations

from collections.abc import Iterable

from chief_of_staff.contracts import Recommendation


def ranking_key(rec: Recommendation) -> tuple[int, float, int, float, float, str]:
    """Sort key implementing the priority order (ascending sort).

    Exposed separately so tests and future UI code can explain *why* one
    recommendation outranks another.
    """
    return (
        int(rec.safety_risk),        # 1. safety: safer (lower) first
        -rec.expected_roi_usd,       # 2. ROI: higher first
        rec.chad_effort_minutes,     # 3. Chad effort: lower first
        -rec.strategic_alignment,    # 4. alignment: higher first
        -rec.confidence,             # 5. confidence: higher first
        rec.id,                      # total-order tiebreak
    )


def rank_recommendations(recommendations: Iterable[Recommendation]) -> list[Recommendation]:
    """Return recommendations best-first under the deterministic priority order."""
    return sorted(recommendations, key=ranking_key)


def top_recommendation(recommendations: Iterable[Recommendation]) -> Recommendation | None:
    """The single best recommendation, or ``None`` for an empty input."""
    ranked = rank_recommendations(recommendations)
    return ranked[0] if ranked else None
