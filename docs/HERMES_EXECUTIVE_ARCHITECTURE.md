# Hermes Executive Architecture

**Status:** Design + interface layer only. No runtime wiring, no deployment.
**Package:** `chief_of_staff/` · **Tests:** `tests/chief_of_staff/`
**Companion docs:** [CHIEF_OF_STAFF.md](CHIEF_OF_STAFF.md) · [CONVERSATION_PATTERNS.md](CONVERSATION_PATTERNS.md)

## The division of labor

| Role | System | Responsibility |
|---|---|---|
| **Executive Brain** | Mission Control | Decides *what matters*: publishes the Morning Plan and the Evening Report. |
| **Executive Assistant** | Hermes | Decides *how it gets done*: executes, escalates precisely, reports leverage. |
| **Executive** | Chad | Spends his ~90 daily minutes only where his authority or knowledge is required. |

Hermes stops being a command runner. It becomes the layer that consumes
executive intent from Mission Control, carries autonomous work under a
deterministic escalation policy, and answers executive questions from data
instead of improvisation.

## Component map

```
Mission Control (future APIs — NOT depended on today)
        │
        │  Morning Plan payload            Evening Report payload
        ▼                                  ▼
┌─────────────────────┐          ┌──────────────────────┐
│ morning_brief.py    │          │ evening_report.py    │   Part 1 & 2
│ MorningBriefSource  │          │ EveningReportSource  │   (consumer contracts)
│ parse_morning_brief │          │ parse_evening_report │
└─────────┬───────────┘          └──────────┬───────────┘
          │                                 │
          ▼                                 ▼
┌──────────────────────────────────────────────────────┐
│ conversation.py — Executive Conversation Mode        │   Part 3
│ classify_intent → ExecutiveConversation composers    │
└─────────┬────────────────────────────────────────────┘
          │ uses
          ▼
┌────────────────────┐   ┌─────────────────────────────┐
│ ranking.py         │   │ escalation.py               │   Parts 5 & 4
│ deterministic      │   │ CONTINUE / PAUSE /          │
│ recommendation     │   │ NEEDS_CHAD rule table       │
│ ordering           │   └─────────────────────────────┘
└────────────────────┘
          │ outcomes feed
          ▼
┌──────────────────────────────────────────────────────┐
│ metrics.py — LeverageLedger / LeverageStore          │   Part 6
│ hours saved · operator time · AI time · accept/reject│
└──────────────────────────────────────────────────────┘
```

## Part 1 — Morning Brief consumer (`morning_brief.py`)

Hermes understands exactly five things about the Morning Plan payload:

| Section | Type | Meaning |
|---|---|---|
| Today's Plan | `tuple[PlanItem, ...]` | Ordered work items, each owned by `"chad"` or `"hermes"`. |
| Biggest Bottleneck | `Bottleneck` | The one constraint, its cost, and the one unblocking action. |
| Executive Recommendation | `Recommendation` | The single best use of Chad's time, with the five ranking fields. |
| AI Responsibilities | `tuple[AIResponsibility, ...]` | What Hermes owns today, flagged autonomous or not. |
| Estimated Operator Time | `estimated_operator_minutes: int` | Total hands-on minutes the plan asks of Chad. |

Contract rules:

- `schema_version` is `"<major>.<minor>"`. Hermes accepts any minor drift
  within major version `1` and rejects everything else (`MorningBriefError`).
- Parsing is **all-or-nothing** — Hermes never acts on a partially valid brief.
- All parsed types are frozen dataclasses; a brief cannot be mutated after parse.

`MorningBriefSource` is the only seam to Mission Control
(`fetch_latest() -> MorningBrief | None`). Today the only implementation is
`StaticMorningBriefSource` (in-memory). The live HTTP adapter is future work
and lives *outside* this package; nothing here knows a URL.

## Part 2 — Evening Report consumer (`evening_report.py`)

Same pattern, four sections:

