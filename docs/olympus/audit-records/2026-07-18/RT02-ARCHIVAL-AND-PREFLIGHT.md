# RT-02 Expired-Request Archival and RC4 Preflight — 2026-07-18

- Record type: operational process metadata (RT-02 closure; W3-HANDOFF steps 2–3)
- Authority: explicit operator (Chad) approval, 2026-07-18, scoped to archival,
  preflight, and push of branch `remediation/olympus-audit-records-20260717`
  only. No ceremony, certification, activation, merge, deploy, or restart was
  authorized or performed.

## Archival (W3 step 2)

| Item | Value |
|---|---|
| Source | `/private/tmp/olympus-gbr-request.json` (762 bytes, mtime 2026-07-17T11:28:30Z, `-rw-------`) |
| Source SHA-256 | `c6baf87d8621f61db31c0931408d7764662379062e64a90d0e10d4339461b82c` |
| Destination | `~/Hermes-Handoff/artifacts/infrastructure-changes/20260718T-olympus-gbr-expired-request-archive/olympus-gbr-request.json` |
| Archived SHA-256 | `c6baf87d8621f61db31c0931408d7764662379062e64a90d0e10d4339461b82c` (MATCH, verified before source removal) |
| Request | `APR-GBR-84d0edb540ed446f708e374e`, action `GBR_ADOPTION`, issued 2026-07-17T11:28:30Z, expired 2026-07-17T11:33:30Z, no assertion ever produced |
| Tombstone | `SOURCE-METADATA.txt` in the archive dir records identity, digests, supersession rationale, and removal |
| Archive manifest (`SHA256SUMS`) SHA-256 | `77d795c5e57af2723ba04731238bc94f09170151686f42fd8c2e2a03b7a6bbef` |
| Post-removal state | zero `/private/tmp/olympus-gbr-*` entries remain; archive dir sealed read-only (files 444, dir 555) |

The earlier `20260717T-olympus-gbr-stale-ceremony-archive/` package was not
modified. The archived request must never be replayed or reused; any ceremony
attempt requires a fresh request from the certified RC4 capture flow.

## RC4 preflight (W3 step 3)

- Command: `python3 gbr_preflight.py` run from
  `20260717T-olympus-gbr-release-candidate-4/` (certified read-only entry per
  `RUNBOOK-RC4.md` Step 1).
- Result: **`RESULT: PASS — GO permitted`** — all checks PASS, including
  "no stale ceremony files in /tmp" (the RT-02 collision blocker is cleared),
  all six upstream manifests + RC4 self-manifest, pinned digests, three
  worktree identities, ledger pre-state, trust root, replay store
  (rows=1, `ae4d9e50…63e35d92`, byte-unchanged), profile revision 2
  authorizing `GBR_ADOPTION`, and verifier policy (no `--now`, no allowlist
  exception).
- Transcript preserved: `RC4-PREFLIGHT-20260718.txt` in the archive dir,
  SHA-256 `12116b6379ffa82c5a338007469c2e66c0f28d330a424486108452da311ba5cc`.

## Sealed-bytes confirmation

Recomputed after all operations, unchanged:

- RC4 `SHA256SUMS`: `e9b9c0ec669cc9eb37cbc3a5f588534ef42d30ef06af2fc1456adc38dbd29aff`
- RC4 certification `SHA256SUMS`: `891912fb832e0a2146d512388cfc67d4f843c75aceab9d946b90a00b140ac4c8`
- On-disk pointer `CURRENT-RELEASE.md`: `53a54b0fc19ce2a75850c3b6748ae984835b79e1ee30cf498258a403ebda43f3`, perms 444, still names RC4 as sole certified candidate.

## Ceremony status after this record

W3 steps 1–3 complete. Still open before ceremony execution: off-box integrity
comparison (W3 step 4) and explicit ceremony authorization (W3 step 5). The
single next authorized ceremony command, to be run only after both, remains
RC4 `gbr_verify_and_preserve.py` per `RUNBOOK-RC4.md`. This record grants no
such authority.
