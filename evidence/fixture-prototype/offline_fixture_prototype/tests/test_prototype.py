import copy
import json
import unittest

from prototype import (
    FIXTURE_NAMESPACE,
    MAX_JSON_DEPTH,
    PROFILE_DIGESTS,
    SCHEMA_VERSION,
    ValidationFailure,
    build_representative_corpus,
    canonical_json,
    compute_provenance_identifier,
    compute_replay_identifier,
    make_record,
    normalize_corpus,
    normalize_input,
    validate_record,
)


def fixture_ref(number: int) -> str:
    return FIXTURE_NAMESPACE + "-" + format(number, "024x")


class CanonicalSerializationTests(unittest.TestCase):
    def test_canonical_json_sorts_keys_and_has_no_whitespace(self):
        value = {"z": "last", "a": True, "m": "middle"}
        self.assertEqual(canonical_json(value), b'{"a":true,"m":"middle","z":"last"}')

    def test_canonical_json_rejects_non_nfc_strings(self):
        with self.assertRaisesRegex(ValueError, "NFC"):
            canonical_json({"text": "e\u0301"})


class NewOneDecisionRuleTests(unittest.TestCase):
    def test_exact_recommendation_matrix_rejects_semantically_wrong_fail_closed_categories(self):
        cases = (
            ({"policy_evaluation_result": "indeterminate", "governance_action_class": "protected_mutation", "target_classification": "production_protected", "recommendation_category": "deny", "uncertainty_reason": "policy_conflict"}, "recommendation"),
            ({"policy_evaluation_result": "pass", "recommendation_category": "invalid_input"}, "recommendation"),
            ({"policy_evaluation_result": "pass", "recommendation_category": "escalate_policy_conflict"}, "recommendation"),
        )
        for index, (overrides, message) in enumerate(cases, 200):
            with self.subTest(overrides=overrides):
                record = make_record(event_ref=fixture_ref(index), **overrides)
                with self.assertRaisesRegex(ValidationFailure, message):
                    validate_record(record, {record["event_ref"]})

    def test_exact_uncertainty_reason_is_enforced(self):
        record = make_record(
            event_ref=fixture_ref(203),
            policy_evaluation_result="indeterminate",
            uncertainty_reason="other_bounded",
            confidence_bucket="low",
        )
        with self.assertRaisesRegex(ValidationFailure, "uncertainty"):
            validate_record(record, {record["event_ref"]})

    def test_multiple_simultaneous_uncertainties_require_multiple_conditions(self):
        record = make_record(
            event_ref=fixture_ref(205),
            governance_action_class="protected_mutation",
            target_classification="production_protected",
            policy_evaluation_result="indeterminate",
            contract_resolution_status="unknown_contract",
            recommendation_category="abstain_insufficient_information",
            uncertainty_reason="policy_conflict",
            confidence_bucket="low",
        )
        with self.assertRaisesRegex(ValidationFailure, "multiple_conditions"):
            validate_record(record, {record["event_ref"]})

    def test_policy_conflict_precedes_policy_deny(self):
        record = make_record(
            event_ref=fixture_ref(204),
            policy_evaluation_result="deny",
            policy_conflict_indicator=True,
            recommendation_category="escalate_policy_conflict",
            uncertainty_reason="policy_conflict",
            confidence_bucket="low",
        )
        validate_record(record, {record["event_ref"]})

    def test_observe_only_indeterminate_policy_is_provisional_and_valid(self):
        record = make_record(
            event_ref=fixture_ref(1),
            policy_evaluation_result="indeterminate",
            uncertainty_reason="policy_conflict",
            confidence_bucket="low",
        )
        validate_record(record, {record["event_ref"]})

    def test_allow_simulation_rejects_every_indeterminate_fact(self):
        cases = {
            "governance_action_class": "unknown",
            "target_classification": "unknown",
            "policy_evaluation_result": "indeterminate",
            "policy_conflict_indicator": "unknown",
            "contract_resolution_status": "unknown_contract",
            "evidence_sufficiency": "indeterminate",
            "authority_requested": "unknown",
            "authority_available": "unknown",
            "authority_decision": "indeterminate",
        }
        for field, value in cases.items():
            with self.subTest(field=field):
                overrides = {
                    "governance_action_class": "local_reversible_mutation",
                    "target_classification": "local_nonproduction",
                    "recommendation_category": "allow_simulation_only",
                }
                overrides[field] = value
                record = make_record(event_ref=fixture_ref(2), **overrides)
                with self.assertRaises(ValidationFailure):
                    validate_record(record, {record["event_ref"]})

    def test_explicit_deny_precedes_observe_only(self):
        record = make_record(
            event_ref=fixture_ref(3),
            policy_evaluation_result="deny",
            recommendation_category="continue_read_only_observation",
            uncertainty_reason="policy_conflict",
        )
        with self.assertRaisesRegex(ValidationFailure, "deny"):
            validate_record(record, {record["event_ref"]})

    def test_insufficient_evidence_requires_additional_evidence(self):
        record = make_record(
            event_ref=fixture_ref(101),
            governance_action_class="protected_mutation",
            target_classification="production_protected",
            evidence_sufficiency="insufficient",
            authority_decision="approval_required",
            recommendation_category="abstain_insufficient_information",
            confidence_bucket="low",
            uncertainty_reason="insufficient_evidence",
        )
        with self.assertRaisesRegex(ValidationFailure, "evidence"):
            validate_record(record, {record["event_ref"]})

    def test_approval_required_requires_human_approval(self):
        record = make_record(
            event_ref=fixture_ref(102),
            governance_action_class="protected_mutation",
            target_classification="production_protected",
            authority_requested="tier_2",
            authority_available="tier_0",
            authority_decision="approval_required",
            recommendation_category="abstain_insufficient_information",
            confidence_bucket="low",
            uncertainty_reason="authority_indeterminate",
        )
        with self.assertRaisesRegex(ValidationFailure, "approval"):
            validate_record(record, {record["event_ref"]})

    def test_unknown_action_or_target_requires_abstention(self):
        for field in ("governance_action_class", "target_classification"):
            with self.subTest(field=field):
                record = make_record(
                    event_ref=fixture_ref(103),
                    **{field: "unknown"},
                    recommendation_category="request_human_approval",
                    confidence_bucket="low",
                    uncertainty_reason="missing_governance_metadata",
                )
                with self.assertRaisesRegex(ValidationFailure, "unknown"):
                    validate_record(record, {record["event_ref"]})

    def test_indeterminate_policy_cannot_use_allow_like_category(self):
        record = make_record(
            event_ref=fixture_ref(104),
            governance_action_class="local_reversible_mutation",
            target_classification="local_nonproduction",
            policy_evaluation_result="indeterminate",
            recommendation_category="allow_simulation_only",
            uncertainty_reason="policy_conflict",
        )
        with self.assertRaises(ValidationFailure):
            validate_record(record, {record["event_ref"]})

    def test_policy_conflict_requires_explicit_escalation(self):
        record = make_record(
            event_ref=fixture_ref(105),
            policy_evaluation_result="indeterminate",
            policy_conflict_indicator=True,
            recommendation_category="deny",
            uncertainty_reason="policy_conflict",
        )
        with self.assertRaisesRegex(ValidationFailure, "policy conflict"):
            validate_record(record, {record["event_ref"]})

    def test_malformed_schema_is_quarantined(self):
        event_ref = fixture_ref(106)
        raw = canonical_json({"schema_version": SCHEMA_VERSION, "fixture_namespace": FIXTURE_NAMESPACE})
        result = normalize_input(raw, 106, {event_ref})
        self.assertEqual(result["kind"], "quarantine")
        self.assertEqual(result["envelope"]["normalization_status"], "invalid_missing_required")

    def test_unverifiable_authority_and_evidence_reject_allow_like_categories(self):
        cases = (
            {"authority_requested": "unknown", "recommendation_category": "allow_simulation_only"},
            {"authority_available": "unknown", "recommendation_category": "allow_simulation_only"},
            {"authority_decision": "evaluation_error", "recommendation_category": "request_human_approval"},
            {"evidence_sufficiency": "evidence_invalid", "recommendation_category": "abstain_insufficient_information"},
        )
        for index, overrides in enumerate(cases, 107):
            with self.subTest(overrides=overrides):
                record = make_record(
                    event_ref=fixture_ref(index),
                    governance_action_class="local_reversible_mutation",
                    target_classification="local_nonproduction",
                    confidence_bucket="low",
                    uncertainty_reason=(
                        "insufficient_evidence" if "evidence_sufficiency" in overrides else "authority_indeterminate"
                    ),
                    **overrides,
                )
                with self.assertRaises(ValidationFailure):
                    validate_record(record, {record["event_ref"]})


