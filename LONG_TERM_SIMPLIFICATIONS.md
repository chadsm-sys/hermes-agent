# Long-Term Simplifications — hermes-agent

**Audit date:** 2026-07-06 · **Commit:** `93b565b`. These are the multi-week architectural programs. Each states the current shape (with evidence), the target shape, why it pays, and a staged path that ships value incrementally. IDs reference `TECH_DEBT_REGISTER.md`. Evidence only — no code was modified.

A note on feasibility: `AGENTS.md:65-69` explicitly solicits god-file extraction PRs, and several of these programs are already **half-executed in the codebase** (`hermes_cli/subcommands/` holds 38 parser builders; `model_setup_flows.py` is labeled "god-file decomposition Phase 2"; `gateway/platforms/helpers.py` was written to kill the batching duplication; `agent/transports/` was built to unify adapters). The single most repeated failure mode found by this audit is *consolidations that were built and never adopted*. Every program below therefore ends with an **adoption/enforcement step** — a lint rule, CI check, or deleted legacy path — so the fix can't coexist indefinitely with the disease.

---

## P1. Decompose the conversation core (`run_conversation` → phase pipeline)

**Now:** `agent/conversation_loop.py:436` is a 3,982-line function (cyclomatic ≈ 607) — the hottest path in the product — extracted whole from `run_agent.AIAgent` with a `_ra()` monkeypatch-compat shim (:147) and ≥14 banner-marked phases inline (interrupt handling :530, message prep/caching :638-813, refusal recovery :1387, the error-classification mega-block :2168-2800, post-call guardrails :3829, stream recovery :4019, fallback activation :4199). `AIAgent` itself (`run_agent.py:320`) is 4,924 lines/217 methods; `init_agent` (`agent/agent_init.py:154`) is another 1,559-line block. 88 test files import via the `cli` facade and many monkeypatch `run_agent`, which is why the `_ra()` shim exists.

**Target:** a turn pipeline of ~15 named, individually-testable phase functions sharing an explicit `TurnContext` (one already exists: `agent/turn_context.py`), with error-recovery strategies as a dispatch table instead of a 600-line if-tree; `init_agent` as a builder of ~10 `_init_*` steps; provider quirks and OAuth refresh out of `AIAgent` into the provider layer.

**Path:** (1) extract the leaf recovery handlers (encrypted-reasoning replay :2451, llama.cpp grammar :2494, compaction :2610, tier gate :2665) — they're already self-contained blocks; (2) extract pre-call message prep and post-call guardrails; (3) turn the remaining skeleton into a loop over phases; (4) migrate tests off `run_agent` monkeypatches phase-by-phase and delete `_ra()` (defined 6×, TD-060). **Adoption stop:** a CI size gate (e.g. `conversation_loop.py` may not grow) so extractions don't backslide.
**Payoff:** ~150–200h/yr across TD-001/006/010/083; every conversation-behavior bugfix currently means navigating 4k lines with cx 607.

## P2. Decompose the gateway runner (`GatewayRunner` → services)

**Now:** `gateway/run.py` is 16,795 lines; `GatewayRunner` spans ~14,000 of them (~150 methods, ~18 concerns, TD-002); `_run_agent` is 2,585 lines containing a 938-line nested closure (TD-003); `_handle_message`/`_handle_message_with_agent` are 1,200-line stages of one pipeline (TD-012).

**Target:** runner as a thin coordinator over extracted services with disjoint state: Telegram-topics (~15 methods :2717-:10973 — note ~430 more lines of Telegram product logic live inside `hermes_state.SessionDB:4092-4525`, TD-021, and should join this module), voice/presence, restart/shutdown, background watchers, agent-cache, run-generation guard, module-level config resolution.

