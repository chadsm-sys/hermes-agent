# Executive Conversation Patterns

**Status:** Design + interface layer only. Implemented in
`chief_of_staff/conversation.py`; tested in
`tests/chief_of_staff/test_conversation.py`.

## Principle

Hermes stops acting like a command runner. Chad talks to it like a chief of
staff, and it answers **from the Morning Plan and Evening Report — never from
imagination**. Six executive intents are recognized; everything else falls
through (`classify_intent(...) → None`) to the existing Hermes pipeline
unchanged, so current behavior is preserved by construction.

Every answer is an `ExecutiveResponse`: a `headline` (the answer in one
line), `details` (most important first), and a `degraded` flag when a source
had no data. Rendering — chat bubble, TUI panel, printed brief — is the
caller's concern.

## The six patterns

### 1. "Good morning." → `MORNING_GREETING`

The whole day in one glance. Sourced from the Morning Brief.

> **Good morning. Plan for 2026-07-05 is loaded.**
> Your plan has 2 item(s) needing you — about 35 minutes of your time.
> Bottleneck: Hermes gateway restarts are manual
> Recommendation: Sign the Gusto payroll authorization
> 1. Approve quarterly tax transfer (~15 min)
> 2. Review ExpertWitness intake copy (~20 min)
> I'm carrying 3 item(s) autonomously.

Pattern: operator time first (the scarcest resource), then the constraint,
then the single best action, then the short list — and what Hermes is
already carrying so Chad doesn't re-plan it.

### 2. "What should I focus on?" → `FOCUS`

One thing, with its price and its payoff. Sourced from the brief's
Executive Recommendation (already ranked by the deterministic ranker on the
Mission Control side; Hermes re-ranks candidate sets with the same rules).

> **Focus on: Sign the Gusto payroll authorization**
> Unblocks the S-Corp W-2 setup worth $57K/year.
> Costs you about 10 minutes; expected return ≈ $57,000.

Never a list. Focus means one.

### 3. "What's my bottleneck?" → `BOTTLENECK`

The constraint, its cost, and the one unblocking move.

> **Bottleneck: Hermes gateway restarts are manual**
> Cost of leaving it: Every restart costs ~20 operator minutes
> Unblocking move: Approve the supervised-restart runbook

### 4. "What changed overnight?" → `OVERNIGHT_CHANGES`

Sourced from the Evening Report: the day's summary, permanent AI
improvements, then top opportunities by ROI.

> **Overnight, 1 improvement(s) landed.**
> Shipped 3 backlog items; gateway ran clean all day.
> Improved: Retry logic now survives provider timeouts
> Opportunity: Expert witness inquiry pending reply (≈ $12,000, medium effort)
> Opportunity: Facility 3 wants two extra shifts (≈ $4,920, low effort)

### 5. "Anything I should ignore?" → `IGNORE_LIST`

The anti-recommendation. Everything Hermes owns (plan items owned by
`hermes`, autonomous AI responsibilities) is declared explicitly ignorable.
Non-autonomous responsibilities are **not** listed — they may still need Chad.

> **Safe to ignore today: 2 item(s). They're covered.**
> Rebuild flaky gateway test — mine, I'll report back
> Triage overnight backlog — running autonomously

When nothing is delegable: *"Nothing is safely ignorable today — every open
item needs you."*

### 6. "What should I learn?" → `LEARNING`

Sourced from the Compound Engine: the capabilities that keep paying, ranked
by total minutes saved, then reuse count. The thing that compounds hardest
is the thing worth understanding.

> **Worth learning: Backlog triage classifier**
> Backlog triage classifier — reused 30×, 600 operator minutes saved so far
> Invoice draft generator — reused 12×, 240 operator minutes saved so far

## Recognition rules

Matching is deterministic: lowercase, whitespace-normalized, first match in
an ordered pattern table wins.

| Intent | Triggers (regex, ordered) |
|---|---|
| `MORNING_GREETING` | `\bgood\s+morning\b` · `\bmorning\b\W*$` |
| `FOCUS` | `\bfocus\b` |
| `BOTTLENECK` | `\bbottleneck` |
| `OVERNIGHT_CHANGES` | `\bovernight\b` · `\bwhat('s| is| has)? changed\b` |
| `IGNORE_LIST` | `\bignore\b` |
| `LEARNING` | `\blearn(ing)?\b` |

Deliberately conservative. `"run the gateway restart script"`, `"git
status"`, and retired Life-OS phrases like `"log my shift"` classify as
`None` and flow to the normal pipeline untouched.

## Degraded mode

Every composer answers honestly when its source is empty:

| Missing source | Answer |
|---|---|
| Morning Brief | "No Morning Plan is available yet — Mission Control hasn't published one." |
| Evening Report | "No Evening Report is available yet — Mission Control hasn't published one." |

`degraded=True`, `details=()` — no fabrication, ever.

## Non-patterns (rejected designs)

- **LLM intent classification** — rejected: nondeterministic, and a chief of
  staff must answer identically to identical questions.
- **Free-form generated summaries** — rejected: composition is template-level
  and traceable to payload fields, so every claim is auditable.
- **Proactive pings on PAUSE** — rejected: pauses surface in the next brief;
  only `NEEDS_CHAD` may interrupt, with at most one question
  (see the escalation engine in
  [HERMES_EXECUTIVE_ARCHITECTURE.md](HERMES_EXECUTIVE_ARCHITECTURE.md)).