class DigestIntegrityTests(unittest.TestCase):
    def test_provenance_excludes_olympus_outputs_but_binds_facts(self):
        record = make_record(event_ref=fixture_ref(4))
        baseline = compute_provenance_identifier(record, PROFILE_DIGESTS, FIXTURE_NAMESPACE)
        changed_output = copy.deepcopy(record)
        changed_output["recommendation_category"] = "deny"
        changed_output["confidence_bucket"] = "very_low"
        changed_output["uncertainty_reason"] = "other_bounded"
        self.assertEqual(baseline, compute_provenance_identifier(changed_output, PROFILE_DIGESTS, FIXTURE_NAMESPACE))
        changed_fact = copy.deepcopy(record)
        changed_fact["policy_evaluation_result"] = "deny"
        self.assertNotEqual(baseline, compute_provenance_identifier(changed_fact, PROFILE_DIGESTS, FIXTURE_NAMESPACE))

    def test_replay_binds_order_and_every_normalized_item(self):
        corpus = build_representative_corpus()
        normalized = normalize_corpus(corpus["raw_inputs"], corpus["source_event_refs"])
        baseline = compute_replay_identifier(normalized, corpus["source_event_refs"])
        self.assertNotEqual(baseline, compute_replay_identifier(list(reversed(normalized)), corpus["source_event_refs"]))
        changed = copy.deepcopy(normalized)
        changed[0]["record"]["confidence_bucket"] = "very_low"
        self.assertNotEqual(baseline, compute_replay_identifier(changed, corpus["source_event_refs"]))

    def test_spoofed_provenance_is_quarantined(self):
        record = make_record(event_ref=fixture_ref(5))
        record["provenance_identifier"] = "prov-" + "0" * 64
        item = normalize_input(canonical_json(record), 0, {record["event_ref"]})
        self.assertEqual(item["kind"], "quarantine")
        self.assertEqual(item["envelope"]["normalization_status"], "invalid_provenance")


