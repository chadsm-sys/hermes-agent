# Olympus GBR — Audit Record Index, 2026-07-17

Durable index of the 2026-07-17 GBR release/audit lane. All artifact
directories live under
`~/Hermes-Handoff/artifacts/infrastructure-changes/`. Where a directory ships
a `SHA256SUMS` manifest, the SHA-256 **of that manifest file** was recomputed
from disk on 2026-07-17 and is recorded here; verifying it plus the manifest
itself re-verifies the whole directory. Directories without a manifest are
marked `no manifest`.

Logical lineage (not strictly chronological within the day):

| # | Directory | Role | Outcome | Manifest SHA-256 |
|---|---|---|---|---|
| 1 | `20260717T-olympus-final-operator-release-package` | Original operator release candidate | REJECTED; operationally superseded (see `SUPERSESSION-NOTICE.md`) | no manifest |
| 2 | `20260717T-olympus-gbr-independent-red-team-review` | Independent adversarial review #1 of package #1 | **REVISE** (findings F1–F7, risks R1–R9) | no manifest |
| 3 | `20260717T-olympus-independent-adversarial-review` | Independent adversarial review #2 of package #1 | **REVISE** | no manifest |
| 4 | `20260717T-olympus-gbr-release-candidate-2` | RC2 sealed remediation candidate | Superseded by RC3/RC4 | `e137e30af4059fe3e001fe5990cac63972f53613cbe12f5921e1b0976f0e467c` |
| 5 | `20260717T-olympus-gbr-rc2-remediation-evidence` | RC2 remediation evidence (6 reports, 54/54 tests) | Historical | `fc7300bc51ec0812ef6d2cbd649418a87256c4195f4ace043c49fea71a1ca918` |
| 6 | `20260717T-olympus-gbr-rc2-final-independent-certification` | RC2 independent certification | Findings RESOLVED; cycle closed | no manifest |
| 7 | `20260717T-olympus-gbr-release-candidate-3` | RC3 candidate | REJECTED (two additional defects found in independent review) | `c524803659333ead1c171ce364787ad4107c9573bacba61cf5604cf124cc644e` |
| 8 | `20260717T-olympus-gbr-rc3-certification` | RC3 certification materials | Superseded with RC3 | no manifest |
| 9 | `20260717T-olympus-gbr-release-candidate-4` | **RC4 — CURRENT certified candidate** | ACCEPTED | `e9b9c0ec669cc9eb37cbc3a5f588534ef42d30ef06af2fc1456adc38dbd29aff` |
| 10 | `20260717T-olympus-gbr-rc4-certification` | RC4 independent certification | `CERTIFICATION_SUPPORTED_WITH_MINOR_NOTES` | `891912fb832e0a2146d512388cfc67d4f843c75aceab9d946b90a00b140ac4c8` |
| 11 | `20260717T-olympus-gbr-stale-ceremony-archive` | Archive of earlier stale `/tmp/olympus-gbr-*` ceremony files | Complete; a NEW expired request has since appeared (RT-02, see below) | `45db2bd242b5c8a6e0f1441e58d86ea21bef658dfcadd8f51bf0ed86108ce7df` |
| 12 | `20260717T-olympus-supervised-activation-readiness-verification` | Supervised-activation readiness verification | **NOT READY** (RT-20 gates open) | `fa225541af75204140b24666477eb24b4cde1a3914603e915a5da465c3ec7f05` |
| 13 | `20260717T-olympus-grok-v3-adjudication` | Grok V3 finding adjudication + W3 handoff (read-only) | RT-01…RT-30 dispositioned; RC4 unchanged; ceremony NOT GO | no manifest |

## Open items at record time

- **RT-02 residue (open):** `/private/tmp/olympus-gbr-request.json`, request
  `APR-GBR-84d0edb540ed446f708e374e`, issued 2026-07-17T11:28:30Z, expired
  2026-07-17T11:33:30Z, no matching assertion. Archival requires explicit
  operator authority; RC4 preflight fail-closes until cleared.
- **Ceremony:** NOT GO until W3-HANDOFF steps 2–5 complete (see
  `CURRENT-RELEASE.md`).
- **Supervised activation:** separately gated; requires GBR adoption, sealed
  REB/PCE/EER, corrected staged ledger root, reconciled service
  label/topology, complete release/worker/Mission Control assets, a final
  PCE-bound rollback image with proven deterministic rollback, and an explicit
  bounded activation window (RT-20, RT-24).

## Confirmed-defect disposition snapshot

From the Grok V3 adjudication register: RT-01, RT-02, RT-04, RT-06, RT-15,
RT-20 = CONFIRMED_DEFECT. Of these, RT-01/RT-04/RT-15 are remediated by the
records in this directory; RT-06 is remediated operationally by the
supersession prohibition; RT-02 awaits operator authority; RT-20 blocks only
the later activation window. All other RT findings are INTENTIONAL_DESIGN,
ALREADY_RESOLVED, or POST_ACTIVATION_IMPROVEMENT per the register.
