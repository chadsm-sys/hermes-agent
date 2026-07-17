from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

from scripts.morning_brief_v1 import build_report, load_snapshot, render_markdown

FIXTURES = Path(__file__).parent / "fixtures" / "morning_brief"
SCRIPT = Path(__file__).parents[1] / "scripts" / "morning_brief_v1.py"
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


def snapshot(name: str = "healthy_day") -> dict:
    return load_snapshot(FIXTURES / f"{name}.json")


def report(name: str):
    return build_report(snapshot(name))


def run_cli(path: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(SCRIPT), str(path), *args],
        capture_output=True,
        check=False,
        text=True,
    )


@pytest.mark.parametrize("name", CASES)
def test_all_required_synthetic_scenarios_render_deterministically(name):
    first = report(name)
    second = report(name)
    assert first == second
    assert render_markdown(first) == render_markdown(second)
    assert json.dumps(first, sort_keys=True) == json.dumps(second, sort_keys=True)


def test_healthy_day_with_pending_approval_remains_pass():
    healthy = report("healthy_day")
    assert healthy["executive_summary"]["approvals_required"] == 1
    assert healthy["overall_health"] == "PASS"


def test_healthy_day_has_all_ten_decision_sections():
    text = render_markdown(report("healthy_day"))
    for number in range(1, 11):
        assert f"## {number}." in text


def test_overnight_wins_are_newest_first():
    data = snapshot()
    older = dict(data["overnight_wins"][0])
    older.update(title="Older", completion_time="2026-07-11T01:00:00-04:00")
    data["overnight_wins"].append(older)
    titles = [item["title"] for item in build_report(data)["overnight_wins"]]
    assert titles == ["Revenue packet validated", "Older"]


def test_unknown_fleet_is_never_guessed():
    result = report("unknown_state")
    assert all(host["status"] == "UNKNOWN" for host in result["fleet_health"])
    assert "Mission state unavailable" in result["integrity_report"]["unknown_state"]


def test_unexpected_fleet_is_visible_and_downgrades_pass():
    data = snapshot()
    data["fleet_health"].append({
        "name": "Unexpected Host",
        "status": "FAIL",
        "cpu": "91%",
    })
    result = build_report(data)
    assert result["overall_health"] == "WARN"
    assert result["additional_fleet"][0]["name"] == "Unexpected Host"
    assert any(
        "Unexpected Host" in item
        for item in result["integrity_report"]["unknown_state"]
    )
    assert "Unexpected Host" in render_markdown(result)


def test_active_work_uses_explicit_risk_order():
    data = snapshot()
    data["active_work"] = [
        {"title": risk, "risk": risk} for risk in ("LOW", "HIGH", "MEDIUM", "UNKNOWN")
    ]
    assert [item["risk"] for item in build_report(data)["active_work"]] == [
        "HIGH",
        "UNKNOWN",
        "MEDIUM",
        "LOW",
    ]


def test_contradiction_prevents_pass():
    assert report("contradictory_evidence")["overall_health"] == "WARN"


def test_stale_source_is_explicit_and_prevents_pass():
    result = report("stale_evidence")
    assert result["overall_health"] == "WARN"
    assert result["integrity_report"]["stale_reports"]


def test_failure_day_is_fail():
    result = report("failure_day")
    assert result["overall_health"] == "FAIL"
    assert result["executive_summary"]["critical_issues"] == 1


def test_explicit_warn_cannot_mask_derived_fail():
    data = snapshot()
    data["overall_health"] = "WARN"
    data["fleet_health"][0]["status"] = "FAIL"

    assert build_report(data)["overall_health"] == "FAIL"


def test_no_work_overnight_is_explicit():
    assert "No verified overnight completions." in render_markdown(
        report("no_work_overnight")
    )


def test_invalid_snapshot_rejected(tmp_path):
    path = tmp_path / "bad.json"
    path.write_text('{"schema_version": 1}', encoding="utf-8")
    with pytest.raises(ValueError, match="requires as_of"):
        load_snapshot(path)


