"""Contract tests for the exact-digest supply-chain attestation verifier."""

from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import importlib.util
import json
from pathlib import Path
import sys

import pytest


_PATH = (
    Path(__file__).resolve().parents[2]
    / "scripts"
    / "ci"
    / "verify_supply_chain_attestation.py"
)
_SPEC = importlib.util.spec_from_file_location("verify_supply_chain_attestation", _PATH)
if _SPEC is None or _SPEC.loader is None:
    raise ImportError("Failed to load verify_supply_chain_attestation.py")
_MOD = importlib.util.module_from_spec(_SPEC)
sys.modules[_SPEC.name] = _MOD
_SPEC.loader.exec_module(_MOD)


NOW = datetime(2026, 7, 14, 16, 0, tzinfo=timezone.utc)
ATTESTED_AT = "2026-07-14T16:00:00Z"
EXPIRES_AT = "2026-07-21T16:00:00Z"
FINDING = _MOD.render_install_hook_finding(["setup.py"])
EXPECTED = _MOD.ExpectedFinding(
    repository="chadsm-sys/hermes-agent",
    pull_request=18,
    head_sha="a" * 40,
    path="setup.py",
    blob_sha="b" * 40,
    content_sha256="c" * 64,
    scanner_rule=_MOD.INSTALL_HOOK_RULE,
    finding_sha256=hashlib.sha256(FINDING.encode()).hexdigest(),
    required_maintainer="chadsm-sys",
)


def _payload(**overrides):
    payload = {
        "version": 1,
        "repository": EXPECTED.repository,
        "pull_request": EXPECTED.pull_request,
        "head_sha": EXPECTED.head_sha,
        "path": EXPECTED.path,
        "blob_sha": EXPECTED.blob_sha,
        "content_sha256": EXPECTED.content_sha256,
        "scanner_rule": EXPECTED.scanner_rule,
        "finding_sha256": EXPECTED.finding_sha256,
        "maintainer": EXPECTED.required_maintainer,
        "attested_at": ATTESTED_AT,
        "expires_at": EXPIRES_AT,
        "rationale": "Reviewed exact inherited packaging behavior; no hidden execution.",
    }
    payload.update(overrides)
    return payload


def _comment(
    payload=None, *, login="chadsm-sys", association="OWNER", updated=ATTESTED_AT
):
    body = "ordinary comment"
    if payload is not None:
        body = (
            f"{_MOD.ATTESTATION_MARKER}\n"
            "```json\n"
            f"{json.dumps(payload, sort_keys=True)}\n"
            "```"
        )
    return {
        "body": body,
        "user": None if login is None else {"login": login},
        "author_association": association,
        "updated_at": updated,
    }


def _verify(comments, *, now=NOW):
    return _MOD.verify_attestation(comments, EXPECTED, now=now)


def test_render_install_hook_finding_is_canonical():
    assert _MOD.render_install_hook_finding(["setup.py", "setup.cfg", "setup.py"]) == (
        "\n### 🚨 CRITICAL: Install-hook file added or modified\n"
        "These files can execute code during package installation or interpreter startup.\n\n"
        "**Files:**\n"
        "```\n"
        "setup.cfg\n"
        "setup.py\n"
        "```\n"
    )


def test_valid_attestation_accepts_gh_api_slurped_pages():
    payload = _payload()
    assert _verify([[_comment(None)], [_comment(payload)]]) == payload


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("repository", "someone-else/hermes-agent"),
        ("pull_request", 19),
        ("head_sha", "d" * 40),
        ("path", "other/setup.py"),
        ("blob_sha", "d" * 40),
        ("content_sha256", "d" * 64),
        ("scanner_rule", "supply-chain/changed-rule/v2"),
        ("finding_sha256", "d" * 64),
    ],
)
def test_exact_binding_rejects_replay_or_drift(field, value):
    with pytest.raises(_MOD.AttestationError, match=field):
        _verify([_comment(_payload(**{field: value}))])


@pytest.mark.parametrize(
    ("login", "association", "maintainer", "message"),
    [
        (None, "OWNER", "chadsm-sys", "no authenticated GitHub identity"),
        ("intruder", "OWNER", "intruder", "not the required maintainer"),
        ("chadsm-sys", "MEMBER", "chadsm-sys", "not the repository owner"),
        ("chadsm-sys", "OWNER", None, "does not match the comment author"),
    ],
)
def test_missing_or_invalid_maintainer_identity_fails_closed(
    login, association, maintainer, message
):
    with pytest.raises(_MOD.AttestationError, match=message):
        _verify([
            _comment(
                _payload(maintainer=maintainer),
                login=login,
                association=association,
            )
        ])


