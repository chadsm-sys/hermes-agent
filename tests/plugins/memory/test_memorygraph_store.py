"""Tests for the memorygraph GraphStore (entities, relationships, claims,
evidence, time-aware windows, search, audit log)."""

from datetime import datetime, timedelta, timezone

import pytest

from plugins.memory.memorygraph.store import (
    ENTITY_TYPES,
    GraphStore,
    normalize_key,
    parse_ts,
)


class FakeClock:
    """Deterministic UTC clock the store accepts as its ``now`` callable."""

    def __init__(self, start="2026-07-01T00:00:00Z"):
        self.current = datetime.strptime(start, "%Y-%m-%dT%H:%M:%SZ").replace(
            tzinfo=timezone.utc
        )

    def __call__(self):
        return self.current.strftime("%Y-%m-%dT%H:%M:%SZ")

    def advance(self, days=0, hours=0, seconds=0):
        self.current += timedelta(days=days, hours=hours, seconds=seconds)


@pytest.fixture
def clock():
    return FakeClock()


@pytest.fixture
def store(tmp_path, clock):
    s = GraphStore(str(tmp_path / "graph.db"), now=clock)
    yield s
    s.close()


def test_normalize_key():
    assert normalize_key("  C Smith Anesthesia, LLC! ") == "c smith anesthesia llc"
    assert normalize_key("") == ""
    assert normalize_key("ABC-123") == "abc 123"


def test_parse_ts_roundtrip(clock):
    ts = clock()
    assert parse_ts(ts).strftime("%Y-%m-%dT%H:%M:%SZ") == ts


# -- entities ---------------------------------------------------------------


def test_entity_types_cover_required_domains():
    for required in ("person", "project", "goal", "skill", "business"):
        assert required in ENTITY_TYPES


def test_upsert_entity_creates_and_resolves(store):
    e = store.upsert_entity("Jamie Smith", "person", summary="spouse")
    assert e["id"] > 0
    assert e["type"] == "person"
    resolved = store.resolve_entity("jamie   smith")
    assert resolved is not None and resolved["id"] == e["id"]


def test_upsert_entity_is_idempotent_and_merges(store):
    a = store.upsert_entity("Hermes", "project", summary="gateway")
    b = store.upsert_entity("Hermes", "project", attrs={"priority": "P1"})
    assert a["id"] == b["id"]
    assert b["summary"] == "gateway"  # preserved
    assert '"priority"' in b["attrs"]


def test_upsert_entity_rejects_empty_name(store):
    with pytest.raises(ValueError):
        store.upsert_entity("   ")


def test_unknown_entity_type_falls_back_to_concept(store):
    e = store.upsert_entity("Thing", "starship")
    assert e["type"] == "concept"


def test_alias_resolution(store):
    e = store.upsert_entity("C Smith Anesthesia Staffing LLC", "business")
    assert store.add_alias(e["id"], "CSA") is True
    assert store.add_alias(e["id"], "CSA") is False  # duplicate alias
    resolved = store.resolve_entity("csa")
    assert resolved is not None and resolved["id"] == e["id"]


def test_list_entities_filters_by_type(store):
    store.upsert_entity("Colin", "person")
    store.upsert_entity("Bench 200", "goal")
    people = store.list_entities("person")
    assert [e["name"] for e in people] == ["Colin"]


# -- relationships ------------------------------------------------------------


def test_relationship_lifecycle_time_aware(store, clock):
    a = store.upsert_entity("Chad", "person")
    b = store.upsert_entity("Facility A", "business")
    rel = store.add_relationship(a["id"], b["id"], "works_at", confidence=0.7)
    assert rel["valid_to"] is None
    assert rel["valid_from"] == clock()

    # Re-adding the same open edge reinforces, not duplicates
    again = store.add_relationship(a["id"], b["id"], "works_at")
    assert again["id"] == rel["id"]
    assert again["confidence"] > rel["confidence"]

    clock.advance(days=30)
    assert store.end_relationship(rel["id"]) is True
    assert store.end_relationship(rel["id"]) is False  # already ended
    ended = store.relationships_for(a["id"], include_ended=True)[0]
    assert ended["valid_to"] == clock()
    assert store.relationships_for(a["id"]) == []  # open-only view


def test_neighbors(store):
    a = store.upsert_entity("Chad", "person")
    b = store.upsert_entity("Hermes", "project")
    c = store.upsert_entity("Emma", "person")
    store.add_relationship(a["id"], b["id"], "owns")
    store.add_relationship(c["id"], a["id"], "child_of")
    names = {e["name"] for e in store.neighbors(a["id"])}
    assert names == {"Hermes", "Emma"}


