# Hermes Debugging Guide

Observability, logging, failure recovery, and a field guide to the common
failure modes of each subsystem.

Part of the [Hermes Engineering Handbook](README.md).

---

## 1. Where the logs are

All logs live under `~/.hermes/logs/` (profile-aware via
`get_hermes_home()`; `HERMES_HOME` overrides). Created by the single
idempotent bootstrap `setup_logging()` in `hermes_logging.py`.

| File | Level | Contents |
|---|---|---|
| `agent.log` | INFO+ | Main catch-all activity log (rotating, 5 MB × 3) |
| `errors.log` | WARNING+ | Quick-triage log (2 MB × 2) |
| `gateway.log` | INFO+ | Gateway mode only — adapters, sessions, delivery |
| `gui.log` | INFO+ | Dashboard/TUI-gateway mode — web_server, pty_bridge, tui_gateway, uvicorn |
| `gateway-shutdown-diag.log` | — | Written by the detached forensics subprocess (§4) |
| `tui_gateway_crash.log` | — | Signal/panic dumps from the TUI backend |

Browse with `hermes logs [<file>] [--follow] [--lines N] [--level ...]
[--session <id>] [--since ...] [--component gateway|agent|tools|cli|cron|gui]`.

Useful knobs: `logging.level` / `logging.max_size_mb` /
`logging.backup_count` in `config.yaml`; `--verbose`/`-v` adds a DEBUG
stderr handler. Noisy third-party loggers (openai, httpx, asyncio,
websockets, grpc, …) are pinned to WARNING.

**Log hygiene details worth knowing:**

- Every record is formatted through `RedactingFormatter`
  (`agent/redact.py`) — ~35 vendor key prefixes, env assignments, JSON
  secret fields, bearer headers, Telegram tokens, PEM blocks, JWTs, DB
  connection strings are masked. Redaction is snapshotted at import time
  from `HERMES_REDACT_SECRETS` so a mid-session `export` can't disable
  it; opting out (`security.redact_secrets: false`) logs a startup
  warning.
- `_ManagedRotatingFileHandler` survives external logrotate/`mv` by
  stat-comparing dev/ino before each emit and reopening — writes never
  silently vanish into `gateway.log.1`.
- A LogRecord factory installed at import time injects a
  `[session_id]` tag into every record process-wide.

## 2. Tracing one request end to end

1. **Find the session.** Once `set_session_context(session_id)` fires at
   conversation start, every log line carries `[<session_id>]` — grep any
   log by session, or use `hermes logs --session <id>`.
2. **Pick the right file** by concern (table above).
3. **Follow the turn structure.** One turn = `build_turn_context` →
   (`pre_llm_call` hook) → N × [API call → tool calls] → final response.
   Observer-hook IDs nest: `session_id` → `turn_id` → `api_request_id` →
   `tool_call_id`. Per-attempt telemetry (`pre_api_request` /
   `post_api_request` / `api_request_error`) carries `status_code`,
   `retry_count`, `retryable`, and a structured `error`.
4. **Inspect the stored transcript.** `hermes_state.py`'s SQLite store
   (`~/.hermes/state.db`) holds every message with tool calls, token
   counts, and finish reasons; `session_search`/FTS5 or plain `sqlite3`
   both work. Sessions rotate on context compression — follow
   `parent_session_id` lineage to walk a long conversation.
5. **Memory leaks / RSS growth:** grep `[MEMORY]` for the
   `rss=… gc=… threads=… uptime=…` time series emitted every 5 minutes
   by `gateway/memory_monitor.py` (baseline at start, snapshot at
   shutdown so last-RSS-before-exit is always logged).

For deeper telemetry, register an observer plugin against the
`hermes.observer.v1` contract (`docs/observability/README.md`) — hooks
are read-only, fail-open, and payloads are sanitized/redacted. Bundled
consumers: Langfuse and NeMo Relay (`plugins/observability/`).

## 3. Retry, backoff, and degraded modes

