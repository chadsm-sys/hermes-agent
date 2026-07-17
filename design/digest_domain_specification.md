# Schema v2 R2 — Digest Domain Specification

**Status:** Design only. Normative for every digest in `olympus-governance-metadata/v2`
records under design revision R2. Resolves independent-review finding P1-1.

## 1. Canonicalization profile `ogm-canon/1`

All digest payloads are canonical JSON objects serialized under profile `ogm-canon/1`:

1. Encoding is UTF-8 with no byte-order mark.
2. The payload is a single JSON object; nested objects, arrays, numbers, booleans, and
   `null` are prohibited. Every value is a JSON string.
3. Keys are exactly the set specified for the payload — no more, no fewer. A missing
   key or an extra key makes the payload uncanonicalizable (fail closed).
4. Keys are sorted lexicographically by Unicode code point.
5. Serialization contains no insignificant whitespace: `{"k1":"v1","k2":"v2"}`.
6. Strings use the shortest JSON escaping; all payload values in this schema are
   restricted to `[a-z0-9_/.:-]` so escaping never occurs in practice, but the rule is
   stated for completeness.
7. Digest input bytes for domain `D` and canonical payloads `P1..Pn` are:
   `UTF8(D) || 0x0A || UTF8(P1) || 0x0A || ... || UTF8(Pn)` (single line-feed byte
   between segments, no trailing line feed).
8. All digests are SHA-256; identifiers render as the stated prefix plus 64 lowercase
   hexadecimal characters.

## 2. Domain separators

| Domain constant | Used for |
|---|---|
| `olympus-governance-provenance/v2r2` | `provenance_identifier` (field 17) |
| `olympus-governance-advisory/v2r2` | `advisory_output_digest` (field 18) |
| `olympus-governance-factset/v2r2` | run-level `fact_set_digest` |
| `olympus-governance-advisoryset/v2r2` | run-level `advisory_set_digest` |
| `olympus-governance-replay/v2r2` | `replay_identifier` (field 16) |

Domain constants are versioned with the design revision; any future change to input
domains requires new constants. The pre-R2 domains (`.../v2`) are retired unused — no
record was ever produced under them — so cross-revision collision is impossible.

## 3. Pin block

The **pin block** is a canonical payload of the pinned dependency digests for a run.
Every value is a 64-lowercase-hex SHA-256 string:

```json
{
  "action_taxonomy_digest": "<64 hex>",
  "advisory_engine_profile_digest": "<64 hex>",
  "authority_taxonomy_digest": "<64 hex>",
  "contract_registry_digest": "<64 hex>",
  "evidence_rules_digest": "<64 hex>",
  "policy_set_digest": "<64 hex>",
  "source_snapshot_digest": "<64 hex>",
  "target_registry_digest": "<64 hex>"
}
```

The pin block is declared once per certification run in the run manifest and is
identical for every record in the run.

## 4. `provenance_identifier` (field 17)

**Fact payload:** canonical payload containing exactly fields 1–12 by their JSON keys:
`schema_version`, `event_ref`, `governance_action_class`, `target_classification`,
`policy_evaluation_result`, `policy_conflict_indicator`, `contract_resolution_status`,
`evidence_sufficiency`, `authority_requested`, `authority_available`,
`authority_decision`, `schema_validation_status`.

**Definition:**

```text
provenance_identifier =
  "prov-" + hex(SHA256(
    UTF8("olympus-governance-provenance/v2r2") || 0x0A ||
    UTF8(canonical(pin_block)) || 0x0A ||
    UTF8(canonical(fact_payload))
  ))
```

**Exclusions (anti-circularity):** fields 13–15 (Olympus advisory outputs), field 16,
and field 18 are never inputs. Olympus output cannot influence fact provenance.

## 5. `advisory_output_digest` (field 18)

**Advisory payload:** canonical payload containing exactly:
`schema_version`, `event_ref`, `provenance_identifier`, `recommendation_category`,
`confidence_bucket`, `uncertainty_reason`.

**Definition:**

```text
advisory_output_digest =
  "adv-" + hex(SHA256(
    UTF8("olympus-governance-advisory/v2r2") || 0x0A ||
    UTF8(canonical(pin_block)) || 0x0A ||
    UTF8(canonical(advisory_payload))
  ))
```

