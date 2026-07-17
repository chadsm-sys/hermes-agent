# Governance Metadata Schema v2 — Certification Rationale

## Why v1 was insufficient

The certified v1 stream exposes only redacted message-observation metadata under one fixed read-only contract, policy set, Tier 0 authority context, mock target, and confidence value. It cannot distinguish ten of eleven required governance scenario classes. Independent decision-quality certification therefore correctly returned `BLOCKED`.

## How the proposed minimum closes the gap

| Certification question | Proposed evidence |
|---|---|
| What kind of governance action was considered? | `governance_action_class` |
| What risk boundary was targeted? | `target_classification` |
| Did policy pass, deny, conflict, or fail? | `policy_evaluation_result`, `policy_conflict_indicator` |
| Did a contract resolve? | `contract_resolution_status` |
| Was evidence adequate? | `evidence_sufficiency` |
| Was authority sufficient and what was decided? | requested/available/decision fields |
| Was metadata valid? | `schema_validation_status` |
| What did Olympus recommend? | `recommendation_category` |
| How certain and why? | `confidence_bucket`, `uncertainty_reason` |
| Are facts independent and replayable? | event, provenance, and replay identifiers |

## Independent adjudication model

1. Freeze independently sourced governance facts and provenance.
2. Present facts to a reviewer without Olympus recommendation/confidence.
3. Capture provisional human disposition using bounded classifications and justification codes.
4. Reveal Olympus recommendation, confidence bucket, and uncertainty reason.
5. Record agreement/disagreement, error owner, ambiguity/evidence status, reproducibility, and regression recommendation.
6. Aggregate only after completeness and privacy thresholds pass.

This avoids exporting a human expected label from Hermes and reduces recommendation anchoring.

## Metrics enabled

- Agreement and disagreement rates by action/target class
- False-approval and false-denial rates
- Policy ambiguity and conflict frequency
- Contract failure/unknown frequency
- Evidence insufficiency frequency
- Authority disagreement frequency
- Invalid-schema handling
- Recommendation distribution
- Confidence calibration by bucket
- Uncertainty reason distribution
- Recurring bounded failure patterns

## Quality limitations

The schema does not guarantee correct source facts, representative sampling, sufficient reviewer expertise, or statistical power. Those remain certification gates. Hashes prove deterministic linkage, not trusted-origin authenticity. A controlled provenance manifest or separately reviewed signing mechanism may be required later, but no signing or key infrastructure is proposed here.

## Readiness judgment

Meaningful certification appears achievable without exposing sensitive operational information because all necessary semantics can be represented as coarse independent outcomes. The decisive prerequisite is source availability: required facts must already exist as typed native/audit values or be deterministically derived from approved non-content metadata. If not, implementation is blocked rather than broadening collection.

## Safety preservation

- No message content, prompts, reasoning, tool arguments, credentials, secrets, targets, or identities are proposed.
- No execution or callback fields exist.
- Olympus remains advisory-only.
- V1 exporter/stream/replay remain unchanged through sidecar design.
- Production authority and activation remain denied.

**Design conclusion:** `SCHEMA_V2_READY_FOR_REVIEW`. This is not implementation approval or decision-quality certification.