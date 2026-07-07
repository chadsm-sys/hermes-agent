# Deprecated or Duplicative Builds

Candidates for retirement. **Nothing here is deleted by the Fresh Slate mission** — these are classifications, not actions. Deleting any ref requires a separate, explicitly approved cleanup mission. Until then: do not build on, rebase, or merge anything below.

## Duplicative build clusters (the sprawl, named)

**1. Chief-of-Staff carried on two bases (top duplicative build).**
`feat/chief-of-staff-integration` (PR #5, based on `main`) and `mission1/chief-of-staff-wheel-20260707T123250` (PR #11, based on the doctrine lineage) both advance the same `chief_of_staff` package on **divergent histories**. Whichever base wins the P-1 reconciliation, the other PR must be re-cut, not merged.

**2. Overlapping hardening snapshots of the live lineage.**
`codex/hermes-review-hardening`, `codex/hermes-runtime-hardening-test-isolation`, and `live/upstream-migration-20260625T074951` are three snapshots of the same June hardening/migration effort (1,317–1,528 commits of shared lineage, 1–13 unique commits each). The doctrine branch (P-1) supersedes them as lineage carrier.

**3. Two "Olympus architecture" generations.**
Olympus v1 governance (Trust Engine, PR #9) vs. Olympus v2 reference architecture (branch, already self-dispositioned as "research appendices"). v1-frozen is the reference; v2 is explicitly not the plan.

**4. Two "knowledge graph" effort names.**
Memory Graph v2 (merged PR #7 — runtime memory provider) vs. Olympus Architecture Intelligence (P-9 — docs about the repo). Different things with colliding vocabulary; keep the names distinct in future work to avoid re-duplication.

**5. Program-planning layers stacked on each other.**
Build Program (25 missions) + Execution Manifest + Reliability Campaign + Test Oracle + Failure Injection + Tech-debt roadmap — six planning/analysis lanes, zero of which are implementation. W-1 exists precisely to collapse this into one build lane.

## Dead / obsolete candidates

| ID | Branch | What it is | Why obsolete | Salvage note |
|---|---|---|---|---|
| D-1 | `codex/hermes-review-hardening` | Hardening snapshot (2026-06-28), +1 unique commit over lineage | Superseded by doctrine lineage (P-1) | Cherry-pick the 1 unique commit if ever needed |
| D-2 | `codex/hermes-runtime-hardening-test-isolation` | Hardening snapshot (2026-06-28), +1 unique | Same as D-1 | Same |
| D-3 | `live/upstream-migration-20260625T074951` | Upstream migration snapshot, +13 unique | Migration completed; lineage superseded | Review 13 unique commits once during P-1 reconciliation |
| D-4 | `fix/stored-prompt-first-header-match-isolated` | Prompt-cache header fix, **PR #2 closed unmerged** (draft, closed same day) | Author closed it; based on lineage +445 | If the bug is real on `main`, re-derive fresh |
| D-5 | `fix/pr-40946-preserve-raw-notification-event` | Port of upstream PR 40946 (2026-06-15) | 140 commits behind `main`; upstream may have landed it | Check upstream status before any revival |
| D-6 | `automation/auto-safe-pr-phase2` | Auto-safe PR CI workflow (2026-06-12) | 122 behind; automation direction superseded by governed-merge practice used since | Design doc value only |
| D-7 | `docs/chief-of-staff-philosophy` | Branch head of **merged** PR #4 | 0 commits ahead — fully in `main` | None needed — content is in `main` |
| D-8 | `feat/memory-graph-v2` | Branch head of **merged** PR #7 | 0 commits ahead | None needed |
| D-9 | `feat/opportunity-scout-engine` | Branch head of **merged** PR #6 | 0 commits ahead | None needed |

## Safe-to-ignore (not even candidates — just noise)

- Upstream planning inheritance: `.plans/openai-api-server.md`, `.plans/streaming-support.md`, `plans/gemini-oauth-provider.md`.
- `hermes-already-has-routines.md` (marketing/positioning note at repo root).
- The local session worktree branch `claude/olympus-fresh-slate-i5960p` duplicating `main` — it is W-1's starting point, not sprawl.
