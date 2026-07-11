"""Generate deterministic Morning Brief v1 synthetic fixtures."""

import copy
import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).parent
BASE: dict[str, Any] = {
    "schema_version": 1,
    "as_of": "2026-07-11T07:00:00-04:00",
    "overall_health": "PASS",
    "priorities": [
        "Approve revenue validation packet",
        "Review reliability PR",
        "Protect family schedule",
    ],
    "blocked_count": 0,
    "estimated_review_minutes": 4,
    "sources": [
        {
            "name": "mission_snapshot",
            "path": "fixtures/morning_brief/healthy_day.json",
            "observed_at": "2026-07-11T06:58:00-04:00",
            "freshness": "PASS",
        },
        {
            "name": "github_snapshot",
            "path": "fixtures/github/2026-07-11.json",
            "observed_at": "2026-07-11T06:55:00-04:00",
            "freshness": "PASS",
        },
    ],
    "evidence_references": ["evidence/revenue-packet.md", "evidence/tests.txt"],
    "overnight_wins": [
        {
            "title": "Revenue packet validated",
            "why_it_matters": "Creates a buyer-proof cash action",
            "evidence_path": "evidence/revenue-packet.md",
            "verification_status": "PASS",
            "repository": "smith-ai-systems",
            "completion_time": "2026-07-11T05:42:00-04:00",
        }
    ],
    "active_work": [
        {
            "title": "Read-only report QA",
            "running_time": "18m",
            "last_heartbeat": "2026-07-11T06:57:00-04:00",
            "percent_complete": "70%",
            "current_stage": "fixture validation",
            "expected_finish": "07:15 EDT",
            "risk": "LOW",
            "chad_needs_to_care": "No",
        }
    ],
    "needs_chad": [
        {
            "title": "Approve manual buyer outreach packet",
            "reason": "Outbound contact requires owner approval",
            "risk": "LOW",
            "recommended_button": "APPROVE",
            "explanation": "The packet is draft-only and evidence-backed. Approval permits manual review and sending; Hermes will not send it automatically.",
        }
    ],
    "failures": [],
    "fleet_health": [
        {
            "name": "Mac mini",
            "status": "PASS",
            "cpu": "18%",
            "memory": "42%",
            "storage": "31%",
            "temperature": "UNKNOWN",
            "ups": "CONNECTED",
            "network": "PASS",
            "tailscale": "PASS",
            "last_heartbeat": "2026-07-11T06:59:00-04:00",
            "certification_status": "N/A",
        },
        {
            "name": "MacBook Pro",
            "status": "PASS",
            "cpu": "UNKNOWN",
            "memory": "UNKNOWN",
            "storage": "UNKNOWN",
            "temperature": "UNKNOWN",
            "ups": "N/A",
            "network": "PASS",
            "tailscale": "PASS",
            "last_heartbeat": "2026-07-11T06:51:00-04:00",
            "certification_status": "N/A",
        },
        {
            "name": "Spark 1",
            "status": "PASS",
            "cpu": "12%",
            "memory": "24%",
            "storage": "8%",
            "temperature": "41 C",
            "ups": "CONNECTED",
            "network": "PASS",
            "tailscale": "PASS",
            "last_heartbeat": "2026-07-11T06:56:00-04:00",
            "certification_status": "PASS",
        },
        {
            "name": "Spark 2",
            "status": "PASS",
            "cpu": "9%",
            "memory": "20%",
            "storage": "7%",
            "temperature": "39 C",
            "ups": "CONNECTED",
            "network": "PASS",
            "tailscale": "PASS",
            "last_heartbeat": "2026-07-11T06:56:00-04:00",
            "certification_status": "PASS",
        },
    ],
    "github": {
        "open_prs": [
            {
                "repository": "hermes-agent",
                "number": 12,
                "title": "Morning brief renderer",
                "status": "PASS",
            }
        ],
        "ready_to_merge": [],
        "blocked_prs": [],
        "failed_ci": [],
        "repositories_needing_attention": ["hermes-agent"],
    },
    "timeline": {
        "yesterday": [{"time": "17:00", "title": "Evidence packet completed"}],
        "today": [{"time": "07:00", "title": "Morning review"}],
        "upcoming": [{"time": "09:00", "title": "Clinical work"}],
        "completed": [{"time": "05:42", "title": "Revenue packet validated"}],
        "running": [{"time": "06:42", "title": "Read-only report QA"}],
        "waiting": [{"time": "UNKNOWN", "title": "Owner approval"}],
    },
    "recommended_actions": [
        {
            "rank": 1,
            "title": "Review buyer outreach packet",
            "impact": "HIGH",
            "risk": "LOW",
            "time_required": "5 minutes",
            "return_on_investment": "High",
            "expected_benefit": "Unlocks one buyer-proof cash action",
            "approval_required": "Yes",
        }
    ],
    "integrity": {
        "missing_evidence": [],
        "stale_reports": [],
        "duplicate_jobs": [],
        "conflicting_state": [],
        "unknown_state": [],
    },
}

fixtures: dict[str, dict[str, Any]] = {"healthy_day": BASE}
busy = copy.deepcopy(BASE)
busy.update(overall_health="WARN", blocked_count=2, estimated_review_minutes=5)
busy["active_work"] *= 3
busy["needs_chad"] *= 2
fixtures["busy_day"] = busy
failure = copy.deepcopy(BASE)
failure.update(overall_health="FAIL")
failure["failures"] = [
    {
        "title": "Required evidence check failed",
        "what_happened": "Checksum did not match",
        "likely_cause": "Artifact changed after generation",
        "evidence": "evidence/checksum-failure.txt",
        "recommended_fix": "Regenerate from immutable inputs and reverify",
        "risk_if_ignored": "HIGH",
    }
]
fixtures["failure_day"] = failure
blocked = copy.deepcopy(BASE)
blocked.update(overall_health="WARN", blocked_count=3, active_work=[])
blocked["needs_chad"] = [
    {
        "title": "Choose whether to proceed",
        "reason": "All work is approval-gated",
        "risk": "MEDIUM",
        "recommended_button": "WAIT",
        "explanation": "Evidence is incomplete. Wait until the missing proof is available.",
    }
]
blocked["integrity"]["missing_evidence"] = ["Three blocked tasks lack current proof"]
fixtures["everything_blocked"] = blocked
no_wins = copy.deepcopy(BASE)
no_wins["overnight_wins"] = []
fixtures["no_work_overnight"] = no_wins
contradictory = copy.deepcopy(BASE)
contradictory.update(overall_health="WARN")
contradictory["integrity"]["conflicting_state"] = [
    "mission A is RUNNING in mission snapshot but COMPLETED in timeline snapshot"
]
fixtures["contradictory_evidence"] = contradictory
stale = copy.deepcopy(BASE)
stale.update(overall_health="WARN")
stale["sources"][0].update(freshness="WARN", observed_at="2026-07-10T06:58:00-04:00")
fixtures["stale_evidence"] = stale
unknown = copy.deepcopy(BASE)
unknown.update(overall_health="UNKNOWN", fleet_health=[])
unknown["sources"][0]["freshness"] = "UNKNOWN"
unknown["integrity"]["unknown_state"].append("Mission state unavailable")
fixtures["unknown_state"] = unknown

for name, data in fixtures.items():
    (ROOT / f"{name}.json").write_text(
        json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
