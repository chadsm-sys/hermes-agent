# Olympus Recovery Matrix

**Lane 4 of the Olympus Reliability Intelligence Campaign.**
**Status:** Design-only analysis. No code, no implementation, no governance changes, no architecture redesign.
**Source of truth:** `docs/reliability/olympus-failure-injection-campaign-v1.md` (100 scenarios). Every cell below is derived from that document's Failure / Detection / Containment / Recovery / RTO / Recovery-evidence / Decision-Packet fields.

**Column key:**
- **Recovery Time** — the campaign's stated RTO.
- **Evidence Complete** — Y/N/Partial: does the campaign's *recovery evidence* field give a verifiable completion signal? (Partial = signal is an open-ended trend/habit, or acknowledges a permanent residual/unobtainable confirmation.)
- **Operator Required** — Y/N: does recovery need Chad, per the Decision Packet field and the recovery text? (Conditional "Yes only if…" cases are marked N with the condition noted in Section 3.)
- **MBP Required** — Y/N: does recovery/verification pass through the Hermes MBP review gate (re-review, merge-audit, review-quality metrics)?

---

## 1. Operator (OP-01 … OP-10)

| ID | Failure | Detection | Containment | Recovery | Recovery Time | Evidence Complete | Operator Required | MBP Required |
|---|---|---|---|---|---|---|---|---|
| OP-01 | Chad away 72+ hours | Unacked packets; queue age | Forks hold; PAUSE throttles | Chad drains queue oldest-first | One 90-min window | Y | Y | N |
| OP-02 | Chad incapacitated for weeks | Sustained silence; runway horizons | Read-only posture; spend frozen | Re-validate credentials, evidence; gradual resume | 1–2 weeks | Y | Y | N |
| OP-03 | Rubber-stamped external send approved | Approval-latency proxies; countermands | None; do-nothing default only | Chad countermands; audits recent approvals | Hours–days | Y | Y | N |
| OP-04 | Two packets answered swapped | Evening Report outcome contradiction | One-question rule; staged sends | Chad reverses both; packets re-forked | Same day–days | Y | Y | N |
| OP-05 | Post-call fatigue degrades decisions | Reversal-rate, post-call correlation | None; do-nothing stays safe | Chad authors post-call deferral rule | Immediate once ruled | Partial | Y | N |
| OP-06 | Interrupt storm; Chad mutes | Safety interrupts unacknowledged | ESCALATING holds; nothing proceeds | Purge backlog; reclassify; Chad unmutes | Window + trust days | Y | Y | N |
| OP-07 | Conversation contradicts published plan | Plan-vs-actual divergence | Contradiction escalates NEEDS_CHAD | Chad decides; plan updated via MC | Minutes once surfaced | Y | Y | N |
| OP-08 | Stale instruction erodes quality | Clustered quality regressions | None automatic; both-days rule | Chad re-scopes; re-run affected deliverables | Days | Y | Y | Y |
| OP-09 | Chad bypasses loop, hand-edits | Foreign writes; failed preconditions | Hand-edits detectable; missions PAUSE | Reconcile state; adopt or revert | Hours | Y | N | N |
| OP-10 | Notification channel silently dead | Heartbeat asymmetry; missing packet | Missions held; no self-approval | Re-credential; replay packets; round-trip test | <1 hour once noticed | Y | Y | N |

## 2. Mission Control (MC-01 … MC-12)

| ID | Failure | Detection | Containment | Recovery | Recovery Time | Evidence Complete | Operator Required | MBP Required |
|---|---|---|---|---|---|---|---|---|
| MC-01 | Torn write corrupts mission store | Load-time parse failure | Backup aside; dispatch refused | Restore snapshot; reconcile orphaned missions | 1–4 hours | Y | N | N |
| MC-02 | Ritual scheduler silently dead | Missing packet; stale timestamps | PAUSE waits; nothing self-approves | Restart scheduler; emit late-marked packets | <1 hour | Y | N | N |
| MC-03 | Duplicate dispatch runs mission twice | Duplicate mission IDs, PRs | Mission IDs; MBP catches twins | Close younger duplicate; keep elder | Minutes per duplicate | Y | N | Y |
| MC-04 | Mission dispatched into void | No execution evidence | Staleness rule flips PAUSE | Re-dispatch same mission ID | ≤1 day, then minutes | Y | N | N |
| MC-05 | WAITING mission never rechecked | Age-in-state flags | Resume plans need recheck dates | Recheck blocker; resume or close | Minutes per item | Y | N | N |
| MC-06 | Low-priority mission blocks ranked work | Rank-vs-start-time correlation | PAUSE-preemption of holder | Preempt, run ranked, resume paused | Minutes | Y | N | N |
| MC-07 | Escalation resolved verbally, never recorded | Age-in-ESCALATING metric | Wedge holds; no auto-unwedge | Fresh packet; Chad records RESOLVE | One attention window | Y | Y | N |
| MC-08 | DST shifts rituals off-window | Ack-latency shift post-transition | None needed; packets pull-consumable | Re-anchor times to Chad's schedule | Minutes | Y | N | N |
| MC-09 | Report counts reverted work | Close-time artifact re-verification | Both-days, ≥2-observation rules | Corrected report; reverse observations; demote | Next report cycle | Y | N | N |
| MC-10 | Queue growth degrades whole loop | Store size, latency trends | ONE recommendation regardless depth | Triage: archive, merge, expire reasoned | One session + packet | Y | Y | N |
| MC-11 | Malformed packet refused whole | MorningBriefError at consume | Never partially trusted; degraded flag | Fix producer; re-emit marked packet | <1 hour | Y | N | N |
| MC-12 | Restore forks store from world | Mass store-vs-world disagreement | Post-restore dispatch freeze | Reconcile ground truth; void duplicates | Half a day | Y | Y | N |

