"""Tests for the memorygraph GovernanceEngine: duplicate detection,
contradiction detection, confidence tracking, aging, and promotion."""

from datetime import datetime, timedelta, timezone

import pytest

from plugins.memory.memorygraph.governance import (
    GovernanceEngine,
    GovernancePolicy,
    text_similarity,
)
from plugins.memory.memorygraph.store import GraphStore


class FakeClock:
    def __init__(self, start="2026-07-01T00:00:00Z"):
        self.current = datetime.strptime(start, "%Y-%m-%dT%H:%M:%SZ").replace(
            tzinfo=timezone.utc
        )

    def __call__(self):
        return self.current.strftime("%Y-%m-%dT%H:%M:%SZ")

    def advance(self, days=0, hours=0):
        self.current += timedelta(days=days, hours=hours)


@pytest.fixture
def clock():
    return FakeClock()


@pytest.fixture
def store(tmp_path, clock):
    s = GraphStore(str(tmp_path / "graph.db"), now=clock)
    yield s
    s.close()


@pytest.fixture
def engine(store):
    return GovernanceEngine(store, GovernancePolicy())


@pytest.fixture
def entity(store):
    return store.upsert_entity("Chad", "person")


def test_text_similarity():
    assert text_similarity("works at Facility A", "works at Facility A") == 1.0
    assert text_similarity("Works at Facility A!", "works at facility a") == 1.0
    assert text_similarity("bench press goal 200", "bench press goal 200 lbs") > 0.8
    assert text_similarity("apples", "submarine") < 0.5
    assert text_similarity("", "anything") == 0.0


# -- duplicate detection ------------------------------------------------------


def test_duplicate_reinforces_instead_of_duplicating(engine, store, entity):
    r1 = engine.assert_claim(entity["id"], "employer", "Facility A", confidence=0.6)
    assert r1["outcome"] == "created"
    r2 = engine.assert_claim(entity["id"], "employer", "facility a")
    assert r2["outcome"] == "reinforced"
    assert r2["claim"]["id"] == r1["claim"]["id"]
    assert r2["claim"]["confidence"] == pytest.approx(0.7)
    assert r2["claim"]["reinforcement_count"] == 1
    assert len(store.claims_for(entity["id"], "employer")) == 1


def test_near_duplicate_fuzzy_match(engine, entity):
    engine.assert_claim(entity["id"], "goal", "bench press 200 lbs by December")
    r = engine.assert_claim(entity["id"], "goal", "bench press 200lbs by December!")
    assert r["outcome"] == "reinforced"


def test_distinct_values_do_not_dedupe(engine, store, entity):
    engine.assert_claim(entity["id"], "skill", "regional anesthesia")
    r = engine.assert_claim(entity["id"], "skill", "pediatric airway management")
    assert r["outcome"] == "created"
    assert len(store.claims_for(entity["id"], "skill")) == 2


def test_duplicate_evidence_accumulates(engine, store, entity):
    r1 = engine.assert_claim(
        entity["id"], "employer", "Facility A",
        evidence={"kind": "session", "ref": "s1"},
    )
    engine.assert_claim(
        entity["id"], "employer", "Facility A",
        evidence={"kind": "session", "ref": "s2"},
    )
    assert store.evidence_count("claim", r1["claim"]["id"]) == 2


def test_find_duplicates_audit(engine, store, entity):
    # Insert raw (ungoverned) near-duplicates, then audit.
    store.insert_claim(entity["id"], "note", "drinks black coffee every morning")
    store.insert_claim(entity["id"], "note", "drinks black coffee every morning!!")
    store.insert_claim(entity["id"], "note", "allergic to shellfish")
    groups = engine.find_duplicates()
    assert len(groups) == 1
    assert len(groups[0]) == 2


# -- contradiction detection ------------------------------------------------------


def test_exclusive_newer_value_supersedes(engine, store, entity, clock):
    r1 = engine.assert_claim(entity["id"], "employer", "Facility A", exclusive=True)
    clock.advance(days=10)
    r2 = engine.assert_claim(entity["id"], "employer", "Facility B", exclusive=True)
    assert r2["outcome"] == "superseded"
    old = store.get_claim(r1["claim"]["id"])
    assert old["status"] == "superseded"
    assert old["superseded_by"] == r2["claim"]["id"]
    assert old["valid_to"] == r2["claim"]["valid_from"]
    active = store.claims_for(entity["id"], "employer")
    assert [c["value"] for c in active] == ["Facility B"]


