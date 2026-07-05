"""Governance engine for the memorygraph provider.

Turns raw writes into *governed* knowledge:

  duplicate detection     — re-asserting known knowledge reinforces instead
                            of duplicating (normalized-key + fuzzy match)
  contradiction detection — conflicting values for an exclusive attribute are
                            either superseded (time-aware update) or flagged
                            as contradicted for review
  confidence tracking     — reinforcement raises confidence, feedback and
                            contradiction lower it, all clamped to [0, 1]
  knowledge aging         — confidence decays with a configurable half-life
                            since last reinforcement; decayed core/established
                            knowledge is demoted
  knowledge promotion     — candidate → established → core, gated on
                            confidence, evidence count, reinforcement count
                            and age, never while contradicted

Every governed mutation is written to the store's governance_log so the
graph stays auditable.
"""

from __future__ import annotations

import difflib
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

from .store import GraphStore, normalize_key, parse_ts


@dataclass
class GovernancePolicy:
    """Tunable thresholds. Defaults are deliberately conservative."""

    # Duplicate detection
    duplicate_similarity: float = 0.88

    # Confidence tracking
    reinforce_delta: float = 0.10
    contradiction_penalty: float = 0.15
    feedback_delta: float = 0.15
    min_confidence: float = 0.0
    max_confidence: float = 1.0

    # Aging
    half_life_days: float = 90.0
    stale_confidence_floor: float = 0.15
    demotion_confidence: float = 0.40

    # Promotion
    promote_established_confidence: float = 0.70
    promote_established_evidence: int = 2
    promote_core_confidence: float = 0.85
    promote_core_reinforcements: int = 3
    promote_core_min_age_days: float = 7.0


def _clamp(value: float, lo: float = 0.0, hi: float = 1.0) -> float:
    return max(lo, min(hi, value))


def text_similarity(a: str, b: str) -> float:
    """Similarity in [0, 1] combining token Jaccard and sequence ratio."""
    ka, kb = normalize_key(a), normalize_key(b)
    if not ka or not kb:
        return 0.0
    if ka == kb:
        return 1.0
    ta, tb = set(ka.split()), set(kb.split())
    jaccard = len(ta & tb) / len(ta | tb) if (ta | tb) else 0.0
    ratio = difflib.SequenceMatcher(None, ka, kb).ratio()
    return max(jaccard, ratio)


