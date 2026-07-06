# Hermes Knowledge Graph — Canonical Schema

A proposal for the **smallest machine-readable representation** of the Hermes
knowledge graph that future tooling can consume — generated *alongside* the
human-readable Markdown, never replacing it.

> **Proposal + seed data only. No code, no generators.** The schema is
> documented here; a verified seed instance lives at
> [`graph/hermes.graph.json`](graph/hermes.graph.json). Both are hand-authored
> from the audited graph and are versioned data, not executable code.

---

## 1. Design principles

1. **Two files, one truth.** The Markdown is for humans; the JSON is for
   tools. They are two *renderings* of one node/edge model. Neither is
   authoritative over the other — a future generator emits both from a single
   scan.
2. **Smallest irreducible core.** Everything a tool needs is `nodes[]` +
   `edges[]`. Prose, diagrams, and tables are derivable views; they do **not**
   belong in the structured file.
3. **Symbols, not line numbers.** Identity is a stable path/symbol
   (`model_tools.py::handle_function_call`). Line numbers are an optional,
   re-derivable convenience — never identity. (Directly from
   [`GRAPH_DRIFT_REPORT.md`](GRAPH_DRIFT_REPORT.md) D2.)
4. **Controlled vocabularies.** Node `type` and edge `type` draw from the
   fixed sets in [`KNOWLEDGE_GRAPH.md`](KNOWLEDGE_GRAPH.md) §1 — no free-form
   types, so tools can switch on them.
5. **Relationships over counts.** No frozen totals (they are change-detectors,
   per the project convention). A count is `len(nodes where type==X)`,
   computed by the consumer.
6. **Provenance on every fact.** Each node/edge carries `source` (the file it
   was derived from) so drift probes can re-verify it.

---

## 2. Top-level shape

```jsonc
{
  "schema_version": "1.0",          // semver; consumers match on MAJOR
  "graph_version": "0.1.0-seed",    // this instance's version
  "generated_for": "hermes-agent",
  "repo_version": "0.16.0",
  "config_version": 29,
  "commit": "da9f2dc",              // commit the scan was taken at
  "generated_at": null,             // ISO-8601; null in the hand-authored seed
  "nodes": [ /* Node[] */ ],
  "edges": [ /* Edge[] */ ]
}
```

`schema_version` follows the repo's existing contract idiom
(`chief_of_staff.contracts.SCHEMA_VERSION`,
`docs/executive-operating-loop-contract.md` §1): **additive minor bumps,
consumers accept any matching major, never guess unknown fields.**

---

## 3. Node schema

```jsonc
{
  "id": "subsystem:agent-core",     // stable, unique, "<type>:<slug>"
  "type": "Subsystem",              // controlled vocabulary (§5)
  "name": "Agent core",
  "path": "run_agent.py",           // primary repo path (dir or file)
  "symbol": null,                   // optional "file::Symbol" anchor
  "summary": "Conversation loop, tool orchestration, dispatch.",
  "owner": "core",                  // ownership domain (§6)
  "attrs": {                        // type-specific free map (optional)
    "loc": "~5.5k",
    "config_keys": ["agent", "delegation"]
  },
  "source": "AGENTS.md; run_agent.py"   // provenance for re-verification
}
```

- `id` is the join key for edges. Format `<type-lowercased>:<kebab-slug>`.
- `symbol` replaces line-number anchors as the drift-resistant locator.
- `attrs` is intentionally open per node type (e.g. a `Provider` carries
  `api_mode`, `base_url`, `auth_type`; a `Config` carries `section`,
  `secrets_only`).

---

## 4. Edge schema

```jsonc
{
  "src": "subsystem:gateway",
  "type": "spawns",                 // controlled vocabulary (§5)
  "dst": "service:cron-ticker",
  "cardinality": "1:1",             // optional
  "condition": "kanban.dispatch_in_gateway", // optional gate/config
  "evidence": "gateway/run.py::_start_cron_ticker",  // symbol, not line
  "source": "gateway/run.py"
}
```

Edges are directional. The direction of a `fails-to` edge encodes failure
propagation (src fails → dst is affected). The direction of a `starts-before`
edge encodes startup order.

---

## 5. Controlled vocabularies

**Node types** (from `KNOWLEDGE_GRAPH.md` §1):
`Subsystem`, `Service`, `EntryPoint`, `CLI`, `Plugin`, `Scheduler`,
`ServiceUnit`, `Config`, `API`, `Provider`, `Model`, `Tool`, `Storage`,
`Dependency`.

**Edge types:**
`calls`, `spawns`, `imports`, `registers-into`, `reads-config`,
`delivers-to`, `gated-by`, `stores-in`, `supervises`, `starts-before`,
`fails-to`, `owns`.

A consumer that encounters an unknown type MUST ignore the node/edge (forward
compatibility) rather than error — mirroring the executive-loop contract's
"never guess an unknown field" rule.

---

## 6. Ownership domains

The `owner` field enables service-ownership lookup (a named Olympus
consumption use case). Proposed domains, aligned to the subsystem map:

`core` · `gateway` · `tui` · `desktop` · `dashboard` · `cli` · `cron` ·
`kanban` · `skills` · `memory` · `providers` · `mcp` · `security` ·
`packaging` · `datagen`.

Each `Subsystem`/`Service`/`Tool` node declares one owner; this is the lookup
table a reviewer-selection or escalation tool joins against.

---

## 7. What is deliberately *out* of the structured file

| Excluded | Why | Lives in |
|---|---|---|
| Prose explanations | Human-facing, not tool-consumable | Markdown |
| Mermaid diagrams | A *view* of edges, re-renderable from `edges[]` | Markdown |
| Line numbers as identity | Drift-prone (D2) | `symbol` field (re-derivable) |
| Frozen counts/totals | Change-detectors | `len()` at read time |
| Narrative failure analysis | Human judgment | Markdown; `fails-to` edges carry the skeleton |

The structured file is the **skeleton**; the Markdown is the **body**. A tool
walks the skeleton; a human reads the body.

---

## 8. Smallest viable instance (the "seed")

[`graph/hermes.graph.json`](graph/hermes.graph.json) is a **verified seed** —
not the entire graph, but a representative, audited subset (every node/edge in
it passed a `GRAPH_DRIFT_REPORT.md` probe). It demonstrates:

- all 14 node types with at least one instance,
- all 12 edge types with at least one instance,
- the join model (edges reference node `id`s),
- provenance and `symbol` anchoring.

It is explicitly `graph_version: 0.1.0-seed`. The full graph is produced by a
future generator (out of scope here — no code) that emits both this JSON and
the Markdown from one repository scan. The seed's job is to **pin the schema**
so that generator has a target to satisfy.

---

## 9. Consumption contract (how tools should read it)

```
1. Load JSON, check schema_version MAJOR == supported.
2. Index nodes by id.
3. Build adjacency from edges (both directions kept).
4. Query:
   - impact of editing X   → traverse `calls`/`imports`/`registers-into` into X (reverse)
   - startup order         → topological sort over `starts-before`
   - owner of service X    → node[X].owner
   - blast radius of X down → traverse `fails-to` forward from X
   - reviewers for path P   → nodes where path prefix matches P → owner → people map
5. Never mutate; the graph is a read model. Regeneration replaces it wholesale.
```

Detailed consumption use cases are in
[`OLYMPUS_GRAPH_INTEGRATION.md`](OLYMPUS_GRAPH_INTEGRATION.md) §3.
