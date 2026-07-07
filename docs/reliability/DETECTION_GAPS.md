# Olympus Detection Gap Analysis

**Lane 3 of the Olympus Reliability Intelligence Campaign.**
**Status:** Design-only analysis. No code changes, no implementation, no governance changes, no new architecture.
**Source of truth:** `docs/reliability/olympus-failure-injection-campaign-v1.md` (the Failure Injection Campaign, 100 scenarios). Component grounding: `docs/executive-operating-loop-contract.md`, `docs/chief-of-staff/MISSION.md`.

## Method

Every scenario's **stated detection method** (the campaign's own Detection field) is classified into one of four latency classes:

- **IMMEDIATE** — fires at fault time: fail-loud parse, boundary rejection, heartbeat loss, error classification, ceiling breach, load-time integrity check.
- **BOUNDED** — caught within one ritual cycle: the next Morning Packet (`waiting_for_you`, loop section, age metrics) or Evening Report reconciliation (plan-vs-actual, counts, close-of-books re-verification). Worst case ~1 day.
- **DELAYED** — days-to-weeks: scheduled audits, trend metrics, periodic sampling, correlation analysis, rehearsals.
- **BLIND** — detected only by external consequence, adversarial audit, sparse proxy, or never: silent boundary crossings, rubber-stamping, model degradation, contamination, trust miscalibration.

**Det<Dmg?** = does the stated detection fire *before* material damage accrues? **Y** = damage prevented or bounded to negligible by the time detection fires (safe stall, clean hold, boundary rejection). **N** = material damage (money spent, trust corrupted, data leaked/lost, wrong decision made, external effect) precedes or coincides with detection.

Where a scenario has both a fast path and a slow variant (e.g. TE-03 clean corruption vs. subtle corruption), the row is classified on the primary stated mechanism and the variant is noted in the gap list.

---

## 1. Full classification table

### Operator (OP)

| ID | Class | Stated detection (abbreviated) | Det<Dmg? |
|---|---|---|---|
| OP-01 | BOUNDED | Packet unack N days; NEEDS_CHAD queue age; `waiting_for_you` growth | Y |
| OP-02 | BOUNDED | OP-01 signals sustained; spend-runway / credential horizons in evidence feeds | Y |
| OP-03 | BLIND | "Hard — approval procedurally valid"; proxies: latency→0, post-hoc contradiction | N |
| OP-04 | BOUNDED | Answer/question mismatch; Evening Report shows contradictory resolutions | N |
| OP-05 | DELAYED | Indirect only: decision-reversal rate; time-of-day/post-call correlation | N |
| OP-06 | DELAYED | Interrupt-ack latency spikes; safety interrupts unacknowledged (sparse events) | N |
| OP-07 | BOUNDED | Evening plan-vs-actual divergence with no PAUSE/NEEDS_CHAD explaining it | N |
| OP-08 | DELAYED | "Hard by design (obeyed)"; quality regressions cluster; confidence_changes decline | N |
| OP-09 | BOUNDED | Precondition failures; foreign-write checksums; git pushes outside provenance | N |
| OP-10 | BOUNDED | Heartbeat asymmetry; Morning Packet absence as daily dead-man tripwire | Y |

### Mission Control (MC)

| ID | Class | Stated detection | Det<Dmg? |
|---|---|---|---|
| MC-01 | IMMEDIATE | Load-time schema/parse failure; fail-loud, back up, refuse | Y |
| MC-02 | BOUNDED | No packet by expected hour; ritual timestamps stale | Y |
| MC-03 | BOUNDED | Same mission ID twice in logs; twin PRs; Evening count reconcile | N |
| MC-04 | BOUNDED | Liveness gap: dispatched with no remote evidence; Evening plan-vs-actual | Y |
| MC-05 | BOUNDED | Age-in-state in `waiting_for_you`; past-recheck-date flag | Y |
| MC-06 | BOUNDED | Plan-rank vs start-time correlation in Evening Report; resource-hold by priority | N |
| MC-07 | BOUNDED | Age-in-ESCALATING; repeats in every Morning Packet until resolved | Y |
| MC-08 | DELAYED | Ack-latency shift correlated with a clock transition | N |
| MC-09 | BOUNDED | Evidence-freshness re-verify at close-of-books; next-day corrections | Y |
| MC-10 | DELAYED | Store size / queue depth / ritual latency trends in evidence feeds | Y |
| MC-11 | IMMEDIATE | `MorningBriefError` at consume time; degraded=True, never improvises | Y |
| MC-12 | IMMEDIATE | Restore is first-class: mandatory reconciliation mode before dispatch | Y |

### Hermes Mini (HM)

