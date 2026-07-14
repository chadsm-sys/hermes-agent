"""Tests for the MemoryGraphProvider: lifecycle, tool surface, built-in
memory mirroring, prefetch, config, and loader discovery."""

import json
import os

import pytest

from plugins.memory.memorygraph import (
    GRAPH_MEMORY_SCHEMA,
    MemoryGraphProvider,
    register,
)


@pytest.fixture
def provider(tmp_path):
    p = MemoryGraphProvider()
    p.initialize("session-1", hermes_home=str(tmp_path), platform="cli",
                 agent_context="primary")
    yield p
    p.shutdown()


def call(provider, **args):
    return json.loads(provider.handle_tool_call("graph_memory", args))


# -- lifecycle -----------------------------------------------------------------


def test_availability_without_initialize():
    p = MemoryGraphProvider()
    assert p.name == "memorygraph"
    assert p.is_available() is True  # local-only: no creds needed


def test_constructor_has_no_side_effects(tmp_path):
    # discover_memory_providers() instantiates providers just to list them —
    # the constructor must not create the database or config files.
    MemoryGraphProvider()
    assert list(tmp_path.rglob("memory_graph.db")) == []
    assert list(tmp_path.rglob("memorygraph.json")) == []


def test_initialize_creates_profile_scoped_db(provider, tmp_path):
    assert os.path.exists(tmp_path / "memory_graph.db")


def test_tool_call_before_initialize_is_safe():
    p = MemoryGraphProvider()
    result = json.loads(p.handle_tool_call("graph_memory", {"action": "stats"}))
    assert "error" in result


def test_shutdown_then_tool_call_is_safe(tmp_path):
    p = MemoryGraphProvider()
    p.initialize("s", hermes_home=str(tmp_path))
    p.shutdown()
    assert "error" in json.loads(p.handle_tool_call("graph_memory", {"action": "stats"}))


def test_session_switch_clears_prefetch_cache(provider):
    provider._prefetch_cache["q"] = "stale"
    provider.on_session_switch("session-2", reset=True)
    assert provider._prefetch_cache == {}
    assert provider._session_id == "session-2"


# -- tool schema ------------------------------------------------------------------


def test_tool_schema_shape(provider):
    schemas = provider.get_tool_schemas()
    assert len(schemas) == 1
    schema = schemas[0]
    assert schema["name"] == "graph_memory"
    assert schema is GRAPH_MEMORY_SCHEMA
    actions = schema["parameters"]["properties"]["action"]["enum"]
    for action in ("remember", "link", "about", "query", "timeline",
                   "contradictions", "resolve", "duplicates", "feedback",
                   "forget", "sweep", "stats"):
        assert action in actions
    assert schema["parameters"]["required"] == ["action"]


def test_unknown_tool_and_action(provider):
    assert "error" in json.loads(provider.handle_tool_call("nope", {}))
    assert "error" in call(provider, action="explode")
    assert "error" in call(provider)  # missing action


def test_missing_required_args_reported(provider):
    result = call(provider, action="remember", entity="Chad")
    assert "required" in result["error"]


# -- core actions round trip ---------------------------------------------------------


def test_remember_and_about(provider):
    result = call(
        provider, action="remember", entity="Hermes", entity_type="project",
        attribute="status", value="P1 reliability push", confidence=0.8,
        source="backlog.md", quote="P1 Hermes reliability",
    )
    assert result["outcome"] == "created"
    assert result["entity"]["type"] == "project"

    about = call(provider, action="about", entity="hermes")
    assert about["found"] is True
    assert about["claims"][0]["value"] == "P1 reliability push"
    assert about["claims"][0]["evidence_count"] == 1

    missing = call(provider, action="about", entity="Unknown Entity")
    assert missing["found"] is False


def test_remember_duplicate_reinforces(provider):
    call(provider, action="remember", entity="Jamie", entity_type="person",
         attribute="birthday", value="March 30")
    result = call(provider, action="remember", entity="Jamie",
                  entity_type="person", attribute="birthday", value="march 30")
    assert result["outcome"] == "reinforced"


def test_remember_exclusive_supersedes_and_timeline(provider):
    call(provider, action="remember", entity="Chad", entity_type="person",
         attribute="employer", value="Facility A", exclusive=True)
    result = call(provider, action="remember", entity="Chad",
                  entity_type="person", attribute="employer",
                  value="Facility B", exclusive=True)
    assert result["outcome"] == "superseded"

    timeline = call(provider, action="timeline", entity="Chad",
                    attribute="employer")
    assert timeline["found"] is True
    statuses = [c["status"] for c in timeline["timeline"]]
    assert statuses == ["superseded", "active"]


