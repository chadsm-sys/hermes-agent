"""Regression tests for the required-job aggregate gate."""

from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest


_PATH = Path(__file__).resolve().parents[2] / "scripts" / "ci" / "validate_job_results.py"
_WORKFLOW = Path(__file__).resolve().parents[2] / ".github" / "workflows" / "ci.yml"
_SPEC = importlib.util.spec_from_file_location("validate_job_results", _PATH)
if _SPEC is None or _SPEC.loader is None:
    raise ImportError("Failed to load validate_job_results.py")
_MOD = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(_MOD)


def test_success_and_skipped_are_accepted():
    assert _MOD.unexpected_results(["success", "skipped", "success"]) == []


@pytest.mark.parametrize("result", ["failure", "cancelled", "unknown", None, ""])
def test_every_other_result_fails_closed(result):
    assert _MOD.unexpected_results(["success", result]) == [result]


def test_aggregate_checks_out_exact_head_before_running_validator():
    workflow = _WORKFLOW.read_text(encoding="utf-8")
    aggregate = workflow.split("  all-checks-pass:", 1)[1].split(
        "  ci-timings:", 1
    )[0]
    checkout = aggregate.index("uses: actions/checkout@")
    exact_ref = aggregate.index(
        "ref: ${{ github.event.pull_request.head.sha || github.sha }}"
    )
    validator = aggregate.index("python3 scripts/ci/validate_job_results.py")
    assert checkout < exact_ref < validator