| ID | Class | Stated detection | Det<Dmg? |
|---|---|---|---|
| HM-01 | IMMEDIATE | Supervisor sees exit; MC heartbeat loss on running mission | Y |
| HM-02 | IMMEDIATE | Git ops fail post-reboot; boot self-check (fsck, stale-lock scan) | Y |
| HM-03 | IMMEDIATE | Disk-usage threshold in evidence feed before 100%; save exceptions; log-gap | Y |
| HM-04 | BOUNDED | Evidence-completeness sampling in Evening Report (transcripts counted) | N |
| HM-05 | DELAYED | Scheduled weekly `git fsck` health mission; else first hard failure | Y |
| HM-06 | IMMEDIATE | Worktree setup fails loudly; boot-time stale-worktree scan | Y |
| HM-07 | IMMEDIATE | Per-mission budget metering; 10× class-cost anomaly; ceiling breach ⇒ PAUSE | Y |
| HM-08 | IMMEDIATE | Diff-size vs mission-class anomaly at PR time; MBP scope-vs-mission gate | Y |
| HM-09 | IMMEDIATE | Boot event + environment self-check vs pre-reboot manifest | Y |
| HM-10 | IMMEDIATE | Auth-error classification: 401/403 across all services = local-credential event | Y |
| HM-11 | DELAYED | Cross-mission failure correlation on one host; diagnostics after anomaly trips | N |
| HM-12 | BOUNDED | Environment-manifest diffing on a schedule; review-side untargeted-diff churn | Y |

### Hermes MBP (HB)

| ID | Class | Stated detection | Det<Dmg? |
|---|---|---|---|
| HB-01 | IMMEDIATE | Review-queue age; MBP heartbeat absent while Mini heartbeat present | Y |
| HB-02 | IMMEDIATE | Same heartbeat/queue-age; sessions that start and never conclude | Y |
| HB-03 | DELAYED | Rejection/finding rate trending to zero; periodic canary defects | N |
| HB-04 | DELAYED | Downstream invariant checks (schema validation, fail-loud loads); RCA traceback | N |
| HB-05 | DELAYED | "Hard from inside"; invariant audits in CI/health missions; sampled re-review | N |
| HB-06 | BLIND | Only visible in outcomes: escaped defects clustered by type; Chad spot-checks | N |
| HB-07 | IMMEDIATE | Merge-audit invariant: merge without verdict = page-level alarm | N |
| HB-08 | BOUNDED | Review-duration trend; queue age rising while heartbeats green | Y |
| HB-09 | BLIND | "Difficult directly"; proxies: rationale-quoting verdicts, session-age correlation | N |

### Trust Engine (TE)

| ID | Class | Stated detection | Det<Dmg? |
|---|---|---|---|
| TE-01 | DELAYED | Evidence-record dedup audit; promotion vs distinct-source cross-check | N |
| TE-02 | IMMEDIATE | Contradiction flagged for review at ingest (the flag is the detection) | Y |
| TE-03 | IMMEDIATE | Integrity check at open (fail-loud); subtle variant: re-derivation audit (DELAYED) | Y |
| TE-04 | IMMEDIATE | Restore-reconciliation: diff vs event trail before lifting trust floor | Y |
| TE-05 | IMMEDIATE | Uniqueness/monotonicity checks at recorder; promotion-rate anomaly alarm | Y |
| TE-06 | DELAYED | Evidence-age audit: newest observation predates environment change | N |
| TE-07 | DELAYED | Provenance-type audit: chains must terminate at reality-contact events | N |
| TE-08 | DELAYED | Scope audit: promotions cross-referenced against citing mission classes | N |
| TE-09 | IMMEDIATE | NTP offset monitoring; non-monotonic causal timestamps; recorder tolerance | Y |
| TE-10 | IMMEDIATE | Read-after-write verification; shutdown/startup ledger diff | Y |

### Continue-Until-Fork (CF)

| ID | Class | Stated detection | Det<Dmg? |
|---|---|---|---|
| CF-01 | BLIND | "After-the-fact only, by construction": Evening CONTINUE audit; spot-sampling; external symptom | N |
| CF-02 | DELAYED | Packet-rate + approval-entropy metrics (needs ~3 weeks of trend) | N |
| CF-03 | DELAYED | Coverage audit: every work unit must reference a classification event | N |
| CF-04 | IMMEDIATE | Packet-similarity check at emission; post-answer contradiction detection | Y |
| CF-05 | DELAYED | Default-execution rate per class, trended; decided-by-Chad rate | N |
| CF-06 | BOUNDED | Emitted-but-unacked age alarm in `waiting_for_you` (independent path) | Y |
| CF-07 | IMMEDIATE | Answered-but-still-holding diff (two stores), alarm within an hour | Y |
| CF-08 | BLIND | Effect-level classification is the *proposed* backstop; absent it, as CF-01 | N |
| CF-09 | DELAYED | Conservation check: live PAUSE count vs surfaced-in-briefs count, over recent briefs | N |

