#!/usr/bin/env python3
"""Verify an exact, GitHub-authenticated supply-chain attestation."""

from __future__ import annotations

import argparse
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
import hashlib
import json
from pathlib import Path
import re
import sys
from typing import Any, Sequence


ATTESTATION_MARKER = "<!-- hermes-supply-chain-attestation:v1 -->"
ATTESTATION_VERSION = 1
INSTALL_HOOK_RULE = "supply-chain/install-hook-file-added-or-modified/v1"
_SHA1_RE = re.compile(r"[0-9a-f]{40}\Z")
_SHA256_RE = re.compile(r"[0-9a-f]{64}\Z")
_EXPECTED_FIELDS = {
    "version",
    "repository",
    "pull_request",
    "head_sha",
    "path",
    "blob_sha",
    "content_sha256",
    "scanner_rule",
    "finding_sha256",
    "maintainer",
    "attested_at",
    "expires_at",
    "rationale",
}


class AttestationError(ValueError):
    """Raised when an attestation is missing, ambiguous, stale, or invalid."""


@dataclass(frozen=True)
class ExpectedFinding:
    repository: str
    pull_request: int
    head_sha: str
    path: str
    blob_sha: str
    content_sha256: str
    scanner_rule: str
    finding_sha256: str
    required_maintainer: str


def _parse_timestamp(value: object, field: str) -> datetime:
    if not isinstance(value, str) or not value.endswith("Z"):
        raise AttestationError(f"{field} must be an RFC3339 UTC timestamp ending in Z")
    try:
        parsed = datetime.fromisoformat(value[:-1] + "+00:00")
    except ValueError as exc:
        raise AttestationError(f"{field} is not a valid RFC3339 timestamp") from exc
    if parsed.utcoffset() != timedelta(0):
        raise AttestationError(f"{field} must use UTC")
    return parsed


def _require_digest(value: object, field: str, pattern: re.Pattern[str]) -> str:
    if not isinstance(value, str) or pattern.fullmatch(value) is None:
        raise AttestationError(f"{field} has an invalid digest")
    return value


def finding_sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def render_install_hook_finding(files: Sequence[str]) -> str:
    normalized = sorted({name.strip() for name in files if name.strip()})
    if not normalized:
        raise AttestationError("the install-hook finding has no files")
    joined = "\n".join(normalized)
    return (
        "\n### 🚨 CRITICAL: Install-hook file added or modified\n"
        "These files can execute code during package installation or interpreter startup.\n\n"
        "**Files:**\n"
        "```\n"
        f"{joined}\n"
        "```\n"
    )


def _flatten_comments(value: object) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        raise AttestationError("comments payload must be a JSON list")
    flattened: list[dict[str, Any]] = []
    for item in value:
        if isinstance(item, list):
            flattened.extend(_flatten_comments(item))
        elif isinstance(item, dict):
            flattened.append(item)
        else:
            raise AttestationError("comments payload contains a non-object entry")
    return flattened


def _extract_attestation(body: object) -> dict[str, Any] | None:
    if not isinstance(body, str) or ATTESTATION_MARKER not in body:
        return None
    if body.count(ATTESTATION_MARKER) != 1:
        raise AttestationError("attestation comment has a repeated marker")
    suffix = body.split(ATTESTATION_MARKER, 1)[1].strip()
    fenced = re.fullmatch(r"```json\s*(\{.*\})\s*```", suffix, flags=re.DOTALL)
    if fenced is None:
        raise AttestationError(
            "attestation marker must be followed by one JSON code block"
        )
    try:
        payload = json.loads(fenced.group(1))
    except json.JSONDecodeError as exc:
        raise AttestationError("attestation JSON is invalid") from exc
    if not isinstance(payload, dict):
        raise AttestationError("attestation JSON must be an object")
    if set(payload) != _EXPECTED_FIELDS:
        missing = sorted(_EXPECTED_FIELDS - set(payload))
        extra = sorted(set(payload) - _EXPECTED_FIELDS)
        raise AttestationError(
            f"attestation fields mismatch: missing={missing}, extra={extra}"
        )
    return payload


def _validate_comment_identity(
    comment: dict[str, Any], payload: dict[str, Any], required_maintainer: str
) -> datetime:
    user = comment.get("user")
    login = user.get("login") if isinstance(user, dict) else None
    if not isinstance(login, str) or not login:
        raise AttestationError(
            "attestation comment has no authenticated GitHub identity"
        )
    if login.casefold() != required_maintainer.casefold():
        raise AttestationError(
            "attestation comment author is not the required maintainer"
        )
    maintainer = payload["maintainer"]
    if not isinstance(maintainer, str) or maintainer.casefold() != login.casefold():
        raise AttestationError(
            "attestation maintainer does not match the comment author"
        )
    if comment.get("author_association") != "OWNER":
        raise AttestationError("attestation author is not the repository owner")
    return _parse_timestamp(comment.get("updated_at"), "comment.updated_at")