@pytest.mark.parametrize("field", ["blocked_count", "estimated_review_minutes"])
@pytest.mark.parametrize("value", [True, "1", 1.5])
def test_public_integer_fields_reject_non_integers(field, value):
    data = snapshot()
    data[field] = value
    with pytest.raises(ValueError, match=field):
        build_report(data)


@pytest.mark.parametrize(
    ("mutate", "field"),
    [
        (
            lambda data: data["github"]["open_prs"][0].update(number=True),
            "github.open_prs[0].number",
        ),
        (
            lambda data: data["recommended_actions"][0].update(rank="first"),
            "recommended_actions[0].rank",
        ),
    ],
)
def test_nested_integer_fields_have_field_specific_errors(mutate, field):
    data = snapshot()
    mutate(data)
    with pytest.raises(ValueError, match=field.replace("[", r"\[").replace("]", r"\]")):
        build_report(data)


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("sources", {}),
        ("overnight_wins", {}),
        ("active_work", {}),
        ("needs_chad", {}),
        ("failures", {}),
        ("fleet_health", {}),
        ("recommended_actions", {}),
        ("evidence_references", {}),
        ("github", []),
        ("timeline", []),
        ("integrity", []),
    ],
)
def test_nested_shapes_have_field_specific_errors(field, value):
    data = snapshot()
    data[field] = value
    with pytest.raises(ValueError, match=field):
        build_report(data)


def test_nested_list_rows_must_be_objects():
    data = snapshot()
    data["sources"] = ["bad"]
    with pytest.raises(ValueError, match=r"sources\[0\]"):
        build_report(data)


def test_cli_invalid_input_has_stable_exit_code_without_traceback(tmp_path):
    data = snapshot()
    data["blocked_count"] = True
    path = tmp_path / "invalid.json"
    path.write_text(json.dumps(data), encoding="utf-8")
    result = run_cli(path)
    assert result.returncode == 2
    assert "blocked_count" in result.stderr
    assert "Traceback" not in result.stderr


def test_output_creates_new_file(tmp_path):
    target = tmp_path / "brief.md"
    result = run_cli(FIXTURES / "healthy_day.json", "--output", str(target))
    assert result.returncode == 0
    assert target.read_text(encoding="utf-8").startswith("# Hermes Morning Brief v1")


def test_output_rejects_existing_path_without_changing_it(tmp_path):
    target = tmp_path / "brief.md"
    target.write_text("preserve me", encoding="utf-8")
    result = run_cli(FIXTURES / "healthy_day.json", "--output", str(target))
    assert result.returncode != 0
    assert "already exists" in result.stderr
    assert target.read_text(encoding="utf-8") == "preserve me"


def test_output_rejects_symlink(tmp_path):
    real = tmp_path / "real.md"
    real.write_text("preserve me", encoding="utf-8")
    target = tmp_path / "brief.md"
    target.symlink_to(real)
    result = run_cli(FIXTURES / "healthy_day.json", "--output", str(target))
    assert result.returncode != 0
    assert "symlink" in result.stderr.lower()
    assert real.read_text(encoding="utf-8") == "preserve me"


def test_markdown_table_cells_escape_untrusted_presentation_data():
    data = snapshot()
    payload = r"pipe | slash \\ `code` # heading *em* [link](https://example.invalid)"
    data["fleet_health"][0]["cpu"] = payload
    text = render_markdown(build_report(data))
    fleet_row = next(
        line for line in text.splitlines() if line.startswith("| Mac mini |")
    )
    assert r"pipe \| slash \\\\" in fleet_row
    assert "`code`" in fleet_row
    assert "# heading" in fleet_row
    assert "*em*" in fleet_row
    assert "[link]" in fleet_row
    assert len(fleet_row.split(" | ")) == 11


def test_output_contains_provenance_fields():
    result = report("healthy_day")
    assert result["as_of"] == "2026-07-11T07:00:00-04:00"
    assert result["data_freshness"]
    assert result["source_paths"]
    assert result["evidence_references"]
