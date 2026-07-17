# R2 Digest Integrity Review

Scope: `design/digest_domain_specification.md` and `design/record_assembly_order.md`
at commit `0a93ee96`, checked against the P1 remediation requirements and attacked
for new defects.

## 1. Input domains — exact, with one representational gap

Every digest now has an enumerated key set: `provenance_identifier` over fields 1–12
plus pin block; `advisory_output_digest` over `{schema_version, event_ref,
provenance_identifier, recommendation_category, confidence_bucket,
uncertainty_reason}` plus pin block; set digests over ordered identifier lists;
`replay_identifier` over `{advisory_set_digest, canonicalization_profile,
corpus_class, fact_set_digest, schema_version, v1_source_stream_digest}` plus pin
block. No prose-only digest definition remains. **PASS**, with finding NEW-2 (below):
the domain is exact for well-formed values but the spec does not say what value
occupies a field slot when the original submission was uncanonicalizable.

## 2. Canonical serialization and ordering — deterministic

`ogm-canon/1` fixes encoding, key sorting (Unicode code point), whitespace, and the
strings-only value rule; the byte-level concatenation formula (domain, 0x0A,
payload segments) is stated once and used consistently in every definition. Record
ordering for set digests is ascending lexicographic `event_ref`, unique per run by
cross-field rule 1, so the order is total and deterministic. **PASS.** Minor: §6 says
set-digest segments are "the per-record identifier" — read naturally this is the full
field value including the `prov-`/`adv-` prefix, but it should say so (NEW-3, P3).

## 3. Domain separation — sound

Five distinct, versioned constants (`*/v2r2`); no two digest types share a domain;
pre-R2 domains retired unused, so cross-revision collision is impossible. The
human-adjudication chain uses its own domain (`olympus-human-adjudication/v1:chain`).
**PASS.**

## 4. Acyclicity and replay self-exclusion — verified by construction

Dependency chain: field 17 (inputs: fields 1–12) → field 18 (inputs: 1, 2, 17,
13–15) → set digests (inputs: lists of 17 and 18 values) → field 16 (inputs: set
digests + run constants). Field 16 appears in no input set, including its own; no
digest consumes a full record. I searched for hidden cycles (e.g., pin block
containing a digest derived from records — it does not; all eight pins are external
dependency digests) and found none. The assembly order S4→S6→S7→S8 enforces the same
topology temporally. **PASS.**

## 5. Advisory binding and post-freeze substitution detection — resolved as required

Fields 13–15 are bound at record level (field 18, chained to `event_ref` and field
17, so a valid advisory digest cannot be transplanted to another event or a mutated
fact set) and at run level (`advisory_set_digest` → `replay_identifier`, with the
ordered per-record digest list in the manifest giving localization). The §10
detection argument holds by inspection: mutating any advisory value changes the
recomputed field 18, which mismatches the anchored manifest list without any
advisory-engine execution. The prior review's engine-determinism assumption is fully
discharged. Manifest self-consistency attack (regenerate manifest to match forged
records) is correctly pushed to the anchoring mechanism, which is mandatory for live
runs and custody-lite for fixtures — acceptable for the fixture-prototype scope this
verdict can authorize. **PASS.**

## 6. Anti-circularity — preserved

Field 17 excludes fields 13–15, 16, 18; Olympus receives only frozen fields 1–12 and
17 (S5); field 18 is computed by the assembler, never the advisory evaluator (S6 and
prohibited-orderings list); ground truth remains the external human ledger with no
Olympus read path. Olympus output influences nothing that certifies Olympus.
**PASS.**

## 7. Recomputation obligations — complete

Digest spec §9 plus assembly order §4 name every recomputable field (12, 15, 16, 17,
18), the fail-closed consequence, the tamper-reporting requirement, and offline
verifiability from record set + manifest + specification. **PASS.**

## Verdict on P1 remediation

**P1-1 is demonstrably resolved.** Two new P2-severity specification gaps were found
during this review (NEW-1, NEW-2 in `review/R2-NEW-FINDINGS.md`); neither reopens
the P1 defect class.
