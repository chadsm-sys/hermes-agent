# Parked Lanes

All lanes below are **PARKED**: valuable, preserved, not to be built on until their resume condition ([RESUME_CONDITIONS.md](RESUME_CONDITIONS.md)) is met. "Next safe action" is always non-destructive. Nothing here is deleted.

Reason all lanes share for parking, in addition to the per-lane reason: **Fresh Slate decision (2026-07-07) — W-1 is the only active lane; build sprawl stops here.**

---

## P-1 — Continue-Until-Fork operational lineage *(anchor — must not be lost)*

- **Branch:** `agent/continue-until-fork-doctrine` (head `738c35a`, 2026-07-07)
- **PR:** none (PR #11 is based on it)
- **Status:** ~2,574 commits ahead of `main`; the trunk of the second ("live machine") lineage that split from `main` at `5a0e0d35` (2026-06-15). Latest work: destructive-rm decision policy hardening.
- **Why parked:** It is a parallel history, not a feature branch. Merging or rebasing it is a major reconciliation project that would swamp W-1.
- **Resume condition:** Explicit "lineage reconciliation" mission approved by operator.
- **Next safe action:** None needed. Keep the ref. Optionally create a dated tag (requires approval) as a preservation anchor.

## P-2 — Mission 1: chief_of_staff wheel packaging

- **Branch:** `mission1/chief-of-staff-wheel-20260707T123250` — **PR #11 (open)**
- **Status:** Adds `chief_of_staff` package to wheel discovery + packaging contract test. MBP review: CONFORMS_WITH_FINDINGS.
- **Why parked:** Based on the doctrine lineage (P-1), not `main` — it cannot merge to `main` as-is. Also implements a Mission-1 step of the Olympus Build Program, which is paused in favor of W-1.
- **Resume condition:** P-1 lineage decision made, or the work is re-cut onto `main`.
- **Next safe action:** Leave PR #11 open with no further pushes.

## P-3 — Chief of Staff interface layer

- **Branch:** `feat/chief-of-staff-integration` — **PR #5 (open)**
- **Status:** 19 new files, interface-only `chief_of_staff/` package (morning brief, evening report, conversation, escalation, ranking, metrics), 114 tests passing, nothing imports it. Deliberately left open per its own directive.
- **Why parked:** Downstream of the Chief-of-Staff/Olympus program, which is paused. Not needed by W-1 v1.
- **Resume condition:** First real consumer is approved (e.g., Mission Control packet wiring, or W-1 needs escalation contracts).
- **Next safe action:** None. It is additive-only and conflicts are unlikely to grow.

## P-4 — Olympus Trust Engine v1 + Build Program + Execution Manifest

- **Branch:** `claude/olympus-trust-engine-0izzp5` — **PR #9 (open)**
- **Status:** Docs-only, 4 commits: `TRUST_ENGINE.md` (frozen v1), `TRUST_ENGINE_PILOT.md`, `olympus-build-program.md` (25 ranked missions, 3 evidence-gated phases), `OLYMPUS_EXECUTION_MANIFEST.md`.
- **Why parked:** This is the sprawl's engine — a 6-month, 25-mission program. Fresh Slate supersedes its sequencing; W-1 replaces it as the sole implementation lane for now. The frozen governance design itself remains valid reference material.
- **Resume condition:** W-1 reaches a working v1 and the operator explicitly re-opens the Build Program (possibly re-scoped around W-1 evidence).
- **Next safe action:** Leave PR #9 open, unmerged, unmodified.

## P-5 — Olympus CTO handoff narrative

- **Branch:** `claude/olympus-cto-handoff-bwyn8e` — **PR #10 (open)**
- **Status:** One doc, `docs/reflections/CTO_HANDOFF.md`, explicitly non-normative.
- **Why parked:** Reflective companion to a paused program; zero implementation impact.
- **Resume condition:** Any time the operator wants to merge docs; it is merge-safe whenever.
- **Next safe action:** None.

## P-6 — Olympus v2 architecture research

- **Branch:** `claude/olympus-v2-architecture-x9926r` (no PR)
- **Status:** 3 doc commits: v2 reference architecture, v1/v2 adoption matrix, and an executive disposition **already recording that v2 docs are research appendices, not the plan**.
- **Why parked:** Self-declared research appendix; building it would restart architecture churn.
- **Resume condition:** Only if a future architecture revision mission is opened with evidence from running systems.
- **Next safe action:** None.

## P-7 — Olympus Test Oracle v1

- **Branch:** `claude/olympus-test-oracle-v1-olzaqg` (no PR)
- **Status:** 1 doc commit — permanent verification oracle design.
- **Why parked:** Verification tooling for the paused Build Program.
- **Resume condition:** Build Program resumes (P-4), or W-1 needs an independent verification harness.
- **Next safe action:** None.

## P-8 — Reliability Intelligence / Failure Injection Campaign

- **Branch:** `claude/olympus-failure-injection-gu3fzc` (no PR)
- **Status:** 8 doc commits under `docs/reliability/`: 100 failure scenarios, top-10 reliability wins, detection gap analysis, failure pattern analysis, build-program risk mapping, integration matrix, executive packet.
- **Why parked:** Feeds the paused Build Program. High-value analysis; no code.
- **Resume condition:** Build Program resumes, or W-1 hardening phase wants the top-10 reliability wins as input.
- **Next safe action:** None. (Candidate for a future docs-only PR to `main` so the analysis isn't stranded on a branch.)

## P-9 — Olympus Architecture Intelligence (repo knowledge graph docs)

- **Branch:** `claude/hermes-knowledge-graph-6ps6gx` (no PR)
- **Status:** 3 doc commits: repository-wide knowledge graph, drift audit + canonical schema, Olympus integration spec.
- **Why parked:** Documentation-of-the-codebase effort, distinct from the merged Memory Graph v2 runtime feature (PR #7) despite the similar name. Not needed for W-1 v1.
- **Resume condition:** A docs/architecture-intelligence mission is approved.
- **Next safe action:** None.

## P-10 — Engineering Handbook + unwired-features register

- **Branch:** `claude/hermes-cloud-context-bootstrap-e82jy5` (no PR)
- **Status:** 7 doc commits: CLAUDE.md cloud context for Chad's operating model, 5-document engineering handbook, top-10 documented-but-unwired features register, upstream PR plan, and prepared PR bodies for branches A–C (P-11/P-12/P-13).
- **Why parked:** Meta/documentation lane; its actionable children are P-11–P-13.
- **Resume condition:** Operator wants the handbook merged, or decides to submit branches A–C upstream.
- **Next safe action:** None.

## P-11 / P-12 / P-13 — Branches A, B, C (small accuracy fixes)

- **Branches:** `docs/docstring-runtime-sync` (+1), `docs/env-example-accuracy` (+1), `fix/cli-default-display-corrections` (+1) — no PRs
- **Status:** One clean commit each, based on `main`; PR bodies already drafted on P-10.
- **Why parked:** Trivial but out-of-lane; opening PRs is external activity deferred under Fresh Slate.
- **Resume condition:** Operator approves opening the three prepared PRs (lowest-risk resumptions in the ledger).
- **Next safe action:** None until approval; then open PRs using the bodies on P-10.

## P-14 — Technical debt audit

- **Branch:** `claude/technical-debt-audit-ydvvfe` (no PR)
- **Status:** 3 commits: audit deliverables, executable debt-reduction roadmap, and a real test-hygiene commit (strict markers, dead flags removed).
- **Why parked:** Roadmap competes with W-1 for sequencing; test-hygiene commit is mergeable later.
- **Resume condition:** Operator schedules a debt-reduction window, or wants just the test-hygiene commit as a small PR.
- **Next safe action:** None.

## P-15 — Mission Control v0 broker

- **Branch:** `mission-control-v0` (no PR)
- **Status:** 6 commits, **code**: mock-only broker plugin skeleton with contracts/tests, plugin layout fix, read-only node connector (GET-only, breaker, schema redaction), registry-driven fleet, loopback MBP demo node, mac-mini SSH-tunnel enablement, desktop read-only state guard. 158 commits behind `main`.
- **Why parked:** Mission Control is the Executive Brain lane — a whole second product surface. Fresh Slate limits building to W-1. This is the **only copy** of this code.
- **Resume condition:** Explicit Mission Control mission re-opened; first step is rebasing onto current `main`.
- **Next safe action:** None. Preserve the ref (must-not-lose list).

## P-16 — Council gate v1

- **Branch:** `feat/hermes-council-gate-v1` — **PR #1 (open)**
- **Status:** Artifact-redaction hardening for the Council feature; human-reviewed "APPROVED FOR PR PROGRESSION — NOT APPROVED FOR MERGE"; gitleaks-clean at reviewed commit.
- **Why parked:** Its own merge gate requires separate human approval that was never given; feature lane inactive.
- **Resume condition:** Operator grants the merge approval its PR body requires (after a rebase-freshness check).
- **Next safe action:** None.

## P-17 — Full-codebase code-review fixes

- **Branch:** `claude/session-planning-u1c0bq` — **PR #3 (open)**
- **Status:** 1 High + 4 Medium correctness fixes (cron runaway-interval, scheduler cwd race, duplicate cron jobs, aux-client provider resolution, compressor boundaries) plus security hardening (SSRF guard, arg-injection guard, secret-env denylist). Full test suite was not run locally; relies on CI.
- **Why parked:** Real fixes, but merging requires verification work (run the suite, re-review 12-commits-behind drift) that belongs to a maintenance window, not the W-1 lane.
- **Resume condition:** A maintenance window where the suite is run green on a rebase of this branch.
- **Next safe action:** None until then. **This is the highest-value parked code** — the cron runaway-interval fix (High) protects the very scheduler/gateway infrastructure W-1 will lean on; schedule its maintenance window early.

---

## Maintenance-only lanes (not parked, not active)

These are one-commit operational patches on the doctrine lineage (P-1). They exist to keep the live machine running and take **no new feature work**.

| ID | Branch | Content |
|---|---|---|
| M-1 | `hotfix/gateway-launchd-no-replace-20260703` | omit `--replace` from launchd gateway service |
| M-2 | `split/54134-auth-token-redaction` | redact credential fragments from diagnostics |
| M-3 | `split/54134-x-search-handle-limit` | enforce twenty-handle filter limit in x-search |

Rule: only critical operational hotfixes of the same shape may be added, and each must be logged here.
