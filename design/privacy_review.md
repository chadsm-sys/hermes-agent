# Governance Metadata Schema v2 — Privacy Review

**Review result:** Conditionally acceptable for design review. Implementation is not approved.

## Privacy objective

Enable a reviewer to judge governance outcomes without learning what a message said, what tool arguments contained, who acted, which account/resource was targeted, or why Olympus reasoned as it did.

## Data categories

| Category | Included | Privacy treatment |
|---|---:|---|
| Content, prompts, reasoning | No | Prohibited |
| Tool names/arguments | No | Prohibited |
| Credentials/secrets | No | Prohibited |
| User/session/platform identities | No new data | Only existing opaque `event_ref` |
| Action/target | Coarse classes | Closed enums; no raw values |
| Policies/contracts | Outcome/status only | No names, IDs, text, or matched values |
| Evidence | Aggregate sufficiency only | No type, source, value, or document identity |
| Authority | Coarse tiers/results | No principal, role, group, approver, credential, or chain |
| Recommendation/confidence | Coarse categories | No rationale or raw score |
| Provenance/replay | Opaque hashes | Correlation controls required |

## Field-level privacy findings

- **Low impact:** schema version, policy result/conflict, contract status, evidence sufficiency, authority decision, validation status, recommendation category, confidence bucket, uncertainty reason.
- **Moderate inference risk:** action class, target class, authority available, replay ID, provenance ID, and event reference.
- **High-impact data excluded:** exact targets, identities, content, policy names, contract names, evidence categories, and free text.

## Inference and correlation controls

1. Keep event-level v2 records inside the certification environment.
2. Publish only aggregates when a cell contains at least 5 events; suppress smaller cells.
3. Do not combine event timestamps with action, target, and authority classes in external reports.
4. Use existing opaque v1 event references only; do not add stable cross-system identifiers.
5. Retain sidecars only for the certification retention period; destroy under an approved process afterward.
6. Do not expose replay/provenance hashes outside certification packets unless necessary for verification.
7. Reviewers must not have a reverse-lookup interface from event references to Hermes data.

## Data subject and household sensitivity

`family_or_calendar_commitment` is intentionally coarse and reveals no person, date, event title, or relationship. If that class remains too identifying in small corpora, merge it into `external_system` for external reporting while preserving the original only in restricted review.

## Purpose limitation

V2 metadata may be used only for governance certification, replay verification, and aggregate defect analysis. It may not be used for user profiling, performance monitoring, behavioral scoring, access decisions, model training, marketing, or automation routing.

## Privacy gate

Before implementation, reviewers must approve: enum granularity, corpus minimum-cell rule, retention period, access roles, deletion procedure, and proof that no native source requires selecting prohibited content. If any required field can only be derived by reading/exporting content, reasoning, tool arguments, credentials, or raw target/principal data into the certification stream, implementation must be `BLOCKED`.