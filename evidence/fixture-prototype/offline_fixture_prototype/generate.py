#!/usr/bin/env python3
"""Generate and certify the standalone Olympus Schema v2 offline fixture corpus."""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
import os
import shutil
import tempfile
from pathlib import Path
from typing import Any, Dict, Iterable, List, Mapping, Sequence, Tuple

from prototype import (
    FIXTURE_NAMESPACE,
    PROFILE_DIGESTS,
    build_representative_corpus,
    canonical_json,
    compute_provenance_identifier,
    compute_replay_identifier,
    normalize_corpus,
    validate_record,
)

ROOT = Path(__file__).resolve().parent
SOURCE_MANIFEST_PATHS = [
    ROOT / "README.md",
    ROOT / "ROLLBACK.md",
    ROOT / "prototype.py",
    ROOT / "generate.py",
    ROOT / "verify_generated.py",
    ROOT / "tests" / "test_prototype.py",
    ROOT / "tests" / "test_generation.py",
    ROOT.parent / "design" / "fixture_profile_normative_resolutions.md",
    ROOT.parent / "design" / "new1_new2_resolution_record.md",
    ROOT.parent / "design" / "governance_metadata_schema_v2.md",
    ROOT.parent / "design" / "security_review.md",
    ROOT.parent / "design" / "threat_model.md",
    ROOT.parent / "design" / "abuse_replay_review.md",
    ROOT.parent / "design" / "backward_compatibility.md",
    ROOT.parent / "review" / "PROTOTYPE-BRANCH-MANIFEST-NOTICE.md",
]


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def write_bytes(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)


def write_json(path: Path, value: Any) -> None:
    write_bytes(path, canonical_json(value) + b"\n")


def safe_name(value: str) -> str:
    return "".join(ch if ch.isalnum() or ch in "-_" else "-" for ch in value)


def manifest_lines(paths: Iterable[Path], base: Path) -> bytes:
    rows = []
    for path in sorted(paths, key=lambda item: item.relative_to(base).as_posix()):
        rows.append(sha256_bytes(path.read_bytes()) + "  " + path.relative_to(base).as_posix())
    return ("\n".join(rows) + "\n").encode("utf-8")


def materialize_corpus() -> Tuple[Dict[str, Any], List[bytes], List[Dict[str, Any]], str]:
    corpus = build_representative_corpus()
    preliminary = normalize_corpus(corpus["raw_inputs"], corpus["source_event_refs"])
    final_raw = list(corpus["raw_inputs"])
    for index, item in enumerate(preliminary):
        if item["kind"] == "valid":
            final_raw[index] = canonical_json(item["record"])
    normalized = normalize_corpus(final_raw, corpus["source_event_refs"])
    replay = compute_replay_identifier(normalized, corpus["source_event_refs"])
    return corpus, final_raw, normalized, replay


def status_of(item: Mapping[str, Any]) -> str:
    return "valid" if item["kind"] == "valid" else item["envelope"]["normalization_status"]


def compute_advisory_output_digest(normalized: Sequence[Mapping[str, Any]]) -> str:
    """Bind ordered advisory outputs without treating the digest as authority."""
    outputs = [
        {
            "confidence_bucket": item["record"]["confidence_bucket"],
            "event_ref": item["record"]["event_ref"],
            "recommendation_category": item["record"]["recommendation_category"],
            "uncertainty_reason": item["record"]["uncertainty_reason"],
        }
        for item in normalized
        if item["kind"] == "valid"
    ]
    payload = {"ordered_valid_advisory_outputs": outputs}
    digest = sha256_bytes(
        b"olympus-governance-advisory-output/v2\n" + canonical_json(payload)
    )
    return "advisory-sha256-" + digest


