# Council Gate V1 — Phase 2 Technical Design

Status: Phase 2 design artifact
Depends on: `docs/design/council-gate-v1-integration-points.md`
Implementation target: `/goal` workflow review layer with mock/manual/command adapters.

## Objective

Add a configurable Council review gate that can inspect major `/goal` plans and deliverables, produce durable review artifacts, and optionally pause auto-continuation when blockers are found.

V1 is deliberately narrow:

- No new model tool.
- No live model adapter.
- No network calls.
- No paid APIs.
- No cron/auth/provider/db mutations.
- Disabled by default.

## Architecture

```text
/goal turn completes
  ↓
GoalManager.evaluate_after_turn(...)
  ↓
CouncilGate.maybe_review(...)
  ↓
Adapter: mock | manual | command
  ↓
ArtifactWriter writes JSON + Markdown
  ↓
CouncilGateResult returned
  ↓
Goal loop continues, pauses, or surfaces NEEDS_REVIEW
```

## Package layout

```text
hermes_cli/council/
  __init__.py
  models.py       # typed request/result/finding models
  adapters.py     # mock/manual/command adapters
  artifacts.py    # artifact path + JSON/Markdown writer
  gate.py         # config resolution + trigger logic
  templates.py    # deterministic review prompt/markdown templates
```

## Public API

```python
from hermes_cli.council import CouncilGate, CouncilReviewRequest, CouncilReviewResult

result = CouncilGate.from_config().maybe_review(
    CouncilReviewRequest(
        session_id=session_id,
        goal=state.goal,
        trigger="delivery_review",
        subject=last_response,
        context="GoalManager.evaluate_after_turn",
    )
)
```

## Data model

```python
CouncilDecision = Literal["pass", "hold", "needs_review", "skipped"]
CouncilSeverity = Literal["info", "warning", "blocker"]
CouncilMode = Literal["mock", "manual", "command"]

@dataclass
class CouncilFinding:
    severity: CouncilSeverity
    title: str
    evidence: str
    recommendation: str

@dataclass
class CouncilReviewRequest:
    session_id: str
    goal: str
    trigger: str
    subject: str
    context: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)

@dataclass
class CouncilReviewResult:
    decision: CouncilDecision
    summary: str
    findings: list[CouncilFinding] = field(default_factory=list)
    reviewer: str = "mock"
    artifact_path: str | None = None
    raw_output: str | None = None
```

Models should provide `to_dict()` helpers for deterministic artifact writing and tests.

## Adapter contracts

```python
class CouncilAdapter(Protocol):
    name: str

    def review(self, request: CouncilReviewRequest) -> CouncilReviewResult:
        ...
```

### Mock adapter

- Deterministic.
- No subprocess/network.
- If subject contains marker `COUNCIL_BLOCKER`, return `hold` with blocker finding.
- If subject contains marker `COUNCIL_NEEDS_REVIEW`, return `needs_review`.
- Else return `pass`.

Purpose: RED/GREEN tests and local smoke tests.

### Manual adapter

- Writes request artifact.
- Returns `needs_review` or configured default decision.
- Used when Chad wants a human/manual review packet.

### Command adapter

- Runs configured local command with JSON request on stdin.
- Expects JSON result on stdout matching `CouncilReviewResult`.
- Has timeout.
- Disabled unless `council.mode=command` and `council.command.argv` is non-empty.
- No shell=True.

## Gate behavior

`CouncilGate.maybe_review(request)` decision flow:

1. If disabled: return `skipped`.
2. If trigger disabled/missing: return `skipped`.
3. If subject empty: return `skipped`.
4. Resolve adapter by mode.
5. Call adapter.
6. Write artifacts when enabled.
7. Return result.

Failure behavior:

- If `blocking=true`: adapter/config/artifact errors return `needs_review` with evidence.
- If `blocking=false`: errors return `skipped` with warning summary.

## Goal loop integration

Primary integration point: `GoalManager.evaluate_after_turn()` in `hermes_cli/goals.py`.

V1 should call Council after the normal judge verdict is available, because that minimizes noise and preserves existing semantics.

Recommended insertion:

- If judge verdict is `done`, run `delivery_review` before returning final `done` message.
- If Council decision is `hold` or `needs_review`, pause goal and return a paused/needs-review message instead of `done`.
- For `continue`, V1 may skip Council to avoid reviewing every continuation turn.

Optional future triggers:

- `goal_plan` when plan markers are detectable.
- `scope_validation` when user asks for build/modify/configure actions.

V1 implementation should start only with `delivery_review` to keep the first patch small and testable.

## User-visible message

When Council blocks/needs review:

```text
⏸ Council review: NEEDS_REVIEW — <summary>. Artifact: <path>
```

When Council passes, default should be silent or a compact debug/status line only if caller surfaces it.

## Artifact behavior

Each review writes:

```text
~/.hermes/council/<YYYYMMDD>/<session_id>-<trigger>-<timestamp>.json
~/.hermes/council/<YYYYMMDD>/<session_id>-<trigger>-<timestamp>.md
```

Use active Hermes profile home via `get_hermes_home()` unless config overrides `artifact_dir`.

## Config

See `docs/design/council-gate-v1-config.md`.

## Test plan

See `docs/design/council-gate-v1-red-test-plan.md`.

## Rollback

Council V1 is rollback-safe because:

- Feature is disabled by default.
- All new runtime code is under `hermes_cli/council/` plus one guarded call site.
- Removing `council` config defaults and the call site restores previous behavior.
- Artifacts are additive under `~/.hermes/council/`.

## Phase 3 implementation order

1. Add model dataclasses and serialization tests.
2. Add artifact writer and tests with temp `HERMES_HOME`.
3. Add adapters and deterministic tests.
4. Add gate config resolution and tests.
5. Add `GoalManager.evaluate_after_turn()` integration test.
6. Add docs/templates.
