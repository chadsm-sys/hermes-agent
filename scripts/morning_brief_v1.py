#!/usr/bin/env python3
"""Deterministic, read-only Hermes Morning Brief v1 renderer.

The renderer consumes a normalized JSON snapshot. It never probes hosts, the
Hermes runtime, GitHub, or the network. Missing, stale, and contradictory data
are surfaced as UNKNOWN/WARN rather than inferred.
"""

from __future__ import annotations

import argparse
import json
from datetime import datetime
from pathlib import Path
from typing import Any

STATUSES = {"PASS", "WARN", "FAIL", "UNKNOWN"}
RISKS = {"LOW", "MEDIUM", "HIGH", "UNKNOWN"}
DECISIONS = {"APPROVE", "WAIT", "REJECT"}
FLEET_ORDER = ("Mac mini", "MacBook Pro", "Spark 1", "Spark 2")
RISK_PRIORITY = {"HIGH": 1, "UNKNOWN": 2, "MEDIUM": 3, "LOW": 4}
INVALID_INPUT_EXIT = 2


def _text(value: Any, default: str = "UNKNOWN") -> str:
    if value is None or value == "":
        return default
    return str(value).replace("\n", " ").strip()


def _status(value: Any) -> str:
    candidate = _text(value).upper()
    return candidate if candidate in STATUSES else "UNKNOWN"


def _risk(value: Any) -> str:
    candidate = _text(value).upper()
    return candidate if candidate in RISKS else "UNKNOWN"


def _time_key(value: Any) -> str:
    text = _text(value, "")
    try:
        return datetime.fromisoformat(text.replace("Z", "+00:00")).isoformat()
    except ValueError:
        return ""