## 3. Hermes Mini (HM-01 … HM-12)

| ID | Failure | Detection | Containment | Recovery | Recovery Time | Evidence Complete | Operator Required | MBP Required |
|---|---|---|---|---|---|---|---|---|
| HM-01 | Agent crashes mid-mission | Supervisor exit; heartbeat loss | Per-mission worktrees; atomic stores | Restart; re-run from last commit | Minutes | Y | N | N |
| HM-02 | Power loss corrupts git state | Boot fsck, lock scan | Boot check quarantines repo | Clear locks; fsck; re-clone | <1 hour | Y | N | N |
| HM-03 | Disk full; writes fail | Usage threshold; log gaps | High-water stop; atomic writes | Purge caches; verify store writes | <1 hour | Y | N | N |
| HM-04 | Mission evidence rotated away | Evidence-completeness sampling | Evidence excluded from rotation | Record permanent UNKNOWN; fix retention | N/A; policy minutes | Partial | N | N |
| HM-05 | Git object corruption, delayed | Weekly scheduled fsck | Quarantine repo; PAUSE missions | Re-clone; salvage un-pushed branches | 1–2 hours | Y | N | N |
| HM-06 | Worktree metadata orphaned | Setup fails; prune scan | Setup failure PAUSEs mission | Prune; remove orphans; retry | Minutes | Y | N | N |
| HM-07 | Wedged loop burns tokens overnight | Budget metering; cost anomaly | Hard ceilings; breach PAUSEs | Inspect transcript; re-scope; resume budgeted | Minutes post-pause | Y | N | N |
| HM-08 | Test fix balloons 4,000 lines | Diff-size anomaly; scope gate | No review, no merge | Split PR; park refactor proposal | Hours | Y | N | Y |
| HM-09 | OS update reboots, environment shifts | Boot self-check manifest diff | Queue refused until check passes | Re-accept toolchain; clear prompts; replay | Minutes–days (physical) | Y | Y | N |
| HM-10 | Keychain locked post-reboot | Simultaneous auth failures everywhere | Queue PAUSEs; no self-repair | Chad unlocks; probe; resume queue | Chad's next access | Y | Y | N |
| HM-11 | Flaky hardware poisons evidence | Cross-mission host-wide correlation | Host quarantine; UNKNOWN-flag evidence | Diagnose; replace; restore; re-run flagged | Days (procurement) | Y | Y | N |
| HM-12 | Auto-updates drift toolchain silently | Scheduled manifest diffing | Pins; manifest alarm PAUSEs | Acknowledge or rollback; record event | Minutes | Y | N | N |

## 4. Hermes MBP (HB-01 … HB-09)

