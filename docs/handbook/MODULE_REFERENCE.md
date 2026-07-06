# Hermes Module Reference

Per-subsystem reference: purpose, dependencies, public interfaces, common
failure modes, testing strategy, and future improvements. Ordered from
the core outward. File paths are repo-relative; line numbers drift —
treat them as anchors, not gospel.

Part of the [Hermes Engineering Handbook](README.md).

---

## 1. Agent core — `run_agent.py` + `agent/`

**Purpose.** `AIAgent` is the tool-calling conversation engine. The class
in `run_agent.py` (~5,200 lines) is a facade: `__init__` forwards to
`agent/agent_init.py::init_agent`, `run_conversation` to
`agent/conversation_loop.py::run_conversation`, tool execution to
`agent/tool_executor.py`, compression to
`agent/conversation_compression.py`, and so on.

**Public interfaces.**
- `AIAgent(model=..., provider=..., api_mode=..., max_iterations=90, enabled_toolsets=..., platform=..., session_id=..., credential_pool=..., iteration_budget=..., fallback_model=..., …)` (~60 kwargs)
- `run_conversation(user_message, system_message=None, conversation_history=None, task_id=None) -> dict` (`final_response` + `messages`)
- `chat(message) -> str`; `switch_model(...)`; `interrupt()`, `steer(text)`, `close()`
- Module CLI: `python run_agent.py --query ... --save_trajectories` (fire)

**Turn control flow** (names you grep for): `build_turn_context` →
loop `while api_call_count < max_iterations and budget.remaining > 0`:
message repair (`repair_message_sequence_with_cursor`), Anthropic cache
control, `_build_api_kwargs` → transport `preflight_kwargs` →
`_interruptible_api_call` / `_interruptible_streaming_api_call` (daemon
worker thread + stale-call watchdog) → `normalize_response` → either
`_execute_tool_calls` (parallel when the batch is safe;
`model_tools.handle_function_call` per call) or final response
(think-block stripping). `api_mode == "codex_app_server"` bypasses the
whole loop via `agent/codex_runtime.py`.

**Dependencies.** `hermes_bootstrap` (must be first import — UTF-8 stdio
on Windows), `hermes_constants`, lazy `openai` (proxy import so tests can
patch `run_agent.OpenAI`), `model_tools`, `hermes_state`, everything in
`agent/`.

**Failure modes & handling.**
- API errors → `agent/error_classifier.py::classify_api_error` (8-stage
  pipeline → `FailoverReason`: auth / auth_permanent / billing /
  rate_limit / overloaded / server_error / timeout / context-overflow /
  unknown). Retries use `agent/retry_utils.py::jittered_backoff`
  (base 5 s, cap 120 s, counter-salted jitter).
