# Council Gate V1 — Artifact Schema

Status: Phase 2 design artifact

## Artifact goals

Council artifacts must be:

- Durable.
- Human-readable.
- Machine-checkable in tests.
- Safe to share without secrets if inputs are safe.
- Additive only; no mutation of existing session history.

## File naming

Default directory:

```text
<active-hermes-home>/council/<YYYYMMDD>/
```

Default basename:

```text
<safe-session-id>-<trigger>-<YYYYMMDDTHHMMSSZ>
```

Written files:

```text
<basename>.json
<basename>.md
```

## JSON schema shape

```json
{
  "schema_version": "council.review.v1",
  "created_at": "2026-06-17T00:00:00Z",
  "request": {
    "session_id": "session-id",
    "goal": "user goal text",
    "trigger": "delivery_review",
    "subject": "assistant response under review",
    "context": "GoalManager.evaluate_after_turn",
    "metadata": {}
  },
  "result": {
    "decision": "pass",
    "summary": "No blockers found.",
    "reviewer": "mock",
    "findings": [
      {
        "severity": "info",
        "title": "Finding title",
        "evidence": "Quoted evidence or deterministic marker.",
        "recommendation": "Concrete next action."
      }
    ],
    "artifact_path": null,
    "raw_output": null
  }
}
```

## Markdown template

```markdown
# Council Review — <DECISION>

- Created: <timestamp>
- Session: `<session_id>`
- Trigger: `<trigger>`
- Reviewer: `<reviewer>`

## Summary

<summary>

## Findings

| Severity | Title | Evidence | Recommendation |
|---|---|---|---|
| blocker | ... | ... | ... |

## Reviewed Subject

```text
<subject>
```
```

## Safety rules

- Artifact writer must create parent directories.
- Artifact writer must not print secrets beyond what was already passed into the reviewed subject.
- Tests should use temp directories and not write to real `~/.hermes`.
- JSON should be deterministic enough for field assertions, not snapshot tests.
- Markdown should be smoke-tested for key headers/decision/path, not exact timestamp snapshots.

## Required artifact assertions

RED tests should assert:

1. JSON artifact is written when `write_artifacts=true`.
2. Markdown artifact is written when `write_artifacts=true`.
3. JSON includes `schema_version=council.review.v1`.
4. Result artifact path is populated after write.
5. Directory uses configured artifact dir.
6. Unsafe session IDs are path-sanitized.
7. Findings serialize as dictionaries.