| ID | Failure | Detection | Containment | Recovery | Recovery Time | Evidence Complete | Operator Required | MBP Required |
|---|---|---|---|---|---|---|---|---|
| HB-01 | Reviewer asleep; queue stalls | Queue age; heartbeat absent | No review, no merge | Wake MBP; drain oldest-first | Lid-open bound + hours | Y | Y | Y |
| HB-02 | Reviewer off-Tailnet; reviews flap | Unconcluded review sessions | Transactional verdicts; gate PAUSEs | Reconnect; void orphans; re-review | Connectivity-bound + hours | Y | N | Y |
| HB-03 | Reviewer approves everything (LGTM) | Finding-rate flatline; canaries | Merges pause; approvals suspect | Fix reviewer; re-review window; re-derive | Days | Y | Y | Y |
| HB-04 | Missed defect festers weeks | Downstream invariant checks | Stores fail loudly downstream | Revert; restore data; checklist update | Hours; day for data | Y | N | Y |
| HB-05 | Reviewer context predates contracts | CI invariant audits | Runtime boundary enforcement | Refresh context; re-review window | A day | Y | N | Y |
| HB-06 | Shared model, correlated blindness | Escaped-defect clustering; spot-checks | Deterministic checks, uncorrelated layer | None; measure and weight sampling | N/A (continuous) | Partial | N | N |
| HB-07 | Auto-proceed flag bypasses review | Merge without verdict alarm | Merge-audit reveals flag | Remove flag; re-review merges; RCA | Days | Y | Y | Y |
| HB-08 | Review runs 90 minutes | Duration trend; green heartbeats | Transactional verdicts; queue buffers | Clean pressure; re-baseline durations | An hour | Y | N | Y |
| HB-09 | Reviewer absorbs implementer narrative | Rationale-quoting verdicts; canaries | Fresh per-review contexts | Purge state; re-run suspect approvals | Hours | Y | N | Y |

## 5. Trust Engine (TE-01 … TE-10)

| ID | Failure | Detection | Containment | Recovery | Recovery Time | Evidence Complete | Operator Required | MBP Required |
|---|---|---|---|---|---|---|---|---|
| TE-01 | Double-counted evidence promotes claim | Provenance dedup audit | ≥2-days rule; ingest dedup | Demote; void duplicate; re-promote later | Minutes per claim | Y | N | N |
| TE-02 | Bad ingest benches core claim | Contradiction-review queue | Blocks promotion; nothing deleted | Adjudicate; void ingest; restore status | Minutes per contradiction | Y | N | N |
| TE-03 | Trust ledger corrupted | Open-time integrity check | Floor trust; maximal escalation | Restore; re-derive from evidence trail | Hours–one day | Y | N | N |
| TE-04 | Stale restore resurrects revoked autonomy | Gap-window demotion diff | Trust floor until reconciled | Replay gap events; verify revocations | Half a day | Y | Y | N |
| TE-05 | Replayed evidence inflates counts | Uniqueness checks; promotion anomaly | Allowlist; idempotent recording | Void replays; re-derive promotions | Hours | Y | N | N |
| TE-06 | Old promotions outlive changed world | Evidence-age audit | Stale claims hedged, dated | Canary re-validation; re-date or demote | Ongoing; per-claim minutes | Partial | N | N |
| TE-07 | System's outputs become own evidence | Provenance-type audit | Reality-terminated provenance enforced | Void circular; re-derive; issue corrections | A day | Y | N | N |
| TE-08 | Trust bleeds across domains | Scope audit citing-vs-evidence | New-category ⇒ NEEDS_CHAD backstop | Narrow scope; reliant missions reclassify | Hours | Y | Y | N |
| TE-09 | Clock skew corrupts day-counting | Non-monotonic causal timestamps | Quarantine-flag suspect observations | Fix sync; re-derive skewed promotions | <1 hour + audit hours | Y | N | N |
| TE-10 | Promotions never persist; oscillation | Read-after-write; restart diff | Fail-loud; unpersisted ineffective | Fix persistence; replay trust events | Hours | Y | N | N |

## 6. Continue-Until-Fork (CF-01 … CF-09)

| ID | Failure | Detection | Containment | Recovery | Recovery Time | Evidence Complete | Operator Required | MBP Required |
|---|---|---|---|---|---|---|---|---|
| CF-01 | Unrecognized fork crossed at CONTINUE | After-the-fact audit only | Default-under-uncertainty rules | Chad remediates externally; authors rule | Hours–days (damage-bound) | Y | Y | N |
| CF-02 | Routine work spams packets | Packet rate; approval entropy | Excess pools; interrupts capped | Chad relaxes rules; reclassify pooled | Days | Y | Y | N |
| CF-03 | Execution path skips classification | Coverage audit finds unclassified | Entrypoints accept classified only | Reroute; retro-classify; escalate forks | Hours; day audit | Y | N | N |
| CF-04 | One fork, two contradictory answers | Packet-similarity; answer contradiction | Same-subject packets serialize | Chad picks governing answer; remediate | Window + remediation | Y | Y | N |
| CF-05 | Defaults become operative policy | Default-execution rate trend | Defaults always conservative branch | Chad delegates explicitly or reclaims | Days | Y | Y | N |
| CF-06 | Packet lost before delivery | Emitted-unacknowledged age alarm | Mission holds regardless delivery | Re-emit; verify round-trip | ≤1 day + minutes | Y | N | N |
| CF-07 | Answer recorded; mission never resumes | Answered-but-holding audit | Idempotent re-drivable answers | Re-apply answers; verify transitions | Hours + minutes | Y | N | N |
| CF-08 | Decomposed steps evade fork detection | Effect-level egress classification | Last-hop re-classification | As CF-01 plus composite audit | Hours–days | Y | Y | N |
| CF-09 | Brief filter hides PAUSE items | Conservation check state-vs-briefs | State kept; nothing expires | Fix briefs; triage backlog session | A day | Y | N | N |

