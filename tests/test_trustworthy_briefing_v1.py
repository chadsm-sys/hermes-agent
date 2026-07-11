from __future__ import annotations

import copy
from datetime import datetime, timedelta, timezone

import yaml

from scripts.trustworthy_briefing_v1 import load_manifest, render_brief

NOW = datetime(2026, 7, 11, 9, 0, tzinfo=timezone.utc)


def source(name, *, required=True, evidence="RUNTIME_OBSERVED", threshold=3600, authoritative=True):
    return {
        "name": name,
        "purpose": name,
        "owner": "test",
        "location": f"fixture:{name}",
        "retrieval": {"method": "json_file", "path": f"/{name}.json"},
        "required": required,
        "freshness_threshold_seconds": threshold,
        "failure_behavior": "DEGRADE" if required else "SUPPRESS",
        "evidence_class": evidence,
        "fallback_behavior": "fail closed",
        "authoritative": authoritative,
    }


def make_manifest():
    return {
        "schema_version": 1,
        "output": {"max_characters": 6000},
        "sources": [
            source("runtime"),
            source("missions"),
            source("approvals"),
            source("prs", required=False),
            source("health", required=False, evidence="DOCUMENTED", authoritative=False),
            source("money", required=False, evidence="DOCUMENTED", authoritative=False),
        ],
    }


def observation(*items, age_seconds=60, confidence=1.0, claims=None):
    return {
        "collected_at": (NOW - timedelta(seconds=age_seconds)).isoformat(),
        "confidence": confidence,
        "claims": claims or {},
        "items": list(items),
    }


def item(item_id, section, title, **overrides):
    value = {
        "id": item_id,
        "section": section,
        "title": title,
        "detail": "verified detail",
        "operator_relevance": 3,
        "urgency": 2,
        "autonomy": "CONTINUE_WITH_BOUNDS",
        "recommendation": "continue within recorded bounds",
        "consequence": "recorded consequence",
    }
    value.update(overrides)
    return value


def fresh_observations():
    return {
        "runtime": observation(claims={"gateway_running": True}),
        "missions": observation(item("m1", "RUNNING WORK", "Evidence audit", owner="builder", next_checkpoint="10:00")),
        "approvals": observation(),
        "prs": observation(),
        "health": observation(),
        "money": observation(),
    }


def test_manifest_loader_rejects_duplicate_sources(tmp_path):
    path = tmp_path / "manifest.yaml"
    path.write_text(yaml.safe_dump({"schema_version": 1, "sources": [source("x"), source("x")]}))
    try:
        load_manifest(path)
    except ValueError as exc:
        assert "duplicated" in str(exc)
    else:
        raise AssertionError("duplicate manifest source was accepted")


def test_all_required_sources_fresh_can_be_green():
    manifest = make_manifest()
    text, report = render_brief(manifest, fresh_observations(), now=NOW)
    assert report["overall_status"] == "GREEN"
    assert report["trustworthy_recommendation"] is True
    assert "3/3 required fresh" in text


def test_required_source_missing_fails_closed():
    manifest = make_manifest()
    observations = fresh_observations()
    del observations["missions"]
    text, report = render_brief(manifest, observations, now=NOW)
    assert report["overall_status"] == "RED"
    assert "missions=MISSING" in text
    assert "NO TRUSTWORTHY RECOMMENDATION" in text


def test_required_source_stale_fails_closed():
    manifest = make_manifest()
    observations = fresh_observations()
    observations["runtime"] = observation(age_seconds=3601)
    text, report = render_brief(manifest, observations, now=NOW)
    assert report["overall_status"] == "RED"
    assert "runtime=STALE" in text


def test_contradictory_authoritative_claims_are_surfaced():
    manifest = make_manifest()
    observations = fresh_observations()
    observations["runtime"]["claims"] = {"gateway_running": True}
    observations["missions"]["claims"] = {"gateway_running": False}
    text, report = render_brief(manifest, observations, now=NOW)
    assert report["overall_status"] == "RED"
    assert "CONTRADICTORY AUTHORITATIVE SOURCES" in text
    assert report["contradictions"]


def test_artifact_pass_does_not_become_runtime_observed():
    manifest = make_manifest()
    observations = fresh_observations()
    observations["runtime"] = observation(
        item("artifact", "RUNNING WORK", "Artifact verifier", evidence_class="DOCUMENTED"),
        claims={"artifact_status": "PASS", "runtime_status": "UNKNOWN"},
    )
    text, report = render_brief(manifest, observations, now=NOW)
    assert "[DOCUMENTED" in text
    artifact = next(i for i in report["items"] if i["id"] == "artifact")
    assert artifact["evidence_class"] == "DOCUMENTED"


def test_no_approvals_required_says_chad_not_required():
    manifest = make_manifest()
    text, _ = render_brief(manifest, fresh_observations(), now=NOW)
    assert "None — Chad is not required." in text


