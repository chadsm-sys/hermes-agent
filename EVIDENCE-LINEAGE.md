# Olympus Evidence Lineage

**Lineage status:** `PROVENANCE_CHAIN_COMPLETE`

## Lineage stages

### L1 — Immutable review input

- **Originating commit:** `67cc8a13e94355daee7266a27613dbebbda6d953`
- **Branch:** `review/olympus-schema-v2-package-20260717`
- **Manifest:** `review/schema-v2-file-manifest.sha256`
- **Manifest SHA-256:** `83fb892ce28354ec32a7899d8f1ae9885cd01a21add0e823feae1ff276c6b3ff`
- **Dependent artifacts:** R-A1 recovery search and loss record; R-A2
  `evidence/schema-v2/package/`; offline fixture evidence.
- **Superseded artifacts:** none. Later design work does not alter this frozen input.
- **Current audit status:** package bytes established; original independent review
  remains unestablished.

### L2 — Independent-review loss determination

- **Originating commit:** `b6754d795f354d4af5300cbcf264b0d7928a8651`
- **Branch:** `remediation/olympus-audit-records-20260717`
- **Manifest:** none under R-A1 Path B. The single canonical loss record is bound by
  SHA-256 `0bb494552e9abff10bda1ba4e871aa63188beb63596db4145997f3b446bbc751`.
- **Dependent artifacts:** R-A2 `EVIDENCE-GAPS.md` G-1; audit-rerun finding
  `AUD-A1-01`; `REMAINING-REMEDIATIONS.md` RR-1; this lineage.
- **Superseded artifacts:** later quotations or party-authored remediation matrices
  as purported substitutes for the original review.
- **Current audit status:** `ORIGINAL_REVIEW_RECORD_LOST`; fresh independent review
  required.

### L3 — Repository evidence root

- **Originating commit:** `39a580769de94668d6c681b50468001080296916`
- **Branch:** `remediation/olympus-evidence-vault-20260717`
- **Manifest:** `evidence/EVIDENCE-MANIFEST.sha256`
- **Manifest SHA-256:** `26dacba1e49cc4557b3f71348203ad6facc17d0041d4711bcacec6e8c2632b51`
- **Dependent artifacts:** audit rerun, updated certification matrix, resolved and
  remaining finding sets, and this provenance chain.
- **Superseded artifacts:** dispersed local locations as the canonical audit index.
  Source files remain historical origins and are not deleted or invalidated.
- **Current audit status:** `OLYMPUS_EVIDENCE_VAULT_PARTIAL`; 139/139 manifest
  entries verify, with documented gaps.

### L4 — Post-remediation audit status

- **Originating commit:** `f6bdab2d418aa54930e19a79d6161fe2b454a5d6`
- **Branch:** `remediation/olympus-audit-rerun-20260717`
- **Manifest:** `HASH-ATTESTATION-RERUN.txt`
- **Attestation SHA-256:** `0c4e5f909f05a54be3d927b9a910524329b0206653343a5d2e1b00e0945d7ba1`
- **Dependent artifacts:** this canonical lineage and its cross-reference matrix.
- **Superseded artifacts:** pre-rerun status classifications only. Evidence and
  prior remediation commits remain canonical.
- **Current audit status:** `OLYMPUS_REMEDIATION_REQUIRED`; 3 resolved findings,
  5 remaining findings, and no new P0/P1 findings.

## Lineage invariants

1. Every stage has an immutable commit identity.
2. Every stage has either a manifest or an explicit single-record integrity anchor.
3. Every dependency points forward from origin to consumer.
4. No later artifact changes or regenerates an earlier artifact.
5. Supersession applies only to audit-reference or status roles, never to original
   evidence bytes.
6. Missing evidence remains missing; cross-references do not manufacture it.
7. No stage grants implementation, activation, deployment, or production authority.
