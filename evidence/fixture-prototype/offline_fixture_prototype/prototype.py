"""Offline-only Olympus Schema v2 fixture validation primitives.

This module is intentionally standalone and standard-library only. It has no Hermes,
exporter, runtime, policy, contract, network, credential, or production imports.
"""

from __future__ import annotations

import copy
import hashlib
import json
import re
import unicodedata
from collections import Counter
from typing import Any, Dict, Iterable, List, Mapping, Sequence, Set, Tuple

FIXTURE_NAMESPACE = "olympus-fixture-v2-20260717"
MAX_JSON_DEPTH = 64
SCHEMA_VERSION = "olympus-governance-metadata/v2"
QUARANTINE_VERSION = "olympus-governance-quarantine/v2"
ZERO_REPLAY = "replay-" + "0" * 64


def _domain_hash(domain: str, payload: Mapping[str, Any]) -> str:
    return hashlib.sha256(domain.encode("utf-8") + b"\n" + canonical_json(payload)).hexdigest()


PROFILE_DIGESTS = {
    "canonicalization_profile_digest": "sha256-" + hashlib.sha256(b"olympus-canonical-json/v2").hexdigest(),
    "fixture_profile_digest": "sha256-" + hashlib.sha256(b"olympus-governance-fixture/v2").hexdigest(),
    "source_snapshot_digest": "sha256-" + hashlib.sha256(b"synthetic-source-snapshot/20260717").hexdigest(),
    "taxonomy_profile_digest": "sha256-" + hashlib.sha256(b"olympus-governance-taxonomies/v2").hexdigest(),
}

FIELD_ENUMS = {
    "schema_version": {SCHEMA_VERSION},
    "governance_action_class": {
        "read_only_observation", "local_reversible_mutation", "protected_mutation",
        "external_outbound", "financial_commitment", "identity_or_access_change",
        "destructive_action", "activation_or_authority_change", "unknown",
    },
    "target_classification": {
        "mock_only", "local_nonproduction", "production_protected", "external_system",
        "financial_system", "identity_or_secret_store", "family_or_calendar_commitment", "unknown",
    },
    "policy_evaluation_result": {"not_applicable", "pass", "deny", "indeterminate", "evaluation_error"},
    "contract_resolution_status": {
        "not_applicable", "resolved", "unknown_contract", "ambiguous_contract",
        "contract_invalid", "resolution_error",
    },
    "evidence_sufficiency": {"not_required", "sufficient", "insufficient", "indeterminate", "evidence_invalid"},
    "authority_requested": {"none", "tier_0", "tier_1", "tier_2", "tier_3", "unknown"},
    "authority_available": {"none", "tier_0", "tier_1", "tier_2", "tier_3", "unknown"},
    "authority_decision": {
        "not_applicable", "within_boundary", "approval_required", "denied", "indeterminate", "evaluation_error",
    },
    "schema_validation_status": {
        "valid", "invalid_missing_required", "invalid_type", "invalid_enum",
        "invalid_additional_property", "invalid_provenance", "unknown_version", "validation_error",
    },
    "recommendation_category": {
        "continue_read_only_observation", "allow_simulation_only", "deny", "request_human_approval",
        "request_additional_evidence", "abstain_insufficient_information", "escalate_policy_conflict", "invalid_input",
    },
    "confidence_bucket": {"very_low", "low", "medium", "high", "very_high", "not_scored"},
    "uncertainty_reason": {
        "none", "missing_governance_metadata", "policy_conflict", "unknown_contract",
        "insufficient_evidence", "authority_indeterminate", "schema_invalid",
        "multiple_conditions", "other_bounded", "not_scored",
    },
}

