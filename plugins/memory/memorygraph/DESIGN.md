# Memory Graph v2 — Design

Status: v0.1 implemented (this plugin). This document records the
architecture decisions behind the implemented core and the **design-only**
roadmap for parts whose architecture is not yet stable enough to build.

## Goals

Transform Hermes memory from searchable notes into a **governed knowledge
graph** while preserving every existing memory behavior:

- Built-in `MEMORY.md` / `USER.md` file memory: untouched. The graph mirrors
  its writes via the existing `on_memory_write` provider hook.
- The `MemoryProvider` ABC and `MemoryManager`: untouched. memorygraph is a
  standard bundled provider, subject to the one-external-provider rule, and
  inert unless `memory.provider: memorygraph` is configured.
- Other providers (honcho, hindsight, holographic, ...): untouched.

## Implemented core (architecture stable)

### Data model

```
entities ──< claims >── evidence
    │                       │
    └──< relationships >────┘  (evidence attaches to claims, relationships
    └──< entity_aliases        and entities via (subject_kind, subject_id))
governance_log (append-only audit)
```

- **Entities** are typed (person, project, goal, skill, business,
  organization, place, tool, concept) and resolved by normalized name key
  with alias support. Projects, goals, skills, businesses and people are
  first-class *entity types*, not separate tables: they share governance,
  evidence and relationship semantics, and new types can be added without
  migration.
- **Claims** are the unit of knowledge: `entity.attribute = value` plus
  confidence, tier, status, temporal validity and provenance. This is the
  classic property-graph-with-reified-statements shape: it lets governance
  operate on statements (contradict, supersede, age, promote) rather than
  on opaque note blobs.
- **Time-aware knowledge** is modeled with `valid_from`/`valid_to` windows
  on both claims and relationships, plus a `superseded_by` chain. History is
  never deleted — `timeline` reconstructs how knowledge evolved.

### Governance lifecycle

```
            re-assertion (dup)            aging sweep
   write ──► reinforce ──► promote ──► decay ──► demote
     │
     ├─ exclusive conflict, clearly newer ──► supersede (time-aware)
     └─ exclusive conflict, ambiguous     ──► contradicted (review queue)
```

- Write-time governance (dedupe, contradiction) keeps the graph clean at
  the source. Sweep-time governance (aging, promotion) is idempotent and
  runs at session end or on demand, never in the hot path.
- Confidence is a bounded scalar in [0, 1]; every mutation is clamped and
  audited. Half-life decay (default 90 days since last reinforcement)
  favors knowledge that keeps getting used.
- Promotion tiers gate trust: `candidate` (new, unproven) → `established`
  (confident + independently evidenced) → `core` (repeatedly reinforced,
  aged, uncontradicted). Consumers can filter recall by tier.

### Why a bundled provider, not a core change

The provider seam (`agent/memory_provider.py`) already carries every signal
the graph needs: turn sync, built-in write mirroring, pre-compression
extraction, session boundaries, tool exposure. Building v2 as a provider
means zero risk to existing memory behavior and a clean rollback path
(unset `memory.provider`).

## Design-only (architecture not yet stable — do not build)

These are specified here so future work is consistent, but deliberately not
implemented in v0.1:

1. **Semantic duplicate/contradiction detection.** Current detection is
   lexical (normalized keys + Jaccard/sequence similarity). Embedding-based
   similarity would catch paraphrases, but Hermes has no core embedding
   dependency and each memory provider currently makes its own choice.
   Design: an optional `Embedder` protocol injected into
   `GovernanceEngine`, falling back to lexical similarity when absent.
   Blocked on: choice of a local, dependency-light embedding path.

2. **Automatic turn extraction (NER → graph).** `sync_turn` /
   `on_pre_compress` could extract entities and claims from conversation
   automatically. Extraction quality gates trust in the whole graph, so
   v0.1 keeps writes explicit (model-invoked `remember`/`link`, plus
   mirrored built-in writes). Design: extraction lands as `candidate`
   claims with `kind='extraction'` evidence and a lower initial confidence
   (0.4), so promotion gates filter noise. Blocked on: an evaluated
   extraction prompt/pipeline.

3. **Cross-provider federation.** Mirroring graph knowledge into an active
   cloud provider (or importing from hindsight's entity graph) conflicts
   with the one-external-provider rule by design. Any federation should be
   an explicit `hermes memory export/import` CLI flow, not a runtime
   bridge.

4. **Promotion into built-in MEMORY.md.** Auto-writing `core` claims into
   `MEMORY.md` would change built-in memory behavior, which v2 must not do.
   Design: a `promote_review` surface (already queryable via `stats` /
   tier filters) that the *model* can act on with the existing memory tool,
   keeping the human/model in the loop.

5. **Multi-hop graph reasoning.** `neighbors()` exists in the store;
   compositional queries ("claims connected to X and Y within 2 hops")
   need recursive CTEs plus result ranking. Deferred until real usage
   shows which query shapes matter.

## Migration & versioning

`meta.schema_version` (currently 1) gates future migrations. Migrations
must be additive (new tables/columns) — history tables are append-only and
never rewritten.
