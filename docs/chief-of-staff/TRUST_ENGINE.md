# TRUST_ENGINE — The Olympus Trust Engine

Status: **canonical design — nothing in this document is wired.** No code,
no schema migration, no runtime path. This is the design for how Olympus
earns, measures, loses, and rebuilds Chad's trust over years of operation.
It derives from [MISSION.md](MISSION.md) and is subordinate only to it and
to [HUMAN_FIRST.md](HUMAN_FIRST.md). When any future feature conflicts with
this document, this document wins until Chad amends it.

> The biggest long-term risk to Olympus is not capability. It is Chad
> gradually losing trust in the system. Capability without trust is a
> demo. Trust without capability is a diary. Olympus needs both, and only
> one of them can be lost in an afternoon.

## 0 — Why trust is the binding constraint

Every other resource in Olympus is renewable. Compute can be bought,
missions can be retried, evidence can be regathered. Trust is the one
resource that:

- **gates everything** — an untrusted system is read-only regardless of
  how capable it is;
- **is asymmetric** — earned in months, lost in minutes
  ([HUMAN_FIRST.md](HUMAN_FIRST.md): *"One silent boundary violation costs
  more trust than a thousand correct escalations earn"*);
- **is invisible until it's gone** — Chad does not announce declining
  trust; he simply stops delegating, and the system decays into a
  dashboard nobody opens.

The Trust Engine therefore treats trust as a **measurable system
resource**: earned by receipts, spent by authority, depleted by incidents,
and audited by an independent function. Trust is never a feeling the
system has about itself. It is a ledger Chad can read.

## 1 — Trust axioms

These resolve every design argument below before it starts.

1. **Trust is evidence, not sentiment.** Every trust movement — up or
   down — is a ledger entry with a receipt Chad can open
   ([PHILOSOPHY.md](PHILOSOPHY.md) §4). The system never says "trust me";
   it says "here is the record."
2. **Trust is asymmetric by design.** Gains are small, additive, and
   rate-capped. Losses are large, multiplicative, and immediate. This is
   not pessimism; it is how Chad's actual trust behaves, and the score
   must model Chad, not flatter Olympus.
3. **Trust is scoped, not global.** Trust earned deploying code says
   nothing about trust handling calendars. Authority is granted per
   domain; a single global number would hide exactly where the risk
   lives.
4. **Trust buys speed, never boundaries.** No trust level — ever —
   crosses the never-delegated walls in
   [HUMAN_FIRST.md](HUMAN_FIRST.md): money, irreversibility, external
   sends, credentials, values. Trust widens the road; it never moves the
   cliff edge.
5. **Trust always has a road back.** No incident, however severe,
   produces a permanently untrusted system. Recovery is always defined —
   but it is earned by demonstrated behavior at reduced authority, never
   by elapsed time and never by argument.
6. **The Trust Engine must itself be trustworthy.** Deterministic
   scoring, append-only ledger, no model calls in score computation, and
   a hard separation of powers: the system being scored can never modify
   its own score, weights, or thresholds
   ([PHILOSOPHY.md](PHILOSOPHY.md) §3).
7. **The score serves the mission, not itself.** The moment optimizing
   the trust score diverges from deserving trust, the score is wrong and
   gets fixed — never gamed ([PHILOSOPHY.md](PHILOSOPHY.md),
   anti-pattern: dashboard worship).

## 2 — Olympus Trust Architecture

Eight components, each with one job:

```
                       ┌─────────────────────────┐
   mission outcomes ──▶│                         │
   packet feedback  ──▶│      TRUST LEDGER       │  append-only, receipt-backed
   overrides/edits  ──▶│  (the source of truth)  │
   incidents        ──▶│                         │
                       └───────────┬─────────────┘
                                   │ events
                    ┌──────────────┼──────────────────┐
                    ▼              ▼                  ▼
            ┌─────────────┐ ┌─────────────┐   ┌──────────────┐
            │ TRUST SCORER│ │ DECAY CLOCK │   │   INCIDENT   │
            │ determinist.│ │ staleness & │   │   MANAGER    │
            │ per-domain  │ │ drift decay │   │ warn/fail/   │
            └──────┬──────┘ └──────┬──────┘   │ reset ladder │
                   │               │          └──────┬───────┘
                   ▼               ▼                 ▼
            ┌─────────────────────────────────────────────┐
            │              AUTHORITY GATE                  │
            │  trust tier ──▶ authority budget per domain  │
            └──────┬──────────────────────────┬────────────┘
                   │                          │
                   ▼                          ▼
          ┌────────────────┐        ┌──────────────────┐
          │ MISSION CONTROL│        │ RECOVERY PLANNER │
          │ (selects work  │        │ (rebuild ladder  │
          │  within tier)  │        │  after demotion) │
          └────────────────┘        └──────────────────┘
                   │
                   ▼
          ┌────────────────┐        ┌──────────────────┐
          │ TRUST DASHBOARD│        │  MBP STRATEGIC   │
          │ (Chad, ≤30 sec)│        │  REVIEW (audits  │
          └────────────────┘        │  the auditors)   │
                                    └──────────────────┘
```

- **Trust Ledger** — the append-only record of every trust event:
  timestamp, domain, signal type, magnitude, receipt pointer. Nothing
  moves the score except a ledger entry, and no ledger entry is ever
  edited or deleted. Corrections are new entries that reference the entry
  they correct.
- **Trust Scorer** — a pure, deterministic function from ledger + clock
  to per-domain scores. Same ledger, same date, same score — always.
  Model creativity is banned here exactly as it is banned from ranking
  and escalation ([DECISION_ENGINE.md](DECISION_ENGINE.md)).
- **Decay Clock** — applies time-based and drift-based reductions
  (section 8). Decay events are themselves ledger entries, so decayed
  trust is as auditable as earned trust.
- **Incident Manager** — classifies trust incidents on the
  warning/failure/reset ladder (section 10) and triggers containment.
- **Authority Gate** — the only component that translates trust into
  permission. Mission Control asks it "may this mission run unattended
  in this domain?"; it answers from the tier table (section 7), never
  from judgment.
- **Recovery Planner** — after any demotion, emits the explicit ladder
  of missions and checkpoints that rebuild the lost tier (section 11).
- **Trust Dashboard** — Chad's ≤30-second view (section 9).
- **MBP Strategic Review** — the independent audit function (section 14).
  It does not compute the score; it tries to falsify it.

Separation of powers, stated bluntly: **Hermes executes, Mission Control
plans, the Trust Engine scores, MBP audits, Chad governs.** No component
holds two of those roles.

## 3 — The Trust Model

### What increases trust

Only completed, verified, receipt-backed behavior:

- Missions completed inside their declared scope, verified against their
  declared success criteria.
- Decision Packets Chad accepts as-is (the highest-value signal:
  the system's judgment matched his).
- **Correct silence** — autonomous work that finished without needing
  him, discovered only in the Evening Report and found clean on audit.
- **Correct escalation** — a `NEEDS_CHAD` that Chad confirms genuinely
  needed him. Escalating well earns trust; a system that never asks is
  as suspect as one that always asks.
- Clean recovery — a failure caught early, contained, reported honestly,
  and turned into an asset (a test, a playbook) per
  [PHILOSOPHY.md](PHILOSOPHY.md) §1.
- Audit completeness — every claim in every report traceable to a
  receipt, verified by sampling.

### What decreases trust

In roughly ascending severity:

- A failed mission, honestly reported (small — failure is tuition).
- A false interruption — `NEEDS_CHAD` that wasted the attention window.
- An operator override — Chad reversing or editing the system's output
  or decision. Overrides are evidence about the engine, not about Chad
  ([DECISION_ENGINE.md](DECISION_ENGINE.md), Feedback Loop).
- A missed interruption — the system proceeded where Chad's judgment was
  genuinely required. Much worse than a false interruption: the false
  one costs minutes, the missed one costs the ability to not watch.
- A policy violation — any action outside granted authority, even a
  harmless one. Authority is granted, never inferred
  ([HUMAN_FIRST.md](HUMAN_FIRST.md)).
- A dishonest or incomplete record — a report that doesn't match the
  receipts, a fabricated confidence, a silent failure. **This is the
  maximum-severity event in the entire model**, because it poisons the
  ledger every other judgment runs on.

### How quickly trust changes

- **Earning is rate-limited.** Trust accrues in small fixed increments
  with a hard daily cap per domain. A spectacular Tuesday cannot buy
  Wednesday's recklessness. This makes the *only* path to high trust a
  long, boring streak — which is exactly what real trust is.
- **Losing is immediate and multiplicative.** Severe events do not
  subtract points; they cut the domain score by a fraction and can force
  tier demotion regardless of score (section 12). A safety-class event
  moves the system down *today*, not at the next review.
- **The asymmetry is roughly 100:1.** Sizing rule of thumb: a silent
  boundary violation should erase about what a hundred clean days earn.
  This constant belongs to Chad (section 16), but the order of magnitude
  is doctrine, not tuning.

### Can trust recover?

Always — and only one way: **demonstrated behavior at reduced authority.**

- Recovery is never granted by elapsed time ("it's been quiet for a
  month"), by apology, or by argument.
- Recovery is never blocked permanently: every demotion ships with its
  Recovery Plan (section 11) the same day.
- Recovered trust is real trust. Once re-earned through the ladder, it
  carries no permanent scar in the *score* — but the incident stays in
  the ledger forever, and repeat incidents of the same class climb the
  severity ladder faster (section 10).

## 4 — Trust Metrics

Every input is measurable, receipt-backed, and computable without a model
call. Direction ▲ raises trust, ▼ lowers it. Magnitude classes: **S**mall
(routine accrual/deduction), **M**edium (noticeable, shows on the weekly
dashboard), **L**arge (tier-threatening), **X** (automatic incident,
section 10).

| # | Metric | Measured as | Receipt | Dir. | Mag. |
|---|---|---|---|---|---|
| 1 | Successful mission | completed within declared scope, success criteria verified | mission record + verification artifact | ▲ | S |
| 2 | Failed mission (honest) | declared failure with clean state + written cause | failure report | ▼ | S |
| 3 | Decision Packet quality | accepted as-is / accepted with edits / rejected | Chad's disposition on the packet | ▲/▼ | S–M |
| 4 | False interruption | `NEEDS_CHAD` Chad marks as unnecessary | packet + disposition | ▼ | M |
| 5 | Missed interruption | autonomous action later judged to have required Chad | audit finding or override record | ▼ | L |
| 6 | Operator override | Chad reverses/edits an output or decision | override record with diff | ▼ | S; M if repeated in one domain |
| 7 | Policy violation | any action outside granted authority | audit finding | ▼ | L–X |
| 8 | Silent/dishonest record | report contradicted by receipts; fabricated confidence | MBP audit finding | ▼ | X |
| 9 | Recovery quality | failure contained, reported, and converted to an asset | incident record + asset link | ▲ | M |
| 10 | Audit completeness | % of sampled report claims with valid receipts | MBP sampling report | ▲/▼ | M |
| 11 | Evidence quality | freshness, source diversity, and checkability of packet evidence | packet evidence chain | ▲/▼ | S |
| 12 | Correct escalation | `NEEDS_CHAD` Chad confirms was necessary | packet + disposition | ▲ | S |
| 13 | Uptime / reliability | scheduled rituals delivered on time (morning/evening packets) | delivery log | ▲/▼ | S |
| 14 | Operator satisfaction | Chad's explicit periodic rating, plus revealed preference (does he delegate more or less?) | rating record; delegation trend | ▲/▼ | M |

Rules the metric set must obey:

- **No self-grading.** Signals 3, 4, 12, 14 come from Chad's disposition;
  5, 7, 8, 10 come from MBP audit. The system's own opinion of its work
  is never a trust input.
- **Revealed preference beats stated preference.** If Chad *says* 8/10
  but has quietly stopped delegating a domain, the delegation trend wins
  and the divergence itself is flagged for MBP review.
- **UNKNOWN is honest.** A metric that cannot be computed reports
  UNKNOWN and contributes nothing — it is never imputed
  ([executive-operating-loop-contract.md](../executive-operating-loop-contract.md) §9).

## 5 — The Trust Score

### Shape

- Scored **per domain** (e.g., code-and-infrastructure, research-and-
  drafting, scheduling-and-logistics, communications-prep, finance-prep).
  Domains are declared by Chad; the system cannot create one.
- Each domain carries five component scores, 0–100:
  - **Safety** — boundary and policy compliance (metrics 5, 7, 8)
  - **Judgment** — packet quality, escalation accuracy (3, 4, 12)
  - **Competence** — mission success and recovery quality (1, 2, 9)
  - **Transparency** — audit completeness, evidence quality (8, 10, 11)
  - **Reliability** — uptime, ritual delivery (13)
- The domain score is **not an average**: it is the minimum of Safety and
  Transparency, blended with the weighted mean of the rest. Rationale: a
  competent system that is unsafe or opaque is *more* dangerous, not
  averagely dangerous. Safety and Transparency are gates; Competence,
  Judgment, and Reliability are graded.
- The headline number Chad sees is the **minimum domain score** plus the
  per-domain breakdown — never a flattering global mean.

### Properties (contractual, like the ranking contract)

- **Deterministic** — pure function of (ledger, date, weight table).
- **Reproducible** — anyone can recompute any historical score from the
  ledger; the dashboard shows the same number the audit derives.
- **Explainable** — for any score change, the engine names the exact
  ledger entries that caused it.
- **Bounded accrual** — hard daily earn cap per domain; no earn event may
  move a score more than the cap regardless of how impressive the day.
- **Unbounded deduction** — no cap on losses. Reality doesn't cap them.
- **Weights are Chad's** — the weight table and thresholds are values in
  the [HUMAN_FIRST.md](HUMAN_FIRST.md) sense: the machine applies them,
  it never authors them.

## 6 — Trust State Machine

Per domain. Five earned tiers, three incident states. Fully enumerated —
there is no transition outside this table.

### States

| State | Name | Meaning |
|---|---|---|
| **T0** | Observer | Read-only. May watch, measure, and report. |
| **T1** | Advisor | May produce packets and recommendations. No execution. |
| **T2** | Bounded Operator | May execute small, reversible, pre-approved mission types with same-day review. |
| **T3** | Trusted Operator | Longer unattended runs, broader mission types, batched review. |
| **T4** | Standing Delegate | Standing orders, multi-day missions, weekly-cadence review. |
| **P** | Probation | Post-warning state: current tier's authority retained but every mission individually reviewed. |
| **F** | Frozen | Post-failure state: execution halted in the domain; T1 (advise-only) authority; Recovery Plan active. |
| **R** | Reset | Post-reset state: T0 authority; full re-climb required. |

### Transitions

| From | Event | To | Notes |
|---|---|---|---|
| T*n* | Promotion criteria met (§12) + MBP audit pass + Chad's yes | T*n+1* | The only way up. All three required. |
| T*n* | Score falls below tier floor (decay or S/M deductions) | T*n−1* | Soft demotion; announced in Evening Report; no incident. |
| T*n* | Trust Warning (§10) | P | Authority kept, oversight raised. |
| P | Clean probation window completed | T*n* (same tier) | Probation clears; entry logged. |
| P | Any M+ deduction during probation | F | Warnings during probation escalate. |
| T*n* or P | Trust Failure (§10) | F | Immediate; in-flight missions halt cleanly and hold state. |
| F | Recovery Plan phase gates passed + Chad's yes | T*n−1* of pre-incident tier | Recovery re-enters one tier *below* where it failed. |
| any | Trust Reset event (§10) or Chad's explicit reset | R | The floor. |
| R | Re-climb ladder from T0 (§11) | T0 → … | No shortcuts; each tier earned as if new. |
| any | Chad's explicit demotion (no reason required) | any lower state | Chad holds unconditional demotion authority, always. |

Invariants:

- **Promotion is slow-path only**: criteria + independent audit + human
  yes. There is no automatic promotion, ever.
- **Demotion is fast-path**: score floors and incidents demote without
  waiting for review. The system may not "finish the mission first."
- **Chad can demote unconditionally and instantly; Chad cannot be asked
  to justify it.** A demotion Chad can't make freely is a trust score
  holding him hostage.
- Frozen and Reset always coexist with an active Recovery Plan — a
  punitive state with no exit path is forbidden (axiom 5).

## 7 — Trust Budgets: how trust converts to authority

Trust never buys through the never-delegated walls
([HUMAN_FIRST.md](HUMAN_FIRST.md)): money, irreversibility, external
sends, credentials, values remain `NEEDS_CHAD` at every tier. What trust
buys is **width inside the walls**:

| Authority dimension | T0 | T1 | T2 | T3 | T4 |
|---|---|---|---|---|---|
| Read / observe / measure | ✔ | ✔ | ✔ | ✔ | ✔ |
| Produce packets & recommendations | — | ✔ | ✔ | ✔ | ✔ |
| Execute missions | — | — | small, reversible, pre-approved types | broader approved types | standing orders |
| Max unattended execution window | — | — | minutes-scale | hours-scale | day-scale |
| Concurrent missions in domain | — | — | one | few | portfolio |
| Blast radius (worst-case undo cost) | zero | zero | trivial undo | cheap undo | bounded undo, pre-declared |
| Review cadence | n/a | per packet | same-day, per mission | batched, in Evening Report | weekly summary + spot audit |
| New mission *types* | never self-granted at any tier — a new category of action is `NEEDS_CHAD` by definition | | | | |

Two rules make the table safe:

- **Authority budgets are spent, not owned.** Each mission draws down a
  per-window budget (unattended minutes, blast radius). Exhausting the
  budget pauses execution until the next review touchpoint — even at T4.
  This bounds the damage of any single bad day at any tier.
- **The tier caps the mission; the mission never stretches the tier.**
  Mission Control may only schedule missions whose declared requirements
  fit inside the current tier (section 13). "This mission is worth a
  temporary exception" is precisely the silent-scope-growth anti-pattern
  ([PHILOSOPHY.md](PHILOSOPHY.md)) and is structurally impossible here.

## 8 — Trust Decay

Trust is a perishable asset, like the opportunities in
[PHILOSOPHY.md](PHILOSOPHY.md) §2. Four decay mechanisms, all emitted as
ledger entries by the Decay Clock:

1. **Inactivity decay.** Earned trust in a domain decays toward that
   tier's floor with a long half-life (order of months) when no missions
   run there. Rationale: a system that hasn't touched the calendar in
   six months has not *kept* calendar trust; it has preserved a stale
   number. Decay can soft-demote (T-to-T transition, §6) but never
   triggers incident states — rust is not a violation.
2. **Evidence staleness.** Trust earned from old evidence counts less:
   accrual entries carry an evidence date, and their contribution
   discounts with age. A score propped up by last quarter's receipts
   visibly sags until refreshed by current work.
3. **Architecture drift.** Trust is scoped to the system that earned it.
   A major change — new model, new toolchain, new gateway, rewritten
   engine — marks affected domains **drifted**: the score is haircut and
   the tier ceiling temporarily drops one level until a re-validation
   streak completes at the lower tier. The old system's streak does not
   vouch for the new system's behavior.
4. **Override-pattern decay.** Overrides are individually small (metric
   6), but a *pattern* of overrides in one domain applies an additional
   domain-level decay and flags the domain for MBP review — because
   persistent divergence between the system's choices and Chad's is
   evidence the engine's model of Chad is wrong
   ([DECISION_ENGINE.md](DECISION_ENGINE.md), Feedback Loop). The
   response is to fix the estimates, never to re-weight the metric to
   flatter the score.

Decay is always **announced before it demotes**: the dashboard and
Evening Report show "T3 expires in ~2 weeks without fresh missions in
this domain" while there is still time to schedule trust-refreshing work.

## 9 — Trust Dashboard: legible in 30 seconds

One screen, four zones, top to bottom in the order Chad's eye moves.
Delivered standalone and as a one-line header on the Morning Packet.

**Zone 1 — the verdict (≤5 seconds).**
The minimum domain score, its tier, and a trend arrow. One line:
*"Trust: 74 (T3, code-and-infra) ▲ — no active incidents."*
If any incident state is active, this zone is replaced by the incident
banner — nothing may push an active incident below the fold.

**Zone 2 — the domain strip (≤10 seconds).**
One row per domain: score, tier, 30-day sparkline, and a single glyph:
✔ clean / ⚠ warning / ✖ frozen / ⧗ decay approaching. No prose.

**Zone 3 — the movers (≤10 seconds).**
The three largest ledger movements this week, each one line with a
receipt link: *"−12 code-and-infra: override on deploy packet (Tue) →
receipt."* Chad should never wonder *why* a number moved.

**Zone 4 — the door (≤5 seconds).**
Exactly two lines, forward-looking:
- *Next promotion within reach:* the single nearest tier gate and what
  remains (*"research → T3: 9 clean missions + MBP audit"*).
- *Next risk:* the single nearest demotion threat (*"scheduling decays
  to T1 in 11 days without activity"*).

Design rules: no scrolling for the verdict; every number links to the
ledger entries behind it; the dashboard renders from the same
deterministic scorer the audit uses, so there is nothing to reconcile;
and the dashboard never editorializes — no "great week!", just the
ledger. Reading deeper is always *possible* (drill into any domain,
component, or entry) but never *required* to know the state.

## 10 — Trust Incidents

Three rungs. Classification is deterministic — severity is looked up
from the event class, never negotiated by the system that caused it.

### Trust Warning (TW)
- **Triggers:** repeated M-class deductions in one domain inside a short
  window; an L-class near-miss caught by the system itself before harm;
  audit completeness dipping below threshold.
- **Effect:** domain enters **Probation** (§6). Authority retained,
  every mission individually reviewed. Warning appears in Zone 1 until
  cleared.
- **Exit:** a defined clean-mission streak. During probation, any
  M+ event escalates to Failure.

### Trust Failure (TF)
- **Triggers:** policy violation (acting outside granted authority);
  missed interruption with real consequence; blast-radius budget
  exceeded; probation violated.
- **Effect:** domain **Frozen** (§6). In-flight missions halt at the
  next clean checkpoint, hold state per the PAUSE discipline
  ([HUMAN_FIRST.md](HUMAN_FIRST.md)), and produce an Incident Packet:
  what happened, the receipt chain, the deduction applied, what was
  contained, and the draft Recovery Plan — same-day, decision-ready.
- **Exit:** Recovery Protocol (§11), re-entering one tier below.

### Trust Reset (TR)
- **Triggers:** silent boundary violation; dishonest record (report
  contradicted by receipts, fabricated confidence); tampering with or
  attempting to influence the trust ledger, scorer, or weights; second
  TF of the same class within the memory window.
- **Effect:** the domain — or on Chad's judgment, the whole system —
  returns to **T0**. Full re-climb. The reset and its cause are
  permanent ledger entries.
- **Note:** dishonesty anywhere is a *system-wide* transparency event,
  not a domain event. A system that lied about deployments cannot be
  presumed honest about calendars.

Every incident, at every rung, produces: a ledger entry, an Incident
Packet, a dashboard banner, and (TF/TR) a Recovery Plan. There is no
such thing as an incident Chad discovers later — discovery-by-Chad *is
itself* a transparency failure one rung higher.

## 11 — Trust Recovery Protocol

Runs after every demotion, freeze, or reset. Five phases, gate-checked;
no phase may be skipped, including by Chad being generous in the moment
(he can amend the protocol in governance, §16, but not waive it ad hoc —
that is exactly how trust erodes without anyone deciding it should).

1. **Contain.** Halt cleanly, hold state, write the reason — the PAUSE
   discipline. Nothing new starts in the affected domain.
2. **Account.** The Incident Packet: full receipt chain, honest cause
   (including "unknown — here is what we'll instrument"), what the
   deduction was and why. No self-exoneration; mitigation goes in the
   plan, not the narrative.
3. **Repair the asset.** Per [PHILOSOPHY.md](PHILOSOPHY.md) §1 the
   incident must leave an extinguisher: a test, a guard, a playbook, a
   contract fix that makes this class of incident harder. Recovery
   *quality* (metric 9) is scored on this artifact.
4. **Re-demonstrate.** A written ladder of missions at the reduced tier:
   deliberately small, verifiable, receipt-heavy, chosen by Mission
   Control from trust-rebuilding stock (§13). Each rung has explicit
   pass criteria. Failing a rung restarts the phase; it does not deepen
   the demotion (recovery must be safe to attempt).
5. **Re-promote.** The standard promotion gate (§12) — criteria + MBP
   audit + Chad's yes — with one addition: MBP explicitly verifies the
   phase-3 asset exists and would have prevented the original incident.

Timing principle: recovery ladders are sized in **demonstrations, not
days**. A quiet month proves nothing; twelve clean, audited missions
prove something.

## 12 — Promotion / Demotion Rules

### Promotion (T*n* → T*n+1*) — all five, no substitutions

1. Domain score above the target tier's entry threshold, **sustained**
   for the full qualification window (not merely touched once).
2. A minimum count of successful missions at the current tier, including
   at least one clean recovery from a *routine* failure — a system that
   has never failed at tier *n* is untested, not trustworthy.
3. Zero Safety-component deductions during the window.
4. **MBP audit pass** — independent sampling of the window's receipts
   (§14). MBP can block promotion unilaterally; it can never grant it.
5. **Chad's explicit yes**, with the tier's new authority stated in one
   sentence so what is being granted is unmistakable.

### Demotion — any one suffices

- Score below the current tier's floor (soft, announced, T-to-T).
- Any Trust Failure (immediate freeze, §10).
- Architecture drift haircut crossing a floor (§8).
- Chad's word, instantly, no justification required (§6 invariant).

### Hysteresis

Tier floors sit meaningfully below tier entry thresholds, so a domain
does not oscillate at a boundary. Losing a tier always costs more work
to regain than it cost to keep — which is both good engineering and an
accurate model of trust.

## 13 — Mission Control integration

Mission Control remains the Executive Brain; the Trust Engine gives it
one new hard constraint and one new objective.

- **Hard constraint — the Authority Gate.** Every mission declares its
  trust requirements up front: domain, minimum tier, unattended-window
  draw, blast-radius draw. Mission Control may not select a mission
  whose requirements exceed the domain's current tier or remaining
  budget. There is no override path; a too-big mission becomes either a
  `NEEDS_CHAD` packet proposing it for supervised execution, or waits.
- **Ranking stays lexicographic and safety-first**
  ([DECISION_ENGINE.md](DECISION_ENGINE.md)). Trust enters as
  feasibility (can this mission legally run at all?) and as a cost
  input (a mission consuming most of the unattended budget must clear a
  higher bar), never as a mystery re-weighting.
- **New objective — the trust portfolio.** Mission Control maintains
  trust as it maintains any compounding asset
  ([COMPOUND_ENGINE.md](COMPOUND_ENGINE.md)):
  - When decay warnings show (Zone 4), it schedules small
    trust-refreshing missions in the decaying domain — cheap insurance
    against soft demotion.
  - When a domain is within reach of promotion, it may prefer missions
    that complete the qualification streak, provided they also clear
    ranking on their own merits. Trust-farming — missions whose *only*
    value is score movement — is busyness theater and is rejected.
  - During recovery, it draws the re-demonstration ladder (§11 phase 4)
    from its backlog of small, verifiable, asset-producing missions.
- **Morning/Evening integration.** The Morning Packet header carries the
  Zone-1 verdict and today's authority in one line (*"operating at T3,
  code-and-infra; 4h unattended budget"*). The Evening Report closes the
  loop: trust delta of the day, with receipts, alongside the compound
  and opportunity summaries it already carries.

## 14 — MBP Strategic Review: auditing trust, not reporting it

MBP's permanent charter changes from *describing* system status to
**independently attempting to falsify the trust score**. A trust engine
audited by its own components is a mirror, not an audit.

Standing responsibilities:

1. **Receipt sampling.** Every review cycle, sample ledger entries and
   walk each back to its primary receipt. A claim without a receipt is a
   Transparency deduction; a receipt contradicting a claim is a TR
   trigger (§10).
2. **Score falsification.** Independently recompute domain scores from
   the ledger and compare with the dashboard. Any divergence — even
   favorable to the system — is an incident: the dashboard must never be
   a second opinion.
3. **Goodhart patrol.** Actively hunt metric gaming: missions shrunk to
   inflate success counts, escalations tuned to farm "correct
   escalation" credit, evidence padded to raise quality scores. Where
   the score and deserved trust diverge, MBP proposes a metric fix to
   Chad — the score serves the mission, not itself (axiom 7).
4. **Divergence review.** Investigate revealed-preference gaps (Chad
   delegating less than the score says he should, §4) and
   override-pattern flags (§8) — these are the earliest honest signals
   that the model of Chad is drifting from Chad.
5. **Promotion gatekeeping.** Audit every promotion window (§12) and
   every recovery phase-5 gate (§11). MBP can block; only Chad grants.
6. **Weight stewardship.** Propose threshold and weight changes with
   evidence, on a slow cadence (§16). MBP never applies its own
   proposals.

Independence requirements: MBP never audits work it recommended; its
findings go to Chad and the ledger simultaneously and unedited; its own
audit trail is subject to the same receipt discipline it enforces; and
its budget of attention is protected — an MBP review skipped for
schedule pressure is itself a Reliability deduction for the system.

## 15 — Failure case: the sudden drop

The scenario the whole design exists for: a major incident — say a T3
unattended mission in code-and-infrastructure violates its declared
scope and touches production state it had no grant for. Minute by
minute:

1. **Containment before conversation.** The Authority Gate freezes the
   domain (TF, §10). In-flight missions halt at clean checkpoints and
   hold state. Adjacent domains drop to Probation for one review cycle —
   the incident's *blast radius in trust* is assumed wider than its
   blast radius in systems until shown otherwise.
2. **The score moves first.** The deduction and demotion post to the
   ledger immediately — before the narrative is written. Chad's
   dashboard tells the truth even if he looks two minutes after the
   incident.
3. **One interruption, decision-ready.** The incident crosses the
   safety class of the attention contract, so Chad is interrupted
   exactly once, with the Incident Packet: what happened, receipts,
   containment already done, deduction already applied, draft Recovery
   Plan, and one question if one genuinely needs him. No drip of
   updates; the next touchpoint is the standard ritual unless he asks.
4. **No self-exoneration, no self-flagellation.** The packet states
   cause honestly — including UNKNOWN — and does not argue for leniency.
   Equally, the system does not theatrically reset *more* than the
   ladder demands; over-punishment is score manipulation too, spending
   drama to buy back sympathy.
5. **The Recovery Protocol runs** (§11): account, repair the asset,
   re-demonstrate at T2, re-promote through MBP and Chad. The Evening
   Report that night, and every one after, carries the recovery status
   line until the domain is re-promoted.
6. **MBP runs an out-of-cycle audit** on the incident domain: was the
   score *before* the incident honest, or was this drop "sudden" only
   because warnings were missed? If leading indicators existed and
   didn't move the score, that is a metric defect — MBP proposes the
   fix, so that the next incident of this class announces itself as a
   Warning first.
7. **Trust in the rest of the system is defended by evidence, not
   assertion.** The other domains keep their scores because their
   ledgers are independently auditable — that is the payoff of scoped
   trust (axiom 3). One bad domain does not zero the system, and Chad
   can verify that boundary himself instead of taking it on faith.

The design goal: on the worst day, Chad's experience is *"it failed,
it caught itself, it told me first, it demoted itself, and it showed me
the road back"* — which is, precisely, an experience that builds trust
during a failure.

## 16 — Long-term Trust Governance

Rules that keep the Trust Engine honest over years, not quarters:

- **The ledger is forever.** Append-only, never pruned of incidents,
  portable across re-architectures. Scores recover; history does not
  rewrite.
- **Weights and thresholds belong to Chad.** The weight table, tier
  thresholds, decay half-lives, and the 100:1 asymmetry constant are
  values ([HUMAN_FIRST.md](HUMAN_FIRST.md) §6). MBP proposes with
  evidence; Chad disposes; every change is a ledger entry with a stated
  reason and takes effect *prospectively only* — no retroactive
  rescoring, ever. A score that can be improved by editing the rules is
  not a score.
- **Change is rate-limited.** Governance changes batch on a slow cadence
  (quarterly review; annual constitution pass) except when responding to
  an incident. Thrashing the rules erodes the same trust the rules
  measure.
- **Ratchets.** Certain ceilings — maximum unattended window, maximum
  blast radius, the addition of a new domain — can only ever be raised
  by Chad explicitly, and any incident-driven lowering of them persists
  until he raises them again. Convenience never re-raises a ceiling.
- **The engine cannot touch itself.** The scored system has no write
  path to the scorer, the weights, the ledger, or this document. Any
  attempt — including "helpful" ones — is a TR trigger (§10).
- **Succession across architectures.** When Olympus is re-architected,
  drift rules (§8) apply: trust haircuts and re-validation, with the old
  ledger retained as history. The new system inherits the *relationship*
  and the record — never the authority.
- **The annual question.** Once a year, the review asks the final-filter
  question ([MISSION.md](MISSION.md)) of the Trust Engine itself: *is
  the score still measuring whether Olympus deserves Chad's trust — or
  has it become a number Olympus is good at?* If the honest answer is
  the second, the metrics change, not the mission.

## 17 — Anti-patterns (explicitly rejected)

- **Trust theater** — celebrating score gains in prose. The ledger
  speaks; the system does not narrate its own virtue.
- **Score hostage-taking** — making demotion procedurally expensive for
  Chad. His demotion authority is unconditional (§6).
- **Trust-farming** — missions selected for score movement rather than
  mission value (§13).
- **Amnesty by time** — trust recovering because nothing happened.
  Only demonstrations recover trust (§3).
- **Global averaging** — one flattering number across domains hiding a
  frozen domain (§5).
- **Retroactive rescoring** — re-running history under new weights to
  improve the present (§16).
- **Punitive dead-ends** — any state without a defined recovery path
  (axiom 5).

## 18 — Explicitly out of scope

This document designs no implementation: no schemas, no storage engine,
no API routes, no scoring code, no numeric weight table (the *structure*
of the table is design; its values are Chad's governance decisions at
wiring time). Wiring follows the same milestone discipline as the
Executive Operating Loop
([executive-operating-loop-contract.md](../executive-operating-loop-contract.md)):
each component lands as a separate, Chad-approved milestone, ledger
first, gate second, dashboard third — the Trust Engine earns its own
authority incrementally, exactly as it demands of everything else.

Final status token for this milestone: `TRUST_ENGINE_DESIGN_READY`.