@pytest.mark.parametrize(
    ("overrides", "now", "updated", "message"),
    [
        ({"expires_at": ATTESTED_AT}, NOW, ATTESTED_AT, "not after"),
        (
            {"expires_at": "2026-07-21T16:00:01Z"},
            NOW,
            ATTESTED_AT,
            "lifetime exceeds",
        ),
        (
            {
                "attested_at": "2026-07-14T15:00:00Z",
                "expires_at": "2026-07-14T15:59:59Z",
            },
            NOW,
            "2026-07-14T15:00:00Z",
            "expired",
        ),
        (
            {
                "attested_at": "2026-07-14T16:06:00Z",
                "expires_at": "2026-07-21T16:06:00Z",
            },
            NOW,
            "2026-07-14T16:06:00Z",
            "timestamp is in the future",
        ),
        ({}, NOW, "2026-07-14T16:06:00Z", "does not match GitHub"),
        ({"rationale": "too short"}, NOW, ATTESTED_AT, "rationale"),
        ({"version": 2}, NOW, ATTESTED_AT, "version"),
    ],
)
def test_time_and_policy_constraints_fail_closed(overrides, now, updated, message):
    with pytest.raises(_MOD.AttestationError, match=message):
        _verify([_comment(_payload(**overrides), updated=updated)], now=now)


def test_absent_malformed_or_ambiguous_attestation_fails_closed():
    with pytest.raises(_MOD.AttestationError, match="found 0"):
        _verify([_comment(None)])

    malformed = _comment(None)
    malformed["body"] = f"{_MOD.ATTESTATION_MARKER}\nnot-json"
    with pytest.raises(_MOD.AttestationError, match="JSON code block"):
        _verify([malformed])

    with pytest.raises(_MOD.AttestationError, match="found 2"):
        _verify([_comment(_payload()), _comment(_payload())])


def test_unknown_attestation_fields_fail_closed():
    payload = _payload()
    payload["waive_other_findings"] = True
    with pytest.raises(_MOD.AttestationError, match="fields mismatch"):
        _verify([_comment(payload)])


def test_cli_hashes_the_exact_finding_bytes(tmp_path, capsys):
    finding_path = tmp_path / "finding.md"
    finding_path.write_text(FINDING, encoding="utf-8")
    comments_path = tmp_path / "comments.json"
    comments_path.write_text(json.dumps([_comment(_payload())]), encoding="utf-8")
    result = _MOD.main([
        "verify",
        "--comments-file",
        str(comments_path),
        "--finding-file",
        str(finding_path),
        "--repository",
        EXPECTED.repository,
        "--pull-request",
        str(EXPECTED.pull_request),
        "--head-sha",
        EXPECTED.head_sha,
        "--path",
        EXPECTED.path,
        "--blob-sha",
        EXPECTED.blob_sha,
        "--content-sha256",
        EXPECTED.content_sha256,
        "--required-maintainer",
        EXPECTED.required_maintainer,
        "--now",
        ATTESTED_AT,
    ])
    assert result == 0
    assert "Valid exact-digest" in capsys.readouterr().out


def test_cli_rejects_changed_scanner_output(tmp_path, capsys):
    changed_finding = tmp_path / "changed.md"
    changed_finding.write_text(FINDING + "scanner output changed\n", encoding="utf-8")
    comments_path = tmp_path / "comments.json"
    comments_path.write_text(json.dumps([_comment(_payload())]), encoding="utf-8")
    result = _MOD.main([
        "verify",
        "--comments-file",
        str(comments_path),
        "--finding-file",
        str(changed_finding),
        "--repository",
        EXPECTED.repository,
        "--pull-request",
        str(EXPECTED.pull_request),
        "--head-sha",
        EXPECTED.head_sha,
        "--path",
        EXPECTED.path,
        "--blob-sha",
        EXPECTED.blob_sha,
        "--content-sha256",
        EXPECTED.content_sha256,
        "--required-maintainer",
        EXPECTED.required_maintainer,
        "--now",
        ATTESTED_AT,
    ])
    assert result == 1
    assert "finding_sha256" in capsys.readouterr().err
