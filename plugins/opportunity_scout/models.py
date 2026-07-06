"""Data models for the Opportunity Scout engine.

This module has no imports from the rest of the plugin (or the network).
Everything serializes to plain dicts so the store can stay a simple,
schema-versioned JSON document.
"""

from __future__ import annotations

import hashlib
import re
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any

SCHEMA_VERSION = 1

_TOKEN_RE = re.compile(r"[a-z0-9]+")

CONFIDENCE_FLOOR = 0.02
CONFIDENCE_CEILING = 0.98


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def clamp_confidence(value: float) -> float:
    return max(CONFIDENCE_FLOOR, min(CONFIDENCE_CEILING, float(value)))


def normalize_tokens(text: str) -> list[str]:
    return _TOKEN_RE.findall(text.lower())


def title_fingerprint(title: str) -> str:
    """Order-insensitive exact fingerprint of a title."""
    tokens = sorted(set(normalize_tokens(title)))
    return hashlib.sha256(" ".join(tokens).encode("utf-8")).hexdigest()


class SourceType(str, Enum):
    IDEA = "idea"
    PERSONAL_NETWORK = "personal_network"
    DIRECT_REQUEST = "direct_request"
    MARKET_SIGNAL = "market_signal"
    RECRUITER = "recruiter"
    EXISTING_CLIENT = "existing_client"


CONFIDENCE_PRIORS: dict[SourceType, float] = {
    SourceType.IDEA: 0.30,
    SourceType.MARKET_SIGNAL: 0.40,
    SourceType.RECRUITER: 0.45,
    SourceType.PERSONAL_NETWORK: 0.50,
    SourceType.DIRECT_REQUEST: 0.60,
    SourceType.EXISTING_CLIENT: 0.65,
}


class Stage(str, Enum):
    CAPTURED = "captured"
    TRIAGED = "triaged"
    SCORED = "scored"
    VALIDATING = "validating"
    VALIDATED = "validated"
    ACTIVE = "active"
    REALIZED = "realized"
    PARKED = "parked"
    REJECTED = "rejected"
    EXPIRED = "expired"


TERMINAL_STAGES = frozenset({Stage.REALIZED, Stage.REJECTED, Stage.EXPIRED})


class EvidenceStrength(str, Enum):
    WEAK = "weak"
    MODERATE = "moderate"
    STRONG = "strong"


EVIDENCE_STRENGTH_FACTOR: dict[EvidenceStrength, float] = {
    EvidenceStrength.WEAK: 0.5,
    EvidenceStrength.MODERATE: 0.75,
    EvidenceStrength.STRONG: 1.0,
}


class CheckStatus(str, Enum):
    PENDING = "pending"
    PASSED = "passed"
    FAILED = "failed"
    SKIPPED = "skipped"


class OpportunityScoutError(Exception):
    """Base error for the plugin."""


class IngestionError(OpportunityScoutError):
    pass


class LifecycleError(OpportunityScoutError):
    pass


class ValidationPipelineError(OpportunityScoutError):
    pass


def _coerce_non_negative(value: Any, field_name: str) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError) as exc:
        raise IngestionError(f"{field_name} must be numeric, got {value!r}") from exc
    if number != number or number in (float("inf"), float("-inf")):
        raise IngestionError(f"{field_name} must be finite, got {value!r}")
    if number < 0:
        raise IngestionError(f"{field_name} must be >= 0, got {value!r}")
    return number