def build_checks(
    corpus: Mapping[str, Any], final_raw: Sequence[bytes], normalized: Sequence[Dict[str, Any]], replay: str
) -> Tuple[Dict[str, bool], List[Dict[str, Any]]]:
    case_results = []
    for case, item in zip(corpus["cases"], normalized):
        actual = status_of(item)
        case_results.append(
            {
                "actual_status": actual,
                "expected_status": case["expected_status"],
                "kind": case["kind"],
                "name": case["name"],
                "pass": actual == case["expected_status"],
            }
        )

    valid_items = [item for item in normalized if item["kind"] == "valid"]
    quarantine_items = [item for item in normalized if item["kind"] == "quarantine"]
    canonical_ok = True
    provenance_ok = True
    for raw, item in zip(final_raw, normalized):
        if item["kind"] == "valid":
            canonical_ok = canonical_ok and raw == canonical_json(json.loads(raw.decode("utf-8")))
            provenance_ok = provenance_ok and (
                item["record"]["provenance_identifier"]
                == compute_provenance_identifier(item["record"])
            )
            try:
                validate_record(item["record"], corpus["source_event_refs"], replay)
            except ValueError:
                provenance_ok = False

    twice = normalize_corpus(final_raw, corpus["source_event_refs"])
    deterministic_ok = canonical_json(list(normalized)) == canonical_json(twice)
    replay_ok = replay == compute_replay_identifier(normalized, corpus["source_event_refs"])
    replay_ok = replay_ok and all(
        item["record"]["replay_identifier"] == replay for item in valid_items
    )
    replay_resists_order = replay != compute_replay_identifier(
        list(reversed(normalized)), corpus["source_event_refs"]
    )
    replay_resists_omission = replay != compute_replay_identifier(
        list(normalized[:-1]), corpus["source_event_refs"]
    )

    baseline = valid_items[0]["record"]
    output_change = copy.deepcopy(baseline)
    output_change["recommendation_category"] = "deny"
    output_change["confidence_bucket"] = "very_low"
    output_change["uncertainty_reason"] = "other_bounded"
    fact_change = copy.deepcopy(baseline)
    fact_change["policy_evaluation_result"] = "deny"
    anti_circular_ok = (
        compute_provenance_identifier(baseline)
        == compute_provenance_identifier(output_change)
        and compute_provenance_identifier(baseline)
        != compute_provenance_identifier(fact_change)
    )
    advisory_digest = compute_advisory_output_digest(normalized)
    advisory_mutation = copy.deepcopy(list(normalized))
    for item in advisory_mutation:
        if item["kind"] == "valid":
            item["record"]["recommendation_category"] = "deny"
            break
    advisory_output_digest_ok = (
        advisory_digest == compute_advisory_output_digest(normalized)
        and advisory_digest != compute_advisory_output_digest(advisory_mutation)
    )

    statuses = {row["name"]: row["actual_status"] for row in case_results}
    downgrade_ok = statuses["downgrade"] == "unknown_version"
    spoof_ok = all(
        statuses[name] == expected
        for name, expected in {
            "provenance_spoof": "invalid_provenance",
            "replay_spoof": "invalid_replay",
            "namespace_spoof": "invalid_additional_property",
            "circular_fact_source": "invalid_additional_property",
        }.items()
    )
    malformed_ok = all(
        row["pass"] for row in case_results if row["kind"] == "adversarial"
    )
    namespace_ok = (
        corpus["fixture_namespace"] == FIXTURE_NAMESPACE
        and all(
            item["envelope"]["fixture_namespace"] == FIXTURE_NAMESPACE
            for item in quarantine_items
        )
        and all("fixture_namespace" not in item["record"] for item in valid_items)
    )
    quarantine_digest_ok = all(
        item["provenance_identifier"].startswith("provq-")
        and item["envelope"]["raw_input_sha256"].startswith("sha256-")
        for item in quarantine_items
    )
    observe_matrix_ok = (
        statuses["observe_indeterminate"] == "valid"
        and statuses["allow_indeterminate"] == "invalid_cross_field"
        and statuses["policy_conflict"] == "invalid_cross_field"
    )
    coverage_ok = len(corpus["covered_action_classes"]) == 9 and len(normalized) == 28
    all_expected_ok = all(row["pass"] for row in case_results)

    checks = {
        "advisory_output_digest_integrity": advisory_output_digest_ok,
        "all_case_expectations": all_expected_ok,
        "anti_circular_provenance": anti_circular_ok,
        "canonical_serialization": canonical_ok,
        "deterministic_replay": deterministic_ok,
        "downgrade_resistance": downgrade_ok,
        "fixture_namespace_separation": namespace_ok,
        "governance_and_adversarial_coverage": coverage_ok,
        "malformed_input_handling": malformed_ok,
        "new_1_observe_indeterminate_matrix": observe_matrix_ok,
        "provenance_integrity": provenance_ok,
        "quarantine_digest_integrity": quarantine_digest_ok,
        "replay_integrity": replay_ok,
        "replay_order_resistance": replay_resists_order,
        "replay_omission_resistance": replay_resists_omission,
        "spoof_resistance": spoof_ok,
    }
    return checks, case_results


