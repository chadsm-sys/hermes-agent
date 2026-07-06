# Hermes Testing Guide

How the test suite is organized, how to run it, what CI enforces, and the
conventions every new test must follow.

Part of the [Hermes Engineering Handbook](README.md).

---

## 1. Quick start

```bash
# Preferred — matches CI (hermetic env). See CONTRIBUTING.md "Run tests".
scripts/run_tests.sh

# Alternative (activate the venv first):
pytest tests/ -v

# One file / one test:
pytest tests/cron/test_jobs.py -q
pytest tests/gateway/test_session.py::test_build_session_key -q
```

- `testpaths = ["tests"]` and `addopts = "-m 'not integration'"` are set in
  `pyproject.toml` — **integration tests are excluded by default**.
- Markers: `integration` (needs external services), `real_concurrent_gate`
  (opts out of the concurrent-instance stub), `live_system_guard_bypass`
  (opts out of the live-system guard, see §4).
- Pinned dev deps: `pytest==9.0.2`, `pytest-asyncio==1.3.0`,
  `ruff==0.15.10`, `ty==0.0.21`.

## 2. Suite map

~17k tests across ~900 files (May 2026 count). Directory → subsystem:

| Directory | ~Files | Covers |
|---|---|---|
| `tests/hermes_cli/` | 345 | CLI commands, config, setup wizard, auth/OAuth, doctor, skins, skills hub/install, MCP config |
| `tests/gateway/` | 318 | Platform adapters (34 Telegram files, ~30 Discord, plus Slack/Signal/WhatsApp/Feishu/…), sessions, streaming, delivery, restart/drain, authz/allowlists, webhooks, pairing |
| `tests/tools/` | 260 | Tool implementations: terminal + environments, file ops, web/browser, skills guard/hub, delegation, code-exec RPC, MCP client |
| `tests/agent/` | 173 | Agent internals: prompt builder, context compressor/engine, retry utils, error classifier, SSL guard, credential pool, auxiliary client, curator |
| `tests/run_agent/` | 110 | The core `AIAgent` loop: tool dispatch, retries, fallback, compression regressions, codex paths (own `conftest.py`) |
| `tests/cli/` | 79 | Top-level `cli.py` / prompt_toolkit TUI paths |
| `tests/plugins/` | 60 | Plugin framework + individual plugins (memorygraph, dashboard_auth contract, langfuse, kanban, achievements…) |
| `tests/cron/` | 19 | Schedule parsing, job store + cross-process lock, scheduler, prompt-injection scan, delivery |
| `tests/acp/` + `tests/acp_adapter/` | 18 | ACP editor adapter: server, permissions, edit approval, provenance |
| `tests/docker/` | 13 | Dockerfile/compose, browser discovery, tini shim |
| `tests/tui_gateway/` | 12 | JSON-RPC TUI backend + WebSocket transport |
| `tests/skills/` | 12 | Bundled skills (stdlib+pytest+mock only, no network) |
| `tests/stress/` | 10 | Concurrency/load |
| `tests/integration/` | 8 | External-service tests (marker `integration`, off by default) |
| `tests/honcho_plugin/` | 7 | Honcho memory provider |
| `tests/providers/` | 6 | Provider profiles, plugin discovery, transport parity |
| `tests/opportunity_scout/` | 6 | Scout engine (determinism-enforced, see §5) |
| `tests/e2e/` | 5 | End-to-end (own CI job) |
| root `tests/test_*.py` | ~90 | hermes_state (176 KB), tui_gateway server (264 KB), logging (40 KB), toolsets, utils, trajectory compressor, SQL injection, WAL fallback… |

The TypeScript TUI has its own suite: `ui-tui/src/__tests__/` (71 vitest
files) plus tests in the vendored `ui-tui/packages/hermes-ink/`.

## 3. Hermetic environment (`tests/conftest.py`)

The autouse `_hermetic_environment` fixture enforces four invariants for
every test:

1. **No real credentials.** All credential-shaped env vars are unset —
   suffix filter (`*_API_KEY`, `*_TOKEN`, `*_SECRET`, …) plus an explicit
   ~130-name frozenset. CI additionally passes empty
   `OPENROUTER_API_KEY`/`OPENAI_API_KEY`/`NOUS_API_KEY`.
