# Hermes Engineering Handbook

The front door to engineering in `chadsm-sys/hermes-agent` — Chad's fork
of NousResearch's Hermes Agent framework, carrying his personal
**Chief of Staff layer**. Read this first; drill down via:

- [ARCHITECTURE_REFERENCE.md](ARCHITECTURE_REFERENCE.md) — system design + diagrams
- [MODULE_REFERENCE.md](MODULE_REFERENCE.md) — per-subsystem deep dive
- [TESTING_GUIDE.md](TESTING_GUIDE.md) — suite map, CI, conventions
- [DEBUGGING_GUIDE.md](DEBUGGING_GUIDE.md) — observability + failure field guide

---

## 1. What this system is

**Hermes Agent** (upstream, Nous Research, MIT) is a self-improving
tool-calling agent: a synchronous conversation loop (`AIAgent`) over any
OpenAI-compatible (or Anthropic/Codex/Bedrock) backend, ~90
self-registering tools grouped into toolsets, a multi-platform messaging
gateway (Telegram, Discord, Slack, WhatsApp, Signal, 18+ more), an Ink
TUI + web dashboard + editor (ACP) surfaces, skills as procedural
memory with a curator lifecycle, cron/webhook automations, delegation,
and a kanban multi-agent queue. Version 0.16.0; Python 3.11; ~17k tests.

**Chad's layer on top** turns this into the Executive Assistant half of
a two-system operating model:

| Role | System | Owns |
|---|---|---|
| Executive Brain | Mission Control (`mission-control-v0`, separate repo) | State of the world, plans, bottlenecks, reports |
| Executive Assistant | Hermes (this repo) | Execution, conversation, escalation, ranking |
| Executive | Chad | Judgment, authority, values, final word |

The constitution is `docs/chief-of-staff/MISSION.md` — it wins all
conflicts. Life OS and the Executive Decision Packet are **historical
only**. The live deployment runs on Chad's Mac mini; this repo is the
source of truth for code, not the running instance.

## 2. Repo map (load-bearing entry points)

```
run_agent.py            AIAgent facade → agent/* extracted modules
agent/                  conversation_loop, transports, error_classifier,
                        context_compressor, auxiliary_client, credential_pool,
                        memory_manager, redact, ssl_guard, …
model_tools.py          tool schema assembly + master dispatcher
tools/                  ~90 tool modules; registry.py at the bottom of the
                        import chain; environments/ = terminal backends
toolsets.py             TOOLSETS dict (per-platform tool bundles)
hermes_state.py         SessionDB — SQLite + FTS5 (state.db)
gateway/                multi-platform messaging (run.py + platforms/)
tui_gateway/ + ui-tui/  JSON-RPC backend + Ink TUI (different from gateway/)
hermes_cli/             CLI subcommands, config, web_server (dashboard :9119)
web/                    dashboard SPA → built into hermes_cli/web_dist/
plugins/                plugin system: memory/, model-providers/ (29),
                        opportunity_scout/, platforms/, observability/, …
skills/ optional-skills/  bundled + install-on-demand skills
cron/                   scheduler, jobs, suggestions, blueprints
acp_adapter/            editor integration (Zed etc.)
mcp_serve.py            Hermes as an MCP server
docs/chief-of-staff/    ★ Chad's constitution (7 docs)
docs/executive-operating-loop-contract.md  ★ M21 seams — contract only
docs/handbook/          ★ this handbook
```

`chief_of_staff/` does **not** exist on main — it lives in open PR #5
(interface-only). Do not import it.

## 3. How a message becomes an answer

Platform adapter normalizes to `MessageEvent` → gateway authorizes
(allowlists, fail-closed) → session key
(`agent:main:<platform>:<chat_type>:<chat_id>…`) resolves a session →
`AIAgent.run_conversation` runs in a thread pool → the loop alternates
LLM calls (via per-`api_mode` transports) with tool dispatches (via the
registry) until a final response, handling retries/fallbacks/
compression along the way → response is sanitized, silence-filtered,
and delivered (streaming edits or final message). Full sequence diagram
in ARCHITECTURE_REFERENCE §3.

## 4. Working in this repo

**Environment.** `setup-hermes.sh` (dev) or the curl installer. uv +
Python 3.11; `uv sync --locked --extra all --extra dev`. User state in
`~/.hermes/` (`config.yaml` settings, `.env` secrets-only, `logs/`,
`skills/`, `state.db`). Profiles give each instance its own
`HERMES_HOME` — always use `get_hermes_home()`, never hardcode paths.

**Non-negotiable upstream policies** (AGENTS.md):
- **Prompt caching must not break** — no mid-conversation system-prompt
  rebuilds, toolset changes, or memory reloads; cache-mutating slash
  commands default to deferred effect (`--now` to opt in).
- Plugins never modify core files; expand the plugin surface instead.
- In-tree memory providers are a closed set; new backends ship as
  standalone plugin repos.
- Tools self-register; tool schemas must not name tools from other
  toolsets.
- Use curses (not simple_term_menu) for menus; no `\033[K` in spinners;
  test behavior, not snapshots; never write tests that touch the real
  `~/.hermes/`.

**Code style.** PEP 8 (pragmatic), specific exceptions with
`exc_info=True` for the unexpected, cross-platform always (the only
repo-wide ruff rule is unspecified-encoding, because Windows cp1252
corrupts text silently). Conventional Commits.