def markdown_report(title: str, summary: Mapping[str, Any], rows: Sequence[Mapping[str, Any]]) -> str:
    lines = ["# " + title, "", "**Scope:** Offline synthetic fixtures only; no production authority.", ""]
    for key, value in summary.items():
        lines.append("- **" + key.replace("_", " ").title() + ":** `" + str(value) + "`")
    lines += ["", "| Case | Expected | Actual | Result |", "|---|---|---|---|"]
    for row in rows:
        lines.append(
            "| `{}` | `{}` | `{}` | **{}** |".format(
                row["name"], row["expected_status"], row["actual_status"],
                "PASS" if row["pass"] else "FAIL",
            )
        )
    lines.append("")
    return "\n".join(lines)


def _generate_into(output: Path) -> Dict[str, Any]:
    if output.exists() or output.is_symlink():
        raise SystemExit("internal generation target must not exist")
    output.mkdir(parents=True)

    corpus, final_raw, normalized, replay = materialize_corpus()
    checks, case_results = build_checks(corpus, final_raw, normalized, replay)
    advisory_output_digest = compute_advisory_output_digest(normalized)
    valid_count = sum(item["kind"] == "valid" for item in normalized)
    quarantine_count = len(normalized) - valid_count

    index_rows = []
    raw_paths = []
    for ordinal, (case, raw, item) in enumerate(zip(corpus["cases"], final_raw, normalized)):
        suffix = ".json" if item["kind"] == "valid" else ".bin"
        relative = Path("fixtures/raw") / ("{:03d}-{}{}".format(ordinal, safe_name(case["name"]), suffix))
        path = output / relative
        write_bytes(path, raw)
        raw_paths.append(path)
        index_rows.append(
            {
                "actual_status": status_of(item),
                "expected_status": case["expected_status"],
                "input_sha256": "sha256-" + sha256_bytes(raw),
                "kind": case["kind"],
                "name": case["name"],
                "ordinal": ordinal,
                "path": relative.as_posix(),
            }
        )

    ledger_path = output / "fixtures" / "normalized-ledger.jsonl"
    write_bytes(ledger_path, b"\n".join(canonical_json(item) for item in normalized) + b"\n")
    source_path = output / "fixtures" / "synthetic-source-event-refs.json"
    write_json(source_path, {"event_refs": corpus["source_event_refs"], "fixture_namespace": FIXTURE_NAMESPACE})
    index_path = output / "fixtures" / "corpus-index.json"
    write_json(
        index_path,
        {
            "cases": index_rows,
            "fixture_namespace": FIXTURE_NAMESPACE,
            "item_count": len(normalized),
            "quarantine_count": quarantine_count,
            "replay_identifier": replay,
            "valid_count": valid_count,
        },
    )

    summary = {
        "advisory_output_digest": advisory_output_digest,
        "fixture_namespace": FIXTURE_NAMESPACE,
        "item_count": len(normalized),
        "quarantine_count": quarantine_count,
        "replay_identifier": replay,
        "valid_count": valid_count,
        "verdict": "FIXTURE_PROTOTYPE_READY" if all(checks.values()) else "NEEDS_REVISION",
    }
    reports = output / "reports"
    replay_evidence = {
        "advisory_output_digest": advisory_output_digest,
        "checks": {key: value for key, value in checks.items() if "replay" in key},
        "expected_item_count": len(normalized),
        "ordered_item_sha256": ["sha256-" + sha256_bytes(canonical_json(item)) for item in normalized],
        "replay_identifier": replay,
        "second_pass_identifier": compute_replay_identifier(
            normalize_corpus(final_raw, corpus["source_event_refs"]), corpus["source_event_refs"]
        ),
    }
    write_json(reports / "replay-evidence.json", replay_evidence)
    write_json(reports / "adversarial-validation-report.json", {"cases": case_results, "checks": checks})
    digest_report = {
        "advisory_output_digest": advisory_output_digest,
        "advisory_output_digest_domain": "olympus-governance-advisory-output/v2",
        "canonicalization_profile": "minimal UTF-8 JSON, sorted keys, NFC, no insignificant whitespace",
        "checks": checks,
        "domain_hash": "SHA-256(UTF8(domain) || 0x0a || canonical_JSON(payload))",
        "profile_digests": PROFILE_DIGESTS,
        "replay_identifier": replay,
    }
    write_json(reports / "digest-verification-report.json", digest_report)

    final_validation = {
        "advisory_output_digest": advisory_output_digest,
        "case_count": len(case_results),
        "check_count": len(checks),
        "checks": checks,
        "failed_checks": sorted(key for key, value in checks.items() if not value),
        "fixture_namespace": FIXTURE_NAMESPACE,
        "new_1_resolution": "single normative observe-only/indeterminate precedence matrix",
        "new_2_resolution": "deterministic namespace-separated malformed-input quarantine",
        "quarantine_count": quarantine_count,
        "replay_identifier": replay,
        "valid_count": valid_count,
        "verdict": summary["verdict"],
    }
    write_json(reports / "final-validation-report.json", final_validation)
    reproducibility = {
        "advisory_output_digest": advisory_output_digest,
        "canonical_serialization": checks["canonical_serialization"],
        "deterministic_normalization": checks["deterministic_replay"],
        "fixture_namespace": FIXTURE_NAMESPACE,
        "item_count": len(normalized),
        "recomputed_replay_identifier": compute_replay_identifier(
            normalize_corpus(final_raw, corpus["source_event_refs"]), corpus["source_event_refs"]
        ),
        "replay_identifier": replay,
        "source_manifest_scope_count": len(SOURCE_MANIFEST_PATHS),
        "verdict": "REPRODUCIBLE" if checks["deterministic_replay"] else "NOT_REPRODUCIBLE",
    }
    write_json(reports / "reproducibility-report.json", reproducibility)

    adversarial_rows = [row for row in case_results if row["kind"] == "adversarial"]
    write_bytes(
        reports / "adversarial-validation-report.md",
        markdown_report("Adversarial Validation Report", summary, adversarial_rows).encode("utf-8"),
    )
    write_bytes(
        reports / "replay-evidence.md",
        markdown_report("Deterministic Replay Evidence", summary, case_results).encode("utf-8"),
    )

    fixture_paths = raw_paths + [ledger_path, source_path, index_path]
    report_paths = sorted(reports.glob("*"))
    manifests = output / "manifests"
    write_bytes(manifests / "fixture-manifest.sha256", manifest_lines(fixture_paths, output))
    write_bytes(manifests / "evidence-manifest.sha256", manifest_lines(report_paths, output))

    source_rows = []
    repo_root = ROOT.parent
    for path in sorted(SOURCE_MANIFEST_PATHS, key=lambda item: item.relative_to(repo_root).as_posix()):
        source_rows.append(sha256_bytes(path.read_bytes()) + "  " + path.relative_to(repo_root).as_posix())
    write_bytes(manifests / "prototype-source-manifest.sha256", ("\n".join(source_rows) + "\n").encode("utf-8"))

    submanifest_digests = {
        name: "sha256-" + sha256_bytes((manifests / name).read_bytes())
        for name in ("fixture-manifest.sha256", "evidence-manifest.sha256", "prototype-source-manifest.sha256")
    }
    certification = {
        "anti_circular_certification": {
            "certification_digest_is_external": True,
            "evidence_manifests_exclude_certification": True,
            "provenance_excludes_recommendation_confidence_uncertainty_replay_and_provenance": True,
            "replay_item_digest_excludes_only_replay_identifier": True,
        },
        "advisory_output_digest": advisory_output_digest,
        "checks": checks,
        "fixture_namespace": FIXTURE_NAMESPACE,
        "olympus_activation": "DENIED",
        "limitations": [
            "offline synthetic fixture evidence only",
            "no Hermes integration",
            "no exporter modification",
            "no runtime, policy, contract, or production configuration modification",
            "no Olympus activation or production authority",
        ],
        "manifest_digests": submanifest_digests,
        "production_authority": "DENIED",
        "replay_identifier": replay,
        "verdict": summary["verdict"],
    }
    certification_path = reports / "fixture-certification-report.json"
    write_json(certification_path, certification)
    write_bytes(
        reports / "fixture-certification-report.md",
        ("# Fixture Certification Report\n\n"
         "**Verdict:** `{}`\n\n"
         "**Replay:** `{}`\n\n"
         "All {} checks passed. Certification is evidence-only, self-excluded from the evidence manifests, "
         "and grants no production authority.\n\n"
         "## Boundaries\n\n"
         "- No Hermes integration.\n- No exporter modification.\n- No runtime, policy, contract, or production configuration change.\n"
         "- Olympus activation: DENIED.\n- Production authority: DENIED.\n").format(
             summary["verdict"], replay, sum(checks.values())
         ).encode("utf-8"),
    )
    certification_paths = [certification_path, reports / "fixture-certification-report.md"]
    write_bytes(manifests / "certification.sha256", manifest_lines(certification_paths, output))

    all_non_manifest = [path for path in output.rglob("*") if path.is_file() and manifests not in path.parents]
    write_bytes(manifests / "combined-artifact-manifest.sha256", manifest_lines(all_non_manifest, output))
    root_manifest = {
        "certification_manifest_sha256": "sha256-" + sha256_bytes((manifests / "certification.sha256").read_bytes()),
        "combined_artifact_manifest_sha256": "sha256-" + sha256_bytes((manifests / "combined-artifact-manifest.sha256").read_bytes()),
        **submanifest_digests,
    }
    write_json(manifests / "manifest-root.json", root_manifest)
    write_bytes(
        manifests / "manifest-root.sha256",
        (sha256_bytes((manifests / "manifest-root.json").read_bytes()) + "  manifests/manifest-root.json\n").encode("utf-8"),
    )
    return {**summary, "checks": checks, "output": str(output)}


