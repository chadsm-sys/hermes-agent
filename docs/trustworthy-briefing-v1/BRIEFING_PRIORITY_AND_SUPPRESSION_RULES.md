# Briefing Priority and Suppression Rules

## Ordering

The renderer emits the required nine sections in the contract order. Within a section, items sort by:

1. requires Chad;
2. urgency;
3. operator relevance;
4. confidence.

## Gate handling

- Information is not an approval.
- `NEEDS_CHAD` is reserved for an actual decision boundary.
- Duplicate gates consolidate by a briefing dedupe key; absent an explicit key, normalized title is used.
- The losing duplicate remains in the machine report with its suppression reason.
- `TODAY'S BEST APPROVAL` contains exactly one highest-ranked supported gate, or `NO TRUSTWORTHY RECOMMENDATION`/“Chad is not required.”
- A technical curiosity, routine green check, or item without consequence/recommendation evidence cannot become the best approval.

## Autonomy classes

- `CONTINUE_AUTONOMOUSLY`: current evidence supports continuation with no new decision.
- `CONTINUE_WITH_BOUNDS`: continuation is safe only inside the recorded task contract.
- `WAIT_FOR_EVIDENCE`: do not decide or advance the affected boundary yet.
- `NEEDS_CHAD`: a genuine operator decision is required.
- `STOP`: current evidence requires work to halt.

## Suppression

Suppress, while retaining a machine-report reason:

- routine successful scheduled jobs;
- duplicate approvals;
- parked Kanban items without a current operator decision;
- section overflow beyond configured caps;
- optional missing or stale sources;
- PRs not explicitly classified as requiring operator judgment;
- health/family items not explicitly active today;
- money items not explicitly active today;
- items with operator relevance zero;
- one recommended action when no action is necessary.

Default caps are five gates, five running items, five degraded lanes, five PRs, two health/family items, and two money items.

## Fail-closed rules

- Required stale/missing/unavailable/unknown source: RED.
- Fresh authoritative contradiction: RED.
- Explicit operator-readiness RED/FAIL/BLOCKED: RED.
- Any RED condition: no best approval and no recommended action.
- Optional degradation: YELLOW unless already RED.
- Output over the configured size is truncated with an explicit marker and cannot remain GREEN.
