# DECISION_ENGINE — Evidence-First, Deterministic Recommendation

How the Chief of Staff layer decides what to recommend, and why the human
can trust the order it recommends things in.

## Principle: Evidence-First Decision Making

Every recommendation is a claim, and every claim carries its evidence:

1. **Observation** — what was actually seen (metric, log, diff, message,
   market fact), with a pointer the human can open.
2. **Inference** — the reasoning from observation to recommendation, stated
   plainly enough to be attacked.
3. **Estimate** — expected ROI (dollars), operator effort (minutes),
   strategic alignment, and confidence — each as an explicit number, not an
   adjective.
4. **Uncertainty** — what would change the recommendation if it turned out
   to be true.

A recommendation missing any of the four is not "pending polish"; it is
inadmissible. The system may say **"insufficient evidence"** — that answer is
always acceptable. Fabricating a confident answer is never acceptable and is
treated as the worst possible failure mode, because it poisons the only thing
the layer runs on: trust.

### Read-only evidence first

Evidence gathering is read-only by default. The engine may look at anything
it is permitted to see; it may not *change* anything to produce evidence
(no sends, no purchases, no state mutations) — action belongs to the
execution layer under the escalation contract
([HUMAN_FIRST.md](HUMAN_FIRST.md)).

## The Ranking Contract

Ranking is implemented in `chief_of_staff.ranking` and is **strictly
lexicographic** — each criterion only breaks ties left by every criterion
before it:

| # | Criterion | Direction | Rationale |
|---|---|---|---|
| 1 | **Safety** | lower risk first | No ROI justifies jumping the safety queue. |
| 2 | **Highest ROI** | larger `expected_roi_usd` first | Among equally safe options, money and time won. |
| 3 | **Lowest human effort** | fewer `chad_effort_minutes` first | The attention window is the scarce resource. |
| 4 | **Strategic alignment** | higher first | Prefer moves that advance the North Star, not just today. |
| 5 | **Confidence** | higher first | Between otherwise equal options, take the surer one. |
| — | Tiebreak: `id` | lexicographic | Makes the order *total* and reproducible. |

Properties the contract guarantees:

- **Deterministic** — the same input set always produces the same output
  order, regardless of input order. No randomness, no model temperature, no
  hidden state.
- **Total** — there are no "ties" surfaced to the human; the system does its
  job and commits to an order.
- **Explainable** — for any pair of recommendations, the engine can name the
  exact criterion that decided their order.

## The Executive Recommendation

The Morning Plan carries exactly **one** Executive Recommendation: the top of
the ranked list. Not three options, not a menu — one. The human can always
ask "what was second, and why?" (conversation mode answers deterministically
from the same ranking), but the default interaction is a single, defended
recommendation. Choice architecture is real: presenting five options costs
the human a decision; presenting one costs him a yes/no.

## What the Decision Engine Does *Not* Decide

- Whether to **commit** money, reputation, or irreversible action — that is
  human authority, always ([HUMAN_FIRST.md](HUMAN_FIRST.md)).
- Values and priorities — strategic alignment weights are *inputs* set by
  the human, not opinions formed by the engine.
- Its own scope — the engine ranks what it is given; it does not grant
  itself new categories of action to rank into existence.

## Feedback Loop

Acceptance is measured (`chief_of_staff.metrics`). A recommendation the human
consistently overrides is evidence about the engine, not about the human.
Persistent divergence between ranking and human choice triggers a review of
the estimates feeding the ranker — never a quiet re-weighting to flatter the
metric.