class MalformedInputTests(unittest.TestCase):
    def test_invalid_utf8_is_deterministically_quarantined(self):
        raw = b"\xff\xfe"
        first = normalize_input(raw, 7, set())
        second = normalize_input(raw, 7, set())
        self.assertEqual(first, second)
        self.assertEqual(first["kind"], "quarantine")
        self.assertEqual(first["envelope"]["normalization_status"], "invalid_utf8")
        self.assertEqual(first["envelope"]["fact_sentinel"], "unavailable_due_to_malformed_input")
        self.assertTrue(first["provenance_identifier"].startswith("provq-"))
        self.assertNotIn(raw.hex(), canonical_json(first).decode("utf-8"))

    def test_duplicate_keys_are_quarantined_before_schema_validation(self):
        raw = b'{"schema_version":"olympus-governance-metadata/v2","schema_version":"x"}'
        item = normalize_input(raw, 0, set())
        self.assertEqual(item["envelope"]["normalization_status"], "duplicate_key")

    def test_downgrade_is_rejected(self):
        record = make_record(event_ref=fixture_ref(6))
        record["schema_version"] = "olympus-governance-metadata/v1"
        item = normalize_input(canonical_json(record), 0, {record["event_ref"]})
        self.assertEqual(item["kind"], "quarantine")
        self.assertEqual(item["envelope"]["normalization_status"], "unknown_version")

    def test_quarantine_namespace_cannot_validate_as_v2(self):
        item = normalize_input(b"not-json", 0, set())
        with self.assertRaises(ValidationFailure):
            validate_record(item["envelope"], set())
        self.assertEqual(item["envelope"]["fixture_namespace"], FIXTURE_NAMESPACE)
        self.assertEqual(item["envelope"]["quarantine_schema_version"], "olympus-governance-quarantine/v2")

    def test_noncanonical_json_is_quarantined(self):
        record = make_record(event_ref=fixture_ref(201))
        raw = json.dumps(record, indent=2).encode("utf-8")
        item = normalize_input(raw, 0, {record["event_ref"]})
        self.assertEqual(item["kind"], "quarantine")
        self.assertEqual(item["envelope"]["normalization_status"], "validation_error")

    def test_json_depth_below_at_and_above_limit_is_deterministic(self):
        for depth in (MAX_JSON_DEPTH - 1, MAX_JSON_DEPTH, MAX_JSON_DEPTH + 1, 1500):
            with self.subTest(depth=depth):
                raw = ("[" * depth + "0" + "]" * depth).encode("utf-8")
                first = normalize_input(raw, 0, set())
                second = normalize_input(raw, 0, set())
                self.assertEqual(first, second)
                self.assertEqual(first["kind"], "quarantine")
                expected = "invalid_json" if depth > MAX_JSON_DEPTH else "invalid_top_level"
                self.assertEqual(first["envelope"]["normalization_status"], expected)

    def test_deep_malformed_json_never_raises(self):
        raw = ("[" * 1501 + "x").encode("utf-8")
        item = normalize_input(raw, 9, set())
        self.assertEqual(item["kind"], "quarantine")
        self.assertEqual(item["envelope"]["normalization_status"], "invalid_json")


