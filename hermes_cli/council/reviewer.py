"""Council Gate V1 reviewer adapters.

Adapters are deliberately inert unless explicitly configured. No provider SDKs,
API keys, or live model calls are used here.
"""

from __future__ import annotations

import json
import subprocess
from abc import ABC, abstractmethod
from typing import Any, Dict, Iterable, List, Optional

from .models import CouncilFinding, CouncilReviewRequest, CouncilReviewResult


class CouncilReviewer(ABC):
    """Abstract Council reviewer adapter."""

    @abstractmethod
    def review(self, request: CouncilReviewRequest) -> CouncilReviewResult:
        """Return a normalized Council review result."""


class MockCouncilReviewer(CouncilReviewer):
    """Safe local reviewer used by default and in tests."""

    reviewer_name = "mock"

    def review(self, request: CouncilReviewRequest) -> CouncilReviewResult:
        return CouncilReviewResult(
            review_id=request.review_id,
            verdict="APPROVE",
            confidence="HIGH",
            final_recommendation=f"Mock Council approval for {request.gate_type}.",
            reviewer_model_or_adapter=self.reviewer_name,
        )


class ManualCouncilReviewer(CouncilReviewer):
    """Manual placeholder reviewer.

    V1 does not block waiting for interactive input inside autonomous runs. Manual
    mode therefore emits a revise result instructing the operator to review the
    artifact explicitly. It makes no external calls.
    """

    reviewer_name = "manual"

    def review(self, request: CouncilReviewRequest) -> CouncilReviewResult:
        return CouncilReviewResult(
            review_id=request.review_id,
            verdict="REVISE",
            confidence="LOW",
            final_recommendation="Manual Council review required before this checkpoint can pass.",
            primary_risks=["manual_review_required"],
            required_fixes=["Inspect the Council artifact and record an explicit decision."],
            findings=[
                CouncilFinding(
                    severity="medium",
                    category="manual_review",
                    message="Council mode is manual; no autonomous approval was granted.",
                    evidence=f"gate_type={request.gate_type}",
                    recommendation="Inspect the candidate and record an explicit Council decision.",
                )
            ],
            reviewer_model_or_adapter=self.reviewer_name,
        )


