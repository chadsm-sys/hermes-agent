# Olympus Evidence Vault Provenance

**Snapshot time (UTC):** `2026-07-17T22:07:11Z`

**Repository:** `chadsm-sys/hermes-agent`

**Vault branch:** `remediation/olympus-evidence-vault-20260717`

**Vault base:** `51bb38871a8159da18ab8c3df603e6be6cbd4798`

## Preservation method

The vault is a byte-preserving import of locally available historical artifacts.
Files were copied with `cp -p` so their content and filesystem modification times
were retained. No source artifact was regenerated, normalized, rewritten, or
executed. SHA-256 values, sizes, timestamps, categories, completeness labels, and
dependencies were computed after copying and are recorded in
`EVIDENCE-INVENTORY.md`.

The top-level `EVIDENCE-MANIFEST.sha256` covers every imported artifact and every
vault control document except the manifest itself. The manifest is self-exempt
because a file cannot contain its own stable digest.

## Canonical source roots

### Mock governance estate

Source root:
`/Users/macmini/Hermes-Handoff/mock-workspaces/olympus-shadow-governance-20260717`

Imported evidence includes the mock-governance reports, false-approval remediation,
deterministic replay records, live read-only shadow evidence, advisory-mode
evidence, the decision-quality certification attempt, certification packets,
dashboards, tests, validation records, and historical manifests.

The decision-quality files are marked `partial` because the preserved historical
packet reports that correctness certification was blocked: exported metadata
covered 1 of 11 requested scenario classes and contained no independent human
labels. The files themselves are copied in full.

### Immutable Schema V2 package

Source root:
`/Users/macmini/Hermes-Handoff/worktrees/olympus-schema-v2-package-20260717`

Source commit: `67cc8a13e94355daee7266a27613dbebbda6d953`, plus the
published whitespace-exception commit at worktree HEAD
`b14e887a331241306e5cbfa93b7023bda392b810`. The vault imports exactly the 14
package files introduced by `67cc8a13`; it does not import or alter the later
whitespace exception.

### Offline fixture prototype and NEW-1/NEW-2 remediation

Source root:
`/Users/macmini/Hermes-Handoff/worktrees/olympus-schema-v2-offline-fixture-20260717`

Source worktree HEAD: `b14e887a331241306e5cbfa93b7023bda392b810`.

At snapshot time this source worktree contained uncommitted historical evidence.
Its `git status --porcelain=v1` stream had SHA-256
`c7960434162f95bb015226ed6006511eae5bb62550bb201564679766671e421c`.
The vault imports the current evidence bytes, including the fixture design
resolutions, source and verification programs, generated fixtures, reports,
manifests, replay evidence, tests, rollback instructions, and certification
reports. Nothing in the source worktree was modified or executed.

## Category and dependency model

- `mock-governance/` is the historical evaluation foundation.
- `replay/` preserves the deterministic replay inputs, decisions, and run
  manifests used by later evidence.
- `shadow/` depends on `replay/live_shadow_manifest.json`.
- `advisory/` depends on `replay/advisory_manifest.json`.
- `decision-quality/` depends on
  `replay/decision_quality_manifest.json` and its preserved adjudication corpus.
- `schema-v2/` is bound by the package's original file manifest and attestation.
- `fixture-prototype/` depends on the preserved Schema V2 package and the
  NEW-1/NEW-2 normative resolution record.
- `certification/` records historical evaluations of the category artifacts; it
  grants no current production authority.
- `manifests/` preserves source-era hash ledgers. The vault's independent
  top-level manifest is `EVIDENCE-MANIFEST.sha256`.

## Authority boundary

This vault preserves evidence only. It does not certify present behavior, rerun a
historical gate, modify Hermes or the exporter, activate Olympus, authorize a
deployment, or grant production authority.
