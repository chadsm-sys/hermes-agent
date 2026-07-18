# Olympus GBR — Supersession Notice

- Record date: 2026-07-17
- Record type: operational process metadata (RT-01 / RT-06 / RT-15 remediation)
- Authority basis: `20260717T-olympus-grok-v3-adjudication/FINDING-DISPOSITION.md`
  and `W3-HANDOFF.md`
- This record modifies no sealed or preserved artifact bytes. Superseded
  packages remain on disk unchanged as historical evidence.

## Operationally SUPERSEDED — must not be executed

| Surface | Status | Reason |
|---|---|---|
| `20260717T-olympus-final-operator-release-package/FINAL_OPERATOR_RUNBOOK.md` | SUPERSEDED, FORBIDDEN as a ceremony path | RT-01: its unsealed `FINAL_RELEASE_PACKET.md` still claims readiness and routes to the historical WP-01/raw-verifier path. Both 2026-07-17 independent adversarial reviews of this package returned REVISE. |
| `20260716T-olympus-wp01/olympus_webauthn_verify.py` (direct operator invocation) | SUPERSEDED, FORBIDDEN | RT-06: retains `--now` and the action exception, and can write the shared replay store without the RC4 durable wrapper journal. |
| RC4 raw `olympus_webauthn_verify.py` (direct operator invocation) | INTERNAL COMPONENT ONLY | RT-07: used by tests and the preservation wrapper. `gbr_verify_and_preserve.py` is the sole approved operator entry; wrapper-only evidence is mandatory. |

Together these resolve the split control plane (RT-15): exactly one ceremony
control plane remains — RC4 preflight plus `gbr_verify_and_preserve.py`, per
`RUNBOOK-RC4.md`.

## Historical (rejected or superseded candidates, preserved unchanged)

| Package | Disposition |
|---|---|
| `20260717T-olympus-final-operator-release-package` | Original candidate; rejected by two independent adversarial reviews (both REVISE). |
| `20260717T-olympus-gbr-release-candidate-2` (+ remediation evidence, + final independent certification) | Remediated and certified in its cycle; superseded by later candidates. |
| `20260717T-olympus-gbr-release-candidate-3` (+ certification materials) | Rejected — two additional defects found during independent review (recorded in RC4 `FINAL-CERTIFICATION-AUDIT.md`). |

## Standing prohibitions

- Do not create RC5, modify RC4, or rerun certification for the Grok V3
  findings; they are process/state/packaging findings, not implementation
  defects in RC4.
- Deferred post-activation improvements (do not hold the ceremony for them):
  RT-09, RT-11, RT-21, RT-25, RT-28, RT-30.
