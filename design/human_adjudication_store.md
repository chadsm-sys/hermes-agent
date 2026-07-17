# Schema v2 R2 — Human Adjudication Store

**Status:** Design only. Resolves independent-review finding P2-6. No store is created
by this document; this is the artifact contract a future implementation must satisfy
before Phase 5 (human adjudication pilot).

## 1. Position in the architecture

Human adjudication is the ground truth for decision-quality certification. It lives in
a dedicated artifact class, proposed identifier `olympus-human-adjudication/v1`,
stored **outside Hermes** in the controlled review environment. It is never part of
the v2 sidecar, never exported from Hermes, and has **no read path from Olympus**:
the advisory evaluator's inputs are exactly the frozen fields defined in
`design/record_assembly_order.md` S5, and adding any adjudication-store input to
Olympus is an automatic `BLOCKED` under the approval gate. Human labels therefore can
never become Olympus recommendation inputs or training signal.

## 2. Storage model: append-only hash-chained ledger

- The store is an append-only JSONL ledger. Records are never edited or deleted;
  corrections are new superseding records referencing the superseded entry.
- Every record carries `prev_record_digest`: the SHA-256 of the previous ledger
  record's canonical bytes (genesis uses 64 zeros), forming a hash chain. Domain
  separator: `olympus-human-adjudication/v1:chain`.
- **Mutation detection:** any in-place edit, deletion, or reordering breaks every
  subsequent `prev_record_digest`. A periodic checkpoint digest (chain head hash plus
  record count) is anchored with the same custody/signature mechanism as run manifests
  (`design/provenance_authenticity_plan.md`), so truncation-and-rebuild of the whole
  chain is also detectable.
- All values are closed enums, bounded codes, or opaque digests under `ogm-canon/1`
  canonicalization. Free text is prohibited, including in justification fields.

## 3. Record content

Each adjudication entry contains exactly:

- `entry_type`: `stage_a_provisional`, `stage_b_comparison`, `supersession`, or
  `checkpoint`.
- `event_ref` and `replay_identifier`: binding to one record of one certified run.
- `reviewer_role`: bounded role enum (for example `privacy_reviewer`,
  `security_reviewer`, `governance_reviewer`, `domain_reviewer`).
- `reviewer_pseudonym`: per-corpus opaque pseudonym (`rev-<16 hex>`). The
  pseudonym-to-person mapping lives only in the review-administration custody record,
  never in the ledger; no name, account, or contact data appears anywhere.
- `recorded_utc`: RFC 3339 UTC timestamp, second precision. Timestamps order the
  chain and support challenge-window enforcement; they are never joined with event
  content, and adjudication timestamps are excluded from published aggregates.
- Stage-specific bounded fields (below).
- `prev_record_digest`.

## 4. Blinded two-stage protocol

- **Stage A (provisional, blind):** the reviewer sees only frozen fields 1–12 and
  field 17 of the subject record. Fields 13–15, 14's bucket, 15's reason, and any
  other reviewer's entries are withheld. The reviewer records
  `provisional_disposition` (closed enum: `should_allow_simulation`,
  `should_continue_observation`, `should_deny`, `should_escalate_human`,
  `should_request_evidence`, `should_abstain`, `cannot_adjudicate`) plus
  `justification_code` (bounded taxonomy) and `reviewer_uncertainty`
  (`low`, `medium`, `high`).
- The stage-A entry is appended and hash-chained **before** the advisory values are
  revealed. Because the chain is append-only and timestamped, it is cryptographically
  evident that the provisional judgment predates the reveal — this is the
  anti-anchoring guarantee.
- **Stage B (comparison):** the reviewer is shown fields 13–15 and records
  `comparison_outcome` (closed enum: `agree`, `disagree_unsafe_recommendation`,
  `disagree_overcautious_recommendation`, `disagree_wrong_abstention`,
  `facts_insufficient_to_judge`, `defect_in_facts_suspected`), `error_owner`
  (`olympus`, `fact_source`, `schema`, `ambiguous`, `none`), and
  `reviewer_uncertainty`. The stage-B entry references the stage-A entry's digest;
  a stage-B entry whose referenced stage-A digest is absent or later in the chain is
  invalid.
- **Disagreement between reviewers** is data, not an error: multiple reviewers'
  entries for the same `event_ref` coexist, and divergence feeds the disagreement
  metrics. Dual review is required for high-risk classes (open question 20 remains
  a workflow gate).

## 5. Anchoring-risk note for validation-status cases (dispositions P3-3)

For records with `schema_validation_status != valid`, cross-field rule 7 fixes the
correct recommendation class, so a stage-A reviewer can infer the recommendation.
For exactly these cases the rubric scores rule conformance rather than independent
judgment (`provisional_disposition` is expected to be `should_abstain` or equivalent),
so the residual anchoring has no effect on any agreement metric. This risk is
accepted with rationale rather than mitigated further.

## 6. Access and privacy

- Ledger access is restricted to the review environment roles; there is no reverse
  lookup from `event_ref` to Hermes data (privacy control 7 unchanged).
- Published metrics derived from the ledger obey the same aggregation rules as v2
  metadata: cell minimum k>=5, coarsening before suppression beyond 20 percent, and
  no reviewer pseudonym appears in any published aggregate.
- Retention follows the certification retention period plus challenge window; ledger
  destruction follows the approved deletion process with manifest confirmation.

## 7. Gate

This store design must pass privacy and security review before any Phase 5 pilot.
Nothing here authorizes creating the store, connecting it to any system, or running
adjudication.
