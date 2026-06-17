"""Data models for Council Gate V1.

The V1 model layer is local-only and serialization-first so review artifacts can
be written and inspected without invoking live providers.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from uuid import uuid4

VALID_GATE_TYPES = {
    "GOAL_PLAN",
    "BUILD_SCOPE",
    "DELIVERY",
    "APPLAB_CANDIDATE",
    "COMMIT_READY",
    "MERGE_READY",
    "CRON_RESUME",
    "PUBLIC_RELEASE",
    "OUTBOUND_OR_SPEND",
    "PROVIDER_AUTH_DB_CRON_CHANGE",
}
VALID_VERDICTS = {"APPROVE", "REVISE", "BLOCK"}
VALID_CONFIDENCE = {"LOW", "MEDIUM", "HIGH"}
VALID_DECISIONS = {"pass", "needs_revision", "blocked"}
VALID_SEVERITIES = {"info", "low", "medium", "major", "high", "critical", "blocker"}
_DECISION_TO_VERDICT = {"pass": "APPROVE", "needs_revision": "REVISE", "blocked": "BLOCK"}
_VERDICT_TO_DECISION = {value: key for key, value in _DECISION_TO_VERDICT.items()}


def _utc_now_iso() -> str:
    return datetime.now(tz=timezone.utc).replace(microsecond=0).isoformat()


def _list(value: Any) -> List[Any]:
    if value is None:
        return []
    if isinstance(value, list):
        return value
    return [value]


def _normalize_gate(value: str) -> str:
    maybe = (value or "").strip().upper()
    mapping = {
        "PLAN": "GOAL_PLAN",
        "GOAL_PLAN": "GOAL_PLAN",
        "SCOPE": "BUILD_SCOPE",
        "BUILD_SCOPE": "BUILD_SCOPE",
        "DELIVERY": "DELIVERY",
        "DELIVERY_REVIEW": "DELIVERY",
        "DONE": "DELIVERY",
        "APPLAB": "APPLAB_CANDIDATE",
        "APPLAB_CANDIDATE": "APPLAB_CANDIDATE",
        "COMMIT": "COMMIT_READY",
        "COMMIT_READY": "COMMIT_READY",
        "MERGE": "MERGE_READY",
        "MERGE_READY": "MERGE_READY",
        "CRON_RESUME": "CRON_RESUME",
        "PUBLIC_RELEASE": "PUBLIC_RELEASE",
        "OUTBOUND_OR_SPEND": "OUTBOUND_OR_SPEND",
        "PROVIDER_AUTH_DB_CRON_CHANGE": "PROVIDER_AUTH_DB_CRON_CHANGE",
    }
    return mapping.get(maybe, maybe)


@dataclass
class CouncilFinding:
    """A single Council review finding.

    ``title`` is the legacy field expected by the frozen RED tests. ``category``
    and ``message`` are supported for the Phase 3 runtime contract.
    """

    severity: str
    title: str = ""
    evidence: str = ""
    recommendation: str = ""
    category: str = ""
    message: str = ""

    def __post_init__(self) -> None:
        self.severity = (self.severity or "").strip().lower()
        if self.severity not in VALID_SEVERITIES:
            raise ValueError(f"invalid Council finding severity: {self.severity!r}")
        if not self.title and self.message:
            self.title = self.category or self.message[:80]
        if not self.message and self.title:
            self.message = self.title
        if not self.category:
            self.category = self.title or "general"
        if not self.title:
            raise ValueError("Council finding title is required")

    def to_dict(self) -> Dict[str, Any]:
        # Preserve legacy exact shape when category/message are derived only.
        if self.message == self.title and self.category == self.title:
            return {
                "severity": self.severity,
                "title": self.title,
                "evidence": self.evidence,
                "recommendation": self.recommendation,
            }
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "CouncilFinding":
        return cls(
            severity=str(data.get("severity") or ""),
            title=str(data.get("title") or ""),
            evidence=str(data.get("evidence") or ""),
            recommendation=str(data.get("recommendation") or ""),
            category=str(data.get("category") or ""),
            message=str(data.get("message") or ""),
        )


@dataclass
class CouncilReviewRequest:
    """Input passed to a Council reviewer adapter."""

    review_id: str = ""
    created_at: str = field(default_factory=_utc_now_iso)
    repo_path: str = ""
    branch: str = ""
    gate_type: str = "GOAL_PLAN"
    goal_name: str = ""
    host_summary: str = ""
    frozen_plan_or_delivery: str = ""
    artifacts: List[str] = field(default_factory=list)
    evidence: List[str] = field(default_factory=list)
    deterministic_checks: Dict[str, Any] = field(default_factory=dict)
    allowed_actions: List[str] = field(default_factory=list)
    forbidden_actions: List[str] = field(default_factory=list)
    risk_notes: List[str] = field(default_factory=list)
    reviewer_questions: List[str] = field(default_factory=list)
    redaction_status: str = "unredacted"
    metadata: Dict[str, Any] = field(default_factory=dict)
    session_id: str = ""
    # Legacy aliases
    trigger: str = ""
    goal: str = ""
    candidate: str = ""
    context: str = ""
    subject: str = ""

    def __post_init__(self) -> None:
        if not self.review_id:
            self.review_id = f"council-{uuid4().hex[:12]}"
        source_gate = self.trigger or self.gate_type
        self.gate_type = _normalize_gate(source_gate)
        if self.gate_type not in VALID_GATE_TYPES:
            raise ValueError(f"invalid Council gate_type: {self.gate_type!r}")
        if not self.trigger:
            self.trigger = self.gate_type.lower()
        if self.goal and not self.goal_name:
            self.goal_name = self.goal
        if self.goal_name and not self.goal:
            self.goal = self.goal_name
        payload = self.subject or self.candidate or self.frozen_plan_or_delivery
        if payload and not self.frozen_plan_or_delivery:
            self.frozen_plan_or_delivery = payload
        if self.frozen_plan_or_delivery and not self.candidate:
            self.candidate = self.frozen_plan_or_delivery
        if self.frozen_plan_or_delivery and not self.subject:
            self.subject = self.frozen_plan_or_delivery
        self.artifacts = [str(x) for x in _list(self.artifacts)]
        self.evidence = [str(x) for x in _list(self.evidence)]
        self.allowed_actions = [str(x) for x in _list(self.allowed_actions)]
        self.forbidden_actions = [str(x) for x in _list(self.forbidden_actions)]
        self.risk_notes = [str(x) for x in _list(self.risk_notes)]
        self.reviewer_questions = [str(x) for x in _list(self.reviewer_questions)]

    def validate(self) -> None:
        if self.gate_type not in VALID_GATE_TYPES:
            raise ValueError(f"invalid Council gate_type: {self.gate_type!r}")
        if not (self.goal_name or self.host_summary or self.frozen_plan_or_delivery or self.subject):
            raise ValueError("Council review request requires goal, summary, or delivery payload")

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "CouncilReviewRequest":
        return cls(**dict(data))


@dataclass
class CouncilReviewResult:
    """Normalized Council review output."""

    review_id: str = ""
    verdict: str = ""
    confidence: str = "MEDIUM"
    primary_risks: List[str] = field(default_factory=list)
    evidence_gaps: List[str] = field(default_factory=list)
    scope_creep_detected: bool = False
    safety_concerns: List[str] = field(default_factory=list)
    distribution_or_monetization_concerns: List[str] = field(default_factory=list)
    required_fixes: List[str] = field(default_factory=list)
    optional_suggestions: List[str] = field(default_factory=list)
    final_recommendation: str = ""
    reviewer_model_or_adapter: str = "mock"
    created_at: str = field(default_factory=_utc_now_iso)
    findings: List[CouncilFinding] = field(default_factory=list)
    artifact_path: Optional[str] = None
    raw_output: str = ""
    # Legacy aliases
    decision: str = ""
    summary: str = ""
    reviewer: str = ""

    def __post_init__(self) -> None:
        if self.decision and not self.verdict:
            self.verdict = _DECISION_TO_VERDICT.get(self.decision.strip().lower(), self.decision)
        self.verdict = (self.verdict or "APPROVE").strip().upper()
        if self.verdict.lower() in VALID_DECISIONS:
            self.verdict = _DECISION_TO_VERDICT[self.verdict.lower()]
        if self.verdict not in VALID_VERDICTS:
            raise ValueError(f"invalid Council verdict: {self.verdict!r}")
        self.confidence = (self.confidence or "MEDIUM").strip().upper()
        if self.confidence not in VALID_CONFIDENCE:
            raise ValueError(f"invalid Council confidence: {self.confidence!r}")
        self.decision = _VERDICT_TO_DECISION[self.verdict]
        if self.summary and not self.final_recommendation:
            self.final_recommendation = self.summary
        if self.final_recommendation and not self.summary:
            self.summary = self.final_recommendation
        if not self.summary:
            raise ValueError("Council review summary is required")
        if self.reviewer and not self.reviewer_model_or_adapter:
            self.reviewer_model_or_adapter = self.reviewer
        if not self.reviewer:
            self.reviewer = self.reviewer_model_or_adapter or "mock"
        normalized: List[CouncilFinding] = []
        for finding in self.findings:
            if isinstance(finding, CouncilFinding):
                normalized.append(finding)
            elif isinstance(finding, dict):
                normalized.append(CouncilFinding.from_dict(finding))
            else:
                raise TypeError("Council findings must be CouncilFinding or dict")
        self.findings = normalized
        self.primary_risks = [str(x) for x in _list(self.primary_risks)]
        self.evidence_gaps = [str(x) for x in _list(self.evidence_gaps)]
        self.safety_concerns = [str(x) for x in _list(self.safety_concerns)]
        self.distribution_or_monetization_concerns = [str(x) for x in _list(self.distribution_or_monetization_concerns)]
        self.required_fixes = [str(x) for x in _list(self.required_fixes)]
        self.optional_suggestions = [str(x) for x in _list(self.optional_suggestions)]

    def to_dict(self) -> Dict[str, Any]:
        data = asdict(self)
        data["findings"] = [finding.to_dict() for finding in self.findings]
        return data

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "CouncilReviewResult":
        payload = dict(data)
        if "findings" in payload:
            payload["findings"] = [CouncilFinding.from_dict(item) for item in payload.get("findings") or []]
        return cls(**payload)
