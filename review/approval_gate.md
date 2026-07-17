# Governance Metadata Schema v2 — Approval Gate

## Current gate

**State:** `READY_FOR_INDEPENDENT_DESIGN_REVIEW`  
**Implementation authority:** `DENIED`  
**Olympus activation:** `DENIED`  
**Production authority:** `DENIED`

## Required approvals before any fixture prototype

All four roles must approve the exact document hashes:

1. Privacy reviewer — enum granularity, correlation, retention, access, reporting.
2. Security reviewer — non-authority semantics, spoofing/downgrade/replay controls, trust boundaries.
3. Governance reviewer — taxonomy correctness, source independence, cross-field safety rules.
4. Replay/certification reviewer — canonicalization, provenance binding, compatibility, metrics sufficiency.

Fixture-only approval does not authorize reading Hermes or modifying the exporter.

## Required evidence before any implementation proposal

- Field-by-field source map proving prohibited content is unnecessary.
- Data-flow diagram showing one-way, read-only, non-networked, non-actuating boundaries.
- Exact machine schema and canonicalization profile reviewed separately.
- Nonproduction fixtures covering every enum, invalid input, downgrade, duplicate, splice, and replay case.
- Privacy impact assessment with retention and access decisions.
- Threat-model closure for all critical threats.
- Plan to preserve v1 bytes and hashes.
- Rollback and fail-closed test plan.

## Automatic blockers

Return `BLOCKED` if any of the following is true:

- A required fact can only be sourced by exporting prompts, content, reasoning, tool arguments, credentials, secrets, raw targets, or identities.
- Olympus is the sole source for both factual governance outcomes and recommendations.
- Metadata can be consumed as authorization or routed to an actuator.
- V1 exporter/stream/replay must be modified in place.
- Unknown versions or missing fields are accepted through fallback.
- Provenance/replay cannot be deterministically recomputed.
- Independent reviewers cannot judge cases from the bounded facts.

## Revision conditions

Return `NEEDS_REVISION` for noncritical ambiguity in enum definitions, canonicalization, source ownership, privacy controls, reviewer workflow, or compatibility rules.

## Ready condition

Return `SCHEMA_V2_READY_FOR_REVIEW` only when documentation is complete, no implementation occurred, the existing boundary remains unchanged, and no unresolved design conflict makes privacy-preserving certification impossible.

## Separate future gates

1. Design approval
2. Fixture-only schema validation
3. Proposed producer boundary review
4. Nonproduction implementation certification
5. Dual-stream replay certification
6. Human adjudication pilot
7. Decision-quality certification

Passing one gate never implies the next.