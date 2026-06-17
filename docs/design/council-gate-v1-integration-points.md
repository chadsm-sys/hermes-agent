# Council Gate V1 — Phase 1 Integration Points

Status: Phase 1 architecture inspection complete
Branch: `feat/hermes-council-gate-v1`
Scope: design-only architecture artifact; no runtime behavior changed by this document.

## Purpose

Council Gate V1 adds an independent review layer around major `/goal` plans and deliverables without widening Hermes' core model-tool surface. V1 must support mock, manual, and command-based review modes behind configuration. Live model invocation remains out of scope unless explicitly approved later.

The correct architecture is to extend the existing `/goal` continuation and approval/gating paths, not to introduce a new workflow framework.

## Inspected architecture

| Area | File | Existing responsibility | Council relevance |
|---|---|---|---|
| Goal state and continuation | `hermes_cli/goals.py` | `GoalState`, persistence in `SessionDB.state_meta`, `GoalManager.evaluate_after_turn()`, continuation prompt generation | Primary state model for `/goal`; Council decisions should attach to this loop without rewriting it |
| CLI `/goal` hook | `cli.py` | `HermesCLI._maybe_continue_goal_after_turn()` judges the last assistant response and queues continuation prompts | Best CLI insertion point after a turn produces a candidate plan/deliverable, before auto-continuation |
| Gateway slash command handling | `gateway/slash_commands.py` | Parses `/goal`, `/subgoal`, status, pause/resume/clear flows for messaging platforms | Council must preserve Telegram/gateway UX and not fork separate goal semantics |
| Gateway turn continuation | `gateway/run.py` | Gateway-side post-turn handling mirrors CLI continuation safety | Council gate must be callable from both CLI and gateway paths, or wrap shared `GoalManager` logic |
| TUI bridge | `tui_gateway/server.py` | TUI JSON-RPC/session layer routes goal commands and continuation state | Council output must be data/file based enough for TUI to display without bespoke coupling |
| Config | `hermes_cli/config.py` | Default config includes `goals.max_turns` and auxiliary model settings | Council feature flags and mode selection belong in `config.yaml`, not `.env`, unless credentials are later needed |
| Approval tooling | `tools/approval.py`, `tools/write_approval.py` | Existing human approval and write-approval primitives | Council must not bypass approval; it adds review evidence before Chad/human approval |
| Background review pattern | `agent/background_review.py` | Existing report-only background review conventions | Useful pattern for report-only Council artifacts and non-blocking review text, but V1 should stay synchronous/testable first |
| Tests | `tests/` | Existing goal and CLI/gateway test suites | Phase 5 should add RED tests around Council state, adapters, gate decisions, artifacts, and `/goal` integration |

## Existing `/goal` flow

### State model

`hermes_cli/goals.py` defines:

- `GoalState`: persisted per session.
- `GoalManager`: owns mutation and continuation decisions.
- `judge_goal()`: auxiliary judge that returns `done` or `continue`.
- `GoalManager.evaluate_after_turn(last_response, user_initiated=True)`: main post-turn decision point.

Current `GoalState` fields include:

```text
goal: str
status: active | paused | done | cleared
turns_used: int
max_turns: int
created_at: float
last_turn_at: float
last_verdict: done | continue | skipped
last_reason: str | None
paused_reason: str | None
consecutive_parse_failures: int
subgoals: list[str]
```

Council should not overload `last_verdict`. Council review is a separate decision layer and should have its own small serializable state if needed.

### CLI continuation hook

`cli.py` has `HermesCLI._maybe_continue_goal_after_turn()`.

Current behavior:

1. Get `GoalManager`.
2. Return if no active goal.
3. Defer if a real user message is queued.
4. Pause on user interrupt.
5. Extract latest assistant response from `conversation_history`.
6. Skip if response is empty.
7. Call `mgr.evaluate_after_turn(last_response, user_initiated=True)`.
8. Print decision message.
9. Queue continuation prompt when `should_continue` is true.

Council insertion can occur before step 7 or immediately after step 7 depending on gate semantics:

