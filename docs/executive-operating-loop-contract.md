# Executive Operating Loop — Hermes-side Contract (M21)

Status: **contract only — nothing in this document is wired.** No HTTP
client, no import by any runtime code path, no gateway, no cron, no
packaging change. This is the Hermes counterpart of Mission Control's
`EXECUTIVE_API_CONTRACTS.md` (mission-control-v0 PR #20, branch
`m21-executive-operating-loop`).

> Mission Control is the **Executive Brain**. Hermes is the **Executive
> Assistant**. Chad is the **Executive**.
> (docs/chief-of-staff/MISSION.md — the merged constitution)

## 0 — What connects to what (and how little)

```
Mission Control (producer)                Hermes (consumer / feeds)
  executive_packet.morning_packet  ──▶  chief_of_staff.parse_morning_brief
  executive_packet.evening_packet  ──▶  chief_of_staff.parse_evening_report
  executive_state.py events        ◀──  chief_of_staff.escalation decisions
  evidence_feeds (source:
    hermes-agent, allowlisted)     ◀──  memorygraph counts   (reserved)
  POST /opportunities via reserved
    extension slot                 ◀──  opportunity_scout    (reserved)
  morning packet
    .learning_recommendation       ──▶  conversation LEARNING intent
```

Every arrow is a **payload shape plus a governance rule**. The
`chief_of_staff` package itself is proposed in PR #5
(`feat/chief-of-staff-integration`, interface-only, deliberately excluded
from the wheel); the `memorygraph` provider and the `opportunity_scout`
engine are merged on `main` and are Mission-Control-agnostic today. This
document changes none of that — it records the seams so the first wiring
milestone has a contract to implement instead of a design to invent.

## 1 — Versioning rule

`chief_of_staff.contracts.SCHEMA_VERSION = "1.0"`; consumers accept any
payload whose **major** version matches (`check_schema_version`). Mission
Control packets declare `contract_version: "1.1"` — every M21 field is
**additive**, so a 1.0 consumer parses the packet unchanged and simply
does not read the new fields. Removing or renaming a 1.x field requires a
major bump and simultaneous updates to both repos. Neither side ever
guesses at an unknown field.

## 2 — Morning Packet (Mission Control → Hermes)

Consumer: `parse_morning_brief(payload)` via the `MorningBriefSource`
Protocol (`fetch_latest() -> MorningBrief | None`) — the adapter that
performs actual I/O is explicitly future work, outside the package.

| MorningBrief field (v1.0, parsed) | Packet field (produced) |
|---|---|
| `todays_plan` | `todays_plan` (plan items; owner `chad` or `hermes`) |
| `biggest_bottleneck` | `biggest_bottleneck` (evidence-backed or null) |
| `executive_recommendation` | `todays_plan.one_thing` (ONE recommendation) |
| `ai_responsibilities` | `ai_responsibilities` (measured, never promised) |
| `estimated_operator_minutes` | `estimated_operator_minutes` |

Additive in 1.1 (ignored by 1.0 consumers, available to adopt):
`learning_recommendation` (M19 coach), `opportunity_highlight`
(deterministic top of ranking), `why_chosen` (ladder rung + receipts),
`waiting_for_you` (deferred attention items), `loop` (state machine).

Parsing stays **all-or-nothing** (`MorningBriefError`): a malformed
packet is refused whole, never partially trusted.

## 3 — Evening Packet (Mission Control → Hermes)

Consumer: `parse_evening_report` via `EveningReportSource`.

| EveningReport field (v1.0) | Packet field |
|---|---|
| `summary` / `ai_improvements` | `ai_accomplished` (store counts only) |
| `compound_engine` | `compound_progress` (7 dimensions, UNKNOWN honest) |
| `opportunity_summary` | `new_opportunities` (snapshot movement) |

Additive in 1.1: `chad_accomplished` (recorded, never assumed),
`new_evidence`, `tomorrow_bottleneck`, `confidence_changes` (both-days
rule), `knowledge_gained` (counted, never narrated), `attention_saved`,
`loop`, `unknowns`. Note: `EveningReport.Opportunity` (lightweight
consumer type) remains distinct from the Opportunity Scout aggregate —
the packet maps into the former; the scout feeds an inbox (section 6),
not this report.

## 4 — Escalation ⇄ Executive State Machine

`chief_of_staff.escalation.classify_work` emits
`CONTINUE | PAUSE | NEEDS_CHAD` (first-match-wins rule table; only
`NEEDS_CHAD` may carry a question, at most one; `PAUSE` is silent).
Mapping into Mission Control's `executive_state.py` (10 states, 9 events,
fully enumerated deterministic table):

| Hermes decision / condition | MC event | Resulting MC state |
|---|---|---|
| `CONTINUE` | `CONTINUE` | canonical loop advance |
| `PAUSE` (throttle: failure ceiling, external block) | `PAUSE` (reason required) | `WAITING` |
| `NEEDS_CHAD` (authority boundary, chad-only knowledge) | `NEED_CHAD` (reason required) | `NEEDS_CHAD` |
| `SafetyRisk >= HIGH` | `ESCALATE` (reason required) | `ESCALATING` |

Alignment guarantees:

* `ESCALATING` has **no CONTINUE row** on the MC side — a safety
  escalation can only be `RESOLVE`d with a stated reason. Safety is never
  waved through, matching HUMAN_FIRST.md's never-delegated boundaries.
