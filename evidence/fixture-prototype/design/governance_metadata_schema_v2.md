# Olympus Governance Metadata Schema v2 — Design Specification

**Document status:** Design only; no implementation authorization  
**Proposed identifier:** `olympus-governance-metadata/v2`  
**Verdict:** `SCHEMA_V2_READY_FOR_REVIEW`

## 1. Scope and non-goals

Schema v2 is a proposed privacy-preserving, typed metadata sidecar for future independent adjudication of non-executable Olympus recommendations. It does not authorize exporter modification, Hermes modification, activation, production authority, callbacks, execution, deployment, or broader data access.

The certified v1 stream remains immutable and authoritative. V2 is designed as a separately approved, append-only sidecar keyed to an existing opaque v1 event reference. It must never contain prompts, message content, reasoning, tool names or arguments, raw target identifiers, principals, account identifiers, credentials, secrets, or free text.

## 2. Design invariants

1. **Closed vocabulary only.** All governance values are enums, booleans, bounded integers, or opaque identifiers.
2. **No free text.** Unknown facts use explicit `unknown`/`indeterminate` values.
3. **Independent facts and recommendations stay separate.** Native governance facts must not be derived from Olympus's recommendation. Recommendation fields are explicitly marked as advisory outputs.
4. **Fail closed.** Missing required fields, unknown versions, duplicate records, invalid enums, or provenance/replay mismatch make a record ineligible for certification.
5. **No authority semantics.** Metadata describes authority; it never grants or delegates it.
6. **No target identity.** Only coarse target classes are permitted.
7. **Deterministic canonicalization.** UTF-8 JSON, lexicographically sorted keys, no insignificant whitespace, arrays in schema-defined order, and SHA-256 identifiers with fixed domain separators.
8. **Sidecar compatibility.** V1 bytes and replay remain unchanged.

## 3. Proposed record shape

```json
{
  "schema_version": "olympus-governance-metadata/v2",
  "event_ref": "live-<24 lowercase hex>",
  "governance_action_class": "read_only_observation",
  "target_classification": "mock_only",
  "policy_evaluation_result": "pass",
  "policy_conflict_indicator": false,
  "contract_resolution_status": "resolved",
  "evidence_sufficiency": "sufficient",
  "authority_requested": "tier_0",
  "authority_available": "tier_0",
  "authority_decision": "within_boundary",
  "schema_validation_status": "valid",
  "recommendation_category": "continue_read_only_observation",
  "confidence_bucket": "very_high",
  "uncertainty_reason": "none",
  "replay_identifier": "replay-<64 lowercase hex>",
  "provenance_identifier": "prov-<64 lowercase hex>"
}
```

This is an illustrative record, not an implemented schema or exported event.

## 4. Requirement classes

- **Required:** Necessary for a record to enter decision-quality certification.
- **Recommended:** Materially improves diagnosis or stratification but is not necessary for the minimum verdict.
- **Optional:** Useful only for bounded analysis; omission must not reduce safety.

All 17 fields below are **Required** for the minimum useful v2 certification record. Candidate optional diagnostics were rejected or deferred in §7 to keep the record minimal.

## 5. Field specification and candidate review

### 5.1 `schema_version` — Required

- **Type:** string constant
- **Allowed values:** exactly `olympus-governance-metadata/v2`
- **Source:** schema producer configuration approved separately
- **Native/derived:** derived envelope metadata
- **Justification:** prevents silent interpretation under the wrong contract.
- **Privacy impact:** negligible; reveals only public schema version.
- **Security impact:** positive; supports strict parser dispatch and downgrade rejection.
- **Abuse analysis:** attacker may substitute `v1`; fail closed unless the certification request explicitly accepts v1, which decision-quality certification must not.
- **Data minimization:** one constant.
- **Replay impact:** included in canonical bytes; version change intentionally changes hashes.
- **Certification benefit:** proves the field contract reviewed by the adjudicator.

### 5.2 `event_ref` — Required

- **Type:** opaque string
- **Allowed values:** `^live-[a-f0-9]{24}$`, referencing one immutable v1 event
- **Source:** existing certified v1 `event_id`
- **Native/derived:** native copy of already-exported opaque reference
- **Justification:** binds metadata and recommendation to the same source event.
- **Privacy impact:** low but linkable within the certified corpus; no raw message/session ID.
- **Security impact:** no capability; must never be resolved outside the approved review environment.
- **Abuse analysis:** correlation across datasets is possible if copied; access and retention controls required.
- **Data minimization:** reuses an existing opaque identifier rather than adding identity.
- **Replay impact:** stable event join key.
- **Certification benefit:** enables packet integrity and duplicate detection.

