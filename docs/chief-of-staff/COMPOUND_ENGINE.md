# COMPOUND_ENGINE — Capability That Gains Value With Reuse

The difference between a tool and an assistant is memory. The difference
between an assistant and a *great* assistant is compounding: every solved
problem makes the next hundred problems cheaper.

## Principle

Work product decays; capability compounds. The Compound Engine is the
discipline of noticing which of today's work can be converted into a
**durable, reusable capability** — and refusing to let that conversion be
optional.

A capability qualifies for the Compound Engine when it is:

1. **Durable** — it survives the session, the model, and the machine. It
   lives in a repo, a contract, a document, a dataset — not in a
   conversation buffer.
2. **Reusable** — the second use costs materially less than the first, and
   the marginal cost keeps falling.
3. **Trustable** — it is tested or verifiable enough to be reused *without
   re-deriving it*, which is the whole point.
4. **Findable** — an asset nobody can locate has a compounding rate of zero.
   Indexing is part of the asset, not an afterthought.

## The Asset Ledger

The Evening Report's **Compound Engine** section is a ledger entry, not a
feelings journal. Each entry records:

- **Asset** — what now exists that did not exist this morning (or what
  existing asset gained value today through reuse or hardening).
- **Trigger** — the work that produced it (ties back to the day's plan).
- **Reuse projection** — honest estimate of how often it will be used and
  what each use saves, in minutes or dollars.
- **Decay risk** — what will silently rot it (an API change, a stale
  credential, an unowned dependency) and how that is monitored.

Assets with zero reuse after a stated horizon are flagged. A library of
unused assets is inventory, and inventory is a cost
([PHILOSOPHY.md](PHILOSOPHY.md), Asset-First).

## AI Improvements vs. Compound Assets

The Evening Report separates two things deliberately:

- **AI Improvements** — the AI layer got permanently better *at doing*
  something today: a new skill, a corrected assumption, a tightened
  contract, a failure mode eliminated.
- **Compound Engine** — a capability exists whose value grows *with reuse*,
  regardless of which layer (human or AI) reuses it.

The first is about the assistant's competence curve. The second is about the
estate's asset base. Both must move; [MISSION.md](MISSION.md) calls this
Better AI + Better Chad, and the compounding ledger is where "better" is
proven rather than asserted.

## Compounding Rules

1. **Second-fire rule.** The first occurrence of a problem may be solved by
   hand. The second occurrence *must* produce an asset (playbook, script,
   contract, test) alongside the fix. Fighting the same fire a third time
   manually is a process defect, and the Evening Report says so.
2. **Interfaces over integrations.** Contracts (like the frozen consumer
   contracts in `chief_of_staff/`) compound across every future
   implementation; a point integration compounds across exactly one.
3. **Small and finished beats large and open.** A shipped 100-line asset
   with a test compounds; an unfinished framework compounds negatively —
   it consumes attention every time it is stepped around.
4. **Deletion is compounding too.** Removing a system nobody trusts, parking
   a project cleanly, or retiring a stale document raises the value of
   everything that remains findable. The ledger records removals as gains.
5. **No compounding without measurement.** `chief_of_staff.metrics` tracks
   hours saved and reuse; an asset's claimed value is periodically compared
   against its measured value, evidence-first
   ([DECISION_ENGINE.md](DECISION_ENGINE.md)).

## Relationship to the Bottleneck Engine

Recurring bottlenecks are the highest-yield asset signals in the system: a
constraint that appears repeatedly is an asset waiting to be built. When the
Bottleneck Engine elevates a constraint ([BOTTLENECK_ENGINE.md](BOTTLENECK_ENGINE.md)),
the Compound Engine's question is always asked first: *"what asset would make
this class of bottleneck impossible?"* — before money or recurring human
time is spent.
