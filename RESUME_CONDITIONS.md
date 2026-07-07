# Resume Conditions

A parked lane may be un-parked **only** when its condition below is met **and** the operator explicitly approves resumption. Until both hold, the lane takes no commits, no rebases, no merges.

General preconditions for resuming *any* lane:

1. W-1 is not blocked or abandoned mid-milestone (one active lane at a time).
2. The resumed branch is first checked for drift against current `main` (rebase or re-cut decision recorded).
3. The resumption is logged in OLYMPUS_FRESH_SLATE_LEDGER.md (class change PARKED → ACTIVE).

| Lane | Resume condition | First action on resume |
|---|---|---|
| P-1 Continue-Until-Fork lineage | Operator opens an explicit "lineage reconciliation" mission deciding: merge into `main`, formally fork, or archive-as-history. | Inventory the 2,574-commit delta by subsystem; propose reconciliation plan before touching anything. |
| P-2 Mission 1 wheel (PR #11) | P-1 lineage decision made, **or** operator asks for a `main`-based re-cut. | Re-cut the 2-commit delta onto `main`; retarget or close-and-replace PR #11. |
| P-3 Chief of Staff interfaces (PR #5) | A first real consumer is approved (Mission Control packets, or W-1 escalation needs). | Rebase check; then wire the consumer in the consumer's lane, merging #5 only when imported. |
| P-4 Trust Engine / Build Program (PR #9) | W-1 v1 shipped **and** operator re-opens the Build Program. | Re-scope the 25 missions against W-1 evidence; merge docs if still authoritative. |
| P-5 CTO handoff (PR #10) | Operator wants the reflective doc in `main` (merge-safe any time). | Merge after link check. |
| P-6 Olympus v2 architecture | A future evidence-driven architecture revision mission. | Treat as research appendix input, per its own disposition commit. |
| P-7 Test Oracle v1 | Build Program resumes, or W-1 needs an independent verification harness. | Review oracle design against W-1's actual test surface. |
| P-8 Reliability campaign | Build Program resumes, or W-1 hardening phase starts. | Extract "Top 10 Reliability Wins" as W-1 hardening input; consider docs-only PR to `main`. |
| P-9 Architecture knowledge graph | A docs/architecture-intelligence mission is approved. | Drift-audit the graph against current `main` first (repo has moved). |
| P-10 Engineering handbook | Operator wants handbook merged or branches A–C submitted. | Open docs PR; use prepared PR bodies for A–C. |
| P-11/12/13 Branches A, B, C | Operator approves opening the three prepared PRs. | Open PRs as-is (lowest-risk resumptions in this ledger). |
| P-14 Tech-debt audit | A scheduled debt-reduction window, or cherry-pick request for the test-hygiene commit. | Split test-hygiene commit into its own small PR first. |
| P-15 Mission Control v0 | Explicit Mission Control mission re-opened. | Rebase onto current `main` (158 behind); re-run its contract tests before any new feature. |
| P-16 Council gate (PR #1) | The separate human **merge** approval its PR body requires. | Rebase-freshness check + re-run gitleaks, then merge. |
| P-17 Code-review fixes (PR #3) | A maintenance window with the full test suite run green on a rebase. | Rebase, run `pytest tests/ -q`, re-verify the High cron fix, then merge. **Recommended first resumption** — it protects the scheduler/gateway infrastructure W-1 depends on. |
| M-1/M-2/M-3 splits & hotfix | Not resumable as feature lanes. Fold into `main` (or the reconciled lineage) during the P-1 reconciliation mission. | Carry each 1-commit delta over; then the branch becomes a dead candidate. |
| D-* candidates | See DEPRECATED_OR_DUPLICATIVE_BUILDS.md — resumption is not expected; salvage is by cherry-pick only, with the source ref preserved. | — |
