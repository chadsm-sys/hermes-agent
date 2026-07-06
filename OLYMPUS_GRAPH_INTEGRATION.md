# Olympus Integration — The Knowledge Graph as an Executive-OS Asset

How the Hermes knowledge graph stops being documentation and becomes a
**live, queryable substrate** the executive operating system reasons over:
consumption use cases (obj 3), how it stays current (obj 4), and the
integration contract (obj 5).

> **Architecture proposal only. Read-only. Nothing wired.** This document
> follows the house style of `docs/executive-operating-loop-contract.md`:
> every seam is a **payload shape plus a governance rule**, and *nothing in
> this document imports, executes, or schedules anything.* It records the
> contract so a future wiring milestone has a target to implement instead of a
> design to invent.

The executive-OS vocabulary is the repo's own
(`docs/chief-of-staff/MISSION.md`):

> Mission Control is the **Executive Brain**. Hermes is the **Executive
> Assistant**. Chad is the **Executive**. North Star: *maximize the value of
> the human's judgment per minute of the human's attention.*

"Olympus" is the umbrella executive operating system over both. The knowledge
graph is proposed as a shared **architectural evidence feed** within it.

---

## 1. The shift: report → asset

| Today (report) | Proposed (asset) |
|---|---|
| 5 Markdown docs, read by humans | + 1 machine-readable graph (`graph/hermes.graph.json`) |
| Generated once, drifts silently | Regenerated on a defined trigger, drift-probed in CI |
| Describes the system | Is *queried by* the system before it acts |
| No consumers | Impact analysis, ownership lookup, reviewer selection, risk scoring |
| Outside the operating loop | An `evidence_feeds` source (`source: hermes-agent`) |

The asset is the pair **`GRAPH_SCHEMA.md` (contract) + `hermes.graph.json`
(data)**. Everything below consumes that pair.

---

## 2. Where it plugs into the executive loop

The M21 contract already reserves an `evidence_feeds` slot with
`source: hermes-agent` (allowlisted). The architecture graph is a natural
second feed alongside `memorygraph` counts:

```
Mission Control (Executive Brain)          Hermes (Executive Assistant)
  evidence_feeds[source=hermes-agent]  ◀──  memorygraph counts        (existing)
  evidence_feeds[source=hermes-agent]  ◀──  architecture graph        (PROPOSED)
      · impact / blast-radius                    graph/hermes.graph.json
      · ownership / reviewer routing
      · mutation-risk score
```

