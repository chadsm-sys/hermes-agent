#!/usr/bin/env python3
"""Fail-closed, evidence-backed morning briefing renderer.

This script is intentionally standalone so a reviewed copy can replace the
local daily_command_center entry point without adding a Hermes core tool.
It never sends messages or mutates source state; stdout is the delivery body.
"""

from __future__ import annotations

import argparse
import copy
import glob
import json
import os
import re
import shutil
import sqlite3
import tempfile
import urllib.error
import urllib.request
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import yaml

EVIDENCE_CLASSES = {
    "DOCUMENTED",
    "RUNTIME_OBSERVED",
    "TEST_VERIFIED",
    "PHYSICALLY_VERIFIED",
    "INFERRED",
    "UNKNOWN",
}
AUTONOMY_CLASSES = {
    "CONTINUE_AUTONOMOUSLY",
    "CONTINUE_WITH_BOUNDS",
    "WAIT_FOR_EVIDENCE",
    "NEEDS_CHAD",
    "STOP",
}
SECTIONS = (
    "ACTIVE GATES",
    "RUNNING WORK",
    "BLOCKED OR DEGRADED LANES",
    "PRS OR CHANGES NEEDING REVIEW",
    "TODAY'S BEST APPROVAL",
    "ONE RECOMMENDED ACTION",
    "HEALTH / FAMILY",
    "MONEY",
)


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def parse_time(value: str | None) -> datetime | None:
    if not value:
        return None
    text = str(value).strip().replace("Z", "+00:00")
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def compact(text: Any, limit: int = 180) -> str:
    value = re.sub(r"\s+", " ", str(text or "")).strip()
    return value if len(value) <= limit else value[: limit - 1].rstrip() + "…"


@dataclass(frozen=True)
class SourceAssessment:
    name: str
    required: bool
    authoritative: bool
    evidence_class: str
    state: str
    confidence: float
    collected_at: str | None
    location: str
    purpose: str
    reason: str = ""


def load_manifest(path: Path) -> dict[str, Any]:
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict) or data.get("schema_version") != 1:
        raise ValueError("manifest schema_version must be 1")
    sources = data.get("sources")
    if not isinstance(sources, list) or not sources:
        raise ValueError("manifest must define a non-empty sources list")
    seen: set[str] = set()
    for source in sources:
        name = source.get("name")
        if not name or name in seen:
            raise ValueError(f"source name missing or duplicated: {name!r}")
        seen.add(name)
        if source.get("evidence_class") not in EVIDENCE_CLASSES:
            raise ValueError(f"invalid evidence class for {name}")
        if int(source.get("freshness_threshold_seconds", -1)) < 0:
            raise ValueError(f"invalid freshness threshold for {name}")
        if source.get("failure_behavior") not in {"DEGRADE", "SUPPRESS"}:
            raise ValueError(f"invalid failure behavior for {name}")
    return data


def assess_sources(
    manifest: dict[str, Any], observations: dict[str, Any], now: datetime
) -> list[SourceAssessment]:
    results: list[SourceAssessment] = []
    for source in manifest["sources"]:
        name = source["name"]
        observation = observations.get(name)
        required = bool(source.get("required"))
        authoritative = bool(source.get("authoritative"))
        evidence_class = str(source["evidence_class"])
        location = str(source.get("location", name))
        purpose = str(source.get("purpose", ""))
        if not observation:
            results.append(SourceAssessment(name, required, authoritative, evidence_class, "MISSING", 0.0, None, location, purpose, "no observation"))
            continue
        collected = parse_time(observation.get("collected_at"))
        if not collected:
            results.append(SourceAssessment(name, required, authoritative, evidence_class, "UNKNOWN", 0.0, None, location, purpose, "invalid collection timestamp"))
            continue
        age = max(0.0, (now - collected).total_seconds())
        threshold = int(source["freshness_threshold_seconds"])
        state = "FRESH" if age <= threshold else "STALE"
        confidence = float(observation.get("confidence", 1.0 if state == "FRESH" else 0.25))
        if observation.get("error"):
            state, confidence = "UNAVAILABLE", 0.0
        results.append(
            SourceAssessment(
                name=name,
                required=required,
                authoritative=authoritative,
                evidence_class=evidence_class,
                state=state,
                confidence=max(0.0, min(1.0, confidence)),
                collected_at=collected.isoformat(),
                location=location,
                purpose=purpose,
                reason=compact(observation.get("error") or (f"age={int(age)}s threshold={threshold}s")),
            )
        )
    return results


