"""Ingestion and duplicate-detection tests for the Opportunity Scout."""

from __future__ import annotations

import json

import pytest

from plugins.opportunity_scout.dedup import find_duplicates, similarity
from plugins.opportunity_scout.ingestion import (
    ingest_inbox,
    ingest_json_file,
    ingest_record,
)
from plugins.opportunity_scout.models import IngestionError, Opportunity, SourceType


class TestIngestRecord:
    def test_minimal_record(self):
        opp = ingest_record({"title": "Locum weekend block"})
        assert opp.title == "Locum weekend block"
        assert opp.source_type is SourceType.IDEA

    def test_full_record(self):
        opp = ingest_record(
            {
                "title": "Direct contract — Facility X",
                "summary": "Bypass agency post July 2027.",
                "tags": "direct-contracts, income-scaling",
                "source_type": "personal_network",
                "expected_revenue_usd": 250000,
                "chad_hours_upfront": 20,
                "ai_hours_upfront": 40,
            }
        )
        assert opp.tags == ["direct-contracts", "income-scaling"]
        assert opp.expected_revenue_usd == 250000.0

    def test_unknown_fields_rejected(self):
        with pytest.raises(IngestionError, match="Unknown opportunity fields"):
            ingest_record({"title": "x", "bogus": 1})

    def test_missing_title_rejected(self):
        with pytest.raises(IngestionError):
            ingest_record({"summary": "no title"})

    def test_non_dict_rejected(self):
        with pytest.raises(IngestionError):
            ingest_record(["not", "a", "dict"])  # type: ignore[arg-type]


class TestFileAndInbox:
    def test_single_object_file(self, tmp_path):
        path = tmp_path / "one.json"
        path.write_text(json.dumps({"title": "From file"}))
        assert [o.title for o in ingest_json_file(path)] == ["From file"]

    def test_list_file(self, tmp_path):
        path = tmp_path / "many.json"
        path.write_text(json.dumps([{"title": "A"}, {"title": "B"}]))
        assert len(ingest_json_file(path)) == 2

    def test_invalid_json_raises(self, tmp_path):
        path = tmp_path / "bad.json"
        path.write_text("{oops")
        with pytest.raises(IngestionError, match="Invalid JSON"):
            ingest_json_file(path)

    def test_missing_file_raises(self, tmp_path):
        with pytest.raises(IngestionError, match="No such file"):
            ingest_json_file(tmp_path / "ghost.json")

    def test_inbox_moves_good_files_keeps_bad_ones(self, tmp_path):
        (tmp_path / "good.json").write_text(json.dumps({"title": "Good"}))
        (tmp_path / "bad.json").write_text("{nope")
        result = ingest_inbox(tmp_path)
        assert [o.title for o in result.ingested] == ["Good"]
        assert "bad.json" in result.errors
        assert (tmp_path / "processed" / "good.json").exists()
        assert (tmp_path / "bad.json").exists()  # never deleted

    def test_inbox_name_collisions_get_suffixed(self, tmp_path):
        (tmp_path / "processed").mkdir()
        (tmp_path / "processed" / "dup.json").write_text("{}")
        (tmp_path / "dup.json").write_text(json.dumps({"title": "Second"}))
        result = ingest_inbox(tmp_path)
        assert len(result.ingested) == 1
        assert (tmp_path / "processed" / "dup-1.json").exists()

    def test_missing_inbox_raises(self, tmp_path):
        with pytest.raises(IngestionError):
            ingest_inbox(tmp_path / "nowhere")


class TestDedup:
    def test_exact_word_shuffle_is_exact_match(self):
        a = Opportunity(title="Expert witness retainer")
        b = Opportunity(title="Retainer: expert WITNESS")
        matches = find_duplicates(a, [b])
        assert len(matches) == 1
        assert matches[0].kind == "exact"
        assert matches[0].similarity == 1.0

    def test_fuzzy_near_duplicate(self):
        a = Opportunity(title="CRNA expert witness consulting service")
        b = Opportunity(title="CRNA expert witness consulting services")
        matches = find_duplicates(a, [b])
        assert len(matches) == 1
        assert matches[0].kind == "fuzzy"
        assert matches[0].similarity >= 0.82

    def test_unrelated_titles_do_not_match(self):
        a = Opportunity(title="Tesla mileage tracking automation")
        b = Opportunity(title="Weekend locum anesthesia coverage")
        assert find_duplicates(a, [b]) == []

    def test_self_is_excluded(self):
        a = Opportunity(title="Same thing")
        assert find_duplicates(a, [a]) == []

    def test_exact_ranks_before_fuzzy(self):
        candidate = Opportunity(title="Direct contract facility")
        exact = Opportunity(title="facility contract direct")
        fuzzy = Opportunity(title="Direct contract facility X")
        matches = find_duplicates(candidate, [fuzzy, exact])
        assert matches[0].kind == "exact"
        assert matches[0].opportunity_id == exact.opportunity_id

    def test_similarity_symmetry(self):
        a = Opportunity(title="Anesthesia staffing pipeline", tags=["staffing"])
        b = Opportunity(title="Anesthesia staffing platform", tags=["staffing"])
        assert similarity(a, b) == pytest.approx(similarity(b, a))
