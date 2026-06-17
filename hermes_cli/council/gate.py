"""Council Gate V1 orchestration and artifact writing."""

from __future__ import annotations

import json
import re
from dataclasses import asdict, is_dataclass
from pathlib import Path
from typing import Any, Dict, Optional

from .models import CouncilFinding, CouncilReviewRequest, CouncilReviewResult
from .reviewer import CouncilReviewer, build_reviewer

_SECRET_PATTERNS = [
    re.compile(r"(?i)(bearer\s+)[A-Za-z0-9._~+/=-]{8,}"),
    re.compile(r"(?i)((?:api[_-]?key|token|password|secret|webhook[_-]?secret)\s*[:=]\s*)([^\s'\"},]+)"),
    re.compile(r"(?i)((?:OPENAI|ANTHROPIC|XAI|GITHUB|GH|SLACK|DISCORD|TELEGRAM)_[A-Z0-9_]*(?:KEY|TOKEN|SECRET)\s*[:=]\s*)([^\s'\"},]+)"),
]


def redact_text(value: str) -> str:
    """Redact obvious secret values from a text payload."""

    text = str(value)
    for pattern in _SECRET_PATTERNS:
        text = pattern.sub(lambda m: f"{m.group(1)}[REDACTED]", text)
    return text


def redact_payload(value: Any) -> Any:
    """Recursively redact secrets from dict/list/string payloads."""

    if is_dataclass(value):
        value = asdict(value)
    if isinstance(value, dict):
        redacted: Dict[str, Any] = {}
        for key, item in value.items():
            key_s = str(key)
            if re.search(r"(?i)(api[_-]?key|token|password|secret|webhook)", key_s):
                redacted[key_s] = "[REDACTED]" if item else item
            else:
                redacted[key_s] = redact_payload(item)
        return redacted
    if isinstance(value, list):
        return [redact_payload(item) for item in value]
    if isinstance(value, str):
        return redact_text(value)
    return value


def _write_json(path: Path, payload: Any) -> None:
    path.write_text(json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False) + "\n", encoding="utf-8")


def _review_markdown(request: CouncilReviewRequest, result: CouncilReviewResult) -> str:
    lines = [
        "# Council Review",
        "",
        f"- Review ID: `{request.review_id}`",
        f"- Gate: `{request.gate_type}`",
        f"- Verdict: `{result.verdict}`",
        f"- Confidence: `{result.confidence}`",
        f"- Reviewer: `{result.reviewer_model_or_adapter}`",
        "",
        "## Final recommendation",
        result.final_recommendation or result.summary,
        "",
    ]
    if result.primary_risks:
        lines += ["## Primary risks", *[f"- {risk}" for risk in result.primary_risks], ""]
    if result.evidence_gaps:
        lines += ["## Evidence gaps", *[f"- {gap}" for gap in result.evidence_gaps], ""]
    if result.required_fixes:
        lines += ["## Required fixes", *[f"- {fix}" for fix in result.required_fixes], ""]
    if result.optional_suggestions:
        lines += ["## Optional suggestions", *[f"- {item}" for item in result.optional_suggestions], ""]
    if result.findings:
        lines += ["## Findings"]
        for finding in result.findings:
            lines.append(f"- **{finding.severity}/{finding.category}**: {finding.message}")
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"


class CouncilArtifactWriter:
    """Minimal artifact writer for Council requests/results."""

    def __init__(self, artifact_dir: str | Path):
        self.artifact_dir = Path(artifact_dir)

    def write_request(self, request: CouncilReviewRequest, redacted_request: Dict[str, Any]) -> Path:
        review_dir = self.artifact_dir / request.review_id
        review_dir.mkdir(parents=True, exist_ok=True)
        _write_json(review_dir / "council_request.json", request.to_dict())
        _write_json(review_dir / "council_request_redacted.json", redacted_request)
        return review_dir

    def write_result(self, request: CouncilReviewRequest, result: CouncilReviewResult, verifier_summary: Optional[Dict[str, Any]] = None) -> Path:
        review_dir = self.artifact_dir / request.review_id
        review_dir.mkdir(parents=True, exist_ok=True)
        _write_json(review_dir / "council_result.json", result.to_dict())
        (review_dir / "council_review.md").write_text(_review_markdown(request, result), encoding="utf-8")
        if verifier_summary is not None:
            _write_json(review_dir / "verifier_summary.json", verifier_summary)
        result.artifact_path = str(review_dir)
        return review_dir