REQUIRED_FIELDS = (
    "schema_version", "event_ref", "governance_action_class", "target_classification",
    "policy_evaluation_result", "policy_conflict_indicator", "contract_resolution_status",
    "evidence_sufficiency", "authority_requested", "authority_available", "authority_decision",
    "schema_validation_status", "recommendation_category", "confidence_bucket",
    "uncertainty_reason", "replay_identifier", "provenance_identifier",
)
FACT_FIELDS = (
    "governance_action_class", "target_classification", "policy_evaluation_result",
    "policy_conflict_indicator", "contract_resolution_status", "evidence_sufficiency",
    "authority_requested", "authority_available", "authority_decision", "schema_validation_status",
)
INDETERMINATE_VALUES = {
    "unknown", "indeterminate", "evaluation_error", "unknown_contract", "ambiguous_contract",
    "contract_invalid", "resolution_error", "insufficient", "evidence_invalid",
}
FAIL_CLOSED = {
    "deny", "request_human_approval", "request_additional_evidence",
    "abstain_insufficient_information", "escalate_policy_conflict", "invalid_input",
}
EVENT_RE = re.compile(r"^" + re.escape(FIXTURE_NAMESPACE) + r"-[a-f0-9]{24}$")
PROV_RE = re.compile(r"^prov-[a-f0-9]{64}$")
REPLAY_RE = re.compile(r"^replay-[a-f0-9]{64}$")
TIER = {"none": 0, "tier_0": 1, "tier_1": 2, "tier_2": 3, "tier_3": 4}


class ValidationFailure(ValueError):
    def __init__(self, status: str, message: str):
        super().__init__(message)
        self.status = status


def _assert_nfc(value: Any) -> None:
    if isinstance(value, str):
        if unicodedata.normalize("NFC", value) != value:
            raise ValueError("all strings must already be Unicode NFC")
    elif isinstance(value, Mapping):
        for key, item in value.items():
            _assert_nfc(key)
            _assert_nfc(item)
    elif isinstance(value, (list, tuple)):
        for item in value:
            _assert_nfc(item)


def canonical_json(value: Any) -> bytes:
    """Return deterministic minimal UTF-8 JSON bytes after enforcing NFC."""
    _assert_nfc(value)
    return json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False,
    ).encode("utf-8")


def compute_provenance_identifier(
    record: Mapping[str, Any],
    profile_digests: Mapping[str, str] = PROFILE_DIGESTS,
    fixture_namespace: str = FIXTURE_NAMESPACE,
) -> str:
    payload = {
        "event_ref": record["event_ref"],
        "facts": {field: record[field] for field in FACT_FIELDS},
        "fixture_namespace": fixture_namespace,
        "profile_digests": dict(profile_digests),
        "schema_version": record["schema_version"],
    }
    return "prov-" + _domain_hash("olympus-governance-provenance/v2", payload)


def make_record(event_ref: str, **overrides: Any) -> Dict[str, Any]:
    """Create a deterministic synthetic record; callers may override fields for tests."""
    record = {
        "schema_version": SCHEMA_VERSION,
        "event_ref": event_ref,
        "governance_action_class": "read_only_observation",
        "target_classification": "mock_only",
        "policy_evaluation_result": "pass",
        "policy_conflict_indicator": False,
        "contract_resolution_status": "resolved",
        "evidence_sufficiency": "sufficient",
        "authority_requested": "tier_0",
        "authority_available": "tier_0",
        "authority_decision": "within_boundary",
        "schema_validation_status": "valid",
        "recommendation_category": "continue_read_only_observation",
        "confidence_bucket": "very_high",
        "uncertainty_reason": "none",
        "replay_identifier": ZERO_REPLAY,
        "provenance_identifier": "prov-" + "0" * 64,
    }
    record.update(overrides)
    if "provenance_identifier" not in overrides:
        record["provenance_identifier"] = compute_provenance_identifier(record)
    return record


def _source_count(source_event_refs: Iterable[str], event_ref: str) -> int:
    if isinstance(source_event_refs, set):
        return 1 if event_ref in source_event_refs else 0
    return sum(1 for item in source_event_refs if item == event_ref)


def _validated_source_refs(source_event_refs: Iterable[str]) -> List[str]:
    refs = list(source_event_refs)
    if not refs:
        raise ValidationFailure("invalid_synthetic_source", "synthetic source must not be empty")
    if any(not isinstance(ref, str) or not EVENT_RE.fullmatch(ref) for ref in refs):
        raise ValidationFailure("invalid_synthetic_source", "every source event_ref must use the exact fixture namespace")
    if len(refs) != len(set(refs)):
        raise ValidationFailure("invalid_synthetic_source", "synthetic source event_refs must be unique")
    return refs