### 5.3 `governance_action_class` — Required

- **Type:** enum string
- **Allowed values:** `read_only_observation`, `local_reversible_mutation`, `protected_mutation`, `external_outbound`, `financial_commitment`, `identity_or_access_change`, `destructive_action`, `activation_or_authority_change`, `unknown`
- **Source:** future typed native governance/audit fact recorded before Olympus evaluation; never inferred from message content by the exporter
- **Native/derived:** native preferred; deterministic mapping from an independently maintained action taxonomy permitted
- **Justification:** distinguishes observation, denial, authority, and high-risk cases.
- **Privacy impact:** low-to-moderate inference about activity class; no payload, target, amount, recipient, or tool.
- **Security impact:** descriptive only; cannot trigger an action.
- **Abuse analysis:** frequency may reveal operating patterns; aggregate publication and corpus access controls required.
- **Data minimization:** coarse class only.
- **Replay impact:** stable enum; mapping-table version must be provenance-bound.
- **Certification benefit:** essential for representative sampling and false-approval/denial analysis.

### 5.4 `target_classification` — Required

- **Type:** enum string
- **Allowed values:** `mock_only`, `local_nonproduction`, `production_protected`, `external_system`, `financial_system`, `identity_or_secret_store`, `family_or_calendar_commitment`, `unknown`
- **Source:** future typed target classification from an independent policy registry or native audit field
- **Native/derived:** deterministic derived classification; raw target prohibited
- **Justification:** risk cannot be judged without knowing the coarse target boundary.
- **Privacy impact:** moderate inference risk; class may reveal sensitive workflow category.
- **Security impact:** does not identify an endpoint or grant access.
- **Abuse analysis:** correlation with time/action can reveal habits; timestamps should be separately coarsened in review packets.
- **Data minimization:** no URI, path, account, person, service, hostname, or resource identifier.
- **Replay impact:** deterministic registry lookup; registry version bound by provenance.
- **Certification benefit:** allows target-boundary and unsafe-approval review.

### 5.5 `policy_evaluation_result` — Required

- **Type:** enum string
- **Allowed values:** `not_applicable`, `pass`, `deny`, `indeterminate`, `evaluation_error`
- **Source:** independently executed policy evaluation/audit result, not Olympus recommendation text
- **Native/derived:** derived from policy engine result
- **Justification:** exposes outcome without policy text or reasoning.
- **Privacy impact:** low; may infer that a protected rule applied.
- **Security impact:** descriptive; must not be accepted as authorization by any actuator.
- **Abuse analysis:** forged `pass` could bias review; provenance and separation-of-duties checks required.
- **Data minimization:** outcome only; no rule body or matched values.
- **Replay impact:** deterministic for a pinned policy-set digest.
- **Certification benefit:** enables policy correctness and denial analysis.

### 5.6 `policy_conflict_indicator` — Required

- **Type:** boolean or string sentinel
- **Allowed values:** `true`, `false`, `unknown`
- **Source:** independently computed policy evaluator summary
- **Native/derived:** derived
- **Justification:** identifies ambiguous or conflicting-policy cases without exposing policy details.
- **Privacy impact:** low.
- **Security impact:** descriptive only; `true` must force human review, not resolve conflict.
- **Abuse analysis:** suppressing conflicts could inflate agreement; provenance and test fixtures required.
- **Data minimization:** one tri-state value.
- **Replay impact:** deterministic under a pinned policy-set digest.
- **Certification benefit:** supports policy ambiguity frequency and governance-revision classification.

### 5.7 `contract_resolution_status` — Required

- **Type:** enum string
- **Allowed values:** `not_applicable`, `resolved`, `unknown_contract`, `ambiguous_contract`, `contract_invalid`, `resolution_error`
- **Source:** independent contract registry/resolver status
- **Native/derived:** derived
- **Justification:** distinguishes valid, missing, unknown, conflicting, and malformed contracts.
- **Privacy impact:** low; contract names and contents excluded.
- **Security impact:** no contract capability or endpoint is exposed.
- **Abuse analysis:** attackers may force `unknown_contract` for denial-of-certification; provenance and reproducibility checks required.
- **Data minimization:** status only.
- **Replay impact:** resolver and registry version must be provenance-bound.
- **Certification benefit:** enables contract-failure coverage and root-cause analysis.

### 5.8 `evidence_sufficiency` — Required