## 7. Income Scout (IS-01 … IS-10)

| ID | Failure | Detection | Containment | Recovery | Recovery Time | Evidence Complete | Operator Required | MBP Required |
|---|---|---|---|---|---|---|---|---|
| IS-01 | Fabricated economics tops ranking | Source priors; sanity flags | Never chases; provenance attached | Fail validation; expire; adjust priors | Minutes once questioned | Y | Y | N |
| IS-02 | Reworded duplicate splits opportunity | Lower-threshold advisory sweep | Ingest dedup flag mode | Merge to elder with provenance | Minutes per pair | Y | N | N |
| IS-03 | One source floods ranking | Source-concentration metric | Volume buys presence only | Bulk-expire; Chad adjusts forwarding habit | One session | Y | Y | N |
| IS-04 | Validated opportunity silently obsolete | Evidence-age receipts; staleness bands | Re-validation flag; expiry transition | Chad refreshes evidence; expire if closed | Days (Chad-hours-bound) | Y | Y | N |
| IS-05 | LLM fabrications entered as evidence | Citation checks; pursuit-time reality | Three gates; honest prices | Mark contradicted; re-derive; RCA habit | Detection-bound + hours | Y | Y | N |
| IS-06 | Unit typo inflates score 12× | Plausibility bands; visible receipts | Flag-for-review net | Correct field; deterministic re-score | Minutes | Y | N | N |
| IS-07 | Hand edit breaks store invariants | Load-time semantic validation | Corrupt-backup; atomic writes | Restore snapshot; re-apply via CLI | <1 hour | Y | N | N |
| IS-08 | Processed inbox files replayed | Fingerprint reject-count spike | Fingerprints reject; flag quarantines | Quarantine; diff; void resurrections | Hours | Y | N | N |
| IS-09 | Rejected opportunity resurrects active | Terminal-state-history audit | Terminal states sticky, reasoned | Re-terminate with original reason | Minutes per item | Y | N | N |
| IS-10 | Fixed weights accrete one strategy | Portfolio-shape reporting | Weights are Chad's values | Chad revises weights; rankings shift | One review session | Partial | Y | N |

## 8. Expert Witness (EW-01 … EW-10)

| ID | Failure | Detection | Containment | Recovery | Recovery Time | Evidence Complete | Operator Required | MBP Required |
|---|---|---|---|---|---|---|---|---|
| EW-01 | Case document in general inbox | Forbidden-marker boundary scan | Boundary rejection; quarantine | Enumerate reach; purge copies; document | Hours; days if past | Y | Y | N |
| EW-02 | Unscannable PHI passes boundary | Default-deny opaque; OCR sweeps | Default-deny unscannable content | As EW-01; format reject-listed | Hours; days if past | Y | Y | N |
| EW-03 | Case B facts infect Case A | Per-assertion provenance check | One matter, one context | Re-derive clean; withdraw unsupported assertions | Days per work product | Y | Y | N |
| EW-04 | PHI sent to cloud endpoint | Egress audit; routing diffs | Per-workspace endpoint pin | Freeze; scope leak; deletions; counsel | Minutes freeze; weeks–months legal | Partial | Y | N |
| EW-05 | Case task dispatched as general | Dispatch-time marker check | Dispatch bounce to NEEDS_CHAD | Purge/redact logs; re-run isolated | Hours–days | Y | Y | N |
| EW-06 | Case facts persist as knowledge | Claim-provenance audit | Per-matter or disabled memory | Purge claims; verify no citations | A day | Y | Y | N |
| EW-07 | Case copies outlive protective order | Recorded matter-close sweep | Enumerable per-matter locations | Destroy; document; counsel on disclosure | Hours; long reputational tail | Y | Y | N |
| EW-08 | Party names leak via metadata | Marker scan on metadata | Opaque codenames at intake | Scrub reachable; accept permanent residual | Hours; residual permanent | Partial | N | N |
| EW-09 | Backup chain exfiltrates case store | Custody-chain enumeration audit | Excluded volumes; approved custody | Break chain; purge cloud; rotate | Days (provider-dependent) | Partial | Y | N |
| EW-10 | Deposition subpoenas Olympus's process | N/A — adversarial audit | Pre-decided honest methodology | Produce honestly; counsel; methodology discipline | Per-matter; reputation years | Partial | Y | N |