def test_ambiguous_conflict_flags_contradiction(engine, store, entity, clock):
    engine.assert_claim(entity["id"], "employer", "Facility A", exclusive=True)
    clock.advance(days=10)
    engine.assert_claim(entity["id"], "employer", "Facility B", exclusive=True)
    # Backdated claim: older than the current active one → ambiguous.
    r3 = engine.assert_claim(
        entity["id"], "employer", "Facility C", exclusive=True,
        valid_from="2026-07-05T00:00:00Z",
    )
    assert r3["outcome"] == "contradicted"
    assert store.get_claim(r3["claim"]["id"])["status"] == "contradicted"
    groups = engine.find_contradictions()
    assert len(groups) == 1
    assert len(groups[0]) == 2


def test_contradiction_lowers_confidence(engine, store, entity):
    r1 = engine.assert_claim(
        entity["id"], "employer", "Facility A", exclusive=True, confidence=0.8,
        valid_from="2026-07-02T00:00:00Z",
    )
    r2 = engine.assert_claim(
        entity["id"], "employer", "Facility B", exclusive=True, confidence=0.8,
        valid_from="2026-07-01T00:00:00Z",  # backdated → ambiguous
    )
    assert r2["outcome"] == "contradicted"
    assert store.get_claim(r1["claim"]["id"])["confidence"] == pytest.approx(0.65)
    assert store.get_claim(r2["claim"]["id"])["confidence"] == pytest.approx(0.65)


def test_resolve_contradiction(engine, store, entity):
    engine.assert_claim(
        entity["id"], "employer", "Facility A", exclusive=True,
        valid_from="2026-07-02T00:00:00Z",
    )
    r2 = engine.assert_claim(
        entity["id"], "employer", "Facility B", exclusive=True,
        valid_from="2026-07-01T00:00:00Z",
    )
    result = engine.resolve_contradiction(r2["claim"]["id"])
    assert result["winner"]["status"] == "active"
    assert len(result["superseded"]) == 1
    assert engine.find_contradictions() == []


def test_non_exclusive_claims_coexist(engine, store, entity):
    engine.assert_claim(entity["id"], "hobby", "hockey with Colin")
    r = engine.assert_claim(entity["id"], "hobby", "golf")
    assert r["outcome"] == "created"
    assert len(store.claims_for(entity["id"], "hobby")) == 2


# -- confidence tracking ---------------------------------------------------------


def test_confidence_clamped_at_one(engine, entity):
    r = engine.assert_claim(entity["id"], "fact", "stable truth", confidence=0.99)
    for _ in range(5):
        r = {"claim": engine.reinforce(r["claim"]["id"])}
    assert r["claim"]["confidence"] == 1.0


def test_feedback_adjusts_confidence(engine, entity):
    r = engine.assert_claim(entity["id"], "fact", "something", confidence=0.5)
    up = engine.feedback(r["claim"]["id"], helpful=True)
    assert up["confidence"] == pytest.approx(0.65)
    assert up["reinforcement_count"] == 1
    down = engine.feedback(r["claim"]["id"], helpful=False)
    assert down["confidence"] == pytest.approx(0.5)
    assert engine.feedback(9999, helpful=True) is None


def test_retract(engine, store, entity):
    r = engine.assert_claim(entity["id"], "fact", "wrong thing")
    assert engine.retract(r["claim"]["id"], "user asked") is True
    assert engine.retract(r["claim"]["id"]) is False  # already retracted
    assert store.get_claim(r["claim"]["id"])["status"] == "retracted"
    assert store.claims_for(entity["id"], "fact") == []


# -- knowledge aging -----------------------------------------------------------------


def test_aging_decays_confidence(engine, store, entity, clock):
    r = engine.assert_claim(entity["id"], "fact", "ages over time", confidence=0.8)
    clock.advance(days=90)  # exactly one half-life
    result = engine.age_knowledge()
    assert result["decayed"] == 1
    aged = store.get_claim(r["claim"]["id"])
    assert aged["confidence"] == pytest.approx(0.4, abs=0.01)