Governance rule (mirrors the contract's §1): the graph feed declares
`schema_version` (semver); consumers match on **major**, treat unknown node/
edge types as ignorable, and **never guess**. The feed is **descriptive, not
directive** — it reports structure; it never tells the Executive what to do.
That stays with the Decision Engine and the human.

---

## 3. Consumption use cases (objective 3)

Each is a read-only query over `nodes[]` + `edges[]`. None require new core
surface — they are graph traversals a tool performs *before* Hermes acts.

### 3.1 Impact analysis before edits
**Query:** reverse-traverse `imports` / `calls` / `registers-into` into the
node whose `path` matches the file about to change.
**Answer:** "editing `model_tools.py::handle_function_call` reaches every
surface (CLI, gateway, tui_gateway, ACP) because they all funnel through
`AIAgent`." Surfaced to the agent as context before it patches a hot-path
file, so it knows the blast radius is *everything*.
**Governance:** advisory. High-fan-in nodes (the narrow waist) get a "this is
core surface" banner, echoing `AGENTS.md`'s footprint discipline.

### 3.2 Startup dependency reasoning
**Query:** topological sort over `starts-before` edges.
**Answer:** "the cron ticker starts *after* `runner.start()`; the dashboard s6
slot starts *after* base." Lets a diagnostic tool explain *why* a service
isn't up ("its predecessor failed") instead of just reporting it down.

### 3.3 Service ownership lookup
**Query:** `node[id].owner` (+ an owner→people map maintained outside the
graph).
**Answer:** "who owns `kanban.db`? → `owner: kanban`." Powers escalation
routing and the "who do I ask?" question the Chief-of-Staff layer already
needs.

### 3.4 Mutation-risk estimation
**Query:** score a target node by `in_degree(calls|imports|registers-into)` +
`type ∈ {Subsystem, core Tool}` + `outgoing fails-to fan-out`.
**Answer:** a 0–1 risk number. `tools/registry.py` (root of the import chain,
zero deps, everything depends on it) scores maximal; a leaf skill scores
minimal. Feeds the approval/guardrail layer and the evening "prove what
changed" report.
**Governance:** *measured, never promised* (MISSION.md). The score is
evidence, not a gate — it informs the human's judgment, doesn't replace it.

### 3.5 Automatic reviewer selection
**Query:** for a diff touching paths P, map each path → owning node → `owner`
→ reviewer set; rank by number of touched nodes per owner.
**Answer:** "this PR touches `gateway/` and `cron/` → route to gateway + cron
owners." Directly usable by the triage sweeper described in `AGENTS.md`.

### 3.6 Architecture-aware code navigation
**Query:** given a symbol, return its node, its edges, and the subsystem it
belongs to.
**Answer:** "`send_message` → toolset `messaging`, gated by gateway-running,
owned by `gateway`, fails-closed when the gateway is down." Turns navigation
from grep into structured "what is this and what depends on it."

### 3.7 (Compounding) Blast-radius for incidents
**Query:** forward-traverse `fails-to` from a failing node.
**Answer:** "provider Anthropic is 429ing → `fails-to` → agent turns degrade,
but `fallback_model` + `credential_pool` absorb it; process survives." The
graph encodes the *isolation-to-smallest-scope* design so an incident tool can
state the true blast radius instead of guessing.

---

## 4. Keeping it current (objective 4)

The drift audit's core finding: the second failure mode is not inconsistency,
it is **silent staleness**. Four strategies, compared:

| Strategy | Freshness | Cost | Drift risk | Verdict |
|---|---|---|---|---|
| **On every release** | Lags between releases | Low (once per tag) | Medium — mid-cycle merges drift | Necessary but insufficient alone |
| **On every CI run** | Always fresh | High — full scan per PR | Near-zero | Overkill; wasteful on doc-only PRs |
| **Only when architecture changes** | Fresh when it matters | Low | Low *if* the trigger is reliable | Best signal-to-noise, needs a trigger |
| **Partially incremental** | Fresh, cheap | Medium — tooling complexity | Low | Ideal end state, most build effort |

### Recommendation: a **layered** policy (not a single choice)

1. **CI drift probe on every PR (cheap gate, not a regen).** Run the ~20
   read-only probes from [`GRAPH_DRIFT_REPORT.md`](GRAPH_DRIFT_REPORT.md) §1
   against the diff. They are `ls`/`grep`-cheap. If a probe's answer changed
   (new provider dir, renamed config key, moved symbol), fail with "knowledge
   graph is stale — regenerate." This catches drift *at the commit that causes
   it*, which is the only place it's cheap to fix.
2. **Full regeneration on architecture-changing triggers.** Trigger when a PR
   touches a **structural surface**: `plugins/*/`, `gateway/platforms/`,
   `providers/`, `tools/` additions/removals, `_BUILTIN_SUBCOMMANDS`,
   `DEFAULT_CONFIG` sections, `pyproject.toml` scripts/deps, `docker/` service
   units. A path-glob CODEOWNERS-style rule decides. Doc-only and
   logic-only-within-a-file PRs skip it.
3. **Guaranteed regeneration on release.** A backstop: every version tag
   regenerates unconditionally, so the graph can never be more than one
   release stale even if triggers miss.
4. **Incremental as the maturity goal.** Once a generator exists, make it
   diff-aware (re-scan only changed subsystems, merge into the prior graph).
   This is the end state, not the starting point.

**Anchor design that makes this cheap:** because the schema anchors on
**symbols not line numbers** (`GRAPH_SCHEMA.md` §3, from drift finding D2),
the vast majority of edits (which only move line numbers) produce **zero
graph diff** — the probe passes, no regen needed. Line-number anchoring would
have made every edit look like drift; symbol anchoring is what makes the
"only when architecture changes" strategy viable.

---

## 5. The Olympus integration contract (objective 5)

Framed exactly like `docs/executive-operating-loop-contract.md`: a set of
seams, each a payload shape plus a governance rule. **None are wired.**

### 5.1 Producer / consumer roles

| Role | Who | Responsibility |
|---|---|---|
| **Producer** | Hermes (`hermes-agent`) | Emits `graph/hermes.graph.json` + Markdown from a repo scan |
| **Feed** | `evidence_feeds[source=hermes-agent]` | Transports the graph into the Executive Brain |
| **Consumer** | Mission Control + Hermes tools | Queries the read model for §3 use cases |
| **Governor** | Decision Engine + the human | Decides; the graph only *informs* |

### 5.2 Contract seams

```
Hermes scan ──emit──▶ graph/hermes.graph.json         (schema_version 1.0)
                          │
              ┌───────────┼─────────────────────────┐
              ▼           ▼                          ▼
     impact/risk    ownership/reviewer        startup/blast-radius
     (pre-edit)     (routing)                 (diagnostics)
              │           │                          │
              └───────────┴──────────► Executive evening "prove what changed"
```

Each seam's governance rule:
- **Additive-only schema evolution** — new node/edge types are minor bumps;
  removals/renames are major bumps updated in both repos simultaneously.
- **Descriptive, never directive** — the graph reports structure; it must not
  encode a recommendation or an action. Recommendations belong to the
  Decision Engine; actions belong to the human or an approved delegation.
- **Evidence-backed** — every node/edge carries `source`; a consumer can
  re-verify any fact via the drift probes. No unverifiable claims enter the
  feed (mirrors "*evidence-backed or null*" from the Bottleneck Engine).
- **Measured, never promised** — the mutation-risk score and blast-radius are
  measurements of the current graph, not guarantees about runtime behavior.
- **Allowlisted source** — the feed is `source: hermes-agent`, already the
  reserved, allowlisted evidence origin in the M21 contract.

### 5.3 What stays out (deliberately)

- **No autonomous action from the graph.** It never triggers an edit, a merge,
  or a deploy. It is a read model consulted *before* a human/agent decision.
- **No new core tool.** Graph queries are a CLI/skill-shaped capability
  (footprint ladder rung 2), not a model tool sent on every API call.
- **No coupling into runtime.** Like the executive-loop contract, the graph
  feed is import-free from the agent hot path; a stale or missing graph
  degrades gracefully to "no architectural context available," never an error.

### 5.4 First wiring milestone (proposed, not built)

When Olympus is ready to consume this:
1. Add a generator (out of scope here) that emits both renderings from one
   scan, satisfying `GRAPH_SCHEMA.md`.
2. Wire the CI drift probe (§4.1) — cheap, high-value, no runtime coupling.
3. Expose one read-only query surface (`hermes graph impact <path>` shape) as
   a CLI+skill, so the agent can consult the graph before edits.
4. Register the graph as the second `evidence_feeds[source=hermes-agent]`
   payload into Mission Control.

Steps 1–3 are Hermes-side and independent of Mission Control; step 4 is the
cross-repo seam and requires the additive schema handshake.

---

## 6. Terminal state

```
GRAPH_READY_FOR_OLYMPUS
```

The graph is **consistent** with the repository
([`GRAPH_DRIFT_REPORT.md`](GRAPH_DRIFT_REPORT.md): ~99%, one cosmetic
imprecision), has a **canonical machine-readable schema**
([`GRAPH_SCHEMA.md`](GRAPH_SCHEMA.md)) with a **validated seed**
([`graph/hermes.graph.json`](graph/hermes.graph.json): 14/14 node types, 12/12
edge types, zero dangling edges), a **defined currency policy** (§4), and a
**contract-shaped integration path** (§5) that matches the executive operating
loop's existing idiom. It is ready to be adopted as an executive-OS asset — as
a descriptive evidence feed that sharpens the Executive's judgment without ever
substituting for it.

Nothing in this proposal is wired. The next milestone has a contract to
implement, not a design to invent.