def validate_record(
    record: Mapping[str, Any],
    source_event_refs: Iterable[str],
    expected_replay: str = "",
) -> None:
    """Strictly validate one v2 record in deterministic NEW-2 order."""
    source_event_refs = _validated_source_refs(source_event_refs)
    if not isinstance(record, dict):
        raise ValidationFailure("invalid_top_level", "top level must be an object")
    if record.get("schema_version") not in (None, SCHEMA_VERSION):
        raise ValidationFailure("unknown_version", "unsupported schema version")
    missing = sorted(set(REQUIRED_FIELDS) - set(record))
    if missing:
        raise ValidationFailure("invalid_missing_required", "missing required: " + ",".join(missing))
    extra = sorted(set(record) - set(REQUIRED_FIELDS))
    if extra:
        raise ValidationFailure("invalid_additional_property", "additional properties: " + ",".join(extra))
    for field, value in record.items():
        if field == "policy_conflict_indicator":
            if not isinstance(value, bool) and value != "unknown":
                raise ValidationFailure("invalid_type", "policy_conflict_indicator must be boolean or unknown")
        elif not isinstance(value, str):
            raise ValidationFailure("invalid_type", field + " must be a string")
    try:
        _assert_nfc(record)
    except ValueError as exc:
        raise ValidationFailure("validation_error", str(exc))
    for field, allowed in FIELD_ENUMS.items():
        if record[field] not in allowed:
            raise ValidationFailure("invalid_enum", "invalid enum for " + field)
    if not EVENT_RE.fullmatch(record["event_ref"]):
        raise ValidationFailure("invalid_identifier", "invalid event_ref")
    if not PROV_RE.fullmatch(record["provenance_identifier"]):
        raise ValidationFailure("invalid_identifier", "invalid provenance identifier")
    if not REPLAY_RE.fullmatch(record["replay_identifier"]):
        raise ValidationFailure("invalid_identifier", "invalid replay identifier")
    if _source_count(source_event_refs, record["event_ref"]) != 1:
        raise ValidationFailure("invalid_cross_field", "event_ref must exist exactly once in synthetic source")

    recommendation = record["recommendation_category"]
    policy = record["policy_evaluation_result"]
    conflict = record["policy_conflict_indicator"]
    contract = record["contract_resolution_status"]
    evidence = record["evidence_sufficiency"]
    authority_decision = record["authority_decision"]
    uncertainty = record["uncertainty_reason"]

    if conflict is True and policy not in {"deny", "indeterminate"}:
        raise ValidationFailure("invalid_cross_field", "policy conflict cannot coexist with pass")

    fact_values = [record[field] for field in FACT_FIELDS]
    has_indeterminate = any(value in INDETERMINATE_VALUES for value in fact_values)
    evidence_indeterminate = evidence in {"insufficient", "indeterminate", "evidence_invalid"}
    observe_rule_one = (
        record["governance_action_class"] == "read_only_observation"
        and record["target_classification"] in {"mock_only", "local_nonproduction"}
        and record["schema_validation_status"] == "valid"
        and policy not in {"deny", "evaluation_error"}
        and conflict is not True
        and contract not in {"contract_invalid", "resolution_error"}
    )
    allow_requirements = (
        record["governance_action_class"] != "unknown"
        and record["governance_action_class"] != "read_only_observation"
        and record["target_classification"] in {"mock_only", "local_nonproduction"}
        and record["schema_validation_status"] == "valid"
        and policy == "pass"
        and conflict is False
        and contract == "resolved"
        and evidence == "sufficient"
        and record["authority_requested"] in TIER
        and record["authority_available"] in TIER
        and authority_decision == "within_boundary"
        and not has_indeterminate
    )

    # NEW-1 Rules 1-7 define one exact recommendation for each valid fact state.
    # Explicit fail-closed outcomes take precedence over provisional observation.
    if record["schema_validation_status"] != "valid":
        expected_recommendation = "invalid_input"
    elif conflict is True:
        expected_recommendation = "escalate_policy_conflict"
    elif policy == "deny":
        expected_recommendation = "deny"
    elif evidence_indeterminate and not observe_rule_one:
        expected_recommendation = "request_additional_evidence"
    elif authority_decision == "approval_required":
        expected_recommendation = "request_human_approval"
    elif authority_decision == "denied":
        expected_recommendation = "deny"
    elif has_indeterminate:
        expected_recommendation = (
            "continue_read_only_observation" if observe_rule_one
            else "abstain_insufficient_information"
        )
    elif observe_rule_one:
        expected_recommendation = "continue_read_only_observation"
    elif allow_requirements:
        expected_recommendation = "allow_simulation_only"
    else:
        raise ValidationFailure("invalid_cross_field", "facts do not map to a normative recommendation")

    if recommendation != expected_recommendation:
        if conflict is True:
            raise ValidationFailure("invalid_cross_field", "policy conflict requires escalate_policy_conflict")
        if record["governance_action_class"] == "unknown" or record["target_classification"] == "unknown":
            raise ValidationFailure("invalid_cross_field", "unknown action or target requires abstention")
        raise ValidationFailure(
            "invalid_cross_field",
            f"recommendation must be {expected_recommendation} for the supplied facts",
        )

    uncertainty_conditions = []
    if record["authority_requested"] == "unknown" or record["authority_available"] == "unknown" or authority_decision in {"indeterminate", "evaluation_error"}:
        uncertainty_conditions.append("authority_indeterminate")
    if policy in {"indeterminate", "evaluation_error"} or conflict == "unknown":
        uncertainty_conditions.append("policy_conflict")
    if contract in {"unknown_contract", "ambiguous_contract", "contract_invalid", "resolution_error"}:
        uncertainty_conditions.append("unknown_contract")
    if evidence_indeterminate:
        uncertainty_conditions.append("insufficient_evidence")
    if record["governance_action_class"] == "unknown" or record["target_classification"] == "unknown":
        uncertainty_conditions.append("missing_governance_metadata")

    if record["schema_validation_status"] != "valid":
        expected_uncertainty = "schema_invalid"
    elif conflict is True:
        expected_uncertainty = "policy_conflict"
    elif len(uncertainty_conditions) > 1:
        expected_uncertainty = "multiple_conditions"
    elif uncertainty_conditions:
        expected_uncertainty = uncertainty_conditions[0]
    else:
        expected_uncertainty = "none"
    if uncertainty != expected_uncertainty:
        raise ValidationFailure(
            "invalid_cross_field",
            f"uncertainty_reason must be {expected_uncertainty} for the supplied facts",
        )

    if authority_decision == "within_boundary":
        requested = record["authority_requested"]
        available = record["authority_available"]
        if requested not in TIER or available not in TIER or TIER[available] < TIER[requested]:
            raise ValidationFailure("invalid_cross_field", "within_boundary requires sufficient known authority")

    expected_provenance = compute_provenance_identifier(record)
    if record["provenance_identifier"] != expected_provenance:
        raise ValidationFailure("invalid_provenance", "provenance mismatch")
    if expected_replay and record["replay_identifier"] != expected_replay:
        raise ValidationFailure("invalid_replay", "replay mismatch")


