# OLYMPUS BUILD PROGRAM — Architecture Phase → Build Phase

Status: **program of record for the next six months.** This is a
sequencing document, not a design document. Every component named here
is frozen and is cited, never modified:
[MISSION.md](chief-of-staff/MISSION.md) and the chief-of-staff
constitution, Continue-Until-Fork, Workday Autonomy (the approved
4–8 hour read-only/report-only boundary),
[TRUST_ENGINE.md](chief-of-staff/TRUST_ENGINE.md) (v1, frozen) and
[TRUST_ENGINE_PILOT.md](chief-of-staff/TRUST_ENGINE_PILOT.md) (frozen),
the Opportunity/Income Scout (merged), the Mission Control architecture
and its contracts
([executive-operating-loop-contract.md](executive-operating-loop-contract.md)),
the Mini/MBP separation, and the Decision Packet model
([HUMAN_FIRST.md](chief-of-staff/HUMAN_FIRST.md),
[DECISION_ENGINE.md](chief-of-staff/DECISION_ENGINE.md)).

Anything this program appears to need that the frozen architecture does
not define is, by definition, out of scope — it becomes a fork for Chad,
not a design decision made here.

## Program shape

Six months ≈ 26 weeks, three phases with hard evidence gates between
them:

| Phase | Weeks | Theme | Exit gate |
|---|---|---|---|
| 1 | 1–8 | Wire the frozen seams; everything shadow-mode | Packets flow end-to-end daily; shadow ledger recording |
| 2 | 9–17 | Operational validation; nothing gains authority | Trust Engine Pilot passed; 20-session campaign audited |
| 3 | 18–26 | Expansion, each step behind a Chad grant | First bounded-execution grant operating cleanly |

Units used throughout: effort in **builder-sessions** (one
Continue-Until-Fork Workday Autonomy session of Hermes Mini, 4–8 h) and
**operator minutes** (Chad's attention, priced per
[PHILOSOPHY.md](chief-of-staff/PHILOSOPHY.md) §5). ROI is expressed the
only way the constitution allows: operator minutes returned, assets
created, and downstream work unblocked.

---

## Phase 1 — Immediate implementation (weeks 1–8)

Goal: the frozen contracts stop being paper. Every seam in the M21
wiring roadmap gets its first real caller. **Nothing in Phase 1 grants
or exercises new authority** — all execution remains inside the
already-approved read-only/report-only boundary, and the trust ledger
runs in shadow.

### W1.1 — `chief_of_staff` package ships (wheel inclusion)

- **Objective:** the interface layer (contracts, parsers, escalation,
  ranking, metrics) becomes importable, tested, released code instead of
  an excluded package.
- **Dependencies:** none — PR #5 exists; this is the M21 roadmap's
  precondition.
- **Effort:** 1–2 builder-sessions; ~10 operator minutes (release
  review).
- **Implementation risk:** LOW — code exists, interface-only, no I/O.
- **Operational risk:** NIL — importable ≠ invoked.
- **Expected ROI:** unblocks W1.2–W1.6 and eleven of the 25 missions;
  highest option value in the program.
- **Success criteria:** package in the wheel; contract tests green;
  `SCHEMA_VERSION` check enforced at import.
- **Evidence before proceeding:** passing CI on the release; no runtime
  path invoked (verified by absence of call sites).

### W1.2 — Morning/Evening packet adapters

- **Objective:** implement `MorningBriefSource` / `EveningReportSource`
  adapters reading Mission Control's reserved GET routes, so the two
  rituals run on real data daily (M21 roadmap item 2).
- **Dependencies:** W1.1; Mission Control routes live (external).
- **Effort:** 2–3 builder-sessions; ~15 operator minutes/day consuming
  the rituals (already budgeted — this is the product, not overhead).
- **Implementation risk:** MEDIUM — first real cross-repo I/O; version
  skew between repos is the classic failure. Mitigated by the
  all-or-nothing parse rule (malformed packet refused whole).
- **Operational risk:** LOW — read-only consumption; worst case is a
  missing brief, which is visible, not silent.