- **Pre-judge Council:** review last assistant response before goal judge decides continuation. Best for plan/deliverable safety.
- **Post-judge Council:** only review if judge says done or if response contains a plan/deliverable marker. Best to reduce noise.

V1 recommendation: implement a separate Council gate function called from shared goal-management logic only when explicit trigger conditions are met. Keep CLI and gateway hooks thin.

### Gateway and TUI

Gateway/TUI paths should not duplicate Council logic. They should call the same gate function via `GoalManager` or a new goal-adjacent helper. Any user-visible Council message should be simple text plus artifact path, so Telegram/CLI/TUI can render it without platform-specific code.

## Integration hook points

### 1. Goal plan approval before execution

**Why:** Major `/goal` workflows can produce risky plans before implementation starts. Council should attack the plan before work proceeds.

**Likely location:** goal-adjacent helper invoked from post-turn goal continuation.

**Candidate signature:**

```python
def maybe_review_goal_turn(
    *,
    session_id: str,
    goal: GoalState,
    assistant_response: str,
    trigger: str,
    config: Mapping[str, Any] | None = None,
) -> CouncilGateResult:
    ...
```

**Trigger:** `trigger="goal_plan"` when assistant response appears to contain an implementation plan, phase plan, high-risk action proposal, or explicit Council marker.

**Authority:** Council may return `hold`, `pass`, or `needs_review`. It must not execute actions.

### 2. Build scope validation before start

**Why:** Prevent scope creep, SaaS overbuild, hardcoded secrets, cron/auth/provider changes, or live model calls.

**Likely location:** same gate helper, with scope-specific review prompt/template.

**Candidate trigger:** `trigger="scope_validation"`.

**Authority:** Council can block auto-continuation by returning `hold`/`needs_review`; user can resume/override manually.

### 3. Delivery artifact review before shipment

**Why:** Before a `/goal` run finalizes, Council should review artifacts for missing tests, rollback, safety gates, and unsupported claims.

**Likely location:** post-judge path when `judge_goal()` returns `done`, before marking the goal fully trusted by the user-facing loop.

**Candidate trigger:** `trigger="delivery_review"`.

**Authority:** Council can require a `NEEDS_REVIEW` final instead of a PASS final. It must not send, publish, merge, deploy, or contact anyone.

### 4. AppLab candidate review before ranking

**Why:** AppLab candidate selection needs an adversarial review layer for buyer proof, self-serve constraints, liability exclusions, and kill rules.

**Likely location:** not current core `/goal` code unless AppLab is run through `/goal`. V1 should support this as a review template/artifact type, not custom AppLab core wiring.

**Candidate trigger:** `trigger="applab_candidate"`.

**Authority:** report-only; no candidate advances without explicit money-loop gate evidence.

### 5. Commit readiness check before local commit

**Why:** Local safety automation already blocks unsafe commits. Council can produce review evidence before a commit, but must not replace secret scans/tests.

**Likely location:** future extension around existing git safety scripts, not V1 core unless invoked manually.

**Candidate trigger:** `trigger="commit_readiness"`.

**Authority:** advisory/report-only in V1. Existing git safety gates remain authoritative.

### 6. Merge readiness check before branch merge

**Why:** Higher-risk than local commit. Council should check diff scope, tests, rollback, and safety claims.

**Likely location:** future git workflow integration; not required for V1 `/goal` core.

**Candidate trigger:** `trigger="merge_readiness"`.

**Authority:** advisory/report-only unless a future approval gate explicitly enables blocking.

### 7. Cron resume approval before scheduler restart

**Why:** Cron/autonomous jobs have failure visibility and recursive scheduling risks.

**Likely location:** future cron workflow integration; V1 can provide a template only.

**Candidate trigger:** `trigger="cron_resume"`.

**Authority:** advisory/report-only; no cron mutations in V1.

## Proposed V1 module boundaries

### New package

```text
hermes_cli/council/
  __init__.py
  models.py
  adapters.py
  gate.py
  artifacts.py
  templates.py
```

Rationale: Council is currently goal/CLI-adjacent and does not justify a new model tool or plugin surface. `hermes_cli` keeps it out of the core model tool schema.