class GovernanceEngine:
    """Applies governance policy to a GraphStore."""

    def __init__(self, store: GraphStore, policy: Optional[GovernancePolicy] = None):
        self.store = store
        self.policy = policy or GovernancePolicy()

    # -- governed write ------------------------------------------------------

    def assert_claim(
        self,
        entity_id: int,
        attribute: str,
        value: str,
        confidence: float = 0.6,
        exclusive: bool = False,
        valid_from: str = "",
        evidence: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Governed claim write. Returns {claim, outcome, [conflicts]}.

        Outcomes:
          created      — new knowledge
          reinforced   — duplicate of existing active claim (confidence up)
          superseded   — exclusive attribute updated time-aware (old claim's
                         validity window closed, linked via superseded_by)
          contradicted — conflicting exclusive values with no clear temporal
                         ordering; both flagged for review
        """
        attribute_key = normalize_key(attribute) or "note"
        existing = self.store.claims_for(entity_id, attribute_key, status="active")

        # 1. Duplicate detection → reinforcement.
        # Exclusive (single-valued) attributes hold short distinguishing
        # values ("Facility A" vs "Facility B") where fuzzy matching would
        # swallow genuine updates — restrict them to exact-key matches.
        exact_only = exclusive or any(c["exclusive"] for c in existing)
        dup = self._find_duplicate(existing, value, exact_only=exact_only)
        if dup is not None:
            reinforced = self.reinforce(dup["id"])
            if evidence:
                self.store.add_evidence("claim", dup["id"], **evidence)
            self.store.log_event("claim_reinforced", "claim", dup["id"],
                                 {"similarity_value": value})
            return {"claim": reinforced, "outcome": "reinforced"}

        # 2. Contradiction detection (exclusive = single-valued attribute)
        conflicts = [c for c in existing if c["exclusive"] or exclusive]
        if conflicts and (exclusive or any(c["exclusive"] for c in conflicts)):
            new_from = valid_from or self.store.now()
            newer = all(new_from >= c["valid_from"] for c in conflicts)
            if newer:
                # Time-aware update: new value supersedes older ones.
                claim = self.store.insert_claim(
                    entity_id, attribute_key, value, confidence,
                    exclusive=True, valid_from=new_from,
                )
                for old in conflicts:
                    self.store.update_claim(
                        old["id"], status="superseded",
                        valid_to=new_from, superseded_by=claim["id"],
                    )
                    self.store.log_event("claim_superseded", "claim", old["id"],
                                         {"by": claim["id"]})
                if evidence:
                    self.store.add_evidence("claim", claim["id"], **evidence)
                return {
                    "claim": self.store.get_claim(claim["id"]),
                    "outcome": "superseded",
                    "conflicts": [old["id"] for old in conflicts],
                }
            # Ambiguous temporal ordering — flag everything for review.
            claim = self.store.insert_claim(
                entity_id, attribute_key, value, confidence,
                exclusive=True, valid_from=new_from,
            )
            penalty = self.policy.contradiction_penalty
            for c in [claim, *conflicts]:
                self.store.update_claim(
                    c["id"], status="contradicted",
                    confidence=_clamp(float(c["confidence"]) - penalty),
                )
                self.store.log_event("claim_contradicted", "claim", c["id"],
                                     {"group": [claim["id"], *(x["id"] for x in conflicts)]})
            if evidence:
                self.store.add_evidence("claim", claim["id"], **evidence)
            return {
                "claim": self.store.get_claim(claim["id"]),
                "outcome": "contradicted",
                "conflicts": [c["id"] for c in conflicts],
            }

        # 3. Plain create
        claim = self.store.insert_claim(
            entity_id, attribute_key, value, confidence,
            exclusive=exclusive, valid_from=valid_from,
        )
        if evidence:
            self.store.add_evidence("claim", claim["id"], **evidence)
        return {"claim": claim, "outcome": "created"}

    def _find_duplicate(
        self,
        existing: List[Dict[str, Any]],
        value: str,
        exact_only: bool = False,
    ) -> Optional[Dict[str, Any]]:
        value_key = normalize_key(value)
        best, best_score = None, 0.0
        for claim in existing:
            if claim["value_key"] == value_key:
                return claim
            if exact_only:
                continue
            score = text_similarity(claim["value"], value)
            if score > best_score:
                best, best_score = claim, score
        if best is not None and best_score >= self.policy.duplicate_similarity:
            return best
        return None

    # -- confidence tracking ---------------------------------------------------

    def reinforce(self, claim_id: int) -> Optional[Dict[str, Any]]:
        claim = self.store.get_claim(claim_id)
        if not claim:
            return None
        self.store.update_claim(
            claim_id,
            confidence=_clamp(float(claim["confidence"]) + self.policy.reinforce_delta),
            reinforcement_count=int(claim["reinforcement_count"]) + 1,
            last_reinforced_at=self.store.now(),
        )
        return self.store.get_claim(claim_id)

    def feedback(self, claim_id: int, helpful: bool) -> Optional[Dict[str, Any]]:
        claim = self.store.get_claim(claim_id)
        if not claim:
            return None
        delta = self.policy.feedback_delta if helpful else -self.policy.feedback_delta
        fields: Dict[str, Any] = {"confidence": _clamp(float(claim["confidence"]) + delta)}
        if helpful:
            fields["last_reinforced_at"] = self.store.now()
            fields["reinforcement_count"] = int(claim["reinforcement_count"]) + 1
        self.store.update_claim(claim_id, **fields)
        self.store.log_event("claim_feedback", "claim", claim_id, {"helpful": helpful})
        return self.store.get_claim(claim_id)

    def retract(self, claim_id: int, reason: str = "") -> bool:
        claim = self.store.get_claim(claim_id)
        if not claim or claim["status"] == "retracted":
            return False
        self.store.update_claim(claim_id, status="retracted", valid_to=self.store.now())
        self.store.log_event("claim_retracted", "claim", claim_id, {"reason": reason})
        return True

    def resolve_contradiction(self, winner_id: int) -> Dict[str, Any]:
        """Keep one claim from a contradicted group; supersede the rest."""
        winner = self.store.get_claim(winner_id)
        if not winner:
            return {"error": f"claim {winner_id} not found"}
        losers = [
            c for c in self.store.claims_for(
                winner["entity_id"], winner["attribute"], status="contradicted")
            if c["id"] != winner_id
        ]
        self.store.update_claim(winner_id, status="active")
        for loser in losers:
            self.store.update_claim(
                loser["id"], status="superseded",
                valid_to=self.store.now(), superseded_by=winner_id,
            )
        self.store.log_event("contradiction_resolved", "claim", winner_id,
                             {"superseded": [loser["id"] for loser in losers]})
        return {"winner": self.store.get_claim(winner_id),
                "superseded": [loser["id"] for loser in losers]}

    # -- audits ------------------------------------------------------------------

    def find_contradictions(self) -> List[List[Dict[str, Any]]]:
        """Groups of claims currently flagged as contradicted."""
        flagged = self.store.claims_by_status("contradicted")
        groups: Dict[tuple, List[Dict[str, Any]]] = {}
        for claim in flagged:
            groups.setdefault((claim["entity_id"], claim["attribute"]), []).append(claim)
        return [g for g in groups.values() if len(g) >= 2]

    def find_duplicates(self) -> List[List[Dict[str, Any]]]:
        """Near-duplicate active claim groups that slipped past write-time checks."""
        by_bucket: Dict[tuple, List[Dict[str, Any]]] = {}
        for claim in self.store.all_active_claims():
            by_bucket.setdefault((claim["entity_id"], claim["attribute"]), []).append(claim)
        out: List[List[Dict[str, Any]]] = []
        for claims in by_bucket.values():
            if len(claims) < 2:
                continue
            used: set = set()
            for i, a in enumerate(claims):
                if a["id"] in used:
                    continue
                group = [a]
                for b in claims[i + 1:]:
                    if b["id"] in used:
                        continue
                    if text_similarity(a["value"], b["value"]) >= self.policy.duplicate_similarity:
                        group.append(b)
                        used.add(b["id"])
                if len(group) >= 2:
                    used.add(a["id"])
                    out.append(group)
        return out

    # -- aging + promotion sweeps -----------------------------------------------

    def age_knowledge(self, now: str = "") -> Dict[str, int]:
        """Decay confidence by half-life since last reinforcement; demote decayed."""
        now_ts = parse_ts(now or self.store.now())
        half_life = max(1e-6, self.policy.half_life_days)
        decayed = demoted = 0
        for claim in self.store.all_active_claims():
            age_days = (now_ts - parse_ts(claim["last_reinforced_at"])).total_seconds() / 86400.0
            if age_days <= 0:
                continue
            factor = 0.5 ** (age_days / half_life)
            new_conf = max(
                self.policy.stale_confidence_floor,
                round(float(claim["confidence"]) * factor, 4),
            )
            if new_conf >= float(claim["confidence"]):
                continue
            fields: Dict[str, Any] = {"confidence": new_conf}
            if (claim["tier"] in ("established", "core")
                    and new_conf < self.policy.demotion_confidence):
                demote_to = "established" if claim["tier"] == "core" else "candidate"
                fields["tier"] = demote_to
                demoted += 1
                self.store.log_event("claim_demoted", "claim", claim["id"],
                                     {"from": claim["tier"], "to": demote_to})
            self.store.update_claim(claim["id"], **fields)
            decayed += 1
        self.store.set_meta("last_aging_run", now or self.store.now())
        return {"decayed": decayed, "demoted": demoted}

    def promote_knowledge(self, now: str = "") -> Dict[str, int]:
        """Promote well-evidenced, reinforced, uncontradicted knowledge."""
        now_ts = parse_ts(now or self.store.now())
        promoted_established = promoted_core = 0
        for claim in self.store.all_active_claims():
            conf = float(claim["confidence"])
            if claim["tier"] == "candidate":
                evidence_n = self.store.evidence_count("claim", claim["id"])
                if (conf >= self.policy.promote_established_confidence
                        and evidence_n >= self.policy.promote_established_evidence):
                    self.store.update_claim(claim["id"], tier="established")
                    self.store.log_event("claim_promoted", "claim", claim["id"],
                                         {"to": "established"})
                    promoted_established += 1
            elif claim["tier"] == "established":
                age_days = (now_ts - parse_ts(claim["created_at"])).total_seconds() / 86400.0
                if (conf >= self.policy.promote_core_confidence
                        and int(claim["reinforcement_count"]) >= self.policy.promote_core_reinforcements
                        and age_days >= self.policy.promote_core_min_age_days):
                    self.store.update_claim(claim["id"], tier="core")
                    self.store.log_event("claim_promoted", "claim", claim["id"], {"to": "core"})
                    promoted_core += 1
        return {"established": promoted_established, "core": promoted_core}

    def sweep(self, now: str = "") -> Dict[str, Any]:
        """Full governance sweep: aging then promotion."""
        aged = self.age_knowledge(now)
        promoted = self.promote_knowledge(now)
        return {"aging": aged, "promotion": promoted}
