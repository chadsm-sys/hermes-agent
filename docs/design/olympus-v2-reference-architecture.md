# Olympus v2 — Reference Architecture

Status: **design only** (2026-07-07). No code, no implementation tasks.
Author role: Chief Systems Architect, redesigning from first principles.

> **Executive disposition (Chad, 2026-07-07): accepted as a research
> appendix — not the governing implementation baseline.** The Build
> Program remains authoritative. This branch is preserved as a strategic
> reference until v1 operational evidence exists. The only actionable
> takeaways carried into v1: consider D3 and R3 before wiring
> milestone 1, and R4 before wiring milestone 2. No Build Program
> reordering without evidence; no v1 architecture replacement; no v2
> implementation start.

This document answers one question:

> *"If you started over today, knowing everything you've learned from the
> current Olympus architecture, what would you build differently?"*

Constraints preserved from v1 (non-negotiable goals):

- Mission Control remains the orchestrator.
- Hermes Mini remains the primary builder.
- Hermes MBP remains independent strategic review.
- Continue-Until-Fork remains the operator interaction model.
- Expert Witness work remains isolated.
- Income Scout remains isolated.
- Chad only interacts at genuine decision forks.

---

## Part I — What v1 Taught Us

Olympus v1 is a doctrine-first system: seven constitutional documents
(`docs/chief-of-staff/`), a cross-repo integration contract
(`docs/executive-operating-loop-contract.md`), and two merged, governed,
deliberately isolated engines (`plugins/opportunity_scout/`, memorygraph).
The doctrine is excellent. The lessons are all structural:

**L1 — Integration debt is the real bottleneck.** The M21 contract opens
with "*contract only — nothing in this document is wired.*" Every seam in
the section-0 diagram is a bespoke point-to-point arrow that will, when
wired one milestone at a time, independently invent transport, auth,
retry, idempotency, and audit. Six arrows means six chances to get each of
those wrong, six test matrices, six drift surfaces.

**L2 — Continue-Until-Fork is implemented twice.** Hermes's
`chief_of_staff.escalation` (CONTINUE / PAUSE / NEEDS_CHAD) and Mission
Control's `executive_state.py` (10 states, 9 events) are two state
machines expressing one operator model, kept aligned by a hand-maintained
mapping table (contract §4). Alignment tables between independently
evolving state machines are where split-brain lives.

**L3 — Roles are welded to hardware.** "Mini" and "MBP" are machine names
doing role duty. Review independence currently rests on "it runs on a
different laptop." If the MBP is closed, traveling, or dead, strategic
review silently halts; nothing in the architecture notices. Hardware is a
deployment detail; independence is an authority property. v1 conflates
them.

**L4 — Isolation is enforced by blocklist.** Expert-witness isolation is
"forbidden markers rejected at every boundary" (contract §9.6). Marker
rejection is enumerative: it fails **open** on any marker nobody thought
to list, and every new boundary must re-implement the rejection. The most
legally sensitive data in the estate deserves fail-**closed** isolation.

**L5 — Governance is enforced by replication.** Evidence-or-silence,
bounded clamps, append-only audit trails, atomic writes, corrupt-file
recovery — memorygraph implements them, the scout store implements them,
MissionStore implements them. Three hand-rolled copies of the same
invariants, each a chance to diverge, each separately tested.

