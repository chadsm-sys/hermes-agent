# NEW-1 / NEW-2 Resolution Record

**Prototype branch:** `prototype/olympus-schema-v2-offline-fixture-20260717`  
**Immutable base:** `b14e887a331241306e5cbfa93b7023bda392b810`  
**Normative profile:** `design/fixture_profile_normative_resolutions.md`

## NEW-1 — observe-only versus indeterminate states

### Inconsistency found

The published prose separately said that unknown/indeterminate facts could be admitted for observation, that no allow should be issued from unknown facts, and that correctness labels required determinate facts. It did not classify `continue_read_only_observation` consistently as non-authorizing or define one precedence rule across policy, conflict, contract, evidence, authority, and action-class indeterminacy.

### Resolution

One mandatory precedence and decision matrix now governs every combination. Explicit deny/conflict/invalid states override observation; simulation allow requires all determining facts; protected or authorizing actions fail closed; and only local/mock read-only observation may continue provisionally with a non-`none` uncertainty reason. Provisional observation is never an allow, approval, definitive correctness label, or production authority.

## NEW-2 — malformed or uncanonicalizable inputs

### Inconsistency found

The published package required canonicalization and duplicate-key rejection but did not define how invalid UTF-8, invalid JSON, duplicate keys, unsupported schema versions, malformed field values, or uncanonicalizable text entered provenance and replay calculations. Provenance/replay could therefore become non-computable exactly where adversarial evidence mattered most.

### Resolution

Malformed inputs now enter a separate `olympus-governance-quarantine/v2` namespace. The deterministic envelope contains only error status, ordinal, raw SHA-256, byte length, a hash-derived `quarantine-` sentinel event reference, profile digests, and a `provq-` digest. Raw content is not echoed. Valid-item replay excludes only the replay field to prevent circularity; quarantine-item replay binds the entire envelope. Replay remains computable for every input byte string.

## Scope

These resolutions govern only this offline fixture prototype. They do not modify or activate Hermes, exporters, runtime behavior, policies, contracts, production configuration, or Olympus authority.