def test_aging_has_confidence_floor(engine, store, entity, clock):
    r = engine.assert_claim(entity["id"], "fact", "ancient", confidence=0.8)
    clock.advance(days=3650)
    engine.age_knowledge()
    assert store.get_claim(r["claim"]["id"])["confidence"] == pytest.approx(0.15)


def test_aging_skips_fresh_claims(engine, entity, clock):
    engine.assert_claim(entity["id"], "fact", "brand new")
    assert engine.age_knowledge()["decayed"] == 0


def test_reinforcement_resets_aging(engine, store, entity, clock):
    r = engine.assert_claim(entity["id"], "fact", "kept alive", confidence=0.8)
    clock.advance(days=89)
    engine.reinforce(r["claim"]["id"])  # refreshes last_reinforced_at
    engine.age_knowledge()
    # No decay: last reinforcement is "now".
    assert store.get_claim(r["claim"]["id"])["confidence"] == pytest.approx(0.9)


def test_aging_demotes_decayed_established(engine, store, entity, clock):
    r = engine.assert_claim(entity["id"], "fact", "was solid", confidence=0.8)
    store.update_claim(r["claim"]["id"], tier="established")
    clock.advance(days=180)  # two half-lives → 0.2 < demotion threshold 0.4
    result = engine.age_knowledge()
    assert result["demoted"] == 1
    assert store.get_claim(r["claim"]["id"])["tier"] == "candidate"


# -- knowledge promotion ----------------------------------------------------------------


def test_promotion_candidate_to_established(engine, store, entity):
    r = engine.assert_claim(
        entity["id"], "fact", "well evidenced", confidence=0.6,
        evidence={"kind": "session", "ref": "s1"},
    )
    claim_id = r["claim"]["id"]
    engine.assert_claim(  # duplicate → reinforce + second evidence link
        entity["id"], "fact", "well evidenced",
        evidence={"kind": "url", "ref": "https://example.com"},
    )
    result = engine.promote_knowledge()
    assert result["established"] == 1
    assert store.get_claim(claim_id)["tier"] == "established"


def test_promotion_requires_evidence(engine, store, entity):
    r = engine.assert_claim(entity["id"], "fact", "confident but unevidenced",
                            confidence=0.95)
    engine.promote_knowledge()
    assert store.get_claim(r["claim"]["id"])["tier"] == "candidate"


def test_promotion_established_to_core_requires_age_and_reinforcement(
    engine, store, entity, clock
):
    r = engine.assert_claim(
        entity["id"], "fact", "core truth", confidence=0.6,
        evidence={"kind": "session", "ref": "s1"},
    )
    claim_id = r["claim"]["id"]
    store.add_evidence("claim", claim_id, kind="session", ref="s2")
    for _ in range(3):
        engine.reinforce(claim_id)  # 0.6 → 0.9, count 3
    assert engine.promote_knowledge()["established"] == 1

    # Not old enough for core yet.
    assert engine.promote_knowledge()["core"] == 0
    clock.advance(days=8)
    # Aging over 8 days pulls 0.9 down a bit but stays above 0.85.
    engine.reinforce(claim_id)  # keep it fresh: 1.0, count 4
    assert engine.promote_knowledge()["core"] == 1
    assert store.get_claim(claim_id)["tier"] == "core"


def test_contradicted_claims_never_promote(engine, store, entity):
    engine.assert_claim(
        entity["id"], "employer", "Facility A", exclusive=True, confidence=0.9,
        valid_from="2026-07-02T00:00:00Z",
    )
    engine.assert_claim(
        entity["id"], "employer", "Facility B", exclusive=True, confidence=0.9,
        valid_from="2026-07-01T00:00:00Z",
    )
    result = engine.promote_knowledge()
    assert result["established"] == 0 and result["core"] == 0


def test_sweep_runs_aging_then_promotion(engine, store, entity, clock):
    engine.assert_claim(entity["id"], "fact", "sweep me", confidence=0.8)
    clock.advance(days=90)
    result = engine.sweep()
    assert result["aging"]["decayed"] == 1
    assert "promotion" in result
    assert store.get_meta("last_aging_run") == clock()
