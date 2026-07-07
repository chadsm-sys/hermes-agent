# Implementation Integration Matrix — Reliability Wins × Build Program

**Olympus Reliability Integration Program.** The Reliability Intelligence Campaign and Parent Synthesis are accepted; the Build Program is authoritative. This document attaches each of the Top 10 Reliability Wins (`TOP_10_RELIABILITY_WINS.md`, severity-corrected per the Parent Synthesis §3.1/§4) to the **existing** Build Program mission ladder (`BUILD_PROGRAM_RISK_MAPPING.md` §0 — Missions 1–21 complete, Missions 22–25 remaining/DOCUMENTED).

**Rules applied throughout:** no new missions; acceptance criteria over milestones; sequencing preserved. Every win lands in one of two ways:
- **ABSORB** — the win becomes acceptance criteria on one of the four remaining missions (22–25), because the mission's own seam is where the win's mechanism belongs.
- **RETROFIT** — the win completes the definition-of-done of an already-shipped mission's artifact (the artifact exists; the win hardens it). A retrofit is *not* a new mission: it is work executed against the owning mission's original scope and closed with that mission's receipts.

**Mission-number caveat (inherited from Lane 5):** M22–M25 and M19–M21 are DOCUMENTED; M1–M18 numbering is INFERRED. Retrofit targets below name the **artifact** first and the inferred rung second — if Chad's canonical ladder numbers differ, the artifact names govern.

---

## Summary matrix

| Win (synthesis priority order) | Attach mode | Build Program mission(s) | Eng. | Operator | MBP verify |
|---|---|---|---|---|---|
| 1. EW egress pin + egress log | ABSORB | **M22** (boundary-enforcement scope) | S | ~10 min once | Yes |
| 2. Default-deny boundary + marker/metadata sweeps | ABSORB | **M22** (its own EW-rejection deliverable) | M | ~5 min/wk | Yes |
| 3. Conservation audit | ABSORB + retrofit | **M23** (rituals live) + M7/M18 queryability retrofits | L | ~5 min/wk | Yes |
| 4. Attention instrumentation | ABSORB | **M25** (LeverageStore) + M12 event retrofit | S–M | ~2 min/day | Yes |
| 5. Canary program | ABSORB | **M24** (observation recording) + M22 (boundary live-fire) | M | ~5 min/wk | Yes (it verifies MBP) |
| 6. Horizon ledger | ABSORB + retrofit | **M23** (Morning Packet surfacing) + M11 recorder retrofit | S–M | ~3 min/day in-ritual | No |
| 7. Event identity + reality-terminated provenance | ABSORB | **M22** and **M24** (their own seams) + M11 retrofit | M | none | Yes |
| 8. Effect-level classification | RETROFIT | **M7** artifact (escalation classifier) | M | one rule-review packet | Yes |
| 9. Restore-reconciliation discipline | RETROFIT | **M18** artifact (MissionStore) + M16 artifact (memorygraph) | M | packet per restore (rare) | Yes |
| 10. Boot-as-deployment | ABSORB | **M23** (wheel/packaging deliverable) | M | none steady-state | Yes |

Net effect on the Build Program: **zero new missions, zero resequencing.** Missions 22–25 gain acceptance criteria; four completed artifacts (M7 classifier, M11 recorder, M16 memorygraph, M18 MissionStore) gain retrofit criteria executed under their original scope.

---

## Win 1 — Expert-Witness Egress Pin + Egress Log

