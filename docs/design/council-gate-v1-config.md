# Council Gate V1 — Config Design

Status: Phase 2 design artifact

## Default config

Add to `DEFAULT_CONFIG` in `hermes_cli/config.py`:

```python
"council": {
    "enabled": False,
    "mode": "manual",
    "blocking": True,
    "artifact_dir": "~/.hermes/council",
    "write_artifacts": True,
    "persist_raw_request_unsafe": False,
    "allow_mock_unsafe": False,
    "triggers": ["plan", "scope", "delivery", "done"],
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
- `mode` values: `manual`, `command`, `mock`. `mock` is unsafe/debug-only and requires `allow_mock_unsafe=true` when Council is enabled.
- `blocking=true` means review failures pause or require human review.
- `blocking=false` means review failures are reported as skipped/non-blocking.
- `artifact_dir` expands `~` and defaults outside the current repo/workspace at `~/.hermes/council`.
- `write_artifacts=false` is allowed for tests, but runtime default is true.
- Raw request persistence is disabled by default; only `council_request_redacted.json` is written unless `persist_raw_request_unsafe=true` is explicitly configured.
- `command.argv` must be a list, not a shell string.
- `command` mode with empty argv is configuration error.
- No `.env` keys for V1 because no secrets are required.

## Example enabled manual config

```yaml
council:
  enabled: true
  mode: manual
  blocking: true
  artifact_dir: "~/.hermes/council"
  write_artifacts: true
  persist_raw_request_unsafe: false
  triggers:
    - delivery
    - done
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
| `mode` | `manual`, `command`, `mock` | configuration error; enabled mock mode requires explicit unsafe opt-in |
| `blocking` | bool-ish | default true |
| `artifact_dir` | non-empty path string | default profile council dir |
| `write_artifacts` | bool-ish | default true |
| `triggers` | list or dict of enabled triggers | `delivery`, `done`, and `delivery_review` all activate the implemented done/delivery checkpoint |
| `persist_raw_request_unsafe` | bool-ish | default false; raw request is not persisted by default |
| `allow_mock_unsafe` | bool-ish | default false; prevents mock mode from approving production-enabled Council gates |
| `manual.default_decision` | valid Council decision | default `needs_review` |
| `command.argv` | non-empty list[str] for command mode | configuration error |
| `command.timeout_seconds` | positive int | default 60 |

## Backward compatibility

- Existing config files without `council` key must load normally.
- `load_config()` deep merge should populate defaults.
- No migration required.
- No user-facing setup wizard change required for V1.
