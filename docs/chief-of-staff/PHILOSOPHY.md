# PHILOSOPHY — What the Chief of Staff Layer Believes

Derived from [MISSION.md](MISSION.md). These are the operating beliefs that
resolve design arguments before they start.

## 1. Asset-First

**Prefer work that leaves an asset behind over work that leaves only an outcome.**

Every task has two possible outputs:

- an **outcome** — the ticket closed, the email drafted, the number computed;
- an **asset** — a contract, a skill, a playbook, a dataset, a test, a
  document that makes the *next* hundred outcomes cheaper.

Given two ways to accomplish the same outcome, the Chief of Staff layer
always chooses the one that also produces an asset — even when it costs
slightly more today. This is the input side of the
[Compound Engine](COMPOUND_ENGINE.md): compounding requires principal, and
assets are the principal.

Corollaries:

- One-off heroics are a smell. If the same fire is fought twice, the second
  firefight must produce the extinguisher.
- Interfaces beat implementations. A frozen contract (like the consumer
  contracts in `chief_of_staff/`) outlives any single integration.
- Documentation is an asset class, not overhead. An undocumented capability
  cannot compound because it cannot be safely reused.

## 2. Opportunity Philosophy

**Opportunities are perishable inventory. Surface them fast, price them
honestly, and let the human spend or discard them.**

The Evening Report carries an **Opportunity Summary** for a reason: valuable
options appear constantly (a contract opening, an arbitrage in scheduling, a
tool that erases a weekly cost) and expire silently. The system's job is:

1. **Detect** — notice the opportunity in the day's evidence.
2. **Price** — attach an honest estimate: expected value in dollars or hours,
   confidence, and cost in operator minutes.
3. **Rank** — feed it through the [Decision Engine](DECISION_ENGINE.md) like
   any other recommendation. Opportunities get no romantic exemption from
   ranking.
4. **Expire** — stale opportunities are removed loudly, not left to rot in a
   backlog that erodes trust in the list.

What the system never does is *chase* opportunities autonomously. Detection
and pricing are machine work; commitment is human work
([HUMAN_FIRST.md](HUMAN_FIRST.md)).

## 3. Determinism Over Cleverness

An executive assistant whose priorities change between identical mornings is
not trustworthy. Wherever possible the layer uses deterministic composition —
same inputs, same outputs, total ordering, no hidden state. Model creativity
is welcome in drafting and research; it is banned from ranking, escalation
classification, and status reporting.

## 4. Evidence Before Opinion

No claim ships without a source the human can check: a metric, a file, a
diff, a log line, a citation. "The AI thinks so" is not evidence. This is
expanded in [DECISION_ENGINE.md](DECISION_ENGINE.md); it applies equally to
coaching claims in [EXECUTIVE_COACH.md](EXECUTIVE_COACH.md) — if the system
tells the human he is improving, it must be able to show the numbers.

## 5. Attention Is the Scarce Resource

Money can be re-earned; the operator's daily attention window cannot. Every
feature is priced in **operator minutes** before it is priced in anything
else. The metrics module (`chief_of_staff.metrics`) exists to keep this
honest: hours saved, operator time required, autonomous time, and whether
recommendations are actually accepted. A Chief of Staff layer that consumes
more attention than it returns gets deleted, however impressive it is.

## 6. The System Serves a Life

Constraints imposed by the human's life are treated as physics, not
preferences: the daily attention window is hard, evenings belong to family,
recovery states gate new construction. The system schedules around these
constraints; it never negotiates with them. The final filter from
[MISSION.md](MISSION.md) applies to every plan the layer produces.

## Anti-Patterns (explicitly rejected)

- **Busyness theater** — reporting activity instead of outcomes and assets.
- **Question spam** — exporting decisions to the human because asking is
  easier than deciding safely ([HUMAN_FIRST.md](HUMAN_FIRST.md)).
- **Dashboard worship** — optimizing a metric after it has stopped
  representing the mission.
- **Silent scope growth** — new autonomous authority acquired by drift
  instead of by explicit grant.
- **Dependence engineering** — designs that make the human weaker so the
  system looks stronger.
