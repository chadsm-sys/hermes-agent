# Schema Diff: Certified v1 to Proposed Governance Metadata v2

## Status

Design comparison only. No v1 file, exporter, stream, replay, contract, or runtime component is changed.

## Architectural difference

| Area | Certified v1 | Proposed v2 |
|---|---|---|
| Purpose | Redacted live activity observation | Governance fact sidecar for future decision-quality adjudication |
| Transport | Immutable JSONL event stream | Separate immutable JSONL sidecar; never embedded into or substituted for v1 |
| Join | `event_id` | `event_ref` copies the existing opaque v1 ID |
| Payload/content | Excluded | Excluded |
| Operational identity | Opaque session/row references | No new operational identity |
| Governance diversity | Fixed read-only observation, Tier 0 | Coarse typed action/target/policy/contract/evidence/authority classes |
| Recommendation | Not part of source facts | Non-executable recommendation category, clearly separated from facts |
| Replay | Existing v1 manifest and canonicalization | New independent v2 replay ID; v1 replay unchanged |
| Provenance | Stream hash/manifests | Per-record provenance digest plus run replay digest |
| Compatibility | Certified | V2-aware consumers use sidecar; v1 consumers ignore it entirely |

## Field mapping

| v1 field | v2 treatment | Notes |
|---|---|---|
| `schema_version` | New independent constant | `olympus-live-export/v1` remains untouched; sidecar uses `olympus-governance-metadata/v2` |
| `event_id` | Referenced as `event_ref` | Exact opaque value; no raw IDs |
| `event_type` | Not copied | Replaced for certification analysis by coarse `governance_action_class` sourced independently |
| `timestamp` | Not copied | Review interface may use coarsened time from v1 when approved |
| `normalized_metadata` | Not copied | Existing role/source/lifecycle metadata is unnecessary for minimum governance adjudication |
| `authority_context` / `authority_tier` | Not copied directly | V2 uses requested/available/decision enums; no principal or entitlement list |
| `available_evidence` / `evidence` | Not copied | V2 exports aggregate `evidence_sufficiency` only |
| `contract_identifiers` | Not copied | V2 exports resolution status only |
| `policy_identifiers` | Not copied | V2 exports result and conflict indicator only |
| `target_identifiers` | Not copied | V2 exports coarse target class only |
| `confidence_inputs` | Not copied | V2 exports confidence bucket and uncertainty reason from advisory output |
| `source`, `state`, `requested_action`, `confidence` | Not copied | Avoid duplication and inference; required linkage remains through event/provenance/replay IDs |

## New v2 fields

`governance_action_class`, `target_classification`, `policy_evaluation_result`, `policy_conflict_indicator`, `contract_resolution_status`, `evidence_sufficiency`, `authority_requested`, `authority_available`, `authority_decision`, `schema_validation_status`, `recommendation_category`, `confidence_bucket`, `uncertainty_reason`, `replay_identifier`, and `provenance_identifier`.

## Compatibility consequences

- **No in-place migration.** Existing v1 bytes remain valid forever under their certification.
- **No automatic upgrade.** Absence of a v2 sidecar means decision-quality status is `NOT_AVAILABLE`, not an error in v1.
- **No downgrade acceptance.** A v2 certification request must reject v1-only records.
- **No semantic overloading.** V1 `authority_tier=0` must not be reinterpreted as a general v2 authority fact.
- **No hash invalidation.** V1 source stream and replay manifest retain their current SHA-256 values.

## Removed/rejected candidates

No v1 field is removed because v1 is untouched. V2 intentionally rejects exact policy/contract identifiers, evidence details, raw confidence, free text, message content, prompts, reasoning, tool arguments, targets, principals, credentials, and secrets.