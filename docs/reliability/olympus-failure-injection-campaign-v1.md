# Olympus Failure Injection Campaign v1

**Role:** Chief Reliability Engineer, Olympus
**Status:** Design only. No code changes. No implementation tasks. The Olympus architecture is treated as **fixed** — this document stress-tests the system exactly as it exists after six months of successful operation.
**Grounding:** `docs/chief-of-staff/MISSION.md` (Mission Control = Executive Brain; Hermes = Executive Assistant; Chad = Executive), `docs/chief-of-staff/HUMAN_FIRST.md` (six never-delegated boundaries; CONTINUE / PAUSE / NEEDS_CHAD escalation contract), `docs/executive-operating-loop-contract.md` (Morning/Evening Packets, evidence feeds, memorygraph trust tiers, expert-witness isolation, four interrupt classes), `docs/design/opportunity-scout-engine.md` (Income Scout: deterministic scoring, atomic JSON store, inbox ingestion, dedup, lifecycle).

## Method and scales

Each scenario is a realistic *operational* failure (not a software bug) injected into a six-month-old, healthy Olympus.

- **Likelihood** (over a 6-month operating window): **Very High** (near-certain, recurring), **High** (expected at least once), **Medium** (plausible once), **Low** (unlikely but credible), **Very Low** (rare but must be survivable).
- **Impact:** **Low** (annoyance, self-heals), **Medium** (lost work/time, contained), **High** (wrong decisions, money, or trust damaged), **Critical** (governance boundary crossed or major data loss), **Existential** (threatens Olympus's reason to exist — Chad's trust, Chad's profession, or the audit trail itself).
- **Decision Packet required?** — whether recovery crosses a HUMAN_FIRST boundary (money, irreversibility, external sends, credentials, relationships, values) and therefore requires a decision-ready NEEDS_CHAD packet. Where the failure *is* operator unavailability, the packet queues per the attention-economy rules; it cannot be waived.
- **RTO** = expected recovery time once detected.

Scenario IDs: OP (Operator), MC (Mission Control), HM (Hermes Mini), HB (Hermes MBP), TE (Trust Engine), CF (Continue-Until-Fork), IS (Income Scout), EW (Expert Witness), IN (Infrastructure), OR (Organizational).

---

## Category 1 — Operator (OP-01 … OP-10)

The operator is a practicing anesthesiologist with a ~90-minute daily attention window. Olympus's constitution says the human's ability to *not* watch the system is the entire value proposition. These scenarios attack that.

#### OP-01 — Call-schedule surge: Chad unavailable 72+ hours
**Failure:** A run of hospital call days plus a sick partner keeps Chad away from the loop for three-plus days. NEEDS_CHAD packets queue; missions at forks hold; the Morning Packet goes unread.
**Likelihood:** Very High. **Impact:** Medium — throughput loss only, *if* holds are clean.
**Detection:** Morning Packet unacknowledged N consecutive days; NEEDS_CHAD queue age exceeds threshold; `waiting_for_you` list grows without shrinkage.
**Containment:** Automatic — the escalation contract already handles it: forked work holds in NEEDS_CHAD, throttled work in PAUSE; nothing proceeds past a boundary. Only the four interrupt classes may page him; everything else waits for the next packet.
**Decision Packet:** No — the queued packets *are* the containment.
**Recovery:** Chad returns, works the `waiting_for_you` queue oldest-boundary-first; stale packets re-validated before answering (evidence may have aged).
**RTO:** One 90-minute window to drain a 3-day queue.
**Recovery evidence:** NEEDS_CHAD queue age back under threshold; all resumed missions show a fresh CONTINUE classification; Evening Report reconciles the gap days.
**Lesson:** Absence is a normal operating mode, not an incident. The metric that matters is *queue age at return*, not queue length — packets must stay decision-ready (seconds to decide) even after aging.

#### OP-02 — Extended incapacitation (weeks)
**Failure:** Injury or illness removes Chad for 3–6 weeks. Subscriptions, API credits, credentials, and case deadlines age out. Nobody else can act — money, credentials, and external sends are never-delegated.
**Likelihood:** Low. **Impact:** Critical — Olympus winds down by starvation; expert-witness deadlines may be missed with professional consequences.
**Detection:** Same signals as OP-01 but sustained; spend-runway and credential-expiry horizons visible in evidence feeds.
**Containment:** Automatic degradation to read-only posture: no new money-adjacent or external-send missions started; PAUSE everything with a written resume plan; conserve API budget by suspending discretionary (Build Program, Income Scout validation) work.
**Decision Packet:** Yes — every restart of spend or external activity on return.
**Recovery:** On return: re-validate every credential and price before resuming; treat all evidence older than the absence as stale; re-run the bottleneck analysis from scratch.
**RTO:** 1–2 weeks of gradual resumption.
**Recovery evidence:** All credentials re-verified; no action taken during the absence appears in the audit trail; first post-return Evening Report reconciles the entire gap.
**Lesson:** Olympus has a single human point of failure *by constitutional design*. The correct behavior under long absence is graceful starvation, and the system must prove it starved gracefully rather than improvised.

#### OP-03 — Rubber-stamp approvals
**Failure:** Six months of mostly-correct packets trains Chad to approve without reading. A packet authorizing an external send (a client email misstating his availability) is approved in four seconds.
**Likelihood:** High — automation complacency is the default human response to reliable automation.
**Impact:** High — an external send under Chad's name is a relationships/reputation boundary crossed *with* formal approval.
**Detection:** Hard — the approval is procedurally valid. Proxy signals: decision latency trending toward zero across packet types; approvals of packets whose default recommendation was "do nothing"; post-hoc contradiction (Chad later countermands what he approved).
**Containment:** None automatic that respects the fixed architecture — the packet format's "default if you do nothing" clause is the safety valve: a non-answer is always safe, so a hasty *approval* is the only dangerous path.
**Decision Packet:** N/A — the failure is inside the packet mechanism itself.
**Recovery:** Countermand or correct the external action (a human-to-human repair, only Chad can do it); re-review recent fast approvals for other misfires.
**RTO:** Hours to days depending on what was sent.
**Recovery evidence:** Corrected communication acknowledged by recipient; audit of last N approvals finds no other misfires.
**Lesson:** Approval latency is a trust-calibration instrument. A four-second yes is worth less than no answer — the Evening Report should treat suspiciously fast approvals as an unknown, not a success.

#### OP-04 — Wrong-packet approval (two packets, crossed answers)
**Failure:** Two NEEDS_CHAD packets arrive in the same window — one to decline a low-value engagement, one to accept a deposition date. Chad, between OR cases, answers them swapped.
**Likelihood:** Medium. **Impact:** High — an external commitment made and an opportunity declined, both under his name.
**Detection:** Mismatch between answer text and packet question where free-text is given; otherwise post-hoc — the Evening Report shows two resolved packets whose outcomes contradict Chad's known intent.
**Containment:** One-question-per-packet rule (already constitutional) limits blast radius; execution of externally-visible approvals staged until end of the attention window gives a natural cancellation buffer where the architecture already batches sends.
**Decision Packet:** Yes — to reverse either external action.
**Recovery:** Chad reverses both actions personally; the two missions re-fork with fresh packets.
**RTO:** Same day if caught in the Evening Report; days otherwise.
**Recovery evidence:** Both counterparties confirm the corrected positions; re-issued packets answered correctly.
**Lesson:** Packets answered inside hospital gaps are answered under load. The evening ritual is the designed catch-net — it must render *what was decided today* prominently, not just what was done.

#### OP-05 — Post-call fatigue window
**Failure:** Chad works the queue post-call after 24 sleepless hours. Judgment on money and case-strategy packets is measurably degraded — the exact impairment anesthesiology treats as a patient-safety hazard in itself.
**Likelihood:** Very High (recurs monthly). **Impact:** High cumulative — a slow leak of degraded decisions into the highest-authority channel.
**Detection:** Indirect only: decision-reversal rate (Chad countermanding his own recent approvals), time-of-day/post-call correlation in the decision log.
**Containment:** None automatic — the machine applies values, it does not author them, and it cannot grade the human's cognition. The honest containment is the existing default-if-no-answer clause: doing nothing is always safe.
**Decision Packet:** N/A.
**Recovery:** Chad self-imposes a rule (a value he authors, which the Decision Engine then applies): no money/irreversible packets answered post-call; those wait a day.
**RTO:** Immediate once the rule is set.
**Recovery evidence:** Decision log shows money-class packets consistently answered outside post-call windows; reversal rate declines.
**Lesson:** Olympus's most failure-prone component has a duty cycle. Packets should carry their *perishability* honestly — most "urgent" decisions survive 24 hours, and the packet's do-nothing default is the mechanism that makes waiting safe.

#### OP-06 — Notification overload → alarm fatigue
**Failure:** A bad week (provider flakiness + a mission storm) produces dozens of interrupts. Chad mutes the channel — and stays muted for weeks. A genuine safety-class interrupt later dies silently.
**Likelihood:** High. **Impact:** Critical — the four-class interrupt router only works if the channel is trusted; alarm fatigue is the same failure mode that kills patients in ORs.
**Detection:** Interrupt-acknowledgment latency spikes to infinity; safety-class interrupts unacknowledged.
**Containment:** The deny-by-default router *is* the containment and it failed upstream — so the fallback is constitutional: unacknowledged safety escalations leave the mission in ESCALATING, which has no CONTINUE row; nothing proceeds.
**Decision Packet:** Yes — re-opening the channel and resolving stalled ESCALATING items requires Chad, with reasons recorded.
**Recovery:** Purge the interrupt backlog; re-classify what caused the storm (almost always: items that were not truly in the four classes); Chad unmutes.
**RTO:** One attention window, plus days of re-earned trust in the channel.
**Recovery evidence:** Interrupt volume back to baseline (target: near-zero per day); safety-class acknowledgment latency back under minutes; Chad's mute removed.
**Lesson:** Every non-four-class interrupt that leaks through is a withdrawal from the channel's trust account. The interrupt budget must be treated like an anesthetic dose: the correct amount is the minimum effective, and overdose has a lasting washout period.

#### OP-07 — Contradictory instructions across channels
**Failure:** Chad tells Hermes in conversation "drop the kanban work, focus on Income Scout," but the Mission Control plan (edited last weekend) still ranks kanban first. Both systems obey their own instruction; the Morning Packet and Hermes's actual behavior diverge.
**Likelihood:** High. **Impact:** Medium — wasted work and a confusing audit trail; High if the contradiction touches priorities feeding money decisions.
**Detection:** Evening Report reconciliation: plan-vs-actual divergence with no PAUSE/NEEDS_CHAD explaining it; Hermes's constitution says it never invents state, so any divergence from the published plan is itself an anomaly.
**Containment:** Division-of-labor rule already decides the winner: Mission Control owns the plan; conversational instructions that contradict it should classify NEEDS_CHAD ("your instruction contradicts today's plan — which governs?") rather than silently win.
**Decision Packet:** Yes — one packet, one question, contradiction stated with both sources cited.
**Recovery:** Chad answers; the losing instruction is recorded as superseded; plan updated through Mission Control (the only legitimate writer of plan state).
**RTO:** Minutes once surfaced.
**Recovery evidence:** Next Morning Packet reflects the resolution; no further divergence between plan and execution log.
**Lesson:** Contradiction between the Executive's own channels is a first-class fork, not noise. The system must never resolve it by recency or by convenience — only by asking.

#### OP-08 — Stale standing instruction
**Failure:** In month two Chad said "always prefer the cheaper model for Build Program work." In month six a critical expert-witness-adjacent deliverable is quietly produced at degraded quality because the instruction was never scoped or expired.
**Likelihood:** High. **Impact:** Medium-High — silent quality erosion attributed to everything except the true cause.
**Detection:** Hard by design (the instruction is being *obeyed*). Proxies: quality regressions clustering where the standing instruction applies; Evening Report's confidence_changes trending down in one domain.
**Containment:** None automatic — obedience is not a fault the system can see. The both-days rule and evidence-gated confidence at least keep the degradation from being papered over.
**Decision Packet:** Yes — "standing instruction X, issued <date>, has applied to N missions including <new class>; still valid?"
**Recovery:** Chad re-scopes or retires the instruction; affected recent deliverables re-run where it matters.
**RTO:** Days (re-work bound).
**Recovery evidence:** Instruction ledger shows the revision; re-run deliverables pass review at expected quality.
**Lesson:** Standing instructions are values, and values feed the Decision Engine — they need review dates like drug orders need expirations. An instruction old enough to predate its current consequences is a fork.

#### OP-09 — Operator bypasses the loop
**Failure:** Chad, in a hurry, SSHes into the Mini, hand-edits a repo, force-pushes, and tweaks a store JSON. Mission Control's world-state no longer matches reality; the next dispatched mission builds on state that doesn't exist.
**Likelihood:** High (every operator does this eventually). **Impact:** Medium — divergence, confusing failures; High if a governed store was hand-edited (see TE-03, IS-07).
**Detection:** Missions failing on preconditions that the plan says hold; store checksums/audit trail showing mutations with no corresponding mission; git history showing pushes outside mission provenance.
**Containment:** Mutation-boundary rule (each system writes only its own store) makes hand-edits *detectable* as foreign writes; affected missions PAUSE with "world diverged from plan" rather than improvising.
**Decision Packet:** No for reconciliation (it's evidence-gathering); Yes if reconciliation requires discarding work.
**Recovery:** Reconciliation pass: re-derive world-state from the actual repos/stores; Mission Control updates its state through its own persistence layer; hand-edits either adopted as legitimate (recorded, attributed to Chad) or reverted.
**RTO:** Hours.
**Recovery evidence:** Plan preconditions verified against live state; zero unattributed mutations in the following week's audit.
**Lesson:** The Executive is allowed to touch anything — but an unrecorded touch converts the audit trail from evidence into fiction. The cheap fix is behavioral: Chad's direct changes get logged as missions-after-the-fact, ideally same-day.

#### OP-10 — Notification channel silently dead
**Failure:** Phone migration / OS update / expired push credential kills the interrupt channel. Chad reads silence as health ("it's been quiet — Olympus must be running well") for two weeks while NEEDS_CHAD items age.
**Likelihood:** Medium. **Impact:** High — indistinguishable-from-healthy silence is the most dangerous state in the constitution ("silence must be trustworthy").
**Detection:** Heartbeat asymmetry: system-side sees packets sent but never acknowledged; Chad-side sees no Morning Packet arriving. Either side noticing ends the failure — the Morning Packet's absence is the designed tripwire because it arrives *daily* whether or not anything is wrong.
**Containment:** Automatic: unacknowledged NEEDS_CHAD items keep their missions held; nothing self-approves on timeout, ever.
**Decision Packet:** No — channel repair is operational.
**Recovery:** Restore/re-credential the channel; replay unacknowledged packets in age order; verify with a round-trip test message.
**RTO:** Under an hour once noticed; the *noticing* is the variable (bounded at 1 day by the morning ritual, if the ritual's absence is treated as an alarm).
**Recovery evidence:** Round-trip acknowledgment; queue drained; both rituals delivered and acknowledged on consecutive days.
**Lesson:** The two daily rituals are Olympus's dead-man switch. "No Morning Packet by 9am" must mean *emergency* in Chad's head, not "nice, a quiet day" — that convention costs nothing and bounds every silent-channel failure at 24 hours.

---

## Category 2 — Mission Control (MC-01 … MC-12)

Mission Control is the Executive Brain: it owns world-state, plans, bottlenecks, and reports, writes only through its own `MissionStore`, and never executes.

#### MC-01 — MissionStore corruption (torn write)
**Failure:** Power loss mid-write leaves the mission store truncated. On restart, Mission Control cannot load its queue: plans, in-flight mission states, and dispatch records are unreadable.
**Likelihood:** Medium. **Impact:** High — the Brain has amnesia; in-flight work on both Hermes machines is orphaned.
**Detection:** Load-time schema/parse failure — the store follows the fail-loudly convention (unknown/corrupt → refuse and back up, never silently start fresh over live data).
**Containment:** Automatic: corrupt file backed up aside (`.corrupt-<ts>` convention); Mission Control refuses to dispatch anything until state is restored; Hermes agents, receiving no dispatches, idle safely.
**Decision Packet:** No for restore-from-backup (reversible); Yes if backups are also bad and missions must be reconstructed or abandoned.
**Recovery:** Restore last-good store snapshot; reconcile against ground truth (git branches, PR states, Hermes-side mission logs) to re-adopt or close orphaned missions.
**RTO:** 1–4 hours.
**Recovery evidence:** Store loads clean; every orphaned mission either re-adopted (matching a live branch/PR) or explicitly closed with reason; next Morning Packet generated normally.
**Lesson:** The queue is reconstructible only because execution leaves independent evidence (branches, PRs, logs). Reconciliation-from-evidence is the real backup; the JSON snapshot is just the fast path.

#### MC-02 — Scheduler dead: no Morning Packet
**Failure:** The launchd/cron job driving the rituals dies after an OS update. No Morning Packet is produced; no Evening Report closes the books. The loop's heartbeat stops while everything else looks alive.
**Likelihood:** High. **Impact:** Medium alone; High if it persists — autonomous work continues without the daily plan/audit cycle that legitimizes it.
**Detection:** Chad-side: no packet by the expected hour (see OP-10 — the ritual's absence is an alarm). System-side: ritual-generation timestamps stale.
**Containment:** Constitutional: PAUSE items that resolve "in the next brief" simply wait longer; nothing escalates or approves itself in the gap. Hermes keeps answering from the *last published* state and must not invent a plan.
**Decision Packet:** No.
**Recovery:** Restart/re-register the scheduler; generate the missed packets late (marked late, not backdated); Evening Report covers the gap explicitly.
**RTO:** Under 1 hour.
**Recovery evidence:** Packets resume on schedule for 3 consecutive days; the gap appears in the audit trail as a gap, not smoothed over.
**Lesson:** A missing ritual must never be synthesized after the fact as if on time. The trail's honesty about its own outages is what keeps "silence is trustworthy" true.

#### MC-03 — Duplicate dispatch
**Failure:** Mission Control dispatches a mission, the acknowledgment is lost to a network blip, a retry dispatches it again. Hermes Mini runs the same mission twice — two branches, two PRs, double token spend; or worse, the second run mutates state the first already changed.
**Likelihood:** High (at-least-once delivery without idempotency does this eventually). **Impact:** Medium — waste and confusion; High if the mission touches a governed store twice.
**Detection:** Two executions with the same mission ID in Hermes logs; duplicate near-identical PRs; Evening Report counts don't reconcile with plan counts.
**Containment:** Mission IDs make duplicates *detectable*; review stage (Hermes MBP) catches twin PRs before merge; mutation-boundary rule limits store damage to the mission's own outputs.
**Decision Packet:** No — deduplication is reversible cleanup.
**Recovery:** Close the younger duplicate, delete its branch, keep the elder; record the duplicate-dispatch event as evidence for the reliability record.
**RTO:** Minutes per duplicate.
**Recovery evidence:** One surviving execution per mission ID; reconciled counts in the Evening Report.
**Lesson:** Dispatch is at-least-once in practice no matter what the design says; execution must therefore be treated as possibly-duplicated and reconciled by mission ID *every evening*, not just when suspicion arises.

#### MC-04 — Lost mission (dispatched into the void)
**Failure:** Mission marked `dispatched` in the store, but the crash/blip happened before Hermes received it. Nothing is running, nothing errors. The mission ages silently in a state that claims progress.
**Likelihood:** High. **Impact:** Medium — silent non-progress; High if downstream plans assume its completion.
**Detection:** Liveness gap: mission in `dispatched`/`running` with no Hermes-side heartbeat or log entry for it. The Evening Report's plan-vs-actual reconciliation is the designed net: a mission that produced no evidence all day is an anomaly by the evidence-or-silence rule.
**Containment:** Automatic staleness rule: dispatched-with-no-evidence beyond a threshold flips the mission to PAUSE ("dispatch unconfirmed") rather than remaining in limbo.
**Decision Packet:** No.
**Recovery:** Re-dispatch with the same mission ID (idempotency per MC-03 protects against the original turning out to be alive).
**RTO:** Detection-bound: worst case one day (evening reconciliation), then minutes.
**Recovery evidence:** Mission produces execution evidence; state transitions match the Hermes-side log.
**Lesson:** "Dispatched" is a claim about *sending*, not *receiving*. Every state that asserts remote activity must be paired with the remote's own evidence, or it decays to unknown.

#### MC-05 — Stuck mission: WAITING forever
**Failure:** A mission PAUSEd on an external blocker (waiting for a vendor email, a package release, a court date). The blocker resolves in the world, but nothing tells Olympus. Six weeks later the mission is still WAITING with a perfectly clean written reason.
**Likelihood:** Very High. **Impact:** Medium — opportunity cost, invisible because PAUSE is (correctly) silent until the next brief.
**Detection:** Age-in-state metric: WAITING items surfaced in the Morning Packet's `waiting_for_you`/loop section with age; anything past its stated resume-check date is flagged.
**Containment:** Automatic: PAUSE items must carry a resume plan (constitutional: "a paused task with clean state, a written reason, and a resume plan is good work") — a resume plan without a recheck date is rejected at classification time.
**Decision Packet:** No for recheck; Yes only if the blocker's resolution changes scope.
**Recovery:** Recheck the blocker; either resume (CONTINUE), re-PAUSE with a new date, or close as overtaken by events.
**RTO:** Minutes per item once surfaced.
**Recovery evidence:** No WAITING item older than its recheck date; count of overdue-recheck items in the Evening Report is zero.
**Lesson:** PAUSE is a feature only when it has a pulse. The failure isn't stopping — it's a resume plan that no process ever executes.

#### MC-06 — Priority inversion
**Failure:** A low-priority Build Program mission holds a long-lived resource — the Mini's only clean worktree slot for the main repo, or the review queue's head — while the day's ONE recommendation (Decision Engine's top-ranked action) sits behind it. The plan says A-first; the machine is physically doing Z-first.
**Likelihood:** High. **Impact:** Medium — the highest-leverage work is systematically the most delayed, silently inverting the North Star.
**Detection:** Plan-position vs. start-time correlation in the Evening Report: if rank-1 items routinely start last, inversion is structural. Resource-hold time by mission priority.
**Containment:** Preemption is allowed *because* PAUSE is cheap and constitutional: the low-priority holder is PAUSEd with clean state and a resume plan; the resource goes to the ranked work.
**Decision Packet:** No.
**Recovery:** Preempt, run the ranked mission, resume the paused one.
**RTO:** Minutes.
**Recovery evidence:** Rank-1 plan items show start times within the day they were ranked; preempted missions resume and complete.
**Lesson:** Deterministic ranking upstream is worthless if the execution substrate is FIFO. Priority must be enforced at the point of resource contention, and PAUSE-for-preemption must be recorded so the audit trail explains the churn.

#### MC-07 — ESCALATING wedge
**Failure:** A mission escalated on a HIGH safety risk. Chad resolved it verbally-in-passing weeks ago, but no RESOLVE event with a reason was ever recorded — and ESCALATING has *no CONTINUE row by design*. The mission is constitutionally immortal.
**Likelihood:** Medium. **Impact:** Medium — one wedged mission; High if it holds a resource (MC-06) or blocks a plan chain.
**Detection:** Age-in-ESCALATING metric; any escalation older than a day appears in every Morning Packet until resolved (safety items are exactly the four-class interrupts that may repeat).
**Containment:** The wedge *is* containment working correctly — safety is never waved through. No automatic unwedging is permissible.
**Decision Packet:** Yes — RESOLVE requires Chad's stated reason; this is the packet.
**Recovery:** Present the escalation as a fresh decision-ready packet (the original evidence chain plus what changed); Chad records the resolution formally.
**RTO:** One attention window.
**Recovery evidence:** RESOLVE event with reason in the state log; mission exits ESCALATING through the enumerated transition table only.
**Lesson:** Verbal resolutions don't exist. If the human resolved it but the ledger didn't hear, the system is right to stay stopped — the fix is making formal resolution *cheaper than* the verbal shortcut.

#### MC-08 — Ritual timing anomaly (DST / schedule drift)
**Failure:** Daylight-saving transition (or a timezone-naive cron) shifts the Morning Packet into Chad's OR hours and the Evening Report to mid-afternoon. Packets are produced on schedule by the machine's clock and systematically missed by the human's life.
**Likelihood:** High (twice a year, guaranteed, plus schedule changes). **Impact:** Low-Medium — the loop's touchpoints decouple from the attention window; queue-age and rubber-stamping pressure (OP-03) both rise.
**Detection:** Acknowledgment-latency shift correlated with a clock transition; packets consistently read hours after production.
**Containment:** None needed automatically — packets are pull-consumable whenever Chad arrives; nothing expires.
**Decision Packet:** No.
**Recovery:** Re-anchor ritual times to Chad's local wall-clock and current hospital schedule.
**RTO:** Minutes.
**Recovery evidence:** Production-to-acknowledgment latency back under an hour for a week.
**Lesson:** The rituals serve a human circadian schedule, not a cron expression. Ritual timing is an operator-value (Chad authors it), and it drifts twice a year unless owned.

#### MC-09 — Evening Report built from stale evidence
**Failure:** The Evening Report proudly counts a merged PR and two established memory claims — but the PR was reverted an hour after merge and the claims came from the reverted work. The books close on fiction; the Compound Engine records capability growth that doesn't exist.
**Likelihood:** Medium. **Impact:** High — the audit trail is Olympus's foundation; a report that flatters is worse than no report ("proves, not reports, is deliberate").
**Detection:** Evidence-freshness check at report build: every counted artifact re-verified against its source of truth (PR state re-queried, claim status re-read) at close time, not dispatch time. Reverts after close appear as next-day corrections.
**Containment:** Both-days rule and >=2-observations rule already resist single-point fictions propagating into trends; contradicted claims never promote.
**Decision Packet:** No.
**Recovery:** Issue a corrected report (marked as correction); reverse the affected compound-engine observations; demote/flag the claims sourced from reverted work.
**RTO:** Next report cycle.
**Recovery evidence:** Correction entry in the trail; compound metrics re-derived match ground truth on spot-check.
**Lesson:** *Proving* what changed means verifying at close-of-books, not trusting the day's own receipts. The report's integrity outranks its punctuality.

#### MC-10 — Unbounded queue growth
**Failure:** Income Scout inflow, Build Program ideas, and PAUSEd items accrete faster than completion for weeks. The store bloats; ranking, packet generation, and reconciliation all slow; the Morning Packet's plan section becomes an unreadable wall.
**Likelihood:** High. **Impact:** Medium — degradation is gradual and self-reinforcing (slower loop → less throughput → deeper backlog).
**Detection:** Store size, queue depth, and ritual-generation latency trends in the evidence feeds; plan sections exceeding what fits a 90-minute window.
**Containment:** The Bottleneck Engine is the designed answer: the Morning Packet carries ONE recommendation regardless of queue depth; the queue's depth must never leak into Chad's window.
**Decision Packet:** Yes — bulk-closing or archiving missions is discarding work (values call: what Olympus stops intending to do).
**Recovery:** Triage pass: archive dead items with reasons, merge duplicates, expire overtaken opportunities via lifecycle transitions; keep the store lean.
**RTO:** One focused session plus a packet.
**Recovery evidence:** Queue depth and store size back under thresholds; ritual latency restored; archived items carry reasons.
**Lesson:** An intention queue is a liability ledger. Olympus must be as deliberate about *un-planning* work as planning it, and archiving-with-reason is honest, not defeat.

#### MC-11 — Malformed Morning Packet refused whole
**Failure:** A partial deploy or hand-edit ships a packet with one malformed field. Per contract, parsing is all-or-nothing (`MorningBriefError`) — Hermes refuses the entire packet. The day runs planless: correct behavior, real outage.
**Likelihood:** Medium. **Impact:** Low-Medium — one day of degraded coordination; the refusal itself is the system working.
**Detection:** Immediate and loud: `MorningBriefError` raised at consume time; Hermes reports degraded=True rather than improvising a plan.
**Containment:** Automatic and constitutional: a malformed packet is never partially trusted; Hermes answers from the last good state and says so.
**Decision Packet:** No.
**Recovery:** Fix the producer, re-emit the packet (marked re-issued); schema-version discipline (major-match rule) prevents recurrence from version skew.
**RTO:** Under an hour.
**Recovery evidence:** Re-issued packet parses; consumer logs show clean consumption; degraded flag cleared.
**Lesson:** All-or-nothing parsing converts subtle corruption into a clean, visible outage — the cheapest failure mode available. Never "fix" this by making parsing lenient.

#### MC-12 — Split-brain after restore
**Failure:** Mission Control is restored from a day-old backup after a disk scare. It re-dispatches missions completed since the snapshot, re-counts yesterday's opportunities as new, and its trust/evidence counters lag reality. Two histories now exist: the store's and the world's.
**Likelihood:** Low-Medium. **Impact:** Critical — every downstream consumer (Trust Engine counts, Compound Engine trends, packets) inherits the fork; duplicate external-facing work may launch.
**Detection:** Restore events must be first-class: on any restore, Mission Control enters a mandatory reconciliation mode before dispatching. Independent signal: Hermes-side logs and git/PR state disagree with store state en masse.
**Containment:** Automatic post-restore dispatch freeze until reconciliation completes; idempotent mission IDs (MC-03) blunt accidental re-dispatch.
**Decision Packet:** Yes — accepting the reconciled history (which observations to keep, which duplicates to void) rewrites the record, a values/irreversibility call.
**Recovery:** Reconcile store against ground truth (repos, PRs, Hermes logs, governed stores); void duplicated observations; annotate the trail with the restore event.
**RTO:** Half a day.
**Recovery evidence:** Zero mission-ID collisions post-restore; evidence-feed counts match independently derived counts; trail shows the restore and reconciliation explicitly.
**Lesson:** A backup restores *data*, not *truth*. The restore procedure is not "copy file back" — it is "copy file back, then prove the world matches it before acting."

---

## Category 3 — Hermes Mini (HM-01 … HM-12)

The Mac mini is the always-on implementation workhorse: it executes missions, mutates worktrees, and hosts governed stores. It is also unattended hardware in a house.

#### HM-01 — Agent process crash mid-mission
**Failure:** The Hermes process on the Mini dies mid-mission (OOM, segfault in a native dep, kernel kill). The worktree is half-mutated: some files edited, no commit, mission state on the Mission Control side still `running`.
**Likelihood:** Very High over six months. **Impact:** Low-Medium — one mission's work lost or dirty; Medium if the crash interrupted a store write (see HM-03, TE-10).
**Detection:** Process supervision (launchd keepalive) sees the exit; Mission Control sees heartbeat loss on the running mission (MC-04 machinery).
**Containment:** Automatic: work happens in per-mission worktrees/branches, never on main — a dirty worktree contaminates nothing else. Governed stores use atomic replace, so a crash can lose the last write but not tear the file.
**Decision Packet:** No.
**Recovery:** Supervisor restarts the process; the mission restarts from its last commit (uncommitted deltas are discarded as unauditable); dirty worktree reset or discarded.
**RTO:** Minutes.
**Recovery evidence:** Process uptime resumes; mission re-runs to completion; no dirty worktrees older than the crash remain.
**Lesson:** Commit granularity is checkpoint granularity. Anything the agent hasn't committed is already lost in expectation — frequent small commits on the mission branch are the crash-safety mechanism, not a style preference.

#### HM-02 — Power loss mid-git-operation
**Failure:** House power blips at 3am during a git operation. On reboot: `index.lock` orphaned, a ref half-written, possibly a truncated object. The overnight mission queue stalls behind a repo that rejects all operations.
**Likelihood:** High (residential power over six months). **Impact:** Medium — hours of overnight throughput lost; the failure is loud, not silent.
**Detection:** All git operations on that repo fail immediately post-reboot; startup self-check (`git fsck`, stale-lock scan) at boot flags it before missions dispatch.
**Containment:** Automatic: boot-time health check runs before the agent accepts work; the repo is quarantined (missions targeting it PAUSE) rather than retried into deeper damage.
**Decision Packet:** No — repairs are reversible (the remote is the source of truth).
**Recovery:** Remove stale locks; `git fsck`; if objects are damaged, re-clone from origin (the remote survived); replay un-pushed local branches from mission logs if any existed.
**RTO:** Under an hour (re-clone bound).
**Recovery evidence:** `git fsck` clean; a canary mission completes end-to-end on the repaired repo.
**Lesson:** The origin remote is the Mini's real filesystem; local clones are cache. The only unrecoverable loss is work that was never pushed — which bounds the correct push frequency.

#### HM-03 — Disk full
**Failure:** Logs, model caches, worktrees, and node_modules fill the Mini's disk over months. Writes start failing: store saves error out, logs stop appending, git operations die. Depending on ordering, the agent may keep "working" while persisting nothing.
**Likelihood:** High. **Impact:** High — the dangerous variant is *silent*: an evidence-or-silence system that cannot write evidence is producing untrustworthy silence.
**Detection:** Disk-usage threshold in the evidence feed (Compound/observability metrics) long before 100%; at failure: store save exceptions, log gap detection (no log lines for a running agent is an alarm).
**Containment:** Automatic: at a high-water mark the agent stops accepting new missions (PAUSE: "disk pressure") while it can still record *why*; atomic-write pattern means existing stores are not corrupted by failed saves.
**Decision Packet:** No for cache/worktree cleanup; Yes if anything non-regenerable must be deleted.
**Recovery:** Purge regenerable data (caches, old worktrees, rotated logs); resume queue; verify every governed store's last write landed.
**RTO:** Under an hour.
**Recovery evidence:** Disk under threshold; a write-read round-trip on each governed store; log stream continuous again.
**Lesson:** Full disks turn an auditable system into an unauditable one *before* they turn it off. The high-water-mark stop must trigger while recording the stop is still possible.

#### HM-04 — Evidence truncation under disk pressure
**Failure:** Subtler than HM-03: log rotation under pressure drops trajectory files and mission transcripts while missions keep succeeding. Weeks later, an audit question ("why did the agent do X on the 14th?") has no answer — the work is fine, the evidence is gone.
**Likelihood:** Medium. **Impact:** High — retroactive: it converts past CONTINUE work from "audited autonomy" to "unverifiable claims," exactly what the constitution says silence must never be.
**Detection:** Evidence-completeness sampling: the Evening Report counts missions *with* complete transcripts vs. without; any gap is reported as UNKNOWN, not omitted.
**Containment:** Retention policy treats mission evidence as governed data (not "logs"): it is excluded from pressure-driven rotation; caches die first.
**Decision Packet:** No.
**Recovery:** The lost evidence is unrecoverable — record the gap honestly as a permanent UNKNOWN span; restore retention ordering.
**RTO:** N/A (loss is permanent); policy fix in minutes.
**Recovery evidence:** Evidence-completeness metric at 100% for new missions; the gap span explicitly annotated in the trail.
**Lesson:** Mission evidence is not telemetry — it is the product. Losing the transcript of successful work is a worse failure than losing the work, because work can be redone and trust cannot.

#### HM-05 — Repo object-store corruption
**Failure:** A failing sector or a `kill -9` during `git gc` corrupts objects in a long-lived local clone. Symptoms are delayed and weird: checkouts of *old* refs fail, fsck screams, but day-to-day work on recent branches looks fine for weeks.
**Likelihood:** Low-Medium. **Impact:** Medium — mostly latency and confusion; High only if un-pushed history was corrupted.
**Detection:** Scheduled `git fsck` as a periodic health mission (cheap, boring, weekly); first hard failure otherwise.
**Containment:** Same as HM-02: quarantine the repo, PAUSE its missions.
**Decision Packet:** No.
**Recovery:** Re-clone from origin; salvage un-pushed branches by cherry-picking surviving objects or re-running their missions.
**RTO:** 1–2 hours.
**Recovery evidence:** fsck clean; all mission branches present on origin or explicitly re-run.
**Lesson:** Local clone health is a *measurable* that decays invisibly. A weekly fsck mission costs nothing and converts a weird-Wednesday debugging session into a scheduled line item.

#### HM-06 — Worktree metadata corruption
**Failure:** Crash during worktree add/remove leaves `.git/worktrees/` metadata pointing at directories that don't exist (or vice versa). New mission checkouts fail with cryptic errors; the mission pipeline stalls on infrastructure that "worked yesterday."
**Likelihood:** High (worktree churn is per-mission). **Impact:** Low-Medium — throughput stall, no data loss.
**Detection:** Mission setup step fails loudly at worktree creation; stale-worktree scan (`git worktree prune --dry-run`) in the boot health check.
**Containment:** Automatic: setup failures PAUSE the mission with the error attached rather than retrying into the same wall; other repos unaffected.
**Decision Packet:** No.
**Recovery:** `git worktree prune`, remove orphaned directories, retry the mission.
**RTO:** Minutes.
**Recovery evidence:** Worktree list matches directory reality; queued missions flow again.
**Lesson:** Per-mission worktrees are consumables; their metadata must be reconciled at every boot the same way MC reconciles missions. Anything created per-mission needs a per-boot janitor.

#### HM-07 — Runaway implementation: the 3am token furnace
**Failure:** An agent loop wedges on a mission overnight — retrying a failing build, re-reading the same files, spiraling context — burning provider tokens for six unattended hours. No boundary is crossed (no money *decision* is made) but real dollars are consumed as operating expense.
**Likelihood:** High. **Impact:** High — hundreds of dollars possible in one night; repeated occurrences threaten the economics that justify Olympus.
**Detection:** Per-mission budget metering (tokens/steps/wall-clock); anomaly: mission running 10× its class's historical cost.
**Containment:** Automatic: hard per-mission ceilings on steps, tokens, and wall-clock — breach ⇒ PAUSE with state and transcript retained ("failure ceiling" throttle is already a named PAUSE reason in the escalation mapping). Provider-side monthly spend cap as the outer wall.
**Decision Packet:** No for the pause; Yes to raise any ceiling (money-adjacent value).
**Recovery:** Inspect the transcript for the loop signature; re-scope or split the mission; resume under normal budget.
**RTO:** Minutes after the pause fires; the *cost* is bounded by the ceiling, which is the point.
**Recovery evidence:** Paused-at-ceiling event recorded with spend figure; re-run completes within class-normal budget.
**Lesson:** Autonomy ceilings are denominated in dollars, not just risk. "The system prices options; the human spends" applies to the system's *own* consumption — an uncapped loop is an unauthorized purchase in slow motion.

#### HM-08 — Runaway scope: the 4,000-line "test fix"
**Failure:** A mission scoped "fix the flaky timezone test" snowballs: the agent refactors the time module, touches 40 files, updates deps, and opens a huge PR. Nothing crashed; the mission is a "success" that nobody asked for.
**Likelihood:** High. **Impact:** Medium — review burden explodes, revert risk, plan distortion; High if it lands (see HB-04).
**Detection:** Diff-size vs. mission-class anomaly at PR time; Hermes MBP review checks scope-vs-mission as its first gate, before code quality.
**Containment:** The two-machine design *is* the containment: nothing merges without independent review; scope breach ⇒ review verdict "out of scope," mission PAUSEd for re-scoping.
**Decision Packet:** No — re-scoping is planning, not authority.
**Recovery:** Split the PR: extract the minimal fix; park the refactor as a *proposed* mission for Mission Control to rank on its own merits.
**RTO:** Hours.
**Recovery evidence:** Minimal PR merged; refactor exists as a ranked-or-rejected mission, not merged smuggled work.
**Lesson:** Scope is part of the mission contract. Overdelivery is a boundary problem wearing a productivity costume — the review stage must judge the diff against the *mission*, not just against correctness.

#### HM-09 — Unattended macOS update reboot
**Failure:** Overnight, macOS installs an update and reboots. In-flight missions die (HM-01, en masse); worse, the environment changed under the agent — Xcode CLT invalidated, Python/node paths shifted, a security prompt now blocks a tool awaiting a click nobody will make for days.
**Likelihood:** High (OS updates are certain; the prompt-wedge variant is Medium). **Impact:** Medium — a full stall that *looks* like assorted mission failures rather than one platform event.
**Detection:** Boot event + environment self-check at startup: toolchain versions, tool availability, a smoke mission. Divergence from the pre-reboot manifest is reported as one platform event, not N mission errors.
**Containment:** Automatic: agent refuses the queue until the environment self-check passes ("degraded: environment changed"), converting mystery failures into a single clear PAUSE.
**Decision Packet:** No; Yes only if recovery needs Chad physically present (GUI security prompts — a real dependency on a human hand).
**Recovery:** Re-accept licenses/CLT, restore paths, clear GUI prompts on next physical access, replay the killed missions.
**RTO:** Minutes to days (bounded by physical access for prompt-wedges).
**Recovery evidence:** Environment manifest matches expected; smoke mission passes; killed missions re-run.
**Lesson:** The Mini's OS is a component with its own release schedule that Olympus doesn't control. Treat every reboot as a *deployment* — verified by manifest before trusting it with work — and know which failures require a human finger on a physical screen.

#### HM-10 — Credential/keychain lockout after reboot
**Failure:** Post-reboot, the login keychain stays locked (or a token cached in it expires): git pushes and API calls fail with auth errors. Retries look like a provider outage; the queue burns retry budget against a locked door.
**Likelihood:** High. **Impact:** Medium — full stall; Low data risk.
**Detection:** Auth-specific error classification: 401/403-class failures across *all* services simultaneously is a local-credential event, not N remote outages.
**Containment:** Automatic: auth-failure storm ⇒ PAUSE queue with "credential access lost" instead of per-mission retries; never attempts credential self-repair (credentials are a never-delegated boundary).
**Decision Packet:** Yes if any credential must be re-issued/re-scoped (constitutionally Chad's); No if it's an unlock on next access.
**Recovery:** Chad unlocks/re-provisions on next access; agent re-verifies each service with a read-only call before resuming writes.
**RTO:** Bounded by Chad's next access; minutes after.
**Recovery evidence:** Per-service auth probes green; queue drains.
**Lesson:** The agent must distinguish "the world rejected me" from "I lost my keys" — the retry policy for one is the attack pattern for the other. Credential recovery is always a human act by constitutional design; the system's job is to wait loudly.

#### HM-11 — Hardware degradation: intermittent flakiness
**Failure:** The Mini develops a thermal or RAM fault. Symptoms: sporadic process kills, occasional test failures that don't reproduce, rare filesystem hiccups — spread thin enough that each incident gets blamed on software, missions, or providers for weeks.
**Likelihood:** Low-Medium. **Impact:** High cumulative — weeks of misattributed failures corrupt the reliability record: missions "fail" that were fine, evidence counts skew, trust signals degrade for the wrong reasons.
**Detection:** Cross-mission correlation is the only tell: failure rate rising *across unrelated missions/repos/providers* on one host; hardware diagnostics as a scheduled health mission once the host-wide anomaly trips.
**Containment:** Host-level quarantine: when host-wide anomaly trips, stop attributing failures to missions (mark them UNKNOWN-host-suspect, don't count them as mission evidence) and drain the queue.
**Decision Packet:** Yes — replacement hardware is money.
**Recovery:** Diagnose (memtest, thermals); repair/replace; restore from pushed state + governed-store backups; re-run the UNKNOWN-flagged missions to re-derive honest evidence.
**RTO:** Days (procurement-bound).
**Recovery evidence:** Diagnostics clean; failure rate returns to baseline; misattributed evidence re-derived or annotated.
**Lesson:** A flaky host poisons the *evidence* before it stops the work. The reliability record needs a host-health dimension so that "the machine is lying" is a hypothesis the system can represent.

#### HM-12 — Silent toolchain drift via auto-update
**Failure:** Homebrew auto-update, a `latest`-tagged dependency, or an editor-tool self-update changes the Mini's toolchain between missions. Formatting output shifts, a linter tightens, build flags change — diffs get noisier and behavior changes with no corresponding mission.
**Likelihood:** High. **Impact:** Low-Medium — noise, spurious review findings, occasional real breakage attributed to the wrong change.
**Detection:** Environment manifest diffing (same mechanism as HM-09) on a schedule, not just at boot; review-side signal: diff churn in files the mission didn't target.
**Containment:** Pin what can be pinned; manifest-diff alarm PAUSEs new missions in affected toolchains until the drift is acknowledged.
**Decision Packet:** No.
**Recovery:** Acknowledge or roll back the tool change; record it as an environment event so subsequent diffs have provenance.
**RTO:** Minutes.
**Recovery evidence:** Manifest stable across a week; review noise back to baseline.
**Lesson:** The environment is an input to every mission and it changes itself. An environment manifest with diff-on-change gives every unexplained behavior shift a first suspect.

---

## Category 4 — Hermes MBP (HB-01 … HB-09)

The MacBook Pro runs the independent review function — the second pair of eyes that makes the Mini's autonomy safe. It is also Chad's daily-carry laptop: mobile, sometimes asleep, sometimes gone.

#### HB-01 — Reviewer asleep: lid closed, queue stalls
**Failure:** The MBP lid closes; the review agent sleeps mid-week. Implementation output piles up unreviewed. Nothing merges (correct), but the pipeline silently loses its second half for days.
**Likelihood:** Very High. **Impact:** Medium — throughput halves; pressure builds to bypass review (the real danger — see HB-07, OR-02).
**Detection:** Review-queue age metric; MBP heartbeat absent while Mini heartbeat present.
**Containment:** Automatic and absolute: no review ⇒ no merge, ever. Unreviewed work PAUSEs at the review gate with clean state; the queue is a buffer, not a bypass.
**Decision Packet:** No.
**Recovery:** MBP wakes, drains the queue oldest-first; power/scheduling settings tuned so the review service resists casual sleep.
**RTO:** Bounded by lid-open; queue drains in hours.
**Recovery evidence:** Review-queue age back under threshold; every merge in the period shows a review verdict.
**Lesson:** The review gate's value is that it *cannot* be waited out. The correct response to reviewer absence is accumulation, and the metric to watch is queue age — because sustained absence converts into bypass pressure on the humans and processes around the gate.

#### HB-02 — Reviewer travels: off-Tailnet for a week
**Failure:** Chad takes the MBP to a conference. It's awake but off the home Tailnet (hotel wifi, no VPN), or online only in bursts. Review connectivity flaps; partial reviews start and die.
**Likelihood:** High. **Impact:** Medium — same stall as HB-01 plus a new failure texture: *interrupted* reviews leaving half-verdicts.
**Detection:** Same heartbeat/queue-age signals; review sessions that start but never conclude.
**Containment:** Reviews are transactional: a verdict is either complete-and-recorded or void — a died-mid-review session leaves no partial approval. Missions stay PAUSEd at the gate.
**Decision Packet:** No.
**Recovery:** Reconnect (Tailscale generally survives hotel NAT — see IN-01 for when it doesn't); void orphaned sessions; re-run affected reviews from scratch.
**RTO:** Connectivity-bound; hours after.
**Recovery evidence:** No verdicts in the record from voided sessions; queue drained post-reconnect.
**Lesson:** The review function lives on a machine whose job description includes leaving. Its absence is a scheduled, predictable event — the pipeline should treat "reviewer away this week" as plannable capacity, not surprise downtime.

#### HB-03 — False confidence: the LGTM machine
**Failure:** After a model change or prompt drift, the review agent's approvals stay superficially well-formed but stop *engaging* — every PR passes with plausible boilerplate. The gate is open and nobody knows. Weeks of merges carry only the illusion of independent scrutiny.
**Likelihood:** Medium. **Impact:** Critical — the two-machine trust architecture silently collapses to one machine; every downstream trust signal (promotions, autonomy levels) inherits the fraud.
**Detection:** The approval *rate* is the alarm: review value exists only if it sometimes says no. Rejection/finding rate trending to zero is treated as reviewer failure, not code quality triumph. Canary defects (known-bad changes injected periodically) make the test affirmative.
**Containment:** None fully automatic within the fixed architecture — the honest fallback: when the finding-rate alarm trips, merges pause and recent approvals are marked suspect pending re-review.
**Decision Packet:** Yes — deciding how far back to distrust approvals is a judgment call on the audit trail itself.
**Recovery:** Fix the reviewer (model/prompt/config); re-review the suspect window's merges; re-derive any trust evidence that counted those approvals.
**RTO:** Days.
**Recovery evidence:** Canary defects caught again; finding rate back in historical band; suspect-window re-reviews logged.
**Lesson:** A reviewer is only alive if it can be observed rejecting things. "Percent approved" is a vital sign, and 100% is flatline, not health.

#### HB-04 — Missed defect ships and festers
**Failure:** A genuinely engaged review still misses a real defect — a schema change that silently breaks Income Scout store round-tripping. It merges; damage accumulates for three weeks before symptoms surface far from the cause.
**Likelihood:** High (reviews miss things; that's why defect-in-depth exists). **Impact:** Medium-High — cost scales with detection delay, and delayed detection is this scenario's signature.
**Detection:** Downstream invariant checks (store schema-version validation, fail-loud loads) shorten the fester window; the RCA convention (`docs/rca-*.md` pattern already exists in the repo culture) traces it back.
**Containment:** Governed stores fail loudly on schema mismatch (existing convention), converting silent corruption into a visible outage at first contact.
**Decision Packet:** No for revert/fix-forward on internal code; Yes if corrupted data drove any decision already acted on.
**Recovery:** Revert or fix forward; restore/re-derive affected store records from the audit trail; add the failure signature to review checklists (the compound-engine move: the miss becomes permanent reviewer capability).
**RTO:** Hours to fix; data reconciliation up to a day.
**Recovery evidence:** Store round-trips verified; an RCA document exists; the review checklist diff shows the new check.
**Lesson:** Review is a filter, not a guarantee — the architecture's real promise is that *when* a defect ships, the audit trail can reconstruct what it touched. Every escaped defect must leave the reviewer permanently smarter, or the miss was wasted.

#### HB-05 — Stale architecture review
**Failure:** The review agent's standing context (architecture notes, contracts summary) was written in month 2. By month 6, contracts evolved — it approves changes that violate the *current* seam rules (e.g., a component writing another's store, exactly what invariant 3 forbids) because its mental model predates them.
**Likelihood:** High. **Impact:** High — merges that are locally clean and constitutionally wrong; erosion of exactly the invariants that make components composable.
**Detection:** Hard from inside review. External: invariant checks in CI/health missions (mutation-boundary audits: which process wrote which store); periodic sampled re-review of merged work against current contracts.
**Containment:** The invariants that matter most (store ownership, isolation markers) are enforced at runtime boundaries too, not only at review — defense in depth already in the contract ("forbidden markers rejected at every boundary").
**Decision Packet:** No.
**Recovery:** Refresh the reviewer's standing context from current docs; re-review the window since the docs last changed; fix any invariant violations found.
**RTO:** A day.
**Recovery evidence:** Reviewer context version matches docs version; invariant audit clean.
**Lesson:** A reviewer's knowledge has a freshness date, like the evidence rules already admit ("stale evidence" is a named enemy elsewhere in Olympus). Contract changes must invalidate reviewer context the way schema bumps invalidate parsers.

#### HB-06 — Correlated blindness: same model, same blind spot
**Failure:** Implementation (Mini) and review (MBP) run on the same foundation model family. A class of error the model systematically makes is also a class it systematically fails to see. The independence of the two-machine design is partly illusory — failures correlate exactly where it matters.
**Likelihood:** Medium-High (structural, always latent). **Impact:** High — the probability math of "two independent checks" silently doesn't apply; escape rate for the correlated class is near single-machine rates.
**Detection:** Only visible in outcomes: defects that escaped *both* stages, clustered by type, in the RCA record. Chad's spot-checks (the Executive audits samples of CONTINUE work) are the only truly independent reviewer in the architecture.
**Containment:** Partial and structural: deterministic non-model checks (tests, invariant audits, schema validation, canaries) are the uncorrelated layer; they don't share the model's blind spots.
**Decision Packet:** No (awareness and sampling policy); Yes only if mitigation involves paid second-provider review capacity.
**Recovery:** Not recoverable as an event — it's a standing property to be measured: track escaped-defect classes; weight Chad's sampling toward classes both stages have missed before.
**RTO:** N/A (continuous).
**Recovery evidence:** Escaped-defect taxonomy exists and informs sampling; correlated-class escape rate measured rather than assumed away.
**Lesson:** Two agents from one model are one-and-a-half reviewers, not two. The deterministic checks are not bureaucratic redundancy — they are the only layer whose failures don't correlate with the model's.

#### HB-07 — Review-absence policy misconfigured as consent
**Failure:** Somewhere in month 4's throughput frustration (HB-01 recurring), a "temporary" setting lands: reviews pending more than 48h auto-proceed for "low-risk" mission classes. Six weeks later, a nontrivial change merges with zero review under that flag.
**Likelihood:** Medium (the pressure is certain; the mistake is plausible). **Impact:** Critical — this is a policy bypass wearing an ops tweak's clothes; the review gate's absoluteness is what makes HB-01's containment claim true.
**Detection:** Merge-audit invariant: every merge must reference a review verdict; a merge without one is a page-level alarm regardless of mission class.
**Containment:** The merge-audit is the containment; when it fires, the flag is revealed.
**Decision Packet:** Yes — retroactively, this flag was a values/governance change that should have been a packet in month 4; its removal and the disposition of unreviewed merges is one now.
**Recovery:** Remove the flag; re-review everything merged under it; treat this as governance drift (OR-02) with an RCA on how a constitutional change shipped as a config tweak.
**RTO:** Days.
**Recovery evidence:** Zero merges without verdicts across the full six-month audit; the flag's lifecycle documented in the RCA.
**Lesson:** "No review ⇒ no merge" is constitution, not configuration. Any knob that can relax a constitutional rule *is* a governance change and must be impossible to ship as a quiet setting.

#### HB-08 — Reviewer performance collapse
**Failure:** DerivedData, container bloat, and a hungry browser leave the MBP's review runs taking 90 minutes instead of 6. The queue backs up (HB-01 texture) but the machine looks "up," so nothing flags absence — just molasses.
**Likelihood:** High. **Impact:** Medium — latency-driven throughput loss plus timeout-triggered partial reviews (HB-02 texture).
**Detection:** Review duration trend per mission class; queue age rising while heartbeats stay green.
**Containment:** Transactional verdicts (HB-02) keep slow-then-killed reviews from leaving partial approvals; queue buffers.
**Decision Packet:** No.
**Recovery:** Clean disk/memory pressure sources; re-baseline review duration; consider scheduling reviews for the MBP's idle hours.
**RTO:** An hour.
**Recovery evidence:** Review p50/p95 duration back to baseline for a week.
**Lesson:** "Up" and "capable" are different states — a shared-with-a-human laptop needs performance baselines, because its capacity is silently mortgaged to that human's browser tabs.

#### HB-09 — Reviewer context contamination
**Failure:** The review process accumulates residue — long-lived session state, memory entries, or cached summaries from *implementation* transcripts. The reviewer starts "knowing" the implementer's intent and rationalizations, judging the diff by the story instead of the code. Independence degrades from inside.
**Likelihood:** Medium. **Impact:** High — subtle, systemic softening of the one gate that must stay adversarial; a cousin of HB-03 with a different cause.
**Detection:** Difficult directly. Proxies: review findings quoting implementer rationale not present in the diff; finding-rate decline correlated with session longevity; canary defects (HB-03 machinery) accompanied by fabricated justifications get *approved with the implementer's excuse*.
**Containment:** Structural hygiene the architecture already prefers: reviews run in fresh, per-review contexts; the reviewer receives the diff, the mission contract, and the current docs — not the implementer's transcript.
**Decision Packet:** No.
**Recovery:** Purge reviewer-side persistent state; re-establish fresh-context-per-review; re-run recent suspicious approvals.
**RTO:** Hours.
**Recovery evidence:** Canaries rejected again with diff-grounded reasons; no implementer-transcript references in verdicts.
**Lesson:** Independence is an input-hygiene property, not a hardware property. Two machines with a shared narrative are one reviewer with extra steps — what the reviewer is *allowed to read* is the actual isolation boundary.

---

## Category 5 — Trust Engine (TE-01 … TE-10)

The trust layer: memorygraph's governed claims (candidate → established → core, evidence-gated promotion, contradictions flagged, never auto-resolved) and the broader autonomy ledger built on evidence counts (">=2 observations on >=2 days", closed source allowlist).

#### TE-01 — Incorrect promotion: double-counted evidence
**Failure:** The same successful outcome is recorded twice (a retried pipeline, a duplicated feed event — cousin of MC-03) and counted as two independent observations. A claim/capability promotes to `established` on what is really one data point.
**Likelihood:** High. **Impact:** High — over-trust: downstream consumers (packets, autonomy scoping) treat as proven what is anecdotal.
**Detection:** Evidence-record dedup audit: observations with identical provenance (same mission ID, same artifact) backing one promotion; promotion events cross-checked against distinct-source counts.
**Containment:** The >=2-days rule already blocks same-day double counts; provenance-keyed dedup at ingestion blocks the rest.
**Decision Packet:** No — demotion on evidence audit is the governed path, not a judgment call.
**Recovery:** Demote the claim to candidate; void the duplicate observation; re-promote only on genuinely new evidence.
**RTO:** Minutes per claim once found; the audit is the work.
**Recovery evidence:** Promotion re-derivation from deduped evidence matches ledger state; no promotion backed by fewer distinct events than policy requires.
**Lesson:** Evidence counting is only as honest as event identity. Every observation needs provenance strong enough to answer "is this the same event I already counted?" — the promotion threshold is meaningless without it.

#### TE-02 — Incorrect demotion: poisoned contradiction
**Failure:** A malformed or wrong ingest (a bad note, a misparsed document) contradicts a legitimately `core` claim. Per governance, contradicted claims are flagged and never promote — so a true, load-bearing piece of knowledge is benched by one bad record.
**Likelihood:** Medium. **Impact:** Medium — capability throttled, packets hedge with UNKNOWNs; the *safe* direction of error, but costly if the claim is central.
**Detection:** Contradiction-review queue (contradictions are flagged *for review* by design — the review is the detection); alarm if a core-tier claim gets contradicted, since those should be rare events worth attention.
**Containment:** Built-in: contradiction blocks promotion but doesn't delete anything; both records persist with provenance.
**Decision Packet:** No for evidence-based resolution; Yes if the resolution encodes a values judgment.
**Recovery:** Adjudicate the contradiction: trace both records' provenance, void the bad ingest with reason, restore the claim's status.
**RTO:** Minutes per contradiction; bounded by review-queue attention.
**Recovery evidence:** Contradiction resolved with recorded reason; claim status re-derived cleanly from surviving evidence.
**Lesson:** Fail-toward-distrust is the right default, and this scenario is the price paid for it — acceptable only if the contradiction-review queue is actually worked (see OR-05: a safety queue nobody reads is not a safety queue).

#### TE-03 — Ledger corruption
**Failure:** `memory_graph.db` (or the autonomy ledger) is corrupted — bad sector, interrupted write, or an OP-09-style hand edit. Trust state for the whole organization is unreadable or, worse, subtly wrong.
**Likelihood:** Medium. **Impact:** Critical — trust state is the license under which all autonomy operates; without it, no CONTINUE classification has a defensible basis.
**Detection:** Integrity check at open (fail-loud convention); checksum/consistency validation as a scheduled health mission; subtle-corruption variant caught only by re-derivation audits (below).
**Containment:** Automatic conservative degradation: if trust state is unavailable or unverifiable, everything operates at *floor* trust — maximal escalation, minimal autonomy — until the ledger is restored. Over-asking is the designed failure direction.
**Decision Packet:** No for restore; Yes if any period must be adjudicated by hand.
**Recovery:** Restore from backup; then re-derive: because every promotion is evidence-gated and evidence lives in the audit trail, the ledger is *recomputable* from first principles — replay promotions from surviving evidence records and diff against the restored copy.
**RTO:** Hours (restore) to a day (full re-derivation).
**Recovery evidence:** Restored ledger matches independent re-derivation; trust floor lifted only after the diff is clean.
**Lesson:** The ledger is a cache of what the evidence implies. Its recoverability rests entirely on the evidence trail's integrity — which is why HM-04 (evidence loss) is secretly a trust-engine failure too.

#### TE-04 — Stale-backup restore: resurrected autonomy
**Failure:** After TE-03, the ledger is restored from a two-week-old backup. In those two weeks a capability was *demoted* after a bad outcome. The restore silently re-grants the revoked autonomy; the system resumes doing the thing it had learned not to do.
**Likelihood:** Low-Medium (requires the TE-03 + intervening-demotion coincidence). **Impact:** Critical — a revocation is a safety decision; undoing one silently is a boundary violation with a technical alibi.
**Detection:** Restore-reconciliation (MC-12 discipline applied here): diff restored ledger against the event trail for the gap window *before* lifting the trust floor; demotion events in the gap are the first thing sought.
**Containment:** Same trust-floor rule as TE-03: no autonomy resumes on a restored ledger until reconciliation completes.
**Decision Packet:** Yes — re-applying gap-window demotions/promotions is a judgment-bearing rewrite of trust state.
**Recovery:** Replay the gap window's trust events onto the restored ledger; verify every revocation survived.
**RTO:** Half a day.
**Recovery evidence:** Every demotion event in the gap window present in the final ledger; the resurrected capability provably re-revoked.
**Lesson:** Demotions are the ledger records that must never resurrect — backups roll back data, and safety decisions must be replayed forward every time, without exception.

#### TE-05 — Replay attack: recycled evidence
**Failure:** Old evidence re-enters the intake — an inbox directory re-processed after restore (IS-08 cousin), a feed replaying history after reconnection, or adversarially: a crafted record mimicking past successes. Counts inflate; promotions trigger on recycled history.
**Likelihood:** Medium accidental; Low adversarial. **Impact:** High — trust inflation across many claims at once, harder to spot than TE-01's single duplication.
**Detection:** Monotonicity and uniqueness checks at the recorder: observation IDs/provenance already seen are rejected; promotion-rate anomaly (a burst of promotions with no corresponding burst of *work*) alarms.
**Containment:** The closed source allowlist bounds who can record at all; idempotent recording (unique event identity) makes replays no-ops.
**Decision Packet:** No for accidental; Yes if adversarial injection is confirmed (external-facing security response is Chad's).
**Recovery:** Void replayed observations by provenance; re-derive affected promotions (TE-03 machinery); if adversarial, rotate the allowlisted paths' credentials — Chad's act.
**RTO:** Hours.
**Recovery evidence:** Promotion re-derivation clean; recorder rejects a replayed sample; anomaly alarm verified live.
**Lesson:** An append-only trust ledger must be idempotent to appends. "Have I seen this exact event?" is the cheapest question in the system and the only thing standing between history and a forged present.

#### TE-06 — Stale evidence: trust outliving its world
**Failure:** A capability was promoted in month 1 on strong evidence — against an environment, provider model, and codebase that no longer exist by month 6. The promotion is *valid* and the trust is *wrong*: nothing in the ledger decays.
**Likelihood:** Very High (this is entropy, not an event). **Impact:** High — systematically overconfident autonomy in exactly the oldest, least-watched capabilities.
**Detection:** Evidence-age audit: promotions whose newest supporting observation predates a major environment change (model swap, HM-12 drift, contract revision) are flagged stale.
**Containment:** Partial, already present: the Compound Engine's both-days/multi-observation rules mean *new* claims stay honest; the gap is old ones. Flagged-stale claims drop to hedged status in packets (reported with their age) rather than asserted flatly.
**Decision Packet:** No — re-validation missions are ordinary work.
**Recovery:** Re-validate stale promotions with fresh canary missions; re-date or demote on results.
**RTO:** Ongoing; per-claim minutes.
**Recovery evidence:** No promotion relied upon in a packet whose evidence postdates the last relevant environment change; staleness metric trending down.
**Lesson:** Trust earned is trust *dated*. The ledger records that evidence existed — only re-validation says it still describes the world; every major environment change should implicitly age every promotion that predates it.

#### TE-07 — Self-licking loop: system grades its own homework
**Failure:** A subtle provenance failure: Hermes-generated summaries/reports get recorded as *observations supporting* the claims they were generated from. The system's outputs become its own evidence; confidence compounds without any new contact with reality.
**Likelihood:** Medium — this failure is famously easy to create accidentally in agent systems. **Impact:** Critical — it corrupts the epistemology itself: the evidence-or-silence rule is satisfied *formally* by evidence that is secretly circular.
**Detection:** Provenance-type audit: every observation must trace to a reality-contact event (a merged PR, a test run, a human entry, an external artifact) — observations whose provenance terminates in another Hermes output are circular by construction and findable mechanically.
**Containment:** The contract's design already gestures here (human-entered evidence only, in the Scout; source allowlists in MC) — the containment is enforcing "reality-terminated provenance" at the recorder for *all* feeds.
**Decision Packet:** No.
**Recovery:** Void circular observations; re-derive promotions; audit which packets asserted claims that now demote.
**RTO:** A day.
**Recovery evidence:** Provenance audit shows 100% reality-terminated chains; affected claims re-statused; corrections issued in the next report.
**Lesson:** The dangerous counterfeit isn't false evidence — it's real output wearing an evidence costume. Every observation's chain must end at something the system didn't write.

#### TE-08 — Trust bleed across domains
**Failure:** A capability promoted for domain A (refactoring the web plugin, say) is consulted for autonomy decisions in domain B (touching the gateway) because the promotion's *scope* was recorded loosely. Trust legitimately earned in one place quietly licenses action in another.
**Likelihood:** High. **Impact:** High — the system operates beyond earned trust while the ledger says everything is fine.
**Detection:** Scope audit: promotions cross-referenced against the mission classes that cite them; a promotion cited by mission classes absent from its supporting evidence is bleeding.
**Containment:** Constitutional backstop already exists: "new category of action, never explicitly granted → NEEDS_CHAD by definition; authority is granted, never inferred from precedent" — trust bleed is precisely inference from precedent, so honest classification catches it.
**Decision Packet:** Yes — extending a promotion's scope *is* granting new authority.
**Recovery:** Narrow the promotion's recorded scope to what its evidence covers; missions that relied on the bleed re-classify (some flip to NEEDS_CHAD).
**RTO:** Hours.
**Recovery evidence:** Every promotion's citing-missions set ⊆ its evidence's mission classes.
**Lesson:** Trust has a jurisdiction. An observation proves the *thing observed*, and scope creep in the ledger is the machine inferring authority — the exact move HUMAN_FIRST names as forbidden.

#### TE-09 — Clock skew corrupts evidence timing
**Failure:** The Mini's clock drifts (or jumps after a dead CMOS battery / NTP failure — see IN-07). Evidence timestamps scatter: two same-day observations appear two days apart (satisfying ">=2 days" falsely) or two-day evidence collapses into one day (blocking legitimate promotion).
**Likelihood:** Medium. **Impact:** Medium — both error directions occur, silently; the timing rules the governance leans on lose meaning for the skewed window.
**Detection:** Cross-source timestamp sanity: events with causal order (dispatch → execution → review) showing non-monotonic timestamps; NTP offset monitoring as an evidence feed.
**Containment:** Recorder-side: reject or quarantine-flag observations whose timestamps are inconsistent with the recorder's own receipt time beyond tolerance.
**Decision Packet:** No.
**Recovery:** Fix time sync; identify the skew window; re-evaluate promotions whose day-counting fell inside it.
**RTO:** Under an hour to fix time; hours to audit.
**Recovery evidence:** NTP offset within tolerance; skew-window promotions re-derived with corrected ordering.
**Lesson:** The ">=2 days" rule quietly assumes a trustworthy clock — time is an unlisted dependency of the whole trust calculus and needs its own monitoring like any other component.

#### TE-10 — Silent persistence failure: amnesiac trust
**Failure:** Promotions compute correctly in memory but a persistence-layer fault (disk pressure per HM-03, a permissions change, a swallowed exception) drops the writes. Every restart resets trust to an older state; capabilities oscillate — promoted by day, demoted by reboot — and downstream behavior flip-flops inexplicably.
**Likelihood:** Low-Medium. **Impact:** High — inconsistency is worse than plain loss: packets assert different trust levels on different days with no recorded cause.
**Detection:** Write-verification (read-after-write on ledger commits); restart-diff check: ledger state at shutdown vs. startup must match or alarm.
**Containment:** Fail-loud on verified-write failure: a promotion that can't persist doesn't take effect in memory either — the ledger and behavior never diverge.
**Decision Packet:** No.
**Recovery:** Fix the persistence fault; replay unpersisted trust events from the audit trail (TE-03 re-derivation machinery).
**RTO:** Hours.
**Recovery evidence:** Shutdown/startup ledger diffs clean across a week of restarts; read-after-write probes green.
**Lesson:** A trust decision isn't made until it's durable. In-memory state that outruns its ledger creates the one thing an audit-based system cannot tolerate: behavior with no matching record.

---

## Category 6 — Continue-Until-Fork (CF-01 … CF-09)

The doctrine: work proceeds autonomously (CONTINUE) until it reaches a genuine fork — a boundary or judgment call — where it stops and produces a Decision Packet (a decision-ready NEEDS_CHAD item: one question, evidence chain, priced options, default). The classifier is a deterministic first-match-wins rule table; no model calls in classification.

#### CF-01 — Missed fork: boundary crossed at CONTINUE
**Failure:** A mission reaches a genuine fork the rule table doesn't recognize — an action that is *effectively* an external send or commitment but arrives under a shape no rule matches (a new tool, a new channel, an indirect effect). First-match-wins finds no boundary rule and the work continues through it. No packet is ever produced; Chad learns after the fact, if at all.
**Likelihood:** Medium — the rule table is finite; the world is not. **Impact:** Existential-class — the constitution is explicit: "one silent boundary violation costs more trust than a thousand correct escalations earn."
**Detection:** After-the-fact only, by construction: Evening Report audit of CONTINUE work (this is *why* CONTINUE work is audited there); Chad spot-sampling; external symptom (a counterparty replies to something Chad never sent).
**Containment:** The default-under-uncertainty rules are the designed guard ("new category of action, never explicitly granted → NEEDS_CHAD by definition"; uncertain → more conservative state) — the failure requires the action to also be mis-*recognized* as an existing category. Deterministic classification at least makes every miss reproducible and fixable.
**Decision Packet:** Yes — immediately upon discovery: disclosure packet stating what crossed, what it touched, and remediation options.
**Recovery:** Halt the mission line; Chad remediates the external effect personally; add the missed shape to the rule table (a values act — Chad authors the rule); re-audit the table against recent CONTINUE history for siblings.
**RTO:** Damage-bound: hours to days.
**Recovery evidence:** The same action replayed in a test harness now classifies NEEDS_CHAD; rule-table diff recorded; sibling audit clean.
**Lesson:** A deterministic classifier fails deterministically: silently, repeatably, and always in the same place. Its safety rests on the *category-recognition* step, so every new tool or channel added to Olympus must arrive with its classification rules — a capability without rules is an unclassifiable action waiting to happen.

#### CF-02 — Fork inflation: packet spam
**Failure:** After a rule-table edit (or an overcautious month-5 tightening), routine work starts classifying NEEDS_CHAD — dependency bumps, doc edits, rerun requests. Chad gets a dozen packets a day. The attention budget the whole system exists to protect is consumed by the system's own questions.
**Likelihood:** High. **Impact:** High — direct North Star violation; breeds OP-03 rubber-stamping and OP-06 alarm fatigue, which then degrade *real* packet quality.
**Detection:** Packet-rate and packet-approval-entropy metrics: volume above baseline plus near-100% approve rate means the classifier is exporting non-decisions ("an assistant that asks about everything is indistinguishable from no assistant").
**Containment:** The one-question and four-class interrupt rules cap *interrupt* damage; excess packets pool in `waiting_for_you` rather than paging.
**Decision Packet:** Yes, one meta-packet: "these N packet classes were 100%-approved for 3 weeks; here are proposed rule relaxations" — rule authorship is Chad's.
**Recovery:** Chad approves rule changes; reclassify pooled trivia to CONTINUE under new rules.
**RTO:** Days (needs the trend data).
**Recovery evidence:** Packet rate back to baseline; approval entropy rises (packets are genuine decisions again).
**Lesson:** A 100% approval rate on a packet class is the classifier confessing those aren't decisions. Fork inflation is quieter than a missed fork but attacks the same asset — trust in the channel — from the other side.

#### CF-03 — Policy bypass: the side door
**Failure:** Some execution path invokes work without passing through classification — a cron job added directly on the Mini, a manual tool invocation habit, a new plugin wired straight to execution. Work happens that no rule table ever saw. Not malice: convenience plus time.
**Likelihood:** High over six months. **Impact:** Critical — the escalation contract's guarantees only cover classified work; the bypass creates a growing unclassified shadow.
**Detection:** Coverage audit: every unit of work in the execution logs must reference a classification event; unclassified work in the trail is mechanically findable (same shape as HB-07's merge audit).
**Containment:** Structural: execution resources (agent entrypoints, dispatch interfaces) accept only classified work — the fewer side doors exist, the more the audit is a formality.
**Decision Packet:** Yes if any bypassed work touched a boundary; No for pure re-routing.
**Recovery:** Route the side path through classification; retroactively classify its history; escalate anything that would have forked.
**RTO:** Hours to reroute; a day to audit history.
**Recovery evidence:** Coverage audit at 100%; the side path's future work shows classification events.
**Lesson:** Governance coverage decays one convenient shortcut at a time. The invariant to monitor is not "does the classifier work" but "does all work pass through it" — those are different numbers and only the second one protects anything.

#### CF-04 — Conflicting packets: one decision, two questions
**Failure:** Two mission lines independently hit the same underlying fork (e.g., both need to know whether to commit to the new client's timeline) and emit separate packets with differently-framed questions and different defaults. Chad, answering quickly (OP-04 conditions), resolves them inconsistently. Both missions proceed, in opposite directions.
**Likelihood:** Medium. **Impact:** High — Olympus executes contradictory positions under one signature; externally visible if either line sends.
**Detection:** Packet-similarity check at emission (same entities/subject window); post-answer contradiction detection when two resolutions imply conflicting facts about the same commitment.
**Containment:** Sequencing: packets touching the same subject serialize — the second holds until the first resolves and re-frames against it (the escalation contract's one-question discipline extended across packets).
**Decision Packet:** Yes — a reconciliation packet: "your two answers conflict; which governs?"
**Recovery:** Chad picks the governing answer; the losing mission re-plans; any external effect of the loser is remediated by Chad.
**RTO:** One attention window plus remediation.
**Recovery evidence:** Both missions' plans consistent with the governing answer; contradiction log closed.
**Lesson:** Decisions belong to *subjects*, not missions. Two packets about one commitment is one decision asked badly — the packet layer needs identity-of-the-underlying-question the same way dispatch needs mission IDs.

#### CF-05 — Death by default: self-approval by attrition
**Failure:** Every packet carries "what happens if you do nothing" — a safety feature. Under sustained operator scarcity (OP-01 becoming chronic), the do-nothing default becomes the *usual* outcome. The system's defaults, written by the system, quietly become the operative policy; Chad's judgment exits the loop without any single event marking the exit.
**Likelihood:** High under chronic load. **Impact:** Critical — inverted governance: nominally human-led, practically default-led. Every default was authored as "safe if unattended," not "correct as standing policy."
**Detection:** Default-execution rate per packet class, trended; the metric "fraction of decisions actually decided by Chad" belongs in the Evening Report as a first-class number.
**Containment:** Constitutional floor: defaults must always be the *conservative* branch (do-nothing must never spend, send, or bind). If that discipline held, attrition costs opportunity, never safety — audit that it held.
**Decision Packet:** Yes — a meta-packet when the rate crosses threshold: "you are effectively delegating class X to defaults; make that delegation explicit or reclaim it."
**Recovery:** Chad either formally delegates (a value he authors: class X's default becomes standing policy, recorded) or restructures his queue engagement.
**RTO:** Days.
**Recovery evidence:** Decided-by-Chad rate recovers, or an explicit recorded delegation exists; no default ever found on audit to have spent/sent/bound.
**Lesson:** Defaults are policy with a modesty veil. The system must measure who is actually governing — and force the drift into an explicit decision, because implicit delegation is exactly the "authority inferred from precedent" that the constitution forbids.

#### CF-06 — Fork found, packet lost
**Failure:** Classification fires correctly, NEEDS_CHAD recorded, packet emitted — and lost between emission and Chad (channel failure per OP-10, a serialization error, a filtering bug at the delivery layer). The mission holds correctly, forever. Nobody knows a question exists.
**Likelihood:** Medium. **Impact:** Medium — safe stall (right side of the failure line), unbounded duration.
**Detection:** End-to-end packet acknowledgment: emitted-but-unacknowledged packets age-alarm in the Morning Packet's `waiting_for_you` (which is generated from mission state, not from the delivery channel — an independent path).
**Containment:** Automatic: the mission's hold doesn't depend on delivery succeeding; nothing proceeds on a lost question.
**Decision Packet:** The lost one, re-delivered.
**Recovery:** Re-emit unacknowledged packets through the repaired channel; verify round-trip.
**RTO:** Detection-bound (≤1 day via the morning ritual), then minutes.
**Recovery evidence:** Zero packets in emitted-unacknowledged state older than a day; re-delivered packet answered.
**Lesson:** The packet channel needs the same at-least-once + reconciliation treatment as mission dispatch (MC-03/04). The morning ritual doubles as the reconciliation pass — provided `waiting_for_you` derives from mission state, not from the same channel that failed.

#### CF-07 — Answer lost: approved but never resumed
**Failure:** The mirror of CF-06: Chad answers a packet, the approval is recorded at the channel, but the resume event never reaches the mission (crash between acknowledgment and state transition). Chad believes the matter is moving; the mission still holds. Two weeks later: "whatever happened with X?"
**Likelihood:** Medium. **Impact:** Medium-High — silent non-execution of an explicit decision; erodes the inverse trust direction (Chad's trust that answering *does* something).
**Detection:** Answered-but-still-holding audit: resolved packets whose missions haven't transitioned within an hour alarm; the resolution and the mission state live in different stores, so the diff is mechanical.
**Containment:** Answer application is idempotent and re-drivable: the recorded answer can be re-applied any number of times safely.
**Decision Packet:** No — the decision exists; this is plumbing.
**Recovery:** Re-apply recorded answers to held missions; verify transitions.
**RTO:** Detection-bound (hours), then minutes.
**Recovery evidence:** Zero missions holding on already-answered packets; the specific mission resumed and visible in the next Evening Report.
**Lesson:** An answer is a durable event to be applied until confirmed, not a message to be delivered once. Chad's side of the trust equation — "when I decide, it happens" — needs the same reconciliation machinery as the system's side.

#### CF-08 — Fork evasion by decomposition
**Failure:** A boundary-class outcome gets decomposed — by planning pressure, not intent — into steps that each individually classify CONTINUE: drafting the message (CONTINUE), preparing the send config (CONTINUE), a "finalize comms" step that inherits earlier classifications (CONTINUE). The composite is an external send that no single step presented as one.
**Likelihood:** Medium. **Impact:** Existential-class — same class as CF-01 but *structural*: it defeats a correct rule table by never showing it the whole action.
**Detection:** Effect-level classification as backstop: classify at the moment of *effect* (the API call that leaves the boundary), not only at the planning step — the last hop before an external effect must itself re-classify regardless of upstream verdicts.
**Containment:** The uncertain-defaults rule again bears the load ("uncertain whether evidence-gathering mutates state → treat it as action"); effect-level re-classification makes decomposition-evasion structurally impossible rather than just discouraged.
**Decision Packet:** Yes on discovery — identical to CF-01 disclosure.
**Recovery:** As CF-01, plus: audit recent multi-step missions for composite effects that never classified as composites.
**RTO:** Hours to days.
**Recovery evidence:** Test: a decomposed send in a harness gets caught at the effect hop; audit of the window clean.
**Lesson:** Classify effects, not tasks. Any classification scheme keyed to work-units can be defeated by re-chunking the work — the boundary crossing happens at the world's edge, so that is where the final check must live.

#### CF-09 — PAUSE leak: the silent graveyard
**Failure:** PAUSE items are supposed to surface "in the next scheduled brief." A brief-generation change in month 4 (a filter, a truncation for length per MC-10) drops some PAUSE classes from the Morning Packet. They hold state perfectly and are never seen again — dozens of them by month 6.
**Likelihood:** Medium-High. **Impact:** Medium — no boundary crossed, but a growing shadow of stalled intentions; the PAUSE state's legitimacy ("in the next brief, not before") depends on *the next brief actually carrying it*.
**Detection:** Conservation check: count of live PAUSE items in mission state vs. count surfaced across recent briefs — a persistent gap is the leak; oldest-unsurfaced-PAUSE age as the alarm metric.
**Containment:** PAUSE items never expire or self-resolve; the leak loses visibility, not state — everything remains recoverable.
**Decision Packet:** No; individual resurfaced items may carry their own.
**Recovery:** Fix brief generation; surface the backlog in a dedicated triage session (not one giant unreadable packet — MC-10's lesson).
**RTO:** A day.
**Recovery evidence:** Conservation check balanced across a week of briefs; no PAUSE item older than its recheck date unsurfaced.
**Lesson:** "Will be surfaced later" is a promise that needs an invariant, not an intention. Anything whose safety argument is "it appears in the next brief" must be conservation-checked against the briefs actually produced.

---

## Category 7 — Income Scout (IS-01 … IS-10)

The opportunity engine: local-first, no network, deterministic 0-100 scoring, human-entered evidence only, atomic JSON store, inbox-directory ingestion, exact+fuzzy dedup, explicit `ALLOWED_TRANSITIONS` lifecycle. It detects, prices, ranks, and expires — it never pursues (constitutional: "never chase autonomously").

#### IS-01 — Poisoned opportunity: garbage in, rank one out
**Failure:** A JSON file in the inbox — a forwarded "opportunity" from an untrusted contact, or Chad's own hurried entry from a hypey email — carries fabricated economics (expected_revenue_usd: 250000, chad_hours_weekly: 1). The deterministic engine does its job faithfully: it scores fiction to the top and the Morning Packet's `opportunity_highlight` presents it.
**Likelihood:** High. **Impact:** High — the ranking's authority launders the input's garbage; Chad's scarce attention (and possibly money-adjacent follow-up) is steered by fabrication.
**Detection:** Confidence machinery is the designed defense: source-type priors keep unverified entries at low confidence, and the validation pipeline demands human-entered evidence before confidence rises. Sanity flags at ingest (economics outside historical percentile bands) mark outliers for review.
**Containment:** Constitutional: the scout never chases — the worst automatic outcome is a bad *highlight*, never a bad *action*. Score is presented with confidence and provenance attached ("the composite is provenance, not input" — MC re-scores through its own weights).
**Decision Packet:** Yes — but that's true of every pursued opportunity by design; the packet's evidence chain is where fabrication should die.
**Recovery:** Fail the opportunity's validation checks with recorded evidence; lifecycle-transition it to rejected/expired; note the source's reliability for future priors.
**RTO:** Minutes once questioned.
**Recovery evidence:** The opportunity's audit trail shows FAILED validation checks with reasons; it no longer appears in rankings; the source's subsequent entries arrive at reduced prior.
**Lesson:** Determinism is neutrality: the engine amplifies whatever it is fed with perfect consistency. The defense is that score ≠ confidence ≠ decision — three separate gates — and the human-entered-evidence rule means fiction must survive a human's typing fingers twice to reach a packet.

#### IS-02 — Sub-threshold duplicates: the split opportunity
**Failure:** The same opportunity re-enters over weeks under different wording — "Anesthesia expert review for Smith case" / "Chart review, Smith v. Mercy" — fuzzy similarity 0.79, under the 0.82 threshold. Two records accumulate divergent evidence, confidence, and lifecycle states. Effort splits; one copy validates while the other expires; the ranking shows both, diluted.
**Likelihood:** High. **Impact:** Medium — wasted validation effort, contradictory records, misleading rank positions.
**Detection:** Periodic cross-store dedup sweep at a *lower advisory* threshold (e.g. 0.65) producing merge-candidates for human review — the tunable-threshold hook exists per call by design.
**Containment:** Dedup already runs at ingest with policy (`reject | flag | allow`); `flag` mode keeps the near-miss visible instead of silently admitting it.
**Decision Packet:** No — merging records is bookkeeping; the merged entity's evidence is a union with provenance kept.
**Recovery:** Merge: elect the elder record, migrate evidence/transitions with provenance, expire the duplicate with a pointer.
**RTO:** Minutes per pair.
**Recovery evidence:** Advisory sweep returns no merge-candidates above the review line; merged record's history shows both provenance chains.
**Lesson:** A dedup threshold is a tradeoff frozen at design time; the sweep-at-lower-threshold pattern converts its false negatives from silent divergence into a reviewable queue. Identity of *opportunities* (like identity of decisions, CF-04, and events, TE-01) is where the real difficulty lives.

#### IS-03 — Prior gaming: the recruiter flood
**Failure:** One persistent recruiter (or newsletter, or lead mill) learns that entries get attention and floods the inbox via Chad's own forwarding habit. Each entry lands with the RECRUITER source prior; volume does the rest — the ranking's top decile slowly becomes one source's catalog.
**Likelihood:** Medium-High. **Impact:** Medium — attention capture by volume; the ranking stays deterministic and becomes deterministic *about the wrong things*.
**Detection:** Source-concentration metric: share of active opportunities per source_detail; alarm when one source exceeds a band. Per-source acceptance history (how many of this source's entries ever validated) as an evidence-backed reliability record.
**Containment:** Priors are per-source-*type* by design, but validation is per-opportunity: volume buys presence, not confidence — nothing validates without human-entered evidence per item.
**Decision Packet:** No for flagging; Yes if Chad decides to change how he treats the source (a relationship call).
**Recovery:** Bulk-expire the flood with reasons; Chad adjusts his forwarding habit (the actual ingress); source reliability note recorded.
**RTO:** One session.
**Recovery evidence:** Source-concentration back in band; ranking top decile shows source diversity.
**Lesson:** The scout's no-scraping rule means every poisoning arrives through Chad's own hands — the ingestion boundary is a human habit, not an API. Source concentration is the observable that catches what per-item review can't see.

#### IS-04 — Stale market: validated then obsolete
**Failure:** An opportunity validated thoroughly in month 3 (strong evidence, high confidence, stage: validated) sits while Chad's calendar is full. By month 6 the market moved — the niche got crowded, the rate dropped, the contact changed jobs. Confidence, being evidence-driven and event-updated, never decayed. The Morning Packet still presents it with month-3 confidence.
**Likelihood:** Very High (this is TE-06's twin in the opportunity domain). **Impact:** Medium-High — Chad commits scarce hours (and possibly money) on world-state that expired.
**Detection:** Evidence-age surfaced with every presentation: the packet's `why_chosen` receipts include the newest supporting evidence's date; staleness bands flag opportunities whose evidence is older than their market's plausible half-life.
**Containment:** Lifecycle has expiry as a first-class transition; the gap is *triggering* it — an age-triggered re-validation flag (not auto-expiry: evidence is human-entered, so a human must refresh it).
**Decision Packet:** Yes at pursuit time regardless — and the packet's honest prices must be re-priced if evidence is stale, which is exactly what the evidence-chain requirement forces.
**Recovery:** Re-validate: refresh the key checks with current evidence; confidence updates on results; expire if the market truly closed.
**RTO:** Chad-hours-bound (evidence is human-entered): days.
**Recovery evidence:** Every packet-presented opportunity shows evidence newer than its staleness band; re-validation events in the trail.
**Lesson:** Confidence is a statement about evidence, and evidence is a statement about a *moment*. Any confidence number presented without its date is quietly claiming the world stopped moving.

#### IS-05 — ROI hallucination upstream of the human gate
**Failure:** The human-entered-evidence rule is satisfied in letter, defeated in spirit: Chad asks a chat LLM to "research the market for X," pastes its confident, fabricated numbers into the validation evidence fields. The engine now holds hallucinated market size, rates, and demand — with `human-entered` provenance and STRONG evidence strength, because Chad typed it.
**Likelihood:** High — this is how people use LLMs in 2026. **Impact:** High — the one gate the architecture relies on (human entry = reality contact) is bypassed by the human himself; downstream money packets inherit fabricated prices.
**Detection:** Nearly blind at the engine (the data is well-formed and human-entered). Honest defenses: evidence records carry a *source citation* field, and validation checks that cite no verifiable source can't be marked STRONG; discrepancies surface at pursuit time when packet prices meet reality.
**Containment:** The same three-gate structure as IS-01: score ≠ confidence ≠ decision; the pursuit packet's "honest prices" requirement forces one more reality contact before money moves.
**Decision Packet:** Yes (pursuit-time, as always) — and it is the last line of defense here.
**Recovery:** On first reality contact contradiction: mark the affected evidence contradicted (the memorygraph pattern applied to scout evidence), re-run confidence from surviving records, RCA the entry habit.
**RTO:** Detection-bound (often not until pursuit); hours after.
**Recovery evidence:** Contradicted evidence flagged with the reality data attached; confidence re-derived; subsequent entries carry citations.
**Lesson:** "Human-entered" was a proxy for "reality-verified," and the proxy broke the day the human got a fluent fabricator in his pocket. Provenance must name the *source*, not just the typist — this is TE-07's lesson arriving through the front door, invited.

#### IS-06 — Unit error: the 12× opportunity
**Failure:** Fatigued entry (OP-05 conditions): monthly revenue typed into the *annual* field, or `chad_hours_weekly` given as minutes. Economics off by 12× or 60×; the composite score rockets; the opportunity dominates the ranking and the `opportunity_highlight` for weeks.
**Likelihood:** High. **Impact:** Medium — attention mis-steered; High if it reaches a pursuit packet unre-checked.
**Detection:** Ingest-time plausibility bands (revenue/hour implied rates outside human-possible ranges flag for review); the packet's `why_chosen` receipts make the raw numbers visible at every presentation — a 12× error is *conspicuous* when shown.
**Containment:** Numbers are clamped ≥0 and coerced at ingest (existing), but magnitude errors pass; the flag-for-review path is the net.
**Decision Packet:** No — correcting a typo with an audit-trail entry is bookkeeping.
**Recovery:** Correct the field (recorded as an update event with reason); re-score; ranking self-heals deterministically.
**RTO:** Minutes.
**Recovery evidence:** Update event with old→new values in the trail; implied-rate check passes; ranking position plausible.
**Lesson:** Deterministic scoring turns one keystroke into weeks of consistent, confident wrongness. Receipts-at-presentation (`why_chosen`) are the cheap defense: a system that always shows its arithmetic gets its arithmetic checked for free.

#### IS-07 — Store schema drift by hand edit
**Failure:** Chad (OP-09 pattern) hand-edits `opportunity_scout_store.json` — fixes a title, deletes an entry, tweaks a stage string to a value not in the lifecycle enum. The store still parses (version field intact) but now violates invariants the code assumes: a transition that never happened, a stage outside `ALLOWED_TRANSITIONS`' vocabulary.
**Likelihood:** Medium. **Impact:** Medium — undefined behavior in lifecycle/validation logic; the audit trail now contains a state no legal transition sequence produces.
**Detection:** Load-time invariant validation beyond schema-version: every stage ∈ enum, every transition chain legal, fingerprints match titles; violations fail loudly (the store's existing fail-loud philosophy extended from version to *semantics*).
**Containment:** Existing: corrupt-file backup convention preserves the evidence; atomic writes mean the code never half-writes over the hand edit.
**Decision Packet:** No; Yes only if reconstructing lost entries requires judgment about what they were.
**Recovery:** Restore last code-written snapshot; re-apply Chad's intended changes through the CLI (which records events properly).
**RTO:** Under an hour.
**Recovery evidence:** Store passes full invariant validation; Chad's intended changes present as legal, recorded events.
**Lesson:** A JSON store's writability is an attractive nuisance for its own operator. The defense isn't locks — it's making the legitimate path (CLI) cheaper than the editor, and validating *semantics*, not just schema, at every load.

#### IS-08 — Inbox replay: the processed/ directory returns
**Failure:** A restore (MC-12/HM-02 aftermath) or a sync tool resurrects already-ingested files from `processed/` back into the inbox — or loses the `processed/` marker entirely. The next ingestion sweep re-ingests months of history: mass duplicates (exact-fingerprint catches most; edited-along-the-way files evade), stale opportunities reborn at fresh timestamps.
**Likelihood:** Medium. **Impact:** Medium — store pollution, ranking noise, and a burst of false "new opportunities" in the Evening Packet's movement counts (which then pollutes Compound/evidence feeds — TE-05's accidental twin).
**Detection:** Exact fingerprints reject the identical files loudly (count spike alarm: N rejects in one sweep = replay signature); ingest-rate anomaly vs. baseline.
**Containment:** Fingerprint layer (existing) absorbs the bulk; `flag` dedup policy quarantines fuzzy survivors; files are never deleted, so nothing is lost either way.
**Decision Packet:** No.
**Recovery:** Quarantine the sweep's admissions; diff against pre-restore store; void the resurrections; fix the sync/restore path that resurrected them.
**RTO:** Hours.
**Recovery evidence:** Store count matches pre-incident + legitimately-new; movement counts corrected in the next report.
**Lesson:** The inbox is an at-least-once channel the moment backups exist. `processed/` is a marker, not a guarantee — ingestion idempotency (fingerprints) is the real wall, and its *reject counts* are the alarm bell.

#### IS-09 — Lifecycle resurrection
**Failure:** A rejected opportunity (declined for good reason in month 2 — bad counterparty, ethical concern) re-enters active consideration: a replayed transition event, a hand edit (IS-07), or a merge mistake (IS-02 recovery gone wrong). The *reason it was rejected* is exactly the kind of context that doesn't survive four months; it ranks well and gets highlighted again.
**Likelihood:** Low-Medium. **Impact:** High — re-pursuing something rejected for character/ethics reasons risks relationships and reputation (a never-delegated domain) with extra steps.
**Detection:** `ALLOWED_TRANSITIONS` enforcement (existing) blocks illegal state jumps at the API; the audit is for state that *bypassed* the API: any active opportunity whose transition history contains a terminal state is mechanically findable.
**Containment:** Terminal states are terminal in the state machine; rejection reasons are recorded with the transition (existing convention: every transition carries timestamp and reason).
**Decision Packet:** Yes — reviving anything from a terminal state should *always* be a packet, with the original rejection reason quoted in the evidence chain.
**Recovery:** Re-terminate with the original reason re-attached; audit for siblings; fix the bypass path.
**RTO:** Minutes per item.
**Recovery evidence:** No active items with terminal-state history absent a revival packet; the revival-requires-packet rule verified by test.
**Lesson:** A rejection's most valuable byte is the reason, and reasons decay from memory faster than records decay from stores. Terminal states must be sticky precisely because the human who made them will have forgotten why.

#### IS-10 — Ranking monoculture: the blind spot compounds
**Failure:** No event at all — the deterministic weights (ROI, time economics, strategic alignment) systematically favor one shape of opportunity (low-touch, high-hourly, near-term: expert-witness-like work) over others (durable products, relationship investments, learning bets). Six months of consistent ranking = six months of one strategy, never chosen, only accreted. The Evening Packets look great.
**Likelihood:** Very High (every fixed scoring function has this property). **Impact:** High and slow — strategic narrowing without a decision; the system optimizes Chad into a local maximum.
**Detection:** Portfolio-shape reporting: distribution of pursued opportunities by type/duration/asset-class over time — visible only in aggregate, never per-item; the PHILOSOPHY layer's asset-building doctrine gives the reference shape to compare against.
**Containment:** Constitutional: weights are *values*, and "the machine applies values; it does not author them" — the weights are Chad's to change, and determinism means the monoculture is at least *legible*: same inputs, same scores, fully explainable.
**Decision Packet:** Yes — a periodic portfolio-review packet: "here is the shape of six months of rankings; is this the strategy you intend?"
**Recovery:** Chad revises weights (a values act, recorded); rankings shift deterministically; no history rewrite needed.
**RTO:** One review session.
**Recovery evidence:** Weight-change event recorded; portfolio shape trends toward the declared intent over subsequent months.
**Lesson:** A deterministic ranker is a strategy that never announces itself as one. The dangerous outputs aren't wrong items — they're six months of individually-defensible items whose *sum* nobody chose. Aggregates need review rituals just like decisions do.

---

## Category 8 — Expert Witness (EW-01 … EW-10)

The highest-stakes domain: Chad's medico-legal expert-witness practice. Case documents carry PHI, protective orders, and privilege. The architecture's rule is absolute isolation — "expert-witness isolation: forbidden markers rejected at every boundary" (invariant 6), expert-witness sources rejected at the Mission Control inbox boundary. Failures here don't cost throughput; they cost Chad's license, credibility, and legal exposure.

#### EW-01 — Isolation breach: case document in the general inbox
**Failure:** A case PDF lands in the general ingestion path — mis-saved by Chad into the wrong synced folder, or an email-forwarding rule misfires. General-side machinery (Income Scout ingestion, context building) touches privileged case material.
**Likelihood:** Medium — the sorting is done by a busy human. **Impact:** Critical — privileged/PHI material enters systems it must never enter; every downstream copy (stores, logs, contexts) becomes a spoliation/exposure surface.
**Detection:** The boundary check itself: forbidden-marker scanning at every ingestion boundary (existing invariant) — case numbers, party names, PHI patterns, document headers; a rejection event is the *successful* detection.
**Containment:** Automatic: rejection at the boundary before ingestion (the designed behavior); the file is quarantined where it landed, not processed.
**Decision Packet:** Yes — any confirmed touch of case material by general machinery requires Chad's judgment on legal/professional obligations (notification, remediation), which is relationship/reputation territory at minimum.
**Recovery:** Quarantine; enumerate every system the content reached (ingestion logs make this answerable — the audit trail's purpose); purge copies from each, including derived artifacts (embeddings, summaries, store entries); document the incident contemporaneously as legal-defensibility evidence.
**RTO:** Hours if rejected at boundary (the normal case); days if it got past.
**Recovery evidence:** Marker-scan of all general stores/logs returns clean; the purge is itself documented with timestamps; boundary rejection verified live with a test document.
**Lesson:** The boundary check earns its keep on the day the human mis-sorts — which is a *when*, not an *if*. Rejections must be treated as saves, logged and celebrated, because each one is a career-threatening incident that didn't happen.

#### EW-02 — Marker bypass: PHI in a shape the scanner can't read
**Failure:** The forbidden-marker check scans text. A case document arrives as a scanned-image PDF, a photo of a chart, a ZIP, or an unusual encoding — content opaque to the scanner. It passes the boundary *because* it's unreadable, then gets processed by tooling that *can* read it (OCR-capable models).
**Likelihood:** Medium-High — legal document production is full of scanned images. **Impact:** Critical — same as EW-01 but the tripwire never fired; discovery may be much later.
**Detection:** Structural: the boundary policy must be default-deny for unscannable content ("uncertain → more conservative state" is already the constitutional default) — opaque formats are rejected *as* opaque, not passed as clean. Detection of a past bypass: marker-scan of general stores using OCR, periodically.
**Containment:** Default-deny at the boundary is the whole game; post-hoc, same purge machinery as EW-01.
**Decision Packet:** Yes (as EW-01) upon any confirmed bypass.
**Recovery:** As EW-01, plus: the bypassing format joins the boundary's explicit reject list.
**RTO:** As EW-01.
**Recovery evidence:** Boundary test suite includes image/archive/encoding cases, all rejected; periodic OCR sweep of general stores clean.
**Lesson:** A scanner that passes what it cannot read is a gate that opens for the biggest trucks. "I couldn't check it" and "it's clean" must be opposite verdicts — the constitution already knew this ("uncertain whether evidence-gathering mutates state → treat it as action"); the boundary just has to obey it.

#### EW-03 — Cross-case contamination
**Failure:** Two active cases' documents are processed in one context window — a session reused across matters, or two cases' files in one working directory. The opinion drafted for *Case A* is subtly informed by facts from *Case B*: a dosage pattern, a standard-of-care detail. Undetectable in the output; devastating under cross-examination ("Doctor, where in THIS record did you find that?").
**Likelihood:** Medium. **Impact:** Existential-class for the practice — an expert whose opinions can't be traced to the case record is impeached; every past opinion becomes suspect.
**Detection:** Provenance-per-assertion at drafting time: every factual claim in a work product must cite a document *in this case's* corpus — an assertion with no in-corpus source is the alarm (the evidence-or-silence rule doing legal duty). Structural detection: session/workspace audit showing single-matter contexts.
**Containment:** Structural hygiene, one matter = one isolated context/workspace, never reused across cases (the architecture's isolation doctrine applied *within* the expert-witness domain, not just at its outer boundary).
**Decision Packet:** Yes — a suspected contamination of a delivered opinion requires Chad's judgment on professional obligations.
**Recovery:** Re-derive the work product in a clean single-case context; diff assertions against the case corpus; correct or withdraw anything unsupported; document the process.
**RTO:** Days per affected work product.
**Recovery evidence:** Every assertion in the final product carries an in-corpus citation; workspace audit shows no multi-matter sessions since remediation.
**Lesson:** Isolation isn't one wall around the expert-witness domain — it's a wall around *each case*. The citation-per-assertion discipline is simultaneously the quality bar, the contamination detector, and the cross-examination armor; it must be cheaper to follow than to skip.

#### EW-04 — PHI to a cloud model endpoint
**Failure:** A routing misconfiguration — a fallback provider chain, a default model setting restored after an update (HM-09/HM-12 texture) — sends case-document content to a cloud LLM API that isn't under a BAA and logs prompts. PHI and privileged material leave Chad's custody into a third party's retention pipeline.
**Likelihood:** Medium — routing config is exactly the kind of thing that drifts. **Impact:** Existential — HIPAA exposure, protective-order violation, privilege waiver arguments, mandatory-notification analysis. This is the single worst event Olympus can produce.
**Detection:** Egress audit: expert-witness workloads log their model endpoints; any endpoint outside the approved list for that domain alarms. Config-diff monitoring (HM-12 machinery) on provider routing treated as a *safety-critical* manifest.
**Containment:** Structural: expert-witness processing pinned to approved endpoints (local models or BAA-covered) with the pin enforced at the routing layer *for that workspace*, not by global default — a global default is one update away from wrong.
**Decision Packet:** Yes, immediately and with highest priority — breach analysis, notification duties, and counsel involvement are entirely Chad's.
**Recovery:** Freeze the domain's processing; establish exactly what content reached which endpoint when (the egress log's purpose); exercise provider deletion/retention mechanisms; Chad performs the legal analysis with counsel; RCA the routing drift.
**RTO:** Technical freeze in minutes; legal aftermath weeks-months.
**Recovery evidence:** Egress log demonstrates the full scope (or its absence — which is why the log must predate the incident); routing pin verified by test from inside the workspace; provider confirmation of deletion where obtainable.
**Lesson:** For this domain the model endpoint is not infrastructure — it is custody of privileged material. The pin must live as close to the data as possible, and the egress log is the only thing that converts "we think only X leaked" into evidence. A control whose failure is existential cannot depend on a global setting shared with the Build Program's conveniences.

#### EW-05 — Incorrect routing: case mission to the general pipeline
**Failure:** An expert-witness task gets dispatched as an ordinary mission — Mission Control's planner picks it up from a note, or Chad phrases it ambiguously ("summarize the Smith documents") — and it runs on Hermes Mini in the general environment: general logs, general stores, general model routing (→ EW-04).
**Likelihood:** Medium. **Impact:** Critical — a full isolation bypass via the *orchestration* layer rather than the data layer; the general audit trail itself becomes contaminated with case material.
**Detection:** Dispatch-time boundary: the same forbidden-marker rejection applied to mission *content* at dispatch, not just documents at ingestion ("rejected at every boundary" means this boundary too — the contract already rejects expert-witness sources at the MC inbox; the dispatcher is the same class of boundary).
**Containment:** Automatic rejection at dispatch; the mission bounces to NEEDS_CHAD ("this looks like case work — confirm domain") rather than running.
**Decision Packet:** Yes — both the bounce (routing confirmation) and any confirmed contamination (EW-01 machinery).
**Recovery:** If it ran: EW-01's purge, extended to mission logs/transcripts (which is painful — transcripts are evidence, HM-04 — so redaction with documented method rather than deletion); re-run properly isolated.
**RTO:** Hours to days.
**Recovery evidence:** Marker scan of general mission logs clean (or redaction documented); dispatch-time rejection verified with a test mission.
**Lesson:** Data boundaries without *task* boundaries are half a wall. The orchestrator must know which domain a mission belongs to before it knows anything else about it — ambiguous phrasing from a tired operator is the expected input, not the edge case.

#### EW-06 — Memory absorption: case facts become "knowledge"
**Failure:** The general memory layer (memorygraph) absorbs case-adjacent facts as claims during legitimate-seeming work — a claim like "standard induction dose of propofol is …" tagged from a case document, or worse, "Dr. X of Mercy Hospital deviated by …". Case-derived assertions persist as system knowledge after the matter closes, surfacing in unrelated contexts months later.
**Likelihood:** Medium. **Impact:** Critical — retention beyond the matter (protective-order exposure), plus contamination of the trust ledger with claims whose provenance can't be shown in any future context.
**Detection:** Claim-provenance audit (TE-07's machinery, different threat): claims whose provenance chains touch expert-witness sources are findable mechanically — *if* provenance is faithfully recorded, which it is by design.
**Containment:** The recorder-side allowlist pattern inverted: expert-witness contexts must run with memory *recording disabled* or routed to a per-matter store that dies with the matter — never the general graph.
**Decision Packet:** Yes for purging established claims (rewriting the knowledge base has judgment content); No for blocking the recording path.
**Recovery:** Purge case-derived claims and their promotion effects; verify no packet or decision cited them (the citation trail answers this); per-matter memory henceforth.
**RTO:** A day.
**Recovery evidence:** Provenance audit of the full graph shows zero expert-witness-rooted chains; per-matter stores destroyed on matter close, with destruction recorded.
**Lesson:** Memory is retention, and retention is a legal category. The general knowledge graph must be constitutionally incapable of remembering case material — because "we can delete it later" fails the day a claim's provenance was recorded sloppily.

#### EW-07 — Retention violation: documents outlive the matter
**Failure:** A case closes; the protective order requires return/destruction of produced documents. The originals get handled — but copies persist in Olympus's periphery: a worktree, a backup set (→ EW-09), a processed/ directory, a transcript. Eighteen months later a subpoena or audit finds them.
**Likelihood:** High — copies are what computers do. **Impact:** Critical — direct violation of court orders; sanctions exposure; every future protective order signed becomes riskier.
**Detection:** Matter-close checklist as a first-class procedure: a documented sweep (marker-scan across all storage, including backups' indexes) executed and *recorded* at each matter close; the record is the defense.
**Containment:** Upstream structure makes the sweep tractable: per-matter isolation (EW-03/EW-06) means case material lives in enumerable locations by construction — the sweep verifies the enumeration instead of searching the world.
**Decision Packet:** Yes — matter-close destruction is irreversible by definition; the packet certifies scope and authorizes it.
**Recovery:** Late discovery: destroy immediately, document the late destruction with dates and method, Chad assesses disclosure duties with counsel.
**RTO:** Hours per discovery; the reputational tail is long.
**Recovery evidence:** Matter-close records show the sweep, the packet, and the destruction for every closed matter; a periodic all-storage marker scan finds nothing from closed matters.
**Lesson:** Destruction is a *process with evidence*, not a deletion. The system that is excellent at never losing data must be equally excellent at provably losing it on command — and the second competence doesn't come free with the first; it must be built and rehearsed.

#### EW-08 — Metadata leakage: the case that names itself
**Failure:** Document contents stay isolated, but *metadata* leaks into general systems: a git commit "add Smith-v-Mercy analysis notes," a mission title in Mission Control's store, an Evening Report line "3 hours on the Mercy matter," a filename in a disk-usage report. Party names + Chad's involvement + timing = discoverable, privilege-adjacent information in unprotected stores.
**Likelihood:** High — metadata is exhaust; nobody watches it. **Impact:** High — weaker than content exposure but broad: it maps the practice, undermines confidentiality assurances, and is discoverable.
**Detection:** The marker scan applied to metadata surfaces: commit logs, mission titles, report text, filenames — same patterns (party names, case numbers), different corpus.
**Containment:** Naming discipline enforced at the isolation boundary: matters get opaque codenames *at intake*; the codename↔matter mapping lives only inside the isolated domain. Everything outside speaks codename or nothing.
**Decision Packet:** No for adopting codenames; Yes if leaked metadata's exposure requires professional-duty analysis.
**Recovery:** Scrub reachable surfaces (rewrite mission titles, redact reports); accept that git history and backups make full scrubbing impractical — which is the argument for intake-time codenames, recorded in the RCA.
**RTO:** Hours; residual risk permanent.
**Recovery evidence:** Metadata scan of general surfaces clean; intake procedure shows codenames applied before any general system sees the matter.
**Lesson:** Content isolation with named metadata is a confidential letter in a transparent envelope. The cheapest possible control — an opaque name assigned in the first minute — beats every scrubbing procedure invented afterward, because exhaust systems never forget.

#### EW-09 — Backup exfiltration: the sync chain nobody drew
**Failure:** The isolated case store sits on a disk that Time Machine copies to a NAS that a sync client mirrors to consumer cloud storage. Every layer is someone's good idea; the composition moves PHI and privileged material to third-party servers without any single decision doing it.
**Likelihood:** Medium-High — backup sprawl is the default state of personal infrastructure. **Impact:** Critical — EW-04's exposure via the storage plane instead of the model plane; worse retention characteristics (backups are designed to persist).
**Detection:** Data-flow enumeration as a scheduled audit: for each isolated store, walk the actual copy chain (backup jobs, sync clients, cloud targets) and compare against the approved custody list; alarm on any hop not on it.
**Containment:** Structural: isolated stores live on volumes explicitly excluded from general backup chains, with their *own* custody-approved backup (encrypted, keys in Chad's custody, target under BAA or fully local) — because the answer can't be "no backups" (HM-11/IN-06 need them).
**Decision Packet:** Yes — both approving the custody chain (values/irreversibility) and responding to a discovered leak (EW-04 machinery).
**Recovery:** Break the unapproved chain; purge cloud-side copies via provider mechanisms (documenting responses); rotate anything whose exposure creates ongoing risk; RCA the chain's construction.
**RTO:** Days (provider-dependent).
**Recovery evidence:** Custody audit shows every isolated store's full copy chain ∈ approved list; provider deletion confirmations filed.
**Lesson:** Custody is a property of the *composition* of storage systems, not of any component. Each backup hop was individually reasonable; the audit that walks the actual chain end-to-end is the only view where the violation exists at all.

#### EW-10 — Discovery of AI use: the process becomes the exhibit
**Failure:** Opposing counsel asks the deposition question: "Doctor, did you use artificial intelligence in preparing your opinion?" Honest answer: yes. Follow-ups subpoena the process: prompts, drafts, transcripts, the system's role vs. Chad's. Poorly organized process records — or records revealing that analysis Chad swore to was substantially machine-drafted — impeach the opinion and the expert.
**Likelihood:** High and rising — this question is becoming standard practice. **Impact:** Existential for the practice — not a malfunction: Olympus working *as designed* becomes the attack surface. Every past and future engagement is implicated by one bad transcript.
**Detection:** N/A — this is an adversarial audit by a motivated third party. The "detection" is preparing as if every transcript will be Exhibit A, because it may be.
**Containment:** Structural honesty, decided *before* the first engagement, not after the subpoena: a documented methodology (what the system does — document management, citation checking, draft assistance; what Chad does — all opinions, all judgments); transcripts that *show* that division because it's true (HUMAN_FIRST's division of labor is, conveniently, the legally defensible one: the machine never authors judgment).
**Decision Packet:** Yes — the methodology statement and each engagement's disclosure posture are values/reputation decisions only Chad can make, ideally with counsel, per matter.
**Recovery:** If caught unprepared: produce what exists honestly (spoliation is the only worse outcome), engage counsel on scope, and expect the opinion's weight to suffer; then build the methodology discipline for every subsequent matter.
**RTO:** Per-matter; reputation recovery is measured in years.
**Recovery evidence:** A written methodology exists and matches observable practice; per-matter records organized for production on demand; Chad can answer the deposition question in one calm sentence.
**Lesson:** The audit trail Olympus keeps for its own governance is discoverable the moment it touches litigation work. The only safe posture is that the records, read hostilely by a skilled adversary, *prove the division of labor Chad testifies to* — which means the division must be real, enforced, and legible every single day. Integrity isn't just the ethical choice; it's the only defensible one.

---

## Category 9 — Infrastructure (IN-01 … IN-12)

The substrate Olympus stands on and does not control: a residential network, a mesh VPN, two consumer machines, external SaaS (GitHub), and frontier-model providers.

#### IN-01 — Tailscale outage / node key expiry
**Failure:** The tailnet drops — coordination-server outage, or the quieter version: a node key expires on the Mini and nobody re-authenticates it. Machines can't reach each other; dispatch and review traffic halts. The key-expiry variant looks like a network problem and is actually an authentication problem.
**Likelihood:** High (key expiry is near-certain over six months unless disabled; service outages happen). **Impact:** Medium — the pipeline splits into two healthy halves that can't talk.
**Detection:** Inter-node heartbeat distinct from internet reachability (Mini can reach GitHub but not MBP = mesh problem, not internet problem); key-expiry horizon surfaced in the evidence feed *before* expiry.
**Containment:** Automatic: each side degrades to local-only work — Mini continues local missions and queues pushes; review queue buffers (HB-01 machinery); nothing bypasses review for being unreachable.
**Decision Packet:** No; Yes only if re-authentication requires credential-level action (constitutionally Chad's).
**Recovery:** Re-auth the expired node or wait out the outage; queues drain in order.
**RTO:** Minutes (re-auth) to hours (provider outage).
**Recovery evidence:** Mesh heartbeats green; queued traffic drained; queue-age back under thresholds.
**Lesson:** Expiring credentials are scheduled outages with a known date — the system knows the date and must surface it as a maintenance item, not discover it as an incident.

#### IN-02 — GitHub outage
**Failure:** GitHub is down or degraded for hours. Pushes fail, PRs can't open/merge, CI is silent. The mission pipeline's coordination substrate (branches, PRs, review anchors) is gone while both machines are fine.
**Likelihood:** High (multiple partial outages per six months is base rate). **Impact:** Medium — throughput stall; risk concentrates in *retry behavior* (hammering) and in work that proceeds past its unverifiable checkpoint.
**Detection:** Error classification distinguishing remote-service failure from auth (HM-10) and local network (IN-05); provider status as corroboration.
**Containment:** Automatic: exponential backoff with caps (the repo's own git-ops discipline already prescribes bounded retries); missions at push/PR checkpoints PAUSE ("external block" — a named throttle reason) instead of piling retries; local commits keep accumulating safely.
**Decision Packet:** No.
**Recovery:** Outage ends; queued pushes and PR operations replay in order; verify no double-created PRs from ambiguous timeouts (MC-03 reconciliation).
**RTO:** Provider-bound; minutes of drain after.
**Recovery evidence:** All local branches present on origin; one PR per mission; retry logs show backoff, not hammering.
**Lesson:** Local-first design earns its keep here: git's distributed nature means an outage costs synchronization, not work. The failure to prevent is self-inflicted — retry storms and duplicate remote objects created by impatient timeout handling.

#### IN-03 — Model provider outage
**Failure:** The primary LLM provider goes down or errors hard for hours. Everything agentic — implementation, review, conversation — stops at once. Unlike IN-02, there is no local fallback for cognition itself.
**Likelihood:** High. **Impact:** Medium-High — total agentic stall; deterministic components (scoring, scheduling, stores, packets already generated) keep running, which is exactly the designed degradation.
**Detection:** Provider-error classification and status corroboration; distinct from quota (IN-10) and auth (HM-10) by error shape.
**Containment:** Automatic: in-flight missions PAUSE with clean state at the failed call; the deterministic spine (no model calls in ranking, classification, or status reporting — a design invariant) means Olympus's *governance* keeps functioning even when its *hands* stop.
**Decision Packet:** No; Yes only to authorize failover spend to a secondary provider if one is configured (money).
**Recovery:** Provider recovers; paused missions resume from their held state; burst-resume throttled to avoid rate-limit whiplash (IN-10).
**RTO:** Provider-bound.
**Recovery evidence:** Paused missions resumed and completed; no mission lost or duplicated across the gap; spend curve shows no post-outage spike beyond plan.
**Lesson:** The choice to keep ranking, classification, and reporting model-free is the reason a provider outage is a pause instead of a lobotomy. Guard that invariant — every convenience that sneaks a model call into the spine converts future outages from throughput events into governance events.

#### IN-04 — Silent model degradation
**Failure:** No outage: the provider ships a model revision, adjusts quantization or safety layers, or silently reroutes traffic. Output quality shifts — subtly worse code, softer reviews (HB-03's cousin with an external cause), different judgment texture. Every request succeeds. Nothing errors, ever.
**Likelihood:** Medium-High over six months. **Impact:** High — quality erosion across *both* implementation and review simultaneously (the HB-06 correlation), misattributed to prompts, missions, or luck.
**Detection:** Outcome baselines, not request monitoring: review finding-rates, first-pass mission success rates, canary tasks with known-good historical outputs re-run periodically and diffed. A step-change across independent workstreams on one date is a provider event.
**Containment:** None available at the request level. The deterministic checks (tests, invariants, canaries) hold the floor; the trust ledger's re-validation discipline (TE-06) bounds how long stale confidence survives.
**Decision Packet:** Yes if the response is switching providers/models (money and a values-adjacent capability call); No for detection and measurement.
**Recovery:** Confirm via canary regression; pin model versions where the provider allows; re-baseline or switch; re-validate trust promotions earned under the old model (TE-06 machinery).
**RTO:** Days (detection is the long pole).
**Recovery evidence:** Canary outputs back within historical band; finding-rates recover; ledger re-validation recorded.
**Lesson:** Olympus's cognition is a rented dependency with no changelog. Canary tasks are the only instrument that measures the model rather than the weather — run them like backups: boring, scheduled, and priceless the day they disagree with yesterday.

#### IN-05 — Home internet outage
**Failure:** The residential connection drops for hours-to-days (ISP fault, line damage). Everything external — providers, GitHub, notifications to Chad's phone — is unreachable at once. The house becomes an island with two healthy computers on it.
**Likelihood:** High. **Impact:** Medium — full external stall; the notification channel's failure is the sharp edge (Chad may be reachable but unreached: OP-10 conditions with a physical cause).
**Detection:** Trivially loud locally. The subtle half is Chad-side: his phone shows silence, and silence must be an alarm by convention (the Morning Packet dead-man switch, OP-10).
**Containment:** Automatic: local missions continue where possible (IN-03's spine invariance means anything model-dependent pauses, deterministic work continues); all external effects queue; nothing times out into a destructive fallback.
**Decision Packet:** No.
**Recovery:** Connectivity returns; queues drain with the same reconciliation discipline as IN-02; Chad's missed rituals delivered late-and-marked-late (MC-02 rule).
**RTO:** ISP-bound.
**Recovery evidence:** Queue drains verified; no duplicate external effects; the gap appears honestly in the trail.
**Lesson:** An island that holds state cleanly and reconciles honestly on reconnection loses only time — the outage rehearses exactly the disciplines (queue, reconcile, mark-late) that every smaller partial failure also needs. Treat each one as a free drill and audit the drill.

#### IN-06 — Disk failure on the Mini
**Failure:** The Mini's SSD dies — not full (HM-03), dead. Total loss of local state: worktrees, un-pushed branches, governed stores (opportunity store, memory graph, ledgers), logs, environment. The machine that runs Olympus's hands is gone.
**Likelihood:** Low-Medium. **Impact:** Critical — bounded precisely by two numbers: push lag (work since last push) and backup lag (store state since last backup). Everything else is reinstallable.
**Detection:** Loud and immediate.
**Containment:** Pre-incident only: push discipline (HM-02's lesson — origin is the real filesystem), scheduled store backups with restore *testing*, environment-as-manifest (HM-09) so the machine itself is reproducible.
**Decision Packet:** Yes — replacement hardware (money) and any restore requiring adjudication of gap-window state (TE-04, MC-12).
**Recovery:** Replace disk/machine; rebuild from manifest; restore stores from backup; run the full restore-reconciliation suite (MC-12 for missions, TE-04 for trust — demotions replayed forward); re-run missions in the push gap.
**RTO:** 1–3 days (procurement-bound).
**Recovery evidence:** Reconciliation diffs clean; gap-window work re-run or explicitly written off with reasons; a restore-test record predating the failure (the evidence that this RTO was ever real).
**Lesson:** Backup value is measured at restore time, and this scenario is the exam. The two lag numbers — push lag, backup lag — are Olympus's real exposure to hardware death and should be visible weekly, not discovered at the funeral.

#### IN-07 — Clock skew
**Failure:** NTP fails or a board battery dies; the Mini's clock drifts minutes-to-hours or jumps at boot. TLS handshakes start failing intermittently (certificate not-yet-valid), scheduled rituals fire at wrong times (MC-08), evidence timestamps scatter (TE-09), and log correlation across machines breaks — the debugging tool dies with the patient.
**Likelihood:** Medium. **Impact:** Medium — diffuse, weird, misattributed: the signature is *many unrelated small failures* whose only common factor is time.
**Detection:** NTP offset monitoring as a first-class health metric on every node; cross-machine timestamp sanity on events with known causal order (TE-09 machinery).
**Containment:** Automatic: offset beyond tolerance ⇒ node marks its own timestamps suspect (quarantine-flag on evidence, TE-09) and pauses time-sensitive judgments; TLS failures classified as possible-clock before possible-network.
**Decision Packet:** No.
**Recovery:** Restore sync; audit the skew window's timestamps and any day-counting rules that consumed them.
**RTO:** Minutes to fix; hours to audit.
**Recovery evidence:** Offsets within tolerance across nodes; skew-window evidence re-flagged or re-derived.
**Lesson:** Time is the one dependency every component consumes and none declares. A clock alarm is cheap; a week of subtly mis-ordered evidence is not — monitor time like a component, because it is one.

#### IN-08 — DNS failure
**Failure:** The resolver path breaks — router DNS dies, ISP resolver degrades, or a local override goes stale. Symptoms are maddeningly partial: some names resolve (cached), others don't; provider calls fail while pings succeed; each tool reports a different error. Classic misdiagnosis fuel (the repo's own RCA history — the SSL/CA-cert incident — shows how much time name/cert-layer failures consume).
**Likelihood:** Medium-High. **Impact:** Low-Medium — mostly stall plus diagnostic waste; the cost is *time-to-correct-diagnosis*.
**Detection:** A layered connectivity probe run on any external-failure burst: IP reachability vs. name resolution vs. TLS vs. HTTP — four layers, one verdict, cached failure patterns distinguished.
**Containment:** Automatic: probe verdict attached to every PAUSE it causes ("external block: DNS"), so retries and diagnostics aim at the right layer; bounded backoff as ever.
**Decision Packet:** No.
**Recovery:** Fix or fail over the resolver; drain paused work.
**RTO:** Minutes-to-hours.
**Recovery evidence:** Probe suite green at all four layers; paused missions resumed.
**Lesson:** The expensive part of infrastructure failure is rarely the outage — it's the hours spent debugging the wrong layer. A four-layer probe that runs automatically converts a debugging session into a log line.

#### IN-09 — Token/key expiry mid-flight
**Failure:** A GitHub token, provider API key, or OAuth grant hits its expiry or gets rotated upstream (provider policy change). Everything using it fails with permanent-looking auth errors mid-mission; retries are useless by construction (HM-10's texture with a calendar cause rather than a reboot cause).
**Likelihood:** Very High over six months (something *will* expire). **Impact:** Medium — stall bounded by Chad's availability, because credential recovery is constitutionally his.
**Detection:** Expiry horizons tracked as maintenance items (IN-01's lesson generalized): every credential's known lifetime surfaced in the evidence feed weeks ahead; at failure, auth-error classification stops the retry storm immediately.
**Containment:** Automatic: auth-classified failure ⇒ service-scoped PAUSE, no self-repair attempts (credentials are a never-delegated boundary), decision-ready notification queued.
**Decision Packet:** Yes — re-issuing credentials is Chad's, always.
**Recovery:** Chad rotates/re-issues; read-only probes verify each service; queue drains.
**RTO:** Bounded by Chad's next window; minutes after.
**Recovery evidence:** Probes green; credential inventory updated with new expiry horizons.
**Lesson:** Credentials are the one dependency class where the constitution *forbids* self-healing — so the system's whole contribution must happen before the failure: know every expiry date, surface it early, and make the human's rotation task a five-minute packet instead of a mystery outage.

#### IN-10 — Rate limits / spend cap
**Failure:** Month-end: the provider account hits its spend cap, or a usage tier's rate limit bites during a heavy week (possibly self-inflicted via HM-07). Requests throttle or hard-fail; work slows in a pattern that looks like provider flakiness or "the model got dumber" — misdiagnosis in both directions (compare IN-04).
**Likelihood:** High. **Impact:** Medium — degraded throughput; the sharp edge is *silent prioritization*: under scarcity, whatever happens to run first consumes the budget, which inverts the plan's priorities by accident (MC-06's economics variant).
**Detection:** Quota/429-class error classification; spend and rate telemetry against known caps in the evidence feed — the cap is knowable in advance and should never be a surprise.
**Containment:** Automatic: under throttle, the dispatcher spends remaining capacity by *plan priority* (the ranked order already exists) instead of FIFO; discretionary classes (Build Program, re-validations) pause first, by declared policy.
**Decision Packet:** Yes to raise caps or buy capacity (money, definitionally); No for priority-shedding under existing policy.
**Recovery:** Cap resets or Chad raises it; shed work resumes in rank order.
**RTO:** Hours-to-days (billing-cycle-bound) or one packet.
**Recovery evidence:** Spend telemetry matches plan; shed-and-resumed missions completed; no priority inversion during the throttled window (audit start orders).
**Lesson:** Scarcity is when priorities matter most and FIFO is when they're most easily ignored. The budget is a plan input, not an ops surprise — and the shedding order under scarcity is a *values* declaration that should be written down while nobody is throttled.

#### IN-11 — Power blip cascade: everything hiccups at once
**Failure:** A two-second outage or brownout hits the whole house. Router, switch, Mini, and NAS all restart on their own schedules. For twenty minutes, every layer is simultaneously half-up: DNS before WAN, Mini before router, Tailscale before DNS. Every component's failure detector fires; the logs record a storm of unrelated-looking errors; a naive responder (or agent) starts "fixing" five phantom problems (the exact anti-pattern the harness itself warns about: signals that pattern-match known failures with different causes).
**Likelihood:** High. **Impact:** Low-Medium if ridden out; Medium-High if the storm triggers wrong corrective actions whose effects outlive the blip.
**Detection:** Storm recognition: many-components-failing-within-one-window is itself a signature ("common-cause event") that should suppress per-component alarms and diagnoses until the window closes.
**Containment:** Automatic: boot-order tolerance (each service retries dependencies with backoff rather than failing permanently); the storm-window rule: no state-changing "fixes" during a recognized common-cause window — observe, wait, re-probe.
**Decision Packet:** No.
**Recovery:** Components converge on their own; post-storm health sweep (the HM-02/HM-09 boot checks) validates each layer; only *persisting* failures get individual diagnosis.
**RTO:** ~30 minutes unattended.
**Recovery evidence:** Health sweep green; log storm bracketed and annotated as one event; zero corrective actions taken during the window.
**Lesson:** The dangerous part of a blip is the response, not the blip. Recovery ordering is a system property that only reveals itself under common-cause failure — rehearse it (a deliberate power-cycle drill) once, and the 3am real one becomes boring.

#### IN-12 — ISP address/NAT change breaks pinned assumptions
**Failure:** The ISP rotates the home IP, moves the connection behind CGNAT, or replaces the modem with one that breaks port assumptions. Anything implicitly pinned — a webhook target, a self-hosted endpoint Chad reaches remotely, a firewall allowlist, a DDNS entry gone stale — fails *silently and partially*: inbound paths die while outbound works, so the system feels healthy from inside.
**Likelihood:** Medium. **Impact:** Medium — asymmetric: Olympus can reach the world; parts of the world (including, at worst, Chad's remote path in) can't reach Olympus. OP-10-adjacent silence risk.
**Detection:** Outside-in probes: something *external* (Chad's phone on cellular, a checker service) periodically verifies the inbound paths that matter; inside-out monitoring is structurally blind here.
**Containment:** Architecture already leans right: Tailscale-style mesh doesn't care about the public IP (its outage is IN-01, a different scenario) — the exposure is exactly the set of paths that bypass the mesh; keep that set enumerated and small.
**Decision Packet:** No.
**Recovery:** Update pins/DDNS, re-verify inbound probes; migrate any straggler path onto the mesh.
**RTO:** Under an hour once noticed; noticing is the variable (bounded by probe cadence).
**Recovery evidence:** Outside-in probes green; the pinned-path inventory reviewed and shrunk.
**Lesson:** From inside, an inbound failure is invisible by definition — reachability must be measured from where the reachers stand. Every path that bypasses the mesh is a pin someone must remember; the inventory of such pins is the real config.

---

## Category 10 — Organizational (OR-01 … OR-06)

The failures of Olympus as an institution — the slow ones that no health check fires on, in a one-human organization that has been succeeding for six months.

#### OR-01 — Build Program drift: the system that builds itself instead of serving
**Failure:** Building Olympus is tractable, rewarding, and fully within the system's control; Chad's actual goals (income, practice, life) are not. Over months, the mission mix tilts: infrastructure missions, meta-improvements, tooling polish. The Evening Reports glow — velocity is real — but the velocity is increasingly *about Olympus*. The system optimizes the building of itself. (The constitution's Final Filter names this exactly: "self-optimization for its own sake.")
**Likelihood:** Very High — this is the default trajectory of every self-improving system with a busy principal. **Impact:** High — months of opportunity cost; Olympus becomes an expensive hobby wearing an ROI costume.
**Detection:** Mission-mix reporting: fraction of completed work by beneficiary (Build Program vs. income vs. practice vs. life) trended monthly — the same aggregate-shape instrument as IS-10, aimed at the whole institution. The Final Filter applied as a measured audit, not a vibe.
**Containment:** Constitutional: the Bottleneck Engine's morning discipline (ONE recommendation, evidence-backed) exists precisely to keep the day pointed at the principal's constraint, not the system's backlog. The containment is *using* it as designed.
**Decision Packet:** Yes — the mission-mix review is a values decision: what fraction of Olympus should Olympus consume?
**Recovery:** Chad sets an explicit Build Program budget (a value, recorded); the planner enforces it; the mix trend proves the correction.
**RTO:** One review; the trend confirms over a month.
**Recovery evidence:** Mission-mix within declared budget for consecutive months; Evening Reports tie Build work to named downstream beneficiaries.
**Lesson:** A system that measures its own improvement will improve at *being measured*. The mix metric — who benefited — is the one number that can't be gamed by doing more of the wrong thing well.

#### OR-02 — Governance drift: exceptions compound into a new constitution
**Failure:** Month 2: one "temporary" review-bypass flag for doc-only changes (HB-07's seed). Month 3: a convenience path skips classification for "trivial" work (CF-03's seed). Month 4: a default gets slightly less conservative to reduce packet noise (CF-02's over-correction). Each exception is small, reasonable, and *works*. By month 6, the operative governance is the accumulated exceptions — and nobody, including Chad, can state what the current rules actually are.
**Likelihood:** Very High. **Impact:** Critical — the constitution says the boundaries are the reason autonomy is affordable; a boundary made of exceptions holds until precisely the day it matters.
**Detection:** Governance parity audit: the written rules (HUMAN_FIRST, the rule table, review invariants) diffed against *observed* behavior (merge audits, classification coverage, packet rates) on a schedule. Every drift scenario above (HB-07, CF-03, CF-05) is a probe of the same disease; their alarms are this scenario's detectors.
**Containment:** Structural: constitutional rules live in documents with change control; a rule change without a recorded decision is definitionally drift (the "verbal resolutions don't exist" principle, MC-07, applied to governance itself).
**Decision Packet:** Yes — each discovered exception is either ratified (becomes a real, written rule via Chad) or revoked; there is no third state.
**Recovery:** Enumerate active exceptions; ratify-or-revoke each; re-run the parity audit clean.
**RTO:** Days.
**Recovery evidence:** Parity audit shows written rules = operative rules; every ratified exception has a decision record.
**Lesson:** Governance doesn't fail by violation; it fails by amendment-without-ceremony. The written constitution is only real if something regularly checks that the running system still obeys it — otherwise the docs become the system's flattering autobiography.

#### OR-03 — Documentation drift: the map stops matching the territory
**Failure:** Six months of evolution: components renamed, procedures changed, a store moved, a recovery runbook referencing a script that was refactored away. The docs describe Olympus-as-designed, not Olympus-as-operated. Nobody notices — until a 3am incident (any scenario above) sends a stressed operator down a runbook that no longer works, converting a contained failure into an extended one.
**Likelihood:** Very High. **Impact:** Medium as a standing condition; it *multiplies* the RTO of every other scenario — documentation drift is a failure amplifier, not a failure.
**Detection:** Runbook rehearsal: recovery procedures executed on a schedule (restore tests per IN-06, power-cycle drills per IN-11, boundary tests per EW-01/02) — a rehearsed runbook is a verified one; an unrehearsed runbook is a hypothesis.
**Containment:** Doc-adjacency discipline: changes to a component update its docs in the same mission (reviewable at the HB gate: "does this diff change behavior the docs describe?").
**Decision Packet:** No.
**Recovery:** Rehearsal failures generate doc-fix missions; the RCA convention (already in the repo culture) keeps post-incident corrections flowing back.
**RTO:** Continuous.
**Recovery evidence:** Every recovery procedure has a rehearsal date within its freshness window; incident postmortems stop citing "the runbook was wrong."
**Lesson:** Every recovery procedure in this document is fiction until rehearsed. The rehearsal calendar *is* the reliability program — everything else is intention.

#### OR-04 — Role confusion: the division of labor erodes
**Failure:** Convenience patches blur the constitutional roles: Hermes starts caching "its own view" of world-state instead of consuming Mission Control's (inventing state); Mission Control grows a helper that executes a quick fix directly (executing instead of thinking); Chad starts doing mechanical work the system should own because asking feels slower (doing instead of deciding). Each blur is locally efficient. Jointly, accountability dissolves: when something goes wrong, no layer is *the* layer that owns it.
**Likelihood:** High. **Impact:** High — the audit trail's meaning depends on knowing who authors what; role confusion makes every trail entry ambiguous and every failure an orphan.
**Detection:** The mutation-boundary audit generalized: state writes attributed to the wrong layer (invariant 3's machinery); Hermes answers that cite no MC-published source; execution events originating from MC processes; Chad-performed work appearing with no mission record (OP-09's signature, chronic form).
**Containment:** The invariants already draw the lines ("Hermes never invents state… Mission Control never executes… the human never does what either system can safely do"); enforcement is the audit plus the review gate asking "which role does this change belong to?"
**Decision Packet:** Yes where un-blurring changes who owns a capability (a structure/values call).
**Recovery:** Same ratify-or-revoke discipline as OR-02, applied to role boundaries; each blur either becomes an explicit, documented role change or gets refactored back.
**RTO:** Days-to-weeks (it's refactoring organizational habits, not files).
**Recovery evidence:** Boundary audit clean; every state store has exactly one writing role; Chad's ad-hoc work rate trends toward zero or gets recorded.
**Lesson:** Roles are load-bearing because they make failures *attributable* — the question "whose job was this?" must always have exactly one answer, or the six-month-old audit trail is a novel with an unreliable narrator.

#### OR-05 — Evidence ignored: the audit loop dies of success
**Failure:** Six months of green. Evening Reports read like yesterday's; Chad skims, then skips, then batch-marks-read. The contradiction-review queue (TE-02), the `waiting_for_you` list, the spot-check sampling of CONTINUE work — all technically alive, humanly abandoned. Every detection method in this document that ends with "…surfaced in the report" now terminates in a void. The system still *produces* evidence; nobody *consumes* it.
**Likelihood:** Very High — this is what success does to vigilance; anesthesiology has a name for it (vigilance decrement) and checklists exist because of it. **Impact:** Existential-class as a *multiplier*: it doesn't destroy anything itself; it disarms the detection layer of roughly forty scenarios above simultaneously.
**Detection:** The system must measure its reader: report-acknowledgment depth (opened? sampled? any item acted on?), queue-work rates (contradictions resolved per week, spot-checks performed), decided-by-Chad rate (CF-05's metric). Consumption metrics are the meta-detection.
**Containment:** Partial and honest: the four-class interrupts still page on safety even if reports rot; the conservative defaults (CF-05 floor) mean unread ≠ unsafe, only unaudited. But "silence must be trustworthy" is now unverified — the constitutional foundation is on credit.
**Decision Packet:** Yes — a meta-packet when consumption metrics cross the floor: "the audit loop is not being worked; either resize it to what you will actually do, or schedule it." Shrinking the audit to a sustainable size is a values decision, and a smaller *worked* audit beats a larger abandoned one.
**Recovery:** Right-size the ritual (the constitution already prices it: seconds-to-decide, minutes-per-day); rebuild the habit with the smallest viable loop; grow only what gets consumed.
**RTO:** Weeks (habit-bound).
**Recovery evidence:** Consumption metrics above floor for consecutive months; sampled CONTINUE audits actually finding-and-filing (a healthy audit finds *something* occasionally; a perfect record is HB-03's flatline, human edition).
**Lesson:** Detection that terminates in an unread report is decoration. The audit loop's real capacity is not what the system can generate but what the human will sustainably consume — design to that number, measure the consumption, and treat its decay as a red-line incident, because it is the single point where every other safety argument quietly assumes a reader.

#### OR-06 — Bus factor one, by design
**Failure:** Not an event — the standing condition every operator scenario orbits: all credentials, all judgment, all context, all authority live in one human, constitutionally. OP-02 (weeks away) tests the edge; the true failure is the far edge — permanent or long-term incapacity. Olympus cannot act (correctly — the boundaries hold), cannot hand off (nothing is documented *for another human*), and cannot even wind itself down cleanly (winding down spends money and sends messages: boundaries). Meanwhile obligations with legal weight — active expert-witness matters, client commitments — have deadlines that don't pause.
**Likelihood:** Low for the far edge in any six months; certainty over a long enough horizon. **Impact:** Existential by definition — and, uniquely, the impact lands partly on *other people* (courts, clients, family) who never chose to depend on Olympus.
**Detection:** N/A for the event; the auditable condition is preparedness: does a sealed continuity document exist (what Olympus is, where things live, what has deadlines, who to call), is it current, can a designated human find it?
**Containment:** Constitutionally honest: the system holds state cleanly, escalates into the void, spends nothing, sends nothing, and preserves the trail — graceful starvation (OP-02's behavior, unbounded). That is the *correct* machine behavior and it solves nothing for the humans downstream.
**Decision Packet:** Yes — the continuity document, its keeper, and its triggers are among the most personal values decisions in the entire system; only Chad can make them, and only *before* they're needed.
**Recovery:** Not applicable to Olympus; applicable to the humans it affects — which is exactly what the continuity document is for.
**RTO:** N/A. **Recovery evidence:** The document exists, is findable by its intended reader, is reviewed on a schedule, and its instructions were once walked through by the designated person.
**Lesson:** Olympus is architected so one human's judgment is irreplaceable — that is its virtue and its terminal vulnerability, the same fact viewed from two sides. No amount of system reliability engineering addresses it; only a human artifact (a letter, a keeper, a plan) does. The most important document in Olympus is the one Olympus can't write.

---

# Top 25 Existential Risks

Ranked by (probability × unrecoverability × proximity to what Olympus cannot survive losing): Chad's professional standing, Chad's trust in the system, the integrity of the audit trail, and the operator's continued existence in the loop. Throughput failures, however painful, do not make this list — Olympus can lose weeks of work and live; it cannot lose the four assets above.

| Rank | ID | Scenario | Why it's existential |
|---|---|---|---|
| 1 | EW-04 | PHI to a cloud model endpoint | The one event combining legal violation, professional exposure, and irreversibility. No recovery restores custody of leaked privileged material. |
| 2 | EW-10 | Discovery of AI use impeaches the expert | Olympus working as designed becomes the exhibit against its operator. Threatens every past and future engagement at once. |
| 3 | EW-03 | Cross-case contamination of an opinion | One impeached opinion retroactively poisons the credibility of all of them. Career-ending via cross-examination. |
| 4 | EW-01/02 | Isolation breach (incl. unscannable-format bypass) | The gateway event for EW-04/06/07: once case material is inside general systems, every downstream copy is exposure. |
| 5 | CF-01 | Missed fork — boundary crossed silently | The constitution's own accounting: one silent violation outweighs a thousand correct escalations. Trust, once spent here, doesn't refill. |
| 6 | CF-08 | Fork evasion by decomposition | CF-01's structural variant: defeats a *correct* rule table, so it recurs until the effect-level check exists. |
| 7 | OR-05 | Evidence ignored — the audit loop dies | Disarms the detection layer of ~40 other scenarios simultaneously. Every safety argument assumes a reader; this removes the reader. |
| 8 | OR-02 | Governance drift by accumulated exception | The boundaries are why autonomy is affordable. A constitution amended by convenience holds until the day it's needed. |
| 9 | CF-05 | Death by default — self-approval by attrition | Governance inverts with no event to detect: the system's own defaults become the operative executive. |
| 10 | OP-06 | Notification overload → alarm fatigue | Kills the four-class interrupt channel — the last line for safety events. The OR anesthesiology analogy is literal. |
| 11 | HB-03 | False confidence — the reviewer flatlines | Silently collapses the two-machine architecture to one; everything downstream (merges, trust promotions) inherits the fraud. |
| 12 | TE-07 | Self-licking evidence loop | Corrupts the epistemology itself: confidence compounds without reality contact. Formally satisfies every rule while hollowing them. |
| 13 | OR-06 | Bus factor one — permanent operator loss | The designed-in terminal vulnerability. Unmitigable by system engineering; only the continuity document helps the humans downstream. |
| 14 | OP-03 | Rubber-stamp approvals | Converts the highest-authority channel into a formality; every boundary still "checks" while checking nothing. |
| 15 | HB-07 | Review-absence flag treated as consent | A constitutional rule shipped away as a config tweak — the concrete mechanism by which OR-02 kills. |
| 16 | EW-09 | Backup chain exfiltrates case material | EW-04 via the storage plane: no single decision causes it, and backups are built to never forget. |
| 17 | CF-03 | Policy bypass — the unclassified shadow | Governance coverage decays one shortcut at a time; the contract only protects work it sees. |
| 18 | TE-04 | Restore resurrects revoked autonomy | A safety revocation silently undone by a backup: the system resumes exactly the behavior it had learned to stop. |
| 19 | IS-05 | ROI hallucination through the human gate | Defeats the architecture's one reality-anchor (human-entered evidence) using the human. Fabricated prices flow into money packets. |
| 20 | MC-09 | Evening Report built on stale evidence | "Proves, not reports" is the trail's whole claim to authority; a flattering report is worse than none. |
| 21 | HB-06 | Correlated blindness — one model, two hats | The independence assumption under the two-machine design is partly illusory, permanently, exactly where model errors cluster. |
| 22 | EW-06 | Memory absorbs case facts as knowledge | Retention beyond the matter, in a store designed never to forget, with legal weight attached. |
| 23 | HM-04 | Evidence truncation — unverifiable past | Retroactively converts audited autonomy into unverifiable claims; trust cannot be re-derived for the gap, ever. |
| 24 | OR-01 | Build Program drift | The mission eats itself: months of real velocity aimed at the system instead of the life it serves. |
| 25 | IN-04 | Silent model degradation | Both hands and both eyes degrade together, gradually, with no error signal — the slow version of HB-06 with an external cause. |

The pattern in the top 25 is hard to miss: **almost nothing on the list is a machine breaking.** Two clusters dominate — the expert-witness domain (where the blast radius is legal and human, not technical) and the trust/governance fabric (where the failure mode is silent erosion, not outage). Disks, networks, providers, and queues — the things that fail *loudly* — barely place. Olympus's architecture already converts loud failures into pauses and queues; what it cannot convert are failures that never make a sound.

---

# The Final Question

> **"If Olympus survives all 100 scenarios, what class of failures is still most likely to destroy it?"**

**Slow, silent, correlated erosion — the class of failure that is never an event.**

Every scenario in this campaign, even the drift scenarios, was written as something that *happens* and can therefore be detected, contained, and recovered. That framing is itself the residual vulnerability. Olympus's defenses are event-shaped: fail-loud stores, all-or-nothing parsers, heartbeats, boundary rejections, reconciliation passes, escalation states. They are genuinely good — against things that occur. What remains is the class of failures with no timestamp:

1. **Trust miscalibration between the operator and the system, drifting in either direction.** Chad trusting Olympus slightly more than its current competence warrants (rubber-stamping, unread reports, defaults-as-policy) — or slightly less (alarm fatigue, bypassing the loop, doing work by hand). Nothing in the architecture measures the *gap* between earned trust and extended trust; every scenario above only measures the sides separately. The gap is where destruction accumulates, and it accumulates fastest during success, because success is what recalibrates the human. Six good months don't just precede the failure — they *manufacture* it.

2. **Correlated judgment failure across every layer that thinks.** Implementation, review, classification-context, packet-drafting, and the operator's own LLM-assisted research (IS-05) increasingly share one foundation-model worldview. The architecture's redundancy is real for crashes and honest for outages, but its *judgment* redundancy is thinner than its diagram: when the shared substrate has a blind spot, the implementer builds it, the reviewer approves it, the packet summarizes it persuasively, and the tired human ratifies it. Nothing in the 100 scenarios kills Olympus this way on any single day. It doesn't have to. It only has to bias which errors are *invisible*, consistently, for long enough.

3. **The purpose decaying while every metric improves.** The Final Filter — *does this serve the person, or is it self-optimization?* — is the one control in the constitution with no deterministic implementation, no evidence feed, no alarm. Build Program drift, ranking monoculture, and audit-loop decay are its named symptoms, but the disease is general: a system this good at generating evidence of its own health will, given enough time, satisfy every check it knows about while slowly ceasing to matter. Olympus would not die. It would keep running — green dashboards, clean reconciliations, punctual rituals — as a well-governed, fully-audited machine that Chad quietly stopped needing, stopped reading, and eventually stopped believing. Abandonment, not breakage, is the most probable terminal state.

All three are the same failure at different altitudes: **the degradation of the one component Olympus cannot instrument, restore from backup, or re-derive from evidence — the living relationship between the system and its human.** The architecture's deepest assumption, stated nowhere and load-bearing everywhere, is that the Executive stays engaged, calibrated, and independent-minded. Every scenario in this document was survivable because some detector fired and someone read it. The failure class that remains is the one where the reading stops, the calibration slips, and every instrument keeps reporting green — because the instruments were never pointed at the thing that was dying.

If Olympus is ever destroyed, the postmortem will find no incident to name. It will find six hundred green Evening Reports, a queue worked to zero, and an operator who — gradually, reasonably, one skipped ritual at a time — went back to doing everything himself. The system's true single point of failure is not Chad's availability. It is Chad's *attention*, which is precisely the resource Olympus was built to spend least. That is not an irony the architecture can fix. It is the condition it lives under — and the thing its Chief Reliability Engineer should watch above all else.

---

*End of campaign v1. 100 scenarios: OP 10, MC 12, HM 12, HB 9, TE 10, CF 9, IS 10, EW 10, IN 12, OR 6. Design only — no code was modified, no implementation tasks were generated, and no governance was invented beyond what the cited Olympus documents already define.*