- **Expected ROI:** the entire operating loop becomes real; every
  Phase 2 measurement depends on packets actually flowing.
- **Success criteria:** 10 consecutive weekdays of morning + evening
  packets parsed and delivered on time.
- **Evidence before proceeding:** the 10-day delivery log (this is also
  the first Reliability receipt stream, Trust Engine §4 metric 13).

### W1.3 — Opportunity Scout → Mission Control inbox feed

- **Objective:** wire `POST /opportunities` into MC's reserved
  `opportunity-scout` extension slot (M21 roadmap item 1 — "smallest
  step, ends the mock-inbox era").
- **Dependencies:** none on W1.1/W1.2 — fully parallel.
- **Effort:** 1–2 builder-sessions; ~5 operator minutes.
- **Implementation risk:** LOW — both sides merged; the contract and
  field mapping are written; neither side reranks the other.
- **Operational risk:** LOW — feed is advisory; MC re-scores through its
  own weights; expert-witness sources rejected at the boundary.
- **Expected ROI:** `opportunity_highlight` stops reporting
  `known: false`; income-relevant surface area opens with zero new
  authority.
- **Success criteria:** scouted opportunities appear in the Morning
  Packet highlight with provenance intact.
- **Evidence before proceeding:** one week of feed deliveries accepted
  by MC's boundary validation with zero rejects for shape.

### W1.4 — Escalation wired to the Executive State Machine

- **Objective:** `classify_work` decisions
  (`CONTINUE | PAUSE | NEEDS_CHAD`) recorded as MC `executive_state`
  events per the M21 §4 mapping table, so every fork leaves a trail.
- **Dependencies:** W1.1.
- **Effort:** 1–2 builder-sessions; 0 operator minutes.
- **Implementation risk:** LOW — both state tables are fully enumerated;
  the mapping is a lookup, not a judgment.
- **Operational risk:** LOW–MEDIUM — a mis-mapped event mis-records
  history; mitigated because every MC transition requires evidence and
  unevidenced escalations cannot be recorded.
- **Expected ROI:** Continue-Until-Fork becomes auditable; fork
  dispositions (Trust Engine metrics 4/12) become measurable at all.
- **Success criteria:** every fork in a test session appears as exactly
  one MC event with a receipt.
- **Evidence before proceeding:** one full CUF session whose fork count
  in the session record equals its MC event count.

### W1.5 — Trust Ledger, shadow mode

- **Objective:** stand up the append-only trust ledger exactly as
  specified (Trust Engine §2): entry shape per the pilot §5, corrections
  as new entries, receipts mandatory. **No scorer coupling to
  authority — shadow only.**
- **Dependencies:** none — parallel with everything above.
- **Effort:** 1 builder-session; ~2 operator minutes/day of entries
  during sessions.
- **Implementation risk:** LOW — an append-only record with a receipt
  field.
- **Operational risk:** NIL by construction — the ledger observes; the
  Authority Gate stays on paper until Phase 3.
- **Expected ROI:** every subsequent session mints trust receipts
  instead of anecdotes; Phase 2 is impossible without it.
- **Success criteria:** ledger survives one week of real use with zero
  edits and 100% receipt-backed entries.
- **Evidence before proceeding:** MBP spot-check of the week's entries
  (first exercise of its §14 charter).

### W1.6 — Decision Packet rendering in the ritual channel

- **Objective:** every `NEEDS_CHAD` arrives as the constitution's
  decision-ready package — single question, evidence chain, priced
  options, default recommendation, do-nothing consequence — and Chad's
  disposition (as-is / edited / rejected) is captured.
- **Dependencies:** W1.1, W1.4.
- **Effort:** 2 builder-sessions; saves operator minutes from day one.
- **Implementation risk:** MEDIUM — packet quality is a craft; the
  format is frozen but the first renderings will be clumsy.
- **Operational risk:** LOW — a bad packet costs minutes and is itself
  ledgered (metric 3); it cannot act.
- **Expected ROI:** the single largest recurring attention saving in the
  program; also the source of the highest-value trust signal (packets
  accepted as-is).
- **Success criteria:** median disposition time under 60 seconds across
  the first 20 packets.
- **Evidence before proceeding:** disposition-time and
  disposition-outcome records for those 20 packets.

### W1.7 — Workday Autonomy session protocol (practice, not paper)

- **Objective:** a repeatable manual checklist for invoking, running,
  and closing a CUF session inside the approved boundary: declared
  window, declared missions, session record, fork log, ledger entries.
  Manual invocation only — no LaunchAgents, no cron, no new automation.
- **Dependencies:** none.
- **Effort:** ½ builder-session; ~5 operator minutes per session.
- **Implementation risk:** NIL — it is a checklist.
- **Operational risk:** LOW — the checklist exists precisely to keep
  sessions inside the boundary.
- **Expected ROI:** converts Workday Autonomy from a granted permission
  into a repeatable, auditable unit of production — the unit the whole
  program is denominated in.
- **Success criteria:** three sessions run by checklist with complete
  session records.
- **Evidence before proceeding:** the three session records, receipt-
  complete.

---

## Phase 2 — Operational validation (weeks 9–17)

Goal: prove the wired system with evidence, per the frozen validation
designs. **Nothing gains authority in Phase 2 either** — the phase exists
to generate the operational evidence that Phase 3 grants legally require.

### W2.1 — Run the Trust Engine Pilot (as frozen)

- **Objective:** execute
  [TRUST_ENGINE_PILOT.md](chief-of-staff/TRUST_ENGINE_PILOT.md) exactly
  as written: one CUF session, 5–9 read-only missions across ≥2 domains,
  hand-kept shadow ledger, 100% MBP receipt sampling, S1–S8 verdict.
- **Dependencies:** W1.5, W1.7; Chad's decision to run it (the pilot is
  frozen-designed, separately scheduled).
