# Build Program × Failure Campaign — Risk Mapping

**Lane 5 of the Olympus Reliability Intelligence Campaign.**
**Status:** Design-only analysis. No code, no implementation tasks, no governance changes, no architecture redesign. The Build Program is treated as **authoritative** — this document maps it against the failure campaign; it does not redesign it.
**Source of truth for failures:** `docs/reliability/olympus-failure-injection-campaign-v1.md` (100 scenarios; Top 25 existential ranking).
**Source of truth for the program:** `docs/executive-operating-loop-contract.md` (M21), `docs/chief-of-staff/*.md` (foundation), `docs/design/opportunity-scout-engine.md`.
**Mission ladder: partially RECONSTRUCTED.** The authoritative Build Program mission list does not exist in this repository. Every mission below is labeled **DOCUMENTED** (directly evidenced) or **INFERRED** (reconstructed from documented artifacts). See Section 0 before citing any mission number.

---

## 0 — Reconstruction statement and confidence

**What is documented, verbatim:**

- **M19** (executive coach `coach()`), **M20** (adaptive conversation / LEARNING intent), **M21** (Executive Operating Loop contract, mission-control-v0 PR #20, branch `m21-executive-operating-loop`) — named as milestone numbers in the M21 contract doc.
- **Missions 22–25** — the four Chad-approved wiring milestones of M21 section 11, in order: (1) Opportunity Scout → MC inbox feed; (2) MorningBrief/EveningReport adapters + wheel inclusion; (3) memory-graph counts as compound observations; (4) LeverageStore consuming `attention_saved`.
- **Merged artifacts whose existence is documented** (but whose ladder position is not): the seven chief-of-staff foundation docs (`CHIEF_OF_STAFF_FOUNDATION_READY`), the `chief_of_staff` package (PR #5: escalation classifier, morning/evening parsers, contracts/schema versioning, metrics LeverageLedger interface), Mission Control's `executive_state.py` (10 states / 9 events), evidence feeds + closed source allowlist, the four-class attention router, decision/bottleneck engine implementations, Compound Engine v2 (7 dimensions), the merged `memorygraph` provider, the merged `opportunity_scout` engine, and MC packet producers (PR #20 context).

**What is inferred:** the assignment of those merged/laid artifacts to rungs **M1–M18**, and their ordering. The artifacts are real (cited by the contract doc); the numbering is my reconstruction.

**Confidence:** HIGH that M19–M25 are correctly identified and ordered. HIGH that the M1–M18 *artifacts* exist as described. LOW-to-MEDIUM on the M1–M18 *numbering and ordering* — do not treat "M7" etc. below as canonical mission numbers. The cumulative-checkpoint curve (Section 3) is therefore reliable in **shape and endpoints**, approximate at the intermediate checkpoints (M1, M5, M10, M15); the M20/M25 checkpoints and the Top-25 verdict (Section 4) depend almost entirely on documented artifacts and are robust to reordering of M1–M18.

**Reconstructed ladder (summary):**

| # | Mission | Label |
|---|---|---|
| 1 | MISSION.md constitution (roles, North Star, Final Filter) | INFERRED |
| 2 | HUMAN_FIRST (six boundaries; CONTINUE/PAUSE/NEEDS_CHAD doctrine) | INFERRED |
| 3 | PHILOSOPHY (asset-first; attention economy doctrine) | INFERRED |
| 4 | DECISION_ENGINE doctrine (evidence-first, deterministic, no model calls in the spine) | INFERRED |
| 5 | BOTTLENECK + COMPOUND + EXECUTIVE_COACH doctrine; foundation READY | INFERRED |
| 6 | `chief_of_staff.contracts` + SCHEMA_VERSION + major-match rule | INFERRED |
| 7 | Escalation classifier (`classify_work`, first-match-wins rule table, one-question rule) | INFERRED |
| 8 | Morning Brief parser (all-or-nothing, `MorningBriefError`, `MorningBriefSource`) | INFERRED |
| 9 | Evening Report parser (`parse_evening_report`, `EveningReportSource`, honest `degraded`) | INFERRED |
| 10 | MC executive state machine (`executive_state.py`: 10 states, 9 events, ESCALATING has no CONTINUE, UNKNOWN first-class, evidence-required transitions) | INFERRED |
| 11 | MC evidence feeds + closed source allowlist (`record_signal`) | INFERRED |
| 12 | Attention router (four-class deny-by-default interrupts; `waiting_for_you` deferral) | INFERRED |
| 13 | Decision Engine implementation (deterministic ranking; `why_chosen` receipts) | INFERRED |
| 14 | Bottleneck Engine implementation (ONE evidence-backed-or-null recommendation) | INFERRED |
| 15 | Compound Engine v2 (7 dimensions, honest UNKNOWN, both-days rule, ≥2 obs on ≥2 days) | INFERRED |
| 16 | `memorygraph` provider (governed claims, tiers, evidence-gated promotion, contradiction flagging) — artifact documented as merged; rung INFERRED | INFERRED |
| 17 | `opportunity_scout` engine (deterministic 0–100 scoring, atomic JSON store, inbox ingestion, exact+fuzzy dedup, `ALLOWED_TRANSITIONS`) — artifact documented as merged; rung INFERRED | INFERRED |
| 18 | MC executive packet producers + `MissionStore` persistence (fail-loud, `.corrupt-<ts>` convention) | INFERRED |
| 19 | Executive Coach (`coach()`) | DOCUMENTED |
| 20 | Adaptive conversation (LEARNING intent consumes `learning_recommendation`) | DOCUMENTED |
| 21 | Executive Operating Loop contract (M21, doc-only; seams + invariants recorded) | DOCUMENTED |
| 22 | Wiring 1: Opportunity Scout → MC inbox feed (`POST /opportunities`; EW sources rejected at boundary) | DOCUMENTED |
| 23 | Wiring 2: MorningBrief/EveningReport adapters on MC's GET routes + wheel inclusion | DOCUMENTED |
| 24 | Wiring 3: memory-graph counts recorded as compound observations (knowledge-growth leaves UNKNOWN) | DOCUMENTED |
| 25 | Wiring 4: LeverageStore consuming `attention_saved` | DOCUMENTED |

**Grading vocabulary used throughout:** *materially mitigates* = the mission's artifact clearly improves likelihood, impact, or detection of the scenario (the campaign itself frequently names these artifacts as the containment); *partially mitigates* = the artifact supplies a necessary ingredient (a channel, a doctrine, a data structure) but the specific instrument or audit the scenario needs is not part of the program. Where a containment named by the campaign is instrumentation the program does not include (disk thresholds, expiry horizons, NTP monitors, canaries, merge audits), the scenario is graded **untouched**, even though the program's evidence-feed channel *could* someday carry it.

---

## 1 — Mission-by-mission mapping

### Mission 1 — MISSION.md constitution [INFERRED]
Roles (Brain/Assistant/Executive), North Star, Final Filter, division of labor.
- **Mitigates:** OP-07 (partial — "Mission Control owns the plan" decides the winner between contradictory channels); OR-04 (partial — roles make failures attributable); OR-01 (partial — the Final Filter names the disease, giving the later audit its test).
- **Unchanged:** everything operational — all MC/HM/HB/TE/IN classes; the entire EW domain.
- **Introduced/worsened:** none functionally; every constitution document adds OR-03 surface (a map that can drift from territory).

### Mission 2 — HUMAN_FIRST boundaries + escalation doctrine [INFERRED]
Six never-delegated boundaries; three-state classification doctrine; conservative defaults.
- **Mitigates:** OP-01 (queued packets *are* the containment for absence); OP-05 (do-nothing default makes waiting safe); CF-05 (partial — the constitutional floor "defaults never spend, send, or bind" is what makes attrition cost opportunity, not safety); CF-01 (partial — "new category → NEEDS_CHAD by definition; uncertain → more conservative"); TE-08 (partial — "authority granted, never inferred from precedent" is the constitutional backstop against trust bleed); OP-02 (partial — graceful-starvation posture); HM-10/IN-09 (partial — credentials never self-repaired; wait loudly); EW-10 (partial — the division of labor "machine never authors judgment" is the legally defensible posture's foundation).
- **Unchanged:** all silent-erosion detection (OR-05, OP-03), all EW data-plane risks, all infrastructure.
- **Introduced/worsened:** none; note that doctrine without enforcement machinery creates a *false-assurance* risk the campaign names in OR-02 (rules that exist on paper only).

### Mission 3 — PHILOSOPHY doctrine [INFERRED]
Asset-first; "Attention Is the Scarce Resource"; never chase autonomously.
- **Mitigates:** OP-06 (partial — the interrupt-budget doctrine that M12 later mechanizes); IS-10 (partial — the asset-building doctrine supplies the reference portfolio shape its detection needs).
- **Unchanged:** everything mechanical; all TE/EW/IN classes.
- **Introduced/worsened:** none (doc-drift surface only).

### Mission 4 — DECISION_ENGINE doctrine [INFERRED]
Evidence-first claims (observation/inference/estimate/uncertainty); determinism; "insufficient evidence" always admissible.
- **Mitigates:** IN-03 (partial — the no-model-calls-in-the-spine invariant is why a provider outage is a pause, not a lobotomy); HB-06 (partial — the deterministic layer is the only uncorrelated check the two-machine design has); IS-01 (partial — score ≠ confidence ≠ decision gate structure); MC-09 (partial — "proves, not reports" doctrine).
- **Unchanged:** everything that needs the doctrine *enforced* rather than stated.
- **Introduced/worsened:** none.

### Mission 5 — BOTTLENECK + COMPOUND + COACH doctrine; foundation READY [INFERRED]
- **Mitigates:** MC-10 (partial — ONE-recommendation discipline defined); OR-01 (partial — bottleneck discipline is the named containment for Build Program drift).
- **Unchanged:** all execution, trust-ledger, EW, infrastructure classes.
- **Introduced/worsened:** the Compound Engine concept creates the *future* TE-07 surface (a system that counts its own improvement must not grade its own homework) — latent until M15/M24.

### Mission 6 — Contracts + schema versioning [INFERRED]
`SCHEMA_VERSION`, `check_schema_version`, major-match rule, additive-only 1.x fields.
- **Mitigates:** MC-11 (materially reduces recurrence — version-skew can no longer produce malformed packets silently; refusal is clean); HB-04 (partial — fail-loud schema validation shortens the fester window of escaped schema defects).
- **Unchanged:** all human-behavior, trust-erosion, EW classes.
- **Introduced/worsened:** the versioning rule is itself a coordination seam: a major bump requires simultaneous two-repo change — a new (small) split-brain opportunity if half-shipped (MC-11 texture at deploy time).

### Mission 7 — Escalation classifier implementation [INFERRED]
`classify_work`: deterministic first-match-wins; PAUSE requires resume plan; one question max.
- **Mitigates:** OP-01 (material — clean holds under absence are now mechanical); OP-07 (material — contradiction classifies NEEDS_CHAD instead of silently winning); MC-05 (material with M18 — resume-plan-without-recheck-date rejected at classification); OP-04 (partial — one-question-per-packet limits blast radius); CF-04 (partial — one-question discipline); CF-01 (partial — deterministic misses are reproducible and fixable, per the campaign's own containment note); CF-03 (partial — classification events now *exist*, making the coverage audit possible); HM-07 (partial — "failure ceiling" is a named PAUSE reason; the ceilings themselves are not built).
- **Unchanged:** CF-08 (effect-level classification absent), CF-07, all EW, all infrastructure.
- **Introduced/worsened:** a finite rule table is now the load-bearing safety component — every future tool/channel added without rules is a CF-01 waiting to happen; rule-table edits create the CF-02 fork-inflation surface.

### Mission 8 — Morning Brief parser [INFERRED]
All-or-nothing parse; `MorningBriefError`; refuse whole, never partial-trust.
- **Mitigates:** MC-11 (material — the refusal behavior *is* the designed cheap failure: subtle corruption becomes a clean, visible outage); MC-02 (partial — consumer answers from last published state and never invents a plan).
- **Unchanged:** producer-side ritual failures, everything else.
- **Introduced/worsened:** parse-refusal outage mode now exists in design; it becomes a live operational exposure only at M23.

### Mission 9 — Evening Report parser [INFERRED]
- **Mitigates:** MC-09 (partial — honest `degraded`/UNKNOWN consumption; `confidence_changes` carries the both-days rule to the consumer).
- **Unchanged:** close-of-books re-verification (the actual MC-09 fix) is producer-side and not in the program.
- **Introduced/worsened:** same M23-deferred parse-refusal exposure as M8.

### Mission 10 — MC executive state machine [INFERRED]
10 states / 9 events; ESCALATING has no CONTINUE row; UNKNOWN first-class; every transition evidence-required.
- **Mitigates:** MC-07 (material — the formal RESOLVE-with-reason path exists, and the wedge is containment working; "verbal resolutions don't exist" is now mechanical); OP-06 (partial — unacknowledged safety escalations hold in ESCALATING; nothing proceeds); CF-06 (partial — the hold never depends on packet delivery); MC-04 (partial — evidence-required transitions mean unevidenced "progress" is recordable as UNKNOWN); HM-11 (partial — UNKNOWN as a first-class state makes "the host is lying" representable).
- **Unchanged:** everything outside mission-state governance; all EW, HB, IN classes.
- **Introduced/worsened:** MC-07's wedge is this mission's deliberate cost — constitutionally immortal escalations require the formal path to be *cheaper than* the verbal shortcut, which is a UX debt the program does not retire.

### Mission 11 — Evidence feeds + closed source allowlist [INFERRED]
- **Mitigates:** TE-05 (material within scope — the closed allowlist bounds who can record at all; the campaign names it as containment); TE-01 (partial — recorder-side provenance is the dedup hook); TE-07 (partial — allowlists are the gesture toward reality-terminated provenance; enforcement is absent).
- **Unchanged:** the instruments the feed could carry (disk, expiry, NTP, spend telemetry) are not in the program — HM-03, IN-01, IN-09, IN-10, TE-09 stay effectively untouched.
- **Introduced/worsened:** the recorder is now a *target*: anything allowlisted (`hermes-agent` already is) can inflate counts — the exact surface M24 later exercises.

### Mission 12 — Attention router [INFERRED]
Four evidence-backed interrupt classes, deny-by-default; deferrals to `waiting_for_you`.
- **Mitigates:** OP-06 (material — this is the designed containment for alarm fatigue: near-zero interrupts/day is a design target, not a hope); OP-01 (material with M7 — only four classes may page; everything else waits for the packet); CF-02 (partial — excess packets pool instead of paging); CF-06 (partial — `waiting_for_you` is the delivery-independent reconciliation path).
- **Unchanged:** channel-dead detection (OP-10) until rituals are live; the *human* side of alarm fatigue (muting).
- **Introduced/worsened:** deny-by-default means misclassified-genuine-safety items wait silently — the router shifts risk from interrupt-spam toward CF-01-shaped misses; it must be fed by the M7 table it depends on.

### Mission 13 — Decision Engine implementation [INFERRED]
- **Mitigates:** IS-06 (material — `why_chosen` receipts show the arithmetic at every presentation; a 12× error is conspicuous); IS-01 (partial — MC re-scores through its own declared weights; the scout's composite is provenance, not input); MC-06 (partial — a ranked total order now exists for the substrate to enforce); IN-10 (partial — the ranked order is what priority-shedding under scarcity would consume).
- **Unchanged:** enforcement at the point of resource contention (MC-06 proper) and shedding *policy* (IN-10 proper) are not built; IS-10's monoculture is a property of any fixed weights, including these.
- **Introduced/worsened:** deterministic weights institutionalize IS-10 — the ranking is now a strategy nobody chose, consistently applied.

### Mission 14 — Bottleneck Engine implementation [INFERRED]
- **Mitigates:** MC-10 (material — ONE recommendation regardless of queue depth; queue depth never leaks into the 90-minute window); OR-01 (partial — the morning discipline pointed at the principal's constraint is the named containment; the mission-mix *metric* is absent).
- **Unchanged:** triage/un-planning machinery (MC-10's recovery path) stays manual.
- **Introduced/worsened:** a single evidence-backed-or-null recommendation concentrates the IS-01/IS-06 poisoning payoff — whatever games the ranking games the *one* thing Chad sees first.

### Mission 15 — Compound Engine v2 [INFERRED]
7 dimensions; honest UNKNOWN; both-days rule; ≥2 observations on ≥2 days; reserved feeds.
- **Mitigates:** TE-01 (material — the ≥2-days rule blocks same-day double counts; with M16's evidence-gating this is the promotion-integrity core); MC-09 (partial — both-days/≥2-obs rules resist single-point fictions propagating into trends); TE-06 (partial — *new* claims stay honest; old ones still never decay); OP-08 (partial — `confidence_changes` trending down in one domain is the named proxy detector).
- **Unchanged:** evidence-age/decay (TE-06 proper), close-of-books re-verification (MC-09 proper).
- **Introduced/worsened:** a growth-counting engine is the TE-07 attack surface by construction — it is safe only while its feeds are reality-terminated, a property M24 will stress.

### Mission 16 — memorygraph provider (merged) [INFERRED rung]
Governed claims; candidate/established/core tiers; evidence-gated promotion; contradictions flagged, never auto-resolved; own store, own writer.
- **Mitigates:** TE-02 (material — contradiction flagging with both records persisting is the built-in containment); TE-01 (material, with M15); TE-03 (partial — fail-loud open plus recomputability-from-evidence by design); TE-07 (partial — faithful provenance recording is what makes circular chains mechanically findable); EW-06 (partial — same provenance makes case-rooted claims findable *after* absorption; recording-disable in EW contexts is not built).
- **Unchanged:** trust-floor degradation, restore reconciliation (TE-04), clock integrity (TE-09), persistence verification (TE-10).
- **Introduced/worsened:** a durable knowledge store is precisely the EW-06 retention hazard — a store designed never to forget now exists on a machine that also sees case-adjacent work.

### Mission 17 — opportunity_scout engine (merged) [INFERRED rung]
Deterministic 0–100; human-entered evidence only; atomic JSON store; inbox ingestion; exact+fuzzy dedup; `ALLOWED_TRANSITIONS`.
- **Mitigates:** IS-01 (material — source-type priors, confidence machinery, human-evidence gate; never chases); IS-02 (material — dedup at ingest with reject/flag/allow policy); IS-07 (material — atomic writes, fail-loud version validation, corrupt-file backup: the store conventions); IS-08 (material — exact fingerprints reject replays loudly); IS-09 (material — terminal states enforced at the API, reasons recorded with transitions); IS-03/IS-06/IS-04/IS-10 (partial — priors, clamping, lifecycle expiry, and legibility exist; concentration metrics, plausibility bands, age triggers, and portfolio reporting do not); OP-09 (partial — a governed store makes hand-edits detectable as foreign writes).
- **Unchanged:** IS-05 (the human gate can still be fed hallucinated numbers — source citations not built); everything outside the opportunity domain.
- **Introduced/worsened:** the inbox directory is a new at-least-once ingestion channel (IS-08 exists *because* this mission does); a hand-editable JSON store is an OP-09/IS-07 attractive nuisance.

### Mission 18 — MC packet producers + MissionStore [INFERRED]
Morning/evening packet emission; fail-loud persistence with `.corrupt-<ts>` convention; mission IDs.
- **Mitigates:** MC-01 (material — fail-loud load, refuse-and-back-up, never silently start fresh); MC-05 (completes material — `waiting_for_you` surfaces WAITING items with age); MC-03/MC-04 (partial — mission IDs make duplicates and voids detectable; evening plan-vs-actual reconciliation is the designed net; idempotent re-dispatch discipline itself is not evidenced); MC-02 (partial — ritual production machinery exists; scheduler liveness does not); MC-12 (partial — mission IDs blunt re-dispatch after restore; mandatory reconciliation mode is not built); CF-09 (partial — PAUSE surfacing in the brief is now a producer feature; the conservation check is not); OP-10 (partial — a daily packet is the dead-man switch precondition); OP-04 (partial — the Evening Report can render what-was-decided).
- **Unchanged:** scheduler death (MC-02 proper), restore reconciliation (MC-12 proper), ritual timing (MC-08).
- **Introduced/worsened:** the MissionStore is now a single point of amnesia (MC-01 exists because it does); "dispatched" as a store state creates the MC-04 claim-vs-reality gap.

### Mission 19 — Executive Coach [DOCUMENTED]
`coach()`; evidence-gated recommendations (unreachable without evidence; UNKNOWN otherwise); judgment preview.
- **Mitigates:** OP-03 (partial — the judgment preview means Chad decides prepared instead of ambushed; the campaign's real detectors — approval-latency trends — are not built); OP-05 (partial — coaching observations on judgment quality are the only instrument aimed at the operator's decision quality).
- **Unchanged:** all mechanical classes; the coach informs judgment, never replaces it — by design it cannot *contain* anything.
- **Introduced/worsened:** none material; a coach that is ignored joins the OR-05 pile of unconsumed evidence.

### Mission 20 — Adaptive conversation / LEARNING intent [DOCUMENTED]
- **Mitigates:** OP-07 (marginal — conversation answers cite MC-published packet state; Hermes never invents state); OR-04 (marginal — reinforces consumer-not-author role).
- **Unchanged:** essentially the entire failure space; this is a value-delivery mission, not a reliability mission.
- **Introduced/worsened:** a conversational surface is a second instruction channel — the OP-07 contradiction surface it partially mitigates, it also *is*.

### Mission 21 — Executive Operating Loop contract [DOCUMENTED]
Doc-only; records every seam's payload shape + governance rule; six invariants enumerated.
- **Mitigates:** OR-02 (partial — seams and invariants written down with change control are what the governance-parity audit would diff against); OR-03 (partial — the map is made to match the territory at the seams, dated); HB-05 (partial — a current-contracts document is exactly what refreshes stale reviewer context); OR-04 (completes material — mutation boundaries enumerated: each system writes only its own store, and the stores now really do have one writer each); MC-11 (reinforces — versioning rule stated as contract).
- **Unchanged:** everything needing runtime enforcement; a contract nobody audits against is OR-02's autobiography problem.
- **Introduced/worsened:** none directly — but it *authorizes* the four wiring missions, each of which adds a live seam.

### Mission 22 — Wiring 1: Scout → MC inbox feed [DOCUMENTED]
`POST /opportunities`; allowed sources only; expert-witness sources rejected at the boundary; MC re-scores locally; ends the mock-inbox era.
- **Mitigates:** the mock-inbox gap — `opportunity_highlight` stops honestly reporting `known: false` and the Evening Packet's opportunity movement becomes real rather than fictional (MC-09-adjacent); IS-01/IS-04 (partial — MC's independent re-scoring and receipts add the second gate at presentation); EW-01/EW-05 (partial — the forbidden-source rejection machinery is now *exercised live* at a real ingestion boundary, converting a paper control into a tested one).
- **Unchanged:** everything outside the opportunity pipeline.
- **Introduced/worsened (honest):** this seam creates the very **MC-03/MC-04-style** dispatch/duplication surface at POST time (at-least-once delivery, lost acks, double-posted opportunities inflating movement counts) and a **TE-05/IS-08 replay surface** (a re-run feed replays history into MC's counts); a network hop and auth credential now sit inside the opportunity path (IN-01/IN-09 texture).

### Mission 23 — Wiring 2: packet adapters + wheel inclusion [DOCUMENTED]
`MorningBriefSource`/`EveningReportSource` adapters on MC's reserved GET routes; `chief_of_staff` enters the wheel.
- **Mitigates:** OP-10 (completes material — the Morning Packet now actually arrives daily, making the dead-man-switch convention possible; its *absence* becomes the designed 24h-bounded tripwire); CF-06 (completes material — `waiting_for_you`, generated from mission state on an independent path, now reaches Chad); MC-02 (partial — a missing ritual is now noticeable at the consumer); OP-01/OP-04 (the rituals the containment stories depend on are finally live); CF-09 (partial — PAUSE items now genuinely surface).
- **Unchanged:** ritual timing (MC-08); the human reading what arrives (OR-05).
- **Introduced/worsened (honest):** this is where **MC-11 parse-refusal becomes a real outage mode** at a new boundary (a malformed packet = a planless day, by design); version skew between repos becomes an operational event, not a doc note; the packet path inherits network/DNS/auth failure textures (IN-05/IN-08/IN-09) it never had while mocked.

### Mission 24 — Wiring 3: memory-graph counts as compound observations [DOCUMENTED]
`record_signal(type="compound-observation", metric="memory_claims_established", source="hermes-agent")`; knowledge-growth leaves UNKNOWN.
- **Mitigates:** the knowledge-growth blind spot — Compound Engine v2's reserved dimension stops reporting UNKNOWN and starts carrying evidence-gated counts; TE-03 (marginal — counts become cross-checkable against MC's independent record).
- **Unchanged:** trust decay (TE-06), restore integrity (TE-04), clock (TE-09).
- **Introduced/worsened (honest):** this is the **TE-07 self-licking surface the campaign explicitly warns about** — a Hermes-side count of Hermes-curated claims recorded as a *compound observation* is one sloppy provenance chain away from the system's outputs becoming its own evidence; it also opens a TE-01/TE-05 double-count/replay surface at the recorder (a re-run reporter re-records the same claim counts). The governance symmetry rules (≥2 obs on ≥2 days; contradicted never promotes) are the only guardrails, and they are threshold rules, not provenance rules.

### Mission 25 — Wiring 4: LeverageStore ← attention_saved [DOCUMENTED]
- **Mitigates:** attention-economy blindness — the resource the whole system optimizes gets a ledger: CF-02 (completes material — packet/deferral volume and declared minute costs are now measurable, enabling the "these N classes were 100%-approved" meta-packet); OP-06 (reinforces — the interrupt budget becomes a measured dose rather than a vibe); CF-05/OR-05 (partial — deferred-decision and attention data are the raw material for decided-by-Chad and consumption metrics, though neither metric itself is in the program).
- **Unchanged:** the reader (OR-05 proper); approval-latency instrumentation (OP-03).
- **Introduced/worsened (honest):** `attention_saved` sums **declared** minute costs only — a self-reported benefit metric is gameable by construction (a small TE-07 cousin: the system reporting how much attention the system saved); plus one more governed store to corrupt, hand-edit, or restore badly (TE-03/OP-09 texture, minor).

---

## 2 — What the whole program never touches

Named once so each mission's "unchanged" line could stay short:

- **Host/hardware plane (HM):** crashes, power, disk full/dead, evidence retention under pressure, git corruption, OS updates, keychain, toolchain drift, flaky RAM — 9 of 12 HM scenarios untouched (HM-04 is Top-25 #23).
- **Reviewer plane (HB):** queue-age metrics, finding-rate/canary alarms (HB-03), merge audits (HB-07), reviewer performance and context hygiene — 6 of 9 untouched, including two Top-25 entries.
- **Infrastructure (IN):** Tailscale, GitHub, provider outages/degradation, DNS, NTP, spend caps, power cascades, NAT — 9 of 12 untouched (IN-04 is Top-25 #25).
- **Expert-witness data plane (EW):** routing pins, egress logs, opaque-format default-deny, per-case contexts, matter-close destruction, custody chains, codenames, methodology records — 6 of 10 untouched, including Top-25 ranks 1 and 3.
- **Erosion instrumentation:** approval-latency trends, default-execution rates, mission-mix reporting, governance-parity audits, consumption metrics, canary defects — the detectors for the Top-25's governance cluster exist in the campaign's text, not in the program.

---

## 3 — Cumulative risk reduction

**Method (transparent, deliberately simple):**

- Each of the 100 scenarios has weight **1**; each scenario ID in the Top-25 table has weight **3** (the table's rank 4 names two IDs, EW-01 and EW-02, so 26 IDs carry weight 3). Total weight = 74×1 + 26×3 = **152**.
- A completed mission gives a scenario credit **1.0** if it materially mitigates it, **0.5** if partially (per Section 1's grading vocabulary); a scenario's credit is the best any completed mission provides.
- Cumulative coverage at checkpoint N = Σ(weight × credit, over scenarios with ≥1 mitigating mission ≤ N) / 152.
- Caveat: checkpoints M1–M15 sit on the INFERRED rungs — treat them as a curve shape, not gospel. M20/M25 rest on documented artifacts.

| Checkpoint | Weighted score | Coverage | One-line interpretation |
|---|---|---|---|
| After Mission 1 | 1.0 / 152 | **0.7%** | A constitution alone mitigates almost nothing; it only makes later failures attributable. |
| After Mission 5 | 14.0 / 152 | **9.2%** | Doctrine buys real coverage of operator-absence and default-safety classes — entirely on paper, enforced by nothing. |
| After Mission 10 | 21.5 / 152 | **14.1%** | The deterministic spine (classifier, parsers, state machine) converts several silent failures into clean refusals and formal holds. |
| After Mission 15 | 29.5 / 152 | **19.4%** | The evidence/attention machinery (allowlist, router, engines) lands the program's single biggest Top-25 win: OP-06's four-class router. |
| After Mission 20 | 49.0 / 152 | **32.2%** | The merged engines and packet producers do the heaviest lifting — the IS category goes from naked to mostly covered, the TE core hardens. |
| After Mission 25 | 57.0 / 152 | **37.5%** | Wiring makes the paper loop real (dead-man switch, live boundary checks, attention ledger) — while adding the seams (MC-03/04, MC-11, TE-05, TE-07) that Lane-5 successors must watch. |

### 3.1 — What each checkpoint interval actually buys (delta view)

- **M1:** OP-07 (P), OR-04 (P). Score +1.0.
- **M2–M5 (doctrine):** OP-01, OP-02, OP-05, TE-08, HM-10, IN-09, IN-03, MC-10 to partial; CF-01, CF-05, EW-10, OP-06, HB-06, OR-01 to partial at triple weight. Score +13.0. Doctrine covers a surprising amount of the Top 25 — all of it at half-credit, none of it enforced.
- **M6–M10 (deterministic spine):** OP-01 and OP-07 upgrade to material; MC-11 material (M8); MC-07 material (M10); OP-04, HM-07, CF-04, HB-04, HM-11, MC-05 partial; CF-03 partial at triple weight. Score +7.5.
- **M11–M15 (evidence + attention machinery):** OP-06 upgrades to material — the program's only Top-25 kill; TE-01 to material; MC-10 to material; TE-05, TE-06, OP-08, CF-02, CF-06, MC-06, IN-10 partial; MC-09 partial at triple weight. Score +8.0.
- **M16–M20 (merged engines + producers):** the single largest jump. M16: TE-02 material; TE-03, TE-07 (×3), EW-06 (×3) partial. M17: five IS scenarios material (IS-01/02/07/08/09), five partial including IS-05 (×3), plus OP-09. M18: MC-01 material, MC-05 completes, five MC/CF/OP scenarios partial. M19: OP-03 (×3) partial. Score +19.5.
- **M21–M25 (contract + wiring):** OR-04 completes to material; OP-10, CF-06, CF-02 complete to material as the loop goes live; EW-01 (×3), OR-02 (×3), OR-05 (×3), EW-05, HB-05, OR-03 partial. Score +8.0 — smaller than it feels, because each wiring step also *adds* the seam risks priced in Section 1.

Unweighted, after Mission 25: **19 scenarios materially mitigated, 44 partially, 37 untouched** (63/100 have at least one mitigating mission). The curve's message: the completed Build Program roughly **doubles** its risk coverage in the merged-engines stretch (M16–M18) and again gains a third of its total in the last ten missions — but it plateaus well under half of the weighted risk surface, because the weight lives in EW and erosion classes the program was never aimed at.

---

## 4 — Top 25 existential risks: entry-by-entry verdict

Verdicts: **MITIGATED** (materially, by named mission), **PARTIAL** (a real ingredient exists; the scenario's own containment/detection does not), **UNTOUCHED**.

| Rank | ID | Verdict | By / why |
|---|---|---|---|
| 1 | EW-04 PHI to cloud endpoint | **UNTOUCHED** | No mission touches model routing pins or egress logs. M21 §10 even hard-excludes runtime/gateway changes. The worst event Olympus can produce is outside the program. |
| 2 | EW-10 Discovery of AI use | **PARTIAL (thin)** | M2: HUMAN_FIRST's division of labor is the legally defensible posture and the escalation contract makes it *true* in the trail. But the methodology statement, per-matter records, and disclosure posture are untouched. |
| 3 | EW-03 Cross-case contamination | **UNTOUCHED** | Per-case isolated contexts and citation-per-assertion discipline appear in no mission. |
| 4 | EW-01/02 Isolation breach / opaque bypass | **PARTIAL** | EW-01: M22 exercises forbidden-source rejection live at the MC inbox boundary — one real, tested boundary. EW-02: opaque-format default-deny untouched; the general (non-scout) ingestion surface untouched. |
| 5 | CF-01 Missed fork | **PARTIAL** | M2 + M7: default-under-uncertainty rules and a deterministic, reproducible classifier. The category-recognition gap — the scenario's actual mechanism — remains; every new tool re-opens it. |
| 6 | CF-08 Fork evasion by decomposition | **UNTOUCHED** | Effect-level re-classification at the last hop exists in no mission. The structural variant of CF-01 recurs until it does. |
| 7 | OR-05 Evidence ignored | **PARTIAL (thin)** | M25 supplies attention/deferral data; nothing measures the *reader* (acknowledgment depth, queue-work rates). The campaign's ~40-scenario multiplier stands. |
| 8 | OR-02 Governance drift | **PARTIAL** | M21 writes the seams and invariants down with change control — the diff-base for a parity audit that is not itself in the program. |
| 9 | CF-05 Death by default | **PARTIAL** | M2's conservative-default floor caps the damage at opportunity, never safety; the default-execution-rate metric and meta-packet do not exist. |
| 10 | OP-06 Alarm fatigue | **MITIGATED** | M12's four-class deny-by-default router is the designed containment, and M25 makes the interrupt budget measurable. The program's one clean Top-25 kill. |
| 11 | HB-03 LGTM machine | **UNTOUCHED** | Finding-rate alarms and canary defects appear in no mission; the review plane is outside the program. |
| 12 | TE-07 Self-licking loop | **PARTIAL — and worsened** | M11 allowlist + M16 faithful provenance make circular chains findable; nothing *enforces* reality-terminated provenance — and M24 wires the exact feed the campaign warns about. |
| 13 | OR-06 Bus factor one | **UNTOUCHED** | The continuity document is, in the campaign's words, the one document Olympus can't write. No mission tries. |
| 14 | OP-03 Rubber-stamping | **PARTIAL** | M19's judgment preview prepares decisions; approval-latency instrumentation is absent. |
| 15 | HB-07 Review-absence flag as consent | **UNTOUCHED** | No merge-audit invariant in the program. |
| 16 | EW-09 Backup-chain exfiltration | **UNTOUCHED** | Custody-chain enumeration exists nowhere in the 25 missions. |
| 17 | CF-03 Policy bypass | **PARTIAL** | M7 makes classification events exist, so the coverage audit is *possible*; the audit and the side-door lockdown are not built. |
| 18 | TE-04 Restore resurrects autonomy | **UNTOUCHED** | Demotion-replay-forward and trust-floor-on-restore appear in no mission. |
| 19 | IS-05 ROI hallucination via human | **PARTIAL** | M17's three gates (score ≠ confidence ≠ decision) and the pursuit packet are the last line; source-citation fields that would catch it are not built. |
| 20 | MC-09 Report on stale evidence | **PARTIAL** | M15's both-days/≥2-obs rules resist fiction-into-trend; close-of-books re-verification is absent. |
| 21 | HB-06 Correlated blindness | **PARTIAL (thin)** | M4/M21's deterministic no-model-call spine is the one uncorrelated layer; implementation/review model correlation is untouched and permanent. |
| 22 | EW-06 Memory absorbs case facts | **PARTIAL** | M16's provenance makes case-rooted claims mechanically findable after the fact; recording-disable / per-matter stores are not built — and M16 created the retention hazard. |
| 23 | HM-04 Evidence truncation | **UNTOUCHED** | Governed-retention policy for mission evidence appears in no mission. |
| 24 | OR-01 Build Program drift | **PARTIAL** | M14's bottleneck discipline is the named containment; the mission-mix (who-benefited) metric is absent. Note the recursion: this document maps the Build Program's own drift risk. |
| 25 | IN-04 Silent model degradation | **UNTOUCHED** | Canary tasks and outcome baselines appear in no mission. |

**Tally: 1 fully/materially mitigated, 14 partial, 10 untouched.**

**Percentage of the Top 25 mitigated (fully or materially) by the completed Build Program**, scoring full = 1 and partial = 0.5:

> **(1 + 14 × 0.5) / 25 = 8 / 25 = 32%** — with honest error bars of roughly **±8 points (24–40%)**: the upside bar assumes the INFERRED rungs M1–M18 are all real and as strong as their documentation implies; the downside bar prices in that several PARTIAL verdicts (EW-10, OR-05, HB-06, CF-03) hang on doctrine or data-exists-but-nobody-reads-it ingredients. If one demands *material* mitigation only, the figure is **1/25 = 4%**.

**Verifying the campaign's final-question claim quantitatively** (rather than asserting it): the campaign's closing analysis says the erosion class and the expert-witness domain are largely outside event-shaped defenses. The mapping confirms it numerically:

- **Expert-witness cluster** (Top-25 ranks 1, 2, 3, 4, 16, 22 — six entries): 0 mitigated, 3 partial (all thin), 3 untouched → ~25% covered, and rank 1 is at zero.
- **Erosion/governance cluster** (ranks 5, 6, 7, 8, 9, 11, 12, 14, 15, 17, 24 — eleven entries): 0 mitigated, 8 partial, 3 untouched → ~36% covered, with every partial resting on an instrument (latency trend, parity audit, finding rate, coverage audit, mix metric) that the program does not build.
- The program's only clean kill (OP-06) and its strongest partials (MC-09, TE-07-detection, CF-05-floor) are exactly the entries where the campaign's containment *named a contract artifact* — the program covers what it was pointed at, and it was never pointed at the two dominant clusters.

---

## 5 — The top residual risks after a fully completed Build Program

1. **EW-04 — PHI to a cloud model endpoint** (Top-25 #1). Untouched, and M21 §10's hard exclusions (no gateway, no runtime, no routing changes) mean the program *structurally cannot* touch it. The single worst event remains ungoverned by any mission.
2. **EW-03 — Cross-case contamination** (Top-25 #3). Untouched; per-case isolation and citation-per-assertion live in no mission, and the program's own memory artifacts (M16) increase the surface.
3. **CF-08 — Fork evasion by decomposition** (Top-25 #6). Untouched; the program builds the classifier (M7) whose structural bypass this is, without the effect-level check that closes it — so the program's most important safety artifact ships with its known counterexample open.

Honorable mentions in the same tier: HB-03 (the reviewer flatlines and nothing measures it), TE-04 (a restore silently re-grants revoked autonomy), OR-06 (the letter only Chad can write), and OR-05 (every partial verdict above quietly assumes a reader).

**One-paragraph verdict:** the completed Build Program is a governance-and-evidence spine, and against the failure classes it was aimed at — packet integrity, escalation discipline, opportunity hygiene, trust-count honesty, attention economics — it performs: 19 scenarios materially covered, one Top-25 risk cleanly killed, and every wiring step honestly priced with the seam risks it introduces (MC-03/04 and TE-05 at the scout seam, MC-11 at the adapter seam, TE-07 at the memory-count seam, a self-reported metric at the leverage seam). But 62.5% of the weighted risk surface and 68% of the existential list remain uncovered, concentrated precisely where the campaign's final question predicted: the expert-witness blast radius and the silent-erosion class. The Build Program makes Olympus's loop real and auditable; it does not yet make Olympus's operator safe in his profession, nor the audit loop safe from its own success.

---

*Lane 5, design-only. Mission numbers M1–M18 are reconstructions and labeled INFERRED throughout; cite them as such. No code was modified and no implementation tasks were generated.*