def contradictions(manifest: dict[str, Any], observations: dict[str, Any], now: datetime) -> list[str]:
    authoritative: set[str] = set()
    for source in manifest["sources"]:
        name = source["name"]
        observation = observations.get(name)
        if not source.get("authoritative") or not observation or observation.get("error"):
            continue
        collected = parse_time(observation.get("collected_at"))
        if collected and (now - collected).total_seconds() <= int(source["freshness_threshold_seconds"]):
            authoritative.add(name)
    claims: dict[str, list[tuple[str, Any]]] = {}
    for source_name, observation in observations.items():
        if source_name not in authoritative:
            continue
        for key, value in (observation.get("claims") or {}).items():
            if value is not None:
                claims.setdefault(key, []).append((source_name, value))
    conflicts: list[str] = []
    for key, values in claims.items():
        normalized = {json.dumps(value, sort_keys=True, default=str) for _, value in values}
        if len(normalized) > 1:
            rendered = ", ".join(f"{source}={compact(value, 60)}" for source, value in values)
            conflicts.append(f"{key}: {rendered}")
    return conflicts


def normalize_item(raw: dict[str, Any], source: SourceAssessment) -> dict[str, Any]:
    evidence_class = raw.get("evidence_class", source.evidence_class)
    if evidence_class not in EVIDENCE_CLASSES:
        evidence_class = "UNKNOWN"
    autonomy = raw.get("autonomy", "WAIT_FOR_EVIDENCE")
    if autonomy not in AUTONOMY_CLASSES:
        autonomy = "WAIT_FOR_EVIDENCE"
    recommendation = compact(raw.get("recommendation") or "No recommendation supported")
    if raw.get("section") == "PRS OR CHANGES NEEDING REVIEW" and "merge" in recommendation.lower() and not raw.get("merge_evidence_current", False):
        recommendation = "Review current checks and diff; no merge recommendation supported"
    return {
        "id": str(raw.get("id") or f"{source.name}:{compact(raw.get('title'), 40)}"),
        "section": raw.get("section", "BLOCKED OR DEGRADED LANES"),
        "title": compact(raw.get("title") or "Unknown item", 100),
        "detail": compact(raw.get("detail") or raw.get("status") or "UNKNOWN"),
        "source": source.name,
        "location": compact(raw.get("location") or source.location, 100),
        "collected_at": source.collected_at,
        "freshness": source.state,
        "evidence_class": evidence_class,
        "confidence": max(0.0, min(1.0, float(raw.get("confidence", source.confidence)))),
        "contradiction": bool(raw.get("contradiction")),
        "operator_relevance": int(raw.get("operator_relevance", 0)),
        "urgency": int(raw.get("urgency", 0)),
        "consequence": compact(raw.get("consequence") or "No material consequence stated"),
        "recommendation": recommendation,
        "recommendation_supported": bool(raw.get("recommendation_supported", raw.get("consequence") and raw.get("recommendation"))),
        "reversible": bool(raw.get("reversible", True)),
        "requires_chad": bool(raw.get("requires_chad", autonomy == "NEEDS_CHAD")),
        "autonomy": autonomy,
        "age": compact(raw.get("age") or "unknown"),
        "owner": compact(raw.get("owner") or "Hermes"),
        "next_checkpoint": compact(raw.get("next_checkpoint") or "UNKNOWN"),
        "suppression_reason": compact(raw.get("suppression_reason") or ""),
    }


def consolidate(items: list[dict[str, Any]], section_limits: dict[str, int] | None = None) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    kept: dict[str, dict[str, Any]] = {}
    suppressed: list[dict[str, Any]] = []
    for item in items:
        key = str(item.get("dedupe_key") or item["id"])
        if item.get("suppress") or item["operator_relevance"] <= 0:
            item["suppression_reason"] = item["suppression_reason"] or "not operator relevant"
            suppressed.append(item)
            continue
        if key not in kept:
            kept[key] = item
            continue
        current = kept[key]
        winner = max((current, item), key=lambda x: (x["requires_chad"], x["urgency"], x["operator_relevance"], x["confidence"]))
        loser = item if winner is current else current
        loser["suppression_reason"] = "duplicate consolidated into " + winner["id"]
        suppressed.append(loser)
        kept[key] = winner
    ordered = sorted(kept.values(), key=lambda x: (x["requires_chad"], x["urgency"], x["operator_relevance"]), reverse=True)
    limits = section_limits or {}
    counts: dict[str, int] = {}
    limited: list[dict[str, Any]] = []
    for item in ordered:
        section = item["section"]
        counts[section] = counts.get(section, 0) + 1
        if counts[section] > int(limits.get(section, 5)):
            item["suppression_reason"] = f"section limit exceeded for {section}"
            suppressed.append(item)
        else:
            limited.append(item)
    return limited, suppressed