*(Synthesis priority 1; Lane 1 Win 8; covers EW-04 — existential #1.)*

- **Build Program mission(s) affected:** **M22** (Wiring 1: Opportunity Scout → MC inbox feed). M22 already owns the campaign-era boundary rule "expert-witness sources rejected at the boundary"; the egress pin is the same isolation invariant (M21 contract invariant 6) enforced on the *outbound* side. M22 is the first remaining mission that touches EW-boundary machinery, and the win is Small — it rides M22's boundary-hardening work rather than waiting for a rung that will never own it better.
- **Acceptance criteria to add to M22:**
  1. Expert-witness workspaces resolve model endpoints from a workspace-scoped approved list; a request to any non-approved endpoint from an EW context fails closed.
  2. Every model request from an EW workspace writes one egress-log line (timestamp, endpoint, workspace, request class — never content).
  3. A test from inside an EW workspace proves both: approved endpoint succeeds, non-approved endpoint is refused and logged.
- **Files/components likely affected:** provider routing configuration on the Mini (hermes-agent provider/model-routing layer, e.g. `providers/` + per-workspace config); EW workspace definition; a small egress-log appender.
- **Estimated engineering effort:** **S** — a pin plus a log line; the smallest item on the list.
- **Estimated operator effort:** ~10 minutes once: Chad approves the endpoint allowlist (a credentials/values call — this is his by constitution).
- **MBP verification required:** **Yes** — review verifies the pin is workspace-scoped (not a global default, per the campaign's EW-04 lesson) and that the refusal path fails closed.
- **Rollback strategy:** remove the workspace pin config (one revert); the egress log is append-only and harmless to leave. Rollback restores pre-win behavior exactly; nothing else depends on it.
- **Evidence proving completion:** the passing in-workspace refusal test recorded in the mission transcript; the first week of egress-log lines showing only approved endpoints; Chad's allowlist-approval packet resolved in the decision log.

## Win 2 — Default-Deny Boundary + Marker/Metadata Sweeps

*(Synthesis priority 2; Lane 1 Win 7; covers EW-01/02/05/06/07/08.)*

- **Build Program mission(s) affected:** **M22.** The marker-rejection boundary is literally in M22's documented scope ("expert-witness sources rejected at the boundary — existing MC machinery"). This win upgrades that deliverable from "scan text" to "default-deny," and extends the same scan to three more surfaces the campaign names.
- **Acceptance criteria to add to M22:**
  1. Content the marker scanner cannot read (image PDFs, archives, unknown encodings) is **rejected as opaque**, not passed as clean (EW-02).
  2. The marker check runs at **dispatch time** on mission content, not only at document ingestion (EW-05) — a marker-positive mission bounces to NEEDS_CHAD.
  3. A scheduled health mission sweeps general stores/logs (including OCR of image content) and **metadata surfaces** — commit messages, mission titles, report text, filenames — for forbidden markers (EW-06/07/08); result is one Evening Report line.
  4. Boundary rejection events are logged and counted (a rejection is a save, per the campaign).
- **Files/components likely affected:** the MC inbox-boundary validator M22 builds; the dispatch path (mission-content check hook); one scheduled health mission on the Mini; marker-pattern definitions shared by all three.
- **Estimated engineering effort:** **M** — one scanner, four call sites, one scheduled sweep.
- **Estimated operator effort:** ~5 min/week reading the sweep line; occasional false-positive adjudication (a bounced mission packet).
- **MBP verification required:** **Yes** — review must verify default-deny semantics (the "I couldn't check it ⇒ reject" branch) with test documents in each opaque format.
- **Rollback strategy:** each surface is independently disableable (ingestion check is M22-core and never rolls back; dispatch hook, metadata sweep, and OCR sweep are individually revertible flags). Rollback of the extensions restores M22's documented baseline, never less.
- **Evidence proving completion:** boundary test-document suite (text, image PDF, archive, bad encoding) all rejected, in the mission transcript; first clean sweep line in an Evening Report; a dispatch-time bounce demonstrated with a synthetic marker-positive mission.

## Win 3 — Conservation Audit

*(Synthesis priority 3; Lane 1 Win 1; covers HB-07, CF-03/07/09, MC-09, OP-09, HM-04, OR-02/04 and partials.)*

- **Build Program mission(s) affected:** **M23** (Wiring 2: MorningBrief/EveningReport adapters + wheel inclusion) as the absorber — the audit's output is an Evening Report line and its conservation subjects (PAUSE items vs. briefs, close-of-books re-verification) only become live when M23 makes the rituals live. **Retrofits:** M7 artifact (classification events must be queryable — they exist; expose a count/join interface) and M18 artifact (MissionStore state must be queryable by the audit read-only).
- **Acceptance criteria to add to M23:**
  1. A scheduled audit pass evaluates the campaign's ~10 books-balance invariants: merge ⇔ review verdict (HB-07); executed work ⇔ classification event (CF-03); live PAUSE set ⇔ PAUSE items surfaced in recent briefs (CF-09); answered packet ⇔ mission transitioned (CF-07); governed-store mutation ⇔ owning writer (OP-09/OR-04); mission ⇔ complete transcript (HM-04); every Evening-Report-counted artifact re-verified against its source of truth at close of books (MC-09).
  2. The audit emits exactly one Evening Report line: zero-imbalances or a named-imbalance alarm.
  3. The audit ships only after a verified-quiet week (no false alarms on known-good history) — the blast-radius guard from Lane 1.
  4. Retrofit criteria (M7/M18 scope): classification events and mission states expose read-only query surfaces sufficient for checks 1–2; no write path is added.
- **Files/components likely affected:** one scheduled health mission (audit runner); read-only queries against MissionStore, classification event log, review-verdict records, brief archives; Evening Report adapter (one line).
- **Estimated engineering effort:** **L** — ~10 simple checks across several stores; the biggest honest build on the list (Lane 1's own grading).
- **Estimated operator effort:** ~5 min/week; more only on a red line.
- **MBP verification required:** **Yes** — each check reviewed against its invariant definition; plus the audit must be canary-tested (Win 5) with a known imbalance before its green line is trusted (HB-03's flatline lesson applied to audits).
- **Rollback strategy:** the audit is read-only by construction — rollback is disabling the scheduled mission; no state to unwind.
- **Evidence proving completion:** one week of quiet audit lines over known-good history; one deliberately injected imbalance per check caught and reported (recorded in the transcript); the Evening Report line present in consecutive rituals.

## Win 4 — Attention Instrumentation

*(Synthesis priority 4; Lane 1 Win 2; covers OP-03/05/06, CF-02/05, OR-05.)*

- **Build Program mission(s) affected:** **M25** (Wiring 4: LeverageStore consuming `attention_saved`) — this *is* the attention-economy measurement mission; the win extends what the same store measures from "interruptions deferred" to "how the operator is actually deciding." **Retrofit:** M12 artifact (attention router) emits acknowledgment/latency events it already observes.
- **Acceptance criteria to add to M25:**
  1. LeverageStore records, per packet: decision latency (emission → answer), answer class (approved / rejected / default-executed), and packet class.
  2. Evening Report carries three derived metrics: decision-latency trend, default-execution rate per packet class (CF-05), and report-consumption depth (opened / sampled / acted-on — OR-05).
  3. Threshold meta-packets fire on the two constitutional floors the campaign names: default-execution rate above threshold ⇒ "make this delegation explicit or reclaim it" (CF-05); consumption below floor ⇒ "resize the audit loop or schedule it" (OR-05). These are ordinary NEEDS_CHAD packets through the existing channel — no new governance.
  4. Retrofit criterion (M12 scope): the router logs acknowledgment timestamps for interrupts and packet deliveries (read-only addition to events it already handles).
- **Files/components likely affected:** LeverageStore schema (the M25 deliverable itself); Evening Report adapter (three metric lines); packet-lifecycle event log; M12 router event emission.
- **Estimated engineering effort:** **S–M** — the store and report channel are M25's own deliverables; the win adds fields and three derivations.
- **Estimated operator effort:** ~2 min/day (the metrics are read inside the existing ritual); rare meta-packets by design.
- **MBP verification required:** **Yes** — review verifies the metrics are *declared-cost honest* (the M21 contract requires `attention_saved` to sum declared minutes only; the same honesty rule applies to the new fields) and that meta-packet thresholds are conservative enough to stay rare.
- **Rollback strategy:** metrics are additive Evening Report lines and additive store fields — rollback is dropping the lines; the store's additive fields are ignored per the 1.x additive-field rule.
- **Evidence proving completion:** two weeks of the three metrics in Evening Reports; one synthetic threshold-crossing produces exactly one meta-packet; LeverageStore rows visible for every packet in the window.

## Win 5 — Canary Program

*(Synthesis priority 5; Lane 1 Win 3; covers HB-03/09, IN-04, HB-06 partial, EW boundary live-fire.)*

- **Build Program mission(s) affected:** **M24** (Wiring 3: memory-graph counts as compound observations) as the absorber — canary outcomes are exactly the kind of governed, reality-terminated observations M24's recorder channel is being built to carry; the canary program rides the mission's own new pipe rather than inventing one. **Cross-attachment:** boundary test documents (the EW live-fire canaries) are already acceptance criterion 3 of Win 2 under M22.
- **Acceptance criteria to add to M24:**
  1. A scheduled canary mission maintains three probe sets: reviewer canaries (known-bad diffs periodically submitted through the review gate — HB-03/HB-09), model-baseline tasks (fixed tasks with known-good historical outputs, diffed on schedule — IN-04/HB-06), and audit canaries (a known imbalance fed to the Win-3 conservation audit).
  2. Canary outcomes are recorded through M24's observation recorder with explicit canary provenance (so they can never masquerade as organic evidence — the TE-07 rule M24 must already enforce).
  3. A caught canary is a quiet green mark; a *missed* canary is a four-class-eligible alarm (a dead reviewer is a safety-relevant condition, per HB-03).
- **Files/components likely affected:** one scheduled health mission (canary runner + probe corpus); the M24 recorder path (canary-tagged observations); review-gate submission path (canary diffs); Evening Report line.
- **Estimated engineering effort:** **M** — probe corpus curation is the real work; the plumbing is M24's own channel.
- **Estimated operator effort:** ~5 min/week; Chad refreshes the probe corpus occasionally (staleness of canaries is itself a TE-06-shaped risk — note in the runbook).
- **MBP verification required:** **Yes — and inverted:** this win exists to verify the MBP. The review gate's continued rejection of canary defects is the standing proof the reviewer is alive; MBP review of the win itself covers only the runner and provenance tagging.
- **Rollback strategy:** disable the scheduled mission; canary-tagged observations are excluded from all organic counts by provenance, so no ledger cleanup is needed on rollback (criterion 2 guarantees this).
- **Evidence proving completion:** first cycle's results — reviewer canaries rejected with diff-grounded reasons, model-baseline diffs within band, audit canary caught — all recorded as canary-tagged observations; one deliberately-missed drill confirming the alarm path fires.

## Win 6 — Horizon Ledger

*(Synthesis priority 6; Lane 1 Win 4; covers IN-01/09, MC-05, TE-06, IS-04, OP-01 queue-age, IN-06 exposure lag.)*

- **Build Program mission(s) affected:** **M23** as the absorber — the ledger's consumer surface is the Morning Packet (`waiting_for_you` / `loop` section already carries deferred and aging items by contract), which M23 makes live. **Retrofit:** M11 artifact (evidence feeds) carries the recorded horizons — `hermes-agent` is already on the closed allowlist; no allowlist change (the M21 contract's own point).
- **Acceptance criteria to add to M23:**
  1. A horizon record type in the existing evidence feed: everything with a date — credential/token expiries (IN-09), Tailscale node-key expiry (IN-01), PAUSE recheck dates (MC-05), trust-evidence age vs. environment changes (TE-06), opportunity-evidence age vs. staleness bands (IS-04), NEEDS_CHAD queue age (OP-01), push lag and backup lag (IN-06).
  2. The Morning Packet surfaces horizons crossing their warning band — inside the existing `waiting_for_you`/loop section, not as interrupts (attention-economy rule: maintenance items never page).
  3. Nothing on the ledger may first be learned about at failure time: a post-incident check "was this expiry on the ledger?" is part of every relevant RCA.
- **Files/components likely affected:** evidence-feed recorder (one record type); small collectors (a credential-expiry reader, a queue-age query, a push/backup-lag query — each a few lines in existing health-mission scope); Morning Packet adapter section.
- **Estimated engineering effort:** **S–M** — each collector is trivial; the value is the union.
- **Estimated operator effort:** ~3 min/day inside the existing morning ritual; acting on a horizon (rotating a key) is work Chad already does — now scheduled instead of forced.
- **MBP verification required:** **No** — read-only collectors and a packet section; standard review suffices, no special verification gate.
- **Rollback strategy:** drop the packet section and stop the collectors; horizon records in the feed are inert data.
- **Evidence proving completion:** the Morning Packet section rendering real horizons for a week; one live save demonstrated (a key rotated from a ledger warning before expiry, cited in the Evening Report).

## Win 7 — Event Identity + Reality-Terminated Provenance

*(Synthesis priority 7; Lane 1 Win 5; covers TE-01/05/07, IS-05/08, MC-03/12, CF-06/07 partials.)*

- **Build Program mission(s) affected:** **M22 and M24** — this is the Parent Synthesis's "seam-hardening as acceptance criteria" recommendation made concrete. M22 opens the scout-feed seam (the campaign's named MC-03/04 dispatch surface and TE-05 replay surface); M24 opens the memory-count seam (the campaign's named TE-07 surface). Each mission absorbs the discipline for its own seam. **Retrofit:** M11 artifact (the recorder) enforces both rules for all existing feeds.
- **Acceptance criteria to add to M22:**
  1. `POST /opportunities` is idempotent: each posted opportunity carries a unique event identity (the scout's existing fingerprint + event ID); a replayed POST is a logged no-op (TE-05/IS-08).
  2. Duplicate-delivery reconciliation: MC-side inbox count ⇔ scout-side sent count, checked by the Win-3 audit.
- **Acceptance criteria to add to M24:**
  3. Every recorded compound observation carries provenance terminating outside Hermes output (a merged PR, a test run, a human entry, an external artifact); observations whose chains terminate in another Hermes output are rejected at the recorder (TE-07).
  4. Observation identity is unique and idempotent: re-recording the same event is a no-op; the reject counter is itself a feed metric (replay signature alarm).
- **Retrofit criterion (M11 scope):** the recorder applies rules 3–4 to all allowlisted sources, not only M24's.
- **Files/components likely affected:** M22 feed endpoint + scout `ingestion`/`dedup` identity plumbing (exists — exact fingerprints); M24 recorder validation; M11 `record_signal` path; provenance-type vocabulary shared with memorygraph (exists — provenance is already recorded by design; this enforces its shape).
- **Estimated engineering effort:** **M** — validation at two recorders plus identity threading at one endpoint.
- **Estimated operator effort:** none steady-state.
- **MBP verification required:** **Yes** — review verifies the rejection branches (replay ⇒ no-op, circular provenance ⇒ reject) with explicit tests; these are the branches whose silent failure recreates TE-05/TE-07.
- **Rollback strategy:** validation-off flags per recorder restore prior behavior; identities already written are inert. Note: rolling back re-opens the named seams — rollback of this win should itself bounce a NEEDS_CHAD packet (it is a governance-relevant relaxation, HB-07's lesson).
- **Evidence proving completion:** replay test (same event twice ⇒ one record + one logged reject) and circularity test (Hermes-output-rooted observation ⇒ rejected) in both mission transcripts; reject counters visible in the feed.

## Win 8 — Effect-Level Classification

*(Synthesis priority 8; Lane 1 Win 10; covers CF-01/CF-08 — existential #5/#6.)*

- **Build Program mission(s) affected:** **RETROFIT of the M7 artifact** (escalation classifier `classify_work`). No remaining mission touches external-effect execution, and the classifier is the owning artifact — the campaign's CF-08 containment names this mechanism as the classifier applied at the effect hop. Per the synthesis (§3.2): this is the most architecture-adjacent win — it *extends an existing gate to an existing choke point* and must be reviewed against that line.
- **Acceptance criteria to add (M7 retrofit scope):**
  1. Every execution path that produces an external effect (message send, post, filing, payment API — the HUMAN_FIRST boundary classes) re-invokes classification on the *composite effect* at the last hop, regardless of upstream CONTINUE verdicts (CF-08).
  2. The set of effect-hop call sites is enumerated and audited by the Win-3 conservation audit (work ⇔ classification includes effect hops).
  3. A decomposed-send test (draft ⇒ prepare ⇒ finalize, each CONTINUE) is caught at the final hop and forks to NEEDS_CHAD.
- **Files/components likely affected:** `chief_of_staff.escalation` classifier call sites at effect-producing tool paths on the Mini; the effect-hop inventory (a list, kept with the rule table); rule table entries for composite effects.
- **Estimated engineering effort:** **M** — the classifier exists; the work is enumerating effect hops and threading the call.
- **Estimated operator effort:** one packet: Chad reviews/ratifies the effect-hop inventory and any new rule-table rows (rule authorship is his — existing governance, not new).
- **MBP verification required:** **Yes** — review verifies (a) the decomposition test, (b) that the change adds call sites without altering the rule table's first-match-wins semantics, and (c) the scope line: extension of the existing gate, no new decision machinery.
- **Rollback strategy:** remove the effect-hop calls (revert); upstream classification remains intact, restoring exactly the pre-win (CF-08-exposed) baseline. Like Win 7, rollback is a governance-relevant relaxation ⇒ packet required.
- **Evidence proving completion:** the decomposed-send harness test passing (caught at final hop) in the transcript; the ratified effect-hop inventory in the decision log; conservation-audit coverage extended to effect hops with a quiet week.

## Win 9 — Restore-Reconciliation Discipline

*(Synthesis priority 9; Lane 1 Win 9; covers MC-12, TE-04, IS-08/09 partials.)*

- **Build Program mission(s) affected:** **RETROFIT of the M18 artifact** (MissionStore persistence — owns restore semantics; the `.corrupt-<ts>` fail-loud convention is its own) and **the M16 artifact** (memorygraph — owns trust-ledger restore, where TE-04's replay-demotions-forward rule lives). No remaining mission owns restores.
- **Acceptance criteria to add (M18 retrofit scope):**
  1. Any restore of MissionStore enters a mandatory dispatch freeze until a reconciliation pass diffs restored state against ground truth (repos, PRs, Hermes-side logs) and Chad accepts the reconciled history via packet (MC-12 — accepting a rewritten record is a values/irreversibility call; existing governance).
  2. Mission IDs are collision-checked post-restore (with Win 7's identities).
- **Acceptance criteria to add (M16 retrofit scope):**
  3. Any restore of the trust ledger holds all autonomy at floor until gap-window trust events are replayed forward from the audit trail; **demotion events must never resurrect** — every gap-window demotion is verified present in the final ledger (TE-04).
- **Files/components likely affected:** MissionStore load path (restore-mode flag + freeze); a reconciliation runbook-mission (read-only diff pass); memorygraph open path (restore-mode + replay); backup tooling notes.
- **Estimated engineering effort:** **M** — mostly a mode flag, a diff pass, and a replay loop over records that already exist (the ledger is recomputable from evidence by design — M16's own property).
- **Estimated operator effort:** none until a restore happens; then one packet per restore (rare by construction).
- **MBP verification required:** **Yes** — the replay-demotions-forward branch is reviewed with a synthetic gap-window (backup, demote, restore, verify the demotion survives) — the exact TE-04 resurrection case.
- **Rollback strategy:** restore-mode flags off ⇒ prior behavior. Since the discipline only activates during restores, rollback risk is nil in steady state; the flags should nonetheless be conservation-audited (a disabled safety mode is HB-07's shape).
- **Evidence proving completion:** one full restore drill on each store (MissionStore and memorygraph) with the drill transcript showing freeze ⇒ diff ⇒ packet ⇒ resume, and the synthetic demotion surviving; drill date recorded on the Win-6 horizon ledger (rehearsals age too — OR-03).

## Win 10 — Boot-as-Deployment

*(Synthesis priority 10; Lane 1 Win 6; covers HM-09/10/12, HM-02/06, EW-04's drift cause.)*

- **Build Program mission(s) affected:** **M23** — the wheel-inclusion/packaging half of M23 is the Build Program's only remaining deployment-shaped deliverable on the Hermes side; environment integrity gating attaches to it as the discipline under which that deployment (and every subsequent boot) is trusted. The Mini's runtime is the artifact; M23 is the mission that next ships changes to it.
- **Acceptance criteria to add to M23:**
  1. An environment manifest (toolchain versions, tool availability, provider-routing config hash — the EW-04 drift cause — key paths) is captured at known-good and diffed at every boot and on schedule (HM-09/12).
  2. The agent refuses the mission queue until the boot self-check passes: manifest diff acknowledged, stale git locks/worktrees pruned (HM-02/06), governed-store write-read probe, auth probes distinguishing "world rejected me" from "lost my keys" (HM-10).
  3. A failed self-check is one platform-event PAUSE, not N mission errors.
- **Files/components likely affected:** Mini boot/launchd health-mission scripts; manifest generator + differ; queue-gate hook in the agent runtime; probe utilities (mostly exist as conventions per the campaign — this wires them).
- **Estimated engineering effort:** **M**.
- **Estimated operator effort:** none steady-state; manifest-diff acknowledgments arrive as brief items, not interrupts.
- **MBP verification required:** **Yes** — review verifies the gate actually blocks the queue on a failed check (the containment is the refusal) and that the manifest covers the provider-routing hash (the EW-04 linkage).
- **Rollback strategy:** disable the queue gate (boot check becomes advisory); manifest capture is read-only and stays. Advisory mode is the documented degraded state, and the conservation audit flags gate-disabled days.
- **Evidence proving completion:** a deliberate reboot drill: manifest diff produced, queue held, acknowledgment recorded, queue released — one transcript; a synthetic toolchain change caught by the scheduled diff; drill date on the horizon ledger.

---

## Cross-cutting notes

1. **Dependency order within the existing sequence.** M22 absorbs Wins 1, 2, 7(a); M23 absorbs Wins 3, 6, 10; M24 absorbs Wins 5, 7(b); M25 absorbs Win 4. The retrofits (Wins 8, 9; plus M7/M11/M12/M16/M18 criteria) have no sequencing dependency on M22–M25 and can be executed as ordinary missions-against-existing-scope in parallel with the wiring rungs — which preserves the synthesis's tranche order (severity first: Wins 1–2 land with M22, the earliest remaining rung) without touching program sequence.
2. **Instrument before audit before enforce** (synthesis §6) maps cleanly: Win 6's horizons and Win 4's metrics (instruments) ship with M23/M25; Win 3's audit consumes them; Wins 7/8's enforcement branches are canary-proofed by Win 5.
3. **Every rollback that relaxes a safety branch requires a packet.** Wins 7, 8, 9, 10 state this individually; it is the HB-07 lesson applied to the wins themselves and uses only the existing NEEDS_CHAD channel.
