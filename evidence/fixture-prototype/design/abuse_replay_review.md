# Governance Metadata Schema v2 — Abuse and Replay Review

## Scope

This document consolidates field-level abuse, replay, and certification-usefulness findings. It adds no fields and authorizes no implementation.

## Candidate matrix

| Field | Primary abuse | Control | Replay rule | Certification use |
|---|---|---|---|---|
| `schema_version` | Downgrade/substitution | Exact constant; no fallback | Included in canonical bytes | Contract identification |
| `event_ref` | Cross-dataset correlation/transplant | Existing opaque ID; provenance binding | Stable join to one v1 event | Packet integrity |
| `governance_action_class` | Activity-pattern inference/misclassification | Coarse enum; pinned mapping; aggregate reporting | Deterministic taxonomy version | Scenario/false-approval analysis |
| `target_classification` | Sensitive workflow inference | No target locator; rare-cell suppression | Pinned target registry | Risk-boundary review |
| `policy_evaluation_result` | Forged pass | Independent evaluator/provenance | Pinned policy-set digest | Policy correctness |
| `policy_conflict_indicator` | Conflict suppression | Tri-state; conflict fails closed | Deterministic conflict rule | Ambiguity frequency |
| `contract_resolution_status` | Forced unknown/false resolved | Independent resolver; reproducibility | Pinned registry/resolver | Contract failure coverage |
| `evidence_sufficiency` | Forged sufficiency | Independent aggregate validator | Pinned evidence rules | Evidence-gap analysis |
| `authority_requested` | Treating request as grant | Non-authority semantics | Pinned action-to-tier mapping | Required boundary |
| `authority_available` | Privilege inference/stale replay | Coarse tier, restricted access, point-in-time only | Never query live authority during replay | Available boundary |
| `authority_decision` | Treating result as authorization | Actuator prohibition; provenance | Deterministic policy evaluation | Authority disagreement |
| `schema_validation_status` | Producer fingerprinting/error hiding | Bounded first-error class | Normative error order | Malformed-input behavior |
| `recommendation_category` | Conversion into executable approval | Advisory-only label; no consumer path | Pinned advisory engine/profile | Decision under review |
| `confidence_bucket` | Automation bias/boundary gaming | Blind provisional review; fixed bins | Deterministic bucket boundaries | Calibration |
| `uncertainty_reason` | Hiding secondary causes | Typed fact fields remain visible; priority rule | Normative priority order | Failure-pattern analysis |
| `replay_identifier` | Stale replay/transplant | Recompute from complete pinned corpus | Deterministic batch digest | Run integrity |
| `provenance_identifier` | Mistaking hash for authenticity | Controlled custody or separately reviewed signature | Deterministic fact-only digest | Source independence |

## Replay profile

For the fixture-only prototype, `design/fixture_profile_normative_resolutions.md` is the single normative source for NEW-1 observe-only/indeterminate decisions and NEW-2 malformed-input normalization. Replay includes one ordered normalized item per raw input: either a valid v2 record or a namespace-separated quarantine envelope. Nothing is silently dropped or repaired.

A future replay profile must pin:

- exact schema version and canonicalization rules;
- immutable v1 source-stream digest;
- complete ordered v2 fact-set digest;
- action/target/authority taxonomy digests;
- policy, contract, and evidence-validator profile digests;
- advisory engine/profile digest;
- validation error ordering;
- confidence-bin and uncertainty-priority definitions.

Runtime timestamps, latency, hostnames, paths, process IDs, and current authority queries are excluded.

## Adversarial fixtures required before implementation review

1. Missing and duplicate fields
2. Duplicate JSON keys
3. Unknown enums and versions
4. Additional properties
5. Event-reference transplant
6. Provenance and replay mismatch
7. Downgrade to v1
8. Stale authority evidence
9. Policy conflict combined with pass/allow
10. Unknown contract or insufficient evidence combined with allow
11. Invalid schema combined with allow
12. Olympus-generated factual fields (circular certification)
13. Rare target/action combinations for privacy review
14. Reviewer anchoring from confidence/recommendation display
15. Every NEW-1 observe-only/indeterminate matrix row, including multiple simultaneous indeterminate states
16. Invalid UTF-8, invalid JSON, duplicate keys, invalid top-level values, non-NFC strings, and every deterministic NEW-2 validation class
17. Quarantine/valid namespace collision and fixture/production namespace spoofing

## Conclusion

The bounded fields can be replay-safe and certification-useful if independently sourced and strictly validated. Hashes do not prove authenticity, and metadata must never become authority. Failure of either condition is an automatic `BLOCKED` result.