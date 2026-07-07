# Top 10 Reliability Wins — Olympus

**Lane 1 of the Reliability Intelligence Campaign.**
**Status:** Design only. No code changes, no implementation tasks, no governance changes, no architecture redesign.
**Source of truth:** `docs/reliability/olympus-failure-injection-campaign-v1.md` (the Failure Injection Campaign, 100 scenarios, OP/MC/HM/HB/TE/CF/IS/EW/IN/OR, plus the Top 25 existential ranking). Every mechanism below is one the campaign's own *detection*, *containment*, or *lesson* fields already describe — the wins are the act of **wiring** those mechanisms, not inventing new ones.

---

## Method

Each of the 100 scenarios names how it would be detected, contained, or prevented. Reading across all 100, a small number of mechanisms recur constantly: conservation audits, attention metrics, canary tasks, age/expiry tracking, event identity, environment manifests, marker scanning, endpoint pinning, restore reconciliation, and effect-point classification. A "win" here is one such mechanism, implemented once, inside the existing Olympus architecture (a health mission, an audit pass, a config pin, a metric in the existing evidence feed, a reconciliation step).

**Scoring — Risk Reduced Per Unit of Engineering:**

- Each scenario the win **materially** helps (reduces likelihood, impact, or detection latency) earns **1 point**; scenarios appearing in the campaign's **Top 25 existential ranking earn 3 points** (weighting unrecoverable risk over throughput risk, per the campaign's own severity logic).
- **Partial** coverage (the win is one of several layers the scenario needs, or covers only a variant) earns **half** points.
- The sum is divided by **effort points**: S = 1, M = 2, L = 3.
- Ties broken by Top-25 mass covered at full weight.

A scenario may be counted by more than one win only where the campaign itself names both mechanisms as independent layers for it (e.g., EW-01/02 need both the default-deny boundary *and* live-fire canary tests). Honesty rule applied throughout: a scenario is listed only if the campaign's own text for that scenario cites the mechanism or an obvious instance of it.

