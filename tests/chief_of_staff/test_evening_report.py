"""Contract tests for the Evening Report consumer (Part 2)."""

from __future__ import annotations

import dataclasses

import pytest

from chief_of_staff.evening_report import (
    EveningReportError,
    EveningReportSource,
    StaticEveningReportSource,
    parse_evening_report,
)
from tests.chief_of_staff.conftest import make_evening_report_payload


class TestParseHappyPath:
    def test_parses_all_four_sections(self, evening_report_payload):
        report = parse_evening_report(evening_report_payload)

        # Evening Report
        assert report.generated_for == "2026-07-04"
        assert "Shipped 3 backlog items" in report.summary
        # AI Improvements
        assert [i.category for i in report.ai_improvements] == ["reliability"]
        # Compound Engine
        assert {c.id for c in report.compound_engine} == {"cmp-1", "cmp-2"}
        # Opportunity Summary
        assert {o.id for o in report.opportunity_summary} == {"opp-1", "opp-2"}

    def test_result_is_immutable(self, evening_report_payload):
        report = parse_evening_report(evening_report_payload)
        with pytest.raises(dataclasses.FrozenInstanceError):
            report.summary = "rewritten"  # type: ignore[misc]
        assert isinstance(report.compound_engine, tuple)

    def test_top_opportunities_highest_roi_first(self, evening_report_payload):
        report = parse_evening_report(evening_report_payload)
        assert [o.id for o in report.top_opportunities()] == ["opp-2", "opp-1"]
        assert [o.id for o in report.top_opportunities(limit=1)] == ["opp-2"]

    def test_empty_sections_are_valid(self):
        payload = make_evening_report_payload(
            ai_improvements=[], compound_engine=[], opportunity_summary=[]
        )
        report = parse_evening_report(payload)
        assert report.ai_improvements == ()
        assert report.top_opportunities() == ()


class TestContractViolations:
    @pytest.mark.parametrize(
        "missing",
        [
            "schema_version",
            "generated_for",
            "summary",
            "ai_improvements",
            "compound_engine",
            "opportunity_summary",
        ],
    )
    def test_missing_top_level_field_rejected(self, missing):
        payload = make_evening_report_payload()
        del payload[missing]
        with pytest.raises(EveningReportError):
            parse_evening_report(payload)

    def test_major_version_mismatch_rejected(self, evening_report_payload):
        evening_report_payload["schema_version"] = "3.1"
        with pytest.raises(EveningReportError, match="schema_version"):
            parse_evening_report(evening_report_payload)

    def test_unknown_effort_grade_rejected(self, evening_report_payload):
        evening_report_payload["opportunity_summary"][0]["effort"] = "heroic"
        with pytest.raises(EveningReportError, match="effort"):
            parse_evening_report(evening_report_payload)

    def test_negative_compound_counts_rejected(self, evening_report_payload):
        evening_report_payload["compound_engine"][0]["reuse_count"] = -1
        with pytest.raises(EveningReportError, match=">= 0"):
            parse_evening_report(evening_report_payload)

    def test_non_object_list_entry_rejected(self, evening_report_payload):
        evening_report_payload["ai_improvements"] = ["got better at stuff"]
        with pytest.raises(EveningReportError, match="objects"):
            parse_evening_report(evening_report_payload)


class TestSourceInterface:
    def test_static_source_round_trip(self, evening_report_payload):
        report = parse_evening_report(evening_report_payload)
        source = StaticEveningReportSource(report)
        assert source.fetch_latest() is report

    def test_empty_source_returns_none(self):
        assert StaticEveningReportSource().fetch_latest() is None

    def test_static_source_satisfies_protocol(self):
        assert isinstance(StaticEveningReportSource(), EveningReportSource)