- **Type:** enum string
- **Allowed values:** `not_required`, `sufficient`, `insufficient`, `indeterminate`, `evidence_invalid`
- **Source:** independent evidence validator operating on typed presence/validity flags, never payload content in this stream
- **Native/derived:** derived
- **Justification:** independent adjudication must distinguish missing evidence from policy or authority failures.
- **Privacy impact:** low-to-moderate inference that evidence exists; evidence identity/value excluded.
- **Security impact:** not an attestation granting action; certification use only.
- **Abuse analysis:** a forged `sufficient` result can conceal unsafe recommendations; provenance and validator separation required.
- **Data minimization:** aggregate state only.
- **Replay impact:** deterministic for pinned evidence rules and immutable source facts.
- **Certification benefit:** enables evidence-gap frequency and insufficient-evidence adjudication.

### 5.9 `authority_requested` — Required

- **Type:** enum string
- **Allowed values:** `none`, `tier_0`, `tier_1`, `tier_2`, `tier_3`, `unknown`
- **Source:** native typed governance request or independent deterministic action-class mapping
- **Native/derived:** native preferred; derived mapping permitted
- **Justification:** required to compare required authority with available authority.
- **Privacy impact:** low; no identity, role name, or approval chain.
- **Security impact:** describes requested tier; does not request or grant it.
- **Abuse analysis:** must never be consumed as an authorization token.
- **Data minimization:** ordinal class only.
- **Replay impact:** stable under a pinned authority taxonomy.
- **Certification benefit:** supports authority-boundary cases.

### 5.10 `authority_available` — Required

- **Type:** enum string
- **Allowed values:** `none`, `tier_0`, `tier_1`, `tier_2`, `tier_3`, `unknown`
- **Source:** independently recorded effective authority class at decision time
- **Native/derived:** native preferred; may be derived from a privacy-preserving entitlement snapshot
- **Justification:** authority mismatch cannot be judged from requested tier alone.
- **Privacy impact:** moderate; may imply operator privilege level. No principal, group, credential, approver, or entitlement list allowed.
- **Security impact:** descriptive and stale by design; cannot authenticate or authorize.
- **Abuse analysis:** privilege inference and targeting risk; restrict corpus access and retention.
- **Data minimization:** coarse tier only; `unknown` preferred over exposing identity.
- **Replay impact:** immutable point-in-time class required; never query live authority during replay.
- **Certification benefit:** enables authority disagreement and false-approval analysis.

### 5.11 `authority_decision` — Required

- **Type:** enum string
- **Allowed values:** `not_applicable`, `within_boundary`, `approval_required`, `denied`, `indeterminate`, `evaluation_error`
- **Source:** independent authority policy evaluator
- **Native/derived:** derived
- **Justification:** prevents reviewers from reconstructing boundary logic from sensitive identity data.
- **Privacy impact:** low.
- **Security impact:** must be marked non-authoritative; no actuator may consume it.
- **Abuse analysis:** spoofed `within_boundary` could normalize unsafe outcomes; provenance and review isolation required.
- **Data minimization:** result only.
- **Replay impact:** deterministic from immutable requested/available classes and pinned authority policy.
- **Certification benefit:** directly measures authority recommendation quality.

### 5.12 `schema_validation_status` — Required

- **Type:** enum string
- **Allowed values:** `valid`, `invalid_missing_required`, `invalid_type`, `invalid_enum`, `invalid_additional_property`, `invalid_provenance`, `unknown_version`, `validation_error`
- **Source:** independent strict validator
- **Native/derived:** derived
- **Justification:** makes malformed-metadata cases observable without retaining malformed values.
- **Privacy impact:** negligible.
- **Security impact:** positive; fail-closed parsing and spoof detection.
- **Abuse analysis:** error-category distribution may fingerprint producers; aggregate external reporting.
- **Data minimization:** first deterministic error class only; no raw error string or path.
- **Replay impact:** deterministic validation-order specification required.
- **Certification benefit:** supports malformed metadata coverage and compatibility testing.

### 5.13 `recommendation_category` — Required

- **Type:** enum string
- **Allowed values:** `continue_read_only_observation`, `allow_simulation_only`, `deny`, `request_human_approval`, `request_additional_evidence`, `abstain_insufficient_information`, `escalate_policy_conflict`, `invalid_input`
- **Source:** Olympus advisory output after governance facts are frozen
- **Native/derived:** derived advisory output
- **Justification:** the object being adjudicated must be represented without rationale text.
- **Privacy impact:** low; may reveal decision distribution.
- **Security impact:** explicitly non-executable; prohibited as actuator input.
- **Abuse analysis:** replaying or relabeling a recommendation as authorization is a primary threat; envelope and UI must display `ADVISORY ONLY`.
- **Data minimization:** category only; no chain-of-thought or rationale.
- **Replay impact:** deterministic recommendation engine/version must be provenance-bound outside this record.
- **Certification benefit:** enables agreement, false-approval/denial, and distribution metrics.

