# The First Three PRs — hermes-agent debt reduction

**Date:** 2026-07-06 · **Baseline:** `93b565b`. These three PRs come **before any refactor of any size**. All three are test/CI-only — zero production code paths change — and together they turn the rest of the roadmap from "carefully reviewed hope" into "CI-proven mechanics". None has been opened; this is the plan.

Why these three and not a quick-win deletion sweep first: the audit showed the test suite currently **lies in three specific ways** (phantom timeout marks, silently forked test files, an unrunnable stress suite) and has **no defenses** against the two failure modes that will threaten the refactor program (god files regrowing; new copies of deduplicated helpers appearing). Fix the lie, install the defenses, then start deleting.

---

## PR-1 — Pytest guardrails: make the suite tell the truth

**Branch name suggestion:** `tests/pytest-guardrails`

**Changes (test/config only):**
1. `pyproject.toml:329-336` — add `--strict-markers` to `addopts`; register the markers actually in use (`integration`, `real_concurrent_gate`, and `timeout` pending item 2; `live_system_guard_bypass` is registered dynamically in `tests/conftest.py:530` — keep that, note it in a comment).
2. Resolve the phantom-timeout class (TD-099): add `pytest-timeout` to the `dev` extra (recommended — the only current cap is the coarse 140 s per-file kill in `scripts/run_tests_parallel.py:75`), which makes the existing `pytest.mark.timeout(180)` (`tests/docker/conftest.py:46`) and `@pytest.mark.timeout(300)` (`tests/test_wheel_locales_e2e.py:37,95`) real; correct the stale comment claiming a global `--timeout=30` exists. *Alternative if maintainers prefer zero new deps: delete the three marks and their comments — but then `--strict-markers` must land in the same PR so no dead marks can reappear.*
3. Fix the unrunnable stress suite (TD-071): in `tests/stress/conftest.py`, make `collect_ignore_glob` (:32-36) conditional on the absence of `--run-stress` instead of unconditional, so the flag defined at :24-30 and the skip hook at :13-21 actually function. (Whether stress gets a CI lane is a separate later decision — this PR only makes the existing switch honest.)
4. Delete the stale conftest reference to the non-existent "subprocess-per-test plugin"/`isolate_timeout` ini key (`tests/conftest.py:445-449`).

**Expected behavior change:** CI may newly fail on any misspelled marker anywhere in the suite — that is the feature. `pytest --run-stress` starts collecting 9 files (run locally to confirm they still pass or skip cleanly; they do not join default CI in this PR).

**Tests required:** full suite green; `pytest --collect-only -q tests/stress --run-stress` shows non-zero collection; `pytest --markers` lists the registered set.

**Rollback:** single revert; nothing depends on it yet.

**Risk:** LOW. **Size:** ~40 lines across 4 files.

---

## PR-2 — Merge the forked test files; remove test-hygiene fossils

**Branch name suggestion:** `tests/merge-forked-cli-tests`

**Changes (test only):**
1. Merge `tests/test_cli_skin_integration.py` (143 lines — carries `TestCompactBannerSkinIntegration`, 3 banner tests + a status-bar assert missing from the copy) into `tests/cli/test_cli_skin_integration.py` (117 lines — carries 2 voice-prompt tests missing from root); delete the root file. (TD-102)
2. Merge `tests/test_cli_file_drop.py` (194 lines) into `tests/cli/test_cli_file_drop.py` (249 lines — already a superset by 4 tests; diff first to confirm the root copy contributes nothing unique, else port the delta); delete the root file.
3. Delete the commented-out file-wide skip fossil `tests/run_agent/test_413_compression.py:10` (`#pytestmark = pytest.mark.skip(...)`) — the autouse `_no_compression_sleep` fixture (:28-37) is the real mechanism and stays.
4. Delete the never-executed `time.sleep(60)` booby trap in `tests/tools/test_mcp_stability.py:447` (the fake is inspected, never called).

**Expected behavior change:** none in production. Collected-test count must **increase or hold** (union of both forks, minus exact duplicates) — record `pytest --collect-only -q tests/cli tests/run_agent tests/tools | wc -l` before/after in the PR body.

**Tests required:** merged files green; a PR-body table listing each test function and which fork it came from, so the reviewer can verify no test was dropped.

**Rollback:** single revert restores both forks.

**Risk:** LOW. **Size:** net ~-150 lines, 4 files.

**Why before refactors:** these files test `cli.py` surfaces (skin/banner, file drop) that lanes M and Q will touch; refactoring against a silently-forked test suite means half the assertions don't run against your change.

---

## PR-3 — The refactor safety net: ratchet + golden snapshot + antipattern guard

**Branch name suggestion:** `ci/refactor-safety-net`

**Changes (CI + test only):**
1. **God-file size ratchet.** A small script (e.g. `scripts/check_file_ratchet.py`) + step in the existing lint workflow (`.github/workflows/lint.yml`) with a checked-in baseline for the six god files: `agent/conversation_loop.py` (4,421), `gateway/run.py` (16,795), `cli.py` (13,984), `hermes_cli/main.py` (12,488), `hermes_cli/web_server.py` (11,899), `hermes_cli/auth.py` (8,050). Rule: line count may decrease or hold; any increase fails with a pointer to the roadmap. (This is the enforcement mechanism the audit found missing everywhere — TD-030's `TextBatchAggregator` sat unadopted precisely because nothing pushed back.)
2. **Gateway-config golden snapshot** (lane G PR#1, pulled forward because it is pure test): a test fixture setting a representative env matrix — all 13 platform `*_HOME_CHANNEL/,_NAME/,_THREAD_ID` triples, the bool variants including `on` (documenting today's inconsistent truth per TD-093), a non-numeric port (documenting today's abort per TD-094) — and snapshotting the resulting `GatewayConfig`. This pins current behavior byte-for-byte so the later declarative-table PR (and the two labeled behavior-fixes) diff against recorded truth instead of reviewer memory.
3. **Mock-antipattern guard extension.** The gateway conftest already ships an adapter antipattern scan (`tests/gateway/conftest.py:246-368`); extend it to fail on any **new** file-local definition of `_ensure_discord_mock`/`_ensure_telegram_mock`/`_ensure_slack_mock`/`_make_runner`, with the current 40+ offenders grandfathered in a checked-in allowlist that lane T burns down (ratchet: the allowlist may only shrink).

**Expected behavior change:** none at runtime; CI gains three new failure modes, all intentional.

**Tests required:** the snapshot test passes against `93b565b` behavior; ratchet script has a self-test (baseline violation → exit 1); antipattern scan catches a synthetic new `_ensure_discord_mock` in a scratch test file (verified locally, not committed).

**Rollback:** revert removes the gates; no production coupling.

**Risk:** LOW. **Size:** ~250 lines, all new files + one workflow step + one conftest extension.

---

## After these three land

The order of everything else is in `TECH_DEBT_REMEDIATION_ROADMAP.md` §6. The immediate next moves become: lane Q deletions (now protected by PR-1/2's honest suite), lane T mock dedup (now enforced by PR-3's guard), and lane A's wecom `TextBatchAggregator` pilot (now protected by the ratchet from regrowing what it deletes).

**Explicitly not in these three PRs:** any production code, any deletion of production code, any dependency removal, the ruff F401 sweep (lane Q, needs the honest suite first), and the three latent-bug fixes (TD-090/093/094 — each needs its lane's test scaffolding, landed here, before the fix).
