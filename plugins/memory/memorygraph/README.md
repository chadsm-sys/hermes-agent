# memorygraph — Governed Knowledge Graph Memory

Transforms Hermes memory from searchable notes into a **governed knowledge
graph**: typed entities, time-aware relationships, evidence-linked claims,
confidence tracking, contradiction/duplicate detection, knowledge aging and
promotion.

Local-only (stdlib `sqlite3`), no network, no credentials. Database at
`$HERMES_HOME/memory_graph.db` (profile-scoped).

## Activate

```yaml
# config.yaml
memory:
  provider: memorygraph
```

The built-in `memory` tool (MEMORY.md / USER.md) is unchanged. Writes to it
are mirrored into the graph via the `on_memory_write` hook, so both stay
consistent.

## Model

| Concept | Table | Notes |
|---|---|---|
| Entities | `entities` | Typed: person, project, goal, skill, business, organization, place, tool, concept. Alias resolution via `entity_aliases`. |
| Relationships | `relationships` | Typed edges with `valid_from`/`valid_to` windows and confidence. |
| Claims | `claims` | `entity.attribute = value` with confidence, tier (candidate → established → core), status (active / superseded / retracted / contradicted), temporal validity. |
| Evidence | `evidence` | Provenance links (session, built-in memory write, tool, URL, quote). |
| Audit | `governance_log` | Append-only log of every governed mutation. |

## Governance

- **Duplicate detection** — re-asserting known knowledge reinforces the
  existing claim (confidence up, reinforcement count up) instead of
  duplicating. Normalized-key match plus fuzzy similarity (default ≥ 0.88).
- **Contradiction detection** — conflicting values for an *exclusive*
  attribute are superseded time-aware when the new value is clearly newer
  (old claim's validity window closes, linked via `superseded_by`);
  otherwise both are flagged `contradicted` for review (`contradictions` /
  `resolve` actions).
- **Confidence tracking** — reinforcement +0.10, feedback ±0.15,
  contradiction −0.15, clamped to [0, 1].
- **Knowledge aging** — confidence decays with a 90-day half-life since last
  reinforcement (configurable); decayed established/core claims are demoted.
- **Knowledge promotion** — candidate → established at confidence ≥ 0.70
  with ≥ 2 evidence links; established → core at confidence ≥ 0.85 with
  ≥ 3 reinforcements and ≥ 7 days of age. Contradicted claims never promote.

Sweeps run at session end (configurable) or on demand via the `sweep`
action.

## Tool

One tool, `graph_memory`, with actions:
`remember`, `link`, `unlink`, `about`, `query`, `timeline`,
`contradictions`, `resolve`, `duplicates`, `feedback`, `forget`, `sweep`,
`stats`.

## Config (optional)

`$HERMES_HOME/memorygraph.json`:

```json
{
  "db_path": "/custom/path/memory_graph.db",
  "half_life_days": 90,
  "duplicate_similarity": 0.88,
  "prefetch_enabled": true,
  "sweep_on_session_end": true
}
```

See `DESIGN.md` for the governance model rationale and the design-only
roadmap.