def test_link_unlink_and_relationships_in_about(provider):
    result = call(provider, action="link", src="Chad", dst="C Smith Anesthesia",
                  rel_type="owns", entity_type="person")
    rel_id = result["relationship"]["id"]
    about = call(provider, action="about", entity="Chad")
    assert len(about["relationships"]) == 1
    assert about["relationships"][0]["rel_type"] == "owns"

    ended = call(provider, action="unlink", relationship_id=rel_id)
    assert ended["ended"] is True
    about = call(provider, action="about", entity="Chad")
    assert about["relationships"] == []


def test_query(provider):
    call(provider, action="remember", entity="Gusto", entity_type="tool",
         attribute="purpose", value="S-Corp W-2 payroll")
    result = call(provider, action="query", query="payroll")
    assert result["results"]
    assert result["results"][0]["_kind"] == "claim"


def test_contradiction_flow(provider):
    call(provider, action="remember", entity="Chad", entity_type="person",
         attribute="employer", value="Facility A", exclusive=True)
    # handle_tool_call has no valid_from arg → backdating happens via the
    # engine; simulate ambiguity by writing directly through the engine.
    entity = provider._store.resolve_entity("Chad")
    provider._engine.assert_claim(
        entity["id"], "employer", "Facility B", exclusive=True,
        valid_from="2020-01-01T00:00:00Z",
    )
    groups = call(provider, action="contradictions")["groups"]
    assert len(groups) == 1
    winner_id = groups[0][0]["id"]
    resolved = call(provider, action="resolve", claim_id=winner_id)
    assert resolved["winner"]["status"] == "active"
    assert call(provider, action="contradictions")["groups"] == []


def test_feedback_and_forget(provider):
    result = call(provider, action="remember", entity="X", attribute="fact",
                  value="something", confidence=0.5)
    claim_id = result["claim"]["id"]
    fb = call(provider, action="feedback", claim_id=claim_id, helpful=True)
    assert fb["claim"]["confidence"] == pytest.approx(0.65)
    assert "error" in call(provider, action="feedback", claim_id=claim_id)

    gone = call(provider, action="forget", claim_id=claim_id)
    assert gone["retracted"] is True
    about = call(provider, action="about", entity="X")
    assert about["claims"] == []


def test_duplicates_audit_action(provider):
    entity = provider._store.upsert_entity("X")
    provider._store.insert_claim(entity["id"], "note", "same fact here")
    provider._store.insert_claim(entity["id"], "note", "same fact here!")
    assert len(call(provider, action="duplicates")["groups"]) == 1


def test_sweep_and_stats(provider):
    call(provider, action="remember", entity="Hermes", entity_type="project",
         attribute="status", value="P1")
    result = call(provider, action="sweep")
    assert "aging" in result and "promotion" in result

    stats = call(provider, action="stats")
    assert stats["entities"] == 1
    assert stats["claims_by_status"]["active"] == 1
    assert any(e["event"] == "claim_created"
               for e in stats["recent_governance_events"])


# -- prompt / prefetch ---------------------------------------------------------------


def test_system_prompt_block(provider):
    assert provider.system_prompt_block().startswith("## Knowledge Graph Memory")
    call(provider, action="remember", entity="Hermes", entity_type="project",
         attribute="status", value="P1")
    block = provider.system_prompt_block()
    assert "1 entities" in block
    assert "graph_memory" in block


def test_system_prompt_block_uninitialized():
    assert MemoryGraphProvider().system_prompt_block() == ""


def test_prefetch_returns_recall(provider):
    call(provider, action="remember", entity="Gusto", entity_type="tool",
         attribute="purpose", value="payroll for the S-Corp")
    text = provider.prefetch("how do I run payroll?")
    assert "[memorygraph recall]" in text
    assert "payroll" in text
    assert provider.prefetch("completely unrelated zebra") == ""
    assert provider.prefetch("") == ""


def test_prefetch_disabled_by_config(tmp_path):
    with open(tmp_path / "memorygraph.json", "w", encoding="utf-8") as f:
        json.dump({"prefetch_enabled": False}, f)
    p = MemoryGraphProvider()
    p.initialize("s", hermes_home=str(tmp_path))
    try:
        p.handle_tool_call("graph_memory", {
            "action": "remember", "entity": "Gusto", "attribute": "purpose",
            "value": "payroll",
        })
        assert p.prefetch("payroll") == ""
    finally:
        p.shutdown()


# -- built-in memory mirroring ----------------------------------------------------------


def test_on_memory_write_mirrors_to_graph(provider):
    provider.on_memory_write("add", "memory", "Chad prefers 4:30 AM training",
                             metadata={"session_id": "s-77"})
    about = call(provider, action="about", entity="Hermes Notes")
    assert about["found"] is True
    assert about["claims"][0]["value"] == "Chad prefers 4:30 AM training"
    evidence = provider._store.evidence_for("claim", about["claims"][0]["id"])
    assert evidence[0]["kind"] == "builtin_memory"
    assert evidence[0]["session_id"] == "s-77"


