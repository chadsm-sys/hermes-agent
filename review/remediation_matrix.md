# Schema v2 R2 — Independent-Review Remediation Matrix

Maps every finding of the independent adversarial review (of package commit
`67cc8a13`, verdict `SCHEMA_V2_REVISE`, dated 2026-07-17) to its R2 resolution.

Verification method key: **doc-review** = confirm by reading the cited section;
**re-review** = requires the independent reviewer's confirmation on this package.

## P1

| ID | Finding | Revision | Affected sections | Status | Rationale | Verification | Residual risk |
|---|---|---|---|---|---|---|---|
| P1-1 | Replay-digest input domain ambiguous ("metadata-set" vs "fact-set"); advisory fields 13–15 bound by no digest under one reading, self-referential digest under the other; recommendation substitution detectable only via advisory-engine re-execution | Exact byte-level digest domains defined; new `advisory_output_digest` (field 18) binds frozen advisory outputs to `event_ref` and `provenance_identifier`; `replay_identifier` binds ordered fact-set and advisory-set digests and appears in no digest input including its own; recomputation is hash-only | `digest_domain_specification.md` (all), R2 §4.4–4.5, `record_assembly_order.md` §3 | RESOLVED | Both defective readings eliminated by construction: dependency chain 17→18→set digests→16 is acyclic, and every advisory value is digest-bound at record and run level | re-review; the §10 detection argument is checkable by inspection | Hash binding still proves integrity, not origin; origin anchoring is P2-5's mechanism, mandatory before live runs |

## P2

| ID | Finding | Revision | Affected sections | Status | Rationale | Verification | Residual risk |
|---|---|---|---|---|---|---|---|
| P2-1 | Mixed boolean/string typing of `policy_conflict_indicator` | Closed string enum `no_conflict`/`conflict`/`unknown`; records are strings-only in every field | R2 §4.2; digest spec §1 | RESOLVED | Single-type records simplify canonicalization and strict validation; closes open question 8 | doc-review | None identified |
| P2-2 | "Allow category" undefined; `continue_read_only_observation` could coexist with denied authority | Normative four-way partition (allow-like, observe-only, deny-like, indeterminate-class); rules 3–6 rewritten against it; observe-only prohibited whenever any fact is failed, conflicted, or indeterminate | R2 §6, §7 | RESOLVED | Continuing as normal must never conceal a governance defect | doc-review | Partition choices for future categories must be assigned at addition time (rule stated) |
| P2-3 | Record assembly order unstated; recompute-don't-trust unstated for `schema_validation_status` | Normative S1–S8 sequence with role separation and prohibited orderings; consumer recomputation obligations for fields 12, 15, 16, 17, 18 | `record_assembly_order.md` (all); R2 §7 rule 11 | RESOLVED | Construction is now well-founded and consumers can never inherit producer claims | doc-review | Pipeline conformance to S1–S8 is an implementation property, gated at Phase 3 |
| P2-4 | `event_ref` `live-` prefix conflates future synthetic fixtures with live-bound records | `fixture-` namespace with mutually exclusive `corpus_class` per run; live runs reject fixture refs and vice versa | R2 §4.1; digest spec §7 | RESOLVED | Namespace separation by construction; no fixtures generated | doc-review | None identified for design phase |
| P2-5 | Provenance authenticity (signing/custody) deferred without a documented mechanism | Documented custody (Option A) and detached dual-signature (Option B) mechanisms, verification obligations, threat closure, and gate placement: non-blocking for fixtures, mandatory before Phase 3+ | `provenance_authenticity_plan.md` (all) | RESOLVED as plan | Mechanism choice and key/custody procedures correctly belong to the Phase 3 boundary review; the requirement and its blocker status are now normative | doc-review | Concrete key custody design remains future work, gated |
| P2-6 | Human adjudication artifact (immutability, timestamps, attribution, anti-anchoring, mutation detection) unspecified | Append-only hash-chained ledger contract: RFC 3339 UTC timestamps, role plus per-corpus pseudonym, two-stage blind protocol with stage-A commitment before reveal, disagreement/uncertainty enums, checkpoint anchoring, no Olympus read path | `human_adjudication_store.md` (all) | RESOLVED as design contract | Stage-A hash-chain commitment makes anchoring violations cryptographically evident; labels structurally excluded from Olympus inputs | doc-review | Store implementation and reviewer workflow remain Phase 5 gates |

## P3

| ID | Finding | Disposition | Where | Status |
|---|---|---|---|---|
| P3-1 | `uncertainty_reason` deterministically derivable (redundancy) | Declared derived consistency-check field; consumers recompute; mismatch fails closed | R2 §4.3 | RESOLVED (documented redundancy) |
| P3-2 | `none`/`unknown` ordering undefined in tier comparison | Total order `none < tier_0..tier_3`; `unknown` incomparable forces `indeterminate`; `requested=none` forces `not_applicable` | R2 §7 rule 2 | RESOLVED |
| P3-3 | `schema_validation_status` lets stage-A reviewers infer the recommendation (anchoring) | Accepted with rationale: for invalid-payload cases the correct recommendation is fixed by rule, so the rubric scores rule conformance and anchoring is immaterial | R2 §9; `human_adjudication_store.md` §5 | DISPOSITIONED (accepted) |
| P3-4 | Multiple records per event across provenance sets; authoritative record unclear | One record per `event_ref` per run (duplicates fail closed); a verdict cites exactly one anchored run; other provenance sets out of scope for that verdict | R2 §7 rule 1; `schema_diff_v2_to_r2.md` | RESOLVED |
| P3-5 | No consistency rule between `confidence_bucket=not_scored` and `uncertainty_reason=not_scored` | Biconditional rule added | R2 §7 rule 9 | RESOLVED |
| P3-6 | k=5 small-cell rule unvalidated for sparse corpora | Floor retained; coarsen-before-suppress rule added (suppression above 20 percent forces class merging, never a lower k); adequacy kept as explicit privacy-gate question | R2 §9 | DISPOSITIONED (gated) |
| P3-7 | v1 "certified" claims rest on an out-of-repo mock workspace | All such statements marked as inherited claims requiring independent re-attestation (stream digest plus certification record) before Phase 3+; design validity independent of them | R2 §9 | DISPOSITIONED (gated) |

## Constraint conformance

No code, exporter, Hermes, policy, contract, or runtime change; no fixture generated;
no dependency installed; the reviewed package's 14 files are byte-identical on this
branch (verified in `review/schema-v2-r2-attestation.md`); Olympus remains inactive;
implementation and production authority remain denied.
