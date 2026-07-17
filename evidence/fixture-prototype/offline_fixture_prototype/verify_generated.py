#!/usr/bin/env python3
"""Strictly verify generated Olympus offline fixture manifests and certification evidence."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import tempfile
from pathlib import Path, PurePosixPath
from typing import Dict, Iterable, List, Mapping, Set, Tuple

from generate import generate

ROOT = Path(__file__).resolve().parent
REPO_ROOT = ROOT.parent

REQUIRED_MANIFEST_FILES = {
    "certification.sha256",
    "combined-artifact-manifest.sha256",
    "evidence-manifest.sha256",
    "fixture-manifest.sha256",
    "manifest-root.json",
    "manifest-root.sha256",
    "prototype-source-manifest.sha256",
}
CHILD_MANIFEST_ROOT_KEYS = {
    "certification.sha256": "certification_manifest_sha256",
    "combined-artifact-manifest.sha256": "combined_artifact_manifest_sha256",
    "evidence-manifest.sha256": "evidence-manifest.sha256",
    "fixture-manifest.sha256": "fixture-manifest.sha256",
    "prototype-source-manifest.sha256": "prototype-source-manifest.sha256",
}
SOURCE_MANIFEST_RELATIVE_PATHS = {
    "offline_fixture_prototype/README.md",
    "offline_fixture_prototype/ROLLBACK.md",
    "offline_fixture_prototype/prototype.py",
    "offline_fixture_prototype/generate.py",
    "offline_fixture_prototype/verify_generated.py",
    "offline_fixture_prototype/tests/test_prototype.py",
    "offline_fixture_prototype/tests/test_generation.py",
    "design/fixture_profile_normative_resolutions.md",
    "design/new1_new2_resolution_record.md",
    "design/governance_metadata_schema_v2.md",
    "design/security_review.md",
    "design/threat_model.md",
    "design/abuse_replay_review.md",
    "design/backward_compatibility.md",
    "review/PROTOTYPE-BRANCH-MANIFEST-NOTICE.md",
}
MANIFEST_LINE_RE = re.compile(r"^([0-9a-f]{64})  ([^\r\n]+)$")
REPLAY_RE = re.compile(r"^replay-[0-9a-f]{64}$")
EXPECTED_CHECKS = {
    "advisory_output_digest_integrity", "all_case_expectations", "anti_circular_provenance",
    "canonical_serialization", "deterministic_replay", "downgrade_resistance",
    "fixture_namespace_separation", "governance_and_adversarial_coverage",
    "malformed_input_handling", "new_1_observe_indeterminate_matrix", "provenance_integrity",
    "quarantine_digest_integrity", "replay_integrity", "replay_order_resistance",
    "replay_omission_resistance", "spoof_resistance",
}
EXPECTED_CERTIFICATION_KEYS = {
    "anti_circular_certification", "advisory_output_digest", "checks", "fixture_namespace",
    "limitations", "manifest_digests", "olympus_activation", "production_authority",
    "replay_identifier", "verdict",
}
EXPECTED_ARTIFACT_DIRECTORIES = {"fixtures", "fixtures/raw", "manifests", "reports"}


class ManifestVerificationError(ValueError):
    pass


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _safe_relative_path(text: str) -> str:
    path = PurePosixPath(text)
    if not text or path.is_absolute() or ".." in path.parts or "." in path.parts or path.as_posix() != text:
        raise ManifestVerificationError(f"unsafe or non-canonical manifest path: {text!r}")
    return text


def parse_manifest(path: Path) -> List[Tuple[str, str]]:
    try:
        raw = path.read_bytes()
        text = raw.decode("utf-8", errors="strict")
    except (OSError, UnicodeDecodeError) as exc:
        raise ManifestVerificationError(f"unreadable manifest {path.name}: {exc}") from exc
    if not text or not text.endswith("\n"):
        raise ManifestVerificationError(f"malformed manifest {path.name}: missing content or final newline")
    entries: List[Tuple[str, str]] = []
    seen: Set[str] = set()
    for line in text.splitlines():
        match = MANIFEST_LINE_RE.fullmatch(line)
        if not match:
            raise ManifestVerificationError(f"malformed manifest line in {path.name}: {line!r}")
        digest, relative = match.groups()
        relative = _safe_relative_path(relative)
        if relative in seen:
            raise ManifestVerificationError(f"duplicate manifest entry in {path.name}: {relative}")
        seen.add(relative)
        entries.append((digest, relative))
    if not entries:
        raise ManifestVerificationError(f"empty manifest: {path.name}")
    return entries


def verify_manifest(path: Path, base: Path) -> Dict[str, object]:
    failures: List[Dict[str, str]] = []
    try:
        entries = parse_manifest(path)
    except ManifestVerificationError as exc:
        return {"checked": 0, "failures": [{"error": str(exc)}], "pass": False, "paths": []}
    for expected, relative in entries:
        target = base / relative
        try:
            resolved = target.resolve(strict=True)
            resolved.relative_to(base.resolve(strict=True))
            if target.is_symlink() or any(parent.is_symlink() for parent in target.parents if parent != base.parent):
                actual = "unsafe-symlink"
            else:
                actual = sha256_file(target) if target.is_file() else "missing"
        except (FileNotFoundError, ValueError):
            actual = "missing-or-outside-base"
        except OSError as exc:
            actual = f"unreadable:{exc.__class__.__name__}"
        if actual != expected:
            failures.append({"actual": actual, "expected": expected, "path": relative})
    return {
        "checked": len(entries),
        "failures": failures,
        "pass": not failures,
        "paths": [relative for _, relative in entries],
    }


def _all_relative_files(root: Path, *, exclude_manifests: bool = False) -> Set[str]:
    paths = set()
    for path in root.rglob("*"):
        if not path.is_file():
            continue
        relative = path.relative_to(root).as_posix()
        if exclude_manifests and relative.startswith("manifests/"):
            continue
        paths.add(relative)
    return paths


def _add_failure(results: Dict[str, Dict[str, object]], name: str, message: str) -> None:
    results[name] = {"checked": 0, "failures": [{"error": message}], "pass": False, "paths": []}


def verify(output: Path) -> Dict[str, object]:
    if output.is_symlink():
        return {
            "all_certification_checks_pass": False,
            "all_manifests_pass": False,
            "certification_error": "output path is a symlink",
            "manifest_results": {},
            "replay_identifier": None,
            "verdict": "NEEDS_REVISION",
        }
    output = output.resolve()
    manifests = output / "manifests"
    results: Dict[str, Dict[str, object]] = {}
    symlinks = sorted(path.relative_to(output).as_posix() for path in output.rglob("*") if path.is_symlink())
    actual_directories = {
        path.relative_to(output).as_posix()
        for path in output.rglob("*")
        if path.is_dir() and not path.is_symlink()
    }
    if symlinks or actual_directories != EXPECTED_ARTIFACT_DIRECTORIES:
        _add_failure(
            results,
            "tree-boundary",
            f"symlinks={symlinks} missing_directories={sorted(EXPECTED_ARTIFACT_DIRECTORIES - actual_directories)} "
            f"unexpected_directories={sorted(actual_directories - EXPECTED_ARTIFACT_DIRECTORIES)}",
        )
    else:
        results["tree-boundary"] = {
            "checked": len(EXPECTED_ARTIFACT_DIRECTORIES),
            "failures": [],
            "pass": True,
            "paths": sorted(EXPECTED_ARTIFACT_DIRECTORIES),
        }

    try:
        manifest_entries = list(manifests.rglob("*"))
        actual_manifest_files = {
            path.name for path in manifest_entries
            if path.parent == manifests and path.is_file() and not path.is_symlink()
        }
        invalid_manifest_entries = sorted(
            path.relative_to(manifests).as_posix() for path in manifest_entries
            if path.parent != manifests or not path.is_file() or path.is_symlink()
        )
    except OSError as exc:
        actual_manifest_files = set()
        invalid_manifest_entries = []
        _add_failure(results, "required-manifest-set", f"manifest directory unreadable: {exc}")
    missing = REQUIRED_MANIFEST_FILES - actual_manifest_files
    unexpected = actual_manifest_files - REQUIRED_MANIFEST_FILES
    if missing or unexpected or invalid_manifest_entries:
        _add_failure(
            results,
            "required-manifest-set",
            f"missing={sorted(missing)} unexpected={sorted(unexpected)} invalid_entries={invalid_manifest_entries}",
        )
    elif "required-manifest-set" not in results:
        results["required-manifest-set"] = {
            "checked": len(REQUIRED_MANIFEST_FILES), "failures": [], "pass": True,
            "paths": sorted(REQUIRED_MANIFEST_FILES),
        }

    for name in sorted(REQUIRED_MANIFEST_FILES - {"manifest-root.json"}):
        path = manifests / name
        if not path.is_file():
            _add_failure(results, name, "required manifest missing")
            continue
        base = REPO_ROOT if name == "prototype-source-manifest.sha256" else output
        results[name] = verify_manifest(path, base)

    root_data: Mapping[str, object] = {}
    root_path = manifests / "manifest-root.json"
    try:
        raw_root = root_path.read_bytes()
        decoded = raw_root.decode("utf-8", errors="strict")
        parsed_root = json.loads(decoded)
        if not isinstance(parsed_root, dict):
            raise ManifestVerificationError("manifest-root.json must be a JSON object")
        canonical_root = json.dumps(parsed_root, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8") + b"\n"
        if raw_root != canonical_root:
            raise ManifestVerificationError("manifest-root.json is not canonical JSON")
        root_data = parsed_root
        expected_root_keys = set(CHILD_MANIFEST_ROOT_KEYS.values())
        if set(root_data) != expected_root_keys:
            raise ManifestVerificationError(
                f"manifest-root.json keys mismatch: expected={sorted(expected_root_keys)} actual={sorted(root_data)}"
            )
        results["manifest-root.json"] = {
            "checked": len(root_data), "failures": [], "pass": True, "paths": sorted(root_data),
        }
    except (OSError, UnicodeDecodeError, json.JSONDecodeError, ManifestVerificationError) as exc:
        _add_failure(results, "manifest-root.json", f"invalid root manifest: {exc}")

    root_binding_failures: List[Dict[str, str]] = []
    if root_data:
        for child_name, root_key in CHILD_MANIFEST_ROOT_KEYS.items():
            child_path = manifests / child_name
            try:
                actual = "sha256-" + sha256_file(child_path) if child_path.is_file() else "missing"
            except OSError as exc:
                actual = f"unreadable:{exc.__class__.__name__}"
            expected = root_data.get(root_key)
            if actual != expected:
                root_binding_failures.append({"path": child_name, "actual": actual, "expected": str(expected)})
    else:
        root_binding_failures.append({"error": "root data unavailable"})
    results["root-child-binding"] = {
        "checked": len(CHILD_MANIFEST_ROOT_KEYS), "failures": root_binding_failures,
        "pass": not root_binding_failures, "paths": sorted(CHILD_MANIFEST_ROOT_KEYS),
    }

    expected_sets = {
        "fixture-manifest.sha256": {
            path.relative_to(output).as_posix() for path in (output / "fixtures").rglob("*") if path.is_file()
        },
        "certification.sha256": {
            "reports/fixture-certification-report.json", "reports/fixture-certification-report.md",
        },
        "combined-artifact-manifest.sha256": _all_relative_files(output, exclude_manifests=True),
        "prototype-source-manifest.sha256": SOURCE_MANIFEST_RELATIVE_PATHS,
        "manifest-root.sha256": {"manifests/manifest-root.json"},
    }
    report_files = {
        path.relative_to(output).as_posix() for path in (output / "reports").rglob("*") if path.is_file()
    }
    expected_sets["evidence-manifest.sha256"] = report_files - expected_sets["certification.sha256"]
    for name, expected_paths in expected_sets.items():
        result = results.get(name, {})
        actual_paths = set(result.get("paths", []))
        if actual_paths != expected_paths:
            result.setdefault("failures", []).append({
                "error": f"manifest coverage mismatch missing={sorted(expected_paths - actual_paths)} unexpected={sorted(actual_paths - expected_paths)}"
            })
            result["pass"] = False
            results[name] = result

    certification: Mapping[str, object] = {}
    certification_error = None
    try:
        certification_path = output / "reports" / "fixture-certification-report.json"
        raw_certification = certification_path.read_bytes()
        certification = json.loads(raw_certification.decode("utf-8", errors="strict"))
        if not isinstance(certification, dict) or not isinstance(certification.get("checks"), dict):
            raise ManifestVerificationError("invalid certification report structure")
        canonical_certification = json.dumps(
            certification, sort_keys=True, separators=(",", ":"), ensure_ascii=False
        ).encode("utf-8") + b"\n"
        if raw_certification != canonical_certification:
            raise ManifestVerificationError("certification report is not canonical JSON")
        if set(certification) != EXPECTED_CERTIFICATION_KEYS:
            raise ManifestVerificationError("certification report keys mismatch")
        checks_data = certification["checks"]
        if not isinstance(checks_data, dict) or set(checks_data) != EXPECTED_CHECKS:
            raise ManifestVerificationError("certification check set mismatch")
        if certification.get("fixture_namespace") != "olympus-fixture-v2-20260717":
            raise ManifestVerificationError("certification fixture namespace mismatch")
        if certification.get("olympus_activation") != "DENIED":
            raise ManifestVerificationError("Olympus activation must be explicitly DENIED")
        if certification.get("production_authority") != "DENIED":
            raise ManifestVerificationError("production authority must be explicitly DENIED")
        expected_anti_circular = {
            "certification_digest_is_external": True,
            "evidence_manifests_exclude_certification": True,
            "provenance_excludes_recommendation_confidence_uncertainty_replay_and_provenance": True,
            "replay_item_digest_excludes_only_replay_identifier": True,
        }
        if certification.get("anti_circular_certification") != expected_anti_circular:
            raise ManifestVerificationError("anti-circular certification claims mismatch")
        expected_limitations = [
            "offline synthetic fixture evidence only", "no Hermes integration", "no exporter modification",
            "no runtime, policy, contract, or production configuration modification",
            "no Olympus activation or production authority",
        ]
        if certification.get("limitations") != expected_limitations:
            raise ManifestVerificationError("certification limitations mismatch")
        expected_manifest_digests = {
            key: root_data.get(key)
            for key in ("evidence-manifest.sha256", "fixture-manifest.sha256", "prototype-source-manifest.sha256")
        }
        if certification.get("manifest_digests") != expected_manifest_digests:
            raise ManifestVerificationError("certification manifest digest claims mismatch")
        replay_identifier = certification.get("replay_identifier")
        if not isinstance(replay_identifier, str) or not REPLAY_RE.fullmatch(replay_identifier):
            raise ManifestVerificationError("invalid certification replay identifier")
    except (OSError, UnicodeDecodeError, json.JSONDecodeError, ManifestVerificationError) as exc:
        certification = {}
        certification_error = str(exc)

    semantic_derivation_failures: List[str] = []
    try:
        with tempfile.TemporaryDirectory() as directory:
            expected_output = Path(directory) / "source-derived"
            generate(expected_output)
            actual_paths = _all_relative_files(output)
            expected_paths = _all_relative_files(expected_output)
            if actual_paths != expected_paths:
                semantic_derivation_failures.append(
                    f"source-derived path mismatch missing={sorted(expected_paths - actual_paths)} "
                    f"unexpected={sorted(actual_paths - expected_paths)}"
                )
            for relative in sorted(actual_paths & expected_paths):
                if (output / relative).read_bytes() != (expected_output / relative).read_bytes():
                    semantic_derivation_failures.append(f"source-derived byte mismatch: {relative}")
    except (OSError, SystemExit, ValueError) as exc:
        semantic_derivation_failures.append(f"source derivation failed: {exc}")
    semantic_derivation_pass = not semantic_derivation_failures

    all_manifests_pass = bool(results) and all(result.get("pass") is True for result in results.values())
    all_checks_pass = bool(certification) and all(value is True for value in certification.get("checks", {}).values())
    ready = (
        all_manifests_pass
        and semantic_derivation_pass
        and all_checks_pass
        and certification.get("verdict") == "FIXTURE_PROTOTYPE_READY"
    )
    return {
        "all_certification_checks_pass": all_checks_pass,
        "all_manifests_pass": all_manifests_pass,
        "certification_error": certification_error,
        "manifest_results": results,
        "replay_identifier": certification.get("replay_identifier"),
        "semantic_derivation_failures": semantic_derivation_failures,
        "semantic_derivation_pass": semantic_derivation_pass,
        "verdict": "FIXTURE_PROTOTYPE_READY" if ready else "NEEDS_REVISION",
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=ROOT / "generated")
    args = parser.parse_args()
    # Preserve the caller-supplied path so verify() can reject a symlink at
    # the artifact root before resolving it. Resolving here would erase that
    # security-relevant path identity and bypass the root-symlink guard.
    result = verify(args.output)
    print(json.dumps(result, sort_keys=True, separators=(",", ":")))
    if result["verdict"] != "FIXTURE_PROTOTYPE_READY":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