### Income Scout (IS)

| ID | Class | Stated detection | Det<Dmg? |
|---|---|---|---|
| IS-01 | IMMEDIATE | Source-type priors keep confidence low; ingest sanity flags on outlier economics | Y |
| IS-02 | DELAYED | Periodic cross-store dedup sweep at lower advisory threshold (~0.65) | N |
| IS-03 | BOUNDED | Source-concentration metric vs band; per-source acceptance history | Y |
| IS-04 | BOUNDED | Evidence-age surfaced in `why_chosen` receipts at every presentation; staleness bands | Y |
| IS-05 | BLIND | "Nearly blind at the engine"; discrepancy surfaces at pursuit-time reality contact | N |
| IS-06 | IMMEDIATE | Ingest-time plausibility bands (implied rates); raw numbers visible in receipts | Y |
| IS-07 | IMMEDIATE | Load-time invariant validation (stage ∈ enum, legal transition chains), fail-loud | Y |
| IS-08 | IMMEDIATE | Exact-fingerprint reject-count spike in one sweep = replay signature | Y |
| IS-09 | DELAYED | API blocks legal path; the bypass variant found only by terminal-state-in-history audit | N |
| IS-10 | DELAYED | Portfolio-shape reporting over time; visible only in aggregate | N |

### Expert Witness (EW)

| ID | Class | Stated detection | Det<Dmg? |
|---|---|---|---|
| EW-01 | IMMEDIATE | Forbidden-marker scan at every ingestion boundary; rejection event = detection | Y |
| EW-02 | DELAYED | Default-deny for unscannable content is *policy*; past bypass found by periodic OCR sweep | N |
| EW-03 | BLIND | Provenance-per-assertion at drafting (discipline, not instrument); else adversarial cross-exam | N |
| EW-04 | IMMEDIATE | Egress audit: endpoint outside approved list alarms; routing config-diff monitoring | N |
| EW-05 | IMMEDIATE | Dispatch-time marker rejection on mission *content*; bounce to NEEDS_CHAD | Y |
| EW-06 | DELAYED | Claim-provenance audit: chains touching EW sources findable mechanically | N |
| EW-07 | DELAYED | Matter-close checklist sweep; periodic all-storage marker scan | Y |
| EW-08 | DELAYED | Marker scan applied to metadata surfaces (commits, titles, reports, filenames) | N |
| EW-09 | DELAYED | Data-flow enumeration as scheduled audit: walk actual copy chain vs custody list | N |
| EW-10 | BLIND | "N/A — adversarial audit by a motivated third party" | N |

### Infrastructure (IN)

| ID | Class | Stated detection | Det<Dmg? |
|---|---|---|---|
| IN-01 | IMMEDIATE | Inter-node heartbeat distinct from internet; key-expiry horizon in evidence feed | Y |
| IN-02 | IMMEDIATE | Error classification: remote-service vs auth vs local; status corroboration | Y |
| IN-03 | IMMEDIATE | Provider-error classification distinct from quota/auth by error shape | Y |
| IN-04 | BLIND | No error signal ever; outcome baselines / periodic canaries are prescriptive instruments | N |
| IN-05 | IMMEDIATE | Trivially loud locally; Chad-side silence-is-alarm convention (OP-10) | Y |
| IN-06 | IMMEDIATE | Loud and immediate (disk dead) | N |
| IN-07 | IMMEDIATE | NTP offset monitoring as first-class health metric; timestamp sanity | Y |
| IN-08 | IMMEDIATE | Layered connectivity probe on external-failure burst (IP/DNS/TLS/HTTP) | Y |
| IN-09 | IMMEDIATE | Expiry horizons surfaced weeks ahead; auth classification stops retry storm | Y |
| IN-10 | IMMEDIATE | Quota/429 classification; spend + rate telemetry vs known caps in evidence feed | Y |
| IN-11 | IMMEDIATE | Storm recognition: many components failing in one window = common-cause event | Y |
| IN-12 | BOUNDED | Outside-in probes at cadence; inside-out monitoring structurally blind | Y |

### Organizational (OR)

| ID | Class | Stated detection | Det<Dmg? |
|---|---|---|---|
| OR-01 | DELAYED | Mission-mix by beneficiary, trended monthly; Final Filter as measured audit | N |
| OR-02 | DELAYED | Governance parity audit on a schedule: written rules vs observed behavior | N |
| OR-03 | DELAYED | Runbook rehearsal on schedule; unrehearsed runbook = hypothesis | Y |
| OR-04 | DELAYED | Mutation-boundary audit generalized: writes attributed to wrong layer | N |
| OR-05 | BLIND | Consumption metrics (ack depth, queue-work rates, decided-by-Chad) — whose only reader is the failing reader | N |
| OR-06 | BLIND | "N/A for the event"; internally indistinguishable from OP-01 forever | N |