def evidence_tag(item: dict[str, Any]) -> str:
    conflict = " CONTRADICTED" if item["contradiction"] else ""
    return f"[{item['evidence_class']} {round(item['confidence'] * 100)}% · {item['source']} · {item['freshness']}{conflict}]"


def render_item(item: dict[str, Any]) -> str:
    if item["section"] == "RUNNING WORK":
        return (
            f"- **{item['title']}** — {item['detail']} · owner `{item['owner']}` · next `{item['next_checkpoint']}` "
            f"· **{item['autonomy']}** — {item['recommendation']} {evidence_tag(item)}"
        )
    return (
        f"- **{item['title']}** — {item['detail']} · consequence: {item['consequence']} "
        f"· recommended: {item['recommendation']} · **{item['autonomy']}** {evidence_tag(item)}"
    )


def render_brief(
    manifest: dict[str, Any], observations: dict[str, Any], *, now: datetime | None = None
) -> tuple[str, dict[str, Any]]:
    now = (now or utcnow()).astimezone(timezone.utc)
    assessments = assess_sources(manifest, observations, now)
    by_name = {a.name: a for a in assessments}
    conflicts = contradictions(manifest, observations, now)
    degraded_required = [a for a in assessments if a.required and a.state != "FRESH"]
    all_items: list[dict[str, Any]] = []
    for source_name, observation in observations.items():
        source = by_name.get(source_name)
        if not source or source.state != "FRESH":
            continue
        for raw in observation.get("items") or []:
            item = normalize_item(raw, source)
            item["dedupe_key"] = raw.get("dedupe_key")
            item["suppress"] = bool(raw.get("suppress"))
            all_items.append(item)
    items, suppressed = consolidate(all_items, manifest.get("output", {}).get("section_limits"))
    if conflicts:
        for item in items:
            item["contradiction"] = True

    readiness_claims = [str(o.get("claims", {}).get("operator_readiness", "")).upper() for o in observations.values()]
    explicit_red = any(value in {"RED", "FAIL", "BLOCKED"} for value in readiness_claims)
    gates = [i for i in items if i["requires_chad"] and i["section"] == "ACTIVE GATES" and i["recommendation_supported"]]
    trustworthy_recommendation = not degraded_required and not conflicts and not explicit_red
    overall = "RED" if degraded_required or conflicts or explicit_red else ("YELLOW" if any(a.state != "FRESH" for a in assessments) else "GREEN")
    required = [a for a in assessments if a.required]
    completeness = f"{sum(a.state == 'FRESH' for a in required)}/{len(required)} required fresh"
    confidence = min((a.confidence for a in required), default=0.0)
    last_update = max((parse_time(a.collected_at) for a in required if a.collected_at), default=None)

    lines = [
        "# OLYMPUS / HERMES STATUS",
        f"**{overall}** · last successful update `{last_update.isoformat() if last_update else 'UNKNOWN'}` · input completeness `{completeness}` · confidence `{round(confidence * 100)}%`",
    ]
    if degraded_required:
        lines.append("**INCOMPLETE REQUIRED INPUTS:** " + "; ".join(f"{a.name}={a.state}" for a in degraded_required))
    if conflicts:
        lines.append("**CONTRADICTORY AUTHORITATIVE SOURCES:** " + "; ".join(conflicts))
    lines.append("")

    grouped = {section: [i for i in items if i["section"] == section] for section in SECTIONS}
    for section in SECTIONS:
        lines.append(f"## {section}")
        section_items = grouped[section]
        if section == "TODAY'S BEST APPROVAL":
            if trustworthy_recommendation and gates:
                best = max(gates, key=lambda i: (i["urgency"], i["operator_relevance"], not i["reversible"], i["confidence"]))
                lines.append(render_item(best))
            elif not trustworthy_recommendation:
                lines.append("**NO TRUSTWORTHY RECOMMENDATION**")
            else:
                lines.append("None — Chad is not required.")
        elif section == "ONE RECOMMENDED ACTION":
            candidates = [i for i in items if i["section"] == section]
            if not trustworthy_recommendation:
                lines.append("**NO TRUSTWORTHY RECOMMENDATION**")
            elif candidates:
                lines.append(render_item(candidates[0]))
            else:
                lines.append("Suppressed — no action is necessary.")
        elif section_items:
            lines.extend(render_item(item) for item in section_items)
        elif section in {"HEALTH / FAMILY", "MONEY", "PRS OR CHANGES NEEDING REVIEW"}:
            lines.append("Suppressed — no current, operator-relevant item.")
        else:
            lines.append("None.")
        lines.append("")

    lines.extend(
        [
            "## EVIDENCE COVERAGE",
            *[
                f"- `{a.name}` {a.state} · {a.evidence_class} · {round(a.confidence * 100)}% · `{a.collected_at or 'UNKNOWN'}`"
                for a in assessments
            ],
            f"- Suppressed items: {len(suppressed)} (reasons retained in machine report)",
        ]
    )
    text = "\n".join(lines).strip() + "\n"
    max_chars = int(manifest.get("output", {}).get("max_characters", 6000))
    if len(text) > max_chars:
        text = text[: max_chars - 80].rstrip() + "\n\n**TRUNCATED — machine report retains omitted detail.**\n"
        overall = "YELLOW" if overall == "GREEN" else overall
    report = {
        "schema_version": 1,
        "generated_at": now.isoformat(),
        "overall_status": overall,
        "input_completeness": completeness,
        "confidence": confidence,
        "trustworthy_recommendation": trustworthy_recommendation,
        "sources": [a.__dict__ for a in assessments],
        "contradictions": conflicts,
        "items": items,
        "suppressed": suppressed,
        "character_count": len(text),
    }
    return text, report