- Exhausted retries → fallback chain (`try_activate_fallback`; 60 s
  primary cooldown; dedups entries equal to current runtime — #22548) or
  structured error result.
- Context overflow → `_compress_context` → session rotation under a
  state.db compression lock (prevents parent + background fork from
  double-rotating). Pathological loops are regression-tested
  (`test_infinite_compaction_loop`, `test_1630_context_overflow_loop`).
- Truncation continuations, empty-response retries, content-policy
  blocks (`test_18028_content_policy_blocked`), Ollama context-window
  aborts, interrupt-during-retry — all explicit paths.

**Testing.** `tests/run_agent/` (110 files), `tests/agent/` (173),
incident-numbered regression tests throughout.

**Future improvements.** The facade is still ~5k lines with heavy
provider-specific branches (`_is_qwen_portal`, Copilot/Azure URL
sniffing) that belong in profiles/transports; continued extraction into
`agent/` is the established direction. A live-provider canary suite
would catch upstream API drift that mocks cannot.

## 2. Provider layer — `providers/`, `plugins/model-providers/`, `agent/transports/`, `agent/auxiliary_client.py`, `agent/credential_pool.py`

**Purpose.** Model-agnostic inference: 29 bundled provider profiles, four
wire transports, an auxiliary-model router for side tasks, and a
multi-credential failover pool.

**Public interfaces.**
- `providers.base.ProviderProfile` — declarative dataclass (base_url,
  env_vars, auth_type, api_mode, `build_extra_body`,
  `build_api_kwargs_extras`, `fetch_models`, fallback_models).
  `register_provider(profile)` at plugin import;
  `get_provider_profile(name)`, `list_providers()` (lazy discovery:
  bundled → user `$HERMES_HOME/plugins/model-providers/` overrides →
  legacy `providers/<name>.py`).
- `agent/transports/` — `ProviderTransport` ABC
  (`convert_messages/convert_tools/build_kwargs/normalize_response/…`);
  registered per `api_mode`: `chat_completions`, `anthropic_messages`,
  `codex_responses`, `bedrock_converse`.
- `agent/auxiliary_client.py::resolve_provider_client(...)` — returns an
  OpenAI-shaped client for any provider (Anthropic/Codex wrapped by
  adapters); `call_llm(...)` for auxiliary tasks; per-task config
  `auxiliary.<task>.model` / `.context_length`.
- `agent/credential_pool.py` — rotating pool; states OK / EXHAUSTED
  (status-derived TTL cooldown) / DEAD (terminal until re-login).

**Dependencies.** openai SDK; boto3 (bedrock extra); provider plugins are
import-time registrations with no cross-imports.

**Failure modes.** 402s mark an auxiliary provider unhealthy for 10 min;
auto-detection chain (openrouter → nous → custom → api-key) skips
unhealthy entries; payment/model-not-found fallback ladders; DEAD
credentials never silently revive. Exact-host matching
(`base_url_host_matches`) prevents `api.openai.com.evil` spoofing.

**Testing.** `tests/providers/` (profiles, discovery, transport parity,
e2e wiring), `tests/agent/test_auxiliary_client*.py`,
`test_credential_pool*.py`, `test_error_classifier.py`.

**Future improvements.** The auxiliary client is a 264 KB module —
splitting the health-cache / adapter / task-config concerns would help.
Provider capability metadata (vision, tool-message images, max tokens)
is spread between profiles and `agent/model_metadata.py`; unifying it
would remove several special cases in the loop.

## 3. Tools — `tools/` + `model_tools.py` + `toolsets.py`

**Purpose.** ~90 self-registering tool modules behind one registry;
toolsets group them per platform/task.

**Public interfaces.**
- `tools/registry.py::registry.register(name, toolset, schema, handler,
  check_fn=, requires_env=, is_async=, dynamic_schema_overrides=,
  override=)`; `dispatch(name, args)`; `get_definitions(...)` (OpenAI
  format, `check_fn` TTL-cached 30 s).
- `model_tools.py::get_tool_definitions(enabled, disabled)` (LRU-cached
  by registry generation + config fingerprint) and
  `handle_function_call(...)` — the master dispatcher (arg coercion,
  Tool Search bridge, pre/post hooks, error sanitization).
- `toolsets.py::TOOLSETS` + `resolve_toolset` (recursive `includes`);
  `toolset_distributions.py` for data-gen sampling.
- Terminal backends: `tools/environments/{local,docker,ssh,singularity,
  modal,daytona}.py` selected by `terminal.backend` / `TERMINAL_ENV`.
- Code-exec RPC (`tools/code_execution_tool.py`): model-written Python
  calls Hermes tools via UDS (local) or file-based RPC (remote
  backends); only stdout re-enters context.
- Delegation (`tools/delegate_tool.py`, `async_delegation.py`):
  leaf/orchestrator subagents; children are deny-listed from
  `delegate_task`, `clarify`, `memory`, `send_message`.

**Dependencies.** `tools/registry.py` has none (bottom of the import
chain). Tool modules import lazily (`tools/lazy_deps.py`).

**Failure modes.** All dispatch exceptions → sanitized `{"error": ...}`;
unavailable tools filtered by `check_fn`; env leakage to children blocked
by `_HERMES_PROVIDER_ENV_BLOCKLIST`; path traversal blocked by
`tools/path_security.py`; injection scanning via
`tools/threat_patterns.py` (scopes `all`/`strict`, invisible-unicode
detection). Cross-tool schema references are banned (hallucinated-tool
pitfall, AGENTS.md).

**Testing.** `tests/tools/` (260 files) — the largest suite.

**Future improvements.** Tool result storage/output-cap logic is spread
across `tool_output_limits.py`, `tool_result_storage.py`, and per-tool
caps; a single budget model would simplify. Docker orphan reaping and
backend lifetime handling could unify under one environment supervisor.

## 4. State — `hermes_state.py`

**Purpose.** SQLite session/message store (`~/.hermes/state.db`),
schema v16: sessions (token/cost counters, parent lineage, handoff,
rewind), messages (tool calls, reasoning, platform ids), FTS5 +
trigram (CJK) search, compression locks.

**Public interfaces.** `SessionDB` — `create_session`, `append_message`,
`get_messages*`, `search_messages` (FTS5, query sanitized),
`rewind_to_message`/`restore_rewound`, token/cost updates,
`try_acquire_compression_lock`, pruning/vacuum, Telegram topic bindings,
`request_handoff`.

**Failure modes.** WAL with fallback off network filesystems
(`apply_wal_with_fallback`); malformed-DB detection + self-repair with
backup (`repair_state_db_schema`); single-writer serialization
(`_execute_write`); SQL-injection tests pin the FTS sanitizer.

**Testing.** `tests/test_hermes_state.py` (176 KB), `tests/hermes_state/`,
WAL-fallback/malformed-repair/compression-lock/SQL-injection suites.

**Future improvements.** JSON session snapshots are already deprecated
(off by default); the dual gateway store (`sessions.json` + SQLite) is
the remaining duplication worth collapsing.

## 5. Gateway — `gateway/`

**Purpose.** One asyncio process hosting 20+ chat-platform adapters with
shared session, streaming, delivery, auth, and reliability machinery.

**Public interfaces.** `load_gateway_config` → `GatewayConfig`;
`SessionStore.get_or_create_session`; `build_session_key` (the routing
spine); `DeliveryRouter.deliver`; `BasePlatformAdapter` +
`platform_registry.PlatformEntry` (plugin platforms);
`GatewayRunner` (run.py, ~14k lines, three mixins: authz, kanban
watchers, slash commands — ~50 slash handlers). Hooks:
`~/.hermes/hooks/<name>/HOOK.yaml` + `handler.py` for gateway events;
plugin hooks (`pre_gateway_dispatch`, transforms) are the separate
plugin-system surface.

**Dependencies.** Per-platform SDKs (python-telegram-bot, discord.py,
slack-bolt, mautrix, …) gated by `check_*_requirements`; the agent core
runs in a thread pool with contextvars carried across.

**Failure modes.**
- Auth is fail-closed (`dm_policy: open`/`pairing` never counts as
  authorization); unauthorized DMs → pairing (rate-limited, lockout).
- Adapter fatal errors pause the platform and enter the reconnect
  watcher; if all platforms fail, the gateway stays alive degraded for
  cron.
- Drain on shutdown marks `resume_pending`; stuck-loop sessions
  (3+ restarts) are suspended; stale session locks self-heal (#11016).
- Shutdown forensics + systemd timing check diagnose external kills
  (see DEBUGGING_GUIDE §4).
- Delivery: silence markers filtered, oversized cron output truncated
  to disk, Telegram thread-not-found recreates the topic, degraded send
  path falls back to standalone senders.
- Thread-local delivery hygiene via contextvars (not `os.environ`) so
  concurrent tasks can't cross-route replies (commit `5a0e0d3`).

**Testing.** `tests/gateway/` (318 files) including dedicated
reliability suites (drain races, FD leaks, split-brain, redelivery
dedup) and 34 Telegram files.

**Future improvements.** `run.py` (799 KB) and `slash_commands.py`
(177 KB) are the largest refactor targets; `memory_monitor`'s
`start_memory_monitoring` appears config-gated with no production
call site found — verify wiring. Streaming edit cadence is
per-platform tuned by hand; a shared pacing model would reduce drift.

## 6. TUI stack — `ui-tui/`, `tui_gateway/`, `apps/desktop/`

**Purpose.** `ui-tui/` is the Ink (React 19) terminal UI; TypeScript owns
the screen, Python owns everything else. `tui_gateway/` is the Python
JSON-RPC backend (`python -m tui_gateway.entry`, newline-delimited
JSON-RPC over stdio; `ws.py` reuses the same `dispatch` for WebSocket
clients — dashboard chat sidecar, iOS). `apps/desktop/` is a separate
Electron surface speaking the same protocol.

**Public interfaces.** Event vocabulary (`gateway.ready`,
`message.delta`, `tool.start/complete`, `approval.request`,
`clarify.request`, …); slash flow: client built-ins → `slash.exec`
(persistent `_SlashWorker` HermesCLI subprocess) → `command.dispatch`.
`transport.py` `Transport`/`TeeTransport`; `event_publisher.py`
(best-effort dashboard fan-out, bounded queue, never blocks).

**Failure modes.** Peer-gone errnos treated as clean exit vs real
errors re-raised; SIGTERM dumps all-thread stacks to
`tui_gateway_crash.log`; slash worker has a parent-death watchdog
(PID-reuse guarded); malformed stdout surfaces as
`gateway.protocol_error` events rather than corrupting the screen.

**Testing.** 71 vitest files client-side; `tests/tui_gateway/` +
`tests/test_tui_gateway_server.py` (264 KB) Python-side.

**Future improvements.** `tui_gateway/server.py` is a 392 KB single
module; the dashboard's four-socket topology (`/api/pty`, `/api/ws`,
`/api/pub`, `/api/events`) would benefit from a written protocol spec.

## 7. Web dashboard — `web/` + `hermes_cli/web_server.py`

**Purpose.** Vite/React/Tailwind SPA (built to `hermes_cli/web_dist/`)
served by a FastAPI server on port 9119: config editor, env/API-key
management, sessions, cron, MCP, plugins, logs, analytics, and embedded
chat (real `hermes --tui` over a PTY WebSocket + JSON-RPC sidecar).

**Public interfaces.** ~120 REST routes under `/api/*`; public-path
allowlist is a single shared frozenset (`dashboard_auth/public_paths.py`)
consumed by both auth middlewares. Auth: loopback/insecure mode uses an
ephemeral per-start session token injected into the SPA; non-loopback
binds require a registered `DashboardAuthProvider` (basic scrypt+HMAC,
Nous OAuth, self-hosted OAuth) and **refuse to start** without one.

**Failure modes & hardening.** Host-header middleware (DNS-rebinding,
GHSA-ppp5-vxwm-4cf7); loopback-only CORS; WS peer gating;
`/api/env/reveal` rate-limited (5/30 s) + audited, write-side env-name
denylist (`LD_PRELOAD`, `PYTHONPATH`, `PATH`, `HERMES_HOME`, …);
outbound SSRF guard (`tools/url_safety.py`) with an untoggleable
cloud-metadata blocklist and fail-closed DNS.

**Testing.** `tests/test_web_server.py`, dashboard-auth contract test,
sidecar close-on-disconnect test.

**Future improvements.** `web_server.py` is 467 KB/11.9k lines — route
modules are the obvious split. The reveal endpoint has no per-key
allowlist (defense is token + rate limit + audit); tightening to
known-key names would close a residual risk.

## 8. Plugin system — `hermes_cli/plugins.py` + `plugins/`

**Purpose.** Four-source discovery (bundled / `~/.hermes/plugins/` /
project / pip entry points), `plugin.yaml` manifests, kinds
(standalone / backend / exclusive / platform / model-provider), and the
`PluginContext` extension API (tools, hooks, middleware, CLI + slash
commands, skills, auxiliary tasks, typed provider slots, `ctx.llm`).

**Failure modes.** Failed scans aren't cached (re-entrancy guard resets
on exception); `HERMES_SAFE_MODE` skips discovery; explicit disable
beats enable; registration is fail-soft (log, never raise);
kind auto-coercion heuristics scan `__init__.py` text; the general
manager records but never imports model-provider plugins (import-ban
enforced by test).