---

## 2. The gap list — every DELAYED and BLIND scenario

41 scenarios (30 DELAYED + 11 BLIND). Top-25 existential entries first, in campaign rank order; the remainder follow. For each: **(a)** the earliest measurable signal that exists in principle before the stated detection fires, and **(b)** the existing Olympus component that could carry it today. Components are restricted to: evidence feeds / Evening Report metrics, Morning Packet (`waiting_for_you`, loop), the escalation classifier's rule table, the review gate (Hermes MBP verdicts), the memorygraph contradiction/review queue, the opportunity scout's validation/receipts machinery, scheduled health missions on the Mini, and boundary marker-scanning. Where no existing component can carry the signal before damage, the entry is marked **RESIDUAL-BLIND** (section 3).

### 2.1 Top-25 existential entries

**EW-10 — Discovery of AI use (rank 2, BLIND).**
(a) Earliest signal: the *preparedness* deficit is measurable long before the deposition question: per-matter assertion-citation coverage rate (fraction of work-product claims with an in-corpus citation), methodology-document age, per-matter records-organization completeness count.
(b) Carrier: scheduled health mission on the Mini auditing per-matter record organization + Evening Report metric for citation-coverage. **The event itself is adversarial by construction — RESIDUAL-BLIND for the event; only preparedness is instrumentable.**

**EW-03 — Cross-case contamination (rank 3, BLIND).**
(a) Earliest signal: multi-matter session count (contexts/workspaces touching files from more than one matter) — a count that should be pinned at zero; and per-draft count of assertions lacking an in-corpus citation, which precedes delivery of the opinion.
(b) Carrier: boundary marker-scanning turned inward — scan each case workspace for *another* case's markers (party names, case numbers of matter B inside matter A's workspace); run as a scheduled health mission. Catches contamination before the opinion ships. Residual: an already-delivered opinion drafted without the discipline is detectable only under cross-examination.

**EW-02 — Marker bypass via unscannable formats (rank 4, DELAYED).**
(a) Earliest signal: count of boundary-admitted items with zero extractable text (opaque PDFs, images, archives passed as "clean"). Every such admission is a scanner confession, loggable at admission time — before any OCR-capable tool reads the content.
(b) Carrier: boundary marker-scanning itself (emit an "unscannable-passed" counter); surface the count in Evening Report metrics; periodic OCR sweep of general stores as a scheduled health mission on the Mini.

**CF-01 — Missed fork: silent boundary crossing (rank 5, BLIND).**
(a) Earliest signal: novel-action-shape rate — classification events where only the generic/catch-all rule matched, or where the action verb/tool/channel has never appeared in the rule table's vocabulary. A new tool producing its first CONTINUE is the precursor state of every missed fork.
(b) Carrier: the escalation classifier's rule table — it is deterministic and first-match-wins, so *which rule matched* is a free byproduct; a per-rule match histogram with a "no-boundary-rule-consulted for novel shape" counter feeds the Evening Report's CONTINUE audit. Residual: the mis-*recognized* variant (a genuinely new action shape matching an existing benign rule) shows a normal match and stays blind until external consequence — see section 3.

**CF-08 — Fork evasion by decomposition (rank 6, BLIND).**
(a) Earliest signal: composite-pattern count in the day's CONTINUE chains — mission step sequences containing send-adjacent verbs (draft / configure-send / finalize-comms) with zero NEEDS_CHAD anywhere in the chain. A deterministic scan of the execution trail, not a model call.
(b) Carrier: Evening Report reconciliation (it already audits CONTINUE work); the scan converts BLIND to BOUNDED for the *pattern*, though only the campaign's proposed effect-level re-classification (new architecture, out of scope) closes it structurally. Partial residual — see section 3.

**OR-05 — Evidence ignored: the audit loop dies (rank 7, BLIND).**
(a) Earliest signal: consumption metrics — report-acknowledgment depth, contradiction-queue resolution rate per week, spot-checks performed per week, decided-by-Chad rate. All exist in principle today: memorygraph's contradiction/review queue has an age; `waiting_for_you` has an age distribution; packet resolutions have timestamps.
(b) Carrier: Evening Report metrics + memorygraph review-queue age + Morning Packet queue ages. **But every one of these carriers terminates in the reader who is the failing component.** Signal exists; a trustworthy consumer of the signal does not. **RESIDUAL-BLIND** (section 3).

