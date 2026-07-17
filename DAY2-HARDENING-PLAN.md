# Day-2 Hermes Hardening Plan

Date: 2026-07-17
Mode: isolated implementation and local review preparation only

## Source and isolation

- Source candidate: `baf98f1c7faa802aa401c43ff0cd874001790211`
- Isolated branch: `codex/day2-hermes-hardening-20260717`
- Isolated worktree: `/Users/macmini/Hermes-Handoff/worktrees/day2-hermes-hardening-20260717`
- Component lineage is imported only from the already-tested clean Hermes integration history: memorygraph, Opportunity Scout, and deterministic Morning Brief.
- The live owner checkout, live runtime checkout, gateway, runtime databases, cron, launchd, credentials, `HERMES_HOME`, RC4, and Olympus release/certification artifacts are forbidden surfaces.

## Bounded remediation sequence

1. Add failing invariant tests for unresolved contradicted exclusive claims, legacy active conflicts, and cross-connection exclusive writes; then make claim transitions atomic and database-defended.
2. Add failing connection-policy and deterministic contention tests; then enable WAL and an explicit busy timeout without weakening transaction durability.
3. Add a failing capture-to-retrieval confidence test; then preserve declared confidence through inbox capture, persistence, scoring, and retrieval.
4. Add a failing severity-order test; then aggregate explicit and derived Morning Brief states by the worse supported severity.
5. Run focused suites, relevant regressions, SQLite integrity/concurrency checks, affected-file Ruff/format checks, `git diff --check`, and a redacted secret scan.
6. Produce the evidence package, create local-only independently reviewable commits where practical, and prove the source/live identities are unchanged and the isolated worktree is clean.

## Stop conditions

- No merge, push, PR, deployment, promotion, service action, or production write.
- Any need to touch a forbidden surface stops the lane with `HARDENING_BLOCKED`.
- Final status is limited to the exact authorized verdict vocabulary.