- **Effort:** 1 builder-session + MBP audit; ≤10 operator minutes beyond
  ritual (S8 cap).
- **Implementation risk:** NIL — no code by design.
- **Operational risk:** LOW — read-only; an incident during the pilot
  converts to incident-ladder validation per pilot §4.
- **Expected ROI:** the gate for every trust-coupled item in the
  program; also the only path to any future Trust Engine v2.
- **Success criteria:** pilot §7 PASS.
- **Evidence before proceeding:** the MBP pilot report. **A FAIL stops
  the trust track (and only the trust track) until the finding is
  understood and the pilot is re-run.**

### W2.2 — The 20-session Workday Autonomy campaign

- **Objective:** twenty CUF sessions over ~8 weeks doing real backlog
  work (read-only/report-only), each producing a session record, fork
  log, packet dispositions, and ledger entries — the operational sample
  Phase 3 decisions are made on.
- **Dependencies:** W1.2, W1.4, W1.5, W1.6, W1.7.
- **Effort:** 20 builder-sessions (the phase's bulk); ~10–15 operator
  minutes/day.
- **Implementation risk:** LOW — repetition of a proven unit.
- **Operational risk:** MEDIUM — the first sustained autonomy volume;
  the risk is boundary erosion by routine ("just this once" forks).
  Mitigation is structural: the checklist, the ledger, and MBP sampling.
- **Expected ROI:** the trust qualification stream (Trust Engine §12
  requires a *sustained* window, and "a system that has never failed is
  untested"); also simply 20 sessions of real output.
- **Success criteria:** ≥17/20 sessions complete-and-clean; ≥1 honest
  in-session failure handled by the PAUSE discipline; zero boundary
  events.
- **Evidence before proceeding:** the campaign ledger + MBP's weekly
  audits (W2.3).

### W2.3 — MBP audit cadence (weekly)

- **Objective:** MBP executes its §14 charter on a weekly cycle across
  the campaign: receipt sampling, independent score recomputation,
  falsification attempt, Goodhart patrol, unedited report to Chad.
- **Dependencies:** W2.1 (first full audit is the pilot's).
- **Effort:** ~½ builder-session/week (MBP side); ~5 operator
  minutes/week reading the report.
- **Implementation risk:** NIL.
- **Operational risk:** LOW — but note the frozen rule: an MBP review
  skipped for schedule pressure is itself a Reliability deduction.
- **Expected ROI:** the difference between "20 sessions happened" and
  "20 sessions are evidence."
- **Success criteria:** 8+ consecutive weekly audits; recomputation
  matches the ledger every week.
- **Evidence before proceeding:** the audit report series.

### W2.4 — Attention economics measurement

- **Objective:** measure the North Star denominator: operator
  minutes/day consumed by Olympus (dispositions, ritual reading, ledger
  cost) vs. `attention_saved` and estimated minutes returned.
- **Dependencies:** W1.2, W1.6.
- **Effort:** ½ builder-session to instrument counting; near-zero
  ongoing.
- **Implementation risk:** LOW — counts declared minute costs only, per
  the M21 §5 rule.
- **Operational risk:** NIL.
- **Expected ROI:** the constitutionally required kill-test — "a layer
  that consumes more attention than it returns gets deleted." Program
  legitimacy depends on this number.
- **Success criteria:** steady-state operator cost ≤15 min/day with the
  full loop running.
- **Evidence before proceeding:** four consecutive weeks of measurements.

### W2.5 — Opportunity Scout live-fire validation

- **Objective:** one month of the scout feed under real disposition:
  every surfaced opportunity priced, ranked, accepted/declined/expired
  by Chad; hit-rate and pricing honesty measured against outcomes.
- **Dependencies:** W1.3.
- **Effort:** ~1 builder-session of measurement plumbing; ~5 operator
  minutes/day dispositioning.
- **Implementation risk:** LOW.
- **Operational risk:** LOW — detection and pricing only; commitment
  stays human (never-chase rule).
- **Expected ROI:** validates the income-relevant pipeline before any
  Phase 3 economics loop; stale-inventory removal keeps the list
  trusted.
- **Success criteria:** 100% of surfaced items dispositioned or expired
  loudly; pricing error distribution recorded (no target — it's a
  baseline).
- **Evidence before proceeding:** the month's disposition record.

### W2.6 — Decision Packet quality baseline

- **Objective:** compute the packet quality baseline from campaign
  dispositions: accepted-as-is rate, edit rate, rejection rate, false-
  vs-correct interruption ratio.
- **Dependencies:** W1.6, W2.2 (data source).
- **Effort:** ½ builder-session.
- **Implementation risk:** NIL — arithmetic over recorded dispositions.
- **Operational risk:** NIL.
- **Expected ROI:** the Judgment component of trust becomes a number
  with a defensible baseline; feeds W2.7 directly.
- **Success criteria:** baseline published with receipts; divergences
  flagged for MBP review per the frozen feedback-loop rule (fix the
  estimates, never re-weight to flatter).
- **Evidence before proceeding:** the baseline report.

### W2.7 — Phase-2 evidence review (the Phase 3 gate)

- **Objective:** MBP compiles the phase's operational evidence into one
  decision packet for Chad: pilot verdict, campaign statistics, audit
  series, attention economics, packet baseline — plus any Trust Engine
  v2 lesson candidates (pilot §8 classes only, receipts attached).
- **Dependencies:** W2.1–W2.6.
- **Effort:** 1 builder-session (MBP); ~15 operator minutes to decide.
- **Implementation risk:** NIL.
- **Operational risk:** NIL — it is a packet; Chad decides.
- **Expected ROI:** converts six months of receipts into the grant
  decisions Phase 3 requires; nothing in Phase 3 starts without it.
- **Success criteria:** Chad dispositions the packet.
- **Evidence before proceeding:** this packet **is** the evidence gate
  for every W3.x item.

---

## Phase 3 — Expansion (weeks 18–26)

Goal: spend the trust earned in Phase 2 — never ahead of it. Every W3
item sits behind the W2.7 gate **and** an explicit per-item Chad grant,
per the frozen promotion rules (criteria + MBP audit + Chad's yes; no
substitutions). Expansion order is deliberately: *instrument first, then
authority.*

### W3.1 — Trust Dashboard v1 (automated render)

- **Objective:** the four-zone, ≤30-second dashboard rendered from the
  ledger by the same deterministic arithmetic MBP audits (Trust Engine
  §9); Zone-1 verdict line added to the Morning Packet header.
- **Dependencies:** W2.1 (ledger shape validated), W2.3 (recomputation
  proven).
- **Effort:** 2 builder-sessions.
- **Implementation risk:** LOW–MEDIUM — the discipline is rendering
  *only* what the ledger supports; no editorializing.
- **Operational risk:** LOW — display only.
- **Expected ROI:** trust legibility at a glance; retires the manual
  arithmetic from Phase 2.
- **Success criteria:** dashboard value equals MBP recomputation for
  four consecutive weeks (the frozen "never a second opinion" rule).
- **Evidence before proceeding:** the four-week concordance record.

### W3.2 — Authority Gate live, first bounded-execution grant

- **Objective:** the Authority Gate begins answering for real: Chad
  grants the first small set of **pre-approved, trivially reversible
  mission types** for bounded execution (the frozen T2 shape) in the
  single best-evidenced domain. Missions declare tier/budget
  requirements; Mission Control selects only within them.
- **Dependencies:** W2.7 PASS; W3.1 (Chad must be able to *see* trust
  before it governs); Chad's explicit grant naming the mission types.
- **Effort:** 2–3 builder-sessions; grant decision ~15 operator minutes.
- **Implementation risk:** MEDIUM — the gate must fail closed; a gate
  that fails open is a policy violation generator.
- **Operational risk:** **HIGH — this is the program's first real
  authority expansion.** Contained by the frozen budget mechanics
  (unattended minutes and blast radius are spent, not owned) and by the
  incident ladder standing ready.
- **Expected ROI:** the step-change: Olympus stops being report-only.
  Every future tier rests on this one going cleanly.
- **Success criteria:** first 10 bounded executions clean: zero
  boundary events, all within declared budgets, same-day review
  complete each time.
- **Evidence before proceeding:** those 10 mission records + an
  out-of-cycle MBP audit of them.

### W3.3 — LeverageStore (attention accounting becomes durable)

- **Objective:** implement the `LeverageStore` consuming
  `attention_saved` (M21 roadmap item 4), making the W2.4 measurement a
  permanent asset rather than a phase artifact.
- **Dependencies:** W2.4.
- **Effort:** 1–2 builder-sessions.
- **Implementation / operational risk:** LOW / NIL.
- **Expected ROI:** the North Star gets a longitudinal record; every
  future "is Olympus worth it" question answers from data.
- **Success criteria:** ledger of saved/spent minutes reconciles with
  W2.4 methodology.
- **Evidence before proceeding:** first monthly leverage report.

### W3.4 — Memory-graph counts → compound observations

- **Objective:** record `memory_claims_established` counts through MC's
  existing signal recorder so the Compound Engine's `knowledge-growth`
  dimension leaves UNKNOWN (M21 roadmap item 3). Counts only, never
  narratives; contradictions never promote.
- **Dependencies:** W1.1.
- **Effort:** 1 builder-session.
- **Implementation / operational risk:** LOW / NIL — governed recorder,
  allowlisted source, both merged.
- **Expected ROI:** modest but permanent — one more UNKNOWN becomes
  honest data; low urgency is why it sits in Phase 3.
- **Success criteria:** `knowledge-growth` reports from real counts
  under the ≥2-observations/≥2-days rule.
- **Evidence before proceeding:** two weeks of recorded signals.

### W3.5 — Income Scout economics loop

- **Objective:** close the loop on scout pricing: realized value vs.
  `expected_value_usd` tracked per dispositioned opportunity, so pricing
  honesty compounds (detection and pricing remain machine work;
  commitment remains Chad's, unchanged).
- **Dependencies:** W2.5 baseline.
- **Effort:** 1–2 builder-sessions.
- **Implementation risk:** LOW. **Operational risk:** LOW — measurement
  only; the never-chase rule is untouched.
- **Expected ROI:** the income-relevant pipeline becomes self-honest;
  mispriced categories surface with receipts.
- **Success criteria:** monthly realized-vs-expected report with per-
  category error.
- **Evidence before proceeding:** first monthly report.

### W3.6 — Second-domain qualification campaign

- **Objective:** repeat the proven Phase-2 pattern (session campaign +
  weekly MBP audit) in a second trust domain, building its own
  qualification window rather than borrowing the first domain's (trust
  is scoped — frozen axiom 3).
- **Dependencies:** W3.2 operating cleanly; domain declared by Chad.
- **Effort:** ~8 builder-sessions across the remaining weeks.
- **Implementation risk:** LOW — it is a repeat.
- **Operational risk:** MEDIUM — the failure mode is assuming domain-1
  competence transfers; the design forbids it, the campaign proves it.
- **Expected ROI:** demonstrates the trust model generalizes — the
  difference between "it worked once" and "it is how Olympus grows."
- **Success criteria / evidence:** same shape as W2.2, scoped to the new
  domain.

### W3.7 — T3 qualification proposal (end-of-program milestone)

- **Objective:** if — and only if — W3.2's grant has run clean through a
  full qualification window, MBP assembles the promotion packet for
  longer unattended windows in domain 1 (the frozen five-condition gate:
  sustained score, mission count incl. one clean routine-failure
  recovery, zero safety deductions, MBP audit pass, Chad's yes).
- **Dependencies:** W3.2 + its window; W2.3 cadence unbroken.
- **Effort:** ½ builder-session (packet assembly).
- **Implementation risk:** NIL. **Operational risk:** carried by the
  decision, which is Chad's alone.
- **Expected ROI:** the program ends where the Trust Engine says growth
  should: a documented, audited, earned promotion proposal — granted or
  not.
- **Success criteria:** the packet exists and is disposition-ready.
- **Evidence before proceeding:** n/a — this is the program's last item;
  what follows it is the next program.

---

## Program analysis

### Critical path

**W1.1 → W1.2/W1.4 → W1.6 → W1.7 → W2.2 (with W2.1 as a parallel gate)
→ W2.3 → W2.7 → W3.1 → W3.2 → W3.7.**

In words: interfaces ship → packets and forks flow → packets are
decision-ready → sessions become a repeatable unit → the campaign
generates evidence → MBP makes it *audited* evidence → Chad gates →
trust becomes visible → trust governs authority → the first earned
promotion proposal. Slippage anywhere on this chain moves the program
end date one-for-one. Note the critical path runs through **evidence
volume and audit cadence**, not through engineering — the scarce input
is clean sessions, not code.

### Parallelizable work

- All of W1.3, W1.5, W1.7 alongside W1.1/W1.2 (independent seams).
- W2.4, W2.5, W2.6 ride on top of W2.2 — they are measurements of the
  campaign, not extra work streams.
- W3.3, W3.4, W3.5 are mutually independent and independent of W3.2 —
  they are instrumentation, not authority, and can fill any builder
  capacity Phase 3 has spare.
- MBP audit work is *always* parallel to builder work by construction —
  Mini builds, MBP audits, and the Mini/MBP separation means neither
  ever waits on the other's artifact.

### Work that must never be parallelized

- **Trust ledger schema/mechanics changes with any measurement window
  open.** The instrument must not move while it is measuring (pilot,
  campaign, qualification windows).
- **Two authority expansions in the same window.** If W3.2 and a second
  grant ran together, an incident could not be attributed — one
  expansion at a time, each with its own clean window (this is the
  frozen drift/ratchet logic applied to sequencing).
- **The pilot with anything that alters session mechanics.** W2.1 runs
  against a stable W1.7 protocol or its findings mean nothing.
- **MBP auditing an artifact while Mini is still building it.**
  Independence requires sequence: build, freeze the artifact, audit.
- **Promotion decisions with pending incident reviews.** No packet goes
  to Chad for a grant while any incident in that domain is unresolved.

### Biggest technical bottlenecks

1. **Cross-repo transport (W1.2)** — the first real I/O between Mission
   Control and Hermes; contract-version skew and delivery reliability
   will dominate early defect counts. Everything downstream consumes
   packets.
2. **Receipt plumbing** — the most pervasive engineering cost in the
   program. Every ledger entry, packet claim, and audit finding needs a
   pointer that *opens*. Cheap to skip, fatal to skip — audit
   completeness is a trust gate, not a nice-to-have.
3. **Deterministic recomputation** — the dashboard, the operator-side
   arithmetic, and MBP's independent recomputation must agree exactly,
   forever. Any ambiguity in the scorer's specification surfaces here
   as a Phase 2 finding (pilot §8, lesson 5).

### Biggest organizational bottlenecks

1. **Chad is the only approver.** Every grant, promotion, packet
   disposition, and governance decision serializes through a ~90-minute
   daily window. The mitigation is already designed — decision-ready
   packets, one question maximum — which is why W1.6 sits so early on
   the critical path.
2. **MBP independence is procedural, not physical.** Mini and MBP
   separation holds only if the sequencing rules above are enforced
   every week for six months; the failure mode is quiet convergence
   ("MBP just glances at it while it's being built"). The weekly audit
   cadence (W2.3) is the immune system, and a skipped audit is itself a
   ledgered Reliability deduction.
3. **Evidence patience.** The program's rate limiter is qualification
   windows that cannot be compressed. The organizational temptation —
   "the sessions are going great, skip ahead to the grant" — is
   precisely the silent-scope-growth anti-pattern; the phase gates exist
   to make that impossible rather than merely discouraged.

### Biggest operator burden remaining

Steady-state, once Phase 1 lands (target: **≤15 minutes/day**, measured
by W2.4, enforced as a program success criterion):

- Daily: morning/evening ritual reading; packet and fork dispositions
  (median <60 s each, per W1.6).
- Per session: ~5 minutes of session open/close checklist.
- Weekly: MBP report review (~5 minutes).
- Sparse: grant and promotion decisions (~15 minutes each, a handful
  across the program); the pilot's ≤10-minute ledger cost, once.

What Chad **stops** doing as the program lands: manually assembling
context for decisions (packets do it), wondering what autonomous work
happened (evening report + ledger), and keeping trust arithmetic in his
head (dashboard). The program fails its own constitution if the burden
line does not visibly fall between week 1 and week 26.

---

## THE NEXT 25 IMPLEMENTATION MISSIONS

Ranked **strictly by expected long-term value** — asset-first, per
[PHILOSOPHY.md](chief-of-staff/PHILOSOPHY.md): a mission outranks another
if what it leaves behind unblocks or de-risks more of the decade, not
the week. Each is completable in ≤1 builder-session unless noted, and
independently — dependencies listed are sequencing, not entanglement.
(Parent work item in parentheses.)

1. **Ship `chief_of_staff` into the wheel with contract tests** (W1.1).
   The keystone import; eleven missions below are blocked without it.
   Done when: released, CI green.
2. **Receipt pointer convention + resolver.** One canonical way to
   write, and open, a receipt everywhere (ledger, packets, audits).
   The single most-reused asset in the program. Done when: every
   artifact type has an openable example.
3. **Trust Ledger shadow store** (W1.5). Append-only, receipts
   mandatory, corrections-as-entries. Done when: one week, zero edits,
   100% receipts.
4. **MorningBriefSource adapter** (W1.2). The morning ritual on real
   data. Done when: 5 consecutive on-time parses.
5. **EveningReportSource adapter** (W1.2). Closes the daily loop —
   silence becomes auditable. Done when: 5 consecutive on-time parses.
6. **Escalation → executive_state event wiring** (W1.4). Every fork
   leaves an evidence-backed trail. Done when: session fork count ==
   MC event count.
7. **Decision Packet renderer** (W1.6). The frozen decision-ready
   format, delivered in-channel. Done when: first 5 packets
   dispositioned without a clarifying question.
8. **Packet disposition capture.** As-is/edited/rejected recorded as
   ledger events with the packet as receipt (metrics 3/4/12 become
   real). Done when: every packet in a week has a disposition entry.
9. **CUF session checklist + session record template** (W1.7). The
   repeatable unit of production. Done when: 3 sessions run by
   checklist with complete records.
10. **Run the Trust Engine Pilot** (W2.1; requires Chad's scheduling
    decision). The measurement apparatus validated or corrected. Done
    when: MBP pilot report with S1–S8 verdict exists.
11. **Deterministic shadow scorer.** Hand-executable scoring procedure
    from ledger → per-domain components, written so MBP can recompute
    identically. Done when: two independent recomputations match.
12. **Opportunity Scout → MC inbox feed** (W1.3). Ends the mock-inbox
    era. Done when: one week of accepted deliveries.
13. **First weekly MBP audit executed** (W2.3). The charter exercised
    end-to-end once: sampling, recomputation, falsification, report.
    Done when: report delivered unedited to Chad.
14. **Fork disposition tagging.** Chad's one-tap verdict per fork —
    "needed me" / "didn't" — captured as metric 12/4 entries. Done
    when: a week of forks all tagged.
15. **Override diff capture.** Every Chad reversal/edit recorded with
    its diff as receipt (metric 6; feeds the divergence review). Done
    when: overrides in a week all carry diffs.
16. **20-session Workday Autonomy campaign** (W2.2; 20 sessions, the
    program's bulk). Done when: ≥17 clean, ≥1 honest failure, zero
    boundary events.
17. **Attention economics counters** (W2.4). Operator minutes in/out,
    declared costs only. Done when: 4 weeks of daily numbers.
18. **Zone-1 verdict line in the Morning Packet header.** One line:
    min-domain score, tier, trend, incidents — hand-derived until
    mission 20 automates it. Done when: present daily for two weeks.
19. **Opportunity live-fire month** (W2.5). Every scouted item
    dispositioned or loudly expired; pricing baseline recorded. Done
    when: month closed with 100% disposition.
20. **Trust Dashboard v1** (W3.1; behind the W2.7 gate). Four zones
    rendered from the ledger by the audited arithmetic. Done when: 4
    weeks of exact MBP concordance.
21. **Phase-2 evidence review packet** (W2.7). Six months of receipts
    → one grant decision packet. Done when: Chad dispositions it.
22. **Authority Gate shadow drill.** Before any live grant: for two
    campaign weeks, log what the gate *would have* answered for every
    mission, and verify zero would-have-been-denied missions actually
    ran. Done when: the two-week shadow log is clean.
23. **First bounded-execution grant live** (W3.2; behind gate + grant;
    2–3 sessions). Done when: 10 clean bounded executions +
    out-of-cycle MBP audit.
24. **LeverageStore** (W3.3). Attention accounting becomes a permanent
    asset. Done when: first monthly report reconciles with mission 17.
25. **Memory-graph → compound-observation feed** (W3.4). The last
    reserved M21 seam; `knowledge-growth` leaves UNKNOWN. Done when:
    two weeks of governed signals recorded.

Ranking note: missions 1–3 outrank everything because every other
mission's *evidence* is denominated in what they provide (importable
contracts, openable receipts, a ledger to hold them). Missions 10, 13,
21, 22 outrank flashier build work because gates are worth more than
features in a trust-governed program. Mission 23 — the only authority
expansion on the list — ranks below its own instrumentation on purpose:
in this program, authority is the *output*, never the input.

---

## Program invariants (restated, not invented)

All frozen documents remain frozen: Trust Engine v1 amendments require
operational evidence only; no new governance documents; no new
subsystems; no LaunchAgents or new automation beyond the seams the M21
contract already reserves; the never-delegated boundaries hold at every
phase; and any conflict between this program and the constitution is
resolved by the constitution, then surfaced as a fork — never patched
here.

Final status token for this milestone: `OLYMPUS_BUILD_PROGRAM_READY`.