- **API errors** are classified by `agent/error_classifier.py` — an
  8-stage pipeline mapping provider patterns / HTTP status / error codes
  / message patterns into a `FailoverReason` (`auth`, `auth_permanent`,
  `billing`, `rate_limit`, `overloaded`, `server_error`, `timeout`,
  context-overflow, unknown). The conversation loop then retries with
  `jittered_backoff` (`agent/retry_utils.py` — decorrelated exponential,
  base 5 s, cap 120 s, counter-salted jitter so concurrent sessions don't
  thunder-herd), activates the **fallback model chain**
  (`try_activate_fallback`, 60 s primary cooldown, dedup of entries that
  match the current runtime), or triggers **context compression** for
  overflow reasons.
- **Credential pool** (`agent/credential_pool.py`): rotates multiple
  credentials per provider. States: `OK`, `EXHAUSTED` (TTL cooldown,
  HTTP-status-derived length), `DEAD` (terminal — e.g. revoked OAuth;
  only cleared by an explicit re-login). The pool sheds bad credentials
  and keeps serving — the primary "degraded but alive" mechanism.
- **Auxiliary models** (`agent/auxiliary_client.py`): its own health
  cache (10-min unhealthy TTL after 402s), provider auto-detection chain
  (openrouter → nous → custom endpoint → api-key), payment/model-fallback
  recovery ladders.
- **Fail-open subsystems** (log and continue, never block the loop):
  observer hooks, middleware, Honcho memory startup, memory-monitor
  iterations, gateway hooks.
- **Fail-closed subsystems**: cron prompt-injection scan (job emits a
  BLOCKED document), webhook routes without secrets (refused at startup),
  dashboard auth gate on non-loopback binds, skills guard `dangerous`
  verdict (cannot be `--force`d for community skills).

## 4. Gateway failure recovery

The gateway is designed to stay alive degraded rather than die:

- **Startup**: duplicate-instance PID guard (`--replace` takeover via
  marker files); if every platform fails to connect it stays up in
  `degraded` state for cron, with a reconnect watcher retrying failed
  platforms with backoff.
- **Shutdown forensics** (`gateway/shutdown_forensics.py`): on any
  shutdown signal, a <10 ms pure-stdlib snapshot logs who killed us —
  parent process summary, systemd parentage, takeover/planned-stop
  markers (smoking gun for a rival `--replace`), tracer PID, loadavg —
  then a detached subprocess appends `ps auxf`, `pstree`, `dmesg` OOM
  lines to `gateway-shutdown-diag.log` (survives cgroup teardown).
  `check_systemd_timing_alignment` warns at startup when systemd's
  `TimeoutStopSec` < drain timeout + 30 s (the phantom
  `code=killed status=9` trap).
- **Restart contract**: exit code 75 (EX_TEMPFAIL) asks the service
  manager to relaunch; SIGUSR1 triggers a graceful service restart;
  drain (`_drain_active_agents`) marks sessions `resume_pending` so the
  next inbound message auto-resumes interrupted work; a `.clean_shutdown`
  marker lets the next boot skip session suspension.
