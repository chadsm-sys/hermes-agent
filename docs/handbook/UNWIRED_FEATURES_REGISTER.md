# Unwired Features Register

Top 10 "documented but unwired" features: places where docs, config
examples, or code comments claim behavior that no production call path
actually delivers. Follow-up to
[MEMORY_MONITOR_VERIFICATION.md](MEMORY_MONITOR_VERIFICATION.md), whose
finding is entry 6. Ranked by operator-facing false expectation.
Findings only — no code was modified. Verified against branch
`claude/hermes-cloud-context-bootstrap-e82jy5` (base `93b565b`,
2026-07-06).

Method: mechanical sweeps of all 119 `.env.example` vars and ~544
website env-reference tokens against production readers (excluding
tests/docs), plus targeted verification of every docstring-claimed
config key (`grep "in config.yaml"` across `*.py`), marketing-doc
commands, tips, and slash/CLI references. Negative results are listed
at the end so future audits don't re-litigate them.

---

## 1. `MATRIX_TOOLS_ALLOW_*` — five documented permission gates with no readers and no tools to gate

- **Claimed:** `website/docs/reference/environment-variables.md:428-431`
  documents `MATRIX_TOOLS_ALLOW_CROSS_ROOM`,
  `MATRIX_TOOLS_ALLOW_CROSS_ROOM_DESTRUCTIVE` ("requires
  …CROSS_ROOM=true"), `MATRIX_TOOLS_ALLOW_REDACTION`,
  `MATRIX_TOOLS_ALLOW_INVITES` — each "(default: false)".
  `gateway/platforms/matrix.py:34-37` additionally documents
  `MATRIX_TOOLS_ALLOW_REDACTION`, `_INVITES`, and `_ROOM_CREATE` as
  gates on "Matrix … tool execution".
- **Actual:** No code anywhere reads any `MATRIX_TOOLS_ALLOW_*` name
  (repo-wide grep: only the docstring and website rows match). Moreover
  the "Matrix tools" they would gate do not exist: the `hermes-matrix`
  toolset is plain `_HERMES_CORE_TOOLS` (`toolsets.py:503-507`) and no
  `matrix_redact`/`matrix_invite`/`matrix_room_create` tool is
  registered anywhere. Sibling vars ARE wired
  (`MATRIX_ALLOW_PUBLIC_ROOMS` read at `matrix.py:1614,3396`;
  `MATRIX_APPROVAL_REQUIRE_SENDER` at `:944`), which makes the unwired
  five look equally real.
- **Evidence:** `grep -rn "MATRIX_TOOLS_ALLOW" --include=*.py` → 3
  docstring lines only; toolset definition; no tool registrations.
- **Operator risk:** **High.** These read as security controls. An
  operator hardening a Matrix deployment will set them and believe
  redaction/invite/cross-room powers are locked down (or unlockable);
  in reality the switch is connected to nothing, and the doc implies
  capabilities that don't exist.
- **Smallest correction:** REMOVE_CLAIM

## 2. `BROWSER_SESSION_TIMEOUT` — active line in `.env.example`, zero readers

- **Claimed:** `.env.example:276-278`: "Browser session timeout in
  seconds (default: 300) / Sessions are cleaned up after this duration
  of inactivity" — and the line ships **uncommented**
  (`BROWSER_SESSION_TIMEOUT=300`), one of the few active lines in the
  file.
- **Actual:** No production reader. The 119-var sweep found zero
  matches in `*.py`/`*.sh`/`*.ts` outside tests/docs. Browser session
  lifecycle is governed elsewhere (browser supervisor/config), not by
  this var.
- **Evidence:** mechanical sweep, then targeted
  `grep -rn "BROWSER_SESSION_TIMEOUT"` — only `.env.example`.
- **Operator risk:** **High.** Operators tuning browser cleanup will
  edit a live-looking value that does nothing, then misattribute
  whatever behavior they observe.
- **Smallest correction:** REMOVE_CLAIM

## 3. `TERMINAL_TIMEOUT=60` — documented default contradicts the real default

- **Claimed:** `.env.example:195-196`: "Default command timeout in
  seconds" with an **uncommented** `TERMINAL_TIMEOUT=60`.
- **Actual:** The var IS wired, but the real default when unset is
  **180** (`hermes_cli/config.py:939 terminal.timeout: 180`;
  `tools/terminal_tool.py:1172 _parse_env_var("TERMINAL_TIMEOUT",
  "180")`). Two stragglers still fall back to "60" (`cli.py:5733`,
  `terminal_tool.py:2621` debug print), so the codebase itself is
  inconsistent. Anyone who copies `.env.example` silently cuts the
  shipped default from 180 s to 60 s.
- **Evidence:** file:line cites above.
- **Operator risk:** Medium-high. Long-running commands time out at
  a third of the documented/intended default, and the "(default)"
  claim is wrong in both directions.
- **Smallest correction:** REMOVE_CLAIM (align the example and the
  stale 60-second fallbacks with the real 180 default)

## 4. `CONTEXT_COMPRESSION_ENABLED` / `CONTEXT_COMPRESSION_THRESHOLD` — env toggles that don't exist

- **Claimed:** `.env.example:388-396` presents
  `CONTEXT_COMPRESSION_ENABLED=true` ("Enable auto-compression
  (default: true)") and `CONTEXT_COMPRESSION_THRESHOLD=0.85` as env
  controls for context compression.
- **Actual:** Zero readers repo-wide. Compression is configured only
  via `config.yaml` `compression:` (which the same block admits one
  line earlier — the env lines are dead weight that contradicts it).
- **Evidence:** mechanical sweep + targeted grep → only `.env.example`.
- **Operator risk:** Medium-high. Compression is the mechanism that
  keeps long conversations alive; an operator who "disables" or tunes
  it via these vars gets no change and a wrong mental model during
  overflow debugging.
- **Smallest correction:** REMOVE_CLAIM

## 5. `.env.example` "SESSION LOGGING" — claims automatic JSON session files that are off by default

- **Claimed:** `.env.example:306-310`: "Session trajectories are
  automatically saved to logs/ directory / Format:
  logs/session_YYYYMMDD_HHMMSS_UUID.json / Contains full conversation
  history … for debugging/replay".
- **Actual:** Per-session JSON snapshots are **opt-in and default
  False** — `sessions.write_json_snapshots: False`
  (`hermes_cli/config.py:2368`), gated in
  `agent/agent_init.py:1038-1045`, confirmed by
  `run_agent.py:2229` ("Gated by sessions.write_json_snapshots
  (default False)") and CONTRIBUTING.md (superseded by the SQLite
  store).
- **Evidence:** file:line cites above.
- **Operator risk:** Medium. A debugging/replay workflow the operator
  is told exists "automatically" produces no files until they discover
  the opt-in flag.
- **Smallest correction:** ADD_DOC_NOTE (point the section at
  `sessions.write_json_snapshots` and `state.db`)

## 6. `gateway/memory_monitor.py` — `logging.memory_monitor` config + `[MEMORY]` series (previously verified)

- **Claimed:** module docstring: config key `logging.memory_monitor`
  "see hermes_cli/config.py for the defaults block"; periodic
  `[MEMORY]` RSS series.
- **Actual:** TRUE_UNUSED — no caller, and the config key exists
  nowhere. Full evidence in
  [MEMORY_MONITOR_VERIFICATION.md](MEMORY_MONITOR_VERIFICATION.md).
- **Operator risk:** Medium (leak-hunting runbooks grep for a series
  that never appears).
- **Smallest correction:** ADD_DOC_NOTE (handbook already corrected;
  module docstring fix is a future upstream one-liner)

## 7. `.env.example` OpenRouter header — "All LLM calls go through OpenRouter — no direct provider keys needed"

- **Claimed:** `.env.example:1-5`, the first section an operator
  reads.
- **Actual:** Legacy claim. Hermes ships 29 provider profiles
  (`plugins/model-providers/`), most of which are direct — the very
  same file documents a dozen direct provider keys below, and the
  provider auto-detection chain (`agent/auxiliary_client.py`) treats
  OpenRouter as just the first candidate.
- **Evidence:** provider plugin directory listing; `.env.example`'s own
  later sections.
- **Operator risk:** Medium for newcomers: implies OpenRouter is
  mandatory or exclusive, contradicting the model-agnostic README
  pitch and confusing key setup.
- **Smallest correction:** REMOVE_CLAIM (reword header to "primary/
  simplest route")

## 8. Cron suggestion sources `usage` and `integration` — described in present tense, no producers

- **Claimed:** `cron/suggestions.py:1-18` docstring: "the single
  surface every automation proposal flows through", listing four
  sources including `usage` — "the background self-improvement review
  noticed a recurring ask…" — and `integration` — "the user connected
  an account (Gmail, GitHub, …) and the obvious automations for that
  surface are offered."
- **Actual:** Only two producers exist: blueprints
  (`tools/blueprints.py:233`) and the catalog
  (`cron/suggestion_catalog.py:124 seed_catalog_suggestions`, invoked
  from `hermes_cli/suggestions_cmd.py:128-130`). Repo-wide, no other
  `add_suggestion(` call site — nothing ever emits `source="usage"` or
  `source="integration"`; they are validated enum values with no
  writers.
- **Evidence:** `grep -rn "add_suggestion(" --include=*.py` → 2
  producer sites; `VALID_SOURCES` at `cron/suggestions.py:56`.
- **Operator risk:** Low-medium. Users led to expect Hermes will
  proactively propose automations from usage patterns or connected
  accounts; it never will until someone builds the producers.
- **Smallest correction:** ADD_DOC_NOTE (mark the two sources as
  reserved) — WIRE_LATER is the upstream option

## 9. `cli.py` `main()` help — "max_turns … (default: 60)"

- **Claimed:** `cli.py:13525` (the fire-driven `--help` docstring):
  `max_turns: Maximum tool-calling iterations (default: 60)`.
- **Actual:** The default is **90** everywhere that counts:
  `hermes_cli/config.py:818` (`agent.max_turns: 90`), `cli.py:421`,
  `cli.py:3224` ("default: 90"), `cli.py:3386-3388`.
- **Evidence:** file:line cites above.
- **Operator risk:** Low-medium. Wrong capacity planning and confusion
  when budget-exhaustion messages don't match the documented number.
- **Smallest correction:** REMOVE_CLAIM (fix the number)

## 10. Homebrew formula — placeholder checksum and stale version pin

- **Claimed:** `packaging/homebrew/hermes-agent.rb` presents a working
  brew install path (listed in AGENTS.md project structure as the
  Homebrew packaging).
- **Actual:** `url` pins release `v2026.3.30` asset
  `hermes_agent-0.6.0.tar.gz` while the repo is at 0.16.0, and
  `sha256 "<replace-with-release-asset-sha256>"` (`:8-9`) is a literal
  placeholder — `brew install` from this formula as committed cannot
  succeed. It is release-process scaffolding, not an installable
  formula; neither README nor the website advertises brew, which caps
  the blast radius.
- **Evidence:** formula lines 8-9, 19; `pyproject.toml` version 0.16.0.
- **Operator risk:** Low. Only someone who finds the formula in-tree
  and tries it is affected; failure is loud, not silent.
- **Smallest correction:** ADD_DOC_NOTE (comment in the formula that
  it is a release-time template)

---

## Verified wired (negative results — do not re-audit)

Claims checked and confirmed **real**, kept here so future audits skip
them: `gateway.strict` (run.py:1266), `onboarding.profile_build`
(run.py:8777+), `voice.auto_tts` (run.py:2592), curator auto-run
(`maybe_run_curator` called from gateway run.py:16292 and cli.py:11049),
`hermes cron create` (subcommands/cron.py:27), `hermes gateway install`
(gateway.py:6489), `hermes sessions browse` (main.py:12017,12201),
`hermes skills tap/snapshot`, `hermes doctor --fix`, `hermes config
check`, `/gquota` (cli.py:7431, CLI-only as documented),
`display.tool_progress_command`, `approvals.destructive_slash_confirm`,
`hooks_auto_accept`, `session_reset`, `platform_toolsets`,
`agent.tool_use_enforcement`, `prompt_caching.cache_ttl`,
`tool_loop_guardrails`, sessions/checkpoints `auto_prune`,
`HERMES_HUMAN_DELAY_MODE` (base.py:4121), `HERMES_BACKGROUND_NOTIFICATIONS`
(run.py:3616), `HERMES_KANBAN_DISPATCH_IN_GATEWAY`, `API_SERVER_KEY`,
`TELEGRAM_CRON_THREAD_ID`, `WEB_TOOLS_DEBUG`, `TERMINAL_LIFETIME_SECONDS`,
`STT_*_MODEL` overrides, `GITHUB_APP_*` (skills_hub.py:314),
`CAMOFOX_*`, `HYPERLIQUID_*` (skill script), `WHATSAPP_DEBUG` (read by
`scripts/whatsapp-bridge/bridge.js` — JS, easy to miss in Python-only
sweeps), `AZURE_AUTHORITY_HOST`/`AZURE_CLIENT_CERTIFICATE_PATH` (read
implicitly by the `azure.identity` SDK via
`agent/azure_identity_adapter.py`), `hermes honcho` (honestly documented
as active-provider-conditional, cli-commands.md:1161), observer hook
`api_request_error` (conversation_loop.py:1198+), middleware
`register_middleware` (plugins.py:1016), Langfuse + NeMo Relay plugins
(both present under `plugins/observability/`), SOUL.md identity
(system_prompt.py:88), kanban systemd unit file. Honest non-claims that
are NOT findings: `docs/design/profile-builder.md` (self-described
proposal), `docs/executive-operating-loop-contract.md` (self-described
contract-only), `gateway/builtin_hooks/` ("none shipped"), `.plans/`
(plans), `LLM_MODEL` (explicitly marked "no longer read").

## Caveats

- Sweeps covered `*.py`, `*.sh`, `*.ts`(+`tsx`) readers; a var read only
  by an external dependency at runtime (the Azure pattern) can look
  unwired — each finding above was individually re-checked for that
  class of false positive (partial-name grep + SDK/JS search).
- `cli-config.yaml.example` was spot-checked via docstring-claimed keys
  and a distinctive-leaf sample rather than exhaustively — a full
  key-by-key audit of its ~600 lines is future work.
