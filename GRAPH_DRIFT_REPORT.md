# Hermes Knowledge Graph — Drift Report

A read-only consistency audit between the knowledge graph
([`KNOWLEDGE_GRAPH.md`](KNOWLEDGE_GRAPH.md) and companions) and the current
repository state.

> **Read-only. No code changes.** This report detects where the graph has
> drifted from the tree, establishes a reproducible audit method, and
> declares a terminal state.

- **Audited against:** `hermes-agent` @ `0.16.0`, `_config_version: 29`,
  commit `da9f2dc` (the graph commit itself — no source changes since
  generation).
- **Audit type:** static, read-only probes (no execution of agent code).
- **Terminal state:** **`GRAPH_READY_FOR_OLYMPUS`** — see §5.

---

## 1. Method (reproducible probes)

Every claim below is backed by a read-only shell probe so the audit can be
re-run on any future commit. These are the *canonical drift probes* — they
should become the seed of an automated checker (see
[`OLYMPUS_GRAPH_INTEGRATION.md`](OLYMPUS_GRAPH_INTEGRATION.md) §4).

| # | Graph claim | Probe | Result |
|---|---|---|---|
| P1 | 28 provider plugins | `ls -d plugins/model-providers/*/ \| wc -l` | **28** ✅ |
| P2 | 9 memory providers | `ls -d plugins/memory/*/` | **9** ✅ |
| P3 | `_config_version: 29` | `grep '_config_version' hermes_cli/config.py` | **29** ✅ |
| P4 | 3 console scripts | `[project.scripts]` in `pyproject.toml` | hermes / hermes-agent / hermes-acp ✅ |
| P5 | version 0.16.0 | `grep '^version' pyproject.toml` | **0.16.0** ✅ |
| P6 | 10 plugin platforms | `ls -d plugins/platforms/*/` | discord, google_chat, homeassistant, irc, line, mattermost, ntfy, photon, simplex, teams ✅ |
| P7 | optional-mcps: linear, n8n | `ls -d optional-mcps/*/` | **linear, n8n** ✅ |
| P8 | dashboard port 9119 | `grep 9119 hermes_cli/subcommands/dashboard.py` | **9119** ✅ |
| P9 | proxy port 8645 | `grep 8645 hermes_cli/proxy/server.py` | **8645** ✅ |
| P10 | api_server port 8642 | `grep 8642 gateway/platforms/api_server.py` | **8642** ✅ |
| P11 | webhook port 8644 | `grep 8644 gateway/platforms/webhook.py` | **8644** ✅ |
| P12 | image_gen: fal/krea/openai/openai-codex/xai | `ls plugins/image_gen/` | ✅ (5) |
| P13 | web backends (8) | `ls plugins/web/` | brave_free, ddgs, exa, firecrawl, parallel, searxng, tavily, xai ✅ |
| P14 | browser backends (3) | `ls plugins/browser/` | browser_use, browserbase, firecrawl ✅ |
| P15 | dashboard_auth: basic/nous/self_hosted | `ls plugins/dashboard_auth/` | ✅ (3) |
| P16 | observability: langfuse, nemo_relay | `ls plugins/observability/` | ✅ (2) |
| P17 | `handle_function_call` @ model_tools.py:876 | `grep -n 'def handle_function_call'` | **876** ✅ |
| P18 | `class AIAgent` @ run_agent.py:320 | `grep -n 'class AIAgent'` | **320** ✅ |
| P19 | `discover_builtin_tools` @ registry.py:57 | `grep -n 'def discover_builtin_tools'` | **57** ✅ |
| P20 | "52 builtin subcommands" | `_BUILTIN_SUBCOMMANDS` unique tokens | **55** ⚠️ (see §3) |

---

## 2. Consistent nodes (no drift)

The following graph nodes were verified present and accurate at the paths and
values the graph records:

- **Subsystems** — all 16 subsystem roots exist (`gateway/`, `cron/`,
  `plugins/kanban/`, `skills/`, `plugins/memory/`, `providers/`,
  `tools/environments/`, `acp_adapter/`, `tui_gateway/`, `ui-tui/`,
  `apps/desktop/`, `web/`, `hermes_cli/proxy/`, …).
- **Providers** — exactly the 28 named in `KNOWLEDGE_GRAPH.md` §3.6 and the
  providers report; no additions or removals.
- **Memory providers** — the 9 named (byterover, hindsight, holographic,
  honcho, mem0, memorygraph, openviking, retaindb, supermemory).
- **Platform adapters** — all built-in adapters (incl. `qqbot/` subdir) and
  all 10 plugin platforms present.
- **Ports** — 9119 (dashboard), 8645 (proxy), 8642 (api_server), 8644
  (webhook) all match.
- **Backends** — image_gen (5), video_gen (2: fal, xai), web (8), browser (3),
  dashboard_auth (3), observability (2) all match.
- **Core symbol anchors** — the three most-cited hot-path anchors
  (`handle_function_call`, `AIAgent`, `discover_builtin_tools`) resolve to the
  exact line numbers cited.
- **Config** — `_config_version: 29`, three loaders, `.env`-secrets-only rule
  all hold.