def verify_attestation(
    comments: object,
    expected: ExpectedFinding,
    *,
    now: datetime,
    max_lifetime: timedelta = timedelta(days=7),
) -> dict[str, Any]:
    if now.tzinfo is None or now.utcoffset() != timedelta(0):
        raise AttestationError("verification time must be timezone-aware UTC")

    candidates: list[tuple[dict[str, Any], dict[str, Any]]] = []
    for comment in _flatten_comments(comments):
        payload = _extract_attestation(comment.get("body"))
        if payload is not None:
            candidates.append((comment, payload))
    if len(candidates) != 1:
        raise AttestationError(
            f"expected exactly one attestation comment, found {len(candidates)}"
        )

    comment, payload = candidates[0]
    comment_updated_at = _validate_comment_identity(
        comment, payload, expected.required_maintainer
    )

    if payload["version"] != ATTESTATION_VERSION:
        raise AttestationError("attestation version is unsupported")
    exact_fields = {
        "repository": expected.repository,
        "pull_request": expected.pull_request,
        "head_sha": expected.head_sha,
        "path": expected.path,
        "blob_sha": expected.blob_sha,
        "content_sha256": expected.content_sha256,
        "scanner_rule": expected.scanner_rule,
        "finding_sha256": expected.finding_sha256,
    }
    for field, value in exact_fields.items():
        if payload[field] != value:
            raise AttestationError(
                f"attestation {field} does not match the current finding"
            )

    _require_digest(payload["head_sha"], "head_sha", _SHA1_RE)
    _require_digest(payload["blob_sha"], "blob_sha", _SHA1_RE)
    _require_digest(payload["content_sha256"], "content_sha256", _SHA256_RE)
    _require_digest(payload["finding_sha256"], "finding_sha256", _SHA256_RE)

    rationale = payload["rationale"]
    if not isinstance(rationale, str) or len(rationale.strip()) < 20:
        raise AttestationError("attestation rationale is absent or too short")

    attested_at = _parse_timestamp(payload["attested_at"], "attested_at")
    expires_at = _parse_timestamp(payload["expires_at"], "expires_at")
    if abs(comment_updated_at - attested_at) > timedelta(minutes=5):
        raise AttestationError("attested_at does not match GitHub comment metadata")
    if attested_at > now + timedelta(minutes=5):
        raise AttestationError("attestation timestamp is in the future")
    if expires_at <= attested_at:
        raise AttestationError("attestation expiration is not after attested_at")
    if expires_at - attested_at > max_lifetime:
        raise AttestationError("attestation lifetime exceeds the configured maximum")
    if now >= expires_at:
        raise AttestationError("attestation has expired")

    return payload


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _parse_now(value: str | None) -> datetime:
    return _utc_now() if value is None else _parse_timestamp(value, "now")


def _render_command(args: argparse.Namespace) -> int:
    files = Path(args.files_file).read_text(encoding="utf-8").splitlines()
    Path(args.output).write_text(render_install_hook_finding(files), encoding="utf-8")
    return 0


def _verify_command(args: argparse.Namespace) -> int:
    finding_path = Path(args.finding_file)
    expected = ExpectedFinding(
        repository=args.repository,
        pull_request=args.pull_request,
        head_sha=args.head_sha,
        path=args.path,
        blob_sha=args.blob_sha,
        content_sha256=args.content_sha256,
        scanner_rule=args.scanner_rule,
        finding_sha256=finding_sha256(finding_path),
        required_maintainer=args.required_maintainer,
    )
    comments = json.loads(Path(args.comments_file).read_text(encoding="utf-8"))
    verify_attestation(comments, expected, now=_parse_now(args.now))
    print(
        "Valid exact-digest supply-chain attestation: "
        f"{expected.repository}#{expected.pull_request} {expected.head_sha} "
        f"{expected.path} {expected.content_sha256}"
    )
    return 0


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)

    render = commands.add_parser(
        "render", help="render the canonical install-hook finding"
    )
    render.add_argument("--files-file", required=True)
    render.add_argument("--output", required=True)
    render.set_defaults(func=_render_command)

    verify = commands.add_parser("verify", help="verify one exact attestation comment")
    verify.add_argument("--comments-file", required=True)
    verify.add_argument("--finding-file", required=True)
    verify.add_argument("--repository", required=True)
    verify.add_argument("--pull-request", type=int, required=True)
    verify.add_argument("--head-sha", required=True)
    verify.add_argument("--path", required=True)
    verify.add_argument("--blob-sha", required=True)
    verify.add_argument("--content-sha256", required=True)
    verify.add_argument("--scanner-rule", default=INSTALL_HOOK_RULE)
    verify.add_argument("--required-maintainer", required=True)
    verify.add_argument("--now", help="verification time for deterministic tests")
    verify.set_defaults(func=_verify_command)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        return args.func(args)
    except (AttestationError, json.JSONDecodeError, OSError) as exc:
        print(f"Invalid supply-chain attestation: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