Including `provenance_identifier` in the advisory payload chains each frozen advisory
output to the exact frozen fact set and event, so a valid advisory digest cannot be
transplanted onto a different event or a mutated fact set. Field 16 is not an input.

## 6. Run-level set digests

Records in a run are ordered by ascending lexicographic `event_ref` (unique per run by
cross-field rule 1). With `id_i` the per-record identifier of record `i` in that order:

```text
fact_set_digest =
  hex(SHA256(UTF8("olympus-governance-factset/v2r2") || 0x0A ||
             UTF8(prov_1) || 0x0A || ... || 0x0A || UTF8(prov_n)))

advisory_set_digest =
  hex(SHA256(UTF8("olympus-governance-advisoryset/v2r2") || 0x0A ||
             UTF8(adv_1) || 0x0A || ... || 0x0A || UTF8(adv_n)))
```

The full ordered lists of `prov_i` and `adv_i` values are recorded in the run manifest
so any single-record substitution is localizable, not merely detectable.

## 7. `replay_identifier` (field 16)

**Replay payload:** canonical payload containing exactly:

```json
{
  "advisory_set_digest": "<64 hex>",
  "canonicalization_profile": "ogm-canon/1",
  "corpus_class": "live",
  "fact_set_digest": "<64 hex>",
  "schema_version": "olympus-governance-metadata/v2",
  "v1_source_stream_digest": "<64 hex>"
}
```

`corpus_class` is `live` or `fixture` (see R2 §4.1). For a fixture run,
`v1_source_stream_digest` is replaced by the fixture-manifest digest under the same
key semantics documented in the run manifest.

**Definition:**

```text
replay_identifier =
  "replay-" + hex(SHA256(
    UTF8("olympus-governance-replay/v2r2") || 0x0A ||
    UTF8(canonical(pin_block)) || 0x0A ||
    UTF8(canonical(replay_payload))
  ))
```

The same `replay_identifier` value is stamped into every record of the run.

**Self-exclusion:** field 16 appears in no digest input anywhere in this
specification, including its own: the replay payload contains only set digests, which
are computed over fields 17 and 18 values — never over full records and never over
field 16. The construction is therefore well-founded: 17 → 18 → set digests → 16, with
no cycles.

## 8. Null and unknown handling

- JSON `null` is prohibited in every payload; its presence makes the payload
  uncanonicalizable and the record invalid (`invalid_type`).
- Unknown or indeterminate facts are expressed only through the closed sentinel
  strings defined per field (`unknown`, `indeterminate`, `not_scored`, `none`,
  `not_applicable`). Sentinels are ordinary string values and are digested exactly
  like any other value: an unknown fact still has exact, reproducible integrity
  identifiers.
- Omission is never a way to express absence of knowledge; every payload key is
  mandatory.

## 9. Recomputation rules

1. Embedded values of fields 16, 17, and 18 are claims. Every consumer — validator,
   adjudication packet builder, certification finalizer, and any future independent
   auditor — must recompute all three from the record's own fields, the run manifest's
   pin block and ordered digest lists, and this specification. Any mismatch makes the
   record ineligible (fail closed); a mismatch localized to one record by the manifest
   lists must be reported as a tamper finding, not silently dropped.
2. Recomputation must be possible offline from: the record set, the run manifest, and
   this document. Advisory-engine re-execution is **not** required for integrity
   verification (P1 requirement); engine re-execution remains a separate, additional
   correctness check under the replay profile.
3. `schema_validation_status` (field 12) is likewise recomputed by every consumer per
   `design/record_assembly_order.md`; the embedded value is a recorded historical
   claim about the producer-time validation, never a substitute for consumer-side
   validation.

## 10. Detection argument for post-freeze advisory substitution

Given a run manifest anchored per `design/provenance_authenticity_plan.md`:
mutating any of fields 13–15 in any record changes that record's recomputed
`advisory_output_digest` (§5); the mutated record then mismatches the manifest's
ordered advisory-digest list, `advisory_set_digest` (§6), and `replay_identifier`
(§7). Verification requires only hashing — no advisory-engine execution — and the
manifest lists identify exactly which record was altered. Mutating the manifest
itself to match is prevented by the custody/signature anchoring, which is mandatory
before any live run and recorded-by-hash for offline fixture runs.
