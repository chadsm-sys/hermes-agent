"""End-to-end engine and CLI tests for the Opportunity Scout."""

from __future__ import annotations

import json

import pytest

from plugins.opportunity_scout.cli import main as cli_main
from plugins.opportunity_scout.engine import OpportunityScoutEngine
from plugins.opportunity_scout.models import IngestionError, Stage
from plugins.opportunity_scout.store import OpportunityStore


@pytest.fixture
def engine(tmp_path):
    return OpportunityScoutEngine(store_path=tmp_path / "store.json")


RECORD = {
    "title": "Expert witness retainer — med-mal firm",
    "tags": ["expert-witness", "anesthesia", "recurring-revenue"],
    "source_type": "direct_request",
    "expected_revenue_usd": 60_000,
    "chad_hours_weekly": 2,
    "ai_hours_weekly": 6,
}


class TestEngine:
    def test_capture_auto_triages_and_persists(self, engine, tmp_path):
        result = engine.capture(RECORD)
        assert result.opportunity.stage is Stage.TRIAGED
        assert not result.duplicates
        reloaded = OpportunityScoutEngine(store_path=tmp_path / "store.json")
        assert len(reloaded.store) == 1

    def test_duplicate_flag_policy(self, engine):
        first = engine.capture(RECORD).opportunity
        second = engine.capture(RECORD)
        assert second.opportunity is not None
        assert second.duplicates[0].opportunity_id == first.opportunity_id
        assert first.opportunity_id in second.opportunity.duplicate_of

    def test_duplicate_reject_policy(self, engine):
        engine.capture(RECORD)
        result = engine.capture(RECORD, on_duplicate="reject")
        assert result.rejected_as_duplicate
        assert result.opportunity is None
        assert len(engine.store) == 1

    def test_duplicate_allow_policy(self, engine):
        engine.capture(RECORD)
        result = engine.capture(RECORD, on_duplicate="allow")
        assert result.opportunity.duplicate_of == []
        assert len(engine.store) == 2

    def test_bad_duplicate_policy(self, engine):
        with pytest.raises(IngestionError):
            engine.capture(RECORD, on_duplicate="explode")

    def test_full_pipeline_capture_to_active(self, engine):
        opportunity_id = engine.capture(RECORD).opportunity.opportunity_id
        opp = engine.score(opportunity_id)
        assert opp.stage is Stage.SCORED
        assert opp.score is not None and 0 <= opp.score.composite <= 100

        opp = engine.begin_validation(opportunity_id)
        assert opp.stage is Stage.VALIDATING

        for stage in list(opp.validation.stages):
            engine.add_evidence(
                opportunity_id,
                stage.stage_id,
                summary=f"Evidence for {stage.stage_id}",
                source="human research",
                strength="strong",
            )
            opp = engine.resolve_stage(opportunity_id, stage.stage_id, "pass")
        assert opp.stage is Stage.VALIDATED
        assert opp.confidence > 0.60  # prior moved up by passed stages

        opp = engine.activate(opportunity_id, "Signed.")
        assert opp.stage is Stage.ACTIVE

    def test_rescore_after_scored_keeps_stage(self, engine):
        opportunity_id = engine.capture(RECORD).opportunity.opportunity_id
        engine.score(opportunity_id)
        opp = engine.score(opportunity_id)  # idempotent re-score
        assert opp.stage is Stage.SCORED

    def test_reject_and_park(self, engine):
        first = engine.capture(RECORD).opportunity.opportunity_id
        second = engine.capture(
            {"title": "Completely different thing"}
        ).opportunity.opportunity_id
        engine.reject(first, "Conflicts with family time.")
        engine.park(second, "Not this quarter.")
        assert engine.store.get(first).stage is Stage.REJECTED
        assert engine.store.get(second).stage is Stage.PARKED

    def test_capture_inbox(self, engine, tmp_path):
        inbox = tmp_path / "inbox"
        inbox.mkdir()
        (inbox / "opp.json").write_text(json.dumps({"title": "Inbox opportunity"}))
        (inbox / "bad.json").write_text("{broken")
        result = engine.capture_inbox(inbox)
        assert len(result.captured) == 1
        assert result.captured[0].opportunity.title == "Inbox opportunity"
        assert "bad.json" in result.errors

    def test_top_and_report(self, engine):
        big_id = engine.capture(RECORD).opportunity.opportunity_id
        small_id = engine.capture(
            {"title": "Tiny idea", "expected_revenue_usd": 1_000}
        ).opportunity.opportunity_id
        engine.score(big_id)
        engine.score(small_id)
        top = engine.top(1)
        assert top[0].opportunity_id == big_id

        engine.begin_validation(big_id)
        report = engine.portfolio_report()
        assert report["total"] == 2
        assert report["by_stage"] == {"validating": 1, "scored": 1}
        assert report["active_pipeline"] == 2
        assert report["top"][0]["opportunity_id"] == big_id


