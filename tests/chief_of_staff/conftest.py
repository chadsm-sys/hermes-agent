"""Shared payload builders for the Chief of Staff contract tests.

Builders return plain dicts shaped like future Mission Control payloads, so
individual tests can mutate/delete keys to probe contract enforcement.
"""

from __future__ import annotations

from typing import Any

import pytest


def make_recommendation_payload(**overrides: Any) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "id": "rec-001",
        "title": "Sign the Gusto payroll authorization",
        "rationale": "Unblocks the S-Corp W-2 setup worth $57K/year.",
        "safety_risk": "low",
        "expected_roi_usd": 57000.0,
        "chad_effort_minutes": 10,
        "strategic_alignment": 0.9,
        "confidence": 0.8,
    }
    payload.update(overrides)
    return payload


def make_morning_brief_payload(**overrides: Any) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "schema_version": "1.0",
        "generated_for": "2026-07-05",
        "todays_plan": [
            {
                "id": "plan-1",
                "title": "Approve quarterly tax transfer",
                "owner": "chad",
                "priority": 1,
                "estimated_minutes": 15,
            },
            {
                "id": "plan-2",
                "title": "Rebuild flaky gateway test",
                "owner": "hermes",
                "priority": 2,
                "estimated_minutes": 45,
            },
            {
                "id": "plan-3",
                "title": "Review ExpertWitness intake copy",
                "owner": "chad",
                "priority": 3,
                "estimated_minutes": 20,
            },
        ],
        "biggest_bottleneck": {
            "summary": "Hermes gateway restarts are manual",
            "impact": "Every restart costs ~20 operator minutes",
            "unblocking_action": "Approve the supervised-restart runbook",
        },
        "executive_recommendation": make_recommendation_payload(),
        "ai_responsibilities": [
            {"id": "ai-1", "description": "Triage overnight backlog", "autonomous": True},
            {"id": "ai-2", "description": "Draft invoice follow-ups", "autonomous": False},
        ],
        "estimated_operator_minutes": 35,
    }
    payload.update(overrides)
    return payload


def make_evening_report_payload(**overrides: Any) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "schema_version": "1.0",
        "generated_for": "2026-07-04",
        "summary": "Shipped 3 backlog items; gateway ran clean all day.",
        "ai_improvements": [
            {
                "id": "imp-1",
                "description": "Retry logic now survives provider timeouts",
                "category": "reliability",
            },
        ],
        "compound_engine": [
            {
                "id": "cmp-1",
                "capability": "Invoice draft generator",
                "reuse_count": 12,
                "minutes_saved_total": 240,
            },
            {
                "id": "cmp-2",
                "capability": "Backlog triage classifier",
                "reuse_count": 30,
                "minutes_saved_total": 600,
            },
        ],
        "opportunity_summary": [
            {
                "id": "opp-1",
                "title": "Facility 3 wants two extra shifts",
                "expected_roi_usd": 4920.0,
                "effort": "low",
            },
            {
                "id": "opp-2",
                "title": "Expert witness inquiry pending reply",
                "expected_roi_usd": 12000.0,
                "effort": "medium",
            },
        ],
    }
    payload.update(overrides)
    return payload


@pytest.fixture
def morning_brief_payload() -> dict[str, Any]:
    return make_morning_brief_payload()


@pytest.fixture
def evening_report_payload() -> dict[str, Any]:
    return make_evening_report_payload()