class CommandCouncilReviewer(CouncilReviewer):
    """Run a configured argv command and parse JSON from stdout.

    Command mode accepts argv lists only. Shell strings are blocked to avoid
    command-injection footguns. The command receives redacted request JSON on
    stdin and must return one JSON object on stdout.
    """

    reviewer_name = "command"

    def __init__(self, command: Iterable[str], *, timeout: int = 60, enabled: bool = True):
        self.disabled_reason = ""
        if not enabled:
            self.disabled_reason = "Council command reviewer is disabled unless explicitly enabled"
            self.command = []
        elif isinstance(command, str):
            self.disabled_reason = "Council command reviewer requires argv list, not shell string"
            self.command = []
        else:
            self.command: List[str] = [str(part) for part in command]
            if not self.command:
                self.disabled_reason = "Council command reviewer command cannot be empty"
        self.timeout = int(timeout or 60)

    def review(self, request: CouncilReviewRequest) -> CouncilReviewResult:
        if self.disabled_reason:
            return CouncilReviewResult(
                review_id=request.review_id,
                verdict="BLOCK",
                confidence="HIGH",
                final_recommendation=self.disabled_reason,
                primary_risks=["command_disabled"],
                reviewer_model_or_adapter=self.reviewer_name,
            )
        try:
            proc = subprocess.run(
                self.command,
                input=json.dumps(request.to_dict(), ensure_ascii=False),
                text=True,
                capture_output=True,
                timeout=self.timeout,
                check=False,
            )
        except subprocess.TimeoutExpired as exc:
            return CouncilReviewResult(
                review_id=request.review_id,
                verdict="BLOCK",
                confidence="HIGH",
                final_recommendation="Council command timed out; no approval granted.",
                primary_risks=["command_timeout"],
                findings=[CouncilFinding(
                    severity="high",
                    category="command_timeout",
                    message="Council command reviewer timed out.",
                    evidence=f"timeout_seconds={self.timeout}",
                    recommendation="Fix timeout or switch to mock/manual mode.",
                )],
                reviewer_model_or_adapter=self.reviewer_name,
                raw_output=str(exc),
            )
        except OSError as exc:
            return CouncilReviewResult(
                review_id=request.review_id,
                verdict="BLOCK",
                confidence="HIGH",
                final_recommendation="Council command unavailable; no approval granted.",
                primary_risks=["command_unavailable"],
                findings=[CouncilFinding(
                    severity="high",
                    category="command_unavailable",
                    message=f"Council command could not start: {type(exc).__name__}.",
                    evidence="command launch failed",
                    recommendation="Fix the configured command or switch to mock/manual mode.",
                )],
                reviewer_model_or_adapter=self.reviewer_name,
                raw_output="",
            )

        stdout = (proc.stdout or "").strip()
        stderr = (proc.stderr or "").strip()
        if proc.returncode != 0:
            return CouncilReviewResult(
                review_id=request.review_id,
                verdict="BLOCK",
                confidence="HIGH",
                final_recommendation=f"Council command failed with exit {proc.returncode}.",
                primary_risks=["command_failure"],
                findings=[CouncilFinding(
                    severity="high",
                    category="command_failure",
                    message="Council command reviewer exited non-zero.",
                    evidence=stderr[-1000:] or stdout[-1000:] or f"exit={proc.returncode}",
                    recommendation="Fix the configured Council command or switch to mock/manual mode.",
                )],
                reviewer_model_or_adapter=self.reviewer_name,
                raw_output=stdout + (f"\nSTDERR:\n{stderr}" if stderr else ""),
            )
        try:
            data: Dict[str, Any] = json.loads(stdout)
            result = CouncilReviewResult.from_dict({
                **data,
                "review_id": data.get("review_id") or request.review_id,
                "reviewer_model_or_adapter": data.get("reviewer_model_or_adapter") or data.get("reviewer") or self.reviewer_name,
            })
        except Exception as exc:
            return CouncilReviewResult(
                review_id=request.review_id,
                verdict="BLOCK",
                confidence="HIGH",
                final_recommendation="Council command returned malformed output; no approval granted.",
                primary_risks=["parse_failure"],
                findings=[CouncilFinding(
                    severity="high",
                    category="parse_failure",
                    message=f"Could not parse Council command JSON: {type(exc).__name__}.",
                    evidence=stdout[-1000:],
                    recommendation="Return one JSON object matching CouncilReviewResult.",
                )],
                reviewer_model_or_adapter=self.reviewer_name,
                raw_output=stdout,
            )
        result.raw_output = stdout
        return result


def build_reviewer(config: Optional[Dict[str, Any]] = None) -> CouncilReviewer:
    """Build a reviewer adapter from config."""

    cfg = config or {}
    mode = str(cfg.get("mode") or "mock").strip().lower()
    if mode in {"off", "disabled"}:
        return ManualCouncilReviewer()
    if mode == "mock":
        return MockCouncilReviewer()
    if mode == "manual":
        return ManualCouncilReviewer()
    if mode == "command":
        command = cfg.get("command") or cfg.get("cmd") or []
        timeout = int(cfg.get("timeout_seconds") or cfg.get("timeout") or 60)
        enabled = bool(cfg.get("command_enabled") or cfg.get("allow_command"))
        return CommandCouncilReviewer(command, timeout=timeout, enabled=enabled)
    if mode in {"live_model", "live"}:
        if not cfg.get("live_model_enabled") and not cfg.get("allow_live"):
            return ManualCouncilReviewer()
        raise NotImplementedError("Council live model mode is disabled in V1")
    raise ValueError(f"unsupported Council mode: {mode!r}")