def test_on_memory_write_user_target(provider):
    provider.on_memory_write("add", "user", "Married to Jamie")
    about = call(provider, action="about", entity="User")
    assert about["found"] is True
    assert about["entity"]["type"] == "person"


def test_on_memory_write_ignores_removes_and_blanks(provider):
    provider.on_memory_write("remove", "memory", "whatever")
    provider.on_memory_write("add", "memory", "   ")
    assert call(provider, action="stats")["entities"] == 0


def test_on_memory_write_before_initialize_is_safe():
    MemoryGraphProvider().on_memory_write("add", "memory", "content")  # no raise


def test_on_session_end_runs_sweep(provider):
    call(provider, action="remember", entity="X", attribute="fact", value="v")
    provider.on_session_end([])  # must not raise
    events = [e["event"] for e in provider._store.recent_events(50)]
    assert "claim_created" in events


def test_on_session_end_skipped_for_non_primary(tmp_path):
    p = MemoryGraphProvider()
    p.initialize("s", hermes_home=str(tmp_path), agent_context="cron")
    try:
        p._store.set_meta("last_aging_run", "sentinel")
        p.on_session_end([])
        assert p._store.get_meta("last_aging_run") == "sentinel"
    finally:
        p.shutdown()


# -- config ------------------------------------------------------------------------------


def test_config_schema_and_save(tmp_path):
    p = MemoryGraphProvider()
    keys = [f["key"] for f in p.get_config_schema()]
    assert "half_life_days" in keys
    p.save_config({"half_life_days": "30", "duplicate_similarity": "bad"},
                  str(tmp_path))
    with open(tmp_path / "memorygraph.json", encoding="utf-8") as f:
        saved = json.load(f)
    assert saved == {"half_life_days": 30.0}

    p.initialize("s", hermes_home=str(tmp_path))
    try:
        assert p._engine.policy.half_life_days == 30.0
    finally:
        p.shutdown()


def test_custom_db_path(tmp_path):
    custom = tmp_path / "custom" / "kg.db"
    with open(tmp_path / "memorygraph.json", "w", encoding="utf-8") as f:
        json.dump({"db_path": str(custom)}, f)
    p = MemoryGraphProvider()
    p.initialize("s", hermes_home=str(tmp_path))
    try:
        assert custom.exists()
    finally:
        p.shutdown()


def test_corrupt_config_falls_back_to_defaults(tmp_path):
    with open(tmp_path / "memorygraph.json", "w", encoding="utf-8") as f:
        f.write("{not json")
    p = MemoryGraphProvider()
    p.initialize("s", hermes_home=str(tmp_path))
    try:
        assert p._engine.policy.half_life_days == 90.0
    finally:
        p.shutdown()


# -- registration / discovery ----------------------------------------------------------


def test_register_entry_point():
    class Ctx:
        provider = None

        def register_memory_provider(self, p):
            self.provider = p

    ctx = Ctx()
    register(ctx)
    assert isinstance(ctx.provider, MemoryGraphProvider)


def test_loader_discovers_memorygraph():
    from plugins.memory import find_provider_dir, load_memory_provider

    assert find_provider_dir("memorygraph") is not None
    provider = load_memory_provider("memorygraph")
    assert provider is not None
    assert provider.name == "memorygraph"


def test_bool_args_coerce_string_forms(provider):
    # bool("false") is True — tool args may arrive as strings.
    result = call(provider, action="remember", entity="Chad",
                  entity_type="person", attribute="employer",
                  value="Facility A", exclusive="false")
    assert result["claim"]["exclusive"] == 0

    result = call(provider, action="remember", entity="Chad",
                  entity_type="person", attribute="status",
                  value="active CRNA", exclusive="true")
    assert result["claim"]["exclusive"] == 1

    r = call(provider, action="remember", entity="X", attribute="fact",
             value="v", confidence=0.5)
    fb = call(provider, action="feedback", claim_id=r["claim"]["id"],
              helpful="false")  # string "false" must mean unhelpful
    assert fb["claim"]["confidence"] == pytest.approx(0.35)


def test_config_clamps_invalid_ranges(tmp_path):
    with open(tmp_path / "memorygraph.json", "w", encoding="utf-8") as f:
        json.dump({"half_life_days": -5, "duplicate_similarity": 3.0}, f)
    p = MemoryGraphProvider()
    p.initialize("s", hermes_home=str(tmp_path))
    try:
        assert p._engine.policy.half_life_days == 0.1
        assert p._engine.policy.duplicate_similarity == 1.0
    finally:
        p.shutdown()