### Models

Recommended minimal models:

```python
@dataclass
class CouncilReviewRequest:
    session_id: str
    goal: str
    trigger: str
    subject: str
    context: str = ""
    artifact_dir: str | None = None

@dataclass
class CouncilFinding:
    severity: Literal["info", "warning", "blocker"]
    title: str
    evidence: str
    recommendation: str

@dataclass
class CouncilReviewResult:
    decision: Literal["pass", "hold", "needs_review", "skipped"]
    summary: str
    findings: list[CouncilFinding]
    artifact_path: str | None = None
    reviewer: str = "mock"
```

### Adapters

V1 adapters:

- `MockCouncilAdapter`: deterministic test adapter.
- `ManualCouncilAdapter`: writes request artifact and returns `needs_review`/`hold` depending on config.
- `CommandCouncilAdapter`: invokes a configured local command with JSON stdin/stdout; disabled by default.

Out of scope:

- Live LLM/model adapter.
- Paid API adapter.
- Network calls.
- Any adapter requiring secrets.

### Gate

`CouncilGate` should:

1. Load config.
2. Check `council.enabled`.
3. Match trigger against `council.triggers`.
4. Build request.
5. Call adapter.
6. Write artifacts.
7. Return a typed result to caller.

It must fail safe for blocking mode and fail open only when explicitly configured. V1 default should be disabled/skipped to preserve backward compatibility.

## Config integration

Add under `DEFAULT_CONFIG` in `hermes_cli/config.py`:

```yaml
council:
  enabled: false
  mode: mock        # mock | manual | command
  blocking: true
  triggers:
    goal_plan: true
    scope_validation: true
    delivery_review: true
  artifact_dir: "~/.hermes/council"
  command:
    argv: []
    timeout_seconds: 60
```

Rules:

- Behavioral settings go in `config.yaml`, not `.env`.
- No secrets required for V1.
- `enabled: false` preserves existing `/goal` behavior.
- `mode: command` must reject empty `argv`.
- Paths must expand under the active Hermes profile unless explicitly configured.

## Decision protocol and authority model

Council is not a human approval substitute.

| Actor | Authority |
|---|---|
| Hermes proposer | Creates plan/deliverable and may continue work within normal tool approvals |
| Council reviewer | Produces independent critique and `pass`/`hold`/`needs_review` decision |
| Verifier/tests | Provides tool-backed evidence; remains required for PASS |
| Chad/human | Approves outbound/contact/spend/destructive/provider/auth/cron changes |

Decision rules:

- `pass`: Council found no blocker; normal goal loop may continue.
- `hold`: Council found a blocker; auto-continuation should pause or surface `NEEDS_REVIEW`.
- `needs_review`: Human review required; no autonomous continuation.
- `skipped`: Feature disabled, no matching trigger, or insufficient input.

Council must not:

- Commit, push, merge, rebase.
- Resume/modify cron.
- Invoke live models or paid APIs.
- Send outbound messages.
- Change provider/auth/db settings.
- Print secrets.

## Backward compatibility notes

- Existing `/goal`, `/subgoal`, pause/resume/clear semantics must remain unchanged when `council.enabled=false`.
- Existing `GoalState` JSON must continue to deserialize. Do not add required fields without defaults.
- Existing `GoalManager.evaluate_after_turn()` return keys must remain stable.
- CLI, gateway, and TUI should not fork separate Council behavior.
- No new core model tool should be added.
- No synthetic user/assistant role alternation changes should be introduced in active conversations.
- Council artifacts should be written to files, not injected into historical prompt context, preserving prompt-cache stability.

## Phase 2 transition criteria

Phase 2 design artifacts may start after this document exists and satisfies:

- File-by-file hook placement documented.
- Candidate method signatures documented.
- Decision protocol and authority model documented.
- Backward compatibility constraints documented.
- V1 adapter boundary documented.
- Safety exclusions documented.

Phase 2 should produce:

1. Council V1 technical design spec.
2. Council config schema and defaults.
3. Council artifact schema/template.
4. RED-test plan mapped to implementation files.
5. Rollback and verification plan.
