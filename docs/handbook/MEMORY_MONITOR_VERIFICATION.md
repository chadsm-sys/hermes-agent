# Verification: `gateway/memory_monitor.py` — is `start_memory_monitoring` used in production?

Follow-up to the finding flagged in
[MODULE_REFERENCE.md](MODULE_REFERENCE.md) §5. Read-only verification;
scope limited to this one question. Verified against commit `d1066a1`
lineage (branch `claude/hermes-cloud-context-bootstrap-e82jy5`,
base = origin/main `93b565b`, 2026-07-06).

## Question

Is `start_memory_monitoring()` actually unused in production, or is it
reached through an indirect call or config path?

## Evidence

### 1. Direct references (whole repo)

`grep -rn "start_memory_monitoring|stop_memory_monitoring|memory_monitor"`
across the entire tree matches **only**:

| Location | Nature |
|---|---|
| `gateway/memory_monitor.py` | The module itself (definitions + docstring) |
| `tests/gateway/test_memory_monitor.py` | Unit tests |
| `docs/handbook/*` | This handbook's own text |

No import of `gateway.memory_monitor` exists anywhere in production
code — not in `gateway/run.py`, not in `hermes_cli/`, not in any plugin,
adapter, or script.

### 2. Indirect / dynamic paths

- No `importlib.import_module` / `__import__` in `gateway/*.py`
  references anything memory-related.
- `gateway/__init__.py` does not re-export it; nothing reaches it via
  the package namespace.

### 3. Config paths

The module docstring (`gateway/memory_monitor.py:27-28`) claims:

> Config: `logging.memory_monitor` in `config.yaml` — see
> `hermes_cli/config.py` for the defaults block.

**That key does not exist.** `memory_monitor` appears nowhere in
`hermes_cli/config.py` (including `DEFAULT_CONFIG`), nowhere in
`cli-config.yaml.example` (the full 64 KB config reference), and nowhere
in `website/` docs. There is no config gate — enabled or disabled —
because there is no code that reads any such key. The docstring
describes wiring that was never landed (the module is a port of
cline/cline#10343; the config hook appears to be aspirational parity).

### 4. Gateway startup path

`git log -S "memory_monitor" -- gateway/run.py` returns **zero
commits**: in all available history (note: history is squashed
whole-tree snapshots, so pre-squash upstream history is not
inspectable from this clone), `gateway/run.py` has never called,
imported, or referenced the module. No other startup path
(`start_gateway`, `GatewayRunner.start`, `hermes_cli/gateway.py`)
references it either.

### 5. Tests

`tests/gateway/test_memory_monitor.py` exercises the module's API
directly and thoroughly: idempotent start (second call returns False),
stop-safe-without-start, baseline line on start, shutdown line on stop,
periodic emission at a short interval, and the RSS-unavailable warning
path. So the module is a **tested, working unit** — the tests import it
directly; they do not (and cannot) demonstrate any production caller.

## Classification

**TRUE_UNUSED** — with one nuance worth recording:

- Not `INDIRECTLY_USED`: no dynamic import, no namespace re-export, and
  the claimed config path does not exist.
- Not `DEAD_CODE` in the pejorative sense: it is a deliberate, tested,
  self-contained diagnostic utility (a documented port from Cline) that
  is importable and callable on demand — e.g. from a debug shell or a
  future one-line wiring in `gateway/run.py`. Upstream may wire it any
  release; deleting it in this fork would buy nothing and create
  permanent merge friction.
- Not `NEEDS_RUNTIME_VERIFICATION`: a function with zero call sites
  cannot be reached at runtime; the Mac mini runs this same source
  (unless it carries local patches, which is outside this repo's
  source-of-truth contract).
- There is additionally a `DOC_ONLY_GAP` component: the module's own
  docstring references a nonexistent `logging.memory_monitor` config
  key, and this handbook's first edition overstated the monitor as
  active (both handbook statements corrected in the same commit as this
  document; the upstream module docstring is left untouched — fixing it
  is an upstream-facing one-liner for a future PR, not a cloud-session
  edit).

## Consequences for operators

Until someone wires it, **no `[MEMORY]` time series appears in any
Hermes log**. Anyone following a leak-hunting runbook that says "grep
`[MEMORY]`" will find nothing — that is expected, not a logging
failure. To get the series today: call
`gateway.memory_monitor.start_memory_monitoring()` manually (debug
shell / temporary patch), or wire it behind a real config key as a
deliberate upstream contribution.

## Recommendation

ADD_DOC_NOTE