## 9. Infrastructure (IN-01 … IN-12)

| ID | Failure | Detection | Containment | Recovery | Recovery Time | Evidence Complete | Operator Required | MBP Required |
|---|---|---|---|---|---|---|---|---|
| IN-01 | Tailnet drops; key expires | Inter-node heartbeat; expiry horizon | Local-only degradation; queues buffer | Re-auth node or outage ends | Minutes–hours | Y | N | N |
| IN-02 | GitHub outage stalls coordination | Error classification; provider status | Bounded backoff; external-block PAUSE | Replay pushes; dedup ambiguous PRs | Provider-bound + minutes | Y | N | N |
| IN-03 | Provider outage stops all cognition | Provider-error classification | Clean PAUSE; deterministic spine runs | Resume paused, throttled burst | Provider-bound | Y | N | N |
| IN-04 | Silent model revision degrades quality | Outcome baselines; canary diffs | Deterministic checks hold floor | Canary confirm; pin/switch; re-validate trust | Days (detection-bound) | Y | N | Y |
| IN-05 | Home internet out; island | Loud locally; Chad-side silence | Local continues; external queues | Reconnect; drain; late-marked rituals | ISP-bound | Y | N | N |
| IN-06 | Mini SSD dies entirely | Loud and immediate | Push discipline; tested backups | Replace; rebuild; restore; full reconciliation | 1–3 days (procurement) | Y | Y | N |
| IN-07 | Clock drift scatters everything timed | NTP offset monitoring | Timestamps self-suspect; pause time-sensitive | Restore sync; audit skew window | Minutes + audit hours | Y | N | N |
| IN-08 | Resolver breaks; partial failures | Four-layer connectivity probe | Probe-attributed PAUSE | Fix/failover resolver; drain paused | Minutes–hours | Y | N | N |
| IN-09 | Credential expires mid-flight | Expiry horizons; auth classification | Service-scoped PAUSE; no self-repair | Chad rotates; probes verify; drain | Chad's next window | Y | Y | N |
| IN-10 | Spend cap throttles work | Quota classification; spend telemetry | Shed by plan priority | Cap resets or Chad raises | Hours–days or packet | Y | N | N |
| IN-11 | House-wide blip; error storm | Common-cause storm recognition | No fixes during window | Converge; post-storm health sweep | ~30 minutes unattended | Y | N | N |
| IN-12 | IP change kills inbound silently | Outside-in external probes | Mesh unaffected; pins enumerated | Update pins; migrate onto mesh | <1 hour once noticed | Y | N | N |

## 10. Organizational (OR-01 … OR-06)

| ID | Failure | Detection | Containment | Recovery | Recovery Time | Evidence Complete | Operator Required | MBP Required |
|---|---|---|---|---|---|---|---|---|
| OR-01 | Mission mix tilts self-building | Beneficiary mission-mix trend | Bottleneck Engine ONE recommendation | Chad sets budget; planner enforces | One review; month confirms | Partial | Y | N |
| OR-02 | Exceptions become operative constitution | Written-vs-observed parity audit | Change control on rules | Chad ratifies or revokes each | Days | Y | Y | N |
| OR-03 | Docs diverge from operations | Scheduled runbook rehearsals | Doc-adjacency at review gate | Rehearsal failures spawn doc-fix missions | Continuous | Partial | N | Y |
| OR-04 | Constitutional roles blur | Wrong-layer write attribution | Invariants; review asks role | Ratify role changes or refactor back | Days–weeks | Y | Y | Y |
| OR-05 | Chad stops consuming evidence | Consumption metrics on reader | Interrupts still page; conservative defaults | Right-size ritual; rebuild habit | Weeks (habit-bound) | Partial | Y | N |
| OR-06 | Permanent operator loss | N/A; audit preparedness | Graceful starvation; trail preserved | N/A; continuity document for humans | N/A | Partial | Y | N |

---

# Highlight 1 — Slow recoveries (RTO ≥ 1 day)

23 scenarios have a stated RTO at or above one day, ranked slowest first. **Irreducible** = bound by procurement, legal process, provider action, operator health, or human habit — cannot be shortened inside the fixed architecture. **Process-bound** = bound by audit/re-review/re-derivation work — improvable within the existing architecture (better baselines, cadence, ceremony).