### 5.14 `confidence_bucket` — Required

- **Type:** enum string
- **Allowed values:** `very_low`, `low`, `medium`, `high`, `very_high`, `not_scored`
- **Normative bins:** `[0,.2)`, `[.2,.4)`, `[.4,.6)`, `[.6,.8)`, `[.8,1.0]`, or no score
- **Source:** deterministic bucketing of Olympus's bounded confidence score
- **Native/derived:** derived advisory output
- **Justification:** supports calibration while avoiding false precision.
- **Privacy impact:** negligible.
- **Security impact:** descriptive only; must not override fail-closed rules.
- **Abuse analysis:** confidence can create automation bias; reviewers must judge facts before revealing it where feasible.
- **Data minimization:** bucket instead of raw float.
- **Replay impact:** deterministic boundary rules; decimal normalization fixed.
- **Certification benefit:** minimum calibration analysis.

### 5.15 `uncertainty_reason` — Required

- **Type:** enum string
- **Allowed values:** `none`, `missing_governance_metadata`, `policy_conflict`, `unknown_contract`, `insufficient_evidence`, `authority_indeterminate`, `schema_invalid`, `multiple_conditions`, `other_bounded`, `not_scored`
- **Source:** deterministic priority mapping from typed facts and advisory state
- **Native/derived:** derived
- **Justification:** distinguishes calibrated abstention from unexplained low confidence.
- **Privacy impact:** low.
- **Security impact:** no sensitive detail; `other_bounded` must not permit text.
- **Abuse analysis:** priority mapping can hide secondary causes; `multiple_conditions` plus separate typed facts preserves signal.
- **Data minimization:** single primary category only.
- **Replay impact:** priority order is normative: schema, authority, policy, contract, evidence, missing metadata, other.
- **Certification benefit:** supports uncertainty and recurring-failure analysis.

### 5.16 `replay_identifier` — Required

- **Type:** opaque string
- **Allowed values:** `^replay-[a-f0-9]{64}$`
- **Source:** SHA-256 over the immutable ordered v1 source-stream digest, v2 metadata-set digest, and approved canonicalization/profile identifiers using domain `olympus-governance-replay/v2`
- **Native/derived:** derived
- **Justification:** binds every record to a reproducible certification run without exposing source data.
- **Privacy impact:** moderate correlation risk across copies of the same batch.
- **Security impact:** integrity label only, not a capability.
- **Abuse analysis:** replay identifier could be transplanted; validators must recompute it, not trust the value.
- **Data minimization:** one batch digest.
- **Replay impact:** central deterministic run identity; runtime timestamps/latency excluded.
- **Certification benefit:** proves corpus and recommendation replay consistency.

### 5.17 `provenance_identifier` — Required

- **Type:** opaque string
- **Allowed values:** `^prov-[a-f0-9]{64}$`
- **Source:** SHA-256 over domain `olympus-governance-provenance/v2`, `event_ref`, canonical governance-fact fields (3–12), source snapshot digest, and pinned taxonomy/registry digests; excludes recommendation fields
- **Native/derived:** derived
- **Justification:** proves factual metadata provenance independently from Olympus output.
- **Privacy impact:** moderate linkability; no reverse mapping to raw identifiers should exist in the review packet.
- **Security impact:** detects fact/recommendation substitution but is not cryptographic authentication unless separately signed.
- **Abuse analysis:** hash alone does not prove trusted origin; certification requires a separately approved signed manifest or controlled custody record.
- **Data minimization:** one digest replaces verbose provenance details.
- **Replay impact:** stable for identical facts and pinned dependencies.
- **Certification benefit:** guards against circular evaluation and schema spoofing.

## 6. Cross-field validity rules

For the fixture-only profile, `design/fixture_profile_normative_resolutions.md` is the single normative source for NEW-1 observe-only/indeterminate combinations and NEW-2 malformed-input handling. The following rules use the same category classification: `continue_read_only_observation` is observe-only and non-authorizing; `allow_simulation_only` is the sole allow category; every other recommendation is fail-closed.

