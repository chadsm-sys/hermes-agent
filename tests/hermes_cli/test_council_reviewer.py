"""RED tests for Council Gate V1 review modes and artifact writing."""

from __future__ import annotations

import json


def _request():
    from hermes_cli.council.models import CouncilReviewRequest

    return CouncilReviewRequest(
        session_id="sess-123",
        goal="Build a safe delivery artifact",
        trigger="delivery_review",
        subject="Status: PASS\nEvidence: tests passed",
        metadata={"phase": "red-test"},
    )


def test_mock_council_reviewer_returns_pass_without_external_call():
    from hermes_cli.council.reviewer import MockCouncilReviewer

    result = MockCouncilReviewer().review(_request())

    assert result.decision == "pass"
    assert result.reviewer == "mock"
    assert "mock" in result.summary.lower()


def test_command_council_reviewer_parses_json_result(tmp_path):
    from hermes_cli.council.reviewer import CommandCouncilReviewer

    script = tmp_path / "reviewer.py"
    script.write_text(
        "import json; print(json.dumps({"
        "'decision':'needs_revision',"
        "'summary':'Rollback missing',"
        "'findings':[{'severity':'major','title':'Rollback','evidence':'none','recommendation':'add it'}]"
        "}))",
        encoding="utf-8",
    )

    result = CommandCouncilReviewer(command=["python3", str(script)]).review(_request())

    assert result.decision == "needs_revision"
    assert result.findings[0].severity == "major"
    assert result.findings[0].title == "Rollback"


def test_command_council_reviewer_blocks_shell_strings():
    from hermes_cli.council.reviewer import CommandCouncilReviewer

    assert CommandCouncilReviewer(command="python3 reviewer.py; rm -rf /tmp/nope").review(_request()).decision == "blocked"


def test_artifact_writer_persists_markdown_and_json(tmp_path):
    from hermes_cli.council.artifacts import write_council_artifact
    from hermes_cli.council.models import CouncilReviewResult

    result = CouncilReviewResult(decision="pass", summary="Safe enough for V1.")
    written = write_council_artifact(
        base_dir=tmp_path,
        request=_request(),
        result=result,
    )

    md_path = written["markdown"]
    json_path = written["json"]

    assert md_path.exists()
    assert json_path.exists()
    assert "Council Gate Review" in md_path.read_text(encoding="utf-8")
    assert json.loads(json_path.read_text(encoding="utf-8"))["result"]["decision"] == "pass"


def test_council_redacts_obvious_secrets_before_review(tmp_path):
    from hermes_cli.council.gate import CouncilGate
    from hermes_cli.council.models import CouncilReviewRequest

    redaction_value = "sk-tes...7890"
    request = CouncilReviewRequest(
        goal="redact",
        trigger="delivery_review",
        subject=f"api" + f"_key={redaction_value} and Bearer {redaction_value}",
        metadata={"token": redaction_value, "safe_placeholder": "FAKE_TEST_PLACEHOLDER"},
    )
    outcome = CouncilGate(config={"mode": "mock", "artifact_dir": str(tmp_path)}).review(request)
    artifact_dir = tmp_path / request.review_id
    redacted = (artifact_dir / "council_request_redacted.json").read_text(encoding="utf-8")
    result = (artifact_dir / "council_result.json").read_text(encoding="utf-8")

    assert outcome["decision"] == "pass"
    assert redaction_value not in redacted
    assert redaction_value not in result
    assert "[REDACTED]" in redacted
    assert "FAKE_TEST_PLACEHOLDER" in redacted


def test_council_gate_does_not_write_raw_request_by_default(tmp_path):
    from hermes_cli.council.gate import CouncilGate

    request = _request()

    CouncilGate(config={"mode": "mock", "artifact_dir": str(tmp_path)}).review(request)

    artifact_dir = tmp_path / request.review_id
    assert (artifact_dir / "council_request_redacted.json").exists()
    assert not (artifact_dir / "council_request.json").exists()
    assert not (artifact_dir / "council_request.raw.unsafe.json").exists()


def test_council_gate_raw_request_requires_unsafe_opt_in(tmp_path):
    from hermes_cli.council.gate import CouncilGate

    request = _request()

    CouncilGate(
        config={
            "mode": "mock",
            "artifact_dir": str(tmp_path),
            "persist_raw_request_unsafe": True,
        }
    ).review(request)

    artifact_dir = tmp_path / request.review_id
    assert (artifact_dir / "council_request_redacted.json").exists()
    assert (artifact_dir / "council_request.raw.unsafe.json").exists()


def test_command_reviewer_missing_verdict_blocks(tmp_path):
    from hermes_cli.council.reviewer import CommandCouncilReviewer

    script = tmp_path / "reviewer.py"
    script.write_text(
        "import json; print(json.dumps({'summary':'No explicit approval'}))",
        encoding="utf-8",
    )

    result = CommandCouncilReviewer(command=["python3", str(script)]).review(_request())

    assert result.decision == "blocked"
    assert "missing_verdict" in result.primary_risks


def test_command_reviewer_blank_and_null_verdict_blocks(tmp_path):
    from hermes_cli.council.reviewer import CommandCouncilReviewer

    for name, verdict in {"blank": "", "null": None}.items():
        script = tmp_path / f"reviewer_{name}.py"
        script.write_text(
            "import json; print(json.dumps({'verdict': "
            + repr(verdict)
            + ", 'summary':'No explicit approval'}))",
            encoding="utf-8",
        )

        result = CommandCouncilReviewer(command=["python3", str(script)]).review(_request())

        assert result.decision == "blocked"
        assert "missing_verdict" in result.primary_risks


def test_command_reviewer_unknown_verdict_blocks_as_parse_failure(tmp_path):
    from hermes_cli.council.reviewer import CommandCouncilReviewer

    script = tmp_path / "reviewer.py"
    script.write_text(
        "import json; print(json.dumps({'verdict':'MAYBE','summary':'Ambiguous'}))",
        encoding="utf-8",
    )

    result = CommandCouncilReviewer(command=["python3", str(script)]).review(_request())

    assert result.decision == "blocked"
    assert "parse_failure" in result.primary_risks


def test_enabled_mock_mode_requires_explicit_unsafe_opt_in():
    from hermes_cli.council.reviewer import ManualCouncilReviewer, MockCouncilReviewer, build_reviewer

    assert isinstance(build_reviewer({"enabled": True, "mode": "mock"}), ManualCouncilReviewer)
    assert isinstance(
        build_reviewer({"enabled": True, "mode": "mock", "allow_mock_unsafe": True}),
        MockCouncilReviewer,
    )
