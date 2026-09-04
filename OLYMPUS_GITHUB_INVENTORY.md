# Project Olympus GitHub Inventory

Final status: `OLYMPUS_GITHUB_INVENTORY_READY`

## Scope and access notes

- Date of inventory: 2026-07-06.
- Requested repositories:
  - `chadsm-sys/mission-control-v0`
  - Hermes repositories available from the current checkout/remotes.
- Local checkout inspected: `/workspace/hermes-agent`, current branch `work`, current commit `93b565b55943fb5126ef5134e27960519f8ac91b`.
- No Git remotes are configured in this checkout (`git remote -v` returned no remotes), so the only Hermes GitHub-derived PR metadata available locally is the merge history already present in this checkout.
- GitHub API access from the shell was unavailable in this environment: `https://api.github.com/repos/chadsm-sys/mission-control-v0/pulls?...` failed with `Tunnel connection failed: 403 Forbidden`. Because of that, CI/check details, currently open PRs, and closed-unmerged PRs that are not represented in local merge commits could not be verified from GitHub.
- This inventory is read-only with respect to remote repositories: no merge, close, push, checkout, reset, stash, service restart, or production configuration operation was performed.

## Executive summary

The local checkout contains four recent Olympus/Mission-Control-relevant PR merge commits on top of the upstream Hermes history:

| PR | Title / local merge subject | State | Merged? | In current branch? | Classification |
| --- | --- | --- | --- | --- | --- |
| #4 | `docs(chief-of-staff): foundational philosophy for Hermes + Mission Control` | closed | yes | yes | docs / philosophy |
| #6 | `feat(opportunity-scout): long-term Opportunity Scout engine` | closed | yes | yes | real code + tests + docs |
| #7 | `Memory Graph v2: governed knowledge graph memory provider (memorygraph)` | closed | yes | yes | real code + tests + docs |
| #8 | `docs(executive-loop): M21 Executive Operating Loop — Hermes-side contracts` | closed | yes | yes | docs / contracts |

No locally visible open or blocked PRs were found, but this is an access-limited conclusion: the checkout has no remote and GitHub PR listing could not be fetched from the shell.

## Relevant PR records

### PR #4 — Chief-of-Staff philosophy for Hermes + Mission Control

- PR number/title: `#4`, `docs(chief-of-staff): foundational philosophy for Hermes + Mission Control`.
- State: closed locally by merge commit.
- Merged or not: merged.
- Base branch: not visible from local metadata; presumed current integration branch from merge history.
- Head branch: `chadsm-sys/docs/chief-of-staff-philosophy` from the merge subject.
- Head SHA: `e45a43a36348ee832c43e463b645c98d9f5c8cc6`.
- Merge SHA: `92bbe8633da3765182933e0e9faa56a7e67f8f25`.
- CI/check status: not visible locally.
- Milestone/component: Mission Control / chief-of-staff operating philosophy; overlaps conceptually with Executive Loop and Mission Control.
- Whether it is in main/current branch: yes, present in current branch history.
- Real code vs docs/demo-only: docs-only.
- Files changed:
  - `docs/chief-of-staff/BOTTLENECK_ENGINE.md`
  - `docs/chief-of-staff/COMPOUND_ENGINE.md`
  - `docs/chief-of-staff/DECISION_ENGINE.md`
  - `docs/chief-of-staff/EXECUTIVE_COACH.md`
  - `docs/chief-of-staff/HUMAN_FIRST.md`
  - `docs/chief-of-staff/MISSION.md`
  - `docs/chief-of-staff/PHILOSOPHY.md`

### PR #6 — Opportunity Scout engine

