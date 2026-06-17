# Council Gate V1 — Config Design

Status: Phase 2 design artifact

## Default config

Add to `DEFAULT_CONFIG` in `hermes_cli/config.py`:

```python
"council": {
    "enabled": False,
    "mode": "mock",
    "blocking": True,
    "artifact_dir": "~/.hermes/council",
    "write_artifacts": True,
    "triggers": {
        "delivery_review": True,
        "goal_plan": False,
        "scope_validation": False,
        "applab_candidate": False,
        "commit_readiness": False,
        "merge_readiness": False,
        "cron_resume": False,
    },
    "manual": {
        "default_decision": "needs_review",
    },
    "command": {
        "argv": [],
        "timeout_seconds": 60,
    },
}
```

## Rules

- `enabled=false` must preserve all current `/goal` behavior.
- `mode` values: `mock`, `manual`, `command`.
- `blocking=true` means review failures pause or require human review.
- `blocking=false` means review failures are reported as skipped/non-blocking.
- `artifact_dir` expands `~` and should default to the active Hermes profile home.
- `write_artifacts=false` is allowed for tests, but runtime default is true.
- `command.argv` must be a list, not a shell string.
- `command` mode with empty argv is configuration error.
- No `.env` keys for V1 because no secrets are required.

## Example enabled mock config

```yaml
council:
  enabled: true
  mode: mock
  blocking: true
  artifact_dir: "~/.hermes/council"
  write_artifacts: true
  triggers:
    delivery_review: true
```

## Example manual review config

```yaml
council:
  enabled: true
  mode: manual
  blocking: true
  manual:
    default_decision: needs_review
```

## Example command review config

```yaml
council:
  enabled: true
  mode: command
  blocking: true
  command:
    argv:
      - python3
      - /absolute/path/to/local_council_review.py
    timeout_seconds: 60
```

## Config validation

Validation should happen in `CouncilGate.from_config()` or a small config resolver.

Required checks:

| Field | Validation | Bad value behavior |
|---|---|---|
| `enabled` | bool-ish | disabled/skipped if false |
| `mode` | `mock`, `manual`, `command` | configuration error |
| `blocking` | bool-ish | default true |
| `artifact_dir` | non-empty path string | default profile council dir |
| `write_artifacts` | bool-ish | default true |
| `triggers` | dict of bool-ish | missing trigger = false except `delivery_review` default true |
| `manual.default_decision` | valid Council decision | default `needs_review` |
| `command.argv` | non-empty list[str] for command mode | configuration error |
| `command.timeout_seconds` | positive int | default 60 |

## Backward compatibility

- Existing config files without `council` key must load normally.
- `load_config()` deep merge should populate defaults.
- No migration required.
- No user-facing setup wizard change required for V1.
