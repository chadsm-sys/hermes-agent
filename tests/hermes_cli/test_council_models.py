"""RED tests for Council Gate V1 models."""

from __future__ import annotations


def test_council_finding_to_dict():
    from hermes_cli.council.models import CouncilFinding

    finding = CouncilFinding(
        severity="blocker",
        title="Missing rollback",
        evidence="No rollback path was provided.",
        recommendation="Add an explicit rollback section before PASS.",
    )

    assert finding.to_dict() == {
        "severity": "blocker",
        "title": "Missing rollback",
        "evidence": "No rollback path was provided.",
        "recommendation": "Add an explicit rollback section before PASS.",
    }


def test_council_review_request_metadata_is_not_shared():
    from hermes_cli.council.models import CouncilReviewRequest

    first = CouncilReviewRequest(
        session_id="s1",
        goal="ship safely",
        trigger="delivery_review",
        subject="done",
    )
    second = CouncilReviewRequest(
        session_id="s2",
        goal="ship safely",
        trigger="delivery_review",
        subject="done",
    )

    first.metadata["x"] = "y"

    assert second.metadata == {}


def test_council_review_result_defaults():
    from hermes_cli.council.models import CouncilReviewResult

    result = CouncilReviewResult(decision="pass", summary="No blockers.")

    assert result.reviewer == "mock"
    assert result.findings == []
    assert result.artifact_path is None
    assert result.to_dict()["decision"] == "pass"
