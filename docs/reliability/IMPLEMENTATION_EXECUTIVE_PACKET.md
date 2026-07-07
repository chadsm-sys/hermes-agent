# Implementation Executive Packet — Reliability Integration

**Olympus Reliability Integration Program.** Decision-ready summary for the Executive. Sources: `IMPLEMENTATION_INTEGRATION_MATRIX.md`, `MISSION_ACCEPTANCE_CRITERIA.md`, and the accepted Reliability Intelligence Campaign. This packet answers five questions and nothing else.

---

## 1 — Is the current Build Program still correct?

**Yes.** All five analysis lanes and the Parent Synthesis converge: no reordering of the 25 missions materially changes the risk curve, the remaining missions (22–25) are the right next work in the right order, and the reliability leverage the campaign found lives in *how* those missions close, not *which* missions exist. The program is correct and stays exactly as sequenced.

Two honest qualifications, neither of which changes the answer:
- The program was never primarily a reliability program — completed as originally scoped, it would mitigate ~32% of the Top-25 existential risks. With the reliability criteria embedded (question 2), the same 25 missions carry substantially more of that weight without gaining a single new rung.
- The mission ladder M1–M18 used in this analysis is reconstructed (artifacts real, numbering inferred). If the canonical ladder numbers differ, the artifact names in the two companion documents govern; nothing in this packet depends on the numbering.

## 2 — Exactly what reliability work should be embedded into it?

Ten wins, zero new missions, zero resequencing. Full detail per win in the Integration Matrix; per mission in the Acceptance Criteria document.

**Embedded into the four remaining missions as acceptance criteria (definition-of-done):**

| Mission | Absorbs | In one line |
|---|---|---|
| **M22** (Scout → MC feed) | Wins 1, 2, 7a (+ Win 5's boundary canaries) | EW egress pin + egress log; default-deny marker boundary extended to dispatch, metadata, and scheduled sweeps; idempotent feed with replay rejection |
| **M23** (ritual adapters + wheel) | Wins 3, 6, 10 | Conservation audit (10 books-balance checks, one Evening Report line); horizon ledger in the Morning Packet; boot-as-deployment gate on the runtime it ships |
| **M24** (memory counts → compound obs) | Wins 5, 7b | Reality-terminated provenance + idempotent identity at the recorder; the canary program (reviewer / model-baseline / audit canaries) riding the same channel |
| **M25** (LeverageStore) | Win 4 | Attention instrumentation: decision latency, default-execution rate, consumption depth; two threshold meta-packets via the existing NEEDS_CHAD channel |

**Executed as retrofits against completed missions' original scope (no new missions):**

| Artifact (inferred rung) | Retrofit | In one line |
|---|---|---|
| Escalation classifier (M7) | Win 8 | Effect-level classification: the last hop before any external effect re-classifies the composite, killing the CF-01/CF-08 decomposition bypass |
| MissionStore (M18) + memorygraph (M16) | Win 9 | Restore-reconciliation: restore ⇒ freeze ⇒ ground-truth diff ⇒ replay demotions forward; demotions never resurrect |
| Evidence recorder (M11) | Wins 6, 7 support | Horizon record type; identity/provenance validation for all existing feeds |
| Attention router (M12) | Win 4 support | Acknowledgment/latency event emission (read-only) |

**Not embedded anywhere, deliberately:** the three human artifacts the campaign ranks above all implementation — the continuity document (OR-06), the expert-witness methodology statement (EW-10), and the rehearsal calendar (OR-03). They are yours alone; see question 5.

## 3 — What should Mini implement next?

In order, respecting the existing sequence:

1. **The two governance-free retrofits, immediately and in parallel with M22 prep** — Win 9 (restore-reconciliation on MissionStore and memorygraph, closed with one restore drill each) and the M11 recorder validation (Win 7 retrofit). Neither depends on M22–M25; both harden seams the wiring missions are about to lean on.
2. **M22 with its embedded criteria** — the feed endpoint plus the EW egress pin, default-deny boundary, and idempotent POST. This is the earliest remaining rung and it carries the severity-first tranche (existential #1 coverage) with it.
3. **The Win 8 classifier retrofit** — effect-hop enumeration and last-hop re-classification, delivered for your ratification packet (question 5) while M22 review is in flight.
4. **Then M23 → M24 → M25 in program order**, each closing only when its embedded criteria pass.

Nothing else. No new missions, no side projects.

## 4 — What should MBP verify?

Standing requirements (full detail in the Acceptance Criteria document, per mission):

1. **Every merge references a review verdict — no exceptions, no absence-as-consent.** This remains the constitution of the gate itself; the conservation audit will check it nightly once M23 lands.
2. **M22:** boundary default-deny semantics with test documents in every opaque format; the egress pin proven workspace-scoped (not a global default); replay ⇒ no-op; clause-by-clause conformance to contract section 6.
3. **M23:** adapters against contract sections 2–3 (all-or-nothing parsing preserved — reject any leniency); each conservation-audit check against its invariant definition; the boot gate proven to actually hold the queue.
4. **M24:** the provenance-rejection branch *tested, not just present* (circularity and replay tests); canary observations provably excluded from organic counts; promotion-symmetry rules intact.
5. **M25:** metrics observational-only (no behavior keyed to them); declared-cost honesty preserved; meta-packet thresholds conservative.
6. **Retrofits:** Win 8 adds call sites without touching first-match-wins semantics; Win 9's replay-forward branch proven with a synthetic resurrected-demotion drill; any diff adding a model call to the deterministic spine, removing a schema field without a major bump, or adding a capability without classification rules is an **automatic reject**.
7. **Own health:** the reviewer accepts that it is itself canary-tested from M24 onward — a missed canary is an alarm about MBP, and that is the point.

## 5 — What should Chad approve?

Five decisions, each a single packet through the normal channel; estimated total attention ≈ 45 minutes across the program:

1. **The EW endpoint allowlist** (Win 1, at M22) — which model endpoints are approved custody for expert-witness work. Credentials/values; ~10 minutes; the single highest-severity decision in this packet.
2. **The effect-hop inventory and its rule-table rows** (Win 8 retrofit) — ratify the enumerated list of external-effect paths and the composite-effect classification rules. Rule authorship is yours by constitution; ~10 minutes.
3. **The two attention thresholds** (Win 4, at M25) — the default-execution rate and consumption floors that trigger the meta-packets. These encode how much drift you tolerate before being asked; values call; ~5 minutes.
4. **The standing rollback rule** — any rollback that relaxes a safety branch (Wins 7, 8, 9, 10 flags) requires a packet before it happens. One-time ratification; ~2 minutes.
5. **The three human artifacts** — not approvals but authorship, scheduled at your pace and outside this program's scope: the continuity document, the per-matter expert-witness methodology statement (with counsel), and the rehearsal calendar. The campaign's evidence says these outrank everything the Mini will build; this packet's only ask is that they get calendar time.

**Default if you do nothing:** the program proceeds in existing order with the embedded criteria, except the four items above that structurally require your voice (1–3 block their host missions' closure; 5 blocks nothing but stays open on the horizon ledger until addressed).

---

*End of packet. No Version 2, no new roadmap, no additional missions — the Build Program as sequenced, with reliability as its definition of done.*