def _object(value: Any, field: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ValueError(f"{field} must be an object")
    return value


def _list(value: Any, field: str) -> list[Any]:
    if not isinstance(value, list):
        raise ValueError(f"{field} must be a list")
    return value


def _objects(value: Any, field: str) -> list[dict[str, Any]]:
    rows = _list(value, field)
    for index, row in enumerate(rows):
        if not isinstance(row, dict):
            raise ValueError(f"{field}[{index}] must be an object")
    return rows


def _integer(value: Any, field: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise ValueError(f"{field} must be an integer")
    return value


def _validate_snapshot(snapshot: dict[str, Any]) -> None:
    for field in (
        "sources",
        "overnight_wins",
        "active_work",
        "needs_chad",
        "failures",
        "fleet_health",
        "recommended_actions",
    ):
        _objects(snapshot.get(field, []), field)
    for field in ("priorities", "evidence_references"):
        _list(snapshot.get(field, []), field)
    for field, default in (("blocked_count", 0), ("estimated_review_minutes", 5)):
        _integer(snapshot.get(field, default), field)
    github = _object(snapshot.get("github", {}), "github")
    for field in (
        "open_prs",
        "ready_to_merge",
        "blocked_prs",
        "failed_ci",
        "repositories_needing_attention",
    ):
        rows = _list(github.get(field, []), f"github.{field}")
        if field == "open_prs":
            for index, row in enumerate(rows):
                _object(row, f"github.open_prs[{index}]")
                _integer(row.get("number", 0), f"github.open_prs[{index}].number")
    timeline = _object(snapshot.get("timeline", {}), "timeline")
    for field in ("yesterday", "today", "upcoming", "completed", "running", "waiting"):
        _objects(timeline.get(field, []), f"timeline.{field}")
    integrity = _object(snapshot.get("integrity", {}), "integrity")
    for field in (
        "missing_evidence",
        "stale_reports",
        "duplicate_jobs",
        "conflicting_state",
        "unknown_state",
    ):
        _list(integrity.get(field, []), f"integrity.{field}")
    for index, row in enumerate(snapshot.get("recommended_actions", [])):
        _integer(row.get("rank", 999), f"recommended_actions[{index}].rank")


def load_snapshot(path: Path) -> dict[str, Any]:
    raw = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        raise ValueError("snapshot root must be an object")
    if raw.get("schema_version") != 1:
        raise ValueError("snapshot schema_version must be 1")
    if not raw.get("as_of"):
        raise ValueError("snapshot requires as_of")
    return raw


def _freshness(snapshot: dict[str, Any]) -> list[dict[str, str]]:
    rows = []
    for source in sorted(
        snapshot.get("sources", []), key=lambda row: _text(row.get("name"))
    ):
        rows.append({
            "name": _text(source.get("name")),
            "path": _text(source.get("path")),
            "observed_at": _text(source.get("observed_at")),
            "freshness": _status(source.get("freshness")),
        })
    return rows


def _integrity(
    snapshot: dict[str, Any], freshness: list[dict[str, str]]
) -> dict[str, list[str]]:
    supplied = snapshot.get("integrity", {})
    result = {
        "missing_evidence": sorted({
            _text(x) for x in supplied.get("missing_evidence", [])
        }),
        "stale_reports": sorted({_text(x) for x in supplied.get("stale_reports", [])}),
        "duplicate_jobs": sorted({
            _text(x) for x in supplied.get("duplicate_jobs", [])
        }),
        "conflicting_state": sorted({
            _text(x) for x in supplied.get("conflicting_state", [])
        }),
        "unknown_state": sorted({_text(x) for x in supplied.get("unknown_state", [])}),
    }
    for source in freshness:
        if source["freshness"] == "UNKNOWN":
            result["unknown_state"].append(
                f"Source freshness UNKNOWN: {source['name']}"
            )
        elif source["freshness"] in {"WARN", "FAIL"}:
            result["stale_reports"].append(
                f"{source['name']} ({source['observed_at']})"
            )
        if source["path"] == "UNKNOWN":
            result["missing_evidence"].append(f"Source path UNKNOWN: {source['name']}")
    return {key: sorted(set(values)) for key, values in result.items()}


def build_report(snapshot: dict[str, Any]) -> dict[str, Any]:
    """Build a report; identical valid snapshots always produce identical output."""
    _validate_snapshot(snapshot)
    freshness = _freshness(snapshot)
    integrity = _integrity(snapshot, freshness)
    wins = sorted(
        snapshot.get("overnight_wins", []),
        key=lambda row: (
            _time_key(row.get("completion_time")),
            _text(row.get("title")),
        ),
        reverse=True,
    )
    active = sorted(
        snapshot.get("active_work", []),
        key=lambda row: (
            RISK_PRIORITY[_risk(row.get("risk"))],
            _text(row.get("title")),
        ),
    )
    approvals = sorted(
        snapshot.get("needs_chad", []),
        key=lambda row: (
            {"HIGH": 3, "MEDIUM": 2, "LOW": 1, "UNKNOWN": 4}[_risk(row.get("risk"))],
            _text(row.get("title")),
        ),
        reverse=True,
    )
    failures = sorted(
        snapshot.get("failures", []),
        key=lambda row: (
            {"HIGH": 3, "MEDIUM": 2, "LOW": 1, "UNKNOWN": 4}[
                _risk(row.get("risk_if_ignored"))
            ],
            _text(row.get("title")),
        ),
        reverse=True,
    )
    actions = sorted(
        snapshot.get("recommended_actions", []),
        key=lambda row: (int(row.get("rank", 999)), _text(row.get("title"))),
    )
    fleet_by_name = {
        _text(row.get("name")): row for row in snapshot.get("fleet_health", [])
    }
    additional_fleet = []
    for name in sorted(set(fleet_by_name) - set(FLEET_ORDER)):
        row = dict(fleet_by_name[name])
        row["name"] = name
        for field in (
            "status",
            "cpu",
            "memory",
            "storage",
            "temperature",
            "ups",
            "network",
            "tailscale",
            "last_heartbeat",
            "certification_status",
        ):
            row[field] = (
                _status(row.get(field)) if field == "status" else _text(row.get(field))
            )
        additional_fleet.append(row)
        integrity["unknown_state"].append(f"Unexpected fleet entry: {name}")
    integrity["unknown_state"] = sorted(set(integrity["unknown_state"]))
    fleet = []
    for name in FLEET_ORDER:
        row = dict(fleet_by_name.get(name, {}))
        row["name"] = name
        for field in (
            "status",
            "cpu",
            "memory",
            "storage",
            "temperature",
            "ups",
            "network",
            "tailscale",
            "last_heartbeat",
            "certification_status",
        ):
            row[field] = (
                _status(row.get(field)) if field == "status" else _text(row.get(field))
            )
        fleet.append(row)
    github = snapshot.get("github", {})
    timeline = snapshot.get("timeline", {})
    priorities = [_text(x) for x in snapshot.get("priorities", [])][:3]
    while len(priorities) < 3:
        priorities.append("UNKNOWN")

    explicit = _status(snapshot.get("overall_health"))
    integrity_count = sum(len(values) for values in integrity.values())
    derived = (
        "FAIL"
        if failures or any(row["status"] == "FAIL" for row in fleet)
        else "WARN"
        if integrity_count or any(row["status"] in {"WARN", "UNKNOWN"} for row in fleet)
        else "PASS"
    )
    overall = explicit
    if explicit == "PASS" and derived != "PASS":
        overall = "WARN" if derived == "WARN" else "FAIL"
    elif explicit == "UNKNOWN":
        overall = derived if derived != "PASS" else "UNKNOWN"

    return {
        "schema_version": 1,
        "as_of": _text(snapshot.get("as_of")),
        "overall_health": overall,
        "executive_summary": {
            "priorities": priorities,
            "approvals_required": len(approvals),
            "critical_issues": len(failures),
            "running_work": len(active),
            "completed_overnight": len(wins),
            "blocked": int(snapshot.get("blocked_count", 0)),
            "estimated_review_minutes": int(
                snapshot.get("estimated_review_minutes", 5)
            ),
        },
        "overnight_wins": wins,
        "active_work": active,
        "needs_chad": approvals,
        "failures": failures,
        "fleet_health": fleet,
        "additional_fleet": additional_fleet,
        "github": {
            "open_prs": sorted(
                github.get("open_prs", []),
                key=lambda row: (
                    _text(row.get("repository")),
                    int(row.get("number", 0)),
                ),
            ),
            "ready_to_merge": sorted(github.get("ready_to_merge", [])),
            "blocked_prs": sorted(github.get("blocked_prs", [])),
            "failed_ci": sorted(github.get("failed_ci", [])),
            "repositories_needing_attention": sorted(
                github.get("repositories_needing_attention", [])
            ),
        },
        "daily_timeline": {
            key: sorted(
                timeline.get(key, []),
                key=lambda row: (_text(row.get("time")), _text(row.get("title"))),
            )
            for key in (
                "yesterday",
                "today",
                "upcoming",
                "completed",
                "running",
                "waiting",
            )
        },
        "recommended_actions": actions,
        "integrity_report": integrity,
        "data_freshness": freshness,
        "source_paths": [row["path"] for row in freshness],
        "evidence_references": sorted({
            _text(path) for path in snapshot.get("evidence_references", [])
        }),
    }


def _items(values: list[Any], empty: str = "None.") -> list[str]:
    return [f"- {_text(value)}" for value in values] or [f"- {empty}"]


def _table_cell(value: Any) -> str:
    """Escape untrusted snapshot text rendered inside a Markdown table."""
    return _text(value).replace("\\", "\\\\").replace("|", "\\|")


def render_markdown(report: dict[str, Any]) -> str:
    s = report["executive_summary"]
    lines = [
        "# Hermes Morning Brief v1",
        f"**As of:** `{report['as_of']}`",
        f"**Overall health:** **{report['overall_health']}**",
        f"**Data freshness:** {len(report['data_freshness'])} declared sources; see Integrity Report.",
        "",
        "## 1. Executive Summary (30 seconds)",
        f"1. **Highest priority:** {s['priorities'][0]}",
        f"2. **Second priority:** {s['priorities'][1]}",
        f"3. **Third priority:** {s['priorities'][2]}",
        "",
        f"- **Approvals required:** {s['approvals_required']}",
        f"- **Critical issues:** {s['critical_issues']}",
        f"- **Running work:** {s['running_work']}",
        f"- **Completed overnight:** {s['completed_overnight']}",
        f"- **Blocked:** {s['blocked']}",
        f"- **Estimated review time:** {s['estimated_review_minutes']} minutes",
        "",
        "## 2. Overnight Wins",
    ]
    for row in report["overnight_wins"]:
        lines.extend([
            f"### {_text(row.get('title'))}",
            f"- **Why it matters:** {_text(row.get('why_it_matters'))}",
            f"- **Evidence:** `{_text(row.get('evidence_path'))}`",
            f"- **Verification:** {_status(row.get('verification_status'))}",
            f"- **Repository:** {_text(row.get('repository'))}",
            f"- **Completed:** {_text(row.get('completion_time'))}",
        ])
    if not report["overnight_wins"]:
        lines.append("No verified overnight completions.")
    lines.extend(["", "## 3. Active Work"])
    for row in report["active_work"]:
        lines.extend([
            f"### {_text(row.get('title'))}",
            f"- Running: {_text(row.get('running_time'))} · heartbeat: {_text(row.get('last_heartbeat'))} · complete: {_text(row.get('percent_complete'))}",
            f"- Stage: {_text(row.get('current_stage'))} · expected finish: {_text(row.get('expected_finish'))}",
            f"- Risk: **{_risk(row.get('risk'))}** · Chad needs to care: {_text(row.get('chad_needs_to_care'))}",
        ])
    if not report["active_work"]:
        lines.append("No active work reported.")
    lines.extend(["", "## 4. Needs Chad"])
    for row in report["needs_chad"]:
        decision = _text(row.get("recommended_button")).upper()
        decision = decision if decision in DECISIONS else "WAIT"
        lines.extend([
            f"### {_text(row.get('title'))}",
            f"- **Why approval is required:** {_text(row.get('reason'))}",
            f"- **Risk:** {_risk(row.get('risk'))}",
            f"- **Recommended:** **{decision}**",
            f"- {_text(row.get('explanation'))}",
        ])
    if not report["needs_chad"]:
        lines.append("No approvals required.")
    lines.extend(["", "## 5. Failures"])
    for row in report["failures"]:
        lines.extend([
            f"### {_text(row.get('title'))}",
            f"- **What happened:** {_text(row.get('what_happened'))}",
            f"- **Likely cause:** {_text(row.get('likely_cause'))}",
            f"- **Evidence:** `{_text(row.get('evidence'))}`",
            f"- **Recommended fix:** {_text(row.get('recommended_fix'))}",
            f"- **Risk if ignored:** {_risk(row.get('risk_if_ignored'))}",
        ])
    if not report["failures"]:
        lines.append("No meaningful failures reported.")
    lines.extend([
        "",
        "## 6. Fleet Health",
        "| Host | Status | CPU | Memory | Storage | Temp | UPS | Network | Tailscale | Last heartbeat | Certification |",
        "|---|---|---|---|---|---|---|---|---|---|---|",
    ])
    for row in report["fleet_health"]:
        lines.append(
            "| "
            + " | ".join(
                _table_cell(row.get(key))
                for key in (
                    "name",
                    "status",
                    "cpu",
                    "memory",
                    "storage",
                    "temperature",
                    "ups",
                    "network",
                    "tailscale",
                    "last_heartbeat",
                    "certification_status",
                )
            )
            + " |"
        )
    if report["additional_fleet"]:
        lines.extend([
            "",
            "### Additional supplied fleet entries (unrecognized)",
            "| Host | Status | CPU | Memory | Storage | Temp | UPS | Network | Tailscale | Last heartbeat | Certification |",
            "|---|---|---|---|---|---|---|---|---|---|---|",
        ])
        for row in report["additional_fleet"]:
            lines.append(
                "| "
                + " | ".join(
                    _table_cell(row.get(key))
                    for key in (
                        "name",
                        "status",
                        "cpu",
                        "memory",
                        "storage",
                        "temperature",
                        "ups",
                        "network",
                        "tailscale",
                        "last_heartbeat",
                        "certification_status",
                    )
                )
                + " |"
            )
    lines.extend([
        "",
        "## 7. GitHub",
        f"- **Open PRs:** {len(report['github']['open_prs'])}",
        "- **Ready to merge:** "
        + (", ".join(report["github"]["ready_to_merge"]) or "None"),
        "- **Blocked PRs:** " + (", ".join(report["github"]["blocked_prs"]) or "None"),
        "- **Failed CI:** " + (", ".join(report["github"]["failed_ci"]) or "None"),
        "- **Repositories needing attention:** "
        + (", ".join(report["github"]["repositories_needing_attention"]) or "None"),
    ])
    for row in report["github"]["open_prs"]:
        lines.append(
            f"  - `{_text(row.get('repository'))}#{_text(row.get('number'))}` {_text(row.get('title'))} — {_status(row.get('status'))}"
        )
    lines.extend(["", "## 8. Daily Timeline"])
    for key, label in (
        ("yesterday", "Yesterday"),
        ("today", "Today"),
        ("upcoming", "Upcoming"),
        ("completed", "Completed"),
        ("running", "Running"),
        ("waiting", "Waiting"),
    ):
        lines.append(f"### {label}")
        rows = report["daily_timeline"][key]
        lines.extend(
            [f"- {_text(row.get('time'))} — {_text(row.get('title'))}" for row in rows]
            or ["- None."]
        )
    lines.extend(["", "## 9. Recommended Actions"])
    for row in report["recommended_actions"]:
        lines.extend([
            f"### {int(row.get('rank', 999))}. {_text(row.get('title'))}",
            f"- Impact: {_text(row.get('impact'))} · Risk: {_risk(row.get('risk'))} · Time: {_text(row.get('time_required'))} · ROI: {_text(row.get('return_on_investment'))}",
            f"- Expected benefit: {_text(row.get('expected_benefit'))}",
            f"- Approval required: {_text(row.get('approval_required'))}",
        ])
    if not report["recommended_actions"]:
        lines.append("No evidence-backed action recommended.")
    lines.extend(["", "## 10. Integrity Report"])
    for key, label in (
        ("missing_evidence", "Missing evidence"),
        ("stale_reports", "Stale reports"),
        ("duplicate_jobs", "Duplicate jobs"),
        ("conflicting_state", "Conflicting state"),
        ("unknown_state", "Unknown state"),
    ):
        lines.append(f"### {label}")
        lines.extend(_items(report["integrity_report"][key]))
    lines.extend(["", "### Sources and freshness"])
    for row in report["data_freshness"]:
        lines.append(
            f"- `{row['name']}` — {row['freshness']} · observed `{row['observed_at']}` · `{row['path']}`"
        )
    lines.extend([
        "",
        "### Evidence references",
        *_items([f"`{path}`" for path in report["evidence_references"]]),
        "",
    ])
    return "\n".join(lines)


def _create_output(path: Path, rendered: str) -> None:
    if path.is_symlink():
        raise ValueError(f"output path is a symlink: {path}")
    try:
        with path.open("x", encoding="utf-8") as handle:
            handle.write(rendered)
    except FileExistsError as error:
        raise ValueError(f"output path already exists: {path}") from error


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "snapshot", type=Path, help="Normalized read-only JSON snapshot"
    )
    parser.add_argument("--format", choices=("markdown", "json"), default="markdown")
    parser.add_argument(
        "--output",
        type=Path,
        help="Write output to a new/local artifact instead of stdout",
    )
    args = parser.parse_args()
    try:
        report = build_report(load_snapshot(args.snapshot))
        rendered = (
            render_markdown(report)
            if args.format == "markdown"
            else json.dumps(report, indent=2, sort_keys=True) + "\n"
        )
        if args.output:
            _create_output(args.output, rendered)
        else:
            print(rendered, end="")
    except (OSError, json.JSONDecodeError, ValueError) as error:
        parser.exit(INVALID_INPUT_EXIT, f"error: {error}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
