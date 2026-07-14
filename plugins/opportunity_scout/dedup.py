"""Duplicate detection for the Opportunity Scout engine.

Two layers, both stdlib:

1. Exact fingerprint — SHA-256 of the sorted lower-cased token set of the
   title. Catches re-submissions and word-order shuffles.
2. Fuzzy match — blended ``difflib.SequenceMatcher`` title similarity and
   Jaccard similarity over title+tag tokens.
"""

from __future__ import annotations

from difflib import SequenceMatcher
from typing import Iterable

from .models import DuplicateMatch, Opportunity, normalize_tokens, title_fingerprint

DEFAULT_FUZZY_THRESHOLD = 0.82

_SEQUENCE_WEIGHT = 0.6
_JACCARD_WEIGHT = 0.4


def _normalized_title(opportunity: Opportunity) -> str:
    return " ".join(normalize_tokens(opportunity.title))


def _token_set(opportunity: Opportunity) -> set[str]:
    tokens = set(normalize_tokens(opportunity.title))
    for tag in opportunity.tags:
        tokens.update(normalize_tokens(tag))
    return tokens


def _jaccard(left: set[str], right: set[str]) -> float:
    if not left or not right:
        return 0.0
    union = left | right
    return len(left & right) / len(union)


def similarity(left: Opportunity, right: Opportunity) -> float:
    """Blended similarity in [0, 1] between two opportunities."""
    sequence = SequenceMatcher(
        None, _normalized_title(left), _normalized_title(right)
    ).ratio()
    jaccard = _jaccard(_token_set(left), _token_set(right))
    return _SEQUENCE_WEIGHT * sequence + _JACCARD_WEIGHT * jaccard


def find_duplicates(
    candidate: Opportunity,
    existing: Iterable[Opportunity],
    fuzzy_threshold: float = DEFAULT_FUZZY_THRESHOLD,
) -> list[DuplicateMatch]:
    """Return matches sorted by similarity (highest first).

    Exact fingerprint matches always rank ahead of fuzzy matches and are
    reported with similarity 1.0.
    """
    candidate_fingerprint = candidate.fingerprint or title_fingerprint(candidate.title)
    matches: list[DuplicateMatch] = []
    for other in existing:
        if other.opportunity_id == candidate.opportunity_id:
            continue
        if other.fingerprint == candidate_fingerprint:
            matches.append(
                DuplicateMatch(
                    opportunity_id=other.opportunity_id,
                    title=other.title,
                    similarity=1.0,
                    kind="exact",
                )
            )
            continue
        score = similarity(candidate, other)
        if score >= fuzzy_threshold:
            matches.append(
                DuplicateMatch(
                    opportunity_id=other.opportunity_id,
                    title=other.title,
                    similarity=round(score, 4),
                    kind="fuzzy",
                )
            )
    matches.sort(key=lambda match: (match.kind != "exact", -match.similarity))
    return matches
