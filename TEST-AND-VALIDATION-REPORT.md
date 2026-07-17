# Test and Validation Report

Date: 2026-07-17
Implementation head: `c76f77c84fc50bfcd30a067852f025bdbe8ebb4f`

## Final test result

The repository-required wrapper ran the affected component suites in a clean environment:

```text
9 files
217 tests passed
0 failed
```

Coverage included:

- memorygraph store, provider, and governance regressions: 87 passing;
- Opportunity Scout ingestion, store, scoring, confidence, lifecycle, engine, and CLI regressions: 84 passing;
- deterministic Morning Brief regressions: 46 passing.

## SQLite checks

- File-backed connections assert `journal_mode=wal`.
- Connections assert explicit `busy_timeout=5000` milliseconds.
- `synchronous=FULL` remains in force.
- A held `BEGIN IMMEDIATE` writer deterministically makes a second connection wait, then commit after release.
- Synchronized cross-connection exclusive writes leave one active claim and reject the competing raw write at the database boundary.
- Reopening a pre-index duplicate-active database atomically marks the ambiguous group `contradicted`, records `exclusive_invariant_repaired`, creates the unique partial index, and returns `PRAGMA integrity_check=ok`.
- Contention tests also finish with `PRAGMA integrity_check=ok`.

## Static and repository checks

| Gate | Result |
|---|---|
| Ruff lint on affected implementation and test files | PASS — `All checks passed!` |
| Ruff formatting on every remediation hunk using `--range --check` | PASS |
| Whole-file Ruff formatting probe | Imported component baselines are not globally Ruff-formatted; broad formatting was intentionally not applied because it would violate the no-unrelated-formatting boundary. |
| `git diff --check 2b828e3cc..HEAD` | PASS |
| Gitleaks, redacted, remediation range `2b828e3cc..c76f77c84` | PASS — six commits, about 15.8 KB scanned, no leaks found |

The hunk-range formatter was used because these components arrived from an already-tested integration lineage whose surrounding files predate the current formatter output. Only remediation lines were formatted; no broad style rewrite was bundled.

## Not run

- The repository-wide Hermes suite was not run; validation was intentionally limited to the three affected components and their full local regression suites.
- No live gateway, Telegram, cron, launchd, credential, runtime database, or network integration test was run.
- No deployment, promotion, push, merge, or PR validation was run.

## Remaining review focus

An independent reviewer should pay particular attention to the fail-closed legacy repair policy: duplicate active exclusive values are all moved to `contradicted` for later governance resolution rather than selecting a winner during startup.