@dataclass
class ConfidenceEvent:
    timestamp: str
    delta: float
    reason: str
    resulting: float

    def to_dict(self) -> dict[str, Any]:
        return {
            "timestamp": self.timestamp,
            "delta": self.delta,
            "reason": self.reason,
            "resulting": self.resulting,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "ConfidenceEvent":
        return cls(
            timestamp=str(data["timestamp"]),
            delta=float(data["delta"]),
            reason=str(data["reason"]),
            resulting=float(data["resulting"]),
        )


@dataclass
class TransitionEvent:
    from_stage: str
    to_stage: str
    timestamp: str
    reason: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "from_stage": self.from_stage,
            "to_stage": self.to_stage,
            "timestamp": self.timestamp,
            "reason": self.reason,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "TransitionEvent":
        return cls(
            from_stage=str(data["from_stage"]),
            to_stage=str(data["to_stage"]),
            timestamp=str(data["timestamp"]),
            reason=str(data["reason"]),
        )


@dataclass
class Evidence:
    summary: str
    source: str
    strength: EvidenceStrength
    added_at: str = field(default_factory=utc_now_iso)

    def __post_init__(self) -> None:
        if not self.summary.strip():
            raise ValidationPipelineError("Evidence.summary is required.")
        if not self.source.strip():
            raise ValidationPipelineError("Evidence.source is required.")
        self.strength = EvidenceStrength(self.strength)

    def to_dict(self) -> dict[str, Any]:
        return {
            "summary": self.summary,
            "source": self.source,
            "strength": self.strength.value,
            "added_at": self.added_at,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Evidence":
        return cls(
            summary=str(data["summary"]),
            source=str(data["source"]),
            strength=EvidenceStrength(data["strength"]),
            added_at=str(data.get("added_at") or utc_now_iso()),
        )


@dataclass
class ValidationStage:
    stage_id: str
    name: str
    weight: float
    status: CheckStatus = CheckStatus.PENDING
    evidence: list[Evidence] = field(default_factory=list)
    resolution_note: str = ""
    resolved_at: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "stage_id": self.stage_id,
            "name": self.name,
            "weight": self.weight,
            "status": self.status.value,
            "evidence": [item.to_dict() for item in self.evidence],
            "resolution_note": self.resolution_note,
            "resolved_at": self.resolved_at,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "ValidationStage":
        return cls(
            stage_id=str(data["stage_id"]),
            name=str(data["name"]),
            weight=float(data["weight"]),
            status=CheckStatus(data.get("status", CheckStatus.PENDING)),
            evidence=[Evidence.from_dict(item) for item in data.get("evidence", [])],
            resolution_note=str(data.get("resolution_note", "")),
            resolved_at=data.get("resolved_at"),
        )


@dataclass
class ValidationState:
    started_at: str | None = None
    stages: list[ValidationStage] = field(default_factory=list)

    @property
    def started(self) -> bool:
        return self.started_at is not None

    @property
    def failed(self) -> bool:
        return any(stage.status is CheckStatus.FAILED for stage in self.stages)

    @property
    def complete(self) -> bool:
        if not self.stages:
            return False
        return all(
            stage.status in (CheckStatus.PASSED, CheckStatus.SKIPPED)
            for stage in self.stages
        )

    def get_stage(self, stage_id: str) -> ValidationStage:
        for stage in self.stages:
            if stage.stage_id == stage_id:
                return stage
        raise ValidationPipelineError(f"Unknown validation stage: {stage_id!r}")

    def to_dict(self) -> dict[str, Any]:
        return {
            "started_at": self.started_at,
            "stages": [stage.to_dict() for stage in self.stages],
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "ValidationState":
        return cls(
            started_at=data.get("started_at"),
            stages=[ValidationStage.from_dict(item) for item in data.get("stages", [])],
        )


@dataclass
class ScoreBreakdown:
    annual_chad_hours: float
    annual_ai_hours: float
    chad_time_cost_usd: float
    total_investment_usd: float
    expected_net_usd: float
    expected_roi: float
    leverage: float
    roi_component: float
    alignment_component: float
    leverage_component: float
    confidence_component: float
    capacity_component: float
    composite: float
    scored_at: str = field(default_factory=utc_now_iso)

    def to_dict(self) -> dict[str, Any]:
        return {
            "annual_chad_hours": self.annual_chad_hours,
            "annual_ai_hours": self.annual_ai_hours,
            "chad_time_cost_usd": self.chad_time_cost_usd,
            "total_investment_usd": self.total_investment_usd,
            "expected_net_usd": self.expected_net_usd,
            "expected_roi": self.expected_roi,
            "leverage": self.leverage,
            "roi_component": self.roi_component,
            "alignment_component": self.alignment_component,
            "leverage_component": self.leverage_component,
            "confidence_component": self.confidence_component,
            "capacity_component": self.capacity_component,
            "composite": self.composite,
            "scored_at": self.scored_at,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "ScoreBreakdown":
        return cls(
            annual_chad_hours=float(data["annual_chad_hours"]),
            annual_ai_hours=float(data["annual_ai_hours"]),
            chad_time_cost_usd=float(data["chad_time_cost_usd"]),
            total_investment_usd=float(data["total_investment_usd"]),
            expected_net_usd=float(data["expected_net_usd"]),
            expected_roi=float(data["expected_roi"]),
            leverage=float(data["leverage"]),
            roi_component=float(data["roi_component"]),
            alignment_component=float(data["alignment_component"]),
            leverage_component=float(data["leverage_component"]),
            confidence_component=float(data["confidence_component"]),
            capacity_component=float(data["capacity_component"]),
            composite=float(data["composite"]),
            scored_at=str(data.get("scored_at") or utc_now_iso()),
        )


@dataclass
class DuplicateMatch:
    opportunity_id: str
    title: str
    similarity: float
    kind: str  # "exact" | "fuzzy"

    def to_dict(self) -> dict[str, Any]:
        return {
            "opportunity_id": self.opportunity_id,
            "title": self.title,
            "similarity": self.similarity,
            "kind": self.kind,
        }


@dataclass
class Opportunity:
    title: str
    summary: str = ""
    tags: list[str] = field(default_factory=list)
    source_type: SourceType = SourceType.IDEA
    source_detail: str = ""
    expected_revenue_usd: float = 0.0
    upfront_cost_usd: float = 0.0
    ongoing_cost_usd_annual: float = 0.0
    chad_hours_upfront: float = 0.0
    chad_hours_weekly: float = 0.0
    ai_hours_upfront: float = 0.0
    ai_hours_weekly: float = 0.0
    opportunity_id: str = field(default_factory=lambda: uuid.uuid4().hex)
    stage: Stage = Stage.CAPTURED
    confidence: float = 0.0
    score: ScoreBreakdown | None = None
    confidence_events: list[ConfidenceEvent] = field(default_factory=list)
    transitions: list[TransitionEvent] = field(default_factory=list)
    validation: ValidationState = field(default_factory=ValidationState)
    duplicate_of: list[str] = field(default_factory=list)
    created_at: str = field(default_factory=utc_now_iso)
    updated_at: str = field(default_factory=utc_now_iso)
    fingerprint: str = ""

    def __post_init__(self) -> None:
        if not self.title.strip():
            raise IngestionError("Opportunity.title is required.")
        self.title = self.title.strip()
        self.summary = self.summary.strip()
        self.source_type = SourceType(self.source_type)
        self.stage = Stage(self.stage)
        self.tags = sorted({tag.strip().lower() for tag in self.tags if tag.strip()})
        for name in (
            "expected_revenue_usd",
            "upfront_cost_usd",
            "ongoing_cost_usd_annual",
            "chad_hours_upfront",
            "chad_hours_weekly",
            "ai_hours_upfront",
            "ai_hours_weekly",
        ):
            setattr(self, name, _coerce_non_negative(getattr(self, name), name))
        if not self.fingerprint:
            self.fingerprint = title_fingerprint(self.title)
        if not self.confidence:
            self.confidence = CONFIDENCE_PRIORS[self.source_type]
        self.confidence = clamp_confidence(self.confidence)

    @property
    def is_terminal(self) -> bool:
        return self.stage in TERMINAL_STAGES

    def touch(self) -> None:
        self.updated_at = utc_now_iso()

    def to_dict(self) -> dict[str, Any]:
        return {
            "opportunity_id": self.opportunity_id,
            "title": self.title,
            "summary": self.summary,
            "tags": list(self.tags),
            "source_type": self.source_type.value,
            "source_detail": self.source_detail,
            "expected_revenue_usd": self.expected_revenue_usd,
            "upfront_cost_usd": self.upfront_cost_usd,
            "ongoing_cost_usd_annual": self.ongoing_cost_usd_annual,
            "chad_hours_upfront": self.chad_hours_upfront,
            "chad_hours_weekly": self.chad_hours_weekly,
            "ai_hours_upfront": self.ai_hours_upfront,
            "ai_hours_weekly": self.ai_hours_weekly,
            "stage": self.stage.value,
            "confidence": self.confidence,
            "score": self.score.to_dict() if self.score else None,
            "confidence_events": [event.to_dict() for event in self.confidence_events],
            "transitions": [event.to_dict() for event in self.transitions],
            "validation": self.validation.to_dict(),
            "duplicate_of": list(self.duplicate_of),
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "fingerprint": self.fingerprint,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Opportunity":
        score_data = data.get("score")
        return cls(
            title=str(data["title"]),
            summary=str(data.get("summary", "")),
            tags=list(data.get("tags", [])),
            source_type=SourceType(data.get("source_type", SourceType.IDEA)),
            source_detail=str(data.get("source_detail", "")),
            expected_revenue_usd=data.get("expected_revenue_usd", 0.0),
            upfront_cost_usd=data.get("upfront_cost_usd", 0.0),
            ongoing_cost_usd_annual=data.get("ongoing_cost_usd_annual", 0.0),
            chad_hours_upfront=data.get("chad_hours_upfront", 0.0),
            chad_hours_weekly=data.get("chad_hours_weekly", 0.0),
            ai_hours_upfront=data.get("ai_hours_upfront", 0.0),
            ai_hours_weekly=data.get("ai_hours_weekly", 0.0),
            opportunity_id=str(data.get("opportunity_id") or uuid.uuid4().hex),
            stage=Stage(data.get("stage", Stage.CAPTURED)),
            confidence=float(data.get("confidence", 0.0)),
            score=ScoreBreakdown.from_dict(score_data) if score_data else None,
            confidence_events=[
                ConfidenceEvent.from_dict(item)
                for item in data.get("confidence_events", [])
            ],
            transitions=[
                TransitionEvent.from_dict(item) for item in data.get("transitions", [])
            ],
            validation=ValidationState.from_dict(data.get("validation", {})),
            duplicate_of=list(data.get("duplicate_of", [])),
            created_at=str(data.get("created_at") or utc_now_iso()),
            updated_at=str(data.get("updated_at") or utc_now_iso()),
            fingerprint=str(data.get("fingerprint", "")),
        )
