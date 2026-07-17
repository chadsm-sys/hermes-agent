# Olympus Schema V2 Offline Fixture Prototype — Root-Cause Report

**Report time:** 2026-07-17T21:46:32Z  
**Scope:** `offline_fixture_prototype/` on `prototype/olympus-schema-v2-offline-fixture-20260717`  
**Final disposition:** All identified verifier and filesystem-boundary defects were reproduced, remediated, regression-tested, and independently re-reviewed.

## Executive finding

The prototype's domain rules and deterministic fixture generation were sound, but several trust-boundary checks initially relied on incomplete representations of the artifact tree or on self-attested metadata. Those gaps could allow malformed generated trees to appear valid or allow unsafe replacement behavior. No production runtime, deployment, outbound action, credential, or Olympus execution authority was involved.

## Root causes

### RC-1 — Manifest enumeration was not closed over the manifest directory

The verifier validated expected manifests but did not initially treat unexpected manifest files, absent manifests, duplicate entries, malformed content, or nested manifest paths as a uniformly fail-closed boundary.

**Impact:** A tree could carry unapproved metadata outside the intended manifest set or produce ambiguous coverage.

### RC-2 — Source-event references were insufficiently namespace-bound

Source references required explicit validation against the fixture-only namespace and rejection of live prefixes, substitution syntax, duplicates, and cross-run transplants.

**Impact:** Polluted provenance could contaminate replay identifiers or weaken fixture/runtime separation.

### RC-3 — Self-consistent hashes were mistaken for independent semantic proof

An attacker able to alter an artifact and recompute its manifests could preserve internal digest consistency. Digest validation alone therefore could not establish that artifacts still matched source-derived semantics.

**Impact:** Rehashed altered advisory, authority, namespace, replay, or certification fields could otherwise evade purely circular verification.

### RC-4 — Filesystem path handling was incomplete

The initial boundary did not comprehensively reject traversal, embedded symlinks, and a CLI root-symlink path before path resolution. The CLI used a resolved path too early, erasing evidence that the caller supplied a symlink.

**Impact:** Verification could inspect a symlink target rather than fail closed on the supplied path.

### RC-5 — Replacement ownership relied on forgeable marker filenames

`generate(..., replace=True)` originally treated two expected filenames as sufficient evidence that a directory was generator-owned.

**Impact:** An unrelated directory containing forged marker names could be moved aside and then deleted after successful replacement, including unrelated sentinel content.

### RC-6 — Tree closure modeled files but not empty directories

Artifact comparison and manifest coverage enumerated files; an unexpected empty directory had no file entry and therefore escaped closure checks.

**Impact:** A generated tree with additional empty directory topology could still receive `FIXTURE_PROTOTYPE_READY`.

## Why earlier reviews missed RC-5 and RC-6

Earlier lanes concentrated on content integrity, normative policy, namespace separation, manifests, and semantic re-derivation. The final filesystem adversarial lane added two distinct probes:

1. forge only the expected marker names inside a non-generated directory, then invoke replacement;
2. add an empty directory that contributes no file to any manifest.

These probes tested ownership and directory topology rather than content hashes, exposing the residual assumptions.

## Containment

- Scope remained an offline fixture prototype.
- Generated certification explicitly denies production authority and Olympus activation.
- No production code path, scheduler, exporter, gateway, credential, network operation, or deployment was exercised.
- Certification was withheld whenever an independent lane reported a blocker.