**Definition of done.** `scripts/run_tests.sh` green (CI parity),
manual check with `hermes`, focused diff. CI gates: 6-slice test matrix,
ruff blocking rule, ty typecheck, hadolint, OSV/supply-chain scans,
lockfile freshness, contributor attribution (AUTHOR_MAP in
`scripts/release.py` — Chad's email was added in commit `c38ac93`),
history check.

## 5. Extension points (pick the right one)

| You want to… | Use | Where |
|---|---|---|
| Add a capability the model invokes | **Tool** (`registry.register`) | `tools/`, or a plugin's `ctx.register_tool` |
| Teach a procedure/workflow | **Skill** (SKILL.md) | `skills/` (bundled), `~/.hermes/skills/` (user/agent), hub for external |
| Ship a feature bundle | **Plugin** (`plugin.yaml` + `register(ctx)`) | `plugins/` or `~/.hermes/plugins/` |
| Add an inference backend | **Model-provider plugin** (`ProviderProfile`) | `plugins/model-providers/<name>/` |
| Add a memory backend | **Standalone plugin repo** (`MemoryProvider` ABC) | never in-tree (closed set) |
| Add a chat platform | **Platform adapter** | `gateway/platforms/` or a `kind: platform` plugin |
| React to lifecycle events | Plugin hooks / gateway hooks / middleware | `ctx.register_hook`, `~/.hermes/hooks/`, `ctx.register_middleware` |
| Schedule / event-trigger work | Cron job / webhook subscription / blueprint | `hermes cron`, `hermes webhook`, blueprint skills |
| Observe telemetry | Observer plugin (`hermes.observer.v1`) | `plugins/observability/` |
| Extend the executive loop | **Milestone-gated contract wiring only** | `docs/executive-operating-loop-contract.md` §11 |

The Skill-vs-Tool rule of thumb (CONTRIBUTING.md): if it's knowledge or
a procedure, it's a skill; if it needs new I/O or privileged access,
it's a tool.

## 6. Chad's governance layer — rules that override upstream

Upstream docs (README/AGENTS/CONTRIBUTING) govern code conventions.
Chad's layer governs **what gets built and wired**:

1. **MISSION.md wins conflicts.** North star: maximize the value of
   Chad's judgment per minute of his attention (~90-min daily window).
   Two rituals — Morning Plan and Evening Report — bound the autonomous
   day.
2. **Invariants** (contract §9, enforced by the merged engines' tests):
   - *Evidence or silence* — UNKNOWN / degraded / contradicted are data,
     never gaps to fill.
   - *Determinism over cleverness* — no model calls in ranking,
     escalation classification, or status reporting.
   - *Mutation boundaries* — each engine writes only its own store
     (memorygraph → `memory_graph.db`; scout →
     `opportunity_scout_store.json`).
   - *Attention economy* — four interrupt classes (safety, judgment,
     missing-evidence, explicit-approval); one question max.
   - *Never chase opportunities autonomously* — detect, price, rank,
     expire; never pursue without Chad.
3. **Wiring is milestone-gated.** The M21 contract records the seams;
   nothing is wired. Roadmap steps (§11) are separate Chad-approved
   milestones. Do not wire opportunistically.
4. **Governed merges.** PRs merge on Chad's explicit approval only.
   Open: #1 (council gate), #3 (review fixes), #5 (chief_of_staff,
   interface-only).
5. **Cloud sessions**: code and docs only — no deploys, no production
   changes, no secret changes; the Mac mini is out of reach by design.

## 7. Security posture (one paragraph you must internalize)

SECURITY.md defines exactly one hard boundary: **OS-level isolation**
(sandboxed terminal backends or whole-process Docker/OpenShell
wrapping). Everything in-process — approval prompts, secret redaction,
skills guard, threat-pattern scanners, tool allowlists, env denylists —
is a useful heuristic over attacker-influenced strings, **not
containment**. Network adapters require allowlists (fail-open without
one is an in-scope bug); session IDs are routing handles, not auth;
the dashboard refuses non-loopback binds without an auth provider; the
SSRF guard's cloud-metadata blocklist cannot be toggled off. When you
change anything on these surfaces, read SECURITY.md §2 first.

## 8. Operational cheat sheet

```bash
hermes                      # chat (CLI); --tui for the Ink UI
hermes gateway run          # the messaging gateway
hermes dashboard            # web UI on 127.0.0.1:9119
hermes status | doctor      # health; doctor includes the SSL/CA check
hermes logs --follow --component gateway
hermes model                # switch provider/model, no code changes
hermes cron list | create   # automations
hermes update               # git/pip update (managed installs refuse)
scripts/run_tests.sh        # CI-parity test run
```

Key state under `~/.hermes/`: `config.yaml`, `.env`, `state.db`,
`sessions/`, `logs/`, `skills/`, `cron/`, `memory_graph.db`,
`opportunity_scout_store.json`, `webhook_subscriptions.json`.

## 9. Current fork status (2026-07)

- Merged Chad-layer work: chief-of-staff docs (constitution),
  executive-loop contract (M21, docs-only), `plugins/opportunity_scout`,
  `plugins/memory/memorygraph`, plus a Mattermost thread-delivery
  hygiene fix.
- Open PRs: #1 council-gate artifact redaction (merge-gated), #3
  codebase review fixes (cron/agent/CLI/tooling hardening), #5
  chief_of_staff interface package (114 tests, excluded from wheel).
- Next allowed wiring steps: contract §11 roadmap, in order, one
  approved milestone at a time.
