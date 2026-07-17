# Governance Metadata Schema v2 — Threat Model

## Assets

- Existing certified v1 exporter, immutable stream, and replay integrity
- Hermes privacy boundary and source database
- Governance facts used for independent adjudication
- Non-executable Olympus recommendations
- Reviewer independence and certification credibility

## Adversaries

- Malicious or compromised metadata producer
- Misconfigured reviewer/certification tooling
- Insider attempting to infer operational patterns
- Consumer attempting to convert descriptive metadata into authority
- Attacker replaying, downgrading, splicing, or spoofing records

## Threats and mitigations

### Information leakage

**Risk:** Coarse action, target, authority, and timing combinations reveal sensitive activity.  
**Mitigations:** no content/arguments/identity/target values; omit duplicated timestamp; restricted event-level access; aggregate minimum cell size; bounded retention.

### Privilege escalation

**Risk:** `authority_available`, `authority_decision`, or recommendation fields are mistaken for authorization.  
**Mitigations:** no credentials/handles; normative non-authority labels; architecture prohibition on actuator consumers; stale point-in-time semantics; production authority remains denied.

### Inference attacks

**Risk:** Rare enum combinations identify a person, workflow, policy, or incident.  
**Mitigations:** coarse taxonomies; no exact policy/contract/evidence IDs; suppress small aggregate cells; merge rare target classes in published reports.

### Metadata correlation

**Risk:** `event_ref`, provenance ID, replay ID, and v1 timestamps allow linkage across datasets.  
**Mitigations:** keep event-level records confined; avoid public hashes when not required; prohibit reverse lookup; retention/deletion controls; no new stable subject identifier.

### Replay abuse

**Risk:** A valid old record is replayed as current authority or recommendation.  
**Mitigations:** identifiers are certification-only; bind replay to complete immutable batch and schema/profile; no actuator acceptance; manifest freshness is a review concern, not authority.

### Downgrade attacks

**Risk:** A producer labels deficient data as v1 or omits v2 fields to avoid checks.  
**Mitigations:** decision-quality profile requires exact v2 version; no fallback; absence yields `NOT_AVAILABLE`; unknown versions fail closed.

### Schema spoofing

**Risk:** Extra fields, alternate enums, duplicated keys, ambiguous JSON numbers, or forged hashes alter meaning.  
**Mitigations:** strict fixture validator; `additionalProperties=false`; duplicate-key rejection; strings/booleans only for v2 record fields; canonicalization; recomputed provenance/replay; deterministic first-error ordering; and NEW-2 namespace-separated quarantine normalization so malformed bytes remain digest-bound without being repaired.

### Compatibility failures

**Risk:** v1 consumers parse v2, v2 consumers reinterpret v1, or taxonomy changes silently.  
**Mitigations:** separate sidecar/media type; exact version dispatch; pinned taxonomy digests; additive minor revisions only; major version for semantic changes.

### Circular certification

**Risk:** Olympus creates both the governance facts and the recommendation, producing self-agreement.  
**Mitigations:** facts 3–12 require independent source; provenance excludes recommendation fields; source facts frozen first; human adjudication separate and blinded where practical.

### Label leakage and automation bias

**Risk:** Reviewers see recommendation/confidence before judging facts.  
**Mitigations:** two-stage interface: independent provisional judgment from facts, then reveal recommendation/confidence for comparison.

### Denial of certification

**Risk:** Attackers force unknown/conflict/error states.  
**Mitigations:** preserve fail-closed behavior; investigate reproducibility; never weaken privacy or validation to improve agreement.

### Observe-only ambiguity

**Risk:** Prose treats `continue_read_only_observation` as an allow in one place and as a non-authorizing observation in another, producing inconsistent handling of indeterminate states.
**Mitigations:** the offline fixture profile MUST apply the single precedence matrix in `fixture_profile_normative_resolutions.md`; provisional observation is not allow, approval, definitive correctness, or production authority; explicit deny/conflict/invalid states still fail closed.

## Residual risks

- Coarse metadata still leaks activity category and privilege class.
- Hashes provide integrity linkage, not trusted-origin authenticity.
- Independent source availability is unproven.
- Taxonomy choices may encode policy bias.
- Human reviewers may still infer context from combinations.

These residual risks require review and controlled implementation. None justifies weakening the existing redaction boundary.

## Threat-model verdict

No inherent conflict prevents a privacy-preserving design. Implementation must be blocked if required typed facts do not already exist independently and can only be produced by inspecting prohibited content or Olympus reasoning.