class FixtureNamespaceTests(unittest.TestCase):
    def test_live_event_ref_is_rejected(self):
        record = make_record(event_ref="live-000000000000000000000001")
        with self.assertRaisesRegex(ValidationFailure, "event_ref"):
            validate_record(record, {record["event_ref"]})

    def test_namespace_substitution_and_cross_run_transplant_are_rejected(self):
        for event_ref in (
            "olympus-fixture-v2-20260718-000000000000000000000001",
            "other-fixture-000000000000000000000001",
            "olympus-fixture-v2-20260717-NOTHEX000000000000000001",
        ):
            with self.subTest(event_ref=event_ref):
                record = make_record(event_ref=event_ref)
                with self.assertRaisesRegex(ValidationFailure, "event_ref"):
                    validate_record(record, {record["event_ref"]})

    def test_generated_corpus_uses_only_exact_fixture_namespace(self):
        corpus = build_representative_corpus()
        self.assertEqual(corpus["fixture_namespace"], "olympus-fixture-v2-20260717")
        self.assertTrue(corpus["source_event_refs"])
        self.assertTrue(all(ref.startswith(FIXTURE_NAMESPACE + "-") for ref in corpus["source_event_refs"]))
        self.assertFalse(any(ref.startswith("live-") for ref in corpus["source_event_refs"]))


class CorpusCoverageTests(unittest.TestCase):
    def test_representative_corpus_covers_all_action_classes_and_adversarial_classes(self):
        corpus = build_representative_corpus()
        self.assertEqual(
            set(corpus["covered_action_classes"]),
            {
                "read_only_observation", "local_reversible_mutation", "protected_mutation",
                "external_outbound", "financial_commitment", "identity_or_access_change",
                "destructive_action", "activation_or_authority_change", "unknown",
            },
        )
        required_adversarial = {
            "downgrade", "provenance_spoof", "replay_spoof", "duplicate_key", "invalid_utf8",
            "invalid_json", "extra_field", "unknown_enum", "invalid_identifier",
            "observe_indeterminate", "allow_indeterminate", "policy_conflict",
            "circular_fact_source", "namespace_spoof",
        }
        self.assertTrue(required_adversarial.issubset(set(corpus["covered_adversarial_classes"])))


class SourceEventNamespaceTests(unittest.TestCase):
    def test_validate_record_rejects_every_polluted_source_reference(self):
        record = make_record(event_ref=fixture_ref(900))
        polluted = [
            record["event_ref"],
            "live-000000000000000000000009",
            "olympus-fixture-v2-20260718-000000000000000000000009",
            "malformed",
        ]
        with self.assertRaisesRegex(ValidationFailure, "exact fixture namespace"):
            validate_record(record, polluted)

    def test_validate_record_rejects_duplicate_source_references(self):
        record = make_record(event_ref=fixture_ref(901))
        with self.assertRaisesRegex(ValidationFailure, "must be unique"):
            validate_record(record, [record["event_ref"], record["event_ref"]])

    def test_replay_identifier_rejects_polluted_source_reference(self):
        with self.assertRaisesRegex(ValidationFailure, "exact fixture namespace"):
            compute_replay_identifier([], ["live-000000000000000000000009"])


if __name__ == "__main__":
    unittest.main()
