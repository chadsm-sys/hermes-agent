# Olympus GBR — CURRENT Release Pointer

- Record date: 2026-07-17
- Record type: operational process metadata (RT-04 remediation)
- Authority basis: `20260717T-olympus-grok-v3-adjudication/W3-HANDOFF.md`, step 1
  ("Establish one operational source of truth")
- This record modifies no sealed artifact bytes.

## CURRENT certified ceremony candidate

**RC4 is the only certified GBR ceremony candidate.** No other package,
runbook, or verifier carries operational authority.

| Item | Value |
|---|---|
| Release directory | `~/Hermes-Handoff/artifacts/infrastructure-changes/20260717T-olympus-gbr-release-candidate-4` |
| Release `SHA256SUMS` SHA-256 | `e9b9c0ec669cc9eb37cbc3a5f588534ef42d30ef06af2fc1456adc38dbd29aff` |
| Certification directory | `~/Hermes-Handoff/artifacts/infrastructure-changes/20260717T-olympus-gbr-rc4-certification` |
| Certification `SHA256SUMS` SHA-256 | `891912fb832e0a2146d512388cfc67d4f843c75aceab9d946b90a00b140ac4c8` |
| Certification verdict | `CERTIFICATION_SUPPORTED_WITH_MINOR_NOTES` |
| Sole approved operator entry | RC4 `gbr_verify_and_preserve.py` (never the raw verifier) |
| Canonical ledger root | `/Users/macmini/.olympus/control-plane/decision-ledger-v1` |

Digests above were independently recomputed from disk on 2026-07-17 when this
record was written and match the values in `FINDING-DISPOSITION.md` and
`W3-HANDOFF.md` of the Grok V3 adjudication.

## Canonical bindings (unchanged)

- WP-01 trust root and append-only replay store remain authoritative.
- GBR payload of 2026-07-16 (`104428d2…f6b5e0`) remains the bound payload.
- Replay store holds one prior WP-01 proof row and no RC4 GBR verification
  receipt.

## Ceremony status at record time

**NOT GO.** Open prerequisites, in order (W3-HANDOFF steps 2–5):

1. Explicit operator authority to archive the expired request residue
   `/private/tmp/olympus-gbr-request.json`
   (request `APR-GBR-84d0edb540ed446f708e374e`, expired 2026-07-17T11:33:30Z,
   no matching assertion). RC4 preflight correctly fail-closes on it (RT-02).
2. RC4 preflight run with preserved transcript; all checks must PASS.
3. Off-box integrity comparison of RC4 root, certification root, and top-level
   digests via an independent medium.
4. Explicit ceremony authorization. Certification and chat narrative are not
   ceremony authority.

A VERIFIED WebAuthn receipt is approval evidence only — it is not GBR
adoption and grants no REB, PCE, EER, activation-window, restart, deployment,
or production authority. Supervised activation remains separately gated
(RT-20, RT-24); see `AUDIT-RECORD-INDEX.md`.