1. `event_ref` must exist exactly once in the referenced immutable v1 stream.
2. `authority_decision=within_boundary` requires known `authority_requested` and `authority_available`, with available tier at least requested under the pinned authority taxonomy.
3. `authority_decision=approval_required|denied|indeterminate|evaluation_error` must not coexist with `recommendation_category=allow_simulation_only`.
4. `policy_conflict_indicator=true` requires `policy_evaluation_result=indeterminate` or `deny`; it may never silently resolve to `pass`.
5. `contract_resolution_status` other than `resolved` must not produce `allow_simulation_only`; `unknown_contract|ambiguous_contract` may coexist with provisional `continue_read_only_observation` only under NEW-1 Rule 1.
6. `evidence_sufficiency=insufficient|indeterminate|evidence_invalid` must not produce `allow_simulation_only`; these values may coexist with provisional `continue_read_only_observation` only under NEW-1 Rule 1.
7. Any invalid `schema_validation_status` requires `recommendation_category=invalid_input` or `abstain_insufficient_information`.
8. `uncertainty_reason=none` requires all required factual evaluations to be determinate and schema-valid.
9. Unknown/indeterminate values never permit `allow_simulation_only` and never produce a definitive correctness label. They may coexist with provisional `continue_read_only_observation` only when every predicate in NEW-1 Rule 1 holds; otherwise they require the fail-closed category selected by NEW-1 Rule 4.
10. No field in this record conveys executable permission.

## 6A. Malformed-input normalization

Malformed or uncanonicalizable inputs must not be dropped or repaired. The NEW-2 profile normalizes each such raw byte string into a canonical `olympus-governance-quarantine/v2` envelope with deterministic first-error status, raw-byte digest, byte length, namespace, ordinal, and fixed sentinels. Quarantine provenance uses the `provq-` namespace, and every quarantine item contributes to the ordered corpus replay digest. Exact envelope fields, error order, canonical JSON rules, sentinel constants, and digest formulas are defined only in `design/fixture_profile_normative_resolutions.md`.

## 7. Candidate disposition

| Candidate | Disposition | Requirement | Reason |
|---|---|---:|---|
| Governance action class | Include | Required | Core scenario and risk stratification |
| Policy evaluation result | Include | Required | Independent policy outcome |
| Policy conflict indicator | Include | Required | Ambiguity detection |
| Contract resolution status | Include | Required | Unknown/failure coverage |
| Evidence sufficiency | Include | Required | Evidence-gap adjudication |
| Authority requested | Include | Required | Required side of boundary comparison |
| Authority available | Include | Required | Available side; coarse only |
| Authority decision | Include | Required | Independent boundary result |
| Schema validation status | Include | Required | Malformed-input coverage |
| Target classification | Include | Required | Coarse risk context |
| Confidence bucket | Include | Required | Calibration without raw precision |
| Uncertainty reason | Include | Required | Abstention/uncertainty analysis |
| Recommendation category | Include | Required | Adjudication target |
| Replay identifier | Include | Required | Deterministic corpus binding |
| Provenance identifier | Include | Required | Independent fact provenance |
| Exact policy identifiers | Exclude | — | Correlation and policy-enumeration risk |
| Exact contract identifiers | Exclude | — | Reveals internal control surface |
| Evidence type list | Defer | Recommended in a later reviewed extension | May improve diagnosis but increases inference risk |
| Raw confidence float | Exclude | — | False precision and automation bias |
| Human expected outcome | Exclude from event schema | Separate adjudication record | Including it would bias/blind-break review and risk circular labels |
| Timestamp | Reuse v1 only; do not duplicate | Optional packet context | Correlation risk; coarse time may be generated in review view |
| Free-text rationale | Exclude | — | Could expose reasoning or sensitive content |
| Tool name/arguments | Exclude | — | Operational and secret leakage risk |
| Raw target/principal/recipient | Exclude | — | Privacy and security risk |

## 8. Source independence requirement

Fields 3–12 must be produced or attested by a source independent of Olympus recommendation generation. Fields 13–15 come from Olympus and must be frozen only after fields 3–12 and `provenance_identifier` are fixed. A certification corpus must preserve this ordering. If the only available source for a factual field is Olympus itself, that field is `indeterminate` and the event cannot establish recommendation correctness.

## 9. Certification sufficiency

The proposed minimum can support independent review of action, target, policy, contract, evidence, authority, malformed-input, recommendation, confidence, and uncertainty classes without content disclosure. It does **not** itself provide ground truth. Ground truth remains a separate blinded human adjudication artifact with reviewer identity pseudonym, classification, bounded reason code, and reproducibility outcome. No human label is exported from Hermes.

## 10. Approval boundary

This specification is ready for privacy, security, governance, and replay review only. Any implementation requires a separate change request, data-flow review, threat-model approval, fixture-only prototype, and recertification. Existing v1 exporter, redaction, stream, replay, and safety certifications remain unchanged.