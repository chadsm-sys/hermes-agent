# Tech Debt Remediation Roadmap — hermes-agent

**Date:** 2026-07-06 · **Baseline commit:** `93b565b` · **Audit evidence:** `TECH_DEBT_REGISTER.md` (TD-xxx IDs), `TOP100_REFACTOR_OPPORTUNITIES.md` (#N ranks), `QUICK_WINS.md`, `LONG_TERM_SIMPLIFICATIONS.md` (P1–P11 programs). This document plans work only — **no code has been changed, no refactors performed, no PRs opened.**

**Operating principle:** every lane ships as small, independently-revertable PRs that are behavior-preserving unless explicitly labeled BEHAVIOR-FIX (a latent-bug repair with a test proving the old behavior was wrong). The audit's most repeated failure mode was *consolidations built but never adopted* (TD-030, TD-070, half-done TD-011) — therefore every lane ends with an **enforcement PR** (lint rule / CI check / deleted legacy path) and no lane is "done" until the duplicate it replaces is deleted.

---

## 1. Top 10 debt items — ranked

Scoring: each dimension 1–5 (5 = worst/highest). **Operator risk** = probability a defect here hurts a running user (auth breaks, config fails to load, sessions leak). **Maintenance drag** = recurring hours burned navigating/syncing it. **Bug probability** = likelihood of NEW defects appearing because of the structure (drifting forks score high). **Consolidation leverage** = how much other work gets cheaper once fixed. **Ease of review** = how tractable the PRs are for upstream maintainers (5 = easy). Rank = weighted sum with ease-of-review as a multiplier on practical priority — we deliberately rank reviewable-and-dangerous above important-but-unreviewable.

| # | Item (evidence) | Op. risk | Maint. drag | Bug prob. | Leverage | Review ease | Verdict |
|---|---|---|---|---|---|---|---|
| 1 | **Platform text-batching fork ×8 + unadopted `TextBatchAggregator`** — TD-030/048; `gateway/platforms/helpers.py:81` (0 importers) vs ~526 duplicated lines in 8 adapters, already drifted | 3 | 4 | 5 | 5 | 5 | The archetype of the repo's disease; the fix already exists and each adapter is an independent, mechanically-reviewable PR |
| 2 | **Provider-registry sextuplets + lookup-normalization bug** — TD-031/090/096; `agent/*_registry.py` ×6 (954 lines, sim 0.79–0.86), whitespace/case-dependent lookups, video_gen missing image_gen's availability fix | 3 | 3 | 5 | 5 | 5 | Small surface, generic replacement proven in-repo (`agent/transports/__init__.py:17-46`), fixes two latent bugs |
| 3 | **Test-suite trust: phantom timeouts, forked test files, mock ×17 dup** — TD-099/102/101/071; no `--strict-markers`, `tests/test_cli_*` diverged forks, ~1,240 dup mock lines, unrunnable stress suite | 2 | 4 | 4 | 5 | 5 | Must land FIRST — every other lane's safety depends on trusting the suite; all-S/M PRs |
| 4 | **gateway/config env-override wall + parse inconsistencies** — TD-015/093/094; 198 env literals, `FOO=on` platform-dependent, bare `int()` aborts whole config load | **5** | 3 | 4 | 4 | 4 | Highest operator risk in the repo: a typo'd port env kills the gateway at boot for two platforms; declarative table fixes the class |
| 5 | **OAuth ×6 implementations / auth.py 7× skeleton** — TD-034/035; 4 loopback servers, 3 PKCE impls, near-copy terminal-error classifiers (`auth.py:4850` vs `:4867`) | **5** | 5 | 4 | 4 | 2 | Highest blast radius (credentials); must move slowly — flow-engine design review before any port; early PRs are extract-only |
| 6 | **Browser/CDP: 4 clients, split session registries, dialog gate bug** — TD-040/041/070/091/092; Camofox sessions invisible to reapers, Browserbase dialogs unanswerable | 4 | 3 | 4 | 3 | 3 | Two live behavioral bugs justify the lane; consolidation follows the bug fixes |
| 7 | **`run_conversation` 3,982-line function** — TD-001 (+TD-010 `init_agent`, TD-037 interruptible fork); cx 607 on the hottest path | 4 | **5** | 4 | 4 | 1 | Biggest drag in the codebase but hardest to review; gated behind lane T (tests) and a characterization harness — banner-by-banner extraction only |
| 8 | **`GatewayRunner` 14k-line class / `_run_agent` 2.6k** — TD-002/003/012; 18 concerns, disjoint-state clusters identified | 4 | 5 | 3 | 4 | 2 | Same treatment as #7; cluster extractions (Telegram-topics, watchers) are the reviewable entry points |
| 9 | **`hermes_cli/main.py`: updater 4.1k lines + import side effects + half-done parser split** — TD-004/011/037-cli; SystemExit at import, sys.argv mutation, bpo-9338 workaround | 4 | 4 | 3 | 3 | 3 | The updater is operator-critical (a bad update PR bricks installs) — extraction yes, logic changes no; parser-block moves are mechanical |
| 10 | **gateway↔TUI↔CLI mirrored behaviors** — TD-043/044/039; 7 parity config-loaders, byte-identical twin in one file, ~35 "Mirrors …" line-number comments | 3 | 4 | 4 | 3 | 4 | The parity-loader extraction is a 4h S-effort win; the full slash-command convergence waits for #8's extractions |

**Items 11–15 (near-miss, tracked in lanes):** Gemini twin adapters (TD-032, lane R2), model-selection ×4 (TD-038, gated on lane M progress), session REST API ×2 (TD-036), skills identity resolvers ×4 (TD-054/127), dead-dependency purge (TD-077, lane Q).

---

## 2–3. PR lanes

Seven lanes. Within a lane, PRs are ordered and sized for review; across lanes, Q and T are prerequisites (see §4). Risk levels: **LOW** = mechanical/deletion/docs, wrong = revert; **MED** = behavior-preserving restructure with test coverage; **HIGH** = touches auth, updater, or hot-path semantics.

### Lane Q — Quick wins (deletions, renames, two-file merges)

- **Files touched:** the ~45 sites in `QUICK_WINS.md` §"Delete/rename" and §"Two-file merges": root junk (`hermes-already-has-routines.md`, `.plans/`, `plans/`, `infographic/`, `tools/neutts_samples/`), `agent/curator_backup.py` (rename), dead imports across `gateway/`, `tools/web_tools.py`, `hermes_cli/main.py`, and the mechanical merges (TD-050/051/052/053/055/058/060/062/063).
- **Expected behavior change:** none, except three flagged BEHAVIOR-FIX candidates that are *excluded from this lane* and get their own PRs in lane G/R (dict-key bugs TD-095, registry normalization TD-090, config parsing TD-093/094 — each changes observable behavior and needs a test first).
- **Tests required:** existing suite green per PR; for each merge, a grep proving no remaining importer of the deleted copy; for the `curator_backup` rename, update its two importers (`agent/curator.py:1450`, `hermes_cli/curator.py:375`) + its tests in the same PR.
- **Rollback:** `git revert` per PR — every PR in this lane is ≤ ~200 lines and self-contained.
- **Risk:** LOW.
- **Smallest safe first PR:** delete `hermes-already-has-routines.md` + `.plans/` + `plans/` (pure deletions of stale docs, zero code). Second PR: `ruff check --select F401,F811 --fix` sweep, one commit per package.

### Lane T — Test trust & mock consolidation

- **Files touched:** `pyproject.toml` (pytest config), `tests/stress/conftest.py`, `tests/docker/conftest.py`, the fork pairs (`tests/test_cli_skin_integration.py`, `tests/test_cli_file_drop.py` vs `tests/cli/*`), `tests/gateway/conftest.py` + 15 discord / 16 telegram / 7 slack test files, `tests/gateway/conftest.py:246-368` (antipattern scan), `tests/e2e/conftest.py`.
- **Expected behavior change:** none in production code (this lane never touches non-test files); CI may newly FAIL on marker typos (`--strict-markers`) — that's the point.
- **Tests required:** the suite *is* the test; per mock-dedup PR, assert identical collected-test count before/after (`pytest --collect-only -q | wc -l`) and green run of the touched directory.
- **Rollback:** revert per PR; mock-dedup PRs are per-platform (discord PR, telegram PR, slack PR) so a bad one doesn't block the others.
- **Risk:** LOW (test-only).
- **Smallest safe first PR:** `--strict-markers` + registered markers + resolve the phantom `timeout` marks (either add `pytest-timeout` to the dev extra or delete the marks; the audit recommends adding the plugin since the 140s runner kill is coarse) — see `FIRST_THREE_PRS.md` PR-1.
- **Enforcement PR (lane exit):** extend the existing conftest antipattern scan (`tests/gateway/conftest.py:246-368`) to fail on any new file-local `_ensure_*_mock`/`_make_runner` definition.

### Lane A — Shared abstraction adoption (build nothing new; adopt what exists)

- **Files touched:** `gateway/platforms/{wecom,feishu,weixin,telegram,whatsapp,matrix}.py`, `plugins/platforms/{discord,simplex}/adapter.py` (batching trio removal); `gateway/platforms/{feishu,ntfy,photon}` (`MessageDeduplicator` adoption); `gateway/platforms/base.py:3499-3663` (debounce retirement, last); `gateway/run.py` + `tui_gateway/server.py` + new `gateway/config.py` home (7 parity loaders); `tui_gateway/server.py:3783` (twin deletion).
- **Expected behavior change:** none — `TextBatchAggregator` was written to be drop-in (its docstring documents the replaced pattern); where adapter copies have drifted (per-platform log tags, split-race guards), the PR must either carry the variant behind an aggregator hook or note the intentional normalization in the PR body with the diff of the drifted lines.
- **Tests required:** `tests/gateway/test_text_batching.py` + per-platform batching tests green per adapter PR; for the parity-loader PR, add one unit test per extracted loader pinning current gateway semantics (including the run.py warning behavior the TUI copy silently dropped — TD-043).
- **Rollback:** one adapter per PR ⇒ revert restores that adapter's local copy only. Keep `TextBatchAggregator` and the inline copies co-existing during the rollout; the final PR deletes the helper-side compatibility shims.
- **Risk:** MED (message delivery paths; mitigated by per-adapter granularity and existing per-platform test files).
- **Smallest safe first PR:** adopt `TextBatchAggregator` in **wecom** only (smallest adapter carrying the trio, byte-identical `_text_batch_key` cohort, has tests) — ~-60 net lines, single file + test.
- **Enforcement PR:** delete `base.py`'s `_text_debounce_*` third mechanism once all 8 adapters are ported; extend the adapter antipattern scan to ban local batching helpers.

### Lane R — Provider registry & adapter consolidation

- **R1 files:** new `agent/provider_registry.py` (generic), then `agent/{tts,transcription,image_gen,video_gen,web_search,browser}_registry.py` shrink to family shims; `tests/` registry tests.
- **R2 files (follow-on):** new `agent/gemini_common.py`; `agent/gemini_native_adapter.py`, `agent/gemini_cloudcode_adapter.py`, `agent/google_code_assist.py` (shared error base, TD-056); later `agent/transports/__init__.py:49-68` registration (TD-128).
- **Expected behavior change:** two deliberate BEHAVIOR-FIXes, each in its own labeled PR with a failing-then-passing test: (a) TD-090 — registration keys normalized (`strip().lower()`) uniformly, making whitespace/case-variant lookups succeed where they silently failed; (b) TD-096 — `video_gen` gains `_is_available_safe` filtering so unavailable providers are no longer selectable. Everything else behavior-preserving; `_reset_for_tests` semantics kept.
- **Tests required:** port the existing per-registry tests onto the generic core first (they define the contract); add the two bug-fix tests; plugin-registration integration tests (`tests/plugins/*`) green.
- **Rollback:** family shims keep public APIs (`register_provider`, `get_provider`, module paths) stable, so reverting the generic core restores per-family code without touching callers.
- **Risk:** LOW–MED (registries are small and heavily test-covered; Gemini adapter extraction is MED).
- **Smallest safe first PR:** the generic `ProviderRegistry[T]` + port of **tts + transcription** only (the 0.84-similarity pair) with their existing tests moved over. ~-150 lines.
- **Enforcement PR:** lint rule (simple AST check in the existing lint workflow) forbidding new module-level `_providers: dict` registries outside the generic module.

### Lane M — Monster function/class decomposition

- **Files touched (in gate order):** `hermes_cli/main.py` (parser blocks → `hermes_cli/subcommands/`, then updater → `hermes_cli/updater/`); `hermes_cli/doctor.py` (check registry); `hermes_cli/config.py:4361` (MIGRATIONS table); `gateway/run.py` (cluster extractions: telegram_topics, watchers, agent_cache, restart/shutdown → new `gateway/runner/*.py` modules); `agent/conversation_loop.py` (banner-by-banner phase extraction); `agent/agent_init.py`; `run_agent.py` (`AIAgent` slimming — LAST).
- **Expected behavior change:** none, ever, in this lane. Extractions move code verbatim behind function boundaries; any cleanup found during extraction is deferred to a follow-up PR so diffs stay `git diff --color-moved`-reviewable.
- **Tests required:** per extraction — the existing tests of the surface (main.py has per-command tests; run.py has 200+ gateway tests; conversation_loop is covered via `tests/run_agent/test_run_agent.py`'s 376 tests) PLUS, for `run_conversation` and `_run_agent` only, a characterization pre-PR (see §4 PR-3) that pins turn-level behavior before the first cut. Monkeypatch compatibility: the `_ra()` shim (TD-083) and `model_setup_flows` re-exports stay until the tests that need them are migrated — shim removal is its own final PR per file.
- **Rollback:** verbatim-move PRs revert cleanly; because each extraction is one cluster/banner, a revert never spans subsystems.
- **Risk:** MED (mechanically LOW, but the surfaces are the product's core — sequencing and characterization coverage are the mitigation).
- **Smallest safe first PR:** move the 11 inline `add_parser` blocks from `main()` into `hermes_cli/subcommands/` — the pattern already exists for 38 commands (TD-011), it's pure motion, and `tests/hermes_cli/` covers dispatch. Explicitly out of scope for that PR: the bpo-9338 workaround removal (follow-up once blocks are moved).
- **Enforcement PR:** CI size ratchet — a check that fails if any file in a tracked list (`conversation_loop.py`, `run.py`, `main.py`, `cli.py`, `web_server.py`, `auth.py`) grows beyond its baseline line count. Land this BEFORE the first extraction (see `FIRST_THREE_PRS.md`).

### Lane O — OAuth consolidation

- **Files touched (strictly in this order):** (1) new `hermes_cli/oauth_core.py` (or `agent/oauth/`) — PKCE + loopback-server + device-code primitives extracted **verbatim** from the two cleanest existing copies; (2) `hermes_cli/auth.py:2341-2356` (delete the Spotify PKCE twins — pure dedup); (3) one pilot provider port (recommend **Qwen**, :1943-2134 — smallest, lowest-stakes); (4) subsequent providers one per PR; (5) `tools/mcp_oauth.py`, `agent/google_oauth.py` adoption; (6) `web_server.py:5146-6250` re-based on the UI-agnostic core; (7) Spotify relocation out of provider auth (TD-063).
- **Expected behavior change:** none per port — token file formats, refresh timing, quarantine behavior, and error classification must be bit-compatible; any improvement is a separate labeled PR.
- **Tests required:** before the pilot port, add token-lifecycle tests for the pilot provider recording current behavior (refresh success/terminal-error/quarantine paths — the near-copy classifiers at `auth.py:4850/:4867` show exactly which cases matter). Every port PR must show the old and new flow producing identical credential-store writes on the recorded fixtures.
- **Rollback:** per-provider ports keep the old code path behind the existing `ProviderConfig` entry until the port has soaked one release; the delete-old-path PR is separate and trivially revertable.
- **Risk:** HIGH (credentials). This lane must not start until its design note (engine API, storage compatibility, rollback story) is reviewed by maintainers — see `DO_NOT_TOUCH_YET.md`.
- **Smallest safe first PR:** the `auth.py:2341-2356` Spotify-PKCE-twin deletion (4 functions → 2, same file, zero flow changes). It's technically lane Q material but belongs here as the lane's confidence-builder.

### Lane B — Browser/CDP consolidation

- **Files touched:** `tools/browser_supervisor.py` (public dispatch API), `tools/browser_cdp_tool.py` (drop private-poking `_browser_cdp_via_supervisor`, drop hand-rolled `_cdp_call`), `tools/browser_tool.py` (`_browser_eval` onto supervisor; `_get_cloud_provider` onto `browser_registry._resolve`; session-registry unification), `tools/browser_camofox.py` (backend class), `agent/browser_registry.py`, `tui_gateway/server.py:9602-9633` (delete mirrored endpoint resolution).
- **Expected behavior change:** three deliberate BEHAVIOR-FIXes, each its own PR with a repro test: (a) TD-092 dialog tool available when a per-session supervisor is live (Browserbase `must_respond` dialogs become answerable); (b) TD-091 Camofox sessions become visible to inactivity/orphan reapers (Camofox tabs now get cleaned up — document the new reaping in the PR); (c) TD-097 Camofox vision gains the native-vision fast path. Consolidation PRs otherwise behavior-preserving.
- **Tests required:** supervisor dispatch unit tests (fake CDP endpoint); reaper test proving a Camofox session is reaped after inactivity; dialog-gate test for the Browserbase-shaped config; existing `tests/tools/test_browser_*` green (note TD-104: the real-Chrome tests never run in CI — the lane inherits an obligation to add CI-runnable fakes).
- **Rollback:** per-PR revert; the Camofox backend-class PR keeps `camofox_*` functions as thin delegates during transition.
- **Risk:** MED (agent-facing tools; no credentials, no message delivery).
- **Smallest safe first PR:** BEHAVIOR-FIX (a) — the dialog gate (`browser_cdp_tool.py:525-552`): a one-conditional change + test, fixing a user-visible dead end.
- **Enforcement PR:** delete `_is_camofox_mode` and the tests-only `_PROVIDER_REGISTRY` shim (`browser_tool.py:423-467`) once backends are unified.

### Lane G — Gateway config declarative table *(added: §1 item 4 needs a home; runs parallel to A)*

- **Files touched:** `gateway/config.py` (spec table + `_apply_env_overrides` shrink), later `cli-config.yaml.example`/`.env.example` generation (P11).
- **Expected behavior change:** two BEHAVIOR-FIXes with tests: TD-093 (uniform `_coerce_bool` — `FOO=on` becomes uniformly truthy; document in changelog) and TD-094 (bad port env logs-and-skips instead of aborting the whole config load). Otherwise: byte-identical resulting `GatewayConfig` for a matrix of env fixtures.
- **Tests required:** a golden test that snapshots `load_gateway_config()` output across a fixture env covering all 13 platform triples BEFORE the table lands, then proves equality after.
- **Rollback:** platform-by-platform migration to the table (telegram first — the audit showed its block is shape-identical to discord's).
- **Risk:** MED-HIGH operator impact if wrong (config at boot), mitigated by the golden-snapshot test being PR #1 of the lane.
- **Smallest safe first PR:** the golden-snapshot test alone (test-only, zero production change) — it converts every subsequent config PR to LOW risk.

---

## 4. The first three PRs (before ANY large refactor)

Detailed in `FIRST_THREE_PRS.md`. Summary: **PR-1** pytest guardrails (`--strict-markers`, phantom-timeout resolution, stress-suite collection fix); **PR-2** merge the diverged test-file forks + test-hygiene fossils; **PR-3** the refactor safety net (CI size-ratchet for the six god files + gateway-config golden-snapshot test + mock-antipattern scan extension). All three are test/CI-only — zero production code — and they convert every subsequent lane from "trust me" to "CI proves it".

## 5. What must NOT be touched yet

Detailed in `DO_NOT_TOUCH_YET.md`. Headlines: no OAuth provider ports before the design review; no `run_conversation`/`GatewayRunner`/`AIAgent`/`HermesCLI` decomposition before PR-3's ratchet + characterization coverage; no updater logic changes at all in phase 1 (verbatim extraction only, later); freeze `yuanbao` (ownership question), the `hermes-ink` fork, the frontend unification (P4), `hermes_state.py` schema/migration internals, `kanban_db` migrations, packaging/i18n consolidation (product decisions), and the `sys.modules` big-bang.

## 6. Sequencing at a glance

```
Week 0        PR-1, PR-2, PR-3 (test/CI only)            ── gate for everything
Wave 1        Lane Q (all)   Lane T (mocks)   Lane G PR#1 (golden test)
Wave 2        Lane A (adapter-by-adapter)  Lane R1 (registries)  Lane B bug-fixes
Wave 3        Lane M (main.py parsers → updater extraction → doctor/config tables)
              Lane R2 (gemini_common)      Lane B consolidation  Lane G table
Wave 4        Lane M (run.py clusters → conversation_loop banners)
              Lane O (design review → primitives → pilot port)
Deferred      Everything in DO_NOT_TOUCH_YET.md until its stated unlock condition
```

Review-bandwidth budget: waves 1–2 are deliberately many-small-PRs (each ≤ ~300 lines, one concern); wave 3+ PRs may reach ~600 lines only when `--color-moved` shows pure motion.

**Terminal state: ROADMAP_READY**
