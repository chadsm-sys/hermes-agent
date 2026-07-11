from __future__ import annotations

import json
from pathlib import Path

import pytest

from scripts.morning_brief_v1 import build_report, load_snapshot, render_markdown

FIXTURES = Path(__file__).parent / "fixtures" / "morning_brief"
CASES = (
    "healthy_day",
    "busy_day",
    "failure_day",
    "everything_blocked",
    "no_work_overnight",
    "contradictory_evidence",
    "stale_evidence",
    "unknown_state",
)


def report(name: str):
    return build_report(load_snapshot(FIXTURES / f"{name}.json"))


@pytest.mark.parametrize("name", CASES)
def test_all_required_synthetic_scenarios_render_deterministically(name):
    first = report(name)
    second = report(name)
    assert first == second
    assert render_markdown(first) == render_markdown(second)
    assert json.dumps(first, sort_keys=True) == json.dumps(second, sort_keys=True)


def test_healthy_day_is_pass_and_has_all_ten_decision_sections():
    healthy = report("healthy_day")
    assert healthy["overall_health"] == "PASS"
    text = render_markdown(healthy)
    for number in range(1, 11):
        assert f"## {number}." in text


def test_overnight_wins_are_newest_first():
    snapshot = load_snapshot(FIXTURES / "healthy_day.json")
    older = dict(snapshot["overnight_wins"][0])
    older.update(title="Older", completion_time="2026-07-11T01:00:00-04:00")
    snapshot["overnight_wins"].append(older)
    titles = [item["title"] for item in build_report(snapshot)["overnight_wins"]]
    assert titles == ["Revenue packet validated", "Older"]


def test_unknown_fleet_is_never_guessed():
    result = report("unknown_state")
    assert all(host["status"] == "UNKNOWN" for host in result["fleet_health"])
    assert "Mission state unavailable" in result["integrity_report"]["unknown_state"]


def test_contradiction_prevents_pass():
    result = report("contradictory_evidence")
    assert result["overall_health"] == "WARN"
    assert result["integrity_report"]["conflicting_state"]


def test_stale_source_is_explicit_and_prevents_pass():
    result = report("stale_evidence")
    assert result["overall_health"] == "WARN"
    assert result["integrity_report"]["stale_reports"]


def test_failure_day_is_fail():
    result = report("failure_day")
    assert result["overall_health"] == "FAIL"
    assert result["executive_summary"]["critical_issues"] == 1


def test_no_work_overnight_is_explicit():
    text = render_markdown(report("no_work_overnight"))
    assert "No verified overnight completions." in text


def test_invalid_snapshot_rejected(tmp_path):
    path = tmp_path / "bad.json"
    path.write_text('{"schema_version": 1}', encoding="utf-8")
    with pytest.raises(ValueError, match="requires as_of"):
        load_snapshot(path)


def test_output_contains_provenance_fields():
    result = report("healthy_day")
    assert result["as_of"] == "2026-07-11T07:00:00-04:00"
    assert result["data_freshness"]
    assert result["source_paths"]
    assert result["evidence_references"]