**Path:** the audit verified these clusters touch disjoint state — extract them one per PR (8–15h each); then stage-split `_run_agent` (setup → threaded core → post-turn); finish with `_handle_message` stage functions. **Adoption stop:** same size gate; new gateway features must land as services, not runner methods.
**Payoff:** ~100–150h/yr; also unblocks P4 (the TUI server duplicates runner behaviors precisely because they aren't importable).

## P3. One OAuth engine

**Now:** ≥6 independent OAuth implementations (TD-034/035): `hermes_cli/auth.py` hand-rolls the identical login/refresh/status/quarantine skeleton for 7 providers (8,050 lines); `agent/google_oauth.py`, `tools/mcp_oauth.py`(+manager), `hermes_cli/web_server.py:5146-6250` (~1,100 lines re-wrapping auth.py because its helpers "print/block/poll" — its own comment :6042), `hermes_cli/dashboard_auth/`, `hermes_cli/main.py:4008`. Four loopback callback servers; three PKCE implementations.

**Target:** one UI-agnostic flow engine (device-code, PKCE-loopback, client-credentials strategies) parameterized by the **already existing** `ProviderConfig` registry (`auth.py:156, :173-407`), with thin CLI (print/poll) and web (session/redirect) frontends; MCP and Google flows consume the same engine.

**Path:** (1) extract pure flow cores from the two newest implementations (web_server sessions are closest to UI-agnostic already); (2) port providers one at a time starting with the pair whose terminal-error classifiers are literal near-copies (xAI :4850 vs Codex :4867); (3) move Spotify (~700 lines, a tool credential, TD-063) out of provider auth; (4) delete per-provider skeletons as each port lands. **Adoption stop:** new providers may only be added as ProviderConfig entries.
**Payoff:** ~70h/yr + a materially smaller auth attack surface (today a token-refresh bug must be found and fixed in up to 7 places).

## P4. One gateway client protocol layer (backend) and one chat core (frontend)

**Now:** three complete chat frontends speak the same newline-delimited JSON-RPC dialect (`web/src/lib/gatewayClient.ts:1-8` says so verbatim): desktop (110k TS lines), ui-tui (68k incl. a vendored Ink fork with a hand-ported yoga layout, TD-078), web (41k). Three JSON-RPC clients (`apps/shared`'s is consumed only by desktop); two 900–1,100-line event→UI-state reducers with 1,500/740-line test twins (TD-042); triplicated themes (3,285 lines), fuzzy matchers, format utils; five i18n systems that disagree on supported languages (TD-123). Backend-side, `tui_gateway/server.py` (10,322 lines) mirrors gateway behaviors via 7 hand-copied config loaders (TD-043) and ~35 "Mirrors …(~line N)" comments across cli.py/run.py (TD-039).

**Target:** `apps/shared` becomes real — one typed protocol client + one event-reducer state machine + shared utils consumed by all three UIs; UIs keep only rendering. Backend: shared behaviors live in importable `gateway/` modules consumed by both the messaging runner and the TUI server.

**Path:** (1) move the JSON-RPC client and the event reducer into `apps/shared` with the ui-tui reducer's 1,564-line test suite as the conformance suite; (2) point web (smallest, 253-line client) at it, then desktop, then ui-tui; (3) extract the 7 parity loaders backend-side (quick win #37); (4) fold utils (fuzzy, format, themes token layer); (5) decide the Ink-fork strategy — upstream the deltas or freeze the fork behind a compatibility test. **Adoption stop:** delete the per-app clients; CI check that no app imports a private protocol impl.
**Payoff:** the largest single number in the audit (~200h+/yr): today every protocol change is implemented 3× and reviewed 3×, and the three UIs already render the same session differently in edge cases.

## P5. One provider-integration layer (transports completion + registries + sync/async)

**Now:** `agent/transports/` (NormalizedResponse, generic registry at `__init__.py:17-46`) was built to unify provider adapters but discovers only 4 transports (:49-68); the twin Gemini adapters (23 parallel same-named functions, similarity to 1.00, TD-032) and `google_code_assist` sit outside it, re-implementing content coercion / response fabrication / stop-reason mapping (TD-128); `auxiliary_client.py` (5,950 lines) carries a 654-line provider if-chain (TD-013), a sync/async `call_llm` fork at similarity 0.74 (TD-033), and six `_is_*_error` functions duplicating `error_classifier.py` (TD-045); six provider registries are copy-paste clones with a latent lookup bug (TD-031/090).

**Target:** all adapters registered in transports; one generic `ProviderRegistry[T]`; one error-classification module; one async core with a `to_thread` sync wrapper (pattern already in-file at `auxiliary_client.py:952-965`); `resolve_provider_client` as a dispatch table over the existing `_try_*` resolvers.

**Path:** registry generic first (mechanical, S/M, fixes live bugs) → gemini_common extraction → transports registration for gemini/code_assist → error-classifier unification → call_llm de-fork → resolver dispatch table → split `auxiliary_client.py` into ~6 modules. **Adoption stop:** new providers land as transports + registry entries only; lint forbids new `_is_*_error` functions outside error_classifier.
**Payoff:** ~90–120h/yr; provider additions go from "edit 4+ files, fork sync/async" to "one transport + one registry entry".

## P6. Platform-adapter fleet consolidation

**Now:** ~20 platform adapters where the same helper families are copy-pasted per adapter: text-batching trio ×8 (~526 lines) beside its purpose-built, never-adopted replacement (`helpers.py:81`, TD-030) and a third mechanism in base.py (TD-048); mention-matching ×5 (TD-047); dedup ×3 holdouts (TD-049); `_guess_extension` ×4; per-platform env-var blocks ×13 in a 790-line `_apply_env_overrides` with inconsistent bool/int parsing (TD-015/093/094); two adapter-loading regimes (builtin if/elif vs plugin registry, TD-122); `base.py` itself 4,932 lines (TD-023); setup wizards split across two modules with ~1,500 near-identical lines (TD-061).

**Target:** adapters = thin protocol bindings over shared helpers; platform config declared in a per-platform spec (env prefix, home-channel keys, coercions) consumed by one loader; one loading regime (the plugin registry discord already proved); wizards generated from the same spec.

**Path:** adopt TextBatchAggregator (quick, the code exists) → retire base.py's debounce family → shared mention/dedup/extension helpers → declarative env spec (fixes the parse bugs by construction) → migrate builtins to the registry one at a time → wizard descriptor table. **Adoption stop:** the gateway conftest already ships an "adapter antipattern scan" (`tests/gateway/conftest.py:246-368`) — extend it to ban private copies of shared helpers.
**Payoff:** ~60–80h/yr; today the audit found the same fixed bug present in some adapter copies and absent in others.

## P7. Test-suite architecture: from isolation-by-subprocess to isolation-by-design

**Now:** CI runs every test file in its own interpreter because 178 raw `sys.modules` mutations across 82 files make shared runs unreliable (`tests.yml:88-108` says cross-file leakage "was the original flake source"; TD-100); ~1,240 duplicated mock-helper lines with drift (TD-101); real-sleep timing races with 50 ms margins (TD-103); giant test files are atomic scheduling units near the 140 s kill limit (TD-106); `tests/stress/` is unrunnable (TD-071); `tests/integration/` never runs anywhere (TD-105); phantom timeout marks (TD-099); 53 legacy event-loop tests kept alive by an autouse shim (TD-109); 96 files still test through the legacy `cli` facade (TD-107).

**Target:** a suite that passes under plain `pytest tests/` (subprocess isolation becomes an optimization, not a correctness requirement); one canonical mock per platform in conftest; event-driven synchronization instead of sleeps; files sized for scheduling; every suite either runs in CI (possibly nightly) or is deleted.

**Path:** (1) quick wins: strict-markers, timeout decision, merge forked files, fix stress collection; (2) dedupe mocks onto the existing canonicals and extend the conftest antipattern scan to enforce it; (3) split the top-4 giant files (immediate CI-latency payoff); (4) burn down `sys.modules` mutations to monkeypatch per directory; (5) convert the worst timing tests to injectable clocks (the good pattern already exists in `test_platform_reconnect.py:195-408`); (6) nightly lane for integration/stress. **Adoption stop:** CI job that runs a shared-interpreter smoke slice and a skip-count budget so silent skip inflation fails loudly.
**Payoff:** ~50h/yr triage + minutes off every CI run (~160 s guaranteed sleep floor today) + local runs finally matching CI.

## P8. Finish the CLI split (`cli.py` ⇄ `hermes_cli`) and shrink the entry point

**Now:** the REPL (`cli.py`, 13,984 lines, shipped as top-level module `cli`) and the command CLI (`hermes_cli/main.py`, 12,488 lines) form a deliberate bidirectional tangle — 30+ lazy `from cli import …` call sites in hermes_cli, module-level mixin imports in cli.py (TD-120); the chat-launch arg surface is defined twice and hand-bridged (main.py:2303-2322); main.py has import-time side effects (SystemExit :245-251, sys.argv mutation :505) and is imported as a library by leaf modules (setup.py:714, fallback_cmd.py:149); three Termux fast-path systems exist specifically to dodge main.py's import cost (TD-037-cli); the updater is ~4,100 lines of main.py (TD-004); slash commands are implemented 3–4× (TD-039).

**Target:** `hermes_cli/` as a package of side-effect-free modules (updater/, wizards, profile, dashboard-launch) with a thin `main()`; `cli.py`'s non-REPL responsibilities (worktree lifecycle, config load/save, formatters) relocated to importable homes; one shared slash-command executor with per-surface renderers; a single launch path.

**Path:** finish the started extractions first (parser blocks → subcommands/ #11; model flows → model_setup_flows #75; updater package #14); relocate cli.py's reverse-imported pieces (#72/#73); then converge slash commands (#43). The 96 test files importing `cli` migrate opportunistically as each piece moves — the facade shims (cli.py:808-905) can stay until last. **Adoption stop:** import-linter contract forbidding `hermes_cli → cli` imports; startup-time budget test replacing the Termux bypasses.
**Payoff:** ~80–120h/yr + faster startup for every user.

## P9. Skills subsystem coherence

**Now:** 12 modules across `tools/` and `agent/` with near-cyclic imports (TD-127); four skill-by-name resolvers with three identity semantics — a skill whose directory name ≠ frontmatter name is visible to view/usage but invisible to edit/delete (TD-054); `skill_view` is a 630-line god-function that mutates sandbox env state on a read (TD-024); duplicated scanners/validators/injection-lists/hashes; two files named `skills_hub.py`; two parallel skill taxonomies (`skills/` vs `optional-skills/` share 9 category names with different membership, TD-126); `setup.py` exists solely to ship both trees (TD-125).

**Target:** one `skills_core` package owning identity (a single resolver), metadata (one frontmatter parser — `skill_utils` already is this), security (guard as the only scanner), and storage layout; tool/command surfaces consume it; one taxonomy with an "optional" flag instead of a parallel tree.

**Path:** single resolver first (it fixes a user-visible inconsistency), then merge validators/scanners onto skill_utils/skills_guard, split skill_view's three endpoints, then the taxonomy/packaging decision. **Adoption stop:** import-linter contract: `agent.skill_* ↛ tools.skills_*` at module level.
**Payoff:** ~40h/yr and closes a security-relevant gap (two injection scanners with different coverage).

## P10. Browser stack unification

**Now:** four CDP client implementations (TD-040), Camofox as a 13-fork parallel backend outside the provider ABC with its own session registry invisible to the reapers (TD-041/091), a production-dead resolver beside its hand-rolled duplicate (TD-070), a live dialog-tool gating bug on cloud sessions (TD-092), a degraded Camofox vision path (TD-097), and ~350 dormant Lightpanda lines (TD-079).

**Target:** `CDPSupervisor` as the one CDP transport with a public dispatch API; all backends (agent-browser CLI, Camofox, cloud providers, CDP-connect) behind `agent/browser_provider.py`; one session registry feeding one reaper.

**Path:** public supervisor dispatch → port browser_cdp_tool/_browser_eval onto it → CamofoxBackend class implementing the ABC → registry unification (fixes the reaping gap) → adopt `_resolve` → fix the dialog gate → decide Lightpanda's fate. **Adoption stop:** delete `_is_camofox_mode` and the test-only legacy registry shim.
**Payoff:** ~40–50h/yr and three latent-bug classes closed.

## P11. Config & packaging surface reduction

**Now:** an option can require touching: `gateway/config.py` (198 env literals), `cli-config.yaml.example` (64 KB/112 keys), `.env.example` (23 KB), the wizard(s), and docs — all by hand (TD-015/151); packaging spans pyproject + setup.py (data_files only) + MANIFEST.in + nix/ + packaging/ + Dockerfile (TD-125); the root package.json doubles as Python runtime dep-holder and npm workspace root so Python-only users carry a 672 KB frontend lockfile; five i18n systems (TD-123); example/config drift is unchecked.

**Target:** a declarative option schema (per-platform spec from P6 is the seed) that *generates* env parsing, example files, and wizard prompts; packaging consolidated so setup.py disappears into pyproject data config; runtime-deps root split from the workspace root; i18n key-parity CI checks per surface.

**Path:** platform spec (P6) → generate examples from it → fold setup.py → split package.json roots → i18n parity checks → retire hand-synced README translations or mark them versioned. **Adoption stop:** CI fails when generated examples drift from source-of-truth.
**Payoff:** ~30–50h/yr and eliminates the "documented option that silently doesn't parse" bug class already observed (TD-093).

---

## Sequencing & dependency notes

- **Independent starters:** P3 (OAuth), P7 (tests), P10 (browser), P9 (skills) touch disjoint code and can begin immediately.
- **P6 before P11** (the platform spec is the seed for config generation). **P2 before/with P4's backend half** (importable gateway services are what the TUI server needs). **P1 and P5 interlock** (conversation phases call the provider layer; land P5's registry+error-classifier first, they're mechanical).
- **P8 last among the big ones** — it gets cheaper after P2/P4 remove the mirrored slash/gateway behaviors that currently anchor cli.py.
- Rough total: **≈ 900–1,200 engineering hours** across the eleven programs, against an estimated **≈ 700–900 hours/yr** of recurring cost they retire — payback inside 18 months even before counting defect risk (the audit surfaced 8+ latent bugs that are direct products of these structures: TD-090…TD-098).
