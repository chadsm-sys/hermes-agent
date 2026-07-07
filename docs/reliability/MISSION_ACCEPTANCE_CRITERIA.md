# Mission Acceptance Criteria — Build Program × Reliability Integration

**Olympus Reliability Integration Program.** One entry per existing Build Program mission (the 25-rung ladder of `BUILD_PROGRAM_RISK_MAPPING.md` §0 — mission numbering for M1–M18 is INFERRED; artifact names govern). For each mission: original objective, reliability additions (from `IMPLEMENTATION_INTEGRATION_MATRIX.md` — **none** where no win attaches), mandatory verification, mandatory receipts, MBP review requirements, and rollback expectations.

**Reading rules:**
- Missions 1–21 are **complete**. Their "reliability additions" are either *none* or *retrofit criteria* — work executed against the mission's original scope to complete its definition-of-done; never a new mission.
- Missions 22–25 are **remaining**. Their reliability additions are acceptance criteria that must pass before the mission is called done.
- "Mandatory receipts" = the evidence artifacts that must exist in the audit trail at closure (the campaign's evidence-or-silence rule applied to the program itself).
- Doctrine missions (M1–M5, M21) are documents: their verification is the **governance parity audit** subject — the written rule must match observed behavior (OR-02) — which the Win-3 conservation audit partially mechanizes.

---

## Completed rungs (M1–M21)

### Mission 1 — MISSION.md constitution [INFERRED]
- **Original objective:** roles (Brain/Assistant/Executive), North Star, Final Filter, division of labor.
- **Reliability additions:** none (doctrine).
- **Mandatory verification:** parity-audit subject — role boundaries observed in behavior (mutation-boundary checks under Win 3 cover the mechanical half; OR-04).
- **Mandatory receipts:** the document itself, versioned; any amendment via recorded decision.
- **MBP review requirements:** review any future diff to this document as a constitutional change (highest scrutiny class).
- **Rollback expectations:** constitutional documents do not roll back; they amend by ceremony (OR-02's rule).

### Mission 2 — HUMAN_FIRST boundaries + escalation doctrine [INFERRED]
- **Original objective:** six never-delegated boundaries; CONTINUE/PAUSE/NEEDS_CHAD doctrine; conservative defaults.
- **Reliability additions:** none to the document. Its enforcement gaps are closed downstream: Win 8 (effect-level classification, M7 retrofit) and Win 4's CF-05 default-execution metric (M25).
- **Mandatory verification:** parity audit — defaults never spend/send/bind (auditable via decision log); "new category ⇒ NEEDS_CHAD" honored (novel-action classifications sampled).
- **Mandatory receipts:** decision-log entries for every boundary-class action.
- **MBP review requirements:** constitutional-change scrutiny on any diff.
- **Rollback expectations:** amend by ceremony only.

### Mission 3 — PHILOSOPHY doctrine [INFERRED]
- **Original objective:** asset-first doctrine; attention economy; never chase autonomously.
- **Reliability additions:** none (doctrine). Win 4's consumption metrics (M25) give its attention doctrine a number.
- **Mandatory verification:** parity audit — interrupt volume near design target (OP-06); scout never pursues (audit: zero pursuit actions without packets).
- **Mandatory receipts:** as M1.
- **MBP review requirements:** constitutional-change scrutiny.
- **Rollback expectations:** amend by ceremony only.

### Mission 4 — DECISION_ENGINE doctrine [INFERRED]
- **Original objective:** evidence-first claims; determinism; no model calls in the spine.
- **Reliability additions:** none to the document. The no-model-calls invariant becomes a standing verification below.
- **Mandatory verification:** the deterministic-spine invariant is test-enforced (the campaign notes it is "banned by both codebases' tests") — those tests remain green in every touching PR; IN-03's degradation property depends on it.
- **Mandatory receipts:** the invariant tests, cited in reviews of any spine-adjacent change.
- **MBP review requirements:** any diff introducing a model call into ranking/classification/status paths is an automatic reject.
- **Rollback expectations:** amend by ceremony only.

### Mission 5 — BOTTLENECK + COMPOUND + COACH doctrine; foundation READY [INFERRED]
- **Original objective:** the remaining foundation docs; `CHIEF_OF_STAFF_FOUNDATION_READY`.
- **Reliability additions:** none (doctrine). Its latent TE-07 surface is closed at M24 (Win 7).
- **Mandatory verification:** parity audit — ONE-recommendation discipline observed in packets (MC-10).
- **Mandatory receipts:** as M1.
- **MBP review requirements:** constitutional-change scrutiny.
- **Rollback expectations:** amend by ceremony only.

### Mission 6 — Contracts + schema versioning [INFERRED]
- **Original objective:** `SCHEMA_VERSION`, major-match rule, additive-only 1.x fields.
- **Reliability additions:** none new — but note the mission's own seam cost (a major bump requires simultaneous two-repo change); the M23 adapters inherit this as a deployment-ordering criterion there.
- **Mandatory verification:** version-skew test: a 1.x consumer parses a newer 1.y packet unchanged; an unknown-major packet is refused whole.
- **Mandatory receipts:** the skew tests in CI; refusal events logged when they occur.
- **MBP review requirements:** any field removal/rename without a major bump is an automatic reject.
- **Rollback expectations:** additive fields are ignorable by construction — rollback is dropping the producer side.

### Mission 7 — Escalation classifier [INFERRED] — **retrofit target (Win 8, Win 3 support)**
- **Original objective:** `classify_work`: deterministic first-match-wins rule table; PAUSE requires resume plan; one question max.
- **Reliability additions:** (1) **Effect-level classification** (Win 8): every external-effect execution path re-classifies the composite effect at the last hop, regardless of upstream verdicts; the effect-hop inventory is enumerated and Chad-ratified. (2) **Queryability** (Win 3 support): classification events expose a read-only query surface for the conservation audit (work ⇔ classification, including effect hops). (3) Standing rule: every new tool/channel added to Olympus arrives with its classification rules (CF-01's lesson) — checked at review.
- **Mandatory verification:** decomposed-send harness test caught at the final hop (CF-08); rule-table edits covered by regression tests over the existing classifications (CF-02 guard).
- **Mandatory receipts:** ratified effect-hop inventory in the decision log; classification-coverage line in the conservation audit at zero unclassified work.
- **MBP review requirements:** verify first-match-wins semantics unchanged; verify the addition is call sites only (no new decision machinery — synthesis §3.2 scope line); reject any capability PR lacking classification rules.
- **Rollback expectations:** removing effect-hop calls restores the CF-08-exposed baseline — permitted only via NEEDS_CHAD packet (safety-branch relaxation).

### Mission 8 — Morning Brief parser [INFERRED]
- **Original objective:** all-or-nothing parse; `MorningBriefError`; refuse whole, never partial-trust.
- **Reliability additions:** none — the artifact is itself a named containment (MC-11). Never make parsing lenient (explicit anti-criterion).
- **Mandatory verification:** malformed-packet test refuses whole; consumer answers from last-good state with `degraded=True`.
- **Mandatory receipts:** refusal tests in CI; degraded events logged.
- **MBP review requirements:** any leniency-adding diff to parse behavior is an automatic reject.
- **Rollback expectations:** n/a (behavior is the safety property).

### Mission 9 — Evening Report parser [INFERRED]
- **Original objective:** `parse_evening_report`; honest `degraded`; both-days rule carried to consumer.
- **Reliability additions:** none here; the producer-side close-of-books re-verification it cannot do lands as Win 3 criterion 1 under M23 (MC-09).
- **Mandatory verification / receipts / MBP / rollback:** as M8.

### Mission 10 — MC executive state machine [INFERRED]
- **Original objective:** 10 states / 9 events; ESCALATING has no CONTINUE; UNKNOWN first-class; evidence-required transitions.
- **Reliability additions:** none to the machine (MC-07's wedge is containment working). The formal-RESOLVE UX debt is noted, not built (would be redesign).
- **Mandatory verification:** transition-table exhaustiveness tests stay green; ESCALATING-age surfaces in every Morning Packet until resolved (existing behavior, now audited by Win 3).
- **Mandatory receipts:** RESOLVE events always carry reasons (audit query).
- **MBP review requirements:** reject any diff adding a CONTINUE row to ESCALATING or an unevidenced transition.
- **Rollback expectations:** n/a (the constraints are the artifact).

### Mission 11 — Evidence feeds + closed source allowlist [INFERRED] — **retrofit target (Wins 6, 7)**
- **Original objective:** `record_signal` with a closed source allowlist.
- **Reliability additions:** (1) **Recorder-side validation** (Win 7 retrofit): unique/idempotent observation identity; reality-terminated provenance required; rejects counted as a feed metric. (2) **Horizon record type** (Win 6 retrofit): the feed carries dated-horizon records (expiries, recheck dates, ages, lags).
- **Mandatory verification:** replay test (duplicate event ⇒ one record + logged reject); circular-provenance test (Hermes-output-rooted observation ⇒ rejected); allowlist unchanged (no new sources — M21 contract's own point).
- **Mandatory receipts:** reject counters visible in the feed; validation tests in CI.
- **MBP review requirements:** verify validation applies to *all* allowlisted sources, not only new ones; verify no allowlist expansion rode along.
- **Rollback expectations:** validation-off flags restore prior behavior; relaxation requires a packet (re-opens TE-05/TE-07).

### Mission 12 — Attention router [INFERRED] — **retrofit target (Win 4 support)**
- **Original objective:** four evidence-backed interrupt classes, deny-by-default; deferrals to `waiting_for_you`.
- **Reliability additions:** acknowledgment/latency event emission for interrupts and packet deliveries (read-only; feeds M25's LeverageStore).
- **Mandatory verification:** deny-by-default regression (a fifth-class item never pages); ack events present for every delivery in a sample window.
- **Mandatory receipts:** ack-event log lines; the OP-10 dead-man convention documented in the runbook (no Morning Packet ⇒ alarm).
- **MBP review requirements:** verify the addition observes without altering routing decisions.
- **Rollback expectations:** stop emitting events; router behavior untouched.

### Mission 13 — Decision Engine implementation [INFERRED]
- **Original objective:** deterministic ranking; `why_chosen` receipts.
- **Reliability additions:** none — receipts-at-presentation is already the IS-06 defense. IS-10's monoculture is addressed by the existing portfolio-review packet mechanism (campaign IS-10), not by this program.
- **Mandatory verification:** determinism test (same inputs ⇒ same scores); receipts render raw economics (a 12× error is conspicuous).
- **Mandatory receipts:** `why_chosen` present in every ranked presentation.
- **MBP review requirements:** reject model calls in ranking (M4 invariant).
- **Rollback expectations:** n/a.

### Mission 14 — Bottleneck Engine implementation [INFERRED]
- **Original objective:** ONE evidence-backed-or-null recommendation.
- **Reliability additions:** none. (The mission-mix metric OR-01 wants is Chad-side portfolio review via existing packet machinery; adding an engine metric here would be new architecture.)
- **Mandatory verification:** null-honesty test (no evidence ⇒ null, never a guess); one-recommendation invariant regardless of queue depth (MC-10).
- **Mandatory receipts:** recommendation receipts in packets.
- **MBP review requirements:** standard, plus M4 invariant.
- **Rollback expectations:** n/a.

### Mission 15 — Compound Engine v2 [INFERRED]
- **Original objective:** 7 dimensions; honest UNKNOWN; both-days rule; ≥2 obs on ≥2 days.
- **Reliability additions:** none directly — its promotion-integrity rules are the artifact; the feeds it consumes are hardened at M11/M24 (Win 7), which is where its TE-07 surface is closed.
- **Mandatory verification:** both-days/≥2-obs regressions; UNKNOWN dimensions honestly reported (`reserved_feed ... not wired` until M24 lands).
- **Mandatory receipts:** dimension statuses in Evening Reports.
- **MBP review requirements:** reject any growth claim path bypassing the observation rules.
- **Rollback expectations:** n/a.

### Mission 16 — memorygraph provider [INFERRED rung] — **retrofit target (Win 9)**
- **Original objective:** governed claims (candidate/established/core); evidence-gated promotion; contradictions flagged, never auto-resolved; own store, own writer.
- **Reliability additions:** **restore-reconciliation** (Win 9): ledger restore ⇒ trust floor until gap-window events replay forward; demotions never resurrect (TE-04). Also inherits EW-06's standing rule at the boundary: expert-witness contexts never record to the general graph (enforced at M22's boundary criteria, verified here by provenance audit).
- **Mandatory verification:** restore drill with synthetic gap-window demotion surviving; provenance audit shows zero EW-rooted chains.
- **Mandatory receipts:** drill transcript; drill date on the horizon ledger; contradiction-queue age visible (TE-02 requires the queue be worked, per OR-05).
- **MBP review requirements:** verify the replay-forward branch and the trust-floor hold with tests.
- **Rollback expectations:** restore-mode flag off ⇒ prior behavior; flag state is conservation-audited (a disabled safety mode is HB-07-shaped).

### Mission 17 — opportunity_scout engine [INFERRED rung]
- **Original objective:** deterministic 0–100 scoring; atomic JSON store; inbox ingestion; exact+fuzzy dedup; `ALLOWED_TRANSITIONS`.
- **Reliability additions:** none new here — the engine's own conventions (fingerprints, atomic writes, corrupt-file backup, terminal states) are named containments (IS-01/02/07/08/09). Its feed seam is hardened at M22 (Win 7). Semantic load-validation (IS-07: every stage ∈ enum, transition chains legal) is confirmed as within original scope; if absent, it is a retrofit criterion here.
- **Mandatory verification:** fingerprint-replay test (re-ingested processed/ files ⇒ loud rejects); semantic invariant validation at load; terminal-state stickiness (revival requires packet — IS-09).
- **Mandatory receipts:** reject-count spikes alarmed; transition events carry reasons.
- **MBP review requirements:** reject schema changes without round-trip tests (HB-04's escaped defect was exactly this).
- **Rollback expectations:** store validation fail-loud is the safety property; never make loads lenient.

### Mission 18 — MC packet producers + MissionStore [INFERRED] — **retrofit target (Wins 9, 3 support)**
- **Original objective:** executive packet producers; fail-loud `MissionStore` (`.corrupt-<ts>` convention).
- **Reliability additions:** (1) **Restore-reconciliation** (Win 9): restore ⇒ dispatch freeze ⇒ ground-truth diff ⇒ Chad-accepted reconciliation packet ⇒ resume; mission-ID collision check post-restore. (2) **Queryability** (Win 3 support): read-only state queries for the conservation audit.
- **Mandatory verification:** restore drill transcript (freeze/diff/packet/resume); corrupt-load test (backup aside, refuse dispatch).
- **Mandatory receipts:** drill on the horizon ledger; reconciliation packets in the decision log.
- **MBP review requirements:** verify the freeze cannot be bypassed by ordinary dispatch paths.
- **Rollback expectations:** as M16 — flag off with audit visibility.

### Mission 19 — Executive Coach (`coach()`) [DOCUMENTED]
- **Original objective:** evidence-gated coaching; recommendation-without-evidence structurally unreachable; UNKNOWN when absent.
- **Reliability additions:** none.
- **Mandatory verification:** the structural-unreachability property covered by tests; UNKNOWN honesty regression.
- **Mandatory receipts:** coaching recommendations always cite evidence in packets.
- **MBP review requirements:** standard.
- **Rollback expectations:** n/a.

### Mission 20 — Adaptive conversation (LEARNING intent) [DOCUMENTED]
- **Original objective:** LEARNING intent consumes `learning_recommendation` as a pure consumer.
- **Reliability additions:** none.
- **Mandatory verification:** pure-consumer property (no state invented — M1 division of labor); absent field ⇒ honest absence.
- **Mandatory receipts:** conversation answers cite packet fields.
- **MBP review requirements:** standard.
- **Rollback expectations:** n/a.

### Mission 21 — Executive Operating Loop contract [DOCUMENTED]
- **Original objective:** doc-only contract: seams, payload shapes, governance rules, invariants 1–6, wiring roadmap.
- **Reliability additions:** none to the contract (changing it would be new governance). The Integration Matrix operates strictly inside its invariants — notably invariant 6 (expert-witness isolation) which Wins 1–2 enforce, and invariant 1 (evidence or silence) which Wins 3–5 instrument.
- **Mandatory verification:** parity audit — each wiring mission's implementation matches its contracted payload shape and governance rule.
- **Mandatory receipts:** contract-version declarations in live packets.
- **MBP review requirements:** wiring PRs reviewed against the contract text clause by clause.
- **Rollback expectations:** contract amendments by ceremony only (major-bump rule).

---

## Remaining rungs (M22–M25) — reliability criteria are part of definition-of-done

### Mission 22 — Wiring 1: Opportunity Scout → MC inbox feed [DOCUMENTED] — **absorbs Wins 1, 2, 7(a); hosts Win 5's boundary canaries**
- **Original objective:** `POST /opportunities` under the reserved extension contract; allowed sources only; expert-witness sources rejected at the boundary; the engine never fetches; neither side reranks the other.
- **Reliability additions:**
  - **Win 1:** EW workspace egress pin + per-request egress log; in-workspace refusal test. (Chad approves the endpoint allowlist by packet.)
  - **Win 2:** default-deny for unscannable content; dispatch-time marker check on mission content; scheduled marker/metadata/OCR sweep of general surfaces; rejection events logged and counted.
  - **Win 7(a):** idempotent `POST /opportunities` (unique event identity; replay ⇒ logged no-op); sent-vs-received reconciliation query for the conservation audit.
  - **Win 5 (cross):** boundary test-document corpus (text/image/archive/encoding) maintained and periodically re-fired as canaries.
- **Mandatory verification:** all four boundary-format rejections; replay no-op test; egress refusal test; a synthetic marker-positive mission bounced at dispatch.
- **Mandatory receipts:** test transcripts; first clean sweep line in an Evening Report; Chad's allowlist packet; reject counters live in the feed.
- **MBP review requirements:** clause-by-clause against the M21 contract's section 6; default-deny semantics verified; pin verified workspace-scoped, not global.
- **Rollback expectations:** feed endpoint revertible whole (the mock-inbox era resumes — documented degraded state); boundary/egress criteria do **not** roll back with it (they attach to the isolation invariant, not the feed); any safety-branch relaxation requires a packet.

### Mission 23 — Wiring 2: MorningBrief/EveningReport adapters + wheel inclusion [DOCUMENTED] — **absorbs Wins 3, 6, 10**
- **Original objective:** adapters reading MC's reserved GET routes; `chief_of_staff` included in the wheel; the rituals go live end-to-end.
- **Reliability additions:**
  - **Win 3:** the conservation audit ships with the rituals it reports through — ~10 books-balance checks, one Evening Report line, verified-quiet week before trust, canary-imbalance proof.
  - **Win 6:** horizon ledger surfaced in the Morning Packet's existing `waiting_for_you`/loop section (expiries, recheck dates, queue ages, push/backup lag); never as interrupts.
  - **Win 10:** boot-as-deployment gates the runtime this mission ships — environment manifest (including provider-routing hash), boot self-check (locks, worktrees, store probe, auth probes) holding the queue until green; failed check = one platform-event PAUSE.
  - **Inherited from M6:** two-repo deployment ordering documented (adapter and producer versions matched; skew ⇒ clean refusal, MC-11 behavior).
- **Mandatory verification:** ritual round-trip live for a week; audit quiet-week + caught-canary; reboot drill (manifest diff ⇒ queue held ⇒ acknowledged ⇒ released); one horizon save demonstrated.
- **Mandatory receipts:** consecutive ritual deliveries with acknowledgments; audit lines; drill transcripts; horizon section rendering real data.
- **MBP review requirements:** adapters reviewed against contract sections 2–3 (field mappings, all-or-nothing); audit checks reviewed against their invariant definitions; queue-gate verified to actually block.
- **Rollback expectations:** adapters revertible (consumers return to last-good-state behavior — already the designed degraded mode); audit and gate independently disableable with conservation-audit visibility of the disabled state; wheel inclusion revert documented.

### Mission 24 — Wiring 3: memory-graph counts as compound observations [DOCUMENTED] — **absorbs Wins 5, 7(b)**
- **Original objective:** governed caller records `memory_claims_established` counts through MC's existing recorder; `hermes-agent` already allowlisted; knowledge-growth dimension leaves UNKNOWN until wired.
- **Reliability additions:**
  - **Win 7(b):** reality-terminated provenance enforced at the recorder (observation chains must end outside Hermes output — the campaign's named TE-07 surface for exactly this mission); idempotent observation identity; reject counter as replay alarm.
  - **Win 5:** the canary program rides this mission's recorder — reviewer canaries, model-baseline tasks, audit canaries, all recorded with explicit canary provenance (never countable as organic); missed canary ⇒ four-class-eligible alarm.
- **Mandatory verification:** circularity test (Hermes-output-rooted observation rejected); replay test; first canary cycle (reviewer canary rejected with diff-grounded reasons; baseline diffs in band; audit canary caught); one missed-canary drill proving the alarm.
- **Mandatory receipts:** reject counters; canary-tagged observations distinguishable by provenance in every count; knowledge-growth dimension flips from UNKNOWN only on reality-terminated data.
- **MBP review requirements:** the promotion-symmetry clause of contract section 7 verified (contradicted claims never promote; ≥2 obs on ≥2 days); provenance validation branch tested, not just present.
- **Rollback expectations:** recorder wiring revertible (dimension returns to honest UNKNOWN — the designed pre-wiring state); provenance validation does not roll back with it (M11 retrofit keeps it for all feeds); relaxation ⇒ packet.

### Mission 25 — Wiring 4: LeverageStore consuming `attention_saved` [DOCUMENTED] — **absorbs Win 4**
- **Original objective:** `LeverageStore` implementation consuming the Evening Packet's `attention_saved` (declared minute costs only).
- **Reliability additions:**
  - **Win 4:** the store also records per-packet decision latency, answer class, and packet class; Evening Report derives decision-latency trend, default-execution rate per class (CF-05), and consumption depth (OR-05); threshold meta-packets on the two constitutional floors (delegation-made-explicit; audit-loop-resize) via the ordinary NEEDS_CHAD channel.
- **Mandatory verification:** declared-cost honesty preserved (no inferred minutes); two weeks of metrics rendering; one synthetic threshold-crossing ⇒ exactly one meta-packet.
- **Mandatory receipts:** LeverageStore rows for every packet in the window; the three metric lines in consecutive Evening Reports.
- **MBP review requirements:** verify metrics are observational only (no routing/priority behavior keyed to them — that would be new architecture); verify meta-packet thresholds conservative (rare by design; OP-06 guard).
- **Rollback expectations:** additive fields and report lines — droppable without residue; meta-packets stop with the metrics.

---

## Closure rule for the whole program

A mission (or retrofit) is **done** when: its verification set passed in a recorded transcript, its receipts exist in the audit trail, its MBP review verdict is recorded, and its rollback path is documented and (where a flag exists) conservation-audit-visible. This is the campaign's own evidence-or-silence rule applied to the Build Program — no mission closes on assertion.