class _DuplicateKey(Exception):
    pass


def _no_duplicate_pairs(pairs: Sequence[Tuple[str, Any]]) -> Dict[str, Any]:
    result: Dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise _DuplicateKey(key)
        result[key] = value
    return result


def _quarantine(raw: bytes, ordinal: int, status: str) -> Dict[str, Any]:
    raw_digest = hashlib.sha256(raw).hexdigest()
    envelope = {
        "event_ref_sentinel": "quarantine-" + raw_digest[:24],
        "fact_sentinel": "unavailable_due_to_malformed_input",
        "fixture_namespace": FIXTURE_NAMESPACE,
        "input_ordinal": ordinal,
        "normalization_status": status,
        "quarantine_schema_version": QUARANTINE_VERSION,
        "raw_input_length": len(raw),
        "raw_input_sha256": "sha256-" + raw_digest,
        "recommendation_sentinel": "invalid_input",
    }
    payload = {"envelope": envelope, "profile_digests": PROFILE_DIGESTS}
    provenance = "provq-" + _domain_hash("olympus-governance-quarantine-provenance/v2", payload)
    return {"kind": "quarantine", "envelope": envelope, "provenance_identifier": provenance}


def _json_depth_exceeds_limit(text: str, limit: int) -> bool:
    """Scan JSON structure without recursion; ignore braces inside strings."""
    depth = 0
    in_string = False
    escaped = False
    for character in text:
        if in_string:
            if escaped:
                escaped = False
            elif character == "\\":
                escaped = True
            elif character == '"':
                in_string = False
            continue
        if character == '"':
            in_string = True
        elif character in "[{":
            depth += 1
            if depth > limit:
                return True
        elif character in "]}":
            depth = max(0, depth - 1)
    return False