def _latest(pattern: str) -> Path | None:
    paths = [Path(p) for p in glob.glob(os.path.expanduser(pattern))]
    return max(paths, key=lambda p: p.stat().st_mtime) if paths else None


def _read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _collect_json(source: dict[str, Any], now: datetime) -> dict[str, Any]:
    retrieval = source["retrieval"]
    path = _latest(retrieval.get("glob", "")) if retrieval.get("glob") else Path(os.path.expanduser(retrieval["path"]))
    if not path or not path.exists():
        return {"collected_at": now.isoformat(), "error": "source file missing"}
    data = _read_json(path)
    file_time = datetime.fromtimestamp(path.stat().st_mtime, timezone.utc).isoformat()
    adapter = retrieval.get("adapter", "generic")
    collected = now.isoformat() if adapter == "action_inbox" else file_time
    if adapter == "gateway_state":
        collected = str(data.get("updated_at") or file_time)
    observation: dict[str, Any] = {"collected_at": collected, "confidence": 1.0, "claims": {}, "items": []}
    if adapter == "operator_readiness":
        status = str(data.get("readiness") or data.get("status") or data.get("overall") or "UNKNOWN").upper()
        observation["claims"]["operator_readiness"] = status
        if status not in {"GREEN", "PASS"}:
            observation["items"].append({"id": "operator-readiness", "section": "BLOCKED OR DEGRADED LANES", "title": "Operator readiness", "detail": status, "autonomy": "WAIT_FOR_EVIDENCE", "operator_relevance": 5, "urgency": 5, "recommendation": "Resolve the recorded readiness blocker before GUI-dependent work", "evidence_class": "TEST_VERIFIED"})
    elif adapter == "gateway_state":
        state = str(data.get("gateway_state") or "UNKNOWN").upper()
        observation["claims"]["gateway_running"] = state == "RUNNING"
        observation["items"].append({"id": "gateway", "section": "RUNNING WORK" if state == "RUNNING" else "BLOCKED OR DEGRADED LANES", "title": "Hermes gateway", "detail": state, "autonomy": "CONTINUE_AUTONOMOUSLY" if state == "RUNNING" else "STOP", "operator_relevance": 4, "urgency": 4, "recommendation": "Continue under launchd supervision" if state == "RUNNING" else "Investigate runtime health"})
    elif adapter == "action_inbox":
        rows = data if isinstance(data, list) else data.get("items", [])
        for row in rows:
            status = str(row.get("status", "")).lower()
            if status not in {"pending", "needs_human", "awaiting_reply"}:
                continue
            title = row.get("title") or row.get("summary") or row.get("action") or "Approval request"
            key = row.get("brief_dedupe_key") or re.sub(r"\W+", "-", str(title).lower()).strip("-")
            requires = status in {"pending", "needs_human"}
            observation["items"].append({"id": str(row.get("id") or key), "dedupe_key": key, "section": "ACTIVE GATES" if requires else "BLOCKED OR DEGRADED LANES", "title": title, "detail": status.upper(), "requires_chad": requires, "autonomy": "NEEDS_CHAD" if requires else "WAIT_FOR_EVIDENCE", "operator_relevance": 4 if requires else 2, "urgency": int(row.get("urgency", 2)), "reversible": bool(row.get("reversible", False)), "consequence": row.get("consequence", "Work remains paused"), "recommendation": row.get("recommendation", "Review evidence; approve only if material"), "recommendation_supported": bool(row.get("consequence") and row.get("recommendation"))})
    elif adapter == "cron_jobs":
        jobs = data.get("jobs", data if isinstance(data, list) else [])
        for job in jobs:
            if not job.get("enabled", True):
                continue
            status = str(job.get("last_status") or job.get("status") or "UNKNOWN").lower()
            observation["items"].append({"id": f"cron:{job.get('id')}", "section": "RUNNING WORK" if status in {"ok", "success"} else "BLOCKED OR DEGRADED LANES", "title": job.get("name", "Scheduled job"), "detail": f"last={status}", "owner": "Hermes cron", "next_checkpoint": job.get("next_run_at") or job.get("next_run") or "next schedule", "autonomy": "CONTINUE_AUTONOMOUSLY" if status in {"ok", "success"} else "WAIT_FOR_EVIDENCE", "operator_relevance": 0 if status in {"ok", "success"} else 4, "urgency": 0 if status in {"ok", "success"} else 4, "recommendation": "Continue on schedule" if status in {"ok", "success"} else "Inspect the recorded job error", "suppression_reason": "routine green scheduled job" if status in {"ok", "success"} else ""})
    elif adapter == "pr_poll":
        prs = data.get("prs", data if isinstance(data, list) else [])
        for pr in prs:
            if not pr.get("requires_operator_review", False):
                continue
            merge_evidence = pr.get("merge_evidence_current", False)
            recommendation = pr.get("recommendation", "Review current checks and diff")
            if "merge" in recommendation.lower() and not merge_evidence:
                recommendation = "Review current checks and diff; no merge recommendation supported"
            observation["items"].append({"id": f"pr:{pr.get('number')}", "section": "PRS OR CHANGES NEEDING REVIEW", "title": f"PR #{pr.get('number')} {pr.get('title', '')}", "detail": pr.get("review_reason", "operator judgment required"), "requires_chad": True, "autonomy": "NEEDS_CHAD", "operator_relevance": 4, "urgency": int(pr.get("urgency", 2)), "recommendation": recommendation, "consequence": pr.get("consequence", "Change remains unmerged")})
    elif adapter in {"health", "money"}:
        rows = data.get("items", []) if isinstance(data, dict) else []
        for row in rows:
            if not row.get("active_today", False):
                continue
            row = dict(row)
            row["section"] = "HEALTH / FAMILY" if adapter == "health" else "MONEY"
            row.setdefault("operator_relevance", 3)
            observation["items"].append(row)
    return observation