**A note on ranking vs. severity:** this table optimizes risk-per-effort. A pure severity ordering would promote Win 8 (which covers EW-04, the campaign's #1 existential risk, at the smallest effort in the list) and Win 10 (which covers existential ranks #5 and #6). All three orderings agree on one thing: everything on this list pays for itself.

---

## Ranking

| Rank | Win | Mechanism (one line) | Weighted pts | Effort | Score |
|---|---|---|---|---|---|
| 1 | Conservation Audit | One scheduled audit pass checking ~10 mechanical "books balance" invariants | 19.5 | L (3) | **6.5** |
| 2 | Attention Instrumentation | Operator-calibration metrics in the existing Evening Report + rare meta-packets | 12.5 | M (2) | **6.25** |
| 3 | Canary Program | Scheduled known-bad/known-good probes: reviewer canary defects, model-baseline tasks, boundary test documents | 11.5 | M (2) | **5.75** |
| 4 | Horizon Ledger | Unified age/expiry/staleness feed: everything with a date, surfaced before it fires | 11.0 | M (2) | **5.5** |
| 5 | Event Identity & Provenance | Idempotent observation identity + reality-terminated provenance enforced at every recorder | 9.0 | M (2) | **4.5** |
| 6 | Boot-as-Deployment | Environment manifest + boot/scheduled self-check gating the mission queue | 9.0 | M (2) | **4.5** |
| 7 | Default-Deny Boundary + Marker Sweep | Unscannable ⇒ rejected; marker scan extended to dispatch, metadata, and periodic store sweeps | 8.5 | M (2) | **4.25** |
| 8 | Expert-Witness Egress Pin + Log | Workspace-level model-endpoint pin + per-request egress log for the EW domain | 3.5 | S (1) | **3.5** |
| 9 | Restore-Reconciliation Discipline | Any restore ⇒ dispatch freeze, diff against ground truth, safety events replayed forward | 7.0 | M (2) | **3.5** |
| 10 | Effect-Level Classification | The last hop before any external effect re-classifies, regardless of upstream verdicts | 6.0 | M (2) | **3.0** |

Ties: #5 over #6 (more Top-25 mass at full coverage); #8 over #9 (covers the single worst scenario in the campaign at the smallest effort on the list).

---

## Win 1 — The Conservation Audit

**What it is.** One scheduled health mission (nightly or weekly, machine-run) that checks a battery of mechanical "books must balance" invariants the campaign cites over and over: every merge references a review verdict (HB-07's merge audit); every unit of executed work references a classification event (CF-03's coverage audit); live PAUSE items = PAUSE items surfaced in recent briefs (CF-09's conservation check); every answered packet's mission has transitioned (CF-07); every governed-store mutation is attributable to its owning writer (OP-09/OR-04's mutation-boundary audit); every mission has a complete transcript (HM-04's evidence-completeness sampling); and every artifact the Evening Report counts is re-verified against its source of truth at close-of-books (MC-09). Each check is a simple query over stores and logs that already exist; the output is one line in the Evening Report — zero when the books balance, loud when they don't.

**Scenarios affected.** HB-07, CF-03, CF-07, CF-09, OP-09, MC-09, HM-04 (partial), OR-02 (partial — this audit *is* the governance-parity probe the OR-02 detection section describes), OR-04 (partial), HB-05 (partial — mutation-boundary audit catches invariant-violating merges), IS-07 (partial — foreign-write/semantic-invariant detection), IS-09 (partial — terminal-state-history audit), CF-06 (partial — emitted-vs-acknowledged conservation), MC-03 (partial — one-execution-per-mission-ID reconciliation), MC-04 (partial — plan-vs-actual), OP-07 (partial — plan-vs-behavior divergence).

**Risk reduced.** This is the single largest bite out of the campaign's dominant silent-erosion cluster. Five Top-25 entries are materially covered: **#8 OR-02** (governance drift), **#15 HB-07** (review-absence flag as consent), **#17 CF-03** (unclassified shadow work), **#20 MC-09** (books closed on fiction), **#23 HM-04** (unverifiable past). It converts "governance decays one shortcut at a time and nobody can see it" into a nightly zero-or-alarm number. The campaign's own words: "the invariant to monitor is not 'does the classifier work' but 'does all work pass through it.'"

**Engineering effort.** **L** — no single check is hard, but there are ~10 of them across several stores/logs, plus report wiring; done honestly this is the biggest build on the list.

**Operational effort.** Machine-time nightly (minutes). Chad: ~5 min/week reading the audit line, more only on a red result — which, per the campaign's severity model, is time he'd otherwise spend on an incident weeks later.

**Blast radius.** A buggy check that cries wolf spends the report's credibility and feeds OP-06/OR-05 alarm fatigue — checks must ship with a verified-quiet week. A check that silently passes when it shouldn't is worse than no check (HB-03's flatline lesson applies to audits too); the Canary Program (Win 3) should occasionally feed it a known imbalance.

**Dependencies.** Existing stores/logs only. Win 5 (event identity) makes the mission-ID and dedup checks trustworthy; Win 3 keeps the audit itself honest.

---

## Win 2 — Attention Instrumentation

**What it is.** Add the operator-calibration metrics the campaign repeatedly names — all derivable from data the loop already records — to the existing Evening Report/evidence feed: decision latency per packet class (OP-03's "four-second yes"), decision-reversal rate and time-of-day/post-call correlation (OP-05), interrupt volume and acknowledgment latency vs. the near-zero budget (OP-06), packet rate and approval entropy (CF-02's "100% approval = not decisions"), default-execution rate per packet class and the "fraction of decisions actually decided by Chad" (CF-05), and report-consumption metrics — acknowledgment depth, queue-work rates, spot-checks performed (OR-05). Threshold crossings emit the meta-packets the campaign already specifies ("you are effectively delegating class X to defaults — make it explicit or reclaim it").

**Scenarios affected.** OP-03, OP-05, OP-06 (partial — detection side), CF-02, CF-05, OR-05.

**Risk reduced.** Four Top-25 entries: **#7 OR-05** (the audit loop dying of success — the multiplier that disarms ~40 other scenarios' detection), **#9 CF-05** (governance inverting to default-led), **#14 OP-03** (rubber-stamping), and the detection half of **#10 OP-06** (alarm fatigue). This is the only win aimed squarely at the campaign's Final Question: the system currently measures everything except its reader. Nothing here grades Chad's cognition (constitutionally forbidden); it measures the *channel* — latencies, rates, entropy — which the campaign explicitly classifies as trust-calibration instruments.

**Engineering effort.** **M** — the raw events (packet timestamps, answers, interrupts, report opens) already exist; this is derivation, trending, and a handful of threshold rules feeding the existing meta-packet path.

**Operational effort.** Approximately zero incremental Chad-minutes: the numbers render inside a report he already reads, and meta-packets should fire roughly monthly at most. The whole point is that it costs attention only when attention is the thing failing.

**Blast radius.** The failure mode is becoming nagware: a meta-packet that fires too often is itself a CF-02 violation and trains the exact rubber-stamping it exists to catch. Thresholds must start loose. Also: these metrics observing the operator must never leak into anything resembling autonomy justification — they inform Chad, not the trust ledger.

**Dependencies.** None hard. Complements Win 4 (queue-age is the absence-side of the same picture).

---

## Win 3 — The Canary Program

**What it is.** A small scheduled corpus of synthetic probes, run as boring health missions: (a) **canary defects** — known-bad changes periodically injected into the review queue; the reviewer must reject them with diff-grounded reasons (HB-03, HB-09); (b) **canary tasks** — known-good historical tasks re-run and diffed against their recorded outputs to detect silent model change (IN-04, TE-06 re-validation); (c) **canary documents** — test files carrying forbidden markers (including image/archive formats) fired at the ingestion and dispatch boundaries, which must reject them (EW-01/EW-02 recovery evidence: "boundary rejection verified live with a test document"). Results are pass/fail lines in the evidence feed.

**Scenarios affected.** HB-03, IN-04, HB-06 (partial — deterministic canaries are the uncorrelated check layer the campaign says is the only one that doesn't share the model's blind spots), HB-09 (partial), TE-06 (partial), EW-01 (partial), EW-02 (partial).

**Risk reduced.** Three Top-25 entries directly: **#11 HB-03** (the LGTM machine — the two-machine architecture silently collapsing to one), **#25 IN-04** (silent model degradation), **#21 HB-06** (partial — correlated blindness becomes measured rather than assumed away). Plus the live-fire half of **#4 EW-01/02**. The campaign's phrasing is the spec: "a reviewer is only alive if it can be observed rejecting things" and "canary tasks are the only instrument that measures the model rather than the weather."

**Engineering effort.** **M** — building the corpus (a handful of known-bad diffs, frozen task/output pairs, marker-bearing test files in awkward formats) plus a scheduler and a comparator.

**Operational effort.** Machine-time weekly. Chad: zero on green; a failed canary is exactly the day his attention is warranted. Corpus refresh ~quarterly (one short session).

**Blast radius.** Two sharp edges. (1) Canary events **must not enter the trust/evidence feeds** — a canary counted as an observation is a self-inflicted TE-01/TE-07; tag canary provenance and exclude it at every recorder. (2) A stale corpus gives false confidence (the model learns the canaries' shape, or the boundary reject-list already covers only the tested formats); escaped-defect RCAs (HB-04's lesson) should continuously feed new canaries.

**Dependencies.** Win 5 (provenance tagging keeps canaries out of the ledger). Feeds Win 1 (audit self-test) and Win 7 (boundary verification).

---

## Win 4 — The Horizon Ledger

**What it is.** One consolidated section in the existing evidence feed listing everything in Olympus that has a date, an age, or a horizon — surfaced *before* it fires: credential and token expiry dates (IN-09's "expiry horizons tracked as maintenance items"), Tailscale node-key expiry (IN-01), WAITING items past their recheck date (MC-05), age-in-ESCALATING (MC-07), emitted-but-unacknowledged packet age (CF-06, OP-10), review-queue age (HB-01) and review-duration trend (HB-08), dispatched-with-no-evidence age with the automatic flip to PAUSE (MC-04), ritual-generation timestamp staleness (MC-02), push lag and backup lag (IN-06's "two numbers visible weekly, not discovered at the funeral"), evidence age on promotions (TE-06) and staleness bands on opportunities (IS-04), and standing-instruction review dates (OP-08).

**Scenarios affected.** IN-01, IN-09, MC-05, MC-07, CF-06, HB-01, HB-08 (partial), MC-04 (partial), MC-02 (partial), OP-10 (partial), TE-06 (partial), IS-04 (partial), OP-08 (partial), OP-01 (partial — queue-age-at-return is the metric that matters), OP-02 (partial — runway horizons), IN-06 (partial).

**Risk reduced.** No Top-25 entries at full weight — this win buys breadth, not existential depth: it retires the largest *likelihood* mass on the list (five Very High and four High likelihood scenarios), converting an entire class of "scheduled outages with a known date" and "silent graveyards" from incidents into maintenance lines. The campaign's IN-01 lesson is the thesis: "expiring credentials are scheduled outages with a known date — the system knows the date and must surface it as a maintenance item, not discover it as an incident."

**Engineering effort.** **M** — many small metrics, each trivially derivable from existing state (stores already carry timestamps, recheck dates, dispatch times); the work is coverage and one rendering surface.

**Operational effort.** ~2–3 Chad-minutes/week scanning the horizon section; occasional five-minute rotation tasks that would otherwise have been mystery outages bounded by his next attention window.

**Blast radius.** A horizon list that grows unbounded becomes MC-10's unreadable wall and gets skipped (OR-05); it must render only items inside their warning window. A wrong date (e.g., mis-parsed expiry) suppresses the alarm precisely when trusted — expiry entries should be verified by read-only probes where possible.

**Dependencies.** None. Feeds Win 2 (queue-age is shared vocabulary) and Win 1 (several conservation checks consume the same age fields).

---

## Win 5 — Event Identity & Reality-Terminated Provenance

**What it is.** Enforce, at every recorder in the trust/evidence path, the two questions the campaign calls the cheapest in the system: **"have I seen this exact event?"** (unique observation identity — provenance-keyed dedup at ingestion, idempotent appends, mission-ID idempotency on dispatch/execution) and **"does this observation's chain end at something the system didn't write?"** (reality-terminated provenance: every observation must trace to a merged PR, a test run, a human entry with a source citation, or an external artifact — chains terminating in another Hermes output are rejected as circular). Plus the IS-05 corollary: evidence records carry a source-citation field, and validation checks citing no verifiable source cannot be marked STRONG.

**Scenarios affected.** TE-01, TE-05, TE-07, IS-05 (partial — the citation-field defense), EW-06 (partial — case-rooted provenance chains become mechanically findable), MC-03 (partial — idempotent mission identity), IS-08 (partial — fingerprint reject-count alarm as replay signature).

**Risk reduced.** Two Top-25 entries at or near full weight: **#12 TE-07** (the self-licking evidence loop — "confidence compounds without any new contact with reality," corrupting the epistemology itself) and **#19 IS-05** (ROI hallucination through the human gate), plus **#22 EW-06** partially. This win protects the thing the campaign says everything else is a cache of: "the ledger is a cache of what the evidence implies." Every restore, replay, and re-derivation story in the TE category (TE-03/04/05) silently assumes this win exists.

**Engineering effort.** **M** — an identity/provenance schema on observations plus rejection logic at a small, closed set of recorders (the source allowlist already bounds who can record).

**Operational effort.** Zero ongoing; occasional contradiction-queue entries when a rejection needs adjudication (minutes, and those minutes are the system working).

**Blast radius.** Over-strict identity drops legitimate distinct events that look similar (under-counting — the safe direction, per fail-toward-distrust, but it throttles honest promotion). Provenance rules that are painful to satisfy will be worked around — the legitimate path must stay cheaper than the shortcut (MC-07's lesson generalized).

**Dependencies.** None hard. Load-bearing for Win 9 (reconciliation trusts identity), Win 3 (canary exclusion), and Win 1 (dedup checks).

---

## Win 6 — Boot-as-Deployment

**What it is.** An environment manifest for each machine (toolchain versions, provider routing config, key paths, NTP offset) plus a self-check that runs at every boot and on a schedule: manifest diff, `git fsck` and stale-lock/worktree-prune scans, read-only auth probes, and a smoke mission — with the agent refusing the queue until the check passes ("degraded: environment changed"). The campaign names this exact machinery in HM-09 ("treat every reboot as a deployment — verified by manifest before trusting it with work") and HM-12, and extends it: routing config diffed as a *safety-critical* manifest (EW-04's detection), post-storm health sweep (IN-11), weekly fsck as "a scheduled line item instead of a weird-Wednesday debugging session" (HM-05).

**Scenarios affected.** HM-02, HM-05, HM-06, HM-09, HM-12, HM-10 (partial — boot auth probes classify lockout as one event), IN-07 (partial — NTP offset check), IN-11 (partial — post-storm sweep), IN-06 (partial — machine reproducible from manifest cuts RTO), TE-09 (partial — clock sanity), EW-04 (partial — routing-drift cause detection; "routing config is exactly the kind of thing that drifts").

**Risk reduced.** Mostly the loud-failure band (Medium impact, High/Very-High likelihood — the entire HM hardware/platform cluster), converting N mystery mission failures into one clear platform event each time. Its existential contribution is indirect but real: it attacks the *cause* side of **#1 EW-04** (config drift after updates) while Win 8 attacks the effect side.

**Engineering effort.** **M** — manifest capture/diff plus a boot gate; each individual check is small and the campaign already enumerates them.

**Operational effort.** Machine-time per boot plus weekly. Chad: acknowledging genuine drift, ~minutes/month.

**Blast radius.** An over-strict manifest blocks the queue on benign drift — safe direction but a throughput tax; a noisy manifest diff becomes ignorable (alarm-fatigue feed). The gate must distinguish "changed" from "changed in ways missions consume."

**Dependencies.** None. Win 8's pin verification and parts of Win 4 (NTP, expiry probes) ride on this check's schedule.

---

## Win 7 — Default-Deny Boundary + Marker Sweep

**What it is.** Harden the existing forbidden-marker isolation invariant in three ways the campaign specifies: (1) **default-deny for unscannable content** — scanned-image PDFs, archives, odd encodings are rejected *as opaque*, never passed as clean ("'I couldn't check it' and 'it's clean' must be opposite verdicts," EW-02); (2) **the same marker check applied at mission dispatch** — mission content, not just documents, so ambiguous phrasing bounces to NEEDS_CHAD instead of running case work through the general pipeline (EW-05); (3) **a scheduled marker sweep** over general stores, logs, commit messages, mission titles, report text, and filenames — including a locally-run OCR pass — to detect past bypasses and metadata leakage (EW-02, EW-06, EW-07, EW-08).

**Scenarios affected.** EW-02, EW-05, EW-08, EW-01 (partial — the boundary exists; this reduces bypass likelihood and post-hoc detection latency), EW-06 (partial — sweep finds absorbed claims), EW-07 (partial — the periodic all-storage scan is the late-discovery net).

**Risk reduced.** The gateway cluster of the existential list: **#4 EW-01/02** is explicitly "the gateway event for EW-04/06/07 — once case material is inside general systems, every downstream copy is exposure," and **#22 EW-06** partially. Impact here is Critical-to-Existential per event; this win narrows the front door and adds the only retroactive detector the domain has.

**Engineering effort.** **M** — the scanner exists; the work is the default-deny policy switch, wiring the check into the dispatcher boundary, and a sweep job over enumerable corpora (local OCR included).

**Operational effort.** Machine-time weekly for the sweep. Chad: ~3 min/week reviewing rejection events — which the campaign says to "treat as saves, logged and celebrated."

**Blast radius.** Default-deny will quarantine legitimate opaque files (the safe direction, but it adds review friction that must not train Chad to rubber-stamp releases). Critical constraint: the OCR sweep must run entirely locally — shipping general-store content to a cloud OCR service to look for PHI would be EW-04 committed by the defense itself.

**Dependencies.** Existing invariant-6 scanning. Win 3 supplies the live-fire tests proving the boundary still rejects.

---

## Win 8 — Expert-Witness Egress Pin + Log

**What it is.** Pin the expert-witness domain's model routing to its approved endpoint list (local or BAA-covered) **at the workspace/routing layer for that domain — not by global default**, exactly as EW-04's containment specifies ("a global default is one update away from wrong"); and log every model-endpoint request from EW workloads (endpoints and timestamps, never content). Any endpoint outside the approved list alarms. The log is what "converts 'we think only X leaked' into evidence" — it must predate any incident to be worth anything.

**Scenarios affected.** EW-04, EW-05 (partial — if a case task is misrouted, the pin and egress log bound and evidence the scope).

**Risk reduced.** **#1 on the Top 25: EW-04, "the single worst event Olympus can produce"** — PHI to a cloud endpoint: HIPAA exposure, protective-order violation, privilege waiver, irreversible loss of custody. This win is small, but it is the designed containment for the campaign's number-one existential risk, and the lowest-effort item on this list. The campaign's lesson: "for this domain the model endpoint is not infrastructure — it is custody of privileged material. The pin must live as close to the data as possible."

**Engineering effort.** **S** — a config pin at the existing routing layer scoped to the isolated workspace, plus one log line per request.

**Operational effort.** Zero routine Chad-minutes; pin-config verification folds into Win 6's manifest diff (routing config as safety-critical manifest).

**Blast radius.** Too-strict pin: EW work stalls against the approved list — the safe direction, resolved by a packet. The egress log must contain endpoints and hashes only; a log capturing prompt content would itself become a retention and discovery surface (EW-07/EW-10 texture).

**Dependencies.** Existing EW workspace isolation; Win 6 for drift detection on the pin itself.

---

## Win 9 — Restore-Reconciliation Discipline

**What it is.** Make restore a first-class event with a fixed sequence, as MC-12/TE-04 describe: any restore of any governed store triggers (1) an automatic **dispatch freeze**, (2) a **reconciliation pass** diffing restored state against ground truth (git branches, PR states, Hermes-side logs, other stores' event trails), (3) **forward replay of gap-window safety events** — demotions and revocations above all ("demotions are the ledger records that must never resurrect"), and (4) a packet where accepting the reconciled history rewrites the record. The trail is annotated with the restore itself. Add a periodic restore-*test* rehearsal so the procedure is verified before it's needed (IN-06's "a restore-test record predating the failure is the evidence that this RTO was ever real").

**Scenarios affected.** MC-12, TE-04, IS-08, TE-03 (partial — the restore path), TE-05 (partial — post-restore replay), MC-01 (partial — reconcile-from-evidence for orphaned missions), IN-06 (partial — the full restore suite is the recovery path).

**Risk reduced.** **#18 TE-04** (restore silently resurrecting revoked autonomy — "a safety decision undone with a technical alibi") plus MC-12's Critical split-brain, where "every downstream consumer inherits the fork" and duplicate external-facing work can launch. This win converts the scariest recovery scenarios in the campaign from judgment-under-pressure into a rehearsed procedure. It is also the reason backups are worth having: "a backup restores *data*, not *truth*."

**Engineering effort.** **M** — a freeze flag, a diff/reconcile health mission over evidence that already exists independently, and a rehearsal schedule.

**Operational effort.** Zero in normal weeks. Monthly restore rehearsal: machine-time plus ~10 Chad-minutes reading the result. On a real restore: the half-day the campaign already budgets, now scripted.

**Blast radius.** A freeze flag stuck on wedges dispatch (loud, safe). A buggy reconciliation that voids legitimate work is the sharp edge — which is why acceptance of the reconciled history stays behind a packet, per the campaign.

**Dependencies.** Win 5 is load-bearing (identity makes the diff trustworthy; idempotent IDs blunt accidental re-dispatch). Backups themselves already exist per HM/IN conventions.

---

## Win 10 — Effect-Level Classification

**What it is.** Wire the classifier's final check at the point of **effect** rather than only at the planning step: the last hop before anything leaves the boundary — an external send, a spend, a publish — re-classifies through the same deterministic rule table, regardless of upstream CONTINUE verdicts. CF-08's detection section specifies it verbatim: "the last hop before an external effect must itself re-classify regardless of upstream verdicts," making decomposition-evasion "structurally impossible rather than just discouraged."

**Scenarios affected.** CF-08, CF-01 (partial — a boundary-crossing action in an unrecognized shape still passes through a known effect-capable hop, where the world's-edge check catches what task-level recognition missed), CF-03 (partial — side-door work that reaches shared egress tooling hits the same check).

**Risk reduced.** **#5 CF-01 and #6 CF-08** — the silent-boundary-violation pair, the constitution's own worst accounting ("one silent boundary violation costs more trust than a thousand correct escalations earn"), plus part of **#17 CF-03**. Few scenarios, enormous mass: these are the failures that spend the trust that never refills. This is the smallest set of scenario IDs on the list attached to the largest per-event stakes outside the EW domain.

**Engineering effort.** **M** — the rule table exists and is deterministic; the work is enumerating the effect-capable tool paths (send, spend, publish — a deliberately small set) and inserting the re-classification call at each.

**Operational effort.** ~Zero: the check is deterministic and silent when upstream classification was right; an occasional extra packet when the effect hop disagrees is the system catching exactly what it should.

**Blast radius.** Over-broad effect rules would fire on routine work and manufacture CF-02 fork inflation — the hop must reuse the same rule table, not grow its own stricter one. An unenumerated effect path is a silent gap; Win 1's coverage audit is the mechanism that proves the hop is actually on every path.

**Dependencies.** Existing deterministic rule table; Win 1 for coverage verification.

---

## What the Top 3 Buy You

The campaign's closing analysis is blunt: Olympus already converts loud failures into pauses and queues; what kills it is the failure class that never makes a sound — governance amended by convenience, a reviewer that flatlines politely, a reader who stops reading. The top three wins are aimed at exactly that class. The **Conservation Audit** makes silent governance erosion arithmetically impossible to hide: every merge, every unit of work, every PAUSE, every counted artifact must balance against its ledger every night, which is the mechanical enforcement of five Top-25 drift scenarios at once. **Attention Instrumentation** points an instrument at the one component the campaign says nothing currently measures — the operator's engagement — so that rubber-stamping, default-rule-by-attrition, and audit-loop decay become trending numbers with thresholds instead of postmortem findings. And the **Canary Program** keeps both of the above honest, plus the reviewer, the model, and the isolation boundary, by regularly feeding the system things it must reject — because in Olympus, a check that is never observed failing is indistinguishable from a check that no longer exists. Together they buy the thing the other 97 scenarios' detection sections quietly assume: proof, renewed daily, that the detectors themselves are still alive and someone is still watching them.

---

## Appendix A — Mechanism Mining: Citation Clusters

How the ten wins were selected. Each row is a mechanism the campaign's detection/containment/lesson fields cite across multiple scenarios; the wins are the ten clusters with the highest weighted mass.

| Mechanism (campaign's own vocabulary) | Cited by (scenario detection/containment/lesson fields) | Became |
|---|---|---|
| Merge/classification/PAUSE/answer conservation audits | HB-07, CF-03, CF-06, CF-07, CF-09, OP-09, OR-02, OR-04, HB-05, IS-07, IS-09, MC-03, MC-04, MC-09, HM-04, OP-07 | Win 1 |
| Decision-latency, default-rate, consumption, packet-entropy metrics | OP-03, OP-05, OP-06, CF-02, CF-05, OR-05 | Win 2 |
| Canary defects / canary tasks / boundary test documents | HB-03, HB-09, IN-04, HB-06, TE-06, EW-01, EW-02, HM-02 (canary mission post-repair) | Win 3 |
| Expiry horizons, age-in-state, queue age, staleness bands, lag numbers | IN-01, IN-09, MC-02, MC-04, MC-05, MC-07, CF-06, HB-01, HB-08, OP-01, OP-02, OP-08, OP-10, TE-06, IS-04, IN-06 | Win 4 |
| Unique event identity / provenance-keyed dedup / reality-terminated chains | TE-01, TE-05, TE-07, IS-05, IS-08, EW-06, MC-03 | Win 5 |
| Environment manifest, boot self-check, fsck/prune scans, smoke mission | HM-02, HM-05, HM-06, HM-09, HM-10, HM-12, IN-06, IN-07, IN-11, TE-09, EW-04 | Win 6 |
| Forbidden-marker scanning: default-deny, dispatch boundary, store/metadata sweeps | EW-01, EW-02, EW-05, EW-06, EW-07, EW-08 | Win 7 |
| Workspace-scoped endpoint pin + egress log | EW-04, EW-05 | Win 8 |
| Restore ⇒ freeze, reconcile against ground truth, replay safety events forward | MC-01, MC-12, TE-03, TE-04, TE-05, IS-08, IN-06 | Win 9 |
| Effect-level (last-hop) re-classification | CF-01, CF-08, CF-03 | Win 10 |
| Per-mission ceilings (tokens/steps/wall-clock) + priority shedding | HM-07, HM-08, IN-10, MC-06 | Cut (natural #11) |
| Layered error classification (auth vs. remote vs. DNS vs. clock vs. storm) | HM-10, IN-02, IN-03, IN-08, IN-09, IN-11 | Cut (loud-failure band; architecture already pauses safely) |

---

## Appendix B — Scoring Worksheet

Points: Top-25 scenario = 3, other = 1; partial coverage = half. Effort: S = 1, M = 2, L = 3. Score = points ÷ effort.

**Win 1 — Conservation Audit (19.5 pts / L = 6.5)**
Full: HB-07 (3), CF-03 (3), MC-09 (3), CF-07 (1), CF-09 (1), OP-09 (1).
Partial: HM-04 (1.5), OR-02 (1.5), CF-06 (0.5), OR-04 (0.5), HB-05 (0.5), IS-07 (0.5), IS-09 (0.5), MC-03 (0.5), MC-04 (0.5), OP-07 (0.5).

**Win 2 — Attention Instrumentation (12.5 pts / M = 6.25)**
Full: OP-03 (3), CF-05 (3), OR-05 (3), CF-02 (1), OP-05 (1).
Partial: OP-06 (1.5).

**Win 3 — Canary Program (11.5 pts / M = 5.75)**
Full: HB-03 (3), IN-04 (3).
Partial: HB-06 (1.5), EW-01 (1.5), EW-02 (1.5), HB-09 (0.5), TE-06 (0.5).

**Win 4 — Horizon Ledger (11.0 pts / M = 5.5)**
Full: IN-01 (1), IN-09 (1), MC-05 (1), MC-07 (1), CF-06 (1), HB-01 (1).
Partial: HB-08 (0.5), MC-02 (0.5), MC-04 (0.5), OP-01 (0.5), OP-02 (0.5), OP-08 (0.5), OP-10 (0.5), TE-06 (0.5), IS-04 (0.5), IN-06 (0.5).

**Win 5 — Event Identity & Provenance (9.0 pts / M = 4.5)**
Full: TE-07 (3), TE-01 (1), TE-05 (1).
Partial: IS-05 (1.5), EW-06 (1.5), MC-03 (0.5), IS-08 (0.5).

**Win 6 — Boot-as-Deployment (9.0 pts / M = 4.5)**
Full: HM-02 (1), HM-05 (1), HM-06 (1), HM-09 (1), HM-12 (1).
Partial: EW-04 (1.5), HM-10 (0.5), IN-07 (0.5), IN-11 (0.5), IN-06 (0.5), TE-09 (0.5).

**Win 7 — Default-Deny Boundary + Marker Sweep (8.5 pts / M = 4.25)**
Full: EW-02 (3), EW-05 (1), EW-08 (1).
Partial: EW-01 (1.5), EW-06 (1.5), EW-07 (0.5).

**Win 8 — Expert-Witness Egress Pin + Log (3.5 pts / S = 3.5)**
Full: EW-04 (3). Partial: EW-05 (0.5).

**Win 9 — Restore-Reconciliation Discipline (7.0 pts / M = 3.5)**
Full: TE-04 (3), MC-12 (1), IS-08 (1).
Partial: TE-03 (0.5), TE-05 (0.5), MC-01 (0.5), IN-06 (0.5).

**Win 10 — Effect-Level Classification (6.0 pts / M = 3.0)**
Full: CF-08 (3). Partial: CF-01 (1.5), CF-03 (1.5).

Some scenarios legitimately appear under two wins (e.g., EW-01/02 need both the default-deny boundary and live-fire canaries; MC-04 needs both an age rule and evening reconciliation) — the campaign names both layers for them, and the double-count reflects genuine defense-in-depth, not inflation. No scenario is counted at full weight by more than one win.

---

## Appendix C — Residual Risk: What the Ten Wins Do Not Cover

Honesty section. Scenarios not materially touched by any win, and why that is acceptable (or not):

- **Loud infrastructure failures** (IN-02, IN-03, IN-05, IN-08, IN-12, HB-01/02 recovery paths): the campaign concludes the architecture already converts these into pauses and queues; residual work is retry/backoff hygiene already prescribed by existing conventions.
- **Runaway cost and priority under scarcity** (HM-07, HM-08, IN-10, MC-06): the natural #11 — per-mission ceilings on tokens/steps/wall-clock plus priority-ordered shedding. HM-07 alone (High likelihood, High impact, "threatens the economics that justify Olympus") argues for doing this soon after the ten; it was outscored, not dismissed.
- **Income Scout input quality** (IS-01, IS-03, IS-06, IS-10): defended by existing three-gate structure (score ≠ confidence ≠ decision) and by never-chase; the residual instruments (plausibility bands, source-concentration, portfolio-shape reports) are worthwhile but carry less weighted mass per unit effort.
- **Human-artifact scenarios** (OR-06 continuity document, EW-10 methodology statement, EW-03 per-case context discipline, OR-03 rehearsal calendar, OP-05 post-call rule): the campaign is explicit that these are values/documents/rituals only Chad can author. No implementation change substitutes; Win 3 and Win 7 reduce adjacent exposure but the core mitigations are his to write. EW-03 (#3 existential) deserves particular flagging: citation-per-assertion drafting discipline is partly tooling-supportable, but the campaign frames it as practice discipline inside the isolated domain — out of scope for this lane's definition of an implementation change.
- **The Final Question's erosion class**: Win 2 is the only instrument pointed at it, and the campaign is clear that instrumentation can measure the relationship but not sustain it. The residual owner is the operator, by constitutional design.

---

*Lane 1 deliverable, design-only. Scoring and all mechanisms are derived exclusively from `olympus-failure-injection-campaign-v1.md`. Honest gaps: per-mission budget ceilings (HM-07/HM-08/IN-10/MC-06) narrowly missed the cut and are the natural #11; OR-06 (continuity document), EW-10 (methodology statement), and OR-03 (runbook rehearsal calendar) are human artifacts and rituals the campaign itself says no implementation change can substitute for.*