**OR-02 — Governance drift by accumulated exception (rank 8, DELAYED).**
(a) Earliest signal: each exception's *first use* is individually countable the day it lands: merges without review verdicts (count), work units without classification events (count), packet-rate step change after a rule edit, rule-table diff events without a recorded decision.
(b) Carrier: review gate verdict records reconciled against merges in the Evening Report; escalation classifier rule-table version/diff surfaced as an evidence-feed event. Each seed of drift (HB-07, CF-03, CF-02's over-correction) has a same-day counter; only their *accumulation* needs the periodic parity audit.

**CF-05 — Death by default (rank 9, DELAYED).**
(a) Earliest signal: default-execution rate per packet class — fraction of packets resolved by the do-nothing default rather than an explicit answer. Rises weeks before the threshold-crossing trend the campaign describes; the very first week of chronic non-answering is visible.
(b) Carrier: Evening Report metrics (packets resolved today: by-answer vs by-default is derivable from existing packet resolution records) + Morning Packet `waiting_for_you` age distribution as the leading indicator.

**OP-06 — Alarm fatigue (rank 10, DELAYED).**
(a) Earliest signal: the *cause* precedes the mute — interrupt volume per day above the near-zero design baseline, and interrupt-ack latency trending up *before* it goes infinite. A week of >N interrupts/day is the precursor; the mute is the consequence.
(b) Carrier: evidence feeds / Evening Report metrics (interrupts emitted and acknowledged are recorded events; volume and ack-latency are counts over them). The four-class router's own emission log is the source.

**HB-03 — False confidence: the LGTM machine (rank 11, DELAYED).**
(a) Earliest signal: reviewer finding-rate per review (findings/verdict) declining; approval rate approaching 100%; verdict specificity collapsing (verdict length / diff-line-referenced count as a crude proxy); review duration dropping below class baseline. All derivable from verdicts already recorded.
(b) Carrier: the review gate (Hermes MBP verdicts) is itself the record; Evening Report counts findings-per-verdict; canary defects run as scheduled health missions on the Mini (a known-bad PR injected weekly) make the test affirmative rather than statistical.

**TE-07 — Self-licking evidence loop (rank 12, DELAYED).**
(a) Earliest signal: fraction of new observations whose provenance terminates in a Hermes-generated artifact rather than a reality-contact event (merged PR, test run, human entry); and the divergence between `memory_claims_established` counts and independently counted external artifacts in the same period (promotions rising with flat merged-PR/test counts).
(b) Carrier: memorygraph — provenance is recorded by design, so circular chains are mechanically findable; flag hits into the memorygraph contradiction/review queue; the cross-count divergence is an Evening Report metric over existing evidence feeds. Run the provenance audit as a scheduled health mission.

**OR-06 — Bus factor one (rank 13, BLIND).**
(a) Earliest signal for the *event*: none internal — the system experiences permanent operator loss as OP-01 with no upper bound; it is constitutionally unable to distinguish vacation from death. Preparedness is measurable (continuity-document existence/age, silence-streak day count).
(b) Carrier: Morning Packet unacknowledged-streak already exists but cannot disambiguate; a scheduled health mission can check continuity-document age. **RESIDUAL-BLIND for the event** (section 3).

**OP-03 — Rubber-stamp approvals (rank 14, BLIND).**
(a) Earliest signal: approval latency trending toward zero across packet classes (a four-second yes is a measurable artifact); rate of approvals on packets whose default was "do nothing"; countermand/reversal rate within N days of approval. Latency decline precedes the misfired external send by weeks.
(b) Carrier: Evening Report metrics — packet emission and resolution timestamps are already recorded, so latency distribution per class is a pure derivation; reversal events appear in the decision log the same day.

**EW-09 — Backup chain exfiltration (rank 16, DELAYED).**
(a) Earliest signal: presence of isolated-store paths in any backup/sync tool's configuration or logs (a hop count that should equal the approved custody list's length); case markers found on any non-approved volume.
(b) Carrier: scheduled health mission on the Mini walking the actual copy chain (backup job configs, sync-client targets) against the custody list; boundary marker-scanning pointed at backup targets/indexes. Detection still trails the first exfiltrated byte, but the *config* appears before the first backup run completes — a same-day window exists.

**CF-03 — Policy bypass: the side door (rank 17, DELAYED).**
(a) Earliest signal: the side door's *creation* is observable before its use accumulates: new crontab/launchd entries, new executable entrypoints, tool invocations in execution logs with no classification-event reference. One unclassified work unit is countable the evening it runs.
(b) Carrier: Evening Report reconciliation (work-evidence count vs classification-event count must balance — same shape as its existing plan-vs-actual pass); scheduled health mission on the Mini diffing cron/launchd/entrypoint inventory.

