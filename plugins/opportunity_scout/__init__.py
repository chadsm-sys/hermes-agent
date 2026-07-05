"""Opportunity Scout engine — local-first opportunity intelligence.

Public API surface. See ``docs/design/opportunity-scout-engine.md`` for the
architecture and ``plugins/opportunity_scout/README.md`` for usage.
"""

from .engine import CaptureResult, InboxCaptureResult, OpportunityScoutEngine
from .models import (
    CheckStatus,
    ConfidenceEvent,
    DuplicateMatch,
    Evidence,
    EvidenceStrength,
    IngestionError,
    LifecycleError,
    Opportunity,
    OpportunityScoutError,
    ScoreBreakdown,
    SourceType,
    Stage,
    TransitionEvent,
    ValidationPipelineError,
    ValidationStage,
    ValidationState,
)
from .scoring import ScoringConfig, ScoringError, score_opportunity
from .store import OpportunityStore, StoreError

__all__ = [
    "CaptureResult",
    "CheckStatus",
    "ConfidenceEvent",
    "DuplicateMatch",
    "Evidence",
    "EvidenceStrength",
    "InboxCaptureResult",
    "IngestionError",
    "LifecycleError",
    "Opportunity",
    "OpportunityScoutEngine",
    "OpportunityScoutError",
    "OpportunityStore",
    "ScoreBreakdown",
    "ScoringConfig",
    "ScoringError",
    "SourceType",
    "Stage",
    "StoreError",
    "TransitionEvent",
    "ValidationPipelineError",
    "ValidationStage",
    "ValidationState",
    "score_opportunity",
]
