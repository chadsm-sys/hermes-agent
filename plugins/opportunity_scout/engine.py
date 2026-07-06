"""Facade for the Opportunity Scout engine.

``OpportunityScoutEngine`` is the only class callers need. It composes
ingestion, dedup, scoring, confidence, validation, and lifecycle over a
durable store. Fully offline by design.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from . import dedup, ingestion, lifecycle, validation
from .models import (
    DuplicateMatch,
    EvidenceStrength,
    IngestionError,
    Opportunity,
    Stage,
    TERMINAL_STAGES,
)
from .scoring import ScoringConfig, score_opportunity
from .store import OpportunityStore

DUPLICATE_POLICIES = ("flag", "reject", "allow")


@dataclass
class CaptureResult:
    opportunity: Opportunity | None
    duplicates: list[DuplicateMatch] = field(default_factory=list)
    rejected_as_duplicate: bool = False


@dataclass
class InboxCaptureResult:
    captured: list[CaptureResult] = field(default_factory=list)
    errors: dict[str, str] = field(default_factory=dict)  # filename -> error


class OpportunityScoutEngine:
    def __init__(
        self,
        store: OpportunityStore | None = None,
        scoring_config: ScoringConfig | None = None,
        store_path: str | Path | None = None,
    ):
        self.store = store or OpportunityStore(store_path)
        self.scoring_config = scoring_config or ScoringConfig()

    # -- capture -----------------------------------------------------------

    def capture(
        self, record: dict[str, Any], on_duplicate: str = "flag"
    ) -> CaptureResult:
        """Ingest a raw record, run dedup, persist, and auto-triage.

        ``on_duplicate``:
        - ``flag``   (default) ingest, but annotate ``duplicate_of``.
        - ``reject`` do not ingest when duplicates exist.
        - ``allow``  ingest without annotation.
        """
        if on_duplicate not in DUPLICATE_POLICIES:
            raise IngestionError(
                f"on_duplicate must be one of {DUPLICATE_POLICIES}, "
                f"got {on_duplicate!r}"
            )
        opportunity = ingestion.ingest_record(record)
        duplicates = dedup.find_duplicates(opportunity, self.store.all())
        if duplicates and on_duplicate == "reject":
            return CaptureResult(
                opportunity=None, duplicates=duplicates, rejected_as_duplicate=True
            )
        if duplicates and on_duplicate == "flag":
            opportunity.duplicate_of = [match.opportunity_id for match in duplicates]
        lifecycle.transition(opportunity, Stage.TRIAGED, "Auto-triage on capture.")
        self.store.upsert(opportunity)
        return CaptureResult(opportunity=opportunity, duplicates=duplicates)

    def capture_inbox(
        self, directory: str | Path, on_duplicate: str = "flag"
    ) -> InboxCaptureResult:
        inbox_result = ingestion.ingest_inbox(directory)
        results: list[CaptureResult] = []
        for opportunity in inbox_result.ingested:
            results.append(
                self.capture(
                    {
                        "title": opportunity.title,
                        "summary": opportunity.summary,
                        "tags": list(opportunity.tags),
                        "source_type": opportunity.source_type.value,
                        "source_detail": opportunity.source_detail,
                        "expected_revenue_usd": opportunity.expected_revenue_usd,
                        "upfront_cost_usd": opportunity.upfront_cost_usd,
                        "ongoing_cost_usd_annual": opportunity.ongoing_cost_usd_annual,
                        "chad_hours_upfront": opportunity.chad_hours_upfront,
                        "chad_hours_weekly": opportunity.chad_hours_weekly,
                        "ai_hours_upfront": opportunity.ai_hours_upfront,
                        "ai_hours_weekly": opportunity.ai_hours_weekly,
                    },
                    on_duplicate=on_duplicate,
                )
            )
        return InboxCaptureResult(captured=results, errors=dict(inbox_result.errors))

    # -- scoring -----------------------------------------------------------

    def score(self, opportunity_id: str) -> Opportunity:
        opportunity = self.store.get(opportunity_id)
        opportunity.score = score_opportunity(opportunity, self.scoring_config)
        if opportunity.stage is Stage.TRIAGED:
            lifecycle.transition(opportunity, Stage.SCORED, "Scored by engine.")
        else:
            opportunity.touch()
        self.store.upsert(opportunity)
        return opportunity

    # -- validation --------------------------------------------------------

    def begin_validation(self, opportunity_id: str) -> Opportunity:
        opportunity = self.store.get(opportunity_id)
        validation.begin_validation(opportunity)
        if opportunity.stage is Stage.SCORED:
            lifecycle.transition(
                opportunity, Stage.VALIDATING, "Market validation started."
            )
        self.store.upsert(opportunity)
        return opportunity

    def add_evidence(
        self,
        opportunity_id: str,
        stage_id: str,
        summary: str,
        source: str,
        strength: EvidenceStrength | str,
    ) -> Opportunity:
        opportunity = self.store.get(opportunity_id)
        validation.add_evidence(opportunity, stage_id, summary, source, strength)
        self.store.upsert(opportunity)
        return opportunity

    def resolve_stage(
        self, opportunity_id: str, stage_id: str, outcome: str, note: str = ""
    ) -> Opportunity:
        opportunity = self.store.get(opportunity_id)
        if outcome == "pass":
            validation.pass_stage(opportunity, stage_id, note)
        elif outcome == "fail":
            validation.fail_stage(opportunity, stage_id, note)
        elif outcome == "skip":
            validation.skip_stage(opportunity, stage_id, note)
        else:
            raise ValueError(f"outcome must be pass|fail|skip, got {outcome!r}")
        if opportunity.validation.complete and opportunity.stage is Stage.VALIDATING:
            lifecycle.transition(
                opportunity, Stage.VALIDATED, "All validation stages resolved."
            )
        self.store.upsert(opportunity)
        return opportunity

    # -- lifecycle ---------------------------------------------------------

    def advance(self, opportunity_id: str, target: Stage | str, reason: str) -> Opportunity:
        opportunity = self.store.get(opportunity_id)
        lifecycle.transition(opportunity, Stage(target), reason)
        self.store.upsert(opportunity)
        return opportunity

    def activate(self, opportunity_id: str, reason: str = "Pursuing.") -> Opportunity:
        return self.advance(opportunity_id, Stage.ACTIVE, reason)

    def park(self, opportunity_id: str, reason: str = "Parked.") -> Opportunity:
        return self.advance(opportunity_id, Stage.PARKED, reason)

    def reject(self, opportunity_id: str, reason: str) -> Opportunity:
        return self.advance(opportunity_id, Stage.REJECTED, reason)

    def realize(self, opportunity_id: str, reason: str = "Realized.") -> Opportunity:
        return self.advance(opportunity_id, Stage.REALIZED, reason)

    # -- reporting ---------------------------------------------------------

    def top(self, n: int = 5) -> list[Opportunity]:
        scored = [
            opportunity
            for opportunity in self.store.all()
            if opportunity.score is not None and not opportunity.is_terminal
        ]
        scored.sort(key=lambda opportunity: -opportunity.score.composite)
        return scored[:n]

    def portfolio_report(self) -> dict[str, Any]:
        opportunities = self.store.all()
        by_stage: dict[str, int] = {}
        for opportunity in opportunities:
            by_stage[opportunity.stage.value] = (
                by_stage.get(opportunity.stage.value, 0) + 1
            )
        active = [
            opportunity
            for opportunity in opportunities
            if opportunity.stage not in TERMINAL_STAGES
        ]
        committed_weekly_hours = sum(
            opportunity.chad_hours_weekly
            for opportunity in opportunities
            if opportunity.stage is Stage.ACTIVE
        )
        aggregate_expected_net = sum(
            opportunity.score.expected_net_usd
            for opportunity in active
            if opportunity.score is not None
        )
        return {
            "total": len(opportunities),
            "by_stage": by_stage,
            "active_pipeline": len(active),
            "committed_chad_hours_weekly": round(committed_weekly_hours, 2),
            "capacity_chad_hours_weekly": self.scoring_config.chad_weekly_capacity_hours,
            "aggregate_expected_net_usd": round(aggregate_expected_net, 2),
            "top": [
                {
                    "opportunity_id": opportunity.opportunity_id,
                    "title": opportunity.title,
                    "stage": opportunity.stage.value,
                    "composite": opportunity.score.composite
                    if opportunity.score
                    else None,
                    "confidence": round(opportunity.confidence, 3),
                }
                for opportunity in self.top(5)
            ],
        }
