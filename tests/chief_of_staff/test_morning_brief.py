"""Contract tests for the Morning Brief consumer (Part 1)."""

from __future__ import annotations

import dataclasses

import pytest

from chief_of_staff.contracts import SafetyRisk
from chief_of_staff.morning_brief import (
    MorningBrief,
    MorningBriefError,
    MorningBriefSource,
    StaticMorningBriefSource,
    parse_morning_brief,
)
from tests.chief_of_staff.conftest import make_morning_brief_payload


class TestParseHappyPath:
    def test_parses_all_five_sections(self, morning_brief_payload):
        brief = parse_morning_brief(morning_brief_payload)

        assert brief.generated_for == "2026-07-05"
        # Today's Plan
        assert [item.id for item in brief.todays_plan] == ["plan-1", "plan-2", "plan-3"]
        # Biggest Bottleneck
        assert brief.biggest_bottleneck.summary == "Hermes gateway restarts are manual"
        assert brief.biggest_bottleneck.unblocking_action
        # Executive Recommendation
        assert brief.executive_recommendation.id == "rec-001"
        assert brief.executive_recommendation.safety_risk is SafetyRisk.LOW
        # AI Responsibilities
        assert [r.autonomous for r in brief.ai_responsibilities] == [True, False]
        # Estimated Operator Time
        assert brief.estimated_operator_minutes == 35

    def test_accepts_minor_version_drift(self, morning_brief_payload):
        morning_brief_payload["schema_version"] = "1.7"
        assert parse_morning_brief(morning_brief_payload).schema_version == "1.7"

    def test_result_is_immutable(self, morning_brief_payload):
        brief = parse_morning_brief(morning_brief_payload)
        with pytest.raises(dataclasses.FrozenInstanceError):
            brief.estimated_operator_minutes = 0  # type: ignore[misc]
        assert isinstance(brief.todays_plan, tuple)
        assert isinstance(brief.ai_responsibilities, tuple)

    def test_owner_splits_sorted_by_priority(self, morning_brief_payload):
        brief = parse_morning_brief(morning_brief_payload)
        assert [i.id for i in brief.chad_items()] == ["plan-1", "plan-3"]
        assert [i.id for i in brief.hermes_items()] == ["plan-2"]


class TestContractViolations:
    @pytest.mark.parametrize(
        "missing",
        [
            "schema_version",
            "generated_for",
            "todays_plan",
            "biggest_bottleneck",
            "executive_recommendation",
            "ai_responsibilities",
            "estimated_operator_minutes",
        ],
    )
    def test_missing_top_level_field_rejected(self, missing):
        payload = make_morning_brief_payload()
        del payload[missing]
        with pytest.raises(MorningBriefError):
            parse_morning_brief(payload)

    def test_major_version_mismatch_rejected(self, morning_brief_payload):
        morning_brief_payload["schema_version"] = "2.0"
        with pytest.raises(MorningBriefError, match="schema_version"):
            parse_morning_brief(morning_brief_payload)

    def test_non_mapping_payload_rejected(self):
        with pytest.raises(MorningBriefError):
            parse_morning_brief(["not", "a", "mapping"])  # type: ignore[arg-type]

    def test_unknown_owner_rejected(self, morning_brief_payload):
        morning_brief_payload["todays_plan"][0]["owner"] = "intern"
        with pytest.raises(MorningBriefError, match="owner"):
            parse_morning_brief(morning_brief_payload)

    def test_bool_is_not_a_count(self, morning_brief_payload):
        morning_brief_payload["estimated_operator_minutes"] = True
        with pytest.raises(MorningBriefError, match="integer"):
            parse_morning_brief(morning_brief_payload)

    def test_negative_operator_minutes_rejected(self, morning_brief_payload):
        morning_brief_payload["estimated_operator_minutes"] = -5
        with pytest.raises(MorningBriefError, match=">= 0"):
            parse_morning_brief(morning_brief_payload)

    def test_non_boolean_autonomous_rejected(self, morning_brief_payload):
        morning_brief_payload["ai_responsibilities"][0]["autonomous"] = "yes"
        with pytest.raises(MorningBriefError, match="boolean"):
            parse_morning_brief(morning_brief_payload)

    def test_bad_recommendation_confidence_rejected(self, morning_brief_payload):
        morning_brief_payload["executive_recommendation"]["confidence"] = 1.5
        with pytest.raises(MorningBriefError, match="confidence"):
            parse_morning_brief(morning_brief_payload)

    def test_string_where_list_expected_rejected(self, morning_brief_payload):
        morning_brief_payload["todays_plan"] = "plan-1, plan-2"
        with pytest.raises(MorningBriefError, match="list"):
            parse_morning_brief(morning_brief_payload)


class TestSourceInterface:
    def test_static_source_round_trip(self, morning_brief_payload):
        brief = parse_morning_brief(morning_brief_payload)
        source = StaticMorningBriefSource(brief)
        assert source.fetch_latest() is brief

    def test_empty_source_returns_none(self):
        assert StaticMorningBriefSource().fetch_latest() is None

    def test_static_source_satisfies_protocol(self):
        assert isinstance(StaticMorningBriefSource(), MorningBriefSource)

    def test_no_live_mission_control_dependency(self):
        """Interface only: the module must not import any HTTP machinery."""
        import chief_of_staff.morning_brief as module

        source = getattr(module, "__file__", "")
        with open(source, encoding="utf-8") as fh:
            text = fh.read()
        for forbidden in ("requests", "urllib", "httpx", "aiohttp", "socket"):
            assert f"import {forbidden}" not in text

    def test_brief_type_is_exported_from_package_root(self):
        import chief_of_staff

        assert chief_of_staff.MorningBrief is MorningBrief