def _collect_http_json(source: dict[str, Any], now: datetime) -> dict[str, Any]:
    retrieval = source["retrieval"]
    request = urllib.request.Request(retrieval["url"], headers={"Accept": "application/json"})
    try:
        with urllib.request.urlopen(request, timeout=float(retrieval.get("timeout_seconds", 3))) as response:
            data = json.loads(response.read().decode("utf-8"))
    except (OSError, urllib.error.URLError, json.JSONDecodeError) as exc:
        return {"collected_at": now.isoformat(), "error": f"runtime probe failed: {compact(exc)}"}
    status = str(data.get("status") or "UNKNOWN").upper()
    running = status in {"OK", "GREEN", "PASS", "RUNNING"}
    return {
        "collected_at": now.isoformat(),
        "confidence": 1.0,
        "claims": {"gateway_running": running},
        "items": [
            {
                "id": "gateway-health",
                "section": "RUNNING WORK" if running else "BLOCKED OR DEGRADED LANES",
                "title": "Hermes gateway health",
                "detail": status,
                "owner": "Hermes gateway",
                "next_checkpoint": "next health collection",
                "autonomy": "CONTINUE_AUTONOMOUSLY" if running else "STOP",
                "operator_relevance": 3 if running else 5,
                "urgency": 2 if running else 5,
                "recommendation": "Continue under supervision" if running else "Stop runtime-dependent work and investigate",
            }
        ],
    }


