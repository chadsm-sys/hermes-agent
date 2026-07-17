# Canonical Olympus Evidence Provenance Chain

**Chain status:** `PROVENANCE_CHAIN_COMPLETE`

**Scope:** documentation and provenance only

## Canonical lineage

The canonical evidence lineage is the following forward-only sequence:

1. **Immutable Schema V2 package** — establishes the exact reviewed input.
2. **R-A1 lost-review record** — establishes that the original independent review
   could not be recovered and must not be reconstructed.
3. **R-A2 Evidence Vault** — preserves the available historical evidence and records
   the lost review as an explicit gap.
4. **Audit rerun** — verifies the vault and reclassifies the remaining audit work.

This is a semantic and cryptographic provenance chain. It does not falsely claim a
linear Git ancestry: R-A1 and R-A2 are sibling commits with common parent
`51bb38871a8159da18ab8c3df603e6be6cbd4798`. R-A1 is bound into the canonical
lineage by exact commit and record hash. R-A2 is the Git parent of the audit rerun.

## Chain anchors

| Stage | Originating commit | Branch | Manifest or integrity anchor | Dependent artifacts | Superseded artifacts | Current audit status |
|---|---|---|---|---|---|---|
| Immutable Schema V2 package | `67cc8a13e94355daee7266a27613dbebbda6d953` | `review/olympus-schema-v2-package-20260717` | `review/schema-v2-file-manifest.sha256`; file SHA-256 `83fb892ce28354ec32a7899d8f1ae9885cd01a21add0e823feae1ff276c6b3ff` | R-A1 loss record; vault package snapshot; fixture evidence | None; frozen package remains canonical | Package integrity PASS; original review UNESTABLISHED |
| R-A1 lost-review record | `b6754d795f354d4af5300cbcf264b0d7928a8651` | `remediation/olympus-audit-records-20260717` | No package manifest by design under Path B; record SHA-256 `0bb494552e9abff10bda1ba4e871aa63188beb63596db4145997f3b446bbc751` | R-A2 gap G-1; audit rerun finding `AUD-A1-01`; this chain | Unsupported assumptions that the missing review could be reconstructed | `ORIGINAL_REVIEW_RECORD_LOST`; underlying finding STILL VALID |
| R-A2 Evidence Vault | `39a580769de94668d6c681b50468001080296916` | `remediation/olympus-evidence-vault-20260717` | `evidence/EVIDENCE-MANIFEST.sha256`; manifest SHA-256 `26dacba1e49cc4557b3f71348203ad6facc17d0041d4711bcacec6e8c2632b51` | Audit rerun; certification matrix; this chain | Dispersed local evidence locations as the audit reference surface; originals remain preserved sources | `OLYMPUS_EVIDENCE_VAULT_PARTIAL` |
| Audit rerun | `f6bdab2d418aa54930e19a79d6161fe2b454a5d6` | `remediation/olympus-audit-rerun-20260717` | `HASH-ATTESTATION-RERUN.txt`; file SHA-256 `0c4e5f909f05a54be3d927b9a910524329b0206653343a5d2e1b00e0945d7ba1` | Remaining-remediation list; certification status; this canonical chain | Pre-rerun finding-status snapshot only; no evidence artifact superseded | `OLYMPUS_REMEDIATION_REQUIRED` |

## Git topology and lineage rule

```text
51bb38871 (common remediation base)
├── 67cc8a13e (immutable Schema V2 package)
├── b6754d795 (R-A1 lost-review record)
└── 39a580769 (R-A2 Evidence Vault)
    └── f6bdab2d4 (audit rerun)
        └── provenance-chain branch (this documentation)
```

The canonical semantic edges are:

```text
67cc8a13e -> b6754d795 -> 39a580769 -> f6bdab2d4
```

Every edge points from an origin to a later record that depends on it. No stage
depends on a future stage, so the lineage is acyclic.

## Verification boundary

This chain establishes identity, ordering, dependencies, supersession, and audit
status. It does not recover the lost review, import missing R2 evidence, rerun a
certification, modify any manifest, activate Olympus, or grant production authority.