* Every MC transition — including plain `CONTINUE` — requires evidence
  from a closed source set. An unevidenced escalation cannot be recorded.
* `UNKNOWN` is a first-class MC state whose only exit is
  `EVIDENCE_ATTACHED`. Hermes's honest analogues are `degraded=True`
  responses, `classify_intent -> None`, and memorygraph's `contradicted`
  status: on both sides, missing or conflicting knowledge is flagged,
  never filled in.

## 5 — Attention economy alignment

Mission Control may interrupt Chad for exactly four evidence-backed
classes: `safety`, `judgment`, `missing-evidence`, `explicit-approval`
(deny-by-default router; unknown or unevidenced items never interrupt —
they wait for the next packet). This is the same doctrine as
PHILOSOPHY.md section 5 ("Attention Is the Scarce Resource") and the
escalation contract's one-question rule. Deferred items surface as
`waiting_for_you` in the Morning Packet, where they cost seconds inside
the ~90-minute window instead of a context switch outside it.
`attention_saved` (Evening Packet) counts deferred interruptions and sums
**declared** minute costs only — the `chief_of_staff.metrics`
LeverageLedger is the natural future consumer.

## 6 — Opportunity Scout → Mission Control (reserved inbox feed)

The scout (merged; deterministic 0-100 composite, human-entered evidence
only, explicit `ALLOWED_TRANSITIONS` lifecycle) feeds Mission Control's
EXISTING reserved slot `EXTENSION_POINTS["opportunity-scout"]`:

* Transport when wired: `POST /opportunities` with allowed sources only;
  expert-witness sources rejected at the boundary (existing MC
  machinery). The engine itself never fetches anything — unchanged.
* Field mapping: `opportunity_id` -> inbox `id`, `title` -> `title`,
  `confidence` -> `confidence`, `SourceType` -> inbox `source`;
  economics fields inform the MC payload (`expected_value_usd`,
  `chad_minutes`, `ai_minutes`).
* **Neither side reranks the other.** Both rankings are deterministic
  total orders; MC re-scores through its own declared weights so its
  receipts stay local. The scout's composite is provenance, not input.
* Until wired, MC's `opportunity_highlight` honestly reports
  `known: false` naming the missing feed.

## 7 — Memory Graph → Mission Control (reserved evidence feed)

The `memorygraph` provider (merged; governed claims with tiers
candidate/established/core, evidence-gated promotion, contradictions
flagged for review) becomes a Mission Control feed **by recording
signals, not by being imported**:

* When wired, a governed caller records counts through MC's existing
  recorder: `evidence_feeds.record_signal(type="compound-observation",
  metric="memory_claims_established", value=<count>,
  source="hermes-agent")`. `hermes-agent` is **already** on MC's closed
  source allowlist — no allowlist change is needed on either side.
* Consumer: Compound Engine v2's `knowledge-growth` dimension, which
  today declares `reserved_feed: hermes-memory-graph ... not wired`.
* Governance symmetry: promotion requires evidence counts; contradicted
  claims never promote; MC growth claims require >=2 observations on
  >=2 days. No side converts a contradiction or a single point into a
  trend.

## 8 — Executive Coach

The coach lives in Mission Control (M19 `coach()` + M20 adaptive
conversation) and honors EXECUTIVE_COACH.md by construction: a coaching
recommendation without evidence is structurally unreachable; absent
evidence the status is UNKNOWN. Hermes's `LEARNING` conversation intent
("What should I learn?") is a pure consumer of the Morning Packet's
`learning_recommendation` field. The coach informs judgment; it never
replaces it (HUMAN_FIRST.md boundary).

## 9 — Invariants every seam must preserve

1. **Evidence or silence** — payloads carry receipts; UNKNOWN /
   `degraded` / `contradicted` are data, never gaps to fill.
2. **Determinism over cleverness** — total-order ranking on both sides;
   no model calls in ranking, escalation classification or status
   reporting (PHILOSOPHY.md; banned by both codebases' tests).
3. **Mutation boundaries** — Mission Control writes only through its
   `persistence.MissionStore`; Hermes engines write only their own
   governed stores (`memory_graph.db`, `opportunity_scout_store.json`).
   Neither ever writes the other's store.
4. **Attention economy** — no seam may interrupt Chad outside the four
   evidence-backed classes; one question maximum.
5. **Never chase autonomously** — opportunities are detected, priced,
   ranked, expired; never pursued without Chad (PHILOSOPHY.md).
6. **Expert-witness isolation** — forbidden markers rejected at every
   boundary.

## 10 — Explicitly out of scope (hard rules, M21)

No runtime deployment. No desktop install. No Telegram. No OAuth. No
gateway changes. No LaunchAgent. No DGX. No packaging change (the
`chief_of_staff` package stays out of the wheel until the PR that wires
the first caller). No new dependencies (`uv.lock` untouched). No code
changes in this PR at all — this document is the entire diff.

## 11 — Wiring roadmap (each step a separate, Chad-approved milestone)

1. Opportunity Scout -> MC inbox feed under the reserved extension
   contract (smallest step, ends the mock-inbox era).
2. A `MorningBriefSource` / `EveningReportSource` adapter reading MC's
   reserved GET routes, plus wheel inclusion for `chief_of_staff`.
3. Memory-graph counts recorded as compound observations
   (`knowledge-growth` leaves UNKNOWN).
4. `LeverageStore` implementation consuming `attention_saved`.

Final status token for this milestone: `EXECUTIVE_OPERATING_LOOP_READY`.