def normalize_input(raw: bytes, ordinal: int, source_event_refs: Iterable[str]) -> Dict[str, Any]:
    """Normalize raw bytes into exactly one valid record or quarantine item."""
    try:
        text = raw.decode("utf-8", errors="strict")
    except UnicodeDecodeError:
        return _quarantine(raw, ordinal, "invalid_utf8")
    if _json_depth_exceeds_limit(text, MAX_JSON_DEPTH):
        return _quarantine(raw, ordinal, "invalid_json")
    try:
        parsed = json.loads(text, object_pairs_hook=_no_duplicate_pairs)
    except _DuplicateKey:
        return _quarantine(raw, ordinal, "duplicate_key")
    except (json.JSONDecodeError, ValueError, RecursionError):
        return _quarantine(raw, ordinal, "invalid_json")
    try:
        if raw != canonical_json(parsed):
            return _quarantine(raw, ordinal, "validation_error")
    except (TypeError, ValueError, RecursionError):
        return _quarantine(raw, ordinal, "validation_error")
    if not isinstance(parsed, dict):
        return _quarantine(raw, ordinal, "invalid_top_level")
    try:
        validate_record(parsed, source_event_refs)
    except ValidationFailure as exc:
        return _quarantine(raw, ordinal, exc.status)
    return {"kind": "valid", "record": parsed}


def _normalized_item_digest(item: Mapping[str, Any]) -> str:
    if item["kind"] == "valid":
        payload_record = dict(item["record"])
        payload_record.pop("replay_identifier", None)
        payload = {"kind": "valid", "record_without_replay": payload_record}
    else:
        payload = {
            "kind": "quarantine",
            "envelope": item["envelope"],
            "provenance_identifier": item["provenance_identifier"],
        }
    return "sha256-" + _domain_hash("olympus-governance-normalized-item/v2", payload)


def compute_replay_identifier(
    normalized_items: Sequence[Mapping[str, Any]], source_event_refs: Iterable[str]
) -> str:
    source_list = sorted(_validated_source_refs(source_event_refs))
    source_digest = "sha256-" + _domain_hash(
        "olympus-governance-synthetic-source/v2", {"event_refs": source_list}
    )
    payload = {
        "expected_item_count": len(normalized_items),
        "fixture_namespace": FIXTURE_NAMESPACE,
        "normalized_item_digests": [_normalized_item_digest(item) for item in normalized_items],
        "profile_digests": PROFILE_DIGESTS,
        "source_stream_digest": source_digest,
    }
    return "replay-" + _domain_hash("olympus-governance-replay/v2", payload)


