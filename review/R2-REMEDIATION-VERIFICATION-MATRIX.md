# R2 Remediation Verification Matrix

Verification of every prior-review finding against the R2 deliverables at commit
`0a93ee96`. "Verified" means the resolution is present, normative, and withstands
the adversarial checks of this re-review.

## Prior P1

| ID | Prior finding | R2 resolution point | Verified | Notes |
|---|---|---|---|---|
| P1-1 | Replay-digest domain ambiguous; advisory fields unbound or digest self-referential; substitution detection required engine re-execution | `digest_domain_specification.md` (exact domains, field 18, set digests, self-exclusion); `record_assembly_order.md` §3 | **YES** | Full analysis in `R2-DIGEST-INTEGRITY-REVIEW.md`; both defective readings eliminated by construction; detection is hash-only and localizing |

## Prior P2

| ID | Prior finding | R2 resolution point | Verified | Notes |
|---|---|---|---|---|
| P2-1 | Mixed boolean/string `policy_conflict_indicator` | R2 §4.2 (`no_conflict`/`conflict`/`unknown`); strings-only rule in digest spec §1 | **YES** | Record is now single-typed in every field; open question 8 closed |
| P2-2 | "Allow category" undefined; observe-only escaped denied authority | R2 §6 partition; §7 rules 3–6 | **YES, with successor finding** | The prior gap (denied/approval-required/indeterminate/error authority vs observe-only) is closed by rule 3. New finding NEW-1 identifies a smaller residual prose/rule mismatch for three indeterminate-fact cases — tracked as a new P2, not a failure of the original remediation |
| P2-3 | Assembly order unstated; recompute-don't-trust missing for field 12 | `record_assembly_order.md` S1–S8, §4, §5; R2 §7 rule 11 | **YES** | Roles, sequence, prohibited orderings, and per-field recomputation obligations all normative |
| P2-4 | `live-` prefix would cover synthetic fixtures | R2 §4.1; digest spec §7 (`corpus_class`) | **YES** | Mutually exclusive namespaces with rejection in both directions; no fixture generated |
| P2-5 | Authenticity mechanism undocumented | `provenance_authenticity_plan.md` | **YES (as plan)** | Custody and dual-signature options, verification obligations, threat closure, gate placement (fixture: custody-lite; Phase 3+: mandatory); concrete key custody correctly deferred to Phase 3 |
| P2-6 | Human adjudication artifact unspecified | `human_adjudication_store.md` | **YES (as contract)** | Append-only hash chain, UTC timestamps, role+pseudonym, stage-A commitment before reveal, disagreement/uncertainty enums, checkpoint anchoring, no Olympus read path |

## Prior P3

| ID | Prior finding | Disposition in R2 | Verified |
|---|---|---|---|
| P3-1 | `uncertainty_reason` redundancy | Declared derived consistency-check; recompute + fail closed (R2 §4.3) | **YES** (precision gap tracked as NEW-6, P3) |
| P3-2 | `none`/`unknown` tier ordering | Total order; incomparable `unknown` forces `indeterminate`; `requested=none` forces `not_applicable` (rule 2) | **YES** |
| P3-3 | Validation-status anchoring | Accepted with rationale; rubric scores rule conformance for invalid cases (R2 §9; store §5) | **YES** (justified residual risk) |
| P3-4 | Multiple provenance sets per event | One record per event per run; verdict cites one anchored run (rule 1; diff doc) | **YES** |
| P3-5 | `not_scored` consistency | Biconditional rule 9 | **YES** |
| P3-6 | Sparse-corpus k=5 | Floor retained; coarsen-before-suppress rule; adequacy kept as privacy-gate question (R2 §9) | **YES** (justified residual risk, gated) |
| P3-7 | Out-of-repo v1 certification claims | Marked as inherited claims requiring re-attestation before Phase 3+ (R2 §9) | **YES** (justified residual risk, gated) |

## Summary

All 1 P1 + 6 P2 + 7 P3 prior findings are demonstrably resolved or explicitly
dispositioned with justified residual risk. The re-review surfaced 2 new P2 and 6
new P3 findings (`R2-NEW-FINDINGS.md`); none reopens a prior finding and none is a
P0/P1.
