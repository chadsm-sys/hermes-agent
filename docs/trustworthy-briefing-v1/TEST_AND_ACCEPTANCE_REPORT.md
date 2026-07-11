# Test and Acceptance Report

Date: 2026-07-11 EDT

## Automated result

Command:

```text
python3 -m pytest -q tests/test_trustworthy_briefing_v1.py
```

Result: **18 passed**.

Covered behavior:

- all required sources fresh;
- one required source missing;
- one required source stale;
- contradictory authoritative claims;
- artifact PASS remains documentary rather than runtime proof;
- no approvals required;
- duplicate approvals;
- one high-value gate over low-value items;
- mission safe to continue autonomously;
- mission requiring Chad;
- stale money suppression;
- incomplete optional health data;
- Telegram-compatible Markdown;
- configured size limit;
- no false GREEN with invalid timestamp;
- no unsupported merge recommendation at render boundary;
- PR adapter neutralizes unsupported merge advice;
- manifest duplicate-source rejection.

Additional checks:

- `python3 -m py_compile scripts/trustworthy_briefing_v1.py`: PASS.
- `git diff --check`: PASS.
- Live read-only collection, no delivery: PASS with honest RED output.

## Acceptance matrix

| Criterion | Result | Evidence |
|---|---|---|
| Every material claim evidence-backed | PASS in engine/tests | Per-item machine envelope and evidence tag |
| Stale data visible | PASS | Source assessment and live stale gateway-state disclosure |
| Missing required inputs degrade | PASS | Required missing/stale tests force RED |
| Documentary/runtime proof separate | PASS | Evidence class retained; test enforced |
| Duplicate decisions consolidated | PASS | Dedupe test and live suppression report |
| Low-value noise suppressed | PASS | Routine cron/parked task suppression and caps |
| Exactly what requires Chad | PASS in renderer | ACTIVE GATES plus autonomy class |
| Autonomous vs blocked work separate | PASS | Required sections and autonomy tests |
| No unsupported claims | PASS for implemented invariants | Contradiction, timestamp, recommendation, merge gates |
| Under three minutes | PASS by size proxy | Live dry run 539 words; 3,954 report characters |
| Fail-closed tests | PASS | 18/18 focused tests |
| Rollback documented | PASS | `ROLLBACK_PLAN.md` |

## Remaining deployment evidence

The code has not replaced the authoritative production script and has not been delivered through Telegram. Therefore controlled-deployment acceptance remains pending:

- one reviewed backup/install operation;
- one direct side-by-side run from the deployment path;
- one explicitly approved Telegram test-fire;
- observation that the following morning remains concise and correctly classified.

Current disposition is PR review, not controlled deployment.