def _safe_output_path(output: Path) -> Path:
    output = output.expanduser()
    if output.is_symlink():
        raise SystemExit("refusing symlink output path")
    parent = output.parent.resolve(strict=True)
    safe = parent / output.name
    forbidden = {Path("/"), ROOT.resolve(), ROOT.parent.resolve()}
    if safe in forbidden or safe in ROOT.resolve().parents or safe in ROOT.parent.resolve().parents:
        raise SystemExit("refusing repository, filesystem-root, or ancestor output path")
    return safe


def _assert_replaceable_generated_tree(output: Path) -> None:
    if not output.is_dir() or output.is_symlink():
        raise SystemExit("replace target must be a real generated-artifact directory")
    required_markers = {
        output / "manifests" / "manifest-root.json",
        output / "reports" / "fixture-certification-report.json",
    }
    if not all(path.is_file() and not path.is_symlink() for path in required_markers):
        raise SystemExit("replace target lacks generated-artifact markers")
    if any(path.is_symlink() for path in output.rglob("*")):
        raise SystemExit("replace target contains symlinks")

    # Marker filenames alone are forgeable and are not ownership evidence.
    # Require the existing target to pass every structural/content check except
    # the source manifest itself, which may legitimately be stale when
    # --replace is used after source edits. Root binding still proves that the
    # old source manifest belongs to the old generated artifact.
    from verify_generated import verify

    verification = verify(output)
    manifest_results = verification.get("manifest_results")
    if not isinstance(manifest_results, Mapping):
        raise SystemExit("replace target is not a verified generated-artifact tree")
    structural_results = {
        name: result
        for name, result in manifest_results.items()
        if name != "prototype-source-manifest.sha256" and isinstance(result, Mapping)
    }
    if (
        verification.get("certification_error") is not None
        or verification.get("all_certification_checks_pass") is not True
        or len(structural_results) != len(manifest_results) - int("prototype-source-manifest.sha256" in manifest_results)
        or not structural_results
        or any(result.get("pass") is not True for result in structural_results.values())
    ):
        raise SystemExit("replace target is not a verified generated-artifact tree")