- **Stuck-loop defense**: sessions active across 3+ restarts are
  suspended rather than resumed; stale in-flight session locks self-heal
  (issue #11016).
- **Telegram specifics**: 409 Conflict (two pollers, one token) is
  prevented by a scoped bot-token lock and handled by
  `_handle_polling_conflict`; DNS/IP blocks routed around by the
  fallback-IP transport; when the send path degrades, cron delivery
  falls back to the standalone sender.
- **Event-loop hardening**: the loop exception handler swallows only
  known-transient network errors so a stray `telegram.error.TimedOut` in
  a background task can't kill the multi-platform process.

## 5. Common failure modes by subsystem

| Symptom | Likely cause | Where to look |
|---|---|---|
| Gateway "keeps dying" | systemd timeout misalignment, OOM, rival `--replace`, bare kill | `gateway-shutdown-diag.log`, `Shutdown context:` WARNING line, `[MEMORY]` series |
| First HTTPS call crashes after `hermes update` | Stale/missing CA bundle | `hermes doctor` → "SSL / CA Certificates"; `agent/ssl_guard.py` raises a typed `SSLConfigurationError` with the repair hint (`pip install --force-reinstall certifi openai httpx`); RCA: `docs/rca-ssl-cacert-post-git-pull.md`; escape hatch `HERMES_SKIP_SSL_GUARD=1` |
| Model calls loop on 429/5xx | Provider outage / rate limit | `api_request_error` telemetry, `errors.log`; check fallback chain config and credential-pool state |
| Agent stops mid-conversation with compression messages | Context overflow → session rotation | `state.db` `parent_session_id` lineage; compression locks table; `tests/run_agent/test_infinite_compaction_loop.py` documents the pathological case |
| Cron job silent | Intentional: empty script stdout or `wakeAgent:false` → `[SILENT]` suppression | `~/.hermes/cron/output/<job_id>/`; `last_error`/`last_delivery_error` in `jobs.json` |
| Recurring cron job stuck in `state=error` | `croniter` missing from the environment | Job's `last_error`; reinstall extras |
| Webhook returns 401/403/429 | Bad HMAC signature / disabled route / rate limit | Gateway log; route config in `~/.hermes/webhook_subscriptions.json` |
| Telegram messages not answered in groups | Mention gating / allowlist / topic filters | `TELEGRAM_REQUIRE_MENTION`, `TELEGRAM_GROUP_ALLOWED_*`, `allowed_topics`, observe-mode settings |
| Two profiles fight over one bot token | Scoped lock contention | `$XDG_STATE_HOME/hermes/gateway-locks`; AGENTS.md profile rule #5 |
| Session DB "malformed" errors | SQLite corruption (crash, NFS) | `repair_state_db_schema` auto-repairs with backup; WAL falls back off network filesystems (`apply_wal_with_fallback`) |
| Skills install blocked | Skills-guard verdict | `~/.hermes/skills/.hub/audit.log`; trust levels in `tools/skills_guard.py`; dangerous verdicts are not overridable |
| Dashboard 401s in dev | Session token not injected | Vite `hermesDevToken` plugin scrapes the token from the running dashboard — make sure `hermes dashboard`/`web` is up first |
| TUI dies silently | Backend crash or signal | `tui_gateway_crash.log` (all-thread stack dumps on SIGTERM/SIGHUP), `gateway.protocol_error` events |

## 6. Health and status surfaces

- `hermes status` — runtime status from `gateway_state.json`
  (gateway_state: starting/running/degraded/draining/stopped/
  startup_failed, per-platform state + error codes, active agents).
- `hermes doctor` — environment diagnostics including the SSL/CA check.
- `hermes logs list` — enumerate log files.
- Dashboard (`hermes dashboard`, port 9119) — status, sessions, logs,
  cron, analytics pages; `/api/status` etc.
- PID/lock files: `~/.hermes/gateway.pid`, `gateway.lock`,
  `gateway_state.json`; machine-wide scoped locks under
  `$XDG_STATE_HOME/hermes/gateway-locks`.
- Multi-gateway fleets: exactly one gateway owns the kanban dispatcher
  (`kanban.dispatch_in_gateway`); see `docs/kanban/multi-gateway.md`.

## 7. Debugging the deterministic engines (Chad's layer)

The governed engines are designed to be debugged by **reading their
stores, not their logs**:

- **memorygraph** (`~/.hermes/memory_graph.db`): every governed mutation
  appends to the `governance_log` table — the audit trail answers "why
  did this claim get demoted/contradicted/promoted". `graph_memory`
  actions `contradictions`, `duplicates`, `timeline`, `stats` are the
  interactive probes. Contradicted claims never promote; if a claim is
  stuck at `candidate`, check evidence count (≥2) and confidence (≥0.70).
- **opportunity_scout** (`~/.hermes/opportunity_scout_store.json`):
  every score keeps its full `ScoreBreakdown`; every stage transition and
  confidence move is an audited event with a required reason. A corrupt
  store is quarantined to `.corrupt-<ts>`, never deleted; an unknown
  schema version fails loudly rather than migrating silently.
- Neither engine makes network or model calls — if you see
  nondeterminism, the inputs changed, not the engine.

## 8. Escalation and safety notes

- SECURITY.md's one hard boundary is **OS-level isolation**; the
  in-process gates (approval prompts, redaction, skills guard, tool
  allowlists) are heuristics, not containment. When debugging a
  suspected injection/exfil issue, treat those layers as evidence
  sources, not guarantees.
- The gateway's authorization is **fail-closed**: `dm_policy: open` or
  `pairing` never substitutes for the allowlist; only explicit allow-all
  env vars opt out.
- For this fork's governance layer: incidents in ranking/escalation/
  status paths should be resolved toward determinism (contract §9) —
  never "fix" a governed engine by adding a model call.