class TestCli:
    def _add(self, store_path, capsys, *extra) -> str:
        code = cli_main(
            [
                "--store",
                str(store_path),
                "add",
                "CLI opportunity",
                "--tags",
                "income-scaling",
                "--revenue",
                "50000",
                *extra,
            ]
        )
        assert code == 0
        out = capsys.readouterr().out
        return out.split()[0]  # id prefix from summary line

    def test_add_list_score_report(self, tmp_path, capsys):
        store_path = tmp_path / "store.json"
        id_prefix = self._add(store_path, capsys)

        assert cli_main(["--store", str(store_path), "list"]) == 0
        assert "CLI opportunity" in capsys.readouterr().out

        assert cli_main(["--store", str(store_path), "score", id_prefix]) == 0
        capsys.readouterr()

        assert cli_main(["--store", str(store_path), "show", id_prefix]) == 0
        shown = json.loads(capsys.readouterr().out)
        assert shown["stage"] == "scored"
        assert shown["score"]["composite"] > 0

        assert cli_main(["--store", str(store_path), "report"]) == 0
        report = json.loads(capsys.readouterr().out)
        assert report["total"] == 1

    def test_duplicate_reject_exit_code(self, tmp_path, capsys):
        store_path = tmp_path / "store.json"
        self._add(store_path, capsys)
        code = cli_main(
            [
                "--store",
                str(store_path),
                "add",
                "CLI opportunity",
                "--on-duplicate",
                "reject",
            ]
        )
        assert code == 2

    def test_validation_workflow_via_cli(self, tmp_path, capsys):
        store_path = tmp_path / "store.json"
        id_prefix = self._add(store_path, capsys)
        assert cli_main(["--store", str(store_path), "score", id_prefix]) == 0
        capsys.readouterr()
        assert (
            cli_main(["--store", str(store_path), "validate", "begin", id_prefix]) == 0
        )
        capsys.readouterr()
        assert (
            cli_main(
                [
                    "--store",
                    str(store_path),
                    "validate",
                    "evidence",
                    id_prefix,
                    "problem_evidence",
                    "--summary",
                    "Real ask from a firm",
                    "--source",
                    "phone call",
                    "--strength",
                    "strong",
                ]
            )
            == 0
        )
        capsys.readouterr()
        assert (
            cli_main(
                [
                    "--store",
                    str(store_path),
                    "validate",
                    "resolve",
                    id_prefix,
                    "problem_evidence",
                    "pass",
                ]
            )
            == 0
        )
        state = json.loads(capsys.readouterr().out)
        assert state["stages"][0]["status"] == "passed"

    def test_illegal_advance_reports_error(self, tmp_path, capsys):
        store_path = tmp_path / "store.json"
        id_prefix = self._add(store_path, capsys)
        code = cli_main(
            [
                "--store",
                str(store_path),
                "advance",
                id_prefix,
                "active",
                "--reason",
                "skipping steps",
            ]
        )
        assert code == 1
        assert "Illegal transition" in capsys.readouterr().err

    def test_inbox_command(self, tmp_path, capsys):
        store_path = tmp_path / "store.json"
        inbox = tmp_path / "inbox"
        inbox.mkdir()
        (inbox / "one.json").write_text(json.dumps({"title": "Inbox via CLI"}))
        assert cli_main(["--store", str(store_path), "inbox", str(inbox)]) == 0
        payload = json.loads(capsys.readouterr().out)
        assert payload["captured"] == 1
