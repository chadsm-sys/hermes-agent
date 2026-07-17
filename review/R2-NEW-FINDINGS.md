# R2 Focused Re-Review — New Findings

New defects found in the R2 deliverables at commit `0a93ee96`. None is P0 or P1.
Both P2 items are machine-schema-level specification gaps whose natural resolution
point is the fixture-prototype phase itself; they must be closed there before any
adversarial fixture for the affected classes is generated.

## P2

### NEW-1 (P2) — §6 prose and §7 rules disagree on observe-only under indeterminate facts

`governance_metadata_schema_v2_r2.md` §6 states that observe-only recommendations are
"impermissible whenever any governance fact is failed, conflicted, or indeterminate."
The rules in §7 do not fully deliver that claim:

- Rule 4 prohibits only **allow-like** (not observe-only) when
  `policy_conflict_indicator=unknown`.
- No rule prohibits observe-only when `governance_action_class=unknown` or
  `target_classification=unknown`.

Authority, contract, evidence, and schema indeterminacy are covered (rules 3, 5, 6,
7), so the gap is limited to the three cases above. Because the rules are the
operative normative layer, the current text under-enforces relative to its own stated
intent — an `unknown` action class with `continue_read_only_observation` would pass
validation while §6 says it must not. Fail-closed certification labeling (rule 10)
still prevents such a record from yielding a definitive correctness label, so this is
not an unsafe-approval channel, but a normative contradiction in a governance schema
is a defect.

**Required fix (either direction, chosen explicitly):** add the missing prohibitions
to rules 1/4 (strict reading), or weaken §6's prose to enumerate exactly which
indeterminate facts exclude observe-only (lenient reading, with rationale). Must be
resolved when the machine schema encodes the cross-field rules, before fixtures for
these cases are generated.

### NEW-2 (P2) — No representation rule for uncanonicalizable malformed submissions

`schema_validation_status` exists to make malformed-metadata cases observable
"without retaining malformed values" (v2 §5.12), and the adversarial fixture list
requires fixtures for duplicate keys, invalid types, and additional properties. But
under `ogm-canon/1`, a fact payload containing a JSON number, boolean, null,
duplicate key, or extra property is **uncanonicalizable** — so `provenance_identifier`
cannot be computed over it, and the corpus record for exactly these cases cannot be
constructed as specified. R2 states that an invalid fact payload "still yields a
record" (S3) but never says what value occupies a field slot whose submitted value
is unrepresentable or absent.

**Required fix:** specify the quarantine-normalization rule — e.g., the assembler
replaces every unrepresentable or missing field value with a reserved sentinel (a
new closed enum value such as `unrepresentable`, prohibited outside
`schema_validation_status != valid` records), records the bounded first-error class
in field 12, and computes digests over the normalized payload; the raw malformed
submission is never retained. Cross-field rule 7 then applies unchanged. Must be
resolved in the machine-schema task before adversarial fixture classes 1–4 can be
built.

## P3

### NEW-3 (P3) — Set-digest input segments underspecified

Digest spec §6 says segments are "the per-record identifier"; state explicitly that
this is the full field value including the `prov-`/`adv-` prefix.

### NEW-4 (P3) — Fixture runs reuse the `v1_source_stream_digest` key

For `corpus_class=fixture` the replay payload carries the fixture-manifest digest
under the key `v1_source_stream_digest`. Unambiguous (corpus_class disambiguates,
domains differ) but misleading; rename to a neutral key (e.g.,
`corpus_source_digest`) in the machine schema.

### NEW-5 (P3) — Fact-only cross-field validation subset unenumerated

S3 validates "the fact-only subset of cross-field rules" without listing which rules
(or rule fragments) that subset contains. Enumerate it in the machine schema.

### NEW-6 (P3) — `uncertainty_reason` derivation domain imprecise

R2 §4.3 derives field 15 from "fields 5–12 and 14", but the
`missing_governance_metadata` reason plausibly depends on fields 3–4 sentinel states.
Specify the exact derivation function per input combination.

### NEW-7 (P3) — `schema_version` constant unchanged across design revisions

Pre-R2 and R2 records share the constant `olympus-governance-metadata/v2`;
distinguishability rests on field count, typing, and digest domains. Acceptable
because zero pre-R2 records exist, and documented in R2 §2; the machine schema
should additionally pin `canonicalization_profile` + digest-domain set as the
operative profile identity.

### NEW-8 (P3) — Adjudication checkpoint cadence unspecified

`human_adjudication_store.md` requires periodic anchored checkpoints but sets no
cadence or trigger (per session, per N entries, per run close). Specify before the
Phase 5 pilot design.

## Explicit non-findings

Attacks attempted with no defect found: digest cycles and hidden self-inclusion
(none; topology verified), manifest spoofing inside the anchoring model (correctly
gated), downgrade to v1 or pre-R2 acceptance (fail-closed, no consumer fallback),
fixture/live namespace confusion (mutually exclusive corpus classes, cross-rejection
both directions), Olympus-generated ground truth (structurally excluded at S5/S6 and
in the ledger), stage-A reviewer anchoring (commitment-before-reveal chain holds),
ledger mutation gaps beyond checkpoint cadence (chain plus anchored checkpoints
cover edit, delete, reorder, truncate), and privacy/correlation regressions (field
18 adds digest-class data only; ledger timestamps are confined and excluded from
aggregates).

## Independence caveat

These findings come from a same-session self-review; see
`review/R2-HASH-ATTESTATION.txt`. External confirmation is required before any gate
beyond the offline fixture prototype.
