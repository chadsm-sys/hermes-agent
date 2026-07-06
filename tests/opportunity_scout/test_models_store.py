"""Model serialization + store durability tests for the Opportunity Scout."""

from __future__ import annotations

import json
import threading

import pytest

from plugins.opportunity_scout.models import (
    CONFIDENCE_PRIORS,
    IngestionError,
    Opportunity,
    SourceType,
    Stage,
    title_fingerprint,
)
from plugins.opportunity_scout.store import OpportunityStore, StoreError


def make_opportunity(**overrides) -> Opportunity:
    defaults = {
        "title": "Expert witness retainer",
        "summary": "Standard-of-care review for a med-mal firm.",
        "tags": ["Expert-Witness", "anesthesia", "expert-witness"],
        "source_type": SourceType.DIRECT_REQUEST,
        "expected_revenue_usd": 60000,
        "chad_hours_weekly": 2,
        "ai_hours_weekly": 6,
    }
    defaults.update(overrides)
    return Opportunity(**defaults)


class TestOpportunityModel:
    def test_requires_title(self):
        with pytest.raises(IngestionError):
            Opportunity(title="   ")

    def test_tags_are_normalized_and_deduped(self):
        opp = make_opportunity()
        assert opp.tags == ["anesthesia", "expert-witness"]

    def test_negative_numbers_rejected(self):
        with pytest.raises(IngestionError):
            make_opportunity(expected_revenue_usd=-1)

    def test_non_numeric_rejected(self):
        with pytest.raises(IngestionError):
            make_opportunity(chad_hours_weekly="lots")

    def test_confidence_prior_from_source_type(self):
        assert make_opportunity().confidence == CONFIDENCE_PRIORS[SourceType.DIRECT_REQUEST]
        idea = make_opportunity(source_type=SourceType.IDEA)
        assert idea.confidence == CONFIDENCE_PRIORS[SourceType.IDEA]

    def test_fingerprint_is_order_insensitive(self):
        left = title_fingerprint("Expert Witness Retainer!")
        right = title_fingerprint("retainer expert witness")
        assert left == right

    def test_round_trip_serialization(self):
        opp = make_opportunity()
        restored = Opportunity.from_dict(opp.to_dict())
        assert restored.to_dict() == opp.to_dict()
        assert restored.stage is Stage.CAPTURED
        assert restored.source_type is SourceType.DIRECT_REQUEST


class TestStore:
    def test_persist_and_reload(self, tmp_path):
        path = tmp_path / "store.json"
        store = OpportunityStore(path)
        opp = make_opportunity()
        store.upsert(opp)

        reloaded = OpportunityStore(path)
        assert len(reloaded) == 1
        assert reloaded.get(opp.opportunity_id).title == opp.title

    def test_get_unknown_raises(self, tmp_path):
        store = OpportunityStore(tmp_path / "store.json")
        with pytest.raises(StoreError):
            store.get("nope")

    def test_delete(self, tmp_path):
        store = OpportunityStore(tmp_path / "store.json")
        opp = make_opportunity()
        store.upsert(opp)
        store.delete(opp.opportunity_id)
        assert len(store) == 0
        with pytest.raises(StoreError):
            store.delete(opp.opportunity_id)

    def test_corrupt_file_is_quarantined_not_lost(self, tmp_path):
        path = tmp_path / "store.json"
        path.write_text("{not json", encoding="utf-8")
        store = OpportunityStore(path)
        assert len(store) == 0
        backups = list(tmp_path.glob("store.json.corrupt-*"))
        assert len(backups) == 1
        assert backups[0].read_text(encoding="utf-8") == "{not json"

    def test_unknown_schema_version_fails_loudly(self, tmp_path):
        path = tmp_path / "store.json"
        path.write_text(json.dumps({"version": 999, "opportunities": {}}))
        with pytest.raises(StoreError):
            OpportunityStore(path)

    def test_env_var_path_resolution(self, tmp_path, monkeypatch):
        target = tmp_path / "env-store.json"
        monkeypatch.setenv("OPPORTUNITY_SCOUT_STORE_PATH", str(target))
        store = OpportunityStore()
        assert store.path == target

    def test_thread_safety_under_concurrent_upserts(self, tmp_path):
        store = OpportunityStore(tmp_path / "store.json")

        def worker(index: int) -> None:
            store.upsert(make_opportunity(title=f"Opportunity number {index}"))

        threads = [threading.Thread(target=worker, args=(i,)) for i in range(12)]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join()
        assert len(store) == 12
        assert len(OpportunityStore(store.path)) == 12
