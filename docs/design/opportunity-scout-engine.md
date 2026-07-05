# Opportunity Scout Engine — Architecture

Status: v1 (2026-07-05)
Location: `plugins/opportunity_scout/`
Tests: `tests/opportunity_scout/`

## Purpose

A long-term, local-first engine that captures income/business opportunities,
scores them against explicit economics and strategic goals, detects
duplicates, walks each opportunity through an evidence-based market
validation pipeline, and tracks confidence over its full lifecycle.

Design constraints (hard requirements):

- **No external APIs.** Everything runs on the Python standard library.
- **No automatic scraping.** All ingestion is manual or file-based; all
  validation evidence is human-entered. The engine never fetches anything.
- **Durable and auditable.** Every state change, score, confidence update,
  and lifecycle transition is recorded with a timestamp and reason.
- **Deterministic.** Same inputs → same scores. No randomness, no network.

## Component Map

```
plugins/opportunity_scout/
├── __init__.py      # public API surface
├── models.py        # dataclasses + enums (Opportunity, evidence, events)
├── store.py         # JSON-backed, atomic, thread-safe persistence
├── ingestion.py     # dict / JSON-file / inbox-directory ingestion
├── dedup.py         # exact fingerprint + fuzzy duplicate detection
├── scoring.py       # ROI, time economics, strategic alignment, composite
├── confidence.py    # prior selection + bounded evidence-driven updates
├── validation.py    # staged market-validation pipeline (state machine)
├── lifecycle.py     # opportunity lifecycle state machine
├── engine.py        # OpportunityScoutEngine facade
├── cli.py           # argparse CLI (add / list / show / score / validate / …)
└── README.md        # user-facing usage docs
```

Dependency direction (no cycles):

```
cli → engine → {ingestion, dedup, scoring, confidence, validation, lifecycle} → models
                 └────────────── store ──────────────┘
```

`models.py` has no internal imports. `store.py` depends only on `models.py`.
Everything else depends on `models.py` (and optionally `store.py` via the
engine). The engine is the only module that composes the others.

## Data Model (`models.py`)

### Opportunity

The single aggregate root. Key field groups:

| Group | Fields |
|---|---|
| Identity | `opportunity_id` (uuid4 hex), `title`, `summary`, `tags` |
| Provenance | `source_type` (enum), `source_detail`, `created_at`, `updated_at` |
| Economics | `expected_revenue_usd` (annual), `upfront_cost_usd`, `ongoing_cost_usd_annual` |
| Time | `chad_hours_upfront`, `chad_hours_weekly`, `ai_hours_upfront`, `ai_hours_weekly` |
| State | `stage` (lifecycle enum), `confidence` (0–1), `score` (ScoreBreakdown \| None) |
| History | `confidence_events[]`, `transitions[]`, `validation` (ValidationState) |
| Dedup | `fingerprint` (derived, stored for exact matching) |

### Enums

- `SourceType`: `IDEA`, `PERSONAL_NETWORK`, `DIRECT_REQUEST`, `MARKET_SIGNAL`,
  `RECRUITER`, `EXISTING_CLIENT` — each maps to a confidence prior.
- `Stage` (lifecycle): see Lifecycle section.
- `EvidenceStrength`: `WEAK`, `MODERATE`, `STRONG`.
- `CheckStatus`: `PENDING`, `PASSED`, `FAILED`, `SKIPPED`.

All models serialize to/from plain dicts (`to_dict` / `from_dict`) so the
store stays a schema-versioned JSON document.

## Persistence (`store.py`)

`OpportunityStore` mirrors the proven `teams_pipeline` store pattern:

- Single JSON document: `{"version": 1, "opportunities": {id: {...}}}`.
- Atomic writes: `NamedTemporaryFile` in the target directory + `os.replace`.
- Thread-safe: one `threading.RLock` around mutations.
- Path resolution: explicit arg → `OPPORTUNITY_SCOUT_STORE_PATH` env →
  `get_hermes_home() / "opportunity_scout_store.json"`.
- Unknown schema versions fail loudly (no silent data loss); corrupt files
  are backed up to `<path>.corrupt-<ts>` before starting fresh.