**L6 — Versioning is enforced by vigilance.** Schema compatibility is a
prose rule ("major must match; additive fields only in minors") spanning
two repos with paired PRs (mission-control-v0 #20 ↔ hermes-agent #8).
Nothing mechanical stops the repos from drifting; the process depends on
one person remembering the pairing.

**L7 — The scarcest resource has no ledger.** Attention is the declared
scarce resource (PHILOSOPHY §5), yet `attention_saved` sums *declared*
minute costs, the LeverageLedger is a "natural future consumer," and the
four interrupt classes are enforced by a classifier with no budget behind
it. Money gets an ROI model; attention gets adjectives.

**L8 — The isolated engines are the best code in the system.** The scout
(stdlib-only, deterministic, explicit `ALLOWED_TRANSITIONS`, everything
audited) and memorygraph (evidence-gated tiers, contradictions flagged)
prove the house style works. v2 should generalize *their* pattern, not
replace them.

---

## Part II — The Recommendations

Every v1 element receives exactly one verdict: **Keep**, **Replace**,
**Merge**, **Delete**, or **Delay** — each with why, expected benefit,
migration difficulty, and the risk of leaving it unchanged.

### KEEP

#### K1 — The doctrine corpus, as a constitutional layer
`MISSION.md`, `HUMAN_FIRST.md`, `PHILOSOPHY.md`, `DECISION_ENGINE.md`,
`BOTTLENECK_ENGINE.md`, `COMPOUND_ENGINE.md`, `EXECUTIVE_COACH.md`.

- **Why:** The doctrine is v1's genuine asset. It resolves design
  arguments before they start, and every good property of the merged
  engines traces back to it. v2 promotes it from "documents that win
  arguments" to the top tier of an explicit governance hierarchy
  (Part III, Governance Model).
- **Expected benefit:** Continuity of values across a full re-platform;
  the redesign changes mechanisms, never mission.
- **Migration difficulty:** None. The documents move unchanged; only
  their references to mechanisms are updated.
- **Risk if unchanged:** None — this is the element to protect.

#### K2 — Deterministic, model-free ranking and classification
Lexicographic ranking (safety → ROI → operator minutes → alignment →
confidence → id), model calls banned from ranking, escalation
classification, and status reporting.

- **Why:** "An assistant whose priorities change between identical
  mornings is not trustworthy" survived contact with reality. Both
  codebases already ban model calls here by test.
- **Expected benefit:** Trust, reproducibility, explainability — the
  properties the entire attention economy depends on.
- **Migration difficulty:** None; carried forward verbatim as a statute
  in the Fork Kernel and Decision Engine.
- **Risk if unchanged:** None.

#### K3 — The two rituals as the only scheduled human surfaces
Morning Plan (five questions, one recommendation, one bottleneck) and
Evening Report (close of books, compound ledger, opportunity summary).

- **Why:** The rituals are the correct shape for a ~90-minute attention
  window. What changes in v2 is their *implementation* — they become
  materialized views over the event ledger rather than hand-assembled
  packets — but their content contract, order, and cadence stay.
- **Expected benefit:** Zero retraining of the operator; the interface
  Chad already trusts survives the re-platform.
- **Migration difficulty:** Low — same fields, new derivation.
- **Risk if unchanged:** None.

#### K4 — All-or-nothing parsing and honest UNKNOWNs
Malformed packets refused whole (`MorningBriefError`); `UNKNOWN`,
`degraded`, and `contradicted` as first-class data.

- **Why:** "Evidence or silence" is the single most important invariant.
  A partially-trusted packet is a fabrication with extra steps.
- **Expected benefit:** Carried into the ledger: an event that fails
  schema validation is refused at append time, which is even earlier
  than v1 refuses it.
- **Migration difficulty:** None.
- **Risk if unchanged:** None.

#### K5 — The isolated-engine house style
Stdlib-only, no network, no scraping, explicit transition maps,
append-only audit events, atomic writes, clamped values (the Opportunity
Scout and memorygraph pattern).

- **Why:** These two engines are the proof that the doctrine compiles.
  Their *pattern* becomes v2's governed-store kernel (M2); the engines
  themselves keep their domain logic untouched.
- **Expected benefit:** v2 is a generalization of the best-tested code in
  the estate, not a rewrite of it.
- **Migration difficulty:** None for the engines; they gain a shared
  substrate underneath over time.
- **Risk if unchanged:** None.

### REPLACE

#### R1 — Point-to-point seams → the Olympus Ledger (single event spine)
Replace the six bespoke arrows of contract §0 (packet pushes, reserved
POST slots, evidence-feed recorder calls) with **one append-only,
hash-chained, schema-validated event ledger** that every component writes
to and reads from. Morning/Evening packets, opportunity inbox items,
compound observations, escalations, review verdicts — all become event
streams; the packets Chad sees become deterministic *views* over the
ledger.

- **Why:** L1. One spine means transport, auth, ordering, idempotency,
  retention, and audit are solved once. It also *is* the written trail
  HUMAN_FIRST demands — today the audit trail is assembled from N store
  files; in v2 the communication medium is the audit trail.
- **Expected benefit:** Every future seam costs one schema, not one
  integration. Replay gives free debugging and free Evening Reports
  ("what happened today" is a ledger query). Hash-chaining makes the
  trail tamper-evident, which matters for an estate touching legal work.
- **Migration difficulty:** **Medium.** The ledger can start as a
  hash-chained JSONL file on the Mini (Phase 0, Part III) — well within
  the house stdlib-only style. Existing stores are not migrated; they
  become per-partition projections. The M21 contract's payload shapes are
  reused verbatim as the first event schemas, so the design work already
  done is conserved.
- **Risk if unchanged:** Each wiring milestone (contract §11) ships a
  bespoke transport; by milestone 4 there are four transports to secure,
  monitor, and version independently. Integration debt compounds exactly
  like the technical debt the Compound Engine warns about.

#### R2 — Machine-bound roles → signed role contracts
Replace "Hermes Mini" and "Hermes MBP" as architectural identities with
three **role contracts** — ORCHESTRATOR, BUILDER, REVIEWER — each a
signed identity (key pair) plus an explicit capability set, *hosted by
default* on the machines that hold them today. Mission Control holds
ORCHESTRATOR; the Mini holds the BUILDER key; the MBP holds the REVIEWER
key. The preserved goals are honored by default binding, not by naming.

- **Why:** L3. Independence of review is an authority property (different
  key, different credential domain, no write access to work streams), not
  a hardware property. Binding roles to keys makes independence
  *verifiable* — every review verdict is signed by a key that provably
  cannot author builds — and makes the hardware replaceable.
- **Expected benefit:** The MBP dying no longer silently kills strategic
  review; the REVIEWER key moves to any trusted host and nothing else
  changes. Multi-machine scaling (Part III) becomes "mint another BUILDER
  key," not "buy another architecture."
- **Migration difficulty:** **Low.** Generate two key pairs, declare the
  capability sets in the contract registry, have each Hermes instance
  sign its ledger events. No behavior changes on day one.
- **Risk if unchanged:** A hardware failure or a machine upgrade becomes
  an unplanned architecture event. Review independence remains a
  convention that nothing enforces or audits.

#### R3 — Marker-based isolation → partition-based isolation (fail closed)
Replace "forbidden markers rejected at every boundary" with **data
partitions**: `ESTATE` (general), `EW-ENCLAVE` (Expert Witness), and
`SCOUT-CELL` (Income/Opportunity Scout). Every ledger event and every
store row carries a partition label from birth. Cross-partition flow is
**default-deny**; the only declassification authority is a Chad-signed
grant event. The Expert Witness enclave additionally gets its own store,
its own encryption keys, and — at Phase 3 — its own host.

- **Why:** L4. Blocklists fail open; partitions fail closed. Med-mal
  expert-witness material is the highest-liability data in the estate:
  confidentiality obligations to attorneys, discoverability concerns, and
  professional exposure. "We rejected the markers we thought of" is not a
  defensible posture; "that partition physically cannot reach Mission
  Control's inbox" is.
- **Expected benefit:** Isolation becomes a property you can demonstrate
  (label propagation + deny-by-default + audit of the zero crossings)
  rather than assert. The same mechanism isolates the Scout cell for
  free, preserving its "never fetches, never chased autonomously" nature.
- **Migration difficulty:** **Medium.** Labels are additive to event
  schemas; the enclave starts as a separately-keyed store on the same
  machine. The existing marker rejection stays during transition as
  defense in depth — it is demoted from load-bearing wall to tripwire.
- **Risk if unchanged:** One unlisted marker, one new boundary wired
  without the rejection check, and privileged legal material leaks into
  the general estate — the single worst outcome the system can produce,
  and one that no Evening Report can undo.

#### R4 — Prose versioning across paired PRs → a contract registry
Replace the two-repo, paired-PR schema discipline with a single
**contract registry**: one versioned artifact holding every event schema,
the fork calculus definition, role capability sets, and partition rules.
Both Mission Control and every Hermes instance pin a registry version and
perform a mechanical compatibility handshake (as a ledger event) at
startup. Mismatch → refuse to participate, loudly.

- **Why:** L6. `check_schema_version` is the right instinct implemented
  in the wrong place — per-consumer, per-payload, maintained in prose.
  Making the contracts a deployable artifact turns "neither side ever
  guesses at an unknown field" from a rule people follow into a property
  the system has.
- **Expected benefit:** Contract drift becomes a startup failure instead
  of a runtime mystery. The M21 document's payload tables become the
  registry's v1.0 content — again, prior design work conserved.
- **Migration difficulty:** **Low-Medium.** The `chief_of_staff`
  contracts package already exists interface-only; it becomes the
  registry seed. The main work is the handshake convention.
- **Risk if unchanged:** The first time the repos wire for real, minor
  version skew produces exactly the silent partial-trust failure the
  all-or-nothing rule was written to prevent — at the transport layer,
  below where that rule can see it.

### MERGE

#### M1 — Two state machines + attention router → the Fork Kernel
Merge Hermes's escalation classifier, Mission Control's
`executive_state.py`, and the four-class attention router into **one Fork
Kernel**: a single deterministic calculus with three work states —
`CONTINUE`, `HOLD` (v1 PAUSE), `FORK` (v1 NEEDS_CHAD) — the four
interrupt classes (`safety`, `judgment`, `missing-evidence`,
`explicit-approval`), the one-question rule, and the evidence-required
transition table. Defined once in the contract registry; the
authoritative instance runs in Mission Control; Hermes instances evaluate
the identical table locally for classification.

- **Why:** L2. Continue-Until-Fork is *one* operator model and deserves
  one implementation with one test suite. The §4 mapping table exists
  only because there are two machines to map between; merge them and the
  table — v1's most dangerous drift surface — ceases to exist.
- **Expected benefit:** A fork means the same thing everywhere. Safety
  properties (`ESCALATING` has no CONTINUE row; new action categories
  default to FORK) are stated once and inherited by every current and
  future role, including builders that don't exist yet.
- **Migration difficulty:** **Medium.** Both existing tables are already
  fully enumerated and deterministic — merging enumerated tables is
  tedious, not risky. The merged table must be proven to refuse
  everything both predecessors refused (a strictly-no-weaker check before
  cutover).
- **Risk if unchanged:** The two machines drift by one row and the system
  develops a state where Hermes believes it may continue and Mission
  Control believes Chad is deciding — a silent boundary violation, the
  exact failure HUMAN_FIRST prices as "costs more trust than a thousand
  correct escalations earn."

#### M2 — Three store implementations → one governed-store kernel
Merge the *mechanics* of memorygraph, the scout store, and MissionStore —
atomic writes, append-only audit events, schema-versioned documents,
corrupt-file quarantine, clamps, explicit transition maps — into one
governed-store kernel instantiated per partition. Domain logic (claim
tiers, opportunity lifecycle, mission state) stays exactly where it is.

- **Why:** L5. The three stores agree on philosophy and diverge only by
  accident of authorship. The mutation-boundary invariant ("neither ever
  writes the other's store") is preserved — partitions keep separate
  files and keys — while the *guarantees* stop being triplicated.
- **Expected benefit:** A hardening fix (like the memorygraph
  teardown-safe sweep, commit `154119b`) lands once and protects every
  store. New engines inherit governance instead of re-implementing it —
  the Compound Engine's "interfaces over integrations" applied to
  persistence.
- **Migration difficulty:** **Medium.** Extract-and-adopt, one store at a
  time, behind the existing test suites; the scout's tests already cover
  atomicity, corruption recovery, and thread safety, so they become the
  kernel's acceptance tests.
- **Risk if unchanged:** Store-guarantee drift: a bug fixed in one store
  survives in the other two, and the written trail — the thing silence's
  trustworthiness rests on — has three different failure modes.

#### M3 — Scattered attention accounting → the Attention Ledger
Merge the interrupt classifier, `attention_saved`, `waiting_for_you`,
`estimated_operator_minutes`, and the aspirational LeverageLedger into
one **Attention Ledger** stream on the Olympus Ledger: every fork raised,
question asked, packet published, and deferral chosen debits or credits a
single explicit budget derived from the ~90-minute window.

- **Why:** L7. The doctrine prices everything in operator minutes but the
  system never balances the books. If attention is the scarce resource,
  it needs what money already has: a ledger, a budget, and an auditor.
- **Expected benefit:** "A Chief of Staff layer that consumes more
  attention than it returns gets deleted" becomes measurable. The
  interrupt router can enforce against a real balance; the coach gets
  calibration data (estimated vs. actual minutes) for free.
- **Migration difficulty:** **Low.** It is one event schema plus a view;
  producers already declare minute estimates.
- **Risk if unchanged:** Attention spend stays self-reported and
  unverified, and the North Star metric — value per minute of attention —
  remains uncomputable. Question-spam drift becomes detectable only by
  Chad's irritation.

### DELETE

#### D1 — The reserved-slot / mock-inbox limbo
Delete the "reserved extension points, mock inbox, `known: false`
placeholder" pattern as a long-lived architectural state. In v2 a seam is
either **wired through the ledger behind a grant** or it **does not
appear in the architecture** — no third state where a slot exists,
carries no data, and must still be versioned, documented, and honestly
reported around.

- **Why:** Reserved slots were the honest v1 answer to "we designed the
  seam but can't wire it safely yet." The ledger removes the reason:
  wiring becomes cheap and uniformly governed, so seams no longer need
  waiting rooms. Placeholder states are inventory, and PHILOSOPHY already
  says inventory is a cost.
- **Expected benefit:** The architecture's map matches its territory.
  Every declared seam carries data; every honest UNKNOWN refers to
  missing *evidence*, not missing *plumbing*.
- **Migration difficulty:** **Trivial** — deletion happens naturally as
  each reserved slot is either wired (R1) or dropped.
- **Risk if unchanged:** Documentation and code accumulate permanently
  reserved slots that every new contributor must learn, version, and
  step around — negative compounding, per COMPOUND_ENGINE rule 3.

#### D2 — The wheel-exclusion packaging hack
Delete the "deliberately excluded from the wheel" mechanism for
`chief_of_staff` as a governance tool.

- **Why:** Packaging is the wrong enforcement layer for "not yet
  authorized to run." v2 expresses the same intent properly: code ships;
  *capability grants* decide what runs. An ungrated component on the
  ledger can do exactly nothing, which is stronger than being absent from
  a wheel (and unlike the wheel trick, it leaves an audit trail of the
  decision).
- **Expected benefit:** One fewer bespoke mechanism; activation decisions
  move into the same signed-grant system as every other authority.
- **Migration difficulty:** **Trivial**, once R2's capability grants
  exist.
- **Risk if unchanged:** Activation-by-packaging is invisible to audit,
  binary (no partial grants), and one `pyproject.toml` edit away from
  silent scope growth — the exact anti-pattern PHILOSOPHY names.

#### D3 — Dual opportunity scoring as an interchange concern
Delete composite-score interchange between the Scout and Mission Control.
The Scout keeps its composite *locally* (it is a fine triage tool); what
crosses the partition boundary is raw declared economics
(`expected_value_usd`, `chad_minutes`, `ai_minutes`, confidence,
provenance) — nothing else. Mission Control ranks with its own declared
weights, full stop.

- **Why:** v1 already ruled "neither side reranks the other," then let
  the composite travel anyway as "provenance, not input." A number that
  crosses a boundary *will* eventually be treated as input — by a future
  contributor, a future view, or a future model. The cleanest way to keep
  a rule is to make breaking it impossible.
- **Expected benefit:** One canonical ranking authority (the Decision
  Engine) with receipts that are entirely local, exactly as
  DECISION_ENGINE demands. The Scout's isolation gets simpler, not
  weaker.
- **Migration difficulty:** **Trivial** — narrow one payload schema
  before the seam is ever wired.
- **Risk if unchanged:** Slow-motion authority leak: two total orders
  over the same items, and the day they disagree visibly, trust in both
  is spent explaining which one was "real."

### DELAY

#### DL1 — Multi-machine and headless deployment (DGX, VPS, LaunchAgent, cloud)
- **Why delay:** Adding machines before roles are keys (R2) and the
  ledger is the spine (R1) multiplies exactly the machine-bound coupling
  v1 suffers from. The scaling path (Part III) makes multi-machine a
  *configuration* change once Phases 0–2 land.
- **Expected benefit of delaying:** Scaling lands on rails instead of
  creating a second bespoke topology to migrate later.
- **Migration difficulty when resumed:** Low, by design — mint keys,
  point at the ledger.
- **Risk of delaying:** Modest throughput ceiling in the interim; the
  Mini remains the only builder. Acceptable: the current bottleneck is
  integration, not build capacity.

#### DL2 — Memory-graph → Compound Engine wiring (knowledge-growth feed)
- **Why delay:** The v1 rule is right: growth claims need ≥2 observations
  on ≥2 days, and claim-quality baselines don't exist yet. Wiring a
  counter before the counted thing is trustworthy manufactures the
  dashboard-worship anti-pattern.
- **Expected benefit of delaying:** The first knowledge-growth numbers
  Chad sees are real.
- **Migration difficulty when resumed:** Trivial — one event schema on an
  existing spine.
- **Risk of delaying:** `knowledge-growth: UNKNOWN` persists in Evening
  Reports. That is honest, therefore acceptable.

#### DL3 — Model-assisted planning anywhere near ranking or escalation
- **Why delay (indefinitely, structurally):** K2 is doctrine. Model
  creativity stays welcome in drafting, research, and build work —
  and permanently banned from ranking, fork classification, and status
  reporting. v2 encodes the ban in the Fork Kernel's contract rather
  than in per-repo tests, making it a property new components inherit.
- **Expected benefit:** The trust properties survive every future model
  upgrade — including more capable models that will be more tempting to
  promote into judgment seats.
- **Migration difficulty:** N/A.
- **Risk of ignoring the delay:** Deterministic trust collapses to
  model-of-the-week behavior; identical mornings stop producing identical
  plans.

---

## Part III — Olympus v2 Reference Architecture

### 1. Component Diagram

```
                                 ┌─────────────────────────────────┐
                                 │              CHAD               │
                                 │   Executive · sole authority     │
                                 │   for money, sends, grants,      │
                                 │   declassification, values       │
                                 └─────▲──────────────┬────────────┘
                        Rituals (views)│              │ Fork Queue
                        Morning/Evening│              │ (decision-ready,
                                       │              │  signed answers)
┌──────────────────────────────────────┴──────────────▼─────────────────────┐
│                     MISSION CONTROL — ORCHESTRATOR role                    │
│                                                                            │
│   Planner · Bottleneck Engine · Decision Engine · Executive Coach          │
│   Compound Ledger · Attention Ledger (auditor)                             │
│   FORK KERNEL (authoritative instance)                                     │
│                                                                            │
│   Thinks, ranks, forks. Never executes. Writes: plan/, fork/, view/        │
└───────▲───────────────────────▲───────────────────────▲───────────────────┘
        │                       │                       │
        │ reads all ESTATE      │ appends/reads          │ reads verdicts
        │ streams               │                       │
┌───────┴───────────────────────┴───────────────────────┴───────────────────┐
│                     THE OLYMPUS LEDGER  (event spine)                      │
│      append-only · hash-chained · schema-validated · signed events         │
│                                                                            │
│   streams:  plan/  work/  fork/  evidence/  review/  attention/  grant/    │
│                                                                            │
│   partitions:   ESTATE        │   EW-ENCLAVE        │   SCOUT-CELL         │
│                 (general)     │   (expert witness,  │   (income scout,     │
│                               │    own keys/store,  │    no fetch, no      │
│                               │    default-deny)    │    autonomous chase) │
│                                                                            │
│   CONTRACT REGISTRY (pinned): event schemas · fork calculus ·              │
│                               role capability sets · partition rules       │
└───────▲───────────────────────────────────────────────▲───────────────────┘
        │ appends work/, evidence/                      │ appends review/
        │ reads plan/, grant/                           │ reads everything
        │                                               │ (read-only
        │                                               │  otherwise)
┌───────┴────────────────────────┐         ┌────────────┴───────────────────┐
│  BUILDER role — Hermes Mini    │         │  REVIEWER role — Hermes MBP    │
│  (default host)                │         │  (default host)                │
│                                │         │                                │
│  Execution runtime: skills,    │         │  Independent strategic review: │
│  cron, tools, drafts, builds.  │         │  audits plans, builds, forks,  │
│  Local Fork Kernel evaluation. │         │  and boundary compliance.      │
│  Acts. Never ranks, never      │         │  Separate key + credential     │
│  grants itself authority.      │         │  domain. Writes verdicts only. │
└────────────────────────────────┘         └────────────────────────────────┘
```

Reading the diagram: the Ledger is the only communication medium. No
component calls another component; every interaction is an event appended
to a stream, validated against the pinned contract registry, signed by a
role key, and labeled with a partition. Chad sits above the whole system
and touches it at exactly two surfaces: the rituals (read) and the fork
queue (decide).

### 2. Data Flow

Four canonical cycles, all expressed as ledger event sequences:

**Morning cycle.** Mission Control derives the Morning Plan as a
deterministic view over yesterday's `work/`, `evidence/`, `review/`, and
`attention/` streams plus the Scout cell's exported economics: today's
plan, one bottleneck, one executive recommendation, AI responsibilities,
and the honest operator-minutes price. The view is appended to `view/`
(so the packet itself is audited) and rendered to Chad. Deferred items
(`waiting_for_you`) ride the same view — they were `fork/` events the
Attention Ledger deferred as below-threshold.

**Work cycle (Continue-Until-Fork).** The Builder claims directives from
`plan/`, executes, and appends `work/` and `evidence/` events as it goes.
After each unit it evaluates the Fork Kernel table locally:
`CONTINUE` → next unit, silently (rolled up in the evening view).
`HOLD` → a `work/hold` event with reason and resume plan; surfaces in the
next ritual, never before.
`FORK` → a `fork/raised` event carrying the decision-ready package: one
question, the evidence chain, ranked options with honest prices, a
default, and the do-nothing consequence.

**Fork cycle.** Mission Control's authoritative Fork Kernel routes
`fork/raised` through the four interrupt classes against the Attention
Ledger's balance. Interrupt-worthy → Chad now; otherwise → deferred into
tomorrow's `waiting_for_you`. Chad's decision returns as a signed
`fork/resolved` event — which is also how new authority is born: a
resolution may mint a `grant/` event extending a role's capability set.
Authority is granted, never inferred; now it is also *recorded*, never
ambient.

**Evening cycle.** The Evening Report is a checkpoint view: plan versus
`work/` actuals, AI improvements and compound-ledger entries with
receipts, opportunity movement (economics only, per D3), attention books
balanced (estimated vs. actual minutes), and the Reviewer's verdicts.
The view closes with the day's ledger hash — the close of books is
literal.

**Cross-partition flow.** There is none by default. `EW-ENCLAVE` events
never join ESTATE views; the Scout cell exports only the narrow economics
schema. Any exception requires a Chad-signed `grant/declassify` event
naming the specific data and destination — and the grant itself is
visible in the evening view.

### 3. Authority Boundaries

Authority is layered, and capability is never an argument for authority
(HUMAN_FIRST, carried forward intact):

| Authority | Holder | Mechanism |
|---|---|---|
| Money, external sends, irreversible actions, credentials beyond granted scope, relationships, values | **Chad only** | No role capability set includes these; a fork is the only path |
| Minting/extending role capabilities; declassification across partitions | **Chad only** | Signed `grant/` events; grants are scoped, dated, auditable, revocable |
| Planning, ranking, fork routing, interrupt decisions | **ORCHESTRATOR** | Sole writer of `plan/`, `fork/` routing, and `view/`; cannot execute |
| Execution within granted capabilities | **BUILDER** | Sole writer of `work/`; cannot rank, cannot self-grant, cannot write `review/` |
| Audit and strategic verdicts | **REVIEWER** | Reads everything; sole writer of `review/`; writes nothing else — independence is enforced by key, not etiquette |
| Schema and calculus definitions | **Contract registry** | Version-pinned; mismatch refuses participation at handshake |

Three structural rules bind the layers:

1. **No role writes another role's streams.** The v1 mutation-boundary
   invariant, promoted from convention to signature check.
2. **No new category of action without a grant.** Undefined action →
   FORK by definition, exactly as v1's defaults-under-uncertainty rule —
   but now the *resolution* leaves a durable grant record.
3. **Partitions fail closed.** Absence of a grant means denial; there is
   no marker list to keep complete.

### 4. Mission Control Responsibilities (ORCHESTRATOR)

- Own the authoritative Fork Kernel instance: classify, route, defer, and
  escalate per the four interrupt classes and the one-question rule.
- Produce the Morning Plan and Evening Report as deterministic,
  ledger-audited views — the only scheduled surfaces Chad sees.
- Run the Bottleneck Engine (one constraint, evidence-backed, with the
  spine to repeat itself) and the Decision Engine (lexicographic ranking,
  one Executive Recommendation).
- Keep the Attention Ledger: budget the window, price every interrupt,
  balance the books nightly, and flag itself for deletion review if the
  books run negative.
- Run the Executive Coach against outcome evidence (decision review,
  calibration deltas, skill delta) — informing judgment, never replacing
  it.
- Maintain the Compound Ledger: assets created, reuse measured, decay
  flagged, deletions recorded as gains.
- **Never execute.** Mission Control thinks; the moment it acts, the
  authority model is void.

### 5. Mini Responsibilities (BUILDER — default host: Hermes Mini)

- Execute plan directives autonomously inside granted capabilities:
  builds, drafts, research, automation runs, scheduled jobs.
- Evaluate the Fork Kernel locally after every unit of work; classify
  honestly, escalate immediately and once on real boundaries, and never
  proceed "just a little" past one.
- Append `work/` and `evidence/` events with receipts as it goes — the
  written trail is produced by working, not reconstructed afterward.
- Hold state cleanly on HOLD: reason recorded, resume plan attached.
  A clean pause is good work, not failure.
- Produce assets alongside outcomes (second-fire rule): playbooks,
  skills, tests, contracts — and record them for the Compound Ledger.
- Respect partitions absolutely: Expert Witness tasks run in the enclave
  with enclave credentials; Scout-cell data is read via its export schema
  only.
- **Never rank its own priorities, never grade its own work, never expand
  its own scope.** Ranking is the Orchestrator's; grading is the
  Reviewer's; scope is Chad's.

### 6. MBP Responsibilities (REVIEWER — default host: Hermes MBP)

- Independent strategic review of the estate: are plans attacking the
  named bottleneck, are builds accumulating assets or inventory, are
  estimates calibrated against outcomes?
- Boundary audit: verify the period's zero cross-partition crossings,
  verify every capability exercised traces to a grant, verify fork
  packages were genuinely decision-ready (one question, evidence chain,
  honest prices).
- Adversarial review of significant builds and proposals *before* they
  reach Chad's fork queue — the governed-merge / audited-head practice,
  now an enforced role rather than a habit.
- Publish signed `review/` verdicts with evidence; a verdict without a
  receipt is inadmissible, same as any other claim.
- Feed the Evening Report's audit section and the Coach's calibration
  data.
- **Write nothing but verdicts.** The Reviewer that fixes what it reviews
  has stopped being independent; the key structure makes this physically
  true.

### 7. Governance Model

Four tiers, each subordinate to the one above:

1. **Constitution** — the doctrine corpus (K1), authored and amended only
   by Chad. Machines read it; no machine writes it. When any lower tier
   conflicts with it, the constitution wins.
2. **Statutes** — the contract registry: event schemas, the fork
   calculus, role capability sets, partition rules, the ranking contract.
   Versioned, pinned, machine-checked at handshake. Amendments are
   proposals that must pass Reviewer verdict and Chad grant.
3. **Mechanisms** — the ledger (append-only, hash-chained, signed), the
   governed-store kernel, partition labels, the Attention Ledger. These
   make the statutes physical: an invalid event cannot be appended, an
   ungranted capability cannot be exercised, a cross-partition read
   cannot happen quietly.
4. **Audit** — the Reviewer's verdicts, the Evening Report's close of
   books, the daily ledger hash. Everything above is periodically proven,
   not presumed.

Change control for autonomous authority (the anti-drift rule): silent
scope growth is impossible by construction, because the only way a role
gains a capability is `proposal → Reviewer verdict → Chad-signed grant →
capability minted → Attention/Compound ledgers monitor it`. Precedent
grants nothing; only grants grant.

The invariants of contract §9 survive verbatim, upgraded from rules to
properties: evidence or silence (schema-refused otherwise), determinism
over cleverness (Fork Kernel + ranking contract), mutation boundaries
(stream ownership by signature), attention economy (budgeted, audited),
never chase autonomously (Scout cell exports economics, holds no
execution capability), expert-witness isolation (fail-closed partition).

### 8. Operational Lifecycle

**Daily loop** (the operator's clock, unchanged in shape from v1):

1. **Morning** — Mission Control publishes the Morning Plan view; Chad
   spends minutes, not context switches: one bottleneck, one
   recommendation, deferred forks batched into `waiting_for_you`.
2. **Autonomous window** — the Builder runs Continue-Until-Fork all day;
   the Reviewer audits streams as they append; the Orchestrator routes
   any raised forks through the attention budget. Chad is interrupted
   only for the four classes, one question at a time.
3. **Evening** — close of books: plan vs. actuals, assets ledgered,
   attention balanced, verdicts attached, ledger hash sealed. Silence all
   day is trustworthy *because* the evening audit is complete.

**Component lifecycle** (how anything new enters Olympus):

`INCUBATE` (isolated, local-first, stdlib house style — exactly how the
Scout was built) → `GOVERN` (adopt the store kernel, declare event
schemas in the registry) → `WIRE` (grant-gated ledger participation; no
reserved slots — wired or absent) → `AUDIT` (Reviewer coverage, attention
and compound measurement) → `RETIRE` (deletion recorded as a compounding
gain when measured value fails claimed value).

**Failure lifecycle:** any component failing handshake, signature, or
schema validation is excluded from the ledger and the exclusion is itself
an event — degraded honestly, per K4. A dead Builder host means unclaimed
directives, visible in the evening view; a dead Reviewer host means
missing verdicts, equally visible. Nothing fails silently because
*participation* is what's audited.

### 9. Scaling Path — from today's two Macs to multi-machine

The path is designed so that each phase is independently valuable and no
phase requires undoing a previous one. The constant across all phases:
**capacity scales; authority does not.** Adding machines adds builders,
never deciders — there is always exactly one ORCHESTRATOR key, one
REVIEWER verdict stream, one Chad.

**Phase 0 — Contracts on rails (current hardware, current repos).**
Contract registry seeded from the M21 payload tables; Fork Kernel merged
from the two existing enumerated tables (strictly-no-weaker check); the
ledger begins as a hash-chained, schema-validated JSONL file on the Mini.
Role keys minted; events signed. Nothing moves machines; everything
gains provenance.

**Phase 1 — One spine (same two machines).**
Ledger service runs on the Mini; Mission Control and the Builder read and
append locally; the MBP tails a read-only replica and appends verdicts.
The M21 wiring roadmap's four milestones all land as event schemas on
this spine instead of four bespoke transports. The EW enclave gets its
own keys and store. Reserved slots are retired (D1).

**Phase 2 — Role mobility (still two machines, no longer *required* to be).**
Any role can run on any trusted host holding its key: the REVIEWER key
can move to a VPS while the MBP travels; a maintenance window on the Mini
no longer stops the estate. Multi-machine is now a configuration, not a
project. This is the phase gate that DL1 waits for.

**Phase 3 — Parallel build lanes (first real multi-machine).**
Additional BUILDER keys minted per Chad grant — a headless worker (DGX,
VPS, or a cloud box) claims directives via ledger leases (single-writer
per work stream; the claim is an event, so contention is impossible by
construction). The EW enclave optionally moves to dedicated hardware,
making its isolation physical. The Orchestrator's ranking is unchanged:
more lanes consume the same one ranked plan.

**Phase 4 — Elastic capacity (optional, likely unnecessary).**
Ephemeral builders spin up for burst work with short-lived, narrowly
scoped keys and are retired with their grants. The ledger remains the
single source of truth; the rituals remain two per day; Chad's surface
area does not grow by one pixel. If the Attention Ledger ever shows the
estate returning less attention than it costs at this scale, the correct
move is Phase retreat — and the Compound Ledger records the deletion as
a gain.

---

## Appendix — v1 → v2 Concept Map

| v1 | v2 | Verdict |
|---|---|---|
| Doctrine corpus (`docs/chief-of-staff/`) | Constitution tier | Keep (K1) |
| Lexicographic ranking; model-free judgment seats | Decision Engine statute + Fork Kernel ban | Keep (K2, DL3) |
| Morning Plan / Evening Report packets | Deterministic views over the ledger | Keep shape (K3), replace derivation (R1) |
| All-or-nothing parsing, honest UNKNOWN | Schema-refusal at append time | Keep (K4) |
| Scout + memorygraph house style | Governed-store kernel pattern | Keep (K5), merge mechanics (M2) |
| Six point-to-point seams (contract §0) | Olympus Ledger streams | Replace (R1) |
| "Hermes Mini" / "Hermes MBP" as identities | BUILDER / REVIEWER role keys, default-hosted on the same machines | Replace (R2) |
| Forbidden-marker rejection | Fail-closed partitions + Chad-signed declassification | Replace (R3); markers demoted to tripwire |
| Prose schema versioning, paired PRs | Contract registry + startup handshake | Replace (R4) |
| Escalation classifier + `executive_state.py` + §4 mapping table + attention router | Fork Kernel (one calculus) | Merge (M1) |
| Three store implementations | One governed-store kernel, per-partition instances | Merge (M2) |
| `attention_saved`, `waiting_for_you`, LeverageLedger (future) | Attention Ledger stream | Merge (M3) |
| Reserved slots / mock inbox / `known: false` plumbing | Wired-or-absent | Delete (D1) |
| Wheel-exclusion of `chief_of_staff` | Capability grants | Delete (D2) |
| Composite score crossing the Scout boundary | Economics-only export schema | Delete (D3) |
| DGX / LaunchAgent / desktop / cloud deployment | Phases 2–4 of the scaling path | Delay (DL1) |
| Memory-graph → knowledge-growth feed | Post-baseline event schema | Delay (DL2) |
| CONTINUE / PAUSE / NEEDS_CHAD | CONTINUE / HOLD / FORK — same operator model, one implementation | Keep semantics, merge mechanics (M1) |

**Design intent in one sentence:** v1 proved the doctrine; v2 gives the
doctrine a spine — one ledger, one fork calculus, roles as keys instead
of laptops, partitions that fail closed — so that every invariant Chad
currently trusts people to maintain becomes a property the system
physically has.