def test_duplicate_approvals_are_consolidated():
    manifest = make_manifest()
    observations = fresh_observations()
    gate = item("g1", "ACTIVE GATES", "Approve bounded rollout", requires_chad=True, autonomy="NEEDS_CHAD", dedupe_key="rollout", urgency=4)
    duplicate = copy.deepcopy(gate)
    duplicate["id"] = "g2"
    observations["approvals"] = observation(gate, duplicate)
    text, report = render_brief(manifest, observations, now=NOW)
    assert text.count("Approve bounded rollout") == 2  # active gate + best approval, not two gates
    assert len(report["suppressed"]) == 1
    assert "duplicate consolidated" in report["suppressed"][0]["suppression_reason"]


def test_high_value_gate_outranks_low_value_items():
    manifest = make_manifest()
    observations = fresh_observations()
    observations["approvals"] = observation(
        item("low", "ACTIVE GATES", "Low-value curiosity", requires_chad=True, autonomy="NEEDS_CHAD", urgency=1, operator_relevance=1),
        item("high", "ACTIVE GATES", "Restore authorization", requires_chad=True, autonomy="NEEDS_CHAD", urgency=5, operator_relevance=5),
    )
    text, _ = render_brief(manifest, observations, now=NOW)
    best_section = text.split("## TODAY'S BEST APPROVAL", 1)[1].split("##", 1)[0]
    assert "Restore authorization" in best_section
    assert "Low-value curiosity" not in best_section


def test_active_mission_can_continue_autonomously():
    manifest = make_manifest()
    observations = fresh_observations()
    observations["missions"] = observation(item("safe", "RUNNING WORK", "Safe mission", autonomy="CONTINUE_AUTONOMOUSLY"))
    text, _ = render_brief(manifest, observations, now=NOW)
    assert "**CONTINUE_AUTONOMOUSLY**" in text


def test_active_mission_requiring_chad_is_a_gate():
    manifest = make_manifest()
    observations = fresh_observations()
    observations["approvals"] = observation(item("gate", "ACTIVE GATES", "Irreversible send", requires_chad=True, reversible=False, autonomy="NEEDS_CHAD", urgency=5))
    text, _ = render_brief(manifest, observations, now=NOW)
    assert "Irreversible send" in text
    assert "**NEEDS_CHAD**" in text


def test_stale_money_lead_is_suppressed():
    manifest = make_manifest()
    observations = fresh_observations()
    observations["money"] = observation(item("lead", "MONEY", "Old lead"), age_seconds=4000)
    # Optional threshold is 3600 in the fixture manifest.
    text, report = render_brief(manifest, observations, now=NOW)
    assert "Old lead" not in text
    assert "Suppressed — no current, operator-relevant item." in text
    assert next(s for s in report["sources"] if s["name"] == "money")["state"] == "STALE"


def test_incomplete_optional_health_data_is_suppressed_not_green_support():
    manifest = make_manifest()
    observations = fresh_observations()
    observations["health"] = {"collected_at": NOW.isoformat(), "error": "packet incomplete"}
    text, report = render_brief(manifest, observations, now=NOW)
    assert report["overall_status"] == "YELLOW"
    assert "HEALTH / FAMILY\nSuppressed" in text


def test_telegram_rendering_is_plain_markdown_without_tables():
    manifest = make_manifest()
    text, _ = render_brief(manifest, fresh_observations(), now=NOW)
    assert "# OLYMPUS / HERMES STATUS" in text
    assert "|---" not in text
    assert "<script" not in text.lower()


def test_brief_remains_operator_readable_size():
    manifest = make_manifest()
    manifest = copy.deepcopy(manifest)
    manifest["output"]["max_characters"] = 1800
    observations = fresh_observations()
    observations["missions"] = observation(*[item(f"m{i}", "RUNNING WORK", f"Mission {i}", detail="x" * 200) for i in range(30)])
    text, report = render_brief(manifest, observations, now=NOW)
    assert len(text) <= 1800
    assert "TRUNCATED" in text
    assert report["overall_status"] == "YELLOW"


def test_no_false_green_when_required_timestamp_invalid():
    manifest = make_manifest()
    observations = fresh_observations()
    observations["runtime"]["collected_at"] = "not-a-time"
    _, report = render_brief(manifest, observations, now=NOW)
    assert report["overall_status"] == "RED"


def test_no_unsupported_merge_recommendation():
    manifest = make_manifest()
    observations = fresh_observations()
    observations["prs"] = observation(
        item(
            "pr:1",
            "PRS OR CHANGES NEEDING REVIEW",
            "PR #1",
            requires_chad=True,
            autonomy="NEEDS_CHAD",
            recommendation="Merge now",
        )
    )
    text, _ = render_brief(manifest, observations, now=NOW)
    assert "Merge now" not in text
    assert "no merge recommendation supported" in text


def test_pr_adapter_strips_unsupported_merge_advice(tmp_path):
    from scripts.trustworthy_briefing_v1 import _collect_json

    packet = tmp_path / "prs.json"
    packet.write_text('{"prs":[{"number":7,"title":"Risky","requires_operator_review":true,"recommendation":"Merge now","merge_evidence_current":false}]}')
    src = source("prs", required=False)
    src["retrieval"] = {"method": "json_file", "path": str(packet), "adapter": "pr_poll"}
    result = _collect_json(src, NOW)
    assert "no merge recommendation supported" in result["items"][0]["recommendation"].lower()
