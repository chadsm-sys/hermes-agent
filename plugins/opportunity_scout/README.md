# Opportunity Scout

Local-first engine for capturing, scoring, deduplicating, and validating
income/business opportunities over their full lifecycle.

**Hard guarantees:** no external APIs, no scraping, stdlib only, fully
deterministic scoring, every state change audited.

Architecture: [`docs/design/opportunity-scout-engine.md`](../../docs/design/opportunity-scout-engine.md)

## Quick start (CLI)

```bash
# Capture
python -m plugins.opportunity_scout.cli add "Expert witness retainer — med-mal firm" \
  --tags expert-witness,anesthesia,recurring-revenue \
  --source-type direct_request \
  --revenue 60000 --chad-hours-weekly 2 --ai-hours-weekly 6

# Score (ROI + alignment + leverage + confidence + capacity fit → 0-100)
python -m plugins.opportunity_scout.cli score <id>

# Market validation (evidence is always human-entered)
python -m plugins.opportunity_scout.cli validate begin <id>
python -m plugins.opportunity_scout.cli validate evidence <id> problem_evidence \
  --summary "Two attorneys asked for CRNA standard-of-care review this quarter" \
  --source "Direct conversations" --strength strong
python -m plugins.opportunity_scout.cli validate resolve <id> problem_evidence pass

# Lifecycle
python -m plugins.opportunity_scout.cli advance <id> active --reason "Signed LOI"

# Portfolio
python -m plugins.opportunity_scout.cli list
python -m plugins.opportunity_scout.cli report
```

IDs accept unique prefixes (first 8 chars shown in `list`).

## Quick start (Python)

```python
from plugins.opportunity_scout import OpportunityScoutEngine

engine = OpportunityScoutEngine(store_path="/tmp/opps.json")
result = engine.capture({
    "title": "CRNA direct contract — Facility X",
    "tags": ["direct-contracts", "income-scaling"],
    "source_type": "personal_network",
    "expected_revenue_usd": 250_000,
    "chad_hours_upfront": 20,
})
opp = engine.score(result.opportunity.opportunity_id)
print(opp.score.composite, opp.score.expected_roi)
```

## Concepts

- **Lifecycle**: `captured → triaged → scored → validating → validated →
  active → realized`, with `parked` (revivable via `triaged`), `rejected`,
  and `expired`. Illegal transitions raise; every transition is logged with
  a reason.
- **Scoring**: composite 0–100 from expected ROI (Chad's time priced at
  $205/hr by default), strategic-goal tag alignment, AI-vs-Chad leverage,
  confidence, and weekly-capacity fit. Full breakdown is stored — every
  score is explainable.
- **Confidence**: prior from source type (idea 0.30 → existing client
  0.65), moved only by audited events (validation outcomes), clamped to
  [0.02, 0.98].
- **Validation**: six ordered stages (problem → demand → willingness to pay
  → competition → regulatory → capacity fit). Passing requires evidence;
  failing/skipping requires a written reason. Outcomes move confidence.
- **Dedup**: exact title fingerprint + fuzzy match (SequenceMatcher +
  Jaccard, threshold 0.82). Policy per capture: `flag` (default), `reject`,
  or `allow`.

## Storage

Single JSON file, atomic writes, thread-safe. Resolution order: explicit
path → `OPPORTUNITY_SCOUT_STORE_PATH` env var →
`~/.hermes/opportunity_scout_store.json`.

## Tests

```bash
pytest tests/opportunity_scout -q
```