def normalize_corpus(raw_inputs: Sequence[bytes], source_event_refs: Iterable[str]) -> List[Dict[str, Any]]:
    source_refs = _validated_source_refs(source_event_refs)
    items = [normalize_input(raw, ordinal, source_refs) for ordinal, raw in enumerate(raw_inputs)]
    supplied_counts = Counter(
        item["record"]["replay_identifier"]
        for item in items
        if item["kind"] == "valid" and item["record"]["replay_identifier"] != ZERO_REPLAY
    )
    consensus_replay = ""
    if supplied_counts:
        candidate, count = supplied_counts.most_common(1)[0]
        if count >= 2:
            consensus_replay = candidate
    for ordinal, (raw, item) in enumerate(zip(raw_inputs, items)):
        if item["kind"] != "valid":
            continue
        supplied = item["record"]["replay_identifier"]
        if supplied != ZERO_REPLAY and (not consensus_replay or supplied != consensus_replay):
            items[ordinal] = _quarantine(raw, ordinal, "invalid_replay")
    final_replay = compute_replay_identifier(items, source_refs)
    if consensus_replay and consensus_replay != final_replay:
        for ordinal, (raw, item) in enumerate(zip(raw_inputs, items)):
            if item["kind"] == "valid" and item["record"]["replay_identifier"] == consensus_replay:
                items[ordinal] = _quarantine(raw, ordinal, "invalid_replay")
        final_replay = compute_replay_identifier(items, source_refs)
    for item in items:
        if item["kind"] == "valid" and item["record"]["replay_identifier"] == ZERO_REPLAY:
            item["record"]["replay_identifier"] = final_replay
    return items


def _event_ref(number: int) -> str:
    return FIXTURE_NAMESPACE + "-" + format(number, "024x")


def _scenario_record(number: int, **overrides: Any) -> Dict[str, Any]:
    return make_record(_event_ref(number), **overrides)


