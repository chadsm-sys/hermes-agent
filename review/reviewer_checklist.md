# Governance Metadata Schema v2 — Reviewer Checklist

Reviewer records **PASS**, **FAIL**, or **N/A** with a short bounded note. Any critical FAIL blocks approval.

## Scope and invariants

- [ ] CRITICAL: Deliverables are documentation only; no code/schema JSON/runtime implementation was added.
- [ ] CRITICAL: Hermes, certified exporter, live event stream, replay manifest, contracts, policies, and services are unchanged.
- [ ] CRITICAL: Olympus remains inactive and production authority denied.
- [ ] CRITICAL: No execution, callback, outbound, credential, or production-target field exists.

## Field necessity and typing

- [ ] Every proposed field has type, allowed values, source, native/derived status, justification, privacy impact, security impact, replay impact, certification benefit, and requirement class.
- [ ] All values use closed vocabularies or opaque bounded identifiers.
- [ ] Unknown/indeterminate values are explicit and fail closed.
- [ ] No field is retained solely because it is convenient.
- [ ] Cross-field validity rules prevent unsafe allow outcomes.

## Privacy

- [ ] CRITICAL: No prompts, message content, reasoning, rationale text, tool names/arguments, credentials, secrets, or raw identifiers are proposed.
- [ ] Exact targets, principals, policy IDs, contract IDs, and evidence details are excluded.
- [ ] Action/target/authority classes are sufficiently coarse.
- [ ] Correlation controls cover event, replay, provenance, and time linkage.
- [ ] Event-level retention, access, and deletion requirements are specified.
- [ ] Aggregate small-cell suppression is acceptable.

## Security and abuse

- [ ] CRITICAL: Authority and recommendation values cannot be interpreted as authorization.
- [ ] Fact provenance is independent of Olympus recommendations.
- [ ] Replay/provenance IDs are recomputed, never trusted as bearer values.
- [ ] Downgrade, spoofing, duplicate-key, additional-field, and unknown-version behavior fails closed.
- [ ] Circular certification and reviewer anchoring are addressed.
- [ ] Metadata transplant and stale-authority replay are addressed.

## Replay

- [ ] Canonicalization is deterministic and excludes runtime latency/current timestamps.
- [ ] V2 replay binds source stream, sidecar facts, schema/profile, and pinned dependency digests.
- [ ] Existing v1 replay bytes/hashes remain untouched.
- [ ] Identical inputs produce identical provenance and replay identifiers.

## Compatibility

- [ ] V2 is a separate sidecar and never substituted for v1.
- [ ] Exact-version negotiation and no-fallback rules are clear.
- [ ] Missing v2 does not invalidate v1; it blocks only v2 certification.
- [ ] Deprecation and major-version rules prevent semantic drift.

## Certification usefulness

- [ ] Schema supports all required action, policy, conflict, contract, evidence, authority, malformed-input, target, recommendation, confidence, and uncertainty cases.
- [ ] Human ground truth remains a separate blinded adjudication artifact.
- [ ] Minimum metrics can be computed without sensitive content.
- [ ] Source availability and reviewer expertise remain explicit gates.

## Final reviewer recommendation

- [ ] `APPROVE_FOR_FIXTURE_DESIGN_ONLY`
- [ ] `NEEDS_REVISION`
- [ ] `BLOCKED`

Approval here never authorizes implementation or exporter/Hermes changes.