class CouncilGate:
    """Validate, redact, review, persist, and enforce a Council checkpoint."""

    def __init__(self, config: Optional[Dict[str, Any]] = None, reviewer: Optional[CouncilReviewer] = None):
        self.config = config or {}
        self.reviewer = reviewer or build_reviewer(self.config)
        self.max_revisions = int(self.config.get("max_revisions") or 1)
        artifact_dir = self.config.get("artifact_dir") or "council"
        self.writer = CouncilArtifactWriter(artifact_dir)

    def _deterministic_failed(self, request: CouncilReviewRequest) -> bool:
        checks = request.deterministic_checks or {}
        for value in checks.values():
            if value is False:
                return True
            if isinstance(value, str) and value.strip().lower() in {"fail", "failed", "false", "blocked", "error"}:
                return True
            if isinstance(value, dict):
                status = str(value.get("status") or value.get("result") or "").lower()
                if status in {"fail", "failed", "blocked", "error"} or value.get("passed") is False:
                    return True
        return False

    def review(self, request: CouncilReviewRequest) -> Dict[str, Any]:
        request.validate()
        request_dict = request.to_dict()
        redacted = redact_payload(request_dict)
        redacted["redaction_status"] = "redacted"
        review_dir = self.writer.write_request(request, redacted)
        redacted_request = CouncilReviewRequest.from_dict(redacted)
        redacted_request.redaction_status = "redacted"

        deterministic_failed = self._deterministic_failed(request)
        try:
            result = self.reviewer.review(redacted_request)
        except Exception as exc:
            result = CouncilReviewResult(
                review_id=request.review_id,
                verdict="BLOCK",
                confidence="HIGH",
                final_recommendation="Council reviewer failed; no approval granted.",
                primary_risks=["reviewer_exception"],
                findings=[CouncilFinding(
                    severity="high",
                    category="reviewer_exception",
                    message=f"Council reviewer raised {type(exc).__name__}.",
                    evidence="exception raised",
                    recommendation="Fix adapter or switch to mock/manual mode.",
                )],
                reviewer_model_or_adapter="gate",
            )
        if result.review_id and result.review_id != request.review_id:
            result.review_id = request.review_id
        elif not result.review_id:
            result.review_id = request.review_id

        final_status = {
            "APPROVE": "approved",
            "REVISE": "needs_revision",
            "BLOCK": "blocked",
        }[result.verdict]
        if deterministic_failed:
            final_status = "blocked"
            if result.verdict == "APPROVE":
                result = CouncilReviewResult(
                    review_id=request.review_id,
                    verdict="BLOCK",
                    confidence="HIGH",
                    final_recommendation="Deterministic checks failed; Council approval cannot override them.",
                    primary_risks=["deterministic_check_failed"],
                    required_fixes=["Fix failing deterministic checks before retrying Council review."],
                    reviewer_model_or_adapter=result.reviewer_model_or_adapter,
                )

        verifier_summary = {
            "review_id": request.review_id,
            "deterministic_failed": deterministic_failed,
            "verdict": result.verdict,
            "final_status": final_status,
        }
        self.writer.write_result(request, result, verifier_summary=verifier_summary)
        return {
            "status": final_status,
            "verdict": result.verdict,
            "decision": result.decision,
            "confidence": result.confidence,
            "result": result,
            "artifact_dir": str(review_dir),
            "deterministic_failed": deterministic_failed,
            "should_continue": result.verdict == "REVISE",
        }


def review_goal_turn(goal: str, last_response: str, *, council_config: Optional[Dict[str, Any]] = None) -> CouncilReviewResult:
    """GoalManager integration shim for done/delivery checkpoints."""

    cfg = dict(council_config or {})
    request = CouncilReviewRequest(
        gate_type="DELIVERY",
        trigger="done",
        goal_name=goal,
        host_summary="Goal judge returned done; Council review requested before marking complete.",
        frozen_plan_or_delivery=last_response,
        forbidden_actions=[
            "commit", "push", "merge", "rebase", "cron_resume", "live_model_call",
            "paid_api_call", "outbound", "spend_money", "edit_files_directly",
        ],
    )
    gate = CouncilGate(cfg)
    outcome = gate.review(request)
    return outcome["result"]