def generate(output: Path, replace: bool = False) -> Dict[str, Any]:
    """Generate into a sibling staging tree and atomically install it."""
    output = _safe_output_path(output)
    if output.exists():
        if not replace:
            raise SystemExit("output exists; pass --replace for this generated-only directory")
        _assert_replaceable_generated_tree(output)

    staging = Path(tempfile.mkdtemp(prefix=f".{output.name}.staging-", dir=output.parent))
    staging.rmdir()
    backup: Path | None = None
    try:
        result = _generate_into(staging)
        if output.exists():
            backup = Path(tempfile.mkdtemp(prefix=f".{output.name}.rollback-", dir=output.parent))
            backup.rmdir()
            os.replace(output, backup)
        os.replace(staging, output)
        if backup is not None:
            shutil.rmtree(backup)
        result["output"] = str(output)
        return result
    except BaseException:
        if staging.exists():
            shutil.rmtree(staging)
        if backup is not None and backup.exists() and not output.exists():
            os.replace(backup, output)
        raise


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=ROOT / "generated")
    parser.add_argument("--replace", action="store_true")
    args = parser.parse_args()
    result = generate(args.output, replace=args.replace)
    print(canonical_json(result).decode("utf-8"))
    if result["verdict"] != "FIXTURE_PROTOTYPE_READY":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
