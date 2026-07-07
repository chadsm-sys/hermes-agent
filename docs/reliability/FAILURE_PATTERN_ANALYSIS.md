# Olympus Failure Pattern Analysis — Top 20 Root Causes

**Lane 2 of the Olympus Reliability Intelligence Campaign.**
**Status:** Design-only analysis. No code changes, no implementation tasks, no governance changes, no architecture redesign.
**Source of truth:** `docs/reliability/olympus-failure-injection-campaign-v1.md` (100 scenarios: OP-01..10, MC-01..12, HM-01..12, HB-01..09, TE-01..10, CF-01..09, IS-01..10, EW-01..10, IN-01..12, OR-01..06, plus the Top 25 existential ranking). Every claim below cites that document's own scenarios, containment vocabulary, and detection mechanisms.

**Method.** Each of the 100 scenarios was assigned to the underlying mechanism(s) that generate or materially amplify it. Mechanisms were then scored **frequency × impact**, where frequency = count of scenarios generated/amplified, and impact = worst-case impact class the cause feeds (Existential=5, Critical=4, High=3, Medium=2, per the campaign's own scale); ties broken first by number of Top-25 existential entries touched, then by highest Top-25 rank reached. A scenario may appear under multiple root causes; the coverage math at the end counts distinct scenarios (union), and states the multi-counting explicitly.

---

## (a) Summary table

| Rank | Root cause | Freq | Top-25 touched | Smallest mitigation (five words) |
|---|---|---|---|---|
| 1 | RC-03 Single-human constitutional dependency | 9 | 1 | Do-nothing defaults never spend/send/bind |
| 2 | RC-04 Missing event/identity idempotency | 10 | 0 | Unique event IDs; evening reconciliation |
| 3 | RC-01 Detection terminates in an unread human | 7 | 4 | Measure the reader; threshold meta-packet |
| 4 | RC-02 Custody is a composition property | 7 | 4 | Custody audit walks every hop |
| 5 | RC-05 Governance amended without ceremony | 8 | 2 | Parity audit: ratify or revoke |
| 6 | RC-08 Silence indistinguishable from health | 10 | 0 | Dead-man rituals; age-in-state alarms |
| 7 | RC-07 Aggregate drift below per-item detection | 7 | 4 | Aggregate-shape trends in Evening Report |
| 8 | RC-06 Ingestion boundary is a human habit | 7 | 2 | Plausibility bands; source-cited evidence |
| 9 | RC-10 Finite recognizer passes the unrecognizable | 5 | 3 | Default-deny unrecognized; classify effects |
| 10 | RC-09 Work reaching effects without the gate | 5 | 3 | Coverage audit: every effect classified |
| 11 | RC-17 Substrate mutates itself without provenance | 5 | 2 | Manifest diff alarms; safety-critical pins |
| 12 | RC-20 Audit trail under-governed for its role | 5 | 2 | Trail is governed, production-ready data |
| 13 | RC-11 Correlated cognition: one model, many hats | 6 | 4 | Deterministic checks; weighted human sampling |
| 14 | RC-16 Controls never rehearsed or affirmatively tested | 6 | 2 | Rehearsal calendar: canaries, drills, restores |
| 15 | RC-15 Restore without reconciliation | 6 | 1 | Post-restore freeze; replay demotions forward |
| 16 | RC-19 Time and expiry calendars unmanaged | 8 | 0 | Surface expiry horizons weeks ahead |
| 17 | RC-13 State asserted without counterpart evidence | 7 | 1 | Unconfirmed remote claims decay UNKNOWN |
| 18 | RC-18 Common-cause events misread as many failures | 7 | 0 | Storm window: probe, don't fix |
| 19 | RC-14 Evidence without freshness dating or decay | 6 | 1 | Evidence carries its date everywhere |
| 20 | RC-12 Self-referential evidence (circular provenance) | 4 | 4 | Reality-terminated provenance at recorder |

Note on rank 20: RC-12 places last by the frequency×impact arithmetic (only 4 scenarios), yet all 4 of its scenarios sit on the Top-25 existential list — it is the highest impact-density cause in the table. The ordering method is stated and followed; the density is flagged so it isn't misread as "least important."

---

## (b) Detailed entries

### 1. RC-03 — Single-human constitutional dependency
**Root cause:** All credentials, judgment, authority, physical presence, and even the reviewer's hardware ride on one human whose attention window is ~90 minutes/day and whose duty cycle includes call shifts, fatigue, travel, and eventually permanent absence.
**Frequency:** 9 — OP-01, OP-02, OP-04, OP-05, HM-09 (GUI prompt needs a physical finger), HM-10, HB-02 (the reviewer laptop travels with Chad), IN-09, OR-06.
**Impact:** Existential — OR-06 (Top-25 #13) is the designed-in terminal vulnerability; OP-02 is Critical (wind-down by starvation). The campaign's Final Question names Chad's attention as the true single point of failure.
**Smallest mitigation:** The packet mechanism's constitutional default clause — "a non-answer is always safe; do-nothing must never spend, send, or bind" (OP-01/OP-05/CF-05 containment) — converts every operator-absence scenario from a safety event into a throughput event; the queued NEEDS_CHAD packets *are* the containment. (OR-06's far edge needs the one artifact the doc says Olympus can't write: the continuity document.)

### 2. RC-04 — Missing event/identity idempotency
**Root cause:** Every channel in the system (dispatch, evidence recording, packet delivery, answer application, inbox ingestion) is at-least-once in practice, but events lack a unique identity strong enough to answer "have I seen this exact event before?"
**Frequency:** 10 — MC-03, MC-12, TE-01, TE-05, CF-04 (identity of *decisions*), CF-06, CF-07, IS-02 (identity of *opportunities*), IS-08, IN-02 (double-created PRs from ambiguous timeouts; amplified).
**Impact:** Critical — MC-12 (split-brain re-dispatch, Critical) and TE-05 (trust inflation across many claims). It is also the upstream feeder of TE-04-class resurrections. The doc's own words: "evidence counting is only as honest as event identity" (TE-01).
**Smallest mitigation:** Provenance-keyed idempotent recording plus the Evening Report's reconciliation-by-ID: "execution must be treated as possibly-duplicated and reconciled by mission ID *every evening*, not just when suspicion arises" (MC-03); the recorder rejects observation IDs already seen (TE-05); answers are durable events re-applied until confirmed (CF-07).

### 3. RC-01 — Detection terminates in an unread human
**Root cause:** Nearly every detection path in the campaign ends "…surfaced in the report/queue" — and six months of green trains the one reader to skim, rubber-stamp, mute, or let defaults govern, disarming the detection layer wholesale.
**Frequency:** 7 — OP-03, OP-05, OP-06, CF-02 (amplifier: packet spam manufactures the fatigue), CF-05, TE-02 ("a safety queue nobody reads is not a safety queue"), OR-05.
**Impact:** Existential-class multiplier — OR-05 (Top-25 #7) "disarms the detection layer of roughly forty scenarios simultaneously"; also OP-03 (#14), OP-06 (#10), CF-05 (#9). Four Top-25 entries, the most human-shaped cluster on the list.
**Smallest mitigation:** The campaign's consumption metrics: report-acknowledgment depth, queue-work rates, and the decided-by-Chad rate as first-class Evening Report numbers, with the OR-05/CF-05 meta-packet when they cross the floor ("either resize the audit to what you will actually do, or schedule it"). The system must measure its reader.

### 4. RC-02 — Custody is a composition property, enforced at only one perimeter
**Root cause:** Expert-witness isolation is asserted at the ingestion boundary while copies, metadata, memory claims, model routing, task dispatch, and backup chains each propagate case material through hops no single decision approved.
**Frequency:** 7 — EW-03, EW-04, EW-05, EW-06, EW-07, EW-08, EW-09.
**Impact:** Existential — EW-04 (Top-25 #1, "the single worst event Olympus can produce"), EW-03 (#3), EW-06 (#22), EW-09 (#16). The doc: "custody is a property of the *composition* of storage systems, not of any component."
**Smallest mitigation:** EW-09's data-flow enumeration generalized: a scheduled audit that walks each isolated store's *actual* chain — copies, sync hops, model endpoints (EW-04's egress log), memory recording paths (EW-06), metadata surfaces (EW-08's marker scan) — against an approved custody list, alarming on any hop not on it. One audit shape covers all seven scenarios because they are all unenumerated hops.

### 5. RC-05 — Governance amended without ceremony
**Root cause:** Rules, instructions, resolutions, and authority scopes change through verbal remarks, hand edits, convenience flags, and inferred precedent instead of the recorded decision channel — so the operative constitution silently diverges from the written one.
**Frequency:** 8 — OP-07 (conversational instruction vs. published plan), OP-08, OP-09, MC-07 ("verbal resolutions don't exist"), HB-07, TE-08 ("authority is granted, never inferred from precedent"), OR-02, OR-04.
**Impact:** Critical — OR-02 (Top-25 #8: "a boundary made of exceptions holds until precisely the day it matters") and HB-07 (#15, the concrete mechanism by which OR-02 kills).
**Smallest mitigation:** OR-02's governance parity audit on a schedule — written rules diffed against observed behavior (merge audits, classification coverage, packet rates) — with its ratify-or-revoke discipline: every discovered exception either becomes a recorded rule via Chad or is revoked; "there is no third state."

### 6. RC-08 — Silence indistinguishable from health
**Root cause:** Absence of signal — a dead channel, a sleeping reviewer, a mission that produced nothing, a slow machine, an unreachable inbound path — reads as good news by default, so failures with no error message age unbounded.
**Frequency:** 10 — OP-10, MC-02, MC-04, HM-03 (the silent variant: working while persisting nothing), HB-01, HB-02, HB-08 ("up and capable are different states"), CF-06, IN-05, IN-12.
**Impact:** High — no Top-25 entries (the architecture's holds are safe), but this is the constitution's named nightmare ("silence must be trustworthy") and the largest single cluster of unbounded-duration stalls.
**Smallest mitigation:** The two daily rituals as dead-man switch — "no Morning Packet by 9am must mean *emergency*, not 'nice, a quiet day'; that convention costs nothing and bounds every silent-channel failure at 24 hours" (OP-10) — paired with age-in-state / queue-age thresholds (MC-04's dispatched-with-no-evidence → PAUSE, HB-01's review-queue age).

### 7. RC-07 — Aggregate drift below per-item detection
**Root cause:** Every item is individually defensible while the *sum* — mission mix, ranking shape, default-execution rate, exception count, queue depth — drifts into a strategy nobody chose; per-event detectors are structurally blind to it.
**Frequency:** 7 — OP-03 (decision-latency trend), MC-10, CF-05, IS-03 (volume capture), IS-10, OR-01, OR-02.
**Impact:** Critical — OR-01 (Top-25 #24), OR-02 (#8), CF-05 (#9), OP-03 (#14). The doc: "the dangerous outputs aren't wrong items — they're six months of individually-defensible items whose *sum* nobody chose" (IS-10).
**Smallest mitigation:** Aggregate-shape reporting in the existing rituals: mission-mix by beneficiary (OR-01), portfolio shape vs. declared intent (IS-10), source-concentration bands (IS-03), default-execution and packet-rate trends (CF-05/CF-02) — each ending in the periodic review packet the campaign already prescribes ("aggregates need review rituals just like decisions do").

### 8. RC-06 — The ingestion boundary is a human habit
**Root cause:** The system's no-scraping, human-entered-evidence design means every input arrives through Chad's own hands — forwarding habits, fatigued typing, hand edits, LLM paste-ins, mis-sorted folders — so the trusted channel is exactly the unvalidated one.
**Frequency:** 7 — IS-01, IS-03, IS-05, IS-06, IS-07, TE-02 (bad ingest poisons a core claim), EW-01 (mis-saved case PDF).
**Impact:** Critical — EW-01 (Top-25 rank-4 gateway event) and IS-05 (#19: "the one gate the architecture relies on is bypassed by the human himself"). The doc: "every poisoning arrives through Chad's own hands — the ingestion boundary is a human habit, not an API" (IS-03).
**Smallest mitigation:** Ingest-time plausibility/sanity bands with flag-for-review (IS-01/IS-06's economics-outside-percentile flags) plus the source-citation rule: evidence that cites no verifiable source can't be marked STRONG (IS-05) — "provenance must name the *source*, not just the typist."

### 9. RC-10 — A finite recognizer passes what it cannot recognize
**Root cause:** Classifiers, scanners, and dedup thresholds are keyed to known shapes in an open world; novel shapes, decomposed composites, opaque formats, and sub-threshold variants pass *because* they weren't recognized — the opposite of the constitutional "uncertain → more conservative."
**Frequency:** 5 — CF-01, CF-08, EW-02 ("a scanner that passes what it cannot read is a gate that opens for the biggest trucks"), EW-05 (ambiguous phrasing unrecognized as case work), IS-02 (0.79 vs 0.82 threshold false negative).
**Impact:** Existential-class — CF-01 (Top-25 #5: "one silent boundary violation costs more trust than a thousand correct escalations earn"), CF-08 (#6), EW-02 (rank-4 gateway).
**Smallest mitigation:** Two applications of existing doctrine: default-deny the unscannable/unrecognized ("'I couldn't check it' and 'it's clean' must be opposite verdicts," EW-02; "new category, never explicitly granted → NEEDS_CHAD by definition," CF-01) and effect-level re-classification at the last hop before an external effect (CF-08: "classify effects, not tasks").

### 10. RC-09 — Work reaching effects without passing the gate
**Root cause:** Execution paths accumulate around the classification/review gates — cron jobs, manual habits, convenience flags, mis-routed dispatches — so governance guarantees cover a shrinking fraction of actual work.
**Frequency:** 5 — OP-09, CF-03, CF-08 (the composite never shown to the classifier), HB-07, EW-05.
**Impact:** Existential-class — CF-08 (#6), CF-03 (#17: "the contract only protects work it sees"), HB-07 (#15). "Governance coverage decays one convenient shortcut at a time."
**Smallest mitigation:** The coverage audit the campaign defines twice: every unit of work in the execution logs must reference a classification event (CF-03), and every merge must reference a review verdict (HB-07's merge-audit, "a page-level alarm regardless of mission class") — the invariant to monitor is "does *all* work pass through it," not "does the gate work."

### 11. RC-17 — The substrate mutates itself without provenance
**Root cause:** OS updates, auto-updating toolchains, provider model revisions, restored defaults, and ISP changes alter the environment between missions with no corresponding recorded change — so behavior shifts have no first suspect and pinned assumptions silently invert.
**Frequency:** 5 — HM-09, HM-12, IN-04, EW-04 (routing "restored after an update" — drift with existential blast radius), IN-12.
**Impact:** Existential — EW-04 (Top-25 #1) and IN-04 (#25). "The environment is an input to every mission and it changes itself" (HM-12).
**Smallest mitigation:** The environment manifest with diff-on-change (HM-12/HM-09: treat every reboot as a deployment, verified by manifest before trusting it with work), with provider-routing config treated as a *safety-critical* manifest and the expert-witness endpoint pin enforced per-workspace, "as close to the data as possible," never by global default (EW-04).

### 12. RC-20 — The audit trail is under-governed relative to its load-bearing role
**Root cause:** Mission evidence is simultaneously the product (the basis of all trust and CONTINUE legitimacy) and, in litigation work, a discoverable exhibit — yet it is handled like rotatable telemetry, poisoned by flaky hosts, and never curated for hostile reading.
**Frequency:** 5 — HM-03, HM-04 ("losing the transcript of successful work is worse than losing the work"), HM-11 (a flaky host poisons the evidence before it stops the work), TE-03 ("the ledger's recoverability rests entirely on the evidence trail's integrity"), EW-10 (the process becomes the exhibit).
**Impact:** Existential — EW-10 (Top-25 #2: Olympus working as designed becomes the attack surface) and HM-04 (#23).
**Smallest mitigation:** HM-04's retention rule generalized: mission evidence is governed data, excluded from pressure-driven rotation (caches die first), evidence-completeness sampled in the Evening Report — and, for the expert-witness domain, kept organized to *prove the division of labor Chad testifies to* (EW-10's documented-methodology posture).

### 13. RC-11 — Correlated cognition: one model wearing every hat
**Root cause:** Implementation, review, packet drafting, and even the operator's own LLM-assisted research share one foundation-model worldview, so the errors the system makes are exactly the errors it cannot see — the two-machine independence is partly illusory.
**Frequency:** 6 — HB-03, HB-04 (the escaped-defect instance; amplified), HB-06, HB-09 (independence lost to shared narrative), IN-04, IS-05.
**Impact:** Critical — four Top-25 entries: HB-03 (#11), HB-06 (#21), IN-04 (#25), IS-05 (#19). The Final Question's second failure class verbatim.
**Smallest mitigation:** HB-06's uncorrelated layer: deterministic non-model checks (tests, invariant audits, schema validation, canary defects) "are the only layer whose failures don't correlate with the model's," plus Chad's spot-check sampling weighted toward escaped-defect classes both stages have missed before.

### 14. RC-16 — Controls never rehearsed or affirmatively tested
**Root cause:** Gates, backups, runbooks, and recovery procedures are presumed healthy because they haven't visibly failed; nothing periodically *exercises* them, so their health is a hypothesis ("100% approved is flatline, not health").
**Frequency:** 6 — HM-05 (weekly fsck as the health mission), HB-03 (canary defects "make the test affirmative"), IN-04 (canary tasks), IN-06 (backup value "measured at restore time"; restore-test record), IN-11 (the deliberate power-cycle drill), OR-03 ("every recovery procedure in this document is fiction until rehearsed").
**Impact:** Critical — HB-03 (#11), IN-04 (#25); OR-03 is a stated RTO multiplier on every other scenario.
**Smallest mitigation:** The rehearsal calendar the campaign itself concludes with: scheduled canary defects, canary tasks, restore tests, boundary-test documents (EW-01/02), and drills — "the rehearsal calendar *is* the reliability program; everything else is intention" (OR-03).

### 15. RC-15 — Restore without reconciliation
**Root cause:** A backup restores data, not truth: restored state silently re-dispatches finished work, resurrects rejected items and revoked autonomy, and forks history unless the world is re-proven against the restored copy before acting.
**Frequency:** 6 — MC-12, TE-03 (restore path), TE-04, IS-08, IS-09, IN-06 (the full restore-reconciliation suite).
**Impact:** Critical — TE-04 (Top-25 #18: "a revocation silently undone by a backup") and MC-12 (Critical: every downstream consumer inherits the fork).
**Smallest mitigation:** MC-12's rule made universal: restores are first-class events triggering a mandatory dispatch/trust freeze until reconciliation against ground truth completes — and TE-04's corollary: "safety decisions must be replayed forward every time, without exception" (demotions are the records that must never resurrect).

### 16. RC-19 — Time and expiry calendars unmanaged
**Root cause:** Clocks and credential lifetimes are dependencies every component consumes and none declares — expiry dates known months in advance surface as mystery outages, and skewed timestamps quietly invalidate the ≥2-days trust rules and ritual timing.
**Frequency:** 8 — OP-02 (credentials age out; amplified), OP-10 (expired push credential), MC-08, HM-10, TE-09, IN-01 ("expiring credentials are scheduled outages with a known date"), IN-07 ("monitor time like a component, because it is one"), IN-09.
**Impact:** Medium-High — no Top-25 entries; the cost is recurring stalls bounded by Chad plus silent corruption of the timing rules the trust calculus leans on (TE-09).
**Smallest mitigation:** IN-09's generalization: every credential's expiry horizon surfaced in the evidence feed weeks ahead as a maintenance item ("a five-minute packet instead of a mystery outage"), plus NTP offset monitoring as a first-class health metric with recorder-side timestamp quarantine (TE-09/IN-07).

### 17. RC-13 — State asserted without counterpart evidence
**Root cause:** A local record claims something about elsewhere — dispatched, resolved, counted, surfaced, reachable — and is believed without the counterpart's own confirming evidence, so the claim and the world diverge silently.
**Frequency:** 7 — MC-04 ("'dispatched' is a claim about *sending*, not *receiving*"), MC-05 (a resume plan no process executes), MC-09 (the report trusts the day's own receipts), TE-10 (in-memory trust outruns its ledger), CF-07, CF-09 ("'will be surfaced later' is a promise that needs an invariant"), IN-12 (inside-out monitoring structurally blind).
**Impact:** High — MC-09 (Top-25 #20: "a report that flatters is worse than no report").
**Smallest mitigation:** MC-04's decay rule applied everywhere: "every state that asserts remote activity must be paired with the remote's own evidence, or it decays to unknown" — implemented as the campaign's mechanical diffs: answered-but-still-holding audits (CF-07), PAUSE conservation checks (CF-09), verify-at-close-of-books (MC-09), outside-in probes (IN-12).

### 18. RC-18 — Common-cause events misread as many unrelated failures
**Root cause:** One underlying event (reboot, locked keychain, failing RAM, dead resolver, brownout, spend cap) presents as N independent failures at the wrong layer, driving retry storms, phantom fixes, and weeks of misattributed evidence.
**Frequency:** 7 — HM-09 ("one platform event, not N mission errors"), HM-10 ("'the world rejected me' vs. 'I lost my keys'"), HM-11 (weeks of misattribution poisoning the reliability record), IN-07, IN-08, IN-10, IN-11.
**Impact:** High — no Top-25 entries, but HM-11 corrupts trust evidence and IN-11 warns the response can outlive the blip ("the dangerous part of a blip is the response").
**Smallest mitigation:** IN-11's storm-window rule plus IN-08's layered probe: many-components-failing-in-one-window suppresses per-component diagnosis ("no state-changing fixes during a recognized common-cause window — observe, wait, re-probe"), and auth/quota/DNS error classification stops the retry storm at the correct layer.

### 19. RC-14 — Evidence without freshness dating or decay
**Root cause:** Trust, confidence, standing instructions, and reviewer context are event-updated but never time-decayed, so month-1 evidence licenses month-6 behavior against a world that no longer exists.
**Frequency:** 6 — OP-01 (aged packets; amplified), OP-08 (instructions "need review dates like drug orders need expirations"), HB-05 (reviewer knowledge "has a freshness date"), TE-06 ("trust earned is trust *dated*" — entropy, not an event), IS-04 ("any confidence number presented without its date is quietly claiming the world stopped moving"), IN-04 (promotions earned under the old model; amplified).
**Impact:** High — IN-04 (Top-25 #25); TE-06/IS-04 are both Very High likelihood.
**Smallest mitigation:** Evidence-age surfaced at every presentation (IS-04's `why_chosen` receipts carry the newest evidence's date) with staleness bands flagging re-validation, and TE-06's rule that every major environment change implicitly ages every promotion that predates it — flagged-stale claims hedge in packets rather than assert flatly.

### 20. RC-12 — Self-referential evidence: the system grades its own homework
**Root cause:** Outputs of the system (or of the operator's LLM) re-enter as observations supporting the claims they were generated from, so confidence compounds with no new contact with reality — the evidence-or-silence rule satisfied formally by circular evidence.
**Frequency:** 4 — TE-07, IS-05 ("TE-07's lesson arriving through the front door, invited"), MC-09 (the report counting its own receipts instead of re-verifying at source), OR-01 ("a system that measures its own improvement will improve at *being measured*").
**Impact:** Critical, with the highest existential density in this analysis: all four scenarios are Top-25 (TE-07 #12, IS-05 #19, MC-09 #20, OR-01 #24). It "corrupts the epistemology itself."
**Smallest mitigation:** TE-07's reality-terminated provenance enforced at the recorder for all feeds: every observation's chain "must end at something the system didn't write" — a merged PR, a test run, a human entry with a named external source, an external artifact; circular chains are findable mechanically.

---

## (c) Coverage check

**Counting rule.** A scenario may be generated/amplified by several root causes (44 of the 135 cause↔scenario assignments are such overlaps: 135 assignments across 91 distinct scenarios, mean 1.48 causes per covered scenario). Coverage below counts **distinct scenarios (union)** — no scenario is counted twice within a tier, and overlaps between causes are absorbed by the union.

### Cumulative coverage

| Tier | Root causes | Distinct scenarios covered | Coverage |
|---|---|---|---|
| Top 5 | RC-03, RC-04, RC-01, RC-02, RC-05 | 40 | **40%** |
| Top 10 | + RC-08, RC-07, RC-06, RC-10, RC-09 | 61 | **61%** |
| Top 20 | + RC-17, RC-20, RC-11, RC-16, RC-15, RC-19, RC-13, RC-18, RC-14, RC-12 | 91 | **91%** |

Top-25 existential coverage: 24 of the 26 scenario IDs on the campaign's Top-25 list (rank 4 counts EW-01 and EW-02) are generated or amplified by at least one of the 20 causes; the top 10 causes alone touch 22 of them. The two Top-25 IDs covered only in the lower tier are HM-04 and EW-10 (both RC-20).

### Scenarios NOT explained by any of the 20 (9 singletons)

**MC-01, MC-06, MC-11, HM-01, HM-02, HM-06, HM-07, HM-08, IN-03.**

None of the nine is on the Top-25 existential list — consistent with the campaign's closing observation that the loud, mechanical failures are the ones the architecture already converts into pauses and queues. Two residual mini-clusters and two true singletons:

- **Interrupted-write torn state** (MC-01, HM-01, HM-02, HM-06 — crash/power mid-write leaves truncated stores, orphaned locks, dangling worktree metadata). This was effectively root cause #21, just below the frequency×impact cut. The campaign's own containment already covers it: atomic-replace writes, the fail-loudly `.corrupt-<ts>` backup convention, and the boot-time health check (`git fsck`, stale-lock scan, worktree prune) run before missions dispatch.
- **Unbounded autonomous execution** (HM-07, HM-08, MC-06 — token furnace, scope runaway, priority inversion: execution ignoring the plan's economics). Effectively root cause #22. Covered by the campaign's existing vocabulary: hard per-mission ceilings on steps/tokens/wall-clock ("failure ceiling" is already a named PAUSE reason), scope-vs-mission as the review's first gate, and PAUSE-for-preemption at resource contention.
- **MC-11** (malformed packet refused whole) is the architecture *working* — all-or-nothing parsing converting corruption into a clean outage; its lesson is "never make parsing lenient," not a defect mechanism.
- **IN-03** (model provider outage) is a pure external-dependency outage whose containment (the model-free deterministic spine) the campaign already declares an invariant to guard, not a gap.

### Top-25 existential traceability

Every entry on the campaign's Top-25 list, traced to the root cause(s) that generate or amplify it (rank 4 on that list names two IDs, EW-01 and EW-02, so 26 IDs appear):

| Top-25 rank | ID | Explained by |
|---|---|---|
| 1 | EW-04 | RC-02 (custody composition), RC-17 (substrate drift) |
| 2 | EW-10 | RC-20 (trail under-governed) |
| 3 | EW-03 | RC-02 |
| 4 | EW-01 | RC-06 (human-habit ingestion) |
| 4 | EW-02 | RC-10 (recognizer passes the unreadable) |
| 5 | CF-01 | RC-10 |
| 6 | CF-08 | RC-09 (gate bypass), RC-10 |
| 7 | OR-05 | RC-01 (unread detection) |
| 8 | OR-02 | RC-05 (amendment without ceremony), RC-07 (aggregate drift) |
| 9 | CF-05 | RC-01, RC-07 |
| 10 | OP-06 | RC-01 |
| 11 | HB-03 | RC-11 (correlated cognition), RC-16 (unrehearsed controls) |
| 12 | TE-07 | RC-12 (circular provenance) |
| 13 | OR-06 | RC-03 (single-human dependency) |
| 14 | OP-03 | RC-01, RC-07 |
| 15 | HB-07 | RC-05, RC-09 |
| 16 | EW-09 | RC-02 |
| 17 | CF-03 | RC-09 |
| 18 | TE-04 | RC-15 (restore without reconciliation) |
| 19 | IS-05 | RC-06, RC-11, RC-12 |
| 20 | MC-09 | RC-12, RC-13 (state without counterpart evidence) |
| 21 | HB-06 | RC-11 |
| 22 | EW-06 | RC-02 |
| 23 | HM-04 | RC-20 |
| 24 | OR-01 | RC-07, RC-12 |
| 25 | IN-04 | RC-11, RC-14 (undated evidence), RC-16, RC-17 |

All 26 IDs are explained — none of the Top-25 falls into the singleton set. Thirteen distinct root causes carry the entire existential list; RC-02 alone carries five of its entries, and RC-01/RC-07 (the two human-attention causes) jointly carry five.

### Overlap structure

The heaviest multi-cause scenarios are the ones the campaign itself flags as compound: IN-04 (4 causes — a provider event that is simultaneously correlated cognition, stale evidence, an untested control, and substrate drift), IS-05 and EW-05 and HM-09/HM-10 and IN-12 (3 causes each). Overlaps are not double-billing: they are the mechanism pairs the campaign repeatedly points at in its cross-references (e.g., CF-08 cited under both the bypass and recognizer causes exactly as the doc treats it — a correct rule table defeated structurally; IS-05 cited under human-habit ingestion, correlated cognition, and circular provenance, matching the scenario's own three-way framing). Where a cause only *amplifies* a scenario whose primary generator lies elsewhere (OP-01/OP-02 under RC-14/RC-19, HB-04 under RC-11, IN-02 under RC-04), the detailed entries say so.

### Reading the shape

The top 5 causes are, in order: the human (RC-03), event identity (RC-04), the unread reader (RC-01), custody composition (RC-02), and ceremony-less amendment (RC-05) — two human-attention mechanisms, one distributed-systems mechanism, one legal-custody mechanism, one governance mechanism. This matches the campaign's own conclusion: almost nothing existential is a machine breaking. The mitigations correspondingly concentrate into a handful of existing-architecture instruments used harder: the Evening Report's reconciliation and consumption metrics, the parity/coverage/custody audits, the dead-man rituals, default-deny under uncertainty, and the rehearsal calendar.

---

## Appendix — Full scenario → root-cause assignment index

This index is the raw data behind the coverage math: 135 assignments across 91 distinct scenarios; 9 scenarios unassigned (marked `—`, discussed above). Each row lists every root cause that materially generates or amplifies the scenario.

| Scenario | Root cause(s) | | Scenario | Root cause(s) |
|---|---|---|---|---|
| OP-01 | RC-03, RC-14 | | IS-01 | RC-06 |
| OP-02 | RC-03, RC-19 | | IS-02 | RC-04, RC-10 |
| OP-03 | RC-01, RC-07 | | IS-03 | RC-06, RC-07 |
| OP-04 | RC-03 | | IS-04 | RC-14 |
| OP-05 | RC-01, RC-03 | | IS-05 | RC-06, RC-11, RC-12 |
| OP-06 | RC-01 | | IS-06 | RC-06 |
| OP-07 | RC-05 | | IS-07 | RC-06 |
| OP-08 | RC-05, RC-14 | | IS-08 | RC-04, RC-15 |
| OP-09 | RC-05, RC-09 | | IS-09 | RC-15 |
| OP-10 | RC-08, RC-19 | | IS-10 | RC-07 |
| MC-01 | — (torn-write cluster) | | EW-01 | RC-06 |
| MC-02 | RC-08 | | EW-02 | RC-10 |
| MC-03 | RC-04 | | EW-03 | RC-02 |
| MC-04 | RC-08, RC-13 | | EW-04 | RC-02, RC-17 |
| MC-05 | RC-13 | | EW-05 | RC-02, RC-09, RC-10 |
| MC-06 | — (unbounded-execution cluster) | | EW-06 | RC-02 |
| MC-07 | RC-05 | | EW-07 | RC-02 |
| MC-08 | RC-19 | | EW-08 | RC-02 |
| MC-09 | RC-12, RC-13 | | EW-09 | RC-02 |
| MC-10 | RC-07 | | EW-10 | RC-20 |
| MC-11 | — (correct-behavior singleton) | | IN-01 | RC-19 |
| MC-12 | RC-04, RC-15 | | IN-02 | RC-04 |
| HM-01 | — (torn-write cluster) | | IN-03 | — (external-outage singleton) |
| HM-02 | — (torn-write cluster) | | IN-04 | RC-11, RC-14, RC-16, RC-17 |
| HM-03 | RC-08, RC-20 | | IN-05 | RC-08 |
| HM-04 | RC-20 | | IN-06 | RC-15, RC-16 |
| HM-05 | RC-16 | | IN-07 | RC-18, RC-19 |
| HM-06 | — (torn-write cluster) | | IN-08 | RC-18 |
| HM-07 | — (unbounded-execution cluster) | | IN-09 | RC-03, RC-19 |
| HM-08 | — (unbounded-execution cluster) | | IN-10 | RC-18 |
| HM-09 | RC-03, RC-17, RC-18 | | IN-11 | RC-16, RC-18 |
| HM-10 | RC-03, RC-18, RC-19 | | IN-12 | RC-08, RC-13, RC-17 |
| HM-11 | RC-18, RC-20 | | OR-01 | RC-07, RC-12 |
| HM-12 | RC-17 | | OR-02 | RC-05, RC-07 |
| HB-01 | RC-08 | | OR-03 | RC-16 |
| HB-02 | RC-03, RC-08 | | OR-04 | RC-05 |
| HB-03 | RC-11, RC-16 | | OR-05 | RC-01 |
| HB-04 | RC-11 | | OR-06 | RC-03 |
| HB-05 | RC-14 | | | |
| HB-06 | RC-11 | | | |
| HB-07 | RC-05, RC-09 | | | |
| HB-08 | RC-08 | | | |
| HB-09 | RC-11 | | | |
| TE-01 | RC-04 | | | |
| TE-02 | RC-01, RC-06 | | | |
| TE-03 | RC-15, RC-20 | | | |
| TE-04 | RC-15 | | | |
| TE-05 | RC-04 | | | |
| TE-06 | RC-14 | | | |
| TE-07 | RC-12 | | | |
| TE-08 | RC-05 | | | |
| TE-09 | RC-19 | | | |
| TE-10 | RC-13 | | | |

**Consistency checks.** Per-cause frequencies summed from this index: RC-01=7, RC-02=7, RC-03=9, RC-04=10, RC-05=8, RC-06=7, RC-07=7, RC-08=10, RC-09=5, RC-10=5, RC-11=6, RC-12=4, RC-13=7, RC-14=6, RC-15=6, RC-16=6, RC-17=5, RC-18=7, RC-19=8, RC-20=5 — total 135 assignments, matching every frequency claimed in the entries above. Distinct scenarios assigned: 91; unassigned: 9 (MC-01, MC-06, MC-11, HM-01, HM-02, HM-06, HM-07, HM-08, IN-03) — matching the coverage table.

---

*End of Lane 2 analysis. Design only — no code changes, no implementation tasks, no governance or architecture changes proposed beyond mechanisms the campaign document itself names.*