2. **Isolated `HERMES_HOME`.** A per-test tempdir with pre-made
   `sessions/ cron/ memories/ skills/` — tests must never write to the
   real `~/.hermes/` (AGENTS.md pitfall). Note `HOME` itself is NOT
   redirected (that broke CI subprocesses); tests that mock `Path.home()`
   must also set `HERMES_HOME` (AGENTS.md profile rule #4).
3. **Deterministic runtime.** `TZ=UTC`, `LANG/LC_ALL=C.UTF-8`,
   `PYTHONHASHSEED=0`.
4. **No cloud lookups.** AWS IMDS disabled, `TIRITH_ENABLED=false`,
   plugin singleton reset. ~150 behavioral `HERMES_*`/platform vars unset.

Other shared fixtures: `mock_config`, `tmp_dir`,
`_ensure_current_event_loop` (event loop for sync tests on py3.11+).

## 4. The live-system guard

`_live_system_guard` (autouse, `tests/conftest.py`) exists because test
runs once SIGTERM'd the developer's real running gateway five times in
three days (PR #23285). It monkeypatches `os.kill`/`os.killpg`,
`subprocess.*`, `os.system`, `pty.spawn`, and
`asyncio.create_subprocess_*` to hard-fail on:

- killing PIDs outside the test's own process subtree;
- `systemctl <verb> hermes-gateway` mutations;
- `pkill`/`killall`/`taskkill`/`fuser` aimed at hermes/python;
- any `hermes update` (would `git pull` over the live checkout).

It inspects full command strings (catches `bash -c`, `sudo`, `env`,
`setsid` wrappers). Opt out only with
`@pytest.mark.live_system_guard_bypass` and a good reason.

## 5. Determinism enforcement

Chad's governance layer requires **determinism over cleverness — no model
calls in ranking, escalation classification, or status reporting**
(`docs/executive-operating-loop-contract.md` §9). In this tree that is
enforced where the governed engines live:

- `tests/opportunity_scout/test_scoring_confidence.py::test_determinism`
  asserts identical inputs → identical scores; the scoring/lifecycle code
  is pure stdlib with no network and an injectable clock. Companion tests
  pin the invariants: weights must sum to 1.0, confidence clamps,
  reason-required transitions, terminal stages have no exits,
  transition-matrix consistency, corrupt store quarantined not lost.
- `tests/plugins/memory/test_memorygraph_governance.py` (24 tests) pins
  the memorygraph governance engine: duplicate reinforcement,
  supersede-vs-contradict, aging/decay floors, promotion gates
  (candidate→established→core), **contradicted claims never promote**,
  and confidence clamping. The store takes an injectable `now` callable
  precisely so these are deterministic.
- The escalation engine (`chief_of_staff.escalation`) is in open PR #5,
  not on main; its rule-table tests (114 tests) live on that branch.

Structural determinism for everything else comes from the hermetic
conftest (§3) and empty API keys in CI — any test that accidentally
depends on a live model call fails fast.

## 6. CI pipeline

`.github/workflows/tests.yml` — the required `test` job:

- ubuntu-latest, 30-min timeout, `fail-fast: false`, **6-way matrix**
  (`slice: 1..6`), slices balanced by cached per-file durations (LPT).
- Steps: checkout → restore `test_durations.json` cache → install
  SHA-pinned ripgrep → install `uv` → `uv sync --locked --python 3.11
  --extra all --extra dev` → `python scripts/run_tests_parallel.py
  --slice N/6` with empty provider keys → upload durations. A
  `save-durations` job (main only) merges slice durations back.
- **Runner model:** `scripts/run_tests_parallel.py` runs each of ~850
  test files in a **fresh subprocess** (bounded ThreadPoolExecutor). Per
  file, not per test: per-test spawn (~250 ms × 17k) was too slow;
  per-file kills cross-file module-state leakage, the historic flake
  source. Consequence: **intra-file test ordering is your
  responsibility** — a file's tests share one interpreter.
- Separate `e2e` job (15 min): packaged-wheel i18n smoke test
  (`pytest -m integration tests/test_wheel_locales_e2e.py`) then
  `pytest tests/e2e/`.

Other gates: `lint.yml` (ruff — deliberately minimal: only `PLW1514`
unspecified-encoding is enforced repo-wide, because bare `open()`
defaults to cp1252 on Windows; tests/skills/plugins exempt),
`typecheck.yml` (ty), `docker-lint.yml` (hadolint), `osv-scanner.yml` +
`supply-chain-audit.yml`, `uv-lockfile-check.yml`,
`contributor-check.yml` (AUTHOR_MAP attribution — see commit `c38ac93`),
`history-check.yml`, `skills-index*.yml`, docs-site checks, Windows
installer build, PyPI upload.

## 7. Conventions for new tests

- **Test behavior and invariants, not snapshots.** AGENTS.md bans
  change-detector tests.
- **Never touch the real `~/.hermes/`** — use the hermetic fixtures'
  `HERMES_HOME`.
- Skill tests: `tests/skills/test_<skill>_skill.py`, stdlib + pytest +
  `unittest.mock` only, no live network, use `monkeypatch`/`tmp_path`.
- Cross-platform: skip POSIX-only assertions (symlinks, `0o600` modes)
  with `@pytest.mark.skipif(sys.platform == "win32")`.
- Catch specific exceptions; log with `exc_info=True` for unexpected
  errors (code-style rule that also applies to test helpers).
- Conventional Commits (`fix:`, `feat:`, `test:`, `docs:`) and matching
  branch prefixes.
- Before opening a PR: run `scripts/run_tests.sh` for CI parity, test
  manually with `hermes`, keep the PR focused.

## 8. Testing strategy per subsystem (summary)

| Subsystem | Strategy in force | Gaps / future improvements |
|---|---|---|
| Agent core | Regression tests keyed to real incidents (`test_1630_context_overflow_loop`, `test_413_compression`, `test_18028_content_policy_blocked`) + transport parity tests | Provider matrix is mock-based; a nightly live-provider canary would catch upstream API drift |
| Gateway | Per-platform suites + reliability suites (drain races, split-brain locks, FD leaks) | Long-run soak tests exist only as `tests/stress/`; no chaos testing of adapter reconnect storms |
| Plugins/memory | Contract tests (dashboard_auth contract, plugin discovery import-ban) + governance tests | No fuzzing of `plugin.yaml` manifests |
| Cron/webhooks | Cross-process lock tests, HMAC/rate-limit tests, injection-scan tests | Scheduler catch-up behavior under clock jumps is lightly covered |
| Chief-of-staff layer | Determinism + lifecycle invariants (scout, memorygraph) | Escalation/ranking tests arrive with PR #5; contract §9 invariants have no repo-wide lint (e.g. an import-ban test for model calls inside governed modules) |
| TUI/Web | 71 vitest files (client) + protocol tests (Python side) | No end-to-end browser test of the dashboard chat path |