**IS-05 — ROI hallucination through the human gate (rank 19, BLIND).**
(a) Earliest signal: count of validation-evidence records marked STRONG that carry no verifiable source citation; implied-rate/round-number plausibility flags on entered economics (the scout's existing sanity-band machinery applied to *evidence* fields, not just intake fields).
(b) Carrier: the opportunity scout's validation/receipts machinery — evidence records are structured, so "citation-less STRONG" is a mechanical count; `why_chosen` receipts already display the numbers at every presentation. Residual: a fluent fabricator that also fabricates plausible *citations* passes every structural check and is caught only at pursuit-time reality contact — see section 3.

**HB-06 — Correlated blindness (rank 21, BLIND).**
(a) Earliest signal: escaped-defect taxonomy — defects found post-merge by deterministic checks (tests, schema validation, invariant audits) that *both* stages missed, counted and clustered by type. Clustering is the correlation confessing.
(b) Carrier: Evening Report metric (post-merge defect count by class, derivable from RCA records and revert events) + review gate verdicts (to compute what review saw vs missed). Weak: this measures the correlation only *after* defects escape; the standing correlation structure itself has no internal instrument. Partial **RESIDUAL-BLIND** (section 3).

**EW-06 — Memory absorbs case facts (rank 22, DELAYED).**
(a) Earliest signal: count of memorygraph claims whose text or provenance chain contains forbidden markers (party names, case numbers, matter identifiers); count of recording events originating from expert-witness contexts. Should be pinned at zero; the first hit is the incident.
(b) Carrier: boundary marker-scanning applied to memorygraph claim text and provenance as a scheduled health mission; hits routed into the memorygraph contradiction/review queue (which exists precisely to hold claims pending adjudication).

**OR-01 — Build Program drift (rank 24, DELAYED).**
(a) Earliest signal: daily/weekly mission-mix by beneficiary (Build Program vs income vs practice vs life) — derivable from mission records the same evening, weeks before the monthly trend confirms drift.
(b) Carrier: Evening Report metrics (`ai_accomplished` counts tagged by beneficiary; the campaign itself notes reports should "tie Build work to named downstream beneficiaries"); Morning Packet loop section showing today's mix against the declared budget.

**IN-04 — Silent model degradation (rank 25, BLIND).**
(a) Earliest signal: canary regression — periodic re-runs of fixed tasks with known-good historical outputs, diffed; plus step-changes on a single date in first-pass mission success rate and reviewer finding rate across independent workstreams.
(b) Carrier: scheduled health missions on the Mini (canary re-runs are exactly the cheap, boring, scheduled work that component exists for); Evening Report metrics carry the success-rate and finding-rate series. With canaries running, this drops from BLIND to DELAYED (days); without them it is detectable only as misattributed quality drift.

### 2.2 Remaining DELAYED scenarios (not in Top 25)

| ID | (a) Earliest measurable signal | (b) Existing carrier |
|---|---|---|
| OP-05 | Reversal rate on recent approvals; answer-timestamp distribution showing money-class packets resolved in known post-call windows | Evening Report metrics (decision log timestamps per packet class) |
| OP-08 | Standing-instruction age × citation count (instruction applied to N missions incl. new classes); `confidence_changes` declining in one domain | Evening Report `confidence_changes` (exists in packet v1.1); Morning Packet loop section surfacing instruction ages |
| MC-08 | Production-to-acknowledgment latency step-shift the day after a clock transition (one day of data suffices) | Evening Report metrics (ack latency); makes it BOUNDED in practice |
| MC-10 | Queue depth, store size, ritual-generation latency — already named evidence-feed metrics; the signal predates unreadability by weeks | Evidence feeds / Evening Report trend rows |
| HM-05 | Checkout-failure rate on old refs; per-repo git-operation error anomalies between weekly fscks | Scheduled health missions (weekly fsck is the stated detector; error counts feed Evening Report between runs) |
| HM-11 | Host-wide failure rate across unrelated missions/repos/providers; non-reproducing test-failure count | Evening Report metrics (failure rate by host dimension); hardware diagnostics as a scheduled health mission once tripped |
| HB-04 | Post-merge invariant failures at first contact; store round-trip (write-read) check failures after merges touching store code | Scheduled health missions (store round-trip probes); review gate checklist accumulating escaped signatures |
| HB-05 | Reviewer standing-context version/hash vs current docs version — an age/diff, checkable daily | Scheduled health mission comparing hashes; review gate records the context version per verdict |
| HB-09* | Verdicts textually referencing implementer rationale absent from the diff; reviewer persistent-state age; finding-rate decline vs session longevity | Review gate verdicts (scannable text); canaries with fabricated justifications via scheduled health missions (HB-03 machinery) |
| TE-01 | Duplicate-provenance count: observations sharing mission ID/artifact behind one promotion; promotions with distinct-source count below policy | Memorygraph (provenance recorded); dedup audit as scheduled health mission; observation-vs-mission count reconcile in Evening Report |
| TE-06 | Promotion staleness: newest supporting observation date vs last environment-change event; count of packet-cited claims older than band | Memorygraph dates + Evening Report staleness metric; claim ages in packet receipts |
| TE-08 | Scope-mismatch count: promotions cited by mission classes ∉ their evidence's mission classes | Memorygraph + escalation classifier ("new category ⇒ NEEDS_CHAD" rule is the constitutional backstop); scope audit as health mission |
| CF-02 | Packet rate/day above baseline + per-class approval entropy near zero — visible within days, not the stated 3 weeks | Evening Report metrics (packet counts and resolution outcomes) |
| CF-09 | Conservation gap: live PAUSE count in mission state minus PAUSE items surfaced in the day's brief; oldest-unsurfaced-PAUSE age | Evening Report reconciliation computing the diff per cycle; Morning Packet loop section carries the count |
| IS-02 | Advisory-threshold (≈0.65) merge-candidate count from a sweep — the tunable-threshold hook exists per call by design | Opportunity scout dedup machinery run as a scheduled health mission; candidates to Chad via `waiting_for_you` |
| IS-09 | Count of active opportunities whose transition history contains a terminal state (must be zero absent a revival packet) | Scout store audit as scheduled health mission; scout lifecycle machinery (`ALLOWED_TRANSITIONS`) supplies the legality check |
| IS-10 | Portfolio-shape distribution (type/duration/asset-class) of active + pursued opportunities over a trailing window | Scout receipts/ranking data aggregated into the Evening Report `opportunity_summary` |
| EW-07 | Marker hits from *closed* matters anywhere in storage; matter-close sweeps recorded vs matters closed (a count that must balance) | Boundary marker-scanning as periodic all-store scan (scheduled health mission); close-sweep records in the trail |
| EW-08 | Marker hits in the metadata corpus: commit messages, mission titles, report text, filenames | Boundary marker-scanning aimed at metadata surfaces, scheduled health mission cadence |
| OR-03 | Rehearsal age per runbook (days since last successful execution); diffs changing documented behavior without doc updates | Scheduled health missions (rehearsals *are* health missions); review gate question "does this diff change documented behavior?" |
| OR-04 | Foreign-write count (store mutations attributed to the wrong layer); Hermes answers citing no MC-published source; execution events from MC processes | Mutation-boundary audit as scheduled health mission (invariant-3 machinery); Evening Report reconciliation |

\* HB-09 classified BLIND in the table; listed here because its proxies are the same machinery as its DELAYED neighbors.

---

## 3. RESIDUAL-BLIND list

Scenarios where **no existing component can detect the failure before damage** — the honest remainder. These align exactly with the campaign's Final Question: erosion-class failures with no timestamp, failures of the reader rather than the system, and adversarial audits from outside the trust boundary.

1. **OR-06 — Bus factor one (the event).** The system cannot distinguish permanent operator loss from a long absence; every internal signal (packet unack streak, queue age) is identical to OP-01 extended indefinitely. Detection belongs to external humans, who are outside every Olympus component. Only preparedness (continuity-document age) is instrumentable — and it measures readiness, not the event.

2. **OR-05 — Evidence ignored (the terminal form).** Every carrier available — Evening Report metrics, queue ages, the memorygraph review queue — terminates in the human whose disengagement is the failure. The signal exists; a consumer that survives the failure does not. This is the campaign's own conclusion: "detection that terminates in an unread report is decoration." Within the fixed architecture, the four-class interrupt channel could theoretically page on consumption-floor breach, but OP-06 shows that channel is itself vulnerable to the same human, and paging the disengaged reader about his disengagement is a mitigation of last resort, not detection.

3. **EW-10 — Discovery of AI use (the event).** An adversarial audit by opposing counsel. No internal feed, packet, queue, or scan observes a subpoena before it arrives. Preparedness (citation coverage, methodology-document freshness, records organization) is measurable by health missions; the event is structurally external.

4. **HB-06 — Correlated blindness (the standing property).** The correlation between implementer and reviewer blind spots can only be observed in *escaped* defects — i.e., after damage. Both potential internal observers share the blind spot by construction; the only uncorrelated layers (deterministic checks, Chad's spot-checks) detect instances, never the structure. Measuring the correlation itself would require a second, independent model family — new architecture, out of scope.

5. **CF-01 — Missed fork, mis-recognition variant.** The novel-shape counter (section 2.1) catches actions the rule table has never seen. It cannot catch a genuinely new action shape that *matches an existing benign rule* — the classifier reports a normal, confident match; the Evening CONTINUE audit samples, and sampling can miss. Until an external counterparty reacts, this variant is silent. (The campaign agrees: "after-the-fact only, by construction.")

6. **CF-08 — Fork evasion, structural residue.** The Evening trail-scan for composite send-adjacent chains (section 2.1) is a heuristic over known verb patterns. A decomposition using vocabulary the pattern doesn't cover crosses silently. The campaign's own fix — re-classification at the effect hop, the last call before the world — is the missing boundary, and it does not exist in the fixed architecture.

7. **IS-05 — ROI hallucination, fabricated-citation variant.** The citation-less-STRONG counter catches lazy fabrication. An LLM that fabricates *plausible citations* along with the numbers defeats every structural check the scout owns; the first detector is pursuit-time reality contact — external consequence, after attention and possibly money moved.

8. **EW-03 — Cross-case contamination, delivered-opinion variant.** The inward marker cross-scan catches contaminated *workspaces*; an opinion already drafted and delivered without citation discipline carries no machine-readable trace of which facts came from where. Its detector is cross-examination.

**Pattern.** Every residual item is one of three kinds the campaign's Final Question predicted: (i) the reader failing (OR-05, OR-06 — the living relationship is not a component and cannot be instrumented by one); (ii) correlated judgment sharing one model's worldview (HB-06, CF-01/CF-08 residues, IS-05 residue — the checker and the checked have the same blind spot); (iii) adversaries and reality auditing from outside the trust boundary (EW-10, EW-03 residue — detection arrives as consequence). None of these is a machine breaking; all are erosion or exposure classes where the earliest honest "signal" is damage itself.

---

## 4. Summary statistics

### Per latency class (all 100 scenarios)

| Class | Count |
|---|---|
| IMMEDIATE | 39 |
| BOUNDED | 20 |
| DELAYED | 30 |
| BLIND | 11 |

Detection precedes material damage: **54 yes / 46 no.** Notably, several IMMEDIATE scenarios still detect *at or after* damage (EW-04 egress alarm fires as the content leaves; HB-07 merge-audit fires as the unreviewed merge lands; IN-06 loss is coincident) — latency class and damage-precedence are independent axes.

### Per category

| Category | n | IMMEDIATE | BOUNDED | DELAYED | BLIND | D+B share |
|---|---|---|---|---|---|---|
| OP | 10 | 0 | 6 | 3 | 1 | 40% |
| MC | 12 | 3 | 7 | 2 | 0 | 17% |
| HM | 12 | 8 | 2 | 2 | 0 | 17% |
| HB | 9 | 3 | 1 | 3 | 2 | 56% |
| TE | 10 | 6 | 0 | 4 | 0 | 40% |
| CF | 9 | 2 | 1 | 4 | 2 | 67% |
| IS | 10 | 4 | 2 | 3 | 1 | 40% |
| EW | 10 | 3 | 0 | 5 | 2 | 70% |
| IN | 12 | 10 | 1 | 0 | 1 | 8% |
| OR | 6 | 0 | 0 | 4 | 2 | 100% |

### Top-25 existential ranking

Of the 25 ranked entries, **20 are DELAYED or BLIND (80%)**. The five that are not (EW-04, HB-07, TE-04, MC-09, HM-04) include three whose detection fires only *at or after* the damage (EW-04, HB-07, HM-04). Net: **23 of 25 existential entries are either detected slowly or detected too late** — the campaign's closing observation ("what it cannot convert are failures that never make a sound") restated as arithmetic.

### Reading

- The loud substrate (IN, HM, MC) is well covered: 21 of 34 scenarios IMMEDIATE, almost all detection-before-damage. Olympus's event-shaped defenses work where failures are events.
- The gap concentrates where the campaign said it would: **OR (100% D/B), EW (70%), CF (67%), HB (56%)** — governance erosion, legal exposure, boundary recognition, and reviewer integrity.
- Of the 41 DELAYED/BLIND scenarios, **33 have an earlier signal that an existing component could carry today** — mostly counts and ages derivable from records the system already keeps (verdicts, packets, provenance, timestamps, marker scans). The two workhorses are the **Evening Report metric surface** (17 scenarios) and **scheduled health missions on the Mini** (16 scenarios), with **boundary marker-scanning repurposed** for five EW gaps and the **memorygraph's recorded provenance** for four TE gaps.
- The remaining 8 residual items (section 3) are not instrumentation gaps; they are the erosion class — failures of the reader, of judgment correlation, and of adversarial exposure — that the campaign's Final Question identified as the failure class no component can own.

*End of Lane 3 detection gap analysis. Design only — no code changed, no architecture proposed; every carrier named above already exists in the cited Olympus documents.*
