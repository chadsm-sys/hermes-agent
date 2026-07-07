# OLYMPUS V2 ADOPTION MATRIX

Status: **research / compatibility assessment only** (2026-07-07).
Companion to `olympus-v2-reference-architecture.md` (same directory).

> **Executive disposition (Chad, 2026-07-07): accepted as a research
> appendix — not the governing implementation baseline.** The Build
> Program remains authoritative. Of this matrix, the only takeaways
> carried into v1 are the §8 ordering facts: consider D3 and R3 before
> wiring milestone 1, and R4 before wiring milestone 2. All
> EVIDENCE-FIRST items remain gated on the §7 checklist; nothing else
> is adopted, scheduled, or reprioritized by this acceptance.

This document classifies every **Replace**, **Merge**, **Delete**, and
**Delay** recommendation from the Olympus v2 proposal against the Olympus
v1 program as it actually stands: doctrine merged, Opportunity Scout and
memorygraph merged and isolated, `chief_of_staff` contracts interface-only
(PR #5, excluded from the wheel), the M21 executive-operating-loop
contract merged as **contract only — nothing wired**, and a four-milestone
wiring roadmap (M21 §11) not yet started.

Hard constraints honored throughout:

- **The Build Program is not modified.** No milestone is added, removed,
  or reordered by this document.
- **The Constitution is not modified.** All seven doctrine documents
  remain authoritative and untouched.
- **Implementation is not reprioritized.** Where a v2 item aligns with an
  existing v1 milestone, that is noted as *compatibility*, not as a
  schedule change. Where a v2 item would conflict with v1 ordering, the
  conflict is named and the item is gated, not the roadmap.
- **No implementation is proposed.** Effort figures are compatibility
  estimates for planning conversations, not tasks.

The v2 **Keep** items (K1–K5) are out of scope here by definition: they
carry v1 forward unchanged and have no adoption question.

---

## 1. Classification Scheme

| Class | Meaning |
|---|---|
| **ADOPT-IN-V1** | Compatible with the v1 program as designed. Can be folded into work v1 already plans (typically the M21 wiring milestones) without reordering anything, or costs nothing because it changes no behavior. |
| **EVIDENCE-FIRST** | Sound in principle, but adopting it before v1 has produced specific operational evidence would mean designing against speculation. The required evidence is named concretely so v1 operations can collect it as a side effect of normal running. |
| **WAIT-FOR-V2** | Correct only inside the v2 architecture. Adopting it during v1 would remove a mechanism v1 still needs or would force other v2 items in prematurely. |
| **REJECT** | Incompatible with the preserved goals, the Constitution, or the v1 program's integrity. (Bar defined in §6; zero items met it.) |

Effort scale: **trivial** (< 1 day) · **small** (days) · **moderate**
(1–2 weeks) · **high** (multi-week).

---

## 2. Summary Matrix

| # | Recommendation | Classification | Migration risk | Effort |
|---|---|---|---|---|
| R1 | Point-to-point seams → Olympus Ledger | **EVIDENCE-FIRST** (shadow ledger adoptable in v1) | Medium | High |
| R2 | Machine-bound roles → signed role contracts | **ADOPT-IN-V1** | Low | Small |
| R3 | Marker isolation → fail-closed partitions | **ADOPT-IN-V1** (labels + default-deny); enclave hardening staged | Low–Medium | Moderate |
| R4 | Prose versioning → contract registry | **ADOPT-IN-V1** | Low | Small–Moderate |
| M1 | Two state machines + router → Fork Kernel | **EVIDENCE-FIRST** (conformance harness adoptable in v1) | High | Moderate–High |
| M2 | Three stores → governed-store kernel | **EVIDENCE-FIRST** (second-fire trigger) | Medium | Moderate |
| M3 | Scattered attention accounting → Attention Ledger | **ADOPT-IN-V1** | Low | Small |
| D1 | Delete reserved-slot / mock-inbox limbo | **WAIT-FOR-V2** | Low (when due) | Trivial (when due) |
| D2 | Delete wheel-exclusion packaging hack | **ADOPT-IN-V1** (deletion); grant replacement is v2 | Low | Trivial |
| D3 | Delete composite-score interchange | **ADOPT-IN-V1** | Trivial | Trivial |
| DL1 | Delay multi-machine deployment | **ADOPT-IN-V1** (already v1 policy) | None | None |
| DL2 | Delay memory-graph → knowledge-growth claims | **EVIDENCE-FIRST** (for lifting UNKNOWN; wiring milestone unchanged) | Low | Trivial |
| DL3 | Model ban as structural property | **ADOPT-IN-V1** (ban already holds); kernel encoding follows M1 | None | Trivial |

Tally: 8 ADOPT-IN-V1 · 4 EVIDENCE-FIRST · 1 WAIT-FOR-V2 · 0 REJECT.

The shape of the tally is itself a finding: the v2 proposal is mostly a
*formalization* of properties v1 already holds by convention (hence eight
items foldable into v1 as designed), and its genuinely disruptive items —
the ledger, the kernel merge, the store unification — are exactly the
ones that must wait for operating data.

---

## 3. ADOPT-IN-V1 — compatible with the v1 program as designed

### R2 — Signed role contracts (ORCHESTRATOR / BUILDER / REVIEWER keys)

- **Rationale.** Purely additive: mint key pairs, declare capability sets
  in the existing `chief_of_staff` contracts package, have each instance
  sign its outputs. No behavior changes; Mini and MBP keep their roles by
  default binding, which is precisely how the preserved goals are stated.
  The "governed merge, audited head" practice already visible in v1
  history is this item's manual predecessor — R2 formalizes an existing
  habit rather than introducing a new one.
- **Operational evidence required.** None. The item does not depend on
  how v1 behaves under load; it records who did what, which is valuable
  from day one and *more* valuable the earlier it starts (provenance
  cannot be added retroactively).
- **Migration risk.** **Low.** Failure mode is a bad key ceremony or a
  lost key; both are recoverable by re-minting because nothing else
  depends on key continuity yet. No rollback complexity: unsigned
  operation is simply the status quo.
- **Estimated effort.** **Small.** Key generation, a capability-set
  declaration in the contracts package, and a signing convention.

### R3 — Partition labels + default-deny (Expert Witness, Scout cell)

- **Rationale.** The cheapest moment to add a partition label to a
  payload schema is *before the seam carrying it is wired* — and v1's
  wiring milestone 1 (Scout → Mission Control inbox) has not started.
  Adding `partition:` labels to the M21 payload shapes and stating the
  default-deny rule at the one existing boundary is schema work, not
  plumbing work. The existing forbidden-marker rejection stays exactly as
  is (per the v2 proposal itself: demoted to tripwire, not removed), so
  nothing v1 relies on is weakened during transition. Given that the
  EW-ENCLAVE protects the highest-liability data in the estate,
  fail-closed labeling is the one v2 item where waiting has asymmetric
  downside.
- **Operational evidence required.** None for labels and the deny rule.
  The *staged* parts — separate enclave keys, separate store, dedicated
  host — follow the v2 scaling phases and are out of v1 scope (consistent
  with M21 §10's out-of-scope rules; no reprioritization implied).
- **Migration risk.** **Low–Medium.** Labels are additive fields
  (minor-version change under v1's own versioning rule). The risk is
  mislabeling at origin; mitigated because today there are only three
  origins, all local, all governed. Marker rejection remains as backstop.
- **Estimated effort.** **Moderate.** Schema additions, label propagation
  through the two engines' serializers, and the deny check at the
  boundary that milestone 1 will wire anyway.

### R4 — Contract registry with mechanical handshake

- **Rationale.** v1 already made the hard decision (frozen consumer
  contracts, prose major/minor rules, `check_schema_version`); R4 moves
  those artifacts into one pinned, versioned package with a startup
  compatibility check. This is a *precondition-shaped* item: wiring
  milestone 2 (packet adapters + wheel inclusion) becomes strictly safer
  if the registry exists first, and nothing about the milestone's content
  or position changes. The M21 payload tables are the registry's seed
  content verbatim — the design work is already done and merged.
- **Operational evidence required.** None. Version-skew failure is a
  known class, not a hypothesis needing v1 data.
- **Migration risk.** **Low.** The registry starts as a re-homing of
  existing declarations. Worst case, the handshake is too strict and
  refuses a valid pairing — which fails loudly and safely, the direction
  v1 doctrine prefers.
- **Estimated effort.** **Small–Moderate.** Package the existing
  contracts + fork/escalation table declarations, add version pinning and
  the handshake convention. The cross-repo coordination (one paired PR to
  end paired PRs) is the real cost.

### M3 — Attention Ledger (unified attention accounting)

- **Rationale.** v1's wiring roadmap item 4 is already "LeverageStore
  implementation consuming `attention_saved`." M3 is that milestone's
  natural shape rather than a new commitment: one event schema recording
  forks raised, questions asked, deferrals chosen, and minutes
  estimated/actual, with the existing `attention_saved` and
  `waiting_for_you` fields as its first producers. Building LeverageStore
  as a standalone consumer and *then* unifying in v2 would build the same
  thing twice. This is compatibility alignment, not reprioritization:
  milestone 4 keeps its position and scope; only its internal data model
  is informed by M3.
- **Operational evidence required.** None to adopt the schema. (The
  *interesting* outputs — whether the layer returns more attention than
  it consumes — are evidence this item produces, which several
  EVIDENCE-FIRST items below consume.)
- **Migration risk.** **Low.** Additive accounting; producers already
  declare minute estimates per doctrine. No consumer depends on it yet.
- **Estimated effort.** **Small.** One schema plus aggregation into the
  Evening Report fields that already reserve space for it.

### D2 — Retire the wheel-exclusion packaging hack

- **Rationale.** v1's own roadmap already retires it: wiring milestone 2
  explicitly includes "wheel inclusion for `chief_of_staff`." The v2
  observation is only that packaging should never again be used as an
  authorization mechanism; in the interim before v2 grants exist, an
  explicit config flag plus a recorded decision serves the same purpose
  visibly. Deleting the hack when milestone 2 lands (as planned) requires
  nothing from v2. The grant-based *replacement* mechanism is v2 machinery
  and is not pulled forward.
- **Operational evidence required.** None.
- **Migration risk.** **Low.** The hack's entire function is inertness;
  its removal is governed by the same milestone that wires the first
  caller, which is where the risk review already lives.
- **Estimated effort.** **Trivial.** It is one packaging decision inside
  an already-planned milestone.

### D3 — Economics-only export schema for the Scout

- **Rationale.** Time-critical in the good sense: wiring milestone 1 is
  the Scout → Mission Control feed, and the field mapping in M21 §6
  already sends economics fields; the composite rides along only as
  "provenance, not input." Narrowing the payload to raw economics +
  confidence + provenance *before* the seam is wired costs one schema
  row; narrowing it after means a breaking change to a live feed. The v1
  rule ("neither side reranks the other") is preserved and strengthened —
  this deletes the temptation, not the rule.
- **Operational evidence required.** None. The failure mode (a
  boundary-crossing number eventually treated as input) is structural,
  not empirical.
- **Migration risk.** **Trivial.** The Scout keeps its composite locally;
  Mission Control's re-scoring path is unchanged and already specified.
- **Estimated effort.** **Trivial.** One payload-shape amendment to the
  milestone-1 contract before it is implemented.

### DL1 — Delay multi-machine / headless deployment

- **Rationale.** Already v1 law: M21 §10 forbids runtime deployment,
  LaunchAgent, DGX, and desktop installs for the current milestone, and
  nothing in the wiring roadmap adds machines. The v2 recommendation and
  v1 practice are the same policy stated twice. Adoption is a no-op.
- **Operational evidence required.** None to adopt the delay. (Lifting
  it later is governed by the v2 scaling-path phase gates, a v2-era
  decision.)
- **Migration risk.** **None.**
- **Estimated effort.** **None.**

### DL3 — Model ban in ranking / escalation / status as structure

- **Rationale.** The ban already holds in v1 by doctrine (PHILOSOPHY §3)
  and by test in both codebases. The only v1-era action is textual:
  stating the ban in the contracts package (alongside R4) so future
  components inherit it as a declared property rather than discovering it
  in test suites. Encoding it into the Fork Kernel itself follows M1's
  schedule and is not pulled forward.
- **Operational evidence required.** None; this is doctrine, and doctrine
  is not modified — merely restated where machines read.
- **Migration risk.** **None.** No behavior change anywhere.
- **Estimated effort.** **Trivial.**

---

## 4. EVIDENCE-FIRST — requires Olympus v1 operational evidence

### R1 — The Olympus Ledger (single event spine)

- **Rationale.** The ledger is the keystone of v2 — and precisely for
  that reason it should not be designed against zero traffic. Today not
  one seam is wired; event taxonomy, volume, retention needs, replay
  requirements, and failure modes are all projections. Building the spine
  first inverts v1's own philosophy: "small and finished beats large and
  open — an unfinished framework compounds negatively" (COMPOUND_ENGINE
  rule 3). The four wiring milestones, run as designed, are the cheapest
  possible experiment for discovering what the ledger must actually
  carry. **Adoptable in v1 without prejudice:** a *shadow ledger* — an
  append-only, hash-chained JSONL record of every payload the wired seams
  carry, observing but never transporting. It is within the stdlib house
  style, changes no behavior, and converts v1 operations into v2 design
  input.
- **Operational evidence required.** (a) All four M21 wiring milestones
  carrying real traffic; (b) shadow-ledger data covering ≥ 30 operating
  days: event counts per seam, payload-shape drift incidents, and
  failure/retry occurrences; (c) at least one concrete instance where
  reconstructing "what happened today" across ≥ 2 store files was
  materially painful — the audit-cost signal that justifies a spine; (d)
  Attention Ledger (M3) data confirming packet cadence and deferral
  volume, since rituals become ledger views.
- **Migration risk.** **Medium.** Mitigated by design (M21 payload shapes
  become the first event schemas verbatim; packets are reproduced as
  views and can be diffed against hand-assembled packets before cutover),
  but it re-platforms every communication path at once if adopted
  wholesale — hence the gate.
- **Estimated effort.** **High** (multi-week) for the spine and view
  derivations. The shadow ledger alone: **small**.

### M1 — The Fork Kernel (merge escalation classifier + executive state machine + attention router)

- **Rationale.** This merge touches the safety-critical core: the
  boundary between autonomous work and Chad's authority. Both v1 tables
  are enumerated and deterministic, so the merge is mechanically feasible
  today — but "the merged table refuses everything both predecessors
  refused" can only be *demonstrated* against real classified traffic,
  and today there is none: the §4 mapping table has never carried a live
  fork. Merging two state machines that have never disagreed in
  production means never learning where they would have. **Adoptable in
  v1 without prejudice:** a conformance harness that cross-evaluates both
  tables on every real work unit once seams are wired, logging any
  divergence. The harness is the evidence collector *and* the
  strictly-no-weaker check the v2 proposal already requires before
  cutover.
- **Operational evidence required.** (a) ≥ 30 operating days or ≥ 50
  classified work units flowing through the wired escalation seam; (b)
  conformance-harness results: zero unexplained divergences between the
  Hermes classification and the Mission Control state transition, with
  every observed divergence documented and dispositioned; (c) at least
  one full fork lifecycle (raised → routed → Chad-resolved) exercised
  end-to-end, since the kernel owns that path; (d) interrupt-class
  routing data from M3 showing the four classes fire as doctrine
  predicts.
- **Migration risk.** **High** — the highest in the matrix. A wrong row
  in the merged table is a silent boundary violation, the failure
  HUMAN_FIRST prices above all others. This is exactly why the item is
  gated on evidence rather than scheduled: risk is retired by data, and
  cutover keeps the old tables running in shadow until the harness shows
  sustained agreement.
- **Estimated effort.** **Moderate–High.** The table merge itself is
  tedious-not-risky; the harness, shadow period, and cutover discipline
  are the real cost. Harness alone: **small**.

### M2 — Governed-store kernel (unify store mechanics)

- **Rationale.** A refactor of the best-tested code in the estate, with
  zero behavior change as the success criterion — which means its value
  is entirely in *future* divergence avoided. v1 doctrine has a precise
  trigger for exactly this situation: the second-fire rule
  (COMPOUND_ENGINE rule 1). One store hardening has occurred (the
  memorygraph teardown-safe sweep, `154119b`) and was *not* needed in the
  other stores; that is first fire. The kernel is justified the moment
  the same hardening class must be applied to a second store — before
  then, extracting it is speculative generalization from a sample of
  one.
- **Operational evidence required.** (a) A second-fire event: the same
  class of bug, hardening, or corruption-recovery fix required in ≥ 2 of
  the three store implementations; **or** (b) a fourth governed store
  being designed (a new engine reaching the GOVERN stage), at which point
  the kernel is cheaper than a fourth hand copy; plus (c) the existing
  store test suites green and stable for ≥ 30 days, since they become
  the kernel's acceptance tests.
- **Migration risk.** **Medium.** It touches all persistence, but
  store-by-store adoption behind existing test suites bounds each step;
  the mutation-boundary invariant (separate files, separate owners) is
  unchanged throughout.
- **Estimated effort.** **Moderate.** Extract-and-adopt across three
  stores, sequentially.

### DL2 — Memory-graph → knowledge-growth claims (lifting UNKNOWN)

- **Rationale.** Compatibility here is subtle and worth stating exactly.
  v1's wiring milestone 3 records memory-graph *counts* as compound
  observations while the knowledge-growth dimension explicitly "leaves
  UNKNOWN" — v1's roadmap already embodies the caution v2's DL2 asks
  for. Therefore: milestone 3 proceeds unchanged (no reprioritization),
  and what is EVIDENCE-FIRST is the *subsequent* step of converting
  counts into growth claims shown to Chad. The gate is v1's own
  both-days rule plus a claim-quality baseline that does not yet exist.
- **Operational evidence required.** (a) Milestone 3 wired and recording
  counts; (b) ≥ 2 observations on ≥ 2 days per v1's existing rule; (c) a
  measured claim-quality baseline from the memorygraph store:
  established-vs-contradicted ratio over a stated window, so that
  "growth" is growth of something trustworthy; (d) contradiction-review
  latency measured (contradictions flagged are only honest if someone
  reviews them).
- **Migration risk.** **Low.** The dimension stays honestly UNKNOWN until
  the gate clears — the failure mode of waiting is a blank field, which
  v1 doctrine explicitly prefers to a fabricated trend.
- **Estimated effort.** **Trivial** once evidence exists: one view rule
  change over already-flowing counts.

---

## 5. WAIT-FOR-V2

### D1 — Delete the reserved-slot / mock-inbox pattern

- **Rationale.** The deletion is correct *only after* R1 makes wiring
  cheap and uniformly governed. During v1, reserved slots are the honest
  mechanism doing real work: they let Mission Control report
  `known: false` naming the missing feed instead of pretending, and they
  hold the seam designs that the wiring milestones implement. Deleting
  the pattern during v1 would either force premature wiring (pulling R1
  forward past its evidence gate) or delete the honesty mechanism with
  nothing to replace it. Adopting D1 early is therefore not a cheaper
  version of v2 — it is a worse version of v1.
- **Operational evidence required.** None as such — the gate is
  *architectural*, not evidentiary: R1 adopted and each slot's seam
  either wired through the ledger or consciously dropped. Each retired
  slot inherits R1's evidence trail.
- **Migration risk.** **Low when due.** The deletion happens slot-by-slot
  as seams wire; at no point does a consumer lose a placeholder it still
  reads. Risk only exists if adopted early (see rationale).
- **Estimated effort.** **Trivial when due** — documentation and
  dead-code removal per slot, absorbed into each wiring step.

---

## 6. REJECT — none, and the bar that none met

A recommendation would be rejected if it (a) violated a preserved goal,
(b) conflicted with the Constitution, or (c) required v1 to take on risk
that no amount of operational evidence could retire. Zero items met the
bar, but two came close enough to deserve their scrutiny recorded:

- **M1 (Fork Kernel)** was the nearest miss on criterion (c): merging
  safety-critical state machines is the kind of change that can look
  green in tests and fail in the one row that matters. It survives
  rejection because both source tables are fully enumerated (the merge is
  verifiable by exhaustive comparison, not judgment), because the
  shadow-run cutover makes the risk observable before it is live, and
  because the alternative — maintaining the §4 alignment table forever —
  carries the *same* failure mode with less visibility. Gated, not
  rejected.
- **D1 (delete reserved slots)** was the nearest miss on criterion (a),
  since deleting the `known: false` mechanism prematurely would damage
  the evidence-or-silence property Chad relies on. It survives as
  WAIT-FOR-V2 because the recommendation is correct in its intended
  context; only its timing was dangerous.

That the remaining eleven items classify cleanly is consistent with the
v2 proposal's own claim: it changes mechanisms, never mission. A v2 that
produced REJECT rows would have been redesigning the goals, which was
out of bounds.

---

## 7. Evidence Checklist (consolidated)

Everything the EVIDENCE-FIRST items need, stated once so v1 operations
can collect it as a byproduct of running the existing roadmap — no new
milestones implied:

| Evidence | Feeds | Source during normal v1 operation |
|---|---|---|
| Four wiring milestones carrying real traffic | R1 | M21 §11 roadmap, as already planned |
| ≥ 30 days shadow-ledger seam data (volume, drift, failures) | R1 | Shadow ledger (observational, adoptable anytime) |
| ≥ 1 documented cross-store audit-reconstruction pain event | R1 | Evening Report preparation |
| ≥ 30 days / ≥ 50 units of classified escalation traffic | M1 | Wired escalation seam |
| Conformance-harness divergence log (target: zero unexplained) | M1 | Harness cross-evaluating both v1 tables |
| ≥ 1 end-to-end fork lifecycle (raised → resolved) | M1 | First real NEEDS_CHAD through the wired loop |
| Interrupt-class routing data | M1 | Attention Ledger (M3, adopted in v1) |
| Second-fire hardening across ≥ 2 stores, or a fourth store reaching GOVERN | M2 | Normal maintenance history |
| ≥ 30 days green store test suites | M2 | CI, as-is |
| Counts flowing per milestone 3; ≥ 2 obs / ≥ 2 days | DL2 | M21 milestone 3, as already planned |
| Claim-quality baseline (established : contradicted ratio) | DL2 | memorygraph store queries |
| Contradiction-review latency | DL2 | memorygraph review workflow |

---

## 8. Compatibility Verdict

The Olympus v2 proposal is **compatible with the Olympus v1 program as
designed**. Eight of thirteen items fold into work v1 already plans or
cost nothing; four are gated on evidence the v1 roadmap will produce as
a side effect of normal operation; one waits for v2 by construction;
none are rejected. No v1 milestone moves. The single scheduling-adjacent
observation in the whole matrix is an *ordering within* existing
milestones, not between them: D3 (narrow the Scout export schema) and R3
(partition labels) are cheapest if decided before wiring milestone 1 is
implemented, and R4 (contract registry) makes milestone 2 safer if it
lands first. Those are compatibility facts for the Build Program's
owner to weigh — this document does not act on them.