**Testing.** `tests/plugins/`, `tests/providers/test_plugin_discovery.py`,
`tests/test_plugin_utils.py` (thread-safe singleton primitives).

**Future improvements.** Hook taxonomy has grown organically (observer
hooks vs middleware vs gateway hooks vs shell hooks); a unified
capability matrix in docs would prevent wrong-surface choices.

## 9. Memory — `agent/memory_manager.py` + `plugins/memory/`

**Purpose.** Builtin memory (MEMORY.md/USER.md + nudges + FTS5 session
search) plus exactly one external `MemoryProvider` (ABC in
`agent/memory_provider.py`; lifecycle: `initialize`, `sync_turn`,
`prefetch`, `on_session_switch`, `on_memory_write`, `shutdown`).

**Key invariants.** Single-worker sync executor (a wedged provider once
blocked ~298 s — never again); core-tool name collisions rejected;
memory context fenced in `<memory-context>` and scrubbed from streams;
cron runs `skip_memory=True`; providers must skip writes for
non-primary `agent_context`.

**memorygraph (Chad's provider, merged).** Governed knowledge graph in
`$HERMES_HOME/memory_graph.db`: entities/aliases/relationships (time-
aware, reinforcing), claims (tier candidate/established/core, status
active/superseded/retracted/contradicted), evidence, append-only
`governance_log`. `assert_claim` outcomes: reinforced / superseded /
contradicted / created. Aging (90-day half-life, floor, demotion) and
promotion (established: conf ≥ 0.70 + evidence ≥ 2; core: conf ≥ 0.85 +
reinforcements ≥ 3 + age ≥ 7 d); **contradicted claims never promote**.
One tool: `graph_memory`. Pure stdlib; injectable clock; config clamps.

**Failure modes.** Uninitialized store guards raise typed errors; tool
errors return JSON `{"error": ...}`; provider failures isolated
per-provider in `sync_all`.

**Testing.** `tests/plugins/memory/test_memorygraph_*` (governance,
store, provider), `tests/honcho_plugin/`, provider fail-open tests.

**Future improvements.** memorygraph's DESIGN.md explicitly defers
semantic dedupe, automatic turn extraction, and federation ("do not
build"); sweeps are O(active claims) — fine at personal scale, index if
that changes. The Mission Control evidence feed (counts →
`record_signal`) is reserved wiring, milestone-gated.

## 10. Opportunity Scout — `plugins/opportunity_scout/`

**Purpose.** Deterministic, local-first opportunity capture → score →
validate → lifecycle engine (Chad's layer; merged via governed PR #6).
Standalone library + CLI (`python -m plugins.opportunity_scout.cli`) —
deliberately **not** wired into agent tools.

**Public interfaces.** `OpportunityScoutEngine`
(capture/score/begin_validation/resolve_stage/advance/park/reject/
realize/top/portfolio_report); JSON store (atomic, thread-safe,
quarantines corruption, refuses unknown schema versions); CLI subcommands
add/inbox/list/show/score/validate/advance/report.

**Governance encoded.** 0–100 composite = weighted ROI(0.40) +
alignment(0.25) + leverage(0.15) + confidence(0.10) + capacity(0.10) —
weights must sum to 1.0 or `ScoringError`; full `ScoreBreakdown` stored.
Confidence moves only through audited events, clamped [0.02, 0.98].
`ALLOWED_TRANSITIONS` state machine with guards, required reasons,
terminal stages. All evidence human-entered; no network, no scraping,
no model calls, no clock dependence beyond timestamps.

**Testing.** `tests/opportunity_scout/` — determinism, invariants,
lifecycle, store corruption, CLI exit codes.

**Future improvements.** Wiring to Mission Control's reserved
`EXTENSION_POINTS["opportunity-scout"]` inbox is roadmap step 1 in the
executive-loop contract (§11) — a separate, Chad-approved milestone.

## 11. Skills — `skills/`, `optional-skills/`, `tools/skills_*.py`

**Purpose.** agentskills.io-format procedural knowledge. Reading/indexing
(`skills_tool.py`), authoring by the agent (`skill_manager_tool.py` —
create/edit/patch under `~/.hermes/skills/`), lifecycle (Curator:
usage telemetry sidecar, stale→archive, never delete, pinned exempt),
external install (skills hub: taps, quarantine, lockfile, audit log),
and static-analysis security (`skills_guard.py`: trust levels
builtin/trusted/community × verdict safe/caution/dangerous;
**dangerous is not `--force`-able** for non-builtin).

**Failure modes.** Bundled-skill seeding respects user modifications
(hash manifest); platform/env gating filters listings but explicit loads
always succeed; cron re-scans assembled skill markdown for injection.

**Testing.** `tests/skills/` (stdlib-only), `tests/hermes_cli/test_skills_*`.

**Future improvements.** Guard patterns are regex-based; the AST audit
(`skills_ast_audit.py`) covers Python but not shell scripts inside
skills.

## 12. Cron & webhooks — `cron/`, `gateway/platforms/webhook.py`

**Purpose.** Durable scheduled jobs (`~/.hermes/cron/jobs.json`, 0600,
cross-process flock) and HMAC-verified event triggers
(`~/.hermes/webhook_subscriptions.json`, hot-reloaded).

**Public interfaces.** `hermes cron <verb>` / `cronjob` tool /
`/cron`; `parse_schedule` (durations, "every monday 9am", 5-field cron
via croniter, ISO one-shots); per-job `skills`, `model`/`provider`,
`script` (sandboxed to `~/.hermes/scripts/`, stdout redacted then
injected; `no_agent` runs script-only; `wakeAgent:false` gate),
`context_from` chaining, `workdir`, multi-platform `deliver`.
`hermes webhook subscribe` with per-route secrets (GitHub/GitLab/Svix
signature formats), template interpolation, `deliver_only` zero-LLM
routes.

**Failure modes.** Missing croniter → job `state="error"` (never
silent); crash recovery via `advance_next_run` at-most-once semantics;
catchup clamps (half-period, 120 s–2 h); 3-minute hard interrupt on
cron sessions; delivery platform names allow-listed (blocks env-var
enumeration); prompt-injection scan → BLOCKED document; corrupt stores
auto-repair or start empty; delivery errors tracked separately from
job success.

**Testing.** `tests/cron/` (19 files), webhook suites in
`tests/gateway/`.

**Future improvements.** Scheduler behavior under large clock jumps is
lightly tested; job output retention has no size-based pruning.

## 13. MCP — `mcp_serve.py`, `tools/mcp_tool.py`, `optional-mcps/`

**Purpose.** Both directions: `hermes mcp serve` exposes Hermes
conversations as 10 MCP tools over stdio (Claude Code/Cursor-compatible);
`tools/mcp_tool.py` connects to external MCP servers (stdio/HTTP/SSE)
and registers their tools as `mcp-<server>` toolsets, with OAuth 2.1
(PKCE) support and a manifest-driven approved catalog
(`optional-mcps/`: linear, n8n).

**Failure modes.** Safe-env filtering for stdio children; tool
descriptions scanned for injection; non-http(s) URLs rejected typed;
`tools/list_changed` handled by deregister/re-register; server
disconnects deregister tools.

**Testing.** `tests/hermes_cli/test_mcp_*`, `tests/test_mcp_serve.py`,
`tests/acp/test_mcp_e2e.py`.

## 14. ACP — `acp_adapter/`, `acp_registry/`

**Purpose.** Runs Hermes inside editors (Zed et al.) as an Agent Client
Protocol stdio server (`hermes-acp`, `uvx hermes-agent[acp]`). Streams
text/thoughts/tool calls, maps the `todo` tool to native ACP plans,
bridges approvals to `request_permission`, and reports session
provenance (compression lineage) via `_meta`.

**Key safety piece.** `edit_approval.py`: policies ask /
session / workspace_session; sensitive paths (`.git`, `.ssh`, `.env*`,
`id_rsa`, `id_ed25519`) **always prompt** even under autonomous
policies; requester timeout (60 s) denies.

**Testing.** `tests/acp/` (14 files) + `tests/acp_adapter/`.

## 15. Configuration — `hermes_cli/config.py`, `.env.example`, `cli-config.yaml.example`

**Purpose.** Two-layer store: `~/.hermes/config.yaml` (structured
settings) + `~/.hermes/.env` (secrets ONLY, 0600). Precedence:
process env override → `.env` (also expands `${VAR}` refs inside yaml)
→ user config.yaml (deep-merged) → `DEFAULT_CONFIG`. CLI flags override
per-invocation. Managed installs (`HERMES_MANAGED` — Homebrew/Nix)
refuse config writes.

**Public interfaces.** `load_config()` (stat-cached), `cfg_get(path)`,
`save_config` (atomic, preserves `${VAR}` templates),
`save_env_value*` (gated by an env-name denylist: `LD_*`, `PYTHON*`,
`NODE_OPTIONS`, `PATH`, `GIT_SSH_COMMAND`, `HERMES_HOME`, …),
`get_missing_env_vars` (powers wizard + dashboard), `OPTIONAL_ENV_VARS`
metadata registry.

**Failure modes.** Corrupt config → backed up + defaults + warning;
non-ASCII credentials rejected; three distinct config loaders exist
(AGENTS.md) — know which path you're in.

**Testing.** `tests/hermes_cli/` (345 files, largest directory).

**Future improvements.** The precedence story is discoverable but not
centrally documented upstream (this handbook now covers it); the
three-loader split is a known source of drift.

## 16. Deployment — installer, Docker, Nix, Homebrew, Termux

- **Installer** (`scripts/install.sh` / `.ps1`): uv-based, unsets
  inherited `PYTHONPATH`/`PYTHONHOME`, multi-tier dependency fallback
  (locked sync → editable all → safe extras → base) so one broken PyPI
  package can't brick setup.
- **Docker**: 3-stage build, s6-overlay PID 1, UID 10000 + privilege-
  drop exec shim, `HERMES_HOME=/opt/data` volume; compose runs gateway +
  dashboard (loopback-bound); `.git` excluded so `hermes update` refuses
  (use `docker pull`). Egress isolation architecture documented in
  `docs/security/network-egress-isolation.md`.
- **Nix**: flake + NixOS module (`services.hermes-agent`) — config
  generated from attrsets, `HERMES_MANAGED` set; native systemd or OCI
  container mode.
- **Homebrew**: virtualenv formula, wrapped binaries inject
  `HERMES_BUNDLED_SKILLS`/`HERMES_MANAGED=homebrew`.
- **Termux**: constraints file + stdlib venv path.
- **Update flow** (`hermes update`): managed/docker refusals; scoped
  fetch; auto-stash; fork detection; pre-pull snapshot; ff-only with
  reset-on-divergence; syntax-error auto-rollback to pre-pull SHA;
  SIGHUP-protected with mirrored log.

**Failure modes.** See the SSL/CA RCA (stale CA env after partial
update → `agent/ssl_guard.py` typed error + `hermes doctor` check).

**This fork's rule:** the production deployment is Chad's Mac mini and
is **never** touched from cloud sessions.

## 17. Observability — `hermes_logging.py`, `docs/observability/`, `docs/middleware/`

Covered in depth in [DEBUGGING_GUIDE.md](DEBUGGING_GUIDE.md). Summary:
profile-aware rotating logs with session tags and always-on redaction;
`hermes.observer.v1` read-only hook contract (fail-open, sanitized
payloads; Langfuse + NeMo Relay consumers); `hermes.middleware.v1` for
behavior-changing interception (nested chain, fail-open, runs before
approvals for `tool_request`); memory monitor `[MEMORY]` series;
shutdown forensics.

## 18. Chief of Staff layer — `docs/chief-of-staff/`, `docs/executive-operating-loop-contract.md`, PR #5

**Purpose.** Chad's governance constitution and the (unwired) Hermes ↔
Mission Control contract. MISSION.md wins all conflicts; the six mapped
documents cover philosophy, decision/bottleneck/compound engines, the
executive coach, and HUMAN_FIRST authority boundaries.

**Interfaces (contract, v1.x).** `parse_morning_brief` /
`parse_evening_report` (all-or-nothing parsing; additive 1.1 fields
ignored by 1.0 consumers), `classify_work` → CONTINUE / PAUSE /
NEEDS_CHAD (one question max, only on NEEDS_CHAD), lexicographic
deterministic ranking, `LeverageStore` metrics — all in PR #5, not on
main.

**Failure modes (by design).** Malformed packets refused whole;
UNKNOWN/degraded/contradicted are first-class data, never gaps to fill;
safety escalations cannot be waved through (no CONTINUE row from
ESCALATING on the MC side).

**Testing.** 114 tests on the PR #5 branch; merged engines' invariants
tested in-tree (§9, §10).

**Future improvements = the wiring roadmap** (contract §11, each a
separate Chad-approved milestone): (1) scout → MC inbox feed;
(2) Morning/Evening source adapters + wheel inclusion; (3) memorygraph
counts as compound observations; (4) `LeverageStore` consuming
`attention_saved`.