def build_representative_corpus() -> Dict[str, Any]:
    """Build deterministic valid scenarios plus adversarial raw inputs."""
    valid_specs = [
        ("read_only_observation", {}),
        ("local_reversible_mutation", {"governance_action_class": "local_reversible_mutation", "target_classification": "local_nonproduction", "recommendation_category": "allow_simulation_only"}),
        ("protected_mutation", {"governance_action_class": "protected_mutation", "target_classification": "production_protected", "authority_requested": "tier_2", "authority_available": "tier_0", "authority_decision": "approval_required", "recommendation_category": "request_human_approval", "confidence_bucket": "high"}),
        ("external_outbound", {"governance_action_class": "external_outbound", "target_classification": "external_system", "policy_evaluation_result": "deny", "authority_decision": "denied", "recommendation_category": "deny", "confidence_bucket": "high"}),
        ("financial_commitment", {"governance_action_class": "financial_commitment", "target_classification": "financial_system", "policy_evaluation_result": "deny", "authority_decision": "denied", "recommendation_category": "deny", "confidence_bucket": "high"}),
        ("identity_or_access_change", {"governance_action_class": "identity_or_access_change", "target_classification": "identity_or_secret_store", "authority_requested": "tier_3", "authority_available": "tier_0", "authority_decision": "approval_required", "recommendation_category": "request_human_approval", "confidence_bucket": "high"}),
        ("destructive_action", {"governance_action_class": "destructive_action", "target_classification": "production_protected", "policy_evaluation_result": "deny", "authority_decision": "denied", "recommendation_category": "deny", "confidence_bucket": "high"}),
        ("activation_or_authority_change", {"governance_action_class": "activation_or_authority_change", "target_classification": "production_protected", "authority_requested": "tier_3", "authority_available": "tier_0", "authority_decision": "approval_required", "recommendation_category": "request_human_approval", "confidence_bucket": "high"}),
        ("unknown", {"governance_action_class": "unknown", "target_classification": "unknown", "authority_requested": "unknown", "authority_available": "unknown", "authority_decision": "indeterminate", "recommendation_category": "abstain_insufficient_information", "confidence_bucket": "very_low", "uncertainty_reason": "multiple_conditions"}),
        ("observe_indeterminate", {"policy_evaluation_result": "indeterminate", "recommendation_category": "continue_read_only_observation", "confidence_bucket": "low", "uncertainty_reason": "policy_conflict"}),
        ("policy_conflict_valid", {"policy_evaluation_result": "indeterminate", "policy_conflict_indicator": True, "recommendation_category": "escalate_policy_conflict", "confidence_bucket": "low", "uncertainty_reason": "policy_conflict"}),
        ("contract_unknown_valid", {"contract_resolution_status": "unknown_contract", "recommendation_category": "continue_read_only_observation", "confidence_bucket": "low", "uncertainty_reason": "unknown_contract"}),
        ("evidence_insufficient_valid", {"governance_action_class": "protected_mutation", "target_classification": "production_protected", "evidence_sufficiency": "insufficient", "authority_decision": "approval_required", "recommendation_category": "request_additional_evidence", "confidence_bucket": "low", "uncertainty_reason": "insufficient_evidence"}),
        ("authority_indeterminate_valid", {"governance_action_class": "protected_mutation", "target_classification": "production_protected", "authority_available": "unknown", "authority_decision": "indeterminate", "recommendation_category": "abstain_insufficient_information", "confidence_bucket": "low", "uncertainty_reason": "authority_indeterminate"}),
    ]
    records: List[Dict[str, Any]] = []
    cases: List[Dict[str, Any]] = []
    for number, (name, overrides) in enumerate(valid_specs, start=1):
        record = _scenario_record(number, **overrides)
        records.append(record)
        cases.append({"name": name, "kind": "valid", "expected_status": "valid"})
    source_refs = [record["event_ref"] for record in records]
    raw_inputs = [canonical_json(record) for record in records]

    adversarial: List[Tuple[str, bytes, str]] = []
    base = _scenario_record(101)
    source_refs.append(base["event_ref"])

    def mutated(**changes: Any) -> bytes:
        record = copy.deepcopy(base)
        record.update(changes)
        if "provenance_identifier" not in changes:
            record["provenance_identifier"] = compute_provenance_identifier(record)
        return canonical_json(record)

    adversarial.append(("downgrade", mutated(schema_version="olympus-governance-metadata/v1"), "unknown_version"))
    adversarial.append(("provenance_spoof", mutated(provenance_identifier="prov-" + "1" * 64), "invalid_provenance"))
    adversarial.append(("replay_spoof", mutated(replay_identifier="replay-" + "2" * 64), "invalid_replay"))
    adversarial.append(("duplicate_key", b'{"schema_version":"olympus-governance-metadata/v2","schema_version":"x"}', "duplicate_key"))
    adversarial.append(("invalid_utf8", b"\xff\xfe\x80", "invalid_utf8"))
    adversarial.append(("invalid_json", b'{"schema_version":', "invalid_json"))
    adversarial.append(("extra_field", mutated(forbidden_extra="x"), "invalid_additional_property"))
    adversarial.append(("unknown_enum", mutated(policy_evaluation_result="approve"), "invalid_enum"))
    adversarial.append(("invalid_identifier", mutated(event_ref="outside-NOT-AN-ID"), "invalid_identifier"))
    adversarial.append(("allow_indeterminate", mutated(governance_action_class="local_reversible_mutation", target_classification="local_nonproduction", policy_evaluation_result="indeterminate", recommendation_category="allow_simulation_only", uncertainty_reason="policy_conflict"), "invalid_cross_field"))
    adversarial.append(("policy_conflict", mutated(policy_evaluation_result="indeterminate", policy_conflict_indicator=True, recommendation_category="continue_read_only_observation", uncertainty_reason="policy_conflict"), "invalid_cross_field"))
    adversarial.append(("circular_fact_source", mutated(fact_source="olympus_recommendation"), "invalid_additional_property"))
    adversarial.append(("namespace_spoof", mutated(fixture_namespace="production"), "invalid_additional_property"))
    adversarial.append(("invalid_top_level", b"[]", "invalid_top_level"))

    for name, raw, expected in adversarial:
        raw_inputs.append(raw)
        cases.append({"name": name, "kind": "adversarial", "expected_status": expected})
    return {
        "fixture_namespace": FIXTURE_NAMESPACE,
        "raw_inputs": raw_inputs,
        "source_event_refs": source_refs,
        "cases": cases,
        "covered_action_classes": [name for name, _ in valid_specs[:9]],
        "covered_adversarial_classes": [name for name, _, _ in adversarial] + ["observe_indeterminate"],
    }