def _collect_kanban(source: dict[str, Any], now: datetime) -> dict[str, Any]:
    pattern = os.path.expanduser(source["retrieval"]["glob"])
    dbs = [Path(p) for p in glob.glob(pattern)]
    if not dbs:
        return {"collected_at": now.isoformat(), "error": "no kanban board databases"}
    items: list[dict[str, Any]] = []
    newest = 0.0
    try:
        for db in dbs:
            newest = max(newest, db.stat().st_mtime)
            with tempfile.TemporaryDirectory(prefix="brief-kanban-") as tmp:
                copied = Path(tmp) / "kanban.db"
                shutil.copy2(db, copied)
                for suffix in ("-wal", "-shm"):
                    sibling = Path(str(db) + suffix)
                    if sibling.exists():
                        shutil.copy2(sibling, Path(str(copied) + suffix))
                conn = sqlite3.connect(f"file:{copied}?mode=ro", uri=True)
                conn.row_factory = sqlite3.Row
                columns = {row[1] for row in conn.execute("PRAGMA table_info(tasks)")}
                wanted = [name for name in ("id", "title", "status", "assignee", "updated_at", "created_at") if name in columns]
                order_column = "updated_at" if "updated_at" in columns else ("created_at" if "created_at" in columns else "rowid")
                rows = conn.execute(f"SELECT {','.join(wanted)} FROM tasks WHERE status IN ('in_progress','running','blocked','review','scheduled') ORDER BY {order_column} DESC LIMIT 20").fetchall()
                conn.close()
                for row in rows:
                    record = dict(row)
                    status = record.get("status", "UNKNOWN")
                    running = status in {"in_progress", "running"}
                    title = record.get("title", "Kanban task")
                    parked = status == "scheduled"
                    explicit_blocker = "blocked" in str(title).lower() or "pending" in str(title).lower()
                    relevance = 4 if explicit_blocker else (0 if parked else 3)
                    items.append({"id": f"kanban:{db.parent.name}:{record.get('id')}", "section": "RUNNING WORK" if running else "BLOCKED OR DEGRADED LANES", "title": title, "detail": f"{db.parent.name}/{status}", "owner": record.get("assignee") or db.parent.name, "age": record.get("updated_at") or "unknown", "next_checkpoint": "next task event", "autonomy": "CONTINUE_WITH_BOUNDS" if running else "WAIT_FOR_EVIDENCE", "operator_relevance": relevance, "urgency": 2 if running else 3, "recommendation": "Continue within task contract" if running else "Resolve blocker or await scheduled condition", "suppression_reason": "parked without a current operator decision" if parked and not explicit_blocker else ""})
    except (OSError, sqlite3.Error) as exc:
        return {"collected_at": now.isoformat(), "error": f"kanban read failed: {compact(exc)}"}
    return {"collected_at": now.isoformat(), "source_data_timestamp": datetime.fromtimestamp(newest, timezone.utc).isoformat(), "confidence": 1.0, "claims": {}, "items": items}


def collect_observations(manifest: dict[str, Any], now: datetime | None = None) -> dict[str, Any]:
    now = now or utcnow()
    observations: dict[str, Any] = {}
    for source in manifest["sources"]:
        method = source["retrieval"]["method"]
        try:
            if method == "json_file":
                observations[source["name"]] = _collect_json(source, now)
            elif method == "http_json":
                observations[source["name"]] = _collect_http_json(source, now)
            elif method == "kanban_sqlite_copy_ro":
                observations[source["name"]] = _collect_kanban(source, now)
            else:
                observations[source["name"]] = {"collected_at": now.isoformat(), "error": f"unsupported retrieval method: {method}"}
        except (OSError, ValueError, json.JSONDecodeError) as exc:
            observations[source["name"]] = {"collected_at": now.isoformat(), "error": compact(exc)}
    return observations


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--observations", type=Path, help="Normalized JSON fixture; omit for read-only live collection")
    parser.add_argument("--report-json", type=Path, help="Optional machine report output")
    args = parser.parse_args()
    manifest = load_manifest(args.manifest)
    observations = _read_json(args.observations) if args.observations else collect_observations(manifest)
    text, report = render_brief(manifest, observations)
    print(text, end="")
    if args.report_json:
        args.report_json.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
