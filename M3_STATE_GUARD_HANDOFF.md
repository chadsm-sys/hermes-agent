# M3 Mission Control Stability + Canonical State Guard

## Status
PARTIAL, packaged and repo-locally verified.

Reason partial:
- State Guard implementation and repo-local verification are complete.
- Canonical `/var/folders/.../hermes-verify-*` temp-script verification was explicitly blocked and not retried.

## Deliverables
- `state_guard.py`
- `tests/test_state_guard.py`

## State Guard commands
```bash
python state_guard.py
python state_guard.py --json
```

## Git status at package time
```text
## mission-control-v0
?? state_guard.py
?? tests/test_state_guard.py
```

## Repo-local verification run
```bash
~/.hermes/hermes-agent/venv/bin/python tests/test_connector.py
~/.hermes/hermes-agent/venv/bin/python tests/test_broker.py
python -m py_compile state_guard.py tests/test_state_guard.py
python state_guard.py --json
```

Results:
- connector test: PASS
- broker test: PASS
- py_compile: PASS
- `state_guard.py --json`: PASS

## Canonical current state
- Hermes version: `0.18.0`
- `HERMES_HOME`: `/Users/chadsmith/.hermes`
- active profile: implicit `default`
- backend URL: `http://127.0.0.1:57658`
- Mission Control plugin installed in active Desktop root: no
- Mission Control plugin enabled: no
- Mission Control plugin visible in Desktop: no
- session count: `9`
- mac mini tunnel PID: `10902`
- mac mini tunnel reachable: true
- fleet card health: `plugin-not-visible-in-desktop`

## Drift found
- Desktop backend `config_version=29`
- Desktop backend `latest_config_version=33`
- active profile is implicit, not explicitly pinned
- Mission Control plugin is not installed under active `~/.hermes/plugins/`

## Safety confirmation
Preserved hard rules:
- no session migration
- no session deletion
- no DB edits
- no gateway restart
- no LaunchAgent changes
- no DGX contact
- no token provisioning
- no prod mutation

## Live endpoints contacted
Read-only only:
- `http://127.0.0.1:57658/api/status`
- `http://127.0.0.1:49171/api/status`

No write endpoints were called.

## Exact recommendation
Treat this as the read-only stability checkpoint.

Canonical operating state:
- Hermes Desktop on `v0.18.x`
- `HERMES_HOME=/Users/chadsmith/.hermes`
- default profile
- local loopback backend only
- Mission Control nodes remain loopback-only and read-only
- mac mini remains tunnel-only
- no changes to session stores

Future controlled change window only:
1. install plugin into `~/.hermes/plugins/mission-control`
2. add `mission-control` to `plugins.enabled` in `~/.hermes/config.yaml`
3. relaunch Desktop in a controlled window
4. separately reconcile config drift `29 -> 33`

Not done here.

## Suggested commit message
```text
feat(mission-control): add read-only state guard for desktop canonical state
```

MISSION_CONTROL_M3_STATE_GUARD_READY
