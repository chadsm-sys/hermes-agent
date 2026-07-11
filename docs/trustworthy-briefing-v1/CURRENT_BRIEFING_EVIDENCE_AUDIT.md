# Current Briefing Evidence Audit

Date: 2026-07-11 EDT
Scope: current production morning briefing and its read-only inputs. Production was not changed.

## Current owner and delivery path

- Generator: `/Users/macmini/.hermes/scripts/daily_command_center.py` (standalone, not tracked by the Hermes repository).
- Schedule: Hermes cron job `e3ecafeb7ce0`, `15 4 * * *`, no-agent mode, Telegram delivery.
- Latest observed output: `/Users/macmini/.hermes/cron/output/e3ecafeb7ce0/2026-07-11_04-15-55.md`.
- Separate claimed entry point: `/Users/macmini/Hermes-Handoff/MORNING_BRIEF.md`, generated 2026-07-02 and now stale.
- Evening input: `/Users/macmini/.hermes/scripts/command_center_feedback.py` and the 19:00 `evening-closeout` job.

No existing canonical machine-readable briefing source manifest was found. The existing Olympus manifests describe governance/workspaces, not briefing source freshness or failure behavior. `config/BRIEF_SOURCE_MANIFEST.yaml` in this change is therefore the first briefing-specific source contract, not a competing copy.

## Current behavior

The current 04:15 output has useful fail-visible behavior:

- It reports overall `RED` when operator readiness is RED.
- It reports an Olympus timeout and a missing health packet as warnings.
- It distinguishes some read-only boundaries and does not send/spend without approval.

It does not yet satisfy the primary-view contract:

- No source manifest defines required inputs, authority, freshness, fallback, or evidence class.
- The output omits the active Kanban mission state and the action-inbox backlog.
- A successful cron run means the script exited successfully; it does not establish input completeness.
- Documentary/artifact status and runtime status are not represented through one typed evidence model.
- Duplicate approvals are not consolidated.
- Routine information and executive decisions do not share a deterministic relevance/urgency policy.
- Optional stale money/health sources can produce warnings, but suppression is source-specific rather than contractual.
- The stale root `MORNING_BRIEF.md` still claims to be the single operator entry point.
- There is no machine report retaining suppressed-item reasons or per-item evidence metadata.

## Current source inventory

| Source | Current use | Authority/freshness gap | V1 decision |
|---|---|---|---|
| Operator readiness JSON | Used | Latest-file behavior exists, no source contract | Required; TEST_VERIFIED; 25-hour threshold |
| Gateway health/state | Indirect current check | State file can be stale while HTTP runtime is healthy | Required live HTTP health; state file optional context |
| Cron jobs JSON | Scheduler context | Green jobs can dominate attention | Required; routine green jobs suppressed |
| Kanban board DBs | Not in current brief | Per-board DBs require safe read-copy handling | Required canonical mission state |
| Action inbox queue | Not in current brief | Duplicates and old items are not consolidated | Required; normalize, dedupe, rank |
| PR poll packet | Planned but absent | No safe merge-readiness evidence | Optional; suppress when absent/stale; never infer merge |
| Health/family packet | Partial/dead path | Missing source warning without a clear relevance contract | Optional; active-today only |
| Money packet | Current bespoke logic | Old leads can resurface | Optional; active-today only |
| Evening feedback | Used by legacy generator | Not required to establish runtime truth | Future normalized optional input; not expanded in V1 |

## Live V1 dry-run evidence

The isolated generator was run against current state without delivery:

- Status: RED.
- Required input completeness: 5/5 fresh.
- Current runtime health: fresh HTTP `OK`.
- Operator readiness: fresh evidence reporting RED.
- Optional gateway-state packet: stale and visibly labeled.
- Optional PR, health/family, and money packets: unavailable and suppressed.
- Duplicate/routine/over-limit items suppressed: 23, with reasons retained in the machine report.
- Output: 539 words / 3,954 report characters, below the 6,000-character Telegram budget.
- Recommendation: `NO TRUSTWORTHY RECOMMENDATION` because the current operator-readiness claim is RED.

## Failure classification

The current production brief is **partially trustworthy but not sufficient as the sole operating view**. Its strongest behavior is honest degradation. Its largest deficiency is lack of a canonical evidence contract tying mission state, approvals, freshness, contradiction handling, and recommendation eligibility together.