# -- claims + evidence -----------------------------------------------------------


def test_claim_insert_defaults(store, clock):
    e = store.upsert_entity("Hermes", "project")
    c = store.insert_claim(e["id"], "Status", "P1 active", confidence=0.9)
    assert c["attribute"] == "status"  # normalized
    assert c["tier"] == "candidate"
    assert c["status"] == "active"
    assert c["valid_from"] == clock()
    assert c["confidence"] == 0.9


def test_claim_confidence_clamped(store):
    e = store.upsert_entity("X")
    c = store.insert_claim(e["id"], "a", "v", confidence=7.5)
    assert c["confidence"] == 1.0


def test_claims_for_history_and_status_filters(store):
    e = store.upsert_entity("X")
    c1 = store.insert_claim(e["id"], "a", "old")
    store.insert_claim(e["id"], "a", "new")
    store.update_claim(c1["id"], status="superseded")
    active = store.claims_for(e["id"], "a")
    assert [c["value"] for c in active] == ["new"]
    history = store.claims_for(e["id"], "a", include_history=True)
    assert len(history) == 2


def test_update_claim_ignores_unknown_fields(store):
    e = store.upsert_entity("X")
    c = store.insert_claim(e["id"], "a", "v")
    store.update_claim(c["id"], entity_id=999, bogus="nope", confidence=0.25)
    updated = store.get_claim(c["id"])
    assert updated["entity_id"] == e["id"]
    assert updated["confidence"] == 0.25


def test_evidence_links(store):
    e = store.upsert_entity("Hermes", "project")
    c = store.insert_claim(e["id"], "status", "P1")
    store.add_evidence("claim", c["id"], kind="session", ref="s-1", quote="it is P1")
    store.add_evidence("claim", c["id"], kind="url", ref="https://example.com")
    assert store.evidence_count("claim", c["id"]) == 2
    kinds = [ev["kind"] for ev in store.evidence_for("claim", c["id"])]
    assert kinds == ["session", "url"]


# -- search / stats / audit -------------------------------------------------------


def test_search_matches_entities_and_claims(store):
    e = store.upsert_entity("Gusto Payroll", "tool", summary="W-2 payroll")
    store.insert_claim(e["id"], "saves", "57K per year via S-Corp", confidence=0.8)
    hits = store.search("gusto payroll")
    assert hits and hits[0]["_kind"] == "entity"
    hits = store.search("s corp 57k")
    assert hits and hits[0]["_kind"] == "claim"
    assert store.search("") == []
    assert store.search("nonexistent zebra") == []


def test_search_excludes_retracted_claims(store):
    e = store.upsert_entity("X")
    c = store.insert_claim(e["id"], "a", "unique zebra fact")
    store.update_claim(c["id"], status="retracted")
    assert store.search("zebra") == []


def test_stats_and_governance_log(store):
    e = store.upsert_entity("Hermes", "project")
    store.insert_claim(e["id"], "status", "P1")
    stats = store.stats()
    assert stats["entities"] == 1
    assert stats["claims_by_status"]["active"] == 1
    assert stats["active_claims_by_tier"]["candidate"] == 1
    assert stats["schema_version"] == 1
    events = [ev["event"] for ev in store.recent_events()]
    assert "entity_created" in events
    assert "claim_created" in events


def test_meta_roundtrip(store):
    store.set_meta("k", "v1")
    store.set_meta("k", "v2")
    assert store.get_meta("k") == "v2"
    assert store.get_meta("missing", "default") == "default"


def test_persistence_across_reopen(tmp_path, clock):
    path = str(tmp_path / "graph.db")
    s1 = GraphStore(path, now=clock)
    s1.upsert_entity("Persist Me", "concept")
    s1.close()
    s2 = GraphStore(path, now=clock)
    assert s2.resolve_entity("persist me") is not None
    s2.close()


def test_normalize_ts_validates_format(store, clock):
    from plugins.memory.memorygraph.store import normalize_ts

    assert normalize_ts("2026-07-01T00:00:00Z", "FB") == "2026-07-01T00:00:00Z"
    assert normalize_ts("", "FB") == "FB"
    assert normalize_ts("2026-07-01 00:00:00", "FB") == "FB"
    assert normalize_ts("2026-07-01T00:00:00.123Z", "FB") == "FB"
    # Write-boundary enforcement: bad valid_from falls back to now()
    e = store.upsert_entity("X")
    c = store.insert_claim(e["id"], "a", "v", valid_from="not-a-timestamp")
    assert c["valid_from"] == clock()
