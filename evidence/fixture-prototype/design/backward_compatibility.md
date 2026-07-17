# Governance Metadata Schema v2 — Backward Compatibility

## Compatibility model

V2 is a separate sidecar, not a replacement or in-place evolution of `olympus-live-export/v1`. This preserves byte identity, read-only publication, replay hashes, consumers, and all existing certifications.

## Version negotiation

1. Consumers declare an exact accepted profile: `olympus-governance-metadata/v2`.
2. Producers emit the exact `schema_version` constant in every sidecar record.
3. Decision-quality certification requires v2 and must not fall back to v1.
4. V1-only operation remains valid for live-shadow/advisory observation but reports v2 decision quality as `NOT_AVAILABLE`.
5. Unknown major/minor versions fail closed and are not auto-coerced.
6. No network negotiation is required; negotiation occurs by manifest/profile declaration over immutable artifacts.

## Migration strategy

- **Phase 0 — current:** v1 certified stream only; decision quality blocked by metadata insufficiency.
- **Phase 1 — design review:** approve taxonomy, provenance, privacy, security, and source independence. No code.
- **Phase 2 — fixture-only prototype:** generate synthetic/nonproduction fixtures outside the certified exporter; no Hermes connection.
- **Phase 3 — independent boundary certification:** separately review any proposed metadata producer and prove prohibited fields are never selected or emitted.
- **Phase 4 — dual publication:** continue unchanged v1 stream and separately publish immutable v2 sidecar.
- **Phase 5 — decision-quality certification:** join by opaque event reference, run replay, and perform blinded human adjudication.

No phase is automatically authorized by this design.

## Compatibility rules

- V1 files and hashes must remain untouched.
- V2 must never be written into `exporter/live_events.jsonl`.
- A v2 record cannot exist without one matching v1 event in the declared source stream.
- One v1 event may have at most one record per exact v2 profile and provenance set.
- Extra/unknown fields are invalid.
- Enum meanings are immutable within a version.
- Taxonomy/registry changes alter provenance and replay IDs even if visible enums do not change.
- Missing v2 metadata never invalidates v1; it only prevents v2 certification.

## Deprecation policy

- Certified v1 is not deprecated by v2.
- A v2 field or enum may be deprecated only in documentation for at least one certification cycle; its meaning cannot change.
- Removal, renamed fields, changed enum semantics, canonicalization changes, or privacy expansion require v3.
- Additions require a separately named profile (for example `v2.1`) and explicit consumer opt-in; decision-quality certification pins one exact profile.
- Old profiles remain replayable with their original manifests and schemas.

## Downgrade protection

- Certification manifest pins exact schema/profile, taxonomy digests, source stream digest, provenance set digest, and replay digest.
- Missing sidecar, mismatched profile, or v1-only record results in `NOT_AVAILABLE`/`BLOCKED`, never implicit acceptance.
- User-controlled version strings are not trusted; validators parse exact constants.

## Failure behavior

Duplicate event references, unknown enums, malformed identifiers, provenance mismatch, replay mismatch, unsupported versions, and cross-field violations fail closed. They do not trigger migration, guessing, or content lookup.

In the fixture-only profile, malformed or uncanonicalizable raw inputs are not omitted. NEW-2 maps each one deterministically into the separate `olympus-governance-quarantine/v2` namespace so provenance and replay remain computable. A quarantine envelope never becomes a v2 sidecar record and never changes v1 compatibility. Exact behavior is defined only in `design/fixture_profile_normative_resolutions.md`.