- PR number/title: `#6`, `feat(opportunity-scout): long-term Opportunity Scout engine`.
- State: closed locally by merge commit.
- Merged or not: merged.
- Base branch: not visible from local metadata; merge parent shows it merged after PR #4.
- Head branch: not preserved in merge subject; merge body records audited head `20f5410b9`.
- Head SHA: `20f5410b98ed1de2ce40e05aef21d973f8958ed0`.
- Merge SHA: `a0362bfba14273fe550eed47fa4e69787061cdef`.
- CI/check status: not visible locally.
- Milestone/component: Opportunity/Income Scout; Runtime Foundation-adjacent because it adds durable local engine, CLI, lifecycle, scoring, validation, and tests.
- Whether it is in main/current branch: yes, present in current branch history.
- Real code vs docs/demo-only: real code with tests and design docs.
- Files changed:
  - `docs/design/opportunity-scout-engine.md`
  - `plugins/opportunity_scout/README.md`
  - `plugins/opportunity_scout/__init__.py`
  - `plugins/opportunity_scout/cli.py`
  - `plugins/opportunity_scout/confidence.py`
  - `plugins/opportunity_scout/dedup.py`
  - `plugins/opportunity_scout/engine.py`
  - `plugins/opportunity_scout/ingestion.py`
  - `plugins/opportunity_scout/lifecycle.py`
  - `plugins/opportunity_scout/models.py`
  - `plugins/opportunity_scout/scoring.py`
  - `plugins/opportunity_scout/store.py`
  - `plugins/opportunity_scout/validation.py`
  - `tests/opportunity_scout/__init__.py`
  - `tests/opportunity_scout/test_engine_cli.py`
  - `tests/opportunity_scout/test_ingestion_dedup.py`
  - `tests/opportunity_scout/test_models_store.py`
  - `tests/opportunity_scout/test_scoring_confidence.py`
  - `tests/opportunity_scout/test_validation_lifecycle.py`

### PR #7 — Memory Graph v2 / governed knowledge graph memory provider

- PR number/title: `#7`, `Memory Graph v2 — governed knowledge graph memory provider (memorygraph)`.
- State: closed locally by merge commit.
- Merged or not: merged.
- Base branch: not visible from local metadata; merge parent shows it merged before PR #4 in current history order.
- Head branch: not preserved in merge subject.
- Head SHA: `154119b01287c22d425b1a8974d0a9d4582f44f0`.
- Merge SHA: `e9b51e530cb4a17d13b7e5838118649a656d6e92`.
- CI/check status: not visible locally.
- Milestone/component: Runtime Foundation / memory substrate; Mission Control support infrastructure.
- Whether it is in main/current branch: yes, present in current branch history.
- Real code vs docs/demo-only: real code with tests and docs.
- Files changed:
  - `hermes_cli/config.py`
  - `hermes_cli/subcommands/memory.py`
  - `plugins/memory/memorygraph/DESIGN.md`
  - `plugins/memory/memorygraph/README.md`
  - `plugins/memory/memorygraph/__init__.py`
  - `plugins/memory/memorygraph/governance.py`
  - `plugins/memory/memorygraph/plugin.yaml`
  - `plugins/memory/memorygraph/store.py`
  - `scripts/release.py`
  - `tests/plugins/memory/test_memorygraph_governance.py`
  - `tests/plugins/memory/test_memorygraph_provider.py`
  - `tests/plugins/memory/test_memorygraph_store.py`
  - `website/docs/user-guide/features/memory-providers.md`

### PR #8 — M21 Executive Operating Loop Hermes-side contracts

- PR number/title: `#8`, `docs(executive-loop): M21 Executive Operating Loop — Hermes-side contracts`.
- State: closed locally by merge commit.
- Merged or not: merged.
- Base branch: not visible from local metadata; merge parent shows it merged after PR #6.
- Head branch: `chadsm-sys/docs/executive-operating-loop-contracts` from the merge subject.
- Head SHA: `f5e6b09debbc5b82ba40cf3498843b8249d657db`.
- Merge SHA: `93b565b55943fb5126ef5134e27960519f8ac91b`.
- CI/check status: not visible locally.
- Milestone/component: M21 / Executive Loop / Hermes-side contracts; related to Morning/Evening packets and dashboard/brief surfaces at the contract level.
- Whether it is in main/current branch: yes, it is the current HEAD of branch `work`.
- Real code vs docs/demo-only: docs-only contract specification.
- Files changed:
  - `docs/executive-operating-loop-contract.md`

## Blocked PRs and missing gates

No blocked PRs are visible from the local checkout. Exact missing gates cannot be identified without GitHub PR/check access. The concrete missing inventory gates for this environment are:

1. GitHub PR list access for `chadsm-sys/mission-control-v0`.
2. GitHub check-suite/status access for each PR head SHA.
3. GitHub visibility into open and closed-unmerged PRs.
4. Git remotes for the local checkout, or another authoritative local clone containing remote refs.

## Duplicate or overlapping builds

- PR #4 and PR #8 overlap conceptually around Mission Control / Executive Loop / chief-of-staff operating doctrine, but they do not duplicate files. PR #4 is broad philosophical doctrine under `docs/chief-of-staff/`; PR #8 is a focused M21 contract under `docs/executive-operating-loop-contract.md`.
- PR #6 and PR #7 are both real runtime-support builds, but they target different domains: Opportunity Scout vs governed memory provider. They do not appear duplicative from local file paths.
- PR #6 is the only locally visible Opportunity/Income Scout implementation.
- PR #8 is the only locally visible M21 Executive Operating Loop contract document.

## Real code vs docs/demo-only classification

- Real code:
  - PR #6 Opportunity Scout engine: plugin package, CLI, models, persistence, scoring, lifecycle, validation, confidence, deduplication, ingestion, and tests.
  - PR #7 Memory Graph v2: plugin package, governance, store, CLI/config integration, release metadata, docs, and tests.
- Docs/demo-only:
  - PR #4 Chief-of-Staff philosophy: docs-only.
  - PR #8 Executive Operating Loop contracts: docs-only.

## Milestone/component coverage matrix

| Requested focus | Locally visible coverage |
| --- | --- |
| M11 | no direct local evidence found |
| M12 | no direct local evidence found |
| M13 | no direct local evidence found |
| M14 | no direct local evidence found |
| M16 | no direct local evidence found |
| M20 | no direct local evidence found |
| M21 | PR #8, Executive Operating Loop contracts |
| Mission Control | PR #4 and PR #8 docs; PR #6 and PR #7 supporting engines |
| Executive Loop | PR #8 directly; PR #4 conceptually |
| Value Loop | no direct local evidence found |
| Runtime Foundation | PR #7 directly; PR #6 partially as a local engine |
| Opportunity/Income Scout | PR #6 directly |
| Expert Witness | no direct local evidence found |
| Morning/Evening packets | PR #8 contract-level reference only; no implementation verified locally |
| Dashboard/brief surfaces | PR #8 contract-level reference only; no implementation verified locally |

## Recommended canonical Olympus source-of-truth

Given the evidence available in this environment, the canonical source-of-truth should be the GitHub repository/branch that contains the current local merge history ending at `93b565b55943fb5126ef5134e27960519f8ac91b`, because it already contains the merged PR #4, #6, #7, and #8 Olympus/Mission-Control work and does not depend on an MBP being powered on.

Operationally:

1. Treat the remote that owns commit `93b565b55943fb5126ef5134e27960519f8ac91b` as the canonical Hermes/Olympus integration source.
2. Treat `chadsm-sys/mission-control-v0` as canonical only after GitHub PR/API visibility confirms that its default branch contains commit `93b565b55943fb5126ef5134e27960519f8ac91b` or an equivalent descendant.
3. Do not treat local-only MBP worktrees as canonical unless their commits are pushed to GitHub and visible from a GitHub branch or PR.
4. For future Olympus inventory, require a remote-configured clone or GitHub token with read-only PR/check permissions so open/blocked/unmerged PRs and CI gates can be recorded precisely.