## Ingestion (`ingestion.py`)

Three entry points, all offline:

1. `ingest_record(dict)` — normalize + validate a raw dict into an
   `Opportunity` (title required; numbers coerced/clamped ≥ 0; tags
   lower-cased and deduped).
2. `ingest_json_file(path)` — one JSON object or a list of objects.
3. `ingest_inbox(dir)` — every `*.json` in a directory; successfully
   ingested files are moved to `<dir>/processed/` (mirrors the existing
   `HermesOpportunityOS/inbox/processed` convention). Malformed files are
   left in place and reported, never deleted.

Ingestion never talks to the network and never invents data: missing
economics default to `0` and simply produce conservative scores.

## Duplicate Detection (`dedup.py`)

Two layers, both stdlib:

1. **Exact fingerprint** — SHA-256 of the sorted, lower-cased alphanumeric
   token set of the title. Catches re-submissions and word-order shuffles.
2. **Fuzzy match** — for non-exact candidates, a blended similarity:
   `0.6 × difflib.SequenceMatcher(title, title).ratio() +
    0.4 × Jaccard(title∪tags tokens)`.
   Default threshold `0.82` (tunable per call).

`find_duplicates(candidate, existing) -> list[DuplicateMatch]` returns
matches sorted by similarity, each labeled `exact` or `fuzzy`. The engine
surfaces duplicates at ingest; policy (`reject` | `flag` | `allow`) is the
caller's choice — default is `flag` (ingest but annotate).

## Scoring (`scoring.py`)

Pure functions; `score_opportunity(opp, config) -> ScoreBreakdown`.

`ScoringConfig` defaults (all overridable):