| Section | Type | Meaning |
|---|---|---|
| Evening Report | `summary: str` | The day's outcome — shipped, slipped, broke. |
| AI Improvements | `tuple[AIImprovement, ...]` | What the AI layer got permanently better at. |
| Compound Engine | `tuple[CompoundEntry, ...]` | Capabilities whose value grows with reuse (`reuse_count`, `minutes_saved_total`). |
| Opportunity Summary | `tuple[Opportunity, ...]` | Money/time opportunities with ROI and Chad-effort grade. |

`EveningReportSource` mirrors `MorningBriefSource`. `EveningReport.top_opportunities()`
orders by ROI with a deterministic id tiebreak.

## Part 3 — Executive Conversation Mode (`conversation.py`)

See [CONVERSATION_PATTERNS.md](CONVERSATION_PATTERNS.md). Two invariants:

1. `classify_intent` returns `None` for anything unrecognized, so the
   existing Hermes pipeline handles it **unchanged** — behavior preservation
   by construction.
2. Composers only speak from the injected sources. No brief → an honest
   degraded answer (`ExecutiveResponse.degraded = True`), never a fabricated one.

## Part 4 — Escalation engine (`escalation.py`)

An ordered, deterministic rule table over `WorkSignals`:

| Order | Rule family | Decision |
|---|---|---|
| 1 | Authority Hermes must not exercise: irreversible, spends money, external side effects, credentials, policy conflict, `SafetyRisk >= HIGH` | `NEEDS_CHAD` |
| 2 | Blocked on knowledge only Chad has | `NEEDS_CHAD` |
| 3 | Failure ceiling (≥ 3 consecutive) or self-resolving external block | `PAUSE` |
| 4 | Everything else | `CONTINUE` |

**Never ask unnecessary questions:** only a `NEEDS_CHAD` result may carry a
question, at most one, and only if a precise one was prepared. A `PAUSE` is
silent by design. Every result names the rule that fired (`authority.money`,
`throttle.failure_ceiling`, …) so decisions are auditable.

## Part 5 — Recommendation ranking (`ranking.py`)

Strictly lexicographic sort key — each criterion only breaks ties left by
the previous ones:

1. Safety (lower `SafetyRisk` first)
2. Highest ROI (`expected_roi_usd`)
3. Lowest Chad effort (`chad_effort_minutes`)
4. Strategic alignment
5. Confidence
6. `id` — final tiebreak, making the order **total**: same set in, same
   order out, independent of input order. No randomness, no model state.

## Part 6 — Human leverage metrics (`metrics.py`)

`LeverageLedger` accumulates the five numbers that justify this layer's
existence: minutes saved, operator minutes, AI autonomous minutes,
recommendations accepted, recommendations rejected. `LeverageSnapshot`
derives hours, `acceptance_rate` (`None` ≠ `0.0`: unused ≠ distrusted) and
`leverage_ratio`. Persistence is behind the `LeverageStore` protocol —
JSON, SQLite, or Mission Control itself can implement it later.

## Guarantees (validation posture)

- **No Mission Control dependency** — no HTTP client, no URL, no import of
  any network machinery anywhere in `chief_of_staff/` (asserted by test).
- **No runtime change** — no existing Hermes module imports this package;
  no existing file is modified by this change; nothing here does I/O.
- **No install/deployment implications** — the package is not added to the
  wheel (`[tool.setuptools.packages.find]` untouched). Packaging inclusion
  is deliberately deferred to the PR that wires the first real caller.
- **Deterministic everywhere** — parsing, intent classification, escalation,
  and ranking are pure functions of their inputs.

## Future wiring (explicitly out of scope here)

1. Mission Control HTTP adapters implementing the two `*Source` protocols.
2. A gateway/TUI hook that offers utterances to `ExecutiveConversation.respond`
   before the normal pipeline (falls through on `None`).
3. `LeverageStore` implementation + inclusion of the package in the wheel.
4. Escalation-engine adoption by lane runners emitting `WorkSignals`.
