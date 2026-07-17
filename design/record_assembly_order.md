# Schema v2 R2 — Normative Record Assembly Order

**Status:** Design only. Resolves independent-review finding P2-3 (construction
sequence unstated; recompute-don't-trust unstated for `schema_validation_status`).

## 1. Roles

- **Fact producer:** independent source of governance facts (fields 3–11). Never
  Olympus. Separately certified in a future boundary review.
- **Independent validator:** strict schema/cross-field validator. Never Olympus.
- **Assembler:** deterministic certification pipeline component that computes digests
  and freezes records. Never Olympus. Cannot amend facts or advisory values.
- **Olympus advisory evaluator:** produces fields 13–15 only, from frozen facts.
- **Consumer:** any downstream reader (packet builder, finalizer, auditor).

Separation-of-duties rules from `design/security_review.md` apply unchanged.

## 2. Normative construction sequence

Each stage must complete for all inputs it consumes before its outputs exist; no stage
may retroactively modify an earlier stage's output. Field numbers per R2 §3.

- **S1 — Event binding.** Confirm `event_ref` resolves exactly once in the declared
  corpus (`corpus_class` fixed for the run; live and fixture namespaces never mix).
- **S2 — Fact acquisition and freeze.** The fact producer emits typed values for
  fields 3–11 with envelope fields 1–2. Values derive only from approved non-content
  sources; if a fact is only obtainable from Olympus or from prohibited content, it is
  recorded as `unknown`/`indeterminate`.
- **S3 — Producer-time validation.** The independent validator validates the fact
  payload (fields 1–11): types, enum membership, pattern conformance, and the
  fact-only subset of cross-field rules. The first deterministic error class (or
  `valid`) is stamped as field 12. An invalid fact payload still yields a record —
  malformed-input cases must remain observable — but rule 7 then constrains the
  recommendation.
- **S4 — Fact provenance.** The assembler computes field 17 over fields 1–12 plus the
  run pin block (`design/digest_domain_specification.md` §4). Fields 1–12 and 17 are
  now frozen.
- **S5 — Advisory evaluation.** Olympus receives the frozen fields 1–12 and 17 (and
  nothing else from the certification stream) and emits fields 13–15. Olympus never
  sees human adjudication data (`design/human_adjudication_store.md`).
- **S6 — Advisory freeze.** The assembler verifies field 15 against its normative
  derivation (R2 §4.3), then computes field 18 over fields 13–15 chained to
  `event_ref` and field 17 (§5 of the digest specification). Fields 13–15 and 18 are
  now frozen.
- **S7 — Run assembly.** After S6 completes for every record in the run, the assembler
  orders records by `event_ref`, computes `fact_set_digest` and
  `advisory_set_digest`, and writes the run manifest: schema version,
  canonicalization profile, `corpus_class`, pin block, source stream (or fixture
  manifest) digest, ordered per-record digest lists, and both set digests.
- **S8 — Replay stamp and anchor.** The assembler computes field 16 and stamps the
  identical value into every record; the completed run manifest is anchored per
  `design/provenance_authenticity_plan.md`. The run is now immutable; any correction
  is a new run with a new `replay_identifier`.

## 3. Well-foundedness

The digest dependency chain is acyclic by stage order: 17 (S4) → 18 (S6) → set digests
(S7) → 16 (S8). Field 16 is an input to nothing; field 17 never covers advisory
fields. This resolves both defective readings identified in review finding P1-1
(unbound advisory fields, and self-referential replay digest).

## 4. Consumer recomputation obligations

On every read for any certification purpose, a consumer must, in order, and failing
closed at the first failure:

1. Reject records whose `schema_version` is not the exact expected constant.
2. Re-validate the full record: strict types, closed vocabularies, patterns,
   `additionalProperties=false`, duplicate-key rejection, and all cross-field rules
   (R2 §7). The embedded field 12 is never trusted as a substitute; it is compared
   against the recomputed producer-time result where reproducible, and a mismatch is
   recorded as `invalid_derived_field`.
3. Recompute field 15 from the normative derivation; mismatch fails closed.
4. Recompute fields 17, 18, and 16 per the digest specification, using the anchored
   run manifest's pin block and ordered lists; any mismatch fails closed and is
   reported as a tamper finding with the affected `event_ref`.
5. Verify run-level uniqueness of `event_ref` and identical field 16 across the run.

No consumer may repair, coerce, default, or guess a value at any step.

## 5. Prohibited orderings

- Olympus must never receive a record before S4 completes (prevents advisory
  influence on facts or provenance).
- Field 18 must never be computed by, or shared for computation with, the advisory
  evaluator.
- The run manifest must never be written before every record's S6 is complete.
- No stage may query live authority, live policy state, or Hermes content; stages
  consume only the frozen inputs named here.