---

## 3. Detected drift (findings)

### D1 — Subcommand count imprecision (LOW severity, numeric)

- **Where:** `KNOWLEDGE_GRAPH.md` §3.3 states *"52 builtin subcommands."*
- **Actual:** `_BUILTIN_SUBCOMMANDS` contains **55** unique tokens
  (`acp, auth, backup, bundles, checkpoints, claw, completion, computer-use,
  config, cron, curator, dashboard, debug, doctor, dump, fallback, gateway,
  hooks, import, insights, gui, desktop, kanban, login, logout, logs, lsp,
  mcp, memory, migrate, model, pairing, plugins, portal, postinstall, profile,
  proxy, prompt-size, send, sessions, setup, skills, slack, status, tools,
  uninstall, update, version, webhook, whatsapp, whatsapp-cloud, chat,
  secrets, security, help`).
- **Impact:** cosmetic. The set is listed correctly in
  [`ENTRY_POINTS.md`](ENTRY_POINTS.md) §2; only the round-number total in the
  master doc is off by three.
- **Root cause:** exactly the class of number the project's "no
  change-detector" convention warns about — a count that drifts with every
  release. The graph should describe *the relationship* ("the authoritative
  set is `_BUILTIN_SUBCOMMANDS`"), not freeze a total.
- **Disposition:** non-blocking. Correct on next regeneration; do **not**
  hand-patch (the number will drift again — the schema should carry the list,
  not a literal count; see §4).

### D2 — Line-number anchors are structurally fragile (INFORMATIONAL)

- The graph cites ~40 `file:line` anchors as evidence. All three spot-checked
  anchors are currently exact, but line numbers drift on any edit to a large
  file (`run_agent.py` ~5.5k LOC, `model_tools.py`, `gateway/run.py` ~16.8k
  LOC). This is not drift *today*, but it is a **latent drift source**: the
  first unrelated edit above line 876 silently invalidates the
  `handle_function_call@876` anchor.
- **Recommendation:** the machine-readable graph (see
  [`GRAPH_SCHEMA.md`](GRAPH_SCHEMA.md)) should anchor on **symbols**
  (`model_tools.py::handle_function_call`) not line numbers, and treat line
  numbers as a re-derivable convenience field, not the identity.

### D3 — No material structural drift

- No graph node points to a deleted path.
- No new subsystem, provider, platform, or plugin exists that the graph omits.
- No API/port/entry-point contradicts the tree.

---

## 4. Why the graph is currently accurate (and why that won't last)

The graph and the repository are in lockstep because the graph was generated
in the **same session** that committed it — commit `da9f2dc` is the graph
itself, and no source commit has landed since. This is the *best possible*
drift state, and it is also *temporary*: the moment a feature PR merges (a new
provider plugin, a renamed config key, a moved function), the graph begins to
drift with no signal.

The audit therefore concludes two things:

1. **The graph is trustworthy right now** — safe to build tooling on.
2. **The graph has no drift-detection mechanism** — the second failure mode is
   not inconsistency, it is *silent staleness*. Fixing that is the subject of
   [`OLYMPUS_GRAPH_INTEGRATION.md`](OLYMPUS_GRAPH_INTEGRATION.md) §4
   (regeneration strategy) and the drift probes in §1 above, which are
   designed to be run in CI.

---

## 5. Terminal state

```
GRAPH_READY_FOR_OLYMPUS
```

**Rationale.** Twenty probes; nineteen exact matches; one low-severity numeric
imprecision (D1) that is cosmetic and does not misrepresent any node, edge,
service, or interface. No structural inconsistency (rules out
`GRAPH_INCONSISTENT`); no material drift requiring regeneration before use
(rules out `GRAPH_NEEDS_REGEN`). The graph faithfully represents the current
architecture and is a sound foundation for the schema and Olympus integration.

**Carry-forward corrections for the next regeneration (non-blocking):**
- Replace the literal "52" in `KNOWLEDGE_GRAPH.md` §3.3 with a relationship
  statement (D1).
- Re-anchor evidence on symbols rather than line numbers (D2).

---

## 6. Audit ledger

| Dimension | Nodes checked | Consistent | Drifted | Missing |
|---|---|---|---|---|
| Subsystems | 16 | 16 | 0 | 0 |
| Providers | 28 | 28 | 0 | 0 |
| Memory providers | 9 | 9 | 0 | 0 |
| Platform adapters | 19 built-in + 10 plugin | all | 0 | 0 |
| Backends (img/vid/web/browser/auth/obs) | 23 | 23 | 0 | 0 |
| Entry points / console scripts | 3 | 3 | 0 | 0 |
| Ports / listeners | 4 | 4 | 0 | 0 |
| Config (version, loaders) | 3 | 3 | 0 | 0 |
| Core symbol anchors | 3 | 3 | 0 | 0 |
| Counts / totals | 1 | 0 | 1 (D1) | 0 |
| **Total** | **~140 checkpoints** | **~139** | **1** | **0** |

Consistency: **~99%**. Drift: **1 cosmetic numeric imprecision.**