- `chad_hourly_rate = 205.0` (opportunity cost of Chad's time)
- `chad_weekly_capacity_hours = 5.0` (discretionary build time)
- `strategic_goals` — tag→weight map seeded from active goals
  (e.g. `income-scaling`, `direct-contracts`, `expert-witness`,
  `anesthesia`, `automation`, `recurring-revenue`).

Derived metrics (all persisted in `ScoreBreakdown`):

- `annual_chad_hours = chad_hours_upfront + 52 × chad_hours_weekly`
- `chad_time_cost = annual_chad_hours × chad_hourly_rate`
- `total_investment = upfront_cost + chad_time_cost`
- `expected_net_usd = expected_revenue × confidence − ongoing_cost −
  total_investment` (first-year, confidence-weighted)
- `expected_roi = expected_net_usd / max(total_investment, 1)`
- `leverage = annual_ai_hours / max(annual_chad_hours, 0.25)` — how much of
  the work AI does instead of Chad.

Composite (0–100), weighted blend:

| Component | Weight | Normalization |
|---|---|---|
| ROI | 0.40 | `tanh(roi / 3)` mapped to 0–1 (saturates ~ROI 3×; negatives punished) |
| Strategic alignment | 0.25 | matched goal weights / total goal weights |
| Leverage | 0.15 | `min(leverage, 10) / 10` |
| Confidence | 0.10 | as-is |
| Capacity fit | 0.10 | 1 if weekly hours ≤ capacity, linear penalty to 0 at 3× capacity |

Weights are config, sum-validated, and the breakdown stores every component
so a score is always explainable.

## Confidence Tracking (`confidence.py`)

- **Prior** by `SourceType` (idea 0.30 → existing client 0.65).
- **Updates** only through `apply_confidence_event(opp, delta, reason)`;
  every update appends a `ConfidenceEvent(timestamp, delta, reason,
  resulting)` — full audit trail.
- Validation outcomes drive standard deltas: passed stage `+stage_weight ×
  strength_factor` (weak 0.5 / moderate 0.75 / strong 1.0); failed stage
  `−stage_weight`.
- Confidence is always clamped to `[0.02, 0.98]` — never certain, never dead.

## Market Validation Pipeline (`validation.py`)

An ordered, evidence-based checklist state machine. Default stages:

| # | Stage | Weight | Question it answers |
|---|---|---|---|
| 1 | `problem_evidence` | 0.06 | Is the pain real and named by real people? |
| 2 | `demand_evidence` | 0.08 | Are people already paying/asking for this? |
| 3 | `willingness_to_pay` | 0.10 | Will *these* buyers pay *this* price? |
| 4 | `competition_scan` | 0.05 | Who else does this; why do we still win? |
| 5 | `regulatory_check` | 0.06 | Licensure/compliance/malpractice exposure? |
| 6 | `capacity_fit` | 0.05 | Does it fit the 90-min window + 48 hr weeks? |

Rules:

- Evidence is **human-entered only** (`add_evidence(stage, summary, source,
  strength)`); the pipeline never gathers anything itself.
- A stage `PASSED` requires ≥1 evidence record; `FAILED` requires a reason;
  `SKIPPED` requires a justification (recorded).
- Stages resolve in order (no passing stage 3 while stage 1 is pending),
  keeping validation honest.
- Each resolution emits the corresponding confidence event.
- Pipeline is complete when every stage is `PASSED` or `SKIPPED`; any
  `FAILED` stage marks the pipeline failed (engine then recommends
  `REJECTED` or `PARKED`).

## Lifecycle (`lifecycle.py`)

```
CAPTURED → TRIAGED → SCORED → VALIDATING → VALIDATED → ACTIVE → REALIZED
   │           │         │         │            │          │
   └───────────┴─────────┴────┬────┴────────────┴──────────┤
                              ▼                            ▼
                       REJECTED / EXPIRED               PARKED ⇄ (TRIAGED)
```

- Transition map is explicit data (`ALLOWED_TRANSITIONS`); anything else
  raises `LifecycleError`.
- `PARKED → TRIAGED` is the only revival path (mirrors the house rule that
  parked systems need explicit reactivation).
- `REALIZED`, `REJECTED`, `EXPIRED` are terminal.
- Every transition appends `TransitionEvent(from, to, timestamp, reason)`.
- Guards: `SCORED` requires a score on record; `VALIDATED` requires a
  completed, non-failed validation pipeline.

## Engine Facade (`engine.py`)

`OpportunityScoutEngine(store, scoring_config)` — the only class callers
need:

- `capture(record, on_duplicate="flag")` → ingest + dedup + persist
  (auto-advances CAPTURED→TRIAGED when core fields are present).
- `score(opportunity_id)` → score + persist + advance to SCORED.
- `begin_validation(id)` / `add_evidence(...)` / `resolve_stage(...)` →
  validation workflow + confidence updates + auto-advance to VALIDATED.
- `advance(id, stage, reason)` / `park(id)` / `reject(id)` / `realize(id)`.
- `top(n)` → highest-composite, non-terminal opportunities.
- `portfolio_report()` → counts by stage, aggregate expected net,
  Chad-hours committed vs capacity, top-5 table.

## CLI (`cli.py`)

`python -m plugins.opportunity_scout.cli <cmd>`:

`add`, `inbox`, `list`, `show`, `score`, `validate` (begin/evidence/resolve),
`advance`, `report`. Output is plain text; `--json` for machine use. The CLI
performs no writes outside the store file and moves inbox files only within
the inbox directory.

## Testing Strategy

Unit tests per module plus an end-to-end engine test, all under
`tests/opportunity_scout/`, all offline and tmp_path-isolated:

- models: serialization round-trips, validation errors
- store: atomic persistence, reload, corrupt-file recovery, thread safety
- ingestion: normalization, file + inbox flows, malformed input handling
- dedup: exact, shuffled-word, fuzzy, and negative cases
- scoring: economics math, alignment, capacity penalty, determinism
- confidence: priors, clamping, audit trail
- validation: ordering, evidence requirements, pass/fail/skip, confidence hooks
- lifecycle: allowed/blocked transitions, guards, terminal states
- engine/cli: capture→score→validate→activate happy path + duplicate policy

## Future (explicitly out of scope for v1)

- Gateway/agent tool bindings (expose engine methods as Hermes tools)
- Scheduled review nudges via the existing cron plugin
- Import bridge from `~/HermesOpportunityOS` inbox format (v1 already reads
  plain JSON, which that scaffold uses)