| Rank | ID | RTO | Bound by | Class |
|---|---|---|---|---|
| 1 | EW-10 | Per-matter; reputation recovery in **years** | Legal/reputation | Irreducible |
| 2 | EW-04 | Freeze in minutes; legal aftermath **weeks–months** | Legal/provider | Irreducible |
| 3 | OP-02 | **1–2 weeks** of gradual resumption | Operator health | Irreducible |
| 4 | OR-05 | **Weeks** (habit-bound) | Human habit | Irreducible |
| 5 | OR-04 | **Days–weeks** ("refactoring organizational habits, not files") | Habit + refactor | Mostly irreducible (habit); audit part improvable |
| 6 | OR-01 | One review; trend confirms over a **month** | Values decision + trend confirmation | Irreducible (habit/trend) |
| 7 | IN-06 | **1–3 days** | Procurement | Irreducible (hardware); reconciliation part improvable |
| 8 | HM-11 | **Days** | Procurement | Irreducible |
| 9 | EW-09 | **Days** | Provider deletion mechanisms | Irreducible (third-party) |
| 10 | EW-03 | **Days per work product** | Professional re-derivation | Partly improvable (citation-per-assertion discipline shrinks it) |
| 11 | IS-04 | **Days** (evidence is human-entered) | Chad-hours | Irreducible (human-entry rule is constitutional) |
| 12 | IN-04 | **Days** (detection is the long pole) | Detection lag | Process-bound (canary cadence) |
| 13 | HB-03 | **Days** | Re-review of suspect window | Process-bound |
| 14 | HB-07 | **Days** | Re-review + RCA | Process-bound |
| 15 | OR-02 | **Days** | Enumerate + ratify/revoke ceremony | Process-bound |
| 16 | CF-02 | **Days** (needs trend data) | Trend accumulation | Process-bound |
| 17 | CF-05 | **Days** | Trend + explicit delegation decision | Process-bound (metric exists; decision is Chad's) |
| 18 | OP-08 | **Days** (re-work bound) | Re-running deliverables | Process-bound (instruction expiry dates would prevent) |
| 19 | TE-07 | **A day** | Provenance audit + re-derivation | Process-bound |
| 20 | HB-05 | **A day** | Context refresh + re-review window | Process-bound |
| 21 | CF-09 | **A day** | Brief fix + triage session | Process-bound |
| 22 | TE-03 | Hours–**a day** (full re-derivation) | Ledger re-derivation | Process-bound |
| 23 | HB-04 | Hours; data reconciliation up to **a day** | Data reconciliation | Process-bound |

**Conditional slow tails** (worst case ≥ 1 day, typical case shorter): OP-03, OP-04 (days if the Evening Report misses it), CF-01, CF-08 (damage-bound), EW-01, EW-02, EW-05 (days if material got past the boundary), HM-09 (days if a GUI prompt awaits physical access), IN-05 (ISP-bound), IN-10 (billing-cycle-bound).

**Pattern:** the slowest six recoveries are all human-bound (reputation, law, health, habit), not machine-bound. Everything the architecture can itself speed up already sits at a day or less; the ≥1-week tail is entirely outside the system's reach.

# Highlight 2 — Irrecoverable failures

11 scenarios involve something permanently lost, or recovery the campaign marks N/A. What exactly is irrecoverable:

**Recovery N/A or total loss (6):**
- **HM-04** — the lost evidence spans themselves: mission transcripts/trajectories dropped by rotation. "The lost evidence is unrecoverable — record the gap honestly as a permanent UNKNOWN span." Past CONTINUE work is retroactively unverifiable; trust for the gap cannot be re-derived, ever.
- **HB-06** — "not recoverable as an event": the correlated blind spot between same-model implementer and reviewer is a standing property, only measurable and sampled, never removed within the fixed architecture. RTO: N/A (continuous).
- **EW-04** — custody of leaked PHI/privileged material. Once content enters a third party's retention pipeline, "no recovery restores custody" (Top-25 #1); provider deletion confirmations only "where obtainable."
- **EW-08** — metadata residue: party names in git history and backups. "Full scrubbing impractical… residual risk permanent."
- **EW-09** — case copies on third-party cloud/backup servers; backups "are designed to persist" and third-party deletion is not provable.
- **OR-06** — the operator himself. "Recovery: not applicable to Olympus"; RTO N/A. All judgment, credentials, and authority are lost with him; only the pre-written continuity document helps the humans downstream.

**Permanent intangible loss despite a defined recovery path (5):**
- **CF-01** — the trust spent by a silent boundary violation: "one silent boundary violation costs more trust than a thousand correct escalations earn"; the external effect is remediable, the trust withdrawal is not fully refillable.
- **EW-03** — a delivered contaminated opinion: a corrected/withdrawn opinion is permanent professional damage, and "every past opinion becomes suspect" once one is impeached.
- **EW-07** — the protective-order violation itself: documents can be destroyed late, but the violation occurred; sanctions exposure and "the reputational tail is long."
- **EW-10** — the expert's reputation and the opinion's weight: "expect the opinion's weight to suffer… reputation recovery is measured in years"; transcripts already produced cannot be unproduced.
- **IN-06** — the push-gap and backup-gap: un-pushed work and store state since last backup either re-run or "explicitly written off with reasons" — the written-off portion is permanently lost (same class as HM-02's "the only unrecoverable loss is work that was never pushed").

**Pattern:** every full irrecoverable is either *evidence/custody* (HM-04, EW-04, EW-08, EW-09) or *a human property* (HB-06's model blindness, OR-06's operator). Nothing mechanical is on the list — the architecture can rebuild anything except what it never recorded, what left its custody, and its human.

# Highlight 3 — Chad-only recoveries (Operator Required = Y)

**46 of 100 scenarios** need Chad in the recovery path. Grouped by why:

**Values / rules / priorities authorship (20)** — the machine applies values, it does not author them:
OP-05 (post-call rule), OP-07 (which instruction governs), OP-08 (re-scope instruction), MC-07 (RESOLVE with reason), MC-10 (bulk-archive is un-planning work), MC-12 (accepting reconciled history), TE-04 (rewriting trust state), TE-08 (scope is granted authority), CF-01 (author missed rule + remediate), CF-02 (rule relaxations), CF-04 (governing answer), CF-05 (explicit delegation or reclaim), CF-08 (rule + remediation), IS-10 (scoring weights), OR-01 (Build Program budget), OR-02 (ratify/revoke each exception), OR-04 (role-ownership changes), HB-03 (how far back to distrust the audit trail), HB-07 (disposition of unreviewed merges), OR-06 (continuity document decisions).

**Legal / professional judgment (9)** — the expert-witness domain, entirely Chad's (with counsel):
EW-01, EW-02, EW-03, EW-04, EW-05, EW-06, EW-07, EW-09, EW-10.

**Attention / habit / relationship repair (10)** — only the human can drain his queue, mend his habits, or repair human relationships:
OP-01 (drain queue), OP-02 (return + gradual resumption), OP-03 (human-to-human repair of a bad send), OP-04 (reverse external commitments), OP-06 (unmute + re-earn channel trust), IS-01 (human-entered failing evidence), IS-03 (forwarding habit / relationship call), IS-04 (human-entered re-validation), IS-05 (entry-habit RCA), OR-05 (rebuild the reading habit).

**Credentials (3)** — a never-delegated boundary; the system "waits loudly":
OP-10 (re-credential notification channel), HM-10 (keychain unlock/re-provision), IN-09 (rotate expired tokens/keys).

**Physical presence (2)** — a human finger on a physical screen:
HM-09 (GUI security prompts after OS update), HB-01 (lid-open on the daily-carry MBP).

**Money / procurement (2):**
HM-11 (replacement hardware), IN-06 (replacement machine + gap adjudication).

*(Conditional cases marked N in the matrix but Chad-required in their worse branch: IN-01/IN-10/IN-03 (credential re-auth / raising caps / failover spend), TE-05 (adversarial variant), HM-03 (deleting non-regenerables), CF-03 (bypassed boundary work), MC-01 (backups also bad), IS-07/IS-09 (judgment reconstruction / revival), EW-08 (professional-duty analysis).)*

**Concentration risk.** This is the operator-dependency load: **46% of all recovery paths terminate in the same single human** — and OP-01/OP-02 are precisely the scenarios where that human is unavailable. Recovery paths that require the operator fail exactly when the operator *is* the failure. The campaign's own answer is that the architecture never converts operator absence into unsafe action — everything Chad-bound degrades to a clean, queued hold (OP-01: "the queued packets *are* the containment"; OP-02: graceful starvation) — so unavailability costs throughput, not safety. Three residues that queuing does not cover: (1) deadline-bound obligations (OP-02: expert-witness deadlines "may be missed with professional consequences" — the world does not PAUSE); (2) the *degraded*-operator variants (OP-03, OP-05): a present-but-impaired Chad executes his 46 recovery roles with the impaired judgment that caused the failure — worse than absence, because holds release; (3) OR-06, where the recovery load has no one to land on at all — which is why the continuity document is the only mitigation the campaign offers.

# Highlight 4 — MBP verification points

**14 scenarios** recover or verify through the Hermes MBP review gate:

- **Non-HB scenarios verified at the gate (6):** OP-08 (re-run deliverables must "pass review at expected quality"), MC-03 (twin PRs caught at review before merge), HM-08 (scope gate; minimal PR merged via review), IN-04 (finding-rates recovering is cited recovery evidence), OR-03 (doc-adjacency enforced at the HB gate; doc-fix missions merge through it), OR-04 (review asks "which role does this change belong to?").
- **HB scenarios whose own recovery is MBP-verified (8):** HB-01, HB-02, HB-03, HB-04, HB-05, HB-07, HB-08, HB-09.

**Circularity risk.** 8 of the 14 MBP-verified recoveries are recoveries *of the MBP itself* (HB-01…HB-09 minus HB-06): the failed component is the verification instrument for its own repair. HB-03 is the sharpest case — a flatlined reviewer would happily "verify" its own unfixed state — and IN-04 shares it: if the model degraded both implementer and reviewer, "finding-rates recover" is exactly the signal the degraded reviewer can fake. The remaining 6 non-HB rows are also unverifiable *during* any HB-01..09 event, but degrade safely: no review ⇒ no merge, so their verification is delayed by the buffer, never falsified.

**What the campaign says covers the circularity — the uncorrelated layer:**
- **Canary defects** (HB-03, HB-09, IN-04): known-bad changes injected periodically make reviewer aliveness an affirmative test — "a reviewer is only alive if it can be observed rejecting things"; canaries "measure the model rather than the weather."
- **Deterministic non-model checks** (HB-05, HB-06, IN-04): tests, invariant audits, schema validation, mutation-boundary audits — "the only layer whose failures don't correlate with the model's."
- **Deterministic merge-audit invariant** (HB-07): every merge must reference a verdict; a page-level alarm needing no model judgment.
- **Transactional verdicts + duration/queue-age/heartbeat metrics** (HB-01, HB-02, HB-08): mechanical signals independent of review content.
- **Chad's spot-checks** (HB-06): "the only truly independent reviewer in the architecture" — which routes the last line of MBP verification back to the operator, and therefore back into Highlight 3's concentration risk.

---

# Summary counts

| Dimension | Count | Members (abbrev.) |
|---|---|---|
| Slow (RTO ≥ 1 day, stated) | **23** (+10 conditional worst-case) | EW-10, EW-04, OP-02, OR-05, OR-04, OR-01, IN-06, HM-11, EW-09, EW-03, IS-04, IN-04, HB-03, HB-07, OR-02, CF-02, CF-05, OP-08, TE-07, HB-05, CF-09, TE-03, HB-04 |
| Irrecoverable (full or partial) | **11** (6 full/N-A + 5 partial) | HM-04, HB-06, EW-04, EW-08, EW-09, OR-06 / CF-01, EW-03, EW-07, EW-10, IN-06 |
| Chad-only (Operator Required = Y) | **46** | see Highlight 3 |
| MBP-verified (MBP Required = Y) | **14** | OP-08, MC-03, HM-08, HB-01–05, HB-07–09, IN-04, OR-03, OR-04 |
| Evidence Complete | **87 Y / 13 Partial / 0 N** | Partial: OP-05, HM-04, HB-06, TE-06, IS-10, EW-04, EW-08, EW-09, EW-10, OR-01, OR-03, OR-05, OR-06 |

**Overlaps:**
- Slow ∩ Chad-only: **17** of 23 — slow recoveries are overwhelmingly operator-bound (all 23 minus IN-04, TE-07, HB-05, CF-09, TE-03, HB-04).
- Irrecoverable ∩ Chad-only: **8** of 11 (all except HM-04, HB-06, EW-08 — the three where nothing anyone does helps).
- Slow ∩ Irrecoverable: **5** (EW-10, EW-04, EW-03, EW-09, IN-06).
- MBP ∩ Slow: **7** (OP-08, IN-04, HB-03, HB-04, HB-05, HB-07, OR-04).
- MBP ∩ Chad-only: **5** (OP-08, HB-01, HB-03, HB-07, OR-04); triple overlap (slow + Chad + MBP): **4** (OP-08, HB-03, HB-07, OR-04).

**Reading:** the machine-recoverable half of the matrix (54 scenarios) is fast, self-verifying, and evidence-complete. Nearly everything slow, everything irrecoverable, and the final verification layer for the reviewer itself all converge on the same component — the operator — which is the campaign's own closing conclusion restated as arithmetic.

*Lane 4 deliverable. 100 rows verified: OP 10, MC 12, HM 12, HB 9, TE 10, CF 9, IS 10, EW 10, IN 12, OR 6.*
