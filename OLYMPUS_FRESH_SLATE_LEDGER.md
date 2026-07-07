# Olympus Fresh Slate Ledger

**Mission:** Olympus Fresh Slate Consolidation
**Date:** 2026-07-07
**Decision:** W-1 Claude Code Kanban Executor is the **only** ACTIVE build lane. Everything else is parked, maintenance-only, or an obsolete candidate. **Nothing is deleted by this mission.**

Companion documents:

- [ACTIVE_LANE.md](ACTIVE_LANE.md) — the one active lane
- [PARKED_LANES.md](PARKED_LANES.md) — full parking records
- [RESUME_CONDITIONS.md](RESUME_CONDITIONS.md) — what un-parks each lane
- [DEPRECATED_OR_DUPLICATIVE_BUILDS.md](DEPRECATED_OR_DUPLICATIVE_BUILDS.md) — dead/duplicative candidates

---

## Repository state at inventory time

- Repo: `chadsm-sys/hermes-agent` (fork of NousResearch/hermes-agent)
- `main` head: `93b565b` (merge of PR #8, M21 Executive Operating Loop contracts)
- 31 remote branches, 11 PRs total (5 open, 4 merged, 2 closed-unmerged)
- Local worktrees: 1 (this session, `claude/olympus-fresh-slate-i5960p`, identical to `main`)

### Structural finding: two lineages exist

The repository contains **two divergent histories** that split at `5a0e0d35` (2026-06-15):

1. **`main` lineage** — the reviewed, PR-governed history (PRs #4, #6, #7, #8 merged).
2. **`agent/continue-until-fork-doctrine` lineage** — an operational/live lineage carrying **~2,574 commits not on `main`**. Nearly every large branch (`mission1/*`, `hotfix/*`, `split/*`, `codex/*`, `live/*`) is this lineage plus 1–13 unique commits.

Consequence: open PR #11 is based on the doctrine lineage, **not** `main`. Reconciling (or formally forking) the two lineages is a parked decision — see PARKED_LANES.md lane P-1 and RESUME_CONDITIONS.md.

---

## Classification summary

| Class | Count | Lanes |
|---|---|---|
| ACTIVE | 1 | W-1 Claude Code Kanban Executor |
| PARKED | 17 | P-1 … P-17 (see PARKED_LANES.md) |
| MAINTENANCE ONLY | 3 | M-1 … M-3 |
| DEAD/OBSOLETE CANDIDATE | 9 | D-1 … D-9 (see DEPRECATED_OR_DUPLICATIVE_BUILDS.md) |

## Full inventory

| ID | Lane | Branch | PR | Class |
|---|---|---|---|---|
| W-1 | Claude Code Kanban Executor | `claude/olympus-fresh-slate-i5960p` | — | **ACTIVE** |
| P-1 | Continue-Until-Fork operational lineage | `agent/continue-until-fork-doctrine` | — | PARKED (anchor — must not be lost) |
| P-2 | Mission 1: chief_of_staff wheel packaging | `mission1/chief-of-staff-wheel-20260707T123250` | #11 open | PARKED |
| P-3 | Chief of Staff interface layer | `feat/chief-of-staff-integration` | #5 open | PARKED |
| P-4 | Olympus Trust Engine v1 + Build Program + Execution Manifest | `claude/olympus-trust-engine-0izzp5` | #9 open | PARKED |
| P-5 | Olympus CTO handoff (non-normative narrative) | `claude/olympus-cto-handoff-bwyn8e` | #10 open | PARKED |
| P-6 | Olympus v2 architecture (research appendices) | `claude/olympus-v2-architecture-x9926r` | — | PARKED |
| P-7 | Olympus Test Oracle v1 | `claude/olympus-test-oracle-v1-olzaqg` | — | PARKED |
| P-8 | Reliability Intelligence / Failure Injection Campaign | `claude/olympus-failure-injection-gu3fzc` | — | PARKED |
| P-9 | Olympus Architecture Intelligence (repo knowledge graph docs) | `claude/hermes-knowledge-graph-6ps6gx` | — | PARKED |
| P-10 | Engineering Handbook + unwired-features register (branches A–C plan) | `claude/hermes-cloud-context-bootstrap-e82jy5` | — | PARKED |
| P-11 | Branch A: docstring/runtime sync | `docs/docstring-runtime-sync` | — | PARKED |
| P-12 | Branch B: .env.example accuracy | `docs/env-example-accuracy` | — | PARKED |
| P-13 | Branch C: CLI default display corrections | `fix/cli-default-display-corrections` | — | PARKED |
| P-14 | Technical debt audit + roadmap | `claude/technical-debt-audit-ydvvfe` | — | PARKED |
| P-15 | Mission Control v0 broker (fleet, node connector, state guard) | `mission-control-v0` | — | PARKED |
| P-16 | Council gate v1 (artifact redaction) | `feat/hermes-council-gate-v1` | #1 open | PARKED |
| P-17 | Full-codebase code-review fixes | `claude/session-planning-u1c0bq` | #3 open | PARKED |
| M-1 | Gateway launchd `--replace` hotfix | `hotfix/gateway-launchd-no-replace-20260703` | — | MAINTENANCE ONLY |
| M-2 | Auth token redaction split-fix | `split/54134-auth-token-redaction` | — | MAINTENANCE ONLY |
| M-3 | X-search handle limit split-fix | `split/54134-x-search-handle-limit` | — | MAINTENANCE ONLY |
| D-1 | Codex review hardening | `codex/hermes-review-hardening` | — | DEAD/OBSOLETE CANDIDATE |
| D-2 | Codex runtime hardening / test isolation | `codex/hermes-runtime-hardening-test-isolation` | — | DEAD/OBSOLETE CANDIDATE |
| D-3 | Upstream migration snapshot | `live/upstream-migration-20260625T074951` | — | DEAD/OBSOLETE CANDIDATE |
| D-4 | Prompt cache header fix | `fix/stored-prompt-first-header-match-isolated` | #2 closed unmerged | DEAD/OBSOLETE CANDIDATE |
| D-5 | Raw notification event fix (upstream PR 40946 port) | `fix/pr-40946-preserve-raw-notification-event` | — | DEAD/OBSOLETE CANDIDATE |
| D-6 | Auto-safe PR automation phase 2 | `automation/auto-safe-pr-phase2` | — | DEAD/OBSOLETE CANDIDATE |
| D-7 | Chief-of-staff philosophy branch head | `docs/chief-of-staff-philosophy` | #4 **merged** | DEAD/OBSOLETE (fully in main) |
| D-8 | Memory Graph v2 branch head | `feat/memory-graph-v2` | #7 **merged** | DEAD/OBSOLETE (fully in main) |
| D-9 | Opportunity Scout branch head | `feat/opportunity-scout-engine` | #6 **merged** | DEAD/OBSOLETE (fully in main) |

Merged-and-safe: PRs #4 (chief-of-staff philosophy docs), #6 (Opportunity Scout), #7 (Memory Graph v2), #8 (M21 Executive Operating Loop contracts) are all in `main`; their branch heads carry zero unique commits.

---

## What must not be lost

1. **`agent/continue-until-fork-doctrine`** — the only trunk of the ~2,574-commit operational lineage. Every `mission1/*`, `hotfix/*`, `split/*` branch depends on it.
2. **`mission-control-v0`** — the only copy of the Mission Control v0 broker code (plugin skeleton, fleet registry, read-only node connector, mac-mini SSH tunnel work). It exists nowhere else in this repo.
3. **Open PR branches** #1, #3, #5, #9, #10, #11 — unmerged code/docs.
4. **Un-PR'd doc campaigns** — failure injection (P-8), test oracle (P-7), knowledge graph (P-9), engineering handbook (P-10), tech-debt audit (P-14), v2 architecture (P-6).

## What can be safely ignored

- D-7/D-8/D-9 (merged branch heads — zero unique content).
- D-1/D-2/D-3 (superseded hardening/migration snapshots of the doctrine lineage; keep refs, never build on them).
- D-4 (PR #2 closed unmerged by its own author), D-5, D-6 (stale, far behind main).
- The `.plans/` and `plans/` upstream planning files (`openai-api-server.md`, `streaming-support.md`, `gemini-oauth-provider.md`) — upstream inheritance, not Olympus lanes.

## Rules while the fresh slate holds

1. No new branches except under W-1.
2. No merges of parked PRs without explicit operator approval.
3. No branch deletion — obsolete candidates stay as refs until a separate, explicitly approved cleanup mission.
4. Any resumed lane must first satisfy its entry in RESUME_CONDITIONS.md.
