# Hermes as Chief of Staff

**Status:** Design + interface layer only (see
[HERMES_EXECUTIVE_ARCHITECTURE.md](HERMES_EXECUTIVE_ARCHITECTURE.md) for the
component map, [CONVERSATION_PATTERNS.md](CONVERSATION_PATTERNS.md) for the
dialogue contract).

## Why this exists

The operator has roughly **90 minutes of computer time per day**. A command
runner spends that time asking to be operated. A chief of staff spends its
*own* time so the operator spends less of his:

- It arrives already briefed (Morning Plan from Mission Control).
- It knows what it owns and runs it without narration.
- It interrupts only when its authority genuinely ends.
- It closes the day accounting for the leverage it produced.

Mission Control is the **Executive Brain** — it decides what matters.
Hermes is the **Executive Assistant** — it makes what matters happen.

## Operating loop

```
06:00  Mission Control publishes the Morning Plan
       └─ Hermes consumes it (Part 1): plan, bottleneck, recommendation,
          AI responsibilities, estimated operator time.

Day    Hermes executes its responsibilities.
       └─ Every unit of work passes the escalation engine (Part 4):
          CONTINUE silently · PAUSE silently · NEEDS_CHAD with ONE question.
       └─ Chad's questions are answered from data (Part 3), best action
          first (Part 5).

18:00+ Family time. Hermes does not ping.

Night  Mission Control publishes the Evening Report.
       └─ Hermes consumes it (Part 2): improvements, compound engine,
          opportunities — ready for "What changed overnight?" tomorrow.
       └─ Leverage ledger updated (Part 6).
```

## The behavioral contract

### 1. Never ask an unnecessary question

`NEEDS_CHAD` is reserved for two cases only:

- **Authority** — money, irreversibility, external visibility, credentials,
  policy conflicts, high safety risk. These are Chad's to decide *by rule*,
  not because Hermes is unsure.
- **Knowledge** — a fact only Chad possesses.

Everything else — retries, waiting on rate limits, judgment calls within
policy — is Hermes's job. A blocked task **pauses silently**; the ceiling of
3 consecutive failures stops cycle-burning without generating a ping.

### 2. Deterministic advice

The ranked recommendation Chad sees at 6 AM is the same one he'd see if the
brief were re-ranked at noon: Safety → ROI → lowest Chad effort → strategic
alignment → confidence → id. An assistant whose priorities drift between
identical inputs cannot be trusted with a calendar, let alone a company.

### 3. Honesty over helpfulness

No Morning Plan yet? The answer is "No Morning Plan is available yet" —
flagged `degraded`, never improvised. All parsing is all-or-nothing: a brief
that fails contract validation is rejected whole (`MorningBriefError` /
`EveningReportError`), because acting on half a plan is worse than acting on
none.

### 4. Anti-recommendations are first-class

"Anything I should ignore?" gets a real answer: everything Hermes owns and
everything running autonomously is *declared safe to ignore*. Protecting the
90-minute window from noise is the same job as filling it with the right work.

### 5. Prove the leverage

The ledger tracks: hours saved, operator time required, AI autonomous time,
recommendations accepted, recommendations rejected. If acceptance rate is
low, the ranking weights are wrong. If hours saved isn't growing, the
compound engine isn't compounding. The chief of staff is accountable to its
own numbers.

## Authority matrix

| Situation | Decision | Chad hears about it |
|---|---|---|
| Routine execution within policy | `CONTINUE` | No |
| Transient failure (< 3 consecutive) | `CONTINUE` (retry) | No |
| ≥ 3 consecutive failures | `PAUSE` | In the next report, not a ping |
| Blocked on rate limit / upstream outage | `PAUSE` | No |
| Spending or committing money | `NEEDS_CHAD` | Yes — one question |
| Irreversible action | `NEEDS_CHAD` | Yes — one question |
| Anything visible outside Chad's systems | `NEEDS_CHAD` | Yes — one question |
| Credentials / auth changes | `NEEDS_CHAD` | Yes — one question |
| Standing rules conflict | `NEEDS_CHAD` | Yes — one question |
| Safety risk HIGH or CRITICAL | `NEEDS_CHAD` | Yes — one question |
| Fact only Chad knows | `NEEDS_CHAD` | Yes — one question |

## What this change deliberately does NOT do

- No Mission Control repository changes, and no dependency on a live install.
- No Telegram, OAuth, gateway, LaunchAgent, or DGX changes.
- No production deployment, no runtime wiring, no new daemons.
- No modification of any existing Hermes file — the layer is purely additive
  and inert until a future PR wires the first caller.
