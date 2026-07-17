# Schema Diff: Reviewed v2 Design to Revision 2 (R2)

**Status:** Design comparison only. The reviewed package (commit `67cc8a13`) is
unchanged; R2 supersedes it by adding documents on a new branch.

## Summary

R2 changes nothing about the v1 stream, the sidecar architecture, the privacy
exclusions, the trust model, or the approval boundary. It corrects the digest
construction, tightens typing and cross-field semantics, adds one integrity field,
and specifies three previously deferred artifacts (assembly order, human adjudication
store, authenticity plan).

## Field-level changes

| Field | Reviewed v2 | R2 | Reason |
|---|---|---|---|
| `event_ref` (2) | `^live-[a-f0-9]{24}$` | `^(live|fixture)-[a-f0-9]{24}$` with mutually exclusive corpus classes | P2-4: fixtures must not masquerade as live-bound records |
| `policy_conflict_indicator` (6) | boolean `true`/`false` or string `"unknown"` | closed string enum `no_conflict`, `conflict`, `unknown` | P2-1 and open question 8: single-type canonicalization |
| `uncertainty_reason` (15) | derived; redundancy unstated | declared derived consistency-check field; consumers recompute; mismatch fails closed | P3-1 disposition |
| `replay_identifier` (16) | hash over "v2 metadata-set digest" (ambiguous) | exact payload: fact-set digest, advisory-set digest, corpus class, profile, pins; self-excluded by construction | P1: domain made exact; self-reference impossible |
| `provenance_identifier` (17) | fields "3–12" prose | exact fact payload = fields 1–12 plus pin block; advisory fields excluded | P1: domain made exact; anti-circularity retained |
| `advisory_output_digest` (18) | absent | new required field binding frozen fields 13–15 to `event_ref` and field 17 | P1: post-freeze advisory substitution detectable by hash alone |

Record size: 17 required fields to 18 required fields. No other field's allowed
values change.

## New normative structures

| Structure | Where | Reason |
|---|---|---|
| Canonicalization profile `ogm-canon/1` | `digest_domain_specification.md` §1 | P1: byte-exact serialization; strings-only records |
| Domain separators `*/v2r2` (5 constants) | `digest_domain_specification.md` §2 | P1: versioned, collision-free domains |
| Pin block (8 pinned digests) | `digest_domain_specification.md` §3 | P1: exact dependency binding formerly prose |
| Run manifest with ordered per-record digest lists | `digest_domain_specification.md` §6 | P1: tamper localization, not just detection |
| Recommendation category partition (allow-like, observe-only, deny-like, indeterminate-class) | R2 §6 | P2-2 |
| Normative assembly sequence S1–S8 with role separation | `record_assembly_order.md` | P2-3 |
| Consumer recomputation obligations (fields 12, 15, 16, 17, 18) | `record_assembly_order.md` §4; digest spec §9 | P2-3 |
| Human adjudication store contract (append-only, hash-chained, two-stage blind) | `human_adjudication_store.md` | P2-6 |
| Authenticity anchoring plan (custody / dual signature) with gate placement | `provenance_authenticity_plan.md` | P2-5 |

## Cross-field rule changes (reviewed §6 to R2 §7)

- Rule 1: adds corpus-class resolution and explicit duplicate handling — duplicates
  make all records for that `event_ref` ineligible (P3-4 partially; run scoping).
- Rule 2: adds total tier order `none < tier_0 < tier_1 < tier_2 < tier_3`,
  incomparable `unknown` forcing `indeterminate`, and `requested=none` forcing
  `not_applicable` (P3-2).
- Rule 3: broadened from prohibiting only `allow_simulation_only` to prohibiting both
  allow-like and observe-only under `approval_required`, `denied`, `indeterminate`,
  or `evaluation_error` authority decisions (closes the P2-2 gap where
  `continue_read_only_observation` could coexist with denied authority).
- Rules 4–6: restated against the normative category partition; conflict/contract/
  evidence failures now prohibit observe-only as well as allow-like outcomes;
  `policy_conflict_indicator=unknown` prohibits allow-like.
- Rule 9 (new): `confidence_bucket=not_scored` if and only if
  `uncertainty_reason=not_scored` (P3-5).
- Rule 11 (new): embedded values of fields 12, 15, 16, 17, 18 are claims; consumers
  recompute; mismatch fails closed (P2-3).

## Run and duplicate semantics

- Within one certification run: exactly one record per `event_ref`; one
  `replay_identifier` stamped in all records.
- Across runs: the anchored run manifest is authoritative; a certification verdict
  cites exactly one pinned run, and records from other provenance sets are out of
  scope for that verdict (P3-4).

## Versioning treatment

The v2 profile has produced zero records; R2 redefines it before first publication,
which the backward-compatibility deprecation rules (governing certified published
profiles) do not forbid. Digest domain constants nevertheless carry `/v2r2` so pre-R2
and R2 constructions can never collide. All v1 compatibility guarantees are untouched:
v1 bytes, hashes, replay, and consumers are unaffected by every change above.

## Explicitly unchanged

Privacy exclusions and prohibited-data lists; sidecar transport; exact-version
fail-closed negotiation; `NOT_AVAILABLE` semantics for missing sidecars; the
non-authority and advisory-only normative warnings; separation of duties; the
approval gate, automatic blockers, and denied implementation/activation/production
authority.
