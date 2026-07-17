# Schema v2 Fixture Profile — Normative Resolutions NEW-1 and NEW-2

**Status:** Normative for the offline fixture prototype only  
**Profile:** `olympus-governance-fixture/v2`  
**Authority:** No Hermes integration, exporter change, production activation, or execution authority

This document is the single normative source for NEW-1 and NEW-2. Other design prose must defer to these rules and must not paraphrase them with different semantics.

## NEW-1 — Observe-only and indeterminate-state rules

### Category classification

- `continue_read_only_observation` is an **observe-only category**, not an allow category. It authorizes nothing and may describe only continued passive inspection of synthetic, mock-only, or local-nonproduction fixture data.
- `allow_simulation_only` is the sole **allow category** in this profile. It remains non-executable and may describe only a synthetic simulation.
- `deny`, `request_human_approval`, `request_additional_evidence`, `abstain_insufficient_information`, `escalate_policy_conflict`, and `invalid_input` are **fail-closed categories**.

### Canonical decision rules

1. `continue_read_only_observation` is valid only when `governance_action_class=read_only_observation`, `target_classification` is `mock_only` or `local_nonproduction`, `schema_validation_status=valid`, `policy_evaluation_result` is neither `deny` nor `evaluation_error`, `policy_conflict_indicator` is not `true`, and `contract_resolution_status` is neither `contract_invalid` nor `resolution_error`.
2. An `unknown` or `indeterminate` factual value never permits `allow_simulation_only` and never produces a definitive correctness label.
3. When Rule 1 holds, an unknown or indeterminate value may coexist with `continue_read_only_observation` only as **provisional observation**. `uncertainty_reason` must be non-`none` and must match the normative priority order: schema, authority, policy, contract, evidence, missing metadata, other.
4. When Rule 1 does not hold, an unknown or indeterminate value requires a fail-closed category. Use `escalate_policy_conflict` for a policy conflict, `request_additional_evidence` for insufficient or indeterminate evidence, `request_human_approval` for an authority boundary requiring human approval, `invalid_input` for schema-invalid input, and `abstain_insufficient_information` for all remaining indeterminate states.
5. `allow_simulation_only` requires all factual evaluations to be determinate and valid: exact v2 schema, no unknown factual enum, `policy_evaluation_result=pass`, `policy_conflict_indicator=false`, `contract_resolution_status=resolved`, `evidence_sufficiency=sufficient`, known requested and available authority, and `authority_decision=within_boundary`.
6. `policy_evaluation_result=deny` requires `recommendation_category=deny`. `policy_conflict_indicator=true` requires `recommendation_category=escalate_policy_conflict`. Invalid schema requires `recommendation_category=invalid_input`. These explicit fail-closed outcomes take precedence over provisional observation.
7. No recommendation category conveys executable permission or production authority.

### Indeterminate combination matrix

| Factual state | Observe-only action satisfying Rule 1 | Any other action | Definitive correctness eligible |
|---|---|---|---|
| `governance_action_class=unknown` | Not applicable; Rule 1 fails | `abstain_insufficient_information` | No |
| `target_classification=unknown` | Rule 1 fails | `abstain_insufficient_information` | No |
| `policy_evaluation_result=indeterminate` | `continue_read_only_observation` as provisional observation | `abstain_insufficient_information` | No |
| `policy_evaluation_result=evaluation_error` | Rule 1 fails | `abstain_insufficient_information` | No |
| `policy_conflict_indicator=unknown` | `continue_read_only_observation` as provisional observation | `abstain_insufficient_information` | No |
| `policy_conflict_indicator=true` | `escalate_policy_conflict` | `escalate_policy_conflict` | No |
| `contract_resolution_status=unknown_contract|ambiguous_contract` | `continue_read_only_observation` as provisional observation | `abstain_insufficient_information` | No |
| `contract_resolution_status=contract_invalid|resolution_error` | Rule 1 fails | `abstain_insufficient_information` | No |
| `evidence_sufficiency=indeterminate|insufficient|evidence_invalid` | `continue_read_only_observation` as provisional observation | `request_additional_evidence` | No |
| `authority_requested=unknown` or `authority_available=unknown` | `continue_read_only_observation` as provisional observation | `abstain_insufficient_information` | No |
| `authority_decision=indeterminate|evaluation_error` | `continue_read_only_observation` as provisional observation | `abstain_insufficient_information` | No |
| missing required factual field | Schema invalid; `invalid_input` | Schema invalid; `invalid_input` | No |

The matrix and Rules 1–7 are identical in effect: the matrix is illustrative, while the rules are exhaustive for combinations involving multiple indeterminate states. Multiple simultaneous indeterminate states use `uncertainty_reason=multiple_conditions` unless a higher-priority explicit fail-closed outcome applies.

