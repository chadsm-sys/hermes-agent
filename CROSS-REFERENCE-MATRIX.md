# Olympus Evidence Cross-Reference Matrix

**Matrix status:** `PROVENANCE_CHAIN_COMPLETE`

## Canonical artifact matrix

| Canonical artifact | Originating commit | Branch | Manifest or integrity anchor | Dependent artifacts | Superseded artifacts | Current audit status |
|---|---|---|---|---|---|---|
| Schema V2 package files | `67cc8a13e94355daee7266a27613dbebbda6d953` | `review/olympus-schema-v2-package-20260717` | `review/schema-v2-file-manifest.sha256`; SHA-256 `83fb892ce28354ec32a7899d8f1ae9885cd01a21add0e823feae1ff276c6b3ff` | R-A1 loss investigation; `evidence/schema-v2/package/`; fixture profile | None | Integrity PASS; review UNESTABLISHED |
| `LOST-REVIEW-RECORD.md` | `b6754d795f354d4af5300cbcf264b0d7928a8651` | `remediation/olympus-audit-records-20260717` | No Path-B manifest; record SHA-256 `0bb494552e9abff10bda1ba4e871aa63188beb63596db4145997f3b446bbc751` | Vault G-1; rerun `AUD-A1-01`; RR-1 | Reconstructed substitutes for the lost original | Lost / STILL VALID |
| `EVIDENCE-INVENTORY.md` | `39a580769de94668d6c681b50468001080296916` | `remediation/olympus-evidence-vault-20260717` | Covered by `EVIDENCE-MANIFEST.sha256` | Audit integrity and provenance checks | Ad hoc evidence listings | PASS — 135 imported artifact rows |
| `EVIDENCE-PROVENANCE.md` | `39a580769de94668d6c681b50468001080296916` | `remediation/olympus-evidence-vault-20260717` | Covered by `EVIDENCE-MANIFEST.sha256` | Audit source and dependency checks | Unbound source-location claims | PASS |
| `EVIDENCE-GAPS.md` | `39a580769de94668d6c681b50468001080296916` | `remediation/olympus-evidence-vault-20260717` | Covered by `EVIDENCE-MANIFEST.sha256` | Rerun remaining findings | Implicit or undocumented absence claims | PARTIAL — 5 missing artifacts recorded |
| `EVIDENCE-MANIFEST.sha256` | `39a580769de94668d6c681b50468001080296916` | `remediation/olympus-evidence-vault-20260717` | Self-exempt root; file SHA-256 `26dacba1e49cc4557b3f71348203ad6facc17d0041d4711bcacec6e8c2632b51` | Audit rerun and this chain | Dispersed per-lane audit roots as the top-level index | PASS — 139/139 |
| `OLYMPUS-AUDIT-RERUN.md` | `f6bdab2d418aa54930e19a79d6161fe2b454a5d6` | `remediation/olympus-audit-rerun-20260717` | Covered by `HASH-ATTESTATION-RERUN.txt` | Updated matrix, remaining and resolved finding sets, this chain | Pre-rerun finding status | `OLYMPUS_REMEDIATION_REQUIRED` |
| `UPDATED-CERTIFICATION-STATUS-MATRIX.md` | `f6bdab2d418aa54930e19a79d6161fe2b454a5d6` | `remediation/olympus-audit-rerun-20260717` | Covered by `HASH-ATTESTATION-RERUN.txt` | Current certification decisions | Earlier non-recomputed status matrix | Remediation required |
| `REMAINING-REMEDIATIONS.md` | `f6bdab2d418aa54930e19a79d6161fe2b454a5d6` | `remediation/olympus-audit-rerun-20260717` | Covered by `HASH-ATTESTATION-RERUN.txt` | Future separately authorized evidence work | Earlier broad remediation list | 5 remaining findings |
| `RESOLVED-FINDINGS.md` | `f6bdab2d418aa54930e19a79d6161fe2b454a5d6` | `remediation/olympus-audit-rerun-20260717` | Covered by `HASH-ATTESTATION-RERUN.txt` | This provenance chain | Earlier unresolved classification of vault controls | 3 resolved findings |
| `HASH-ATTESTATION-RERUN.txt` | `f6bdab2d418aa54930e19a79d6161fe2b454a5d6` | `remediation/olympus-audit-rerun-20260717` | Self-exempt attestation; SHA-256 `0c4e5f909f05a54be3d927b9a910524329b0206653343a5d2e1b00e0945d7ba1` | This provenance chain | Unbound rerun-document hashes | PASS |

## Cross-branch binding

| From | To | Binding | Circularity check |
|---|---|---|---|
| Schema V2 package | R-A1 | Exact package commit named as reviewed input | Forward-only |
| R-A1 | R-A2 | Exact loss status reproduced as vault gap G-1; R-A1 record hash pinned here | Forward-only; sibling Git topology disclosed |
| R-A2 | Audit rerun | Direct Git parent plus vault-manifest hash | Forward-only |
| Audit rerun | Provenance chain | Direct Git parent plus rerun-attestation hash | Forward-only |

All referenced commits exist locally, all referenced manifests or attestations
verify, and no dependency edge points back to an earlier consumer.
