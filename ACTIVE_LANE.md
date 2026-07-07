# Active Lane

**There is exactly one active build lane.**

## W-1 — Claude Code Kanban Executor

| Field | Value |
|---|---|
| Lane ID | W-1 |
| Status | **ACTIVE** (approved lane; implementation **not yet started** — awaiting explicit go-ahead after this inventory) |
| Branch | `claude/olympus-fresh-slate-i5960p` (currently identical to `main` @ `93b565b`) |
| PR | none yet |
| Base | `main` — W-1 builds on the reviewed `main` lineage, **not** the doctrine lineage |

## What W-1 is

An executor that drives work through the Hermes Kanban subsystem using Claude Code as the worker lane. It builds on infrastructure that already exists in `main`:

- Kanban core and dispatcher (`docs/kanban/`, gateway `kanban.dispatch_in_gateway`, per-board `kanban.db`)
- Kanban orchestrator/worker skills (`devops-kanban-orchestrator`, `devops-kanban-worker`, kanban worker lanes — see `website/docs/user-guide/features/kanban-worker-lanes.md`)
- Kanban v1 spec (`docs/hermes-kanban-v1-spec.pdf`)

Note: the name "W-1 Claude Code Kanban Executor" appears in no repo document before this ledger — this file is its canonical definition point. Its detailed spec is the first W-1 deliverable.

## Ground rules for W-1

1. All W-1 work happens on W-1 branches based on `main`; no dependence on any parked branch.
2. If W-1 needs something from a parked lane (e.g. `chief_of_staff` contracts), that lane's resume condition in [RESUME_CONDITIONS.md](RESUME_CONDITIONS.md) must be satisfied first — do not cherry-pick silently.
3. Single-dispatcher posture is preserved (one gateway owns kanban dispatch).
4. Implementation starts only after explicit operator approval of this inventory.

## Everything else

Every other branch, PR, and build lane is PARKED, MAINTENANCE ONLY, or a DEAD/OBSOLETE CANDIDATE. See [PARKED_LANES.md](PARKED_LANES.md) and [DEPRECATED_OR_DUPLICATIVE_BUILDS.md](DEPRECATED_OR_DUPLICATIVE_BUILDS.md).