## NEW-2 — Canonical malformed-input handling

### Input model

The prototype consumes an ordered sequence of raw byte strings. Every input position contributes exactly one normalized item to the replay ledger: either a valid canonical v2 record or a canonical quarantine envelope. No input is dropped, guessed, repaired, or looked up from content.

### Valid canonical representation

- Input must decode as strict UTF-8 and parse as one JSON object with duplicate-key rejection.
- Allowed JSON value types are strings and booleans only. Numbers, `null`, arrays, and nested objects are invalid for v2 record fields.
- Strings must already be Unicode NFC. The validator rejects non-NFC strings rather than silently changing semantic input.
- The object must contain exactly the 17 required keys and no others.
- Canonical JSON is UTF-8, Unicode NFC, lexicographically sorted object keys, lowercase JSON literals, no insignificant whitespace, and one trailing newline only when stored as JSONL. Digest input excludes the JSONL trailing newline.

### Deterministic first-error order

The first error is selected in this order:

1. `invalid_utf8`
2. `invalid_json`
3. `duplicate_key`
4. `invalid_top_level`
5. `unknown_version`
6. `invalid_missing_required`
7. `invalid_additional_property`
8. `invalid_type`
9. `invalid_enum`
10. `invalid_identifier`
11. `invalid_cross_field`
12. `invalid_provenance`
13. `invalid_replay`
14. `validation_error`

### Quarantine normalization

An input that cannot become a valid canonical v2 record is represented by a separate envelope in namespace `olympus-governance-quarantine/v2`. The envelope contains only:

- `quarantine_schema_version`: exact constant `olympus-governance-quarantine/v2`
- `fixture_namespace`: exact declared fixture namespace
- `input_ordinal`: zero-based integer position in the source corpus
- `raw_input_sha256`: `sha256-` plus the lowercase SHA-256 of the exact raw bytes
- `raw_input_length`: non-negative byte count
- `normalization_status`: exact deterministic first-error enum
- `event_ref_sentinel`: `quarantine-` plus the first 24 hex characters of the raw-input SHA-256
- `fact_sentinel`: exact constant `unavailable_due_to_malformed_input`
- `recommendation_sentinel`: exact constant `invalid_input`

The quarantine envelope never contains raw input, a repaired value, an extracted target, free text, or a trusted producer-supplied identifier. Its canonical JSON uses the same key sorting, encoding, and whitespace rules as valid records.

### Sentinel and digest rules

- The valid-record namespace and quarantine namespace are disjoint. A quarantine envelope can never validate as a v2 record.
- A quarantined item receives `provenance_identifier=provq-<64 lowercase hex>` computed with domain `olympus-governance-quarantine-provenance/v2` over its canonical quarantine envelope plus pinned source/profile digests.
- A valid item receives `provenance_identifier=prov-<64 lowercase hex>` computed with domain `olympus-governance-provenance/v2` over fact-only canonical data plus pinned source/profile digests. Recommendation, confidence, uncertainty, replay, and provenance fields are excluded.
- Digest construction is `SHA-256(UTF8(domain) || 0x0a || canonical_JSON(payload))`. Payloads are JSON objects, so concatenation is unambiguous.
- The corpus replay identifier is `replay-<64 lowercase hex>` under domain `olympus-governance-replay/v2`. Its payload contains the exact fixture namespace, source-stream digest, ordered normalized-item digests (valid and quarantine), canonicalization-profile digest, taxonomy/profile digests, and expected item count. A valid normalized-item digest excludes only `replay_identifier`; a quarantine-item digest includes the full quarantine envelope and its `provq-` identifier. This exclusion is the mandatory anti-circular construction: all facts, decisions, and provenance remain bound while the replay identifier can be populated after corpus hashing.
- Fixture generation MAY use `replay-` plus 64 zeroes only as an internal pre-publication sentinel. Published valid fixtures MUST contain the computed corpus replay identifier. Corpus verification determines a non-zero supplied consensus only when at least two structurally and provenance-valid records contain the same replay identifier; non-zero outliers are quarantined as `invalid_replay`, the replay is recomputed, and any consensus that does not equal the recomputed value is also quarantined. The all-zero pre-publication form has no authority and is replaced before fixture publication.
- Validators recompute all digests. Producer-supplied provenance or replay identifiers are never trusted.
- A malformed input remains replay-computable because its exact raw-byte digest and deterministic quarantine envelope are included in the ordered ledger.

## Fixture namespace separation

Fixture records use namespace `olympus-fixture-v2-20260717` and synthetic `event_ref` values. Production-like namespace values, live source paths, Hermes identifiers, exporter records, network inputs, and runtime state are prohibited. The prototype performs no network access and writes only beneath its standalone prototype directory.
