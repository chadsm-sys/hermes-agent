"""Claude Code CLI worker lane for the kanban dispatcher.

Implements the external-CLI lane the worker-lanes doc describes as "not yet a
paved path": a pluggable ``spawn_fn`` that runs tasks through the Claude Code
CLI (``claude -p``) instead of a Hermes profile worker, and maps the CLI's
result back into the kanban lifecycle (``complete_task`` / ``block_task``).

Architecture (mirrors ``kanban_db._default_spawn``):

* ``claude_code_spawn(task, workspace, *, board=None)`` — the dispatcher-side
  half. Pins the same ``HERMES_KANBAN_*`` env contract as the default spawn,
  then launches a detached **shim** process (``python -m
  hermes_cli.claude_code_spawn``) and returns its PID so the dispatcher's
  crash detection keeps working.

* The shim (``main``) — the worker-side half. Runs ``claude -p <prompt>
  --output-format json`` in the task workspace, heartbeats the claim while
  the CLI runs, then writes the terminal transition itself: result JSON with
  ``subtype == "success"`` → ``complete_task``; anything else →
  ``block_task`` with a diagnostic reason. Claude Code has no kanban tools,
  so the shim owns the lifecycle contract on its behalf.

* ``resolve_spawn_fn()`` — env-gated router for the CLI/daemon call sites.
  Returns ``None`` (→ dispatcher default, zero behavior change) unless
  ``HERMES_KANBAN_CLAUDE_CODE_ASSIGNEES`` names the assignees to route here.

Lane configuration is environment-driven so a lane can be shaped per
dispatcher/daemon invocation without config-schema changes:

``HERMES_KANBAN_CLAUDE_CODE_ASSIGNEES``
    Comma-separated assignee names (case-insensitive) routed to this lane.
``HERMES_CLAUDE_CODE_BIN``              Claude binary (default ``claude``).
``HERMES_CLAUDE_CODE_PERMISSION_MODE``  ``--permission-mode`` (default
                                        ``acceptEdits``; never defaults to
                                        ``bypassPermissions``).
``HERMES_CLAUDE_CODE_ALLOWED_TOOLS``    ``--allowedTools`` value.
``HERMES_CLAUDE_CODE_MODEL``            ``--model`` (a task's
                                        ``model_override`` wins).
``HERMES_CLAUDE_CODE_MAX_BUDGET_USD``   ``--max-budget-usd`` value.
``HERMES_CLAUDE_CODE_EFFORT``           ``--effort`` value.
``HERMES_CLAUDE_CODE_SETTINGS``         ``--settings`` file-or-JSON.
``HERMES_CLAUDE_CODE_CONFIG_DIR``       Exported to the CLI as
                                        ``CLAUDE_CONFIG_DIR`` (per-account
                                        isolation for multi-account fleets).
``HERMES_CLAUDE_CODE_EXTRA_ARGS``       Extra argv, shlex-split.
``HERMES_CLAUDE_CODE_HEARTBEAT_SECONDS``  Claim heartbeat cadence (default 60).
"""

from __future__ import annotations

import json
import os
import shlex
import subprocess
import sys
import threading
import uuid
from typing import Optional

_IS_WINDOWS = os.name == "nt"

ASSIGNEES_ENV = "HERMES_KANBAN_CLAUDE_CODE_ASSIGNEES"
DEFAULT_PERMISSION_MODE = "acceptEdits"
DEFAULT_HEARTBEAT_SECONDS = 60.0

# Substrings that mark a failure as a quota wall rather than a task defect.
# The block reason is prefixed so operators (and any future account-rotation
# logic) can distinguish "retry later on another account" from "fix the task".
_RATE_LIMIT_MARKERS = (
    "rate limit",
    "rate_limit",
    "session limit",
    "usage limit",
    "overloaded",
    "429",
    "529",
)


def _lane_assignees() -> set:
    raw = os.environ.get(ASSIGNEES_ENV, "")
    return {part.strip().lower() for part in raw.split(",") if part.strip()}


def resolve_spawn_fn():
    """Return a ``spawn_fn`` for ``dispatch_once``, or ``None``.

    ``None`` when the lane is not enabled (env unset/empty), so callers can
    always pass ``spawn_fn=resolve_spawn_fn()`` and get the dispatcher's
    default behavior unless the operator opted in. When enabled, returns a
    router: assignees named in ``HERMES_KANBAN_CLAUDE_CODE_ASSIGNEES`` go to
    :func:`claude_code_spawn`; everything else falls through to
    ``_default_spawn`` unchanged.
    """
    if not _lane_assignees():
        return None

    from hermes_cli import kanban_db as kb

    def _route(task, workspace, *, board=None):
        assignee = (task.assignee or "").strip().lower()
        if assignee in _lane_assignees():
            return claude_code_spawn(task, workspace, board=board)
        return kb._default_spawn(task, workspace, board=board)

    return _route


def _task_prompt(task) -> str:
    """Build the worker prompt from the task card.

    The default Hermes worker reads its card through kanban tools; the Claude
    CLI has none, so the card content is embedded in the prompt and the shim
    owns the lifecycle transition.
    """
    lines = [f"You are a kanban worker. Task {task.id}: {task.title}"]
    if task.body:
        lines.append("")
        lines.append(task.body)
    lines.append("")
    if task.branch_name:
        lines.append(f"Work on git branch: {task.branch_name}")
    lines.append(
        "Work in the current directory. Do the work described above, run the "
        "relevant tests, and keep changes scoped to the task. Do not push to "
        "any remote unless the task explicitly says to. Your final message is "
        "recorded verbatim as the task result: end with a concise summary of "
        "what you did and how you verified it."
    )
    return "\n".join(lines)


def claude_code_spawn(task, workspace: str, *, board: Optional[str] = None) -> Optional[int]:
    """Fire-and-forget Claude Code shim subprocess for ``task``.

    Dispatcher-side half of the lane; contract-compatible with
    ``kanban_db._default_spawn`` (returns the child PID for crash detection,
    logs to the same per-task worker log, pins the same board env).
    """
    from hermes_cli import kanban_db as kb

    if not task.assignee:
        raise ValueError(f"task {task.id} has no assignee")

    env = dict(os.environ)
    if task.tenant:
        env["HERMES_TENANT"] = task.tenant
    env["HERMES_KANBAN_TASK"] = task.id
    env["HERMES_KANBAN_WORKSPACE"] = workspace
    if task.branch_name:
        env["HERMES_KANBAN_BRANCH"] = task.branch_name
    if task.current_run_id is not None:
        env["HERMES_KANBAN_RUN_ID"] = str(task.current_run_id)
    if task.claim_lock:
        env["HERMES_KANBAN_CLAIM_LOCK"] = task.claim_lock
    # Same belt-and-braces board pins as _default_spawn: the shim must
    # resolve the exact DB/workspaces/board the dispatcher claimed from.
    env["HERMES_KANBAN_DB"] = str(kb.kanban_db_path(board=board))
    env["HERMES_KANBAN_WORKSPACES_ROOT"] = str(kb.workspaces_root(board=board))
    env["HERMES_KANBAN_BOARD"] = (
        kb._normalize_board_slug(board) or kb.get_current_board()
    )
    env["HERMES_PROFILE"] = task.assignee
    env["HERMES_CLAUDE_TASK_PROMPT"] = _task_prompt(task)
    if task.model_override:
        env["HERMES_CLAUDE_MODEL_OVERRIDE"] = task.model_override
    if task.max_runtime_seconds:
        env["HERMES_CLAUDE_MAX_RUNTIME_SECONDS"] = str(int(task.max_runtime_seconds))

    cmd = [sys.executable, "-m", "hermes_cli.claude_code_spawn"]

    log_dir = kb.worker_logs_dir(board=board)
    log_dir.mkdir(parents=True, exist_ok=True)
    log_path = log_dir / f"{task.id}.log"
    rotate_bytes, backup_count = kb.worker_log_rotation_config()
    kb._rotate_worker_log(log_path, rotate_bytes, backup_count)

    # 'a' so a re-run on unblock appends rather than overwrites (matches
    # _default_spawn; the FD stays open in the child after we return).
    log_f = open(log_path, "ab")
    proc = subprocess.Popen(  # noqa: S603 -- argv is a fixed list built above
        cmd,
        cwd=workspace if os.path.isdir(workspace) else None,
        stdin=subprocess.DEVNULL,
        stdout=log_f,
        stderr=subprocess.STDOUT,
        env=env,
        start_new_session=True,
        creationflags=subprocess.CREATE_NO_WINDOW if _IS_WINDOWS else 0,
    )
    return proc.pid


# ---------------------------------------------------------------------------
# Worker-side shim
# ---------------------------------------------------------------------------

def _build_claude_argv(prompt: str) -> list:
    binary = os.environ.get("HERMES_CLAUDE_CODE_BIN", "").strip() or "claude"
    argv = [
        binary,
        "-p", prompt,
        "--output-format", "json",
        "--permission-mode",
        os.environ.get("HERMES_CLAUDE_CODE_PERMISSION_MODE", "").strip()
        or DEFAULT_PERMISSION_MODE,
    ]
    allowed = os.environ.get("HERMES_CLAUDE_CODE_ALLOWED_TOOLS", "").strip()
    if allowed:
        argv.extend(["--allowedTools", allowed])
    model = (
        os.environ.get("HERMES_CLAUDE_MODEL_OVERRIDE", "").strip()
        or os.environ.get("HERMES_CLAUDE_CODE_MODEL", "").strip()
    )
    if model:
        argv.extend(["--model", model])
    budget = os.environ.get("HERMES_CLAUDE_CODE_MAX_BUDGET_USD", "").strip()
    if budget:
        argv.extend(["--max-budget-usd", budget])
    effort = os.environ.get("HERMES_CLAUDE_CODE_EFFORT", "").strip()
    if effort:
        argv.extend(["--effort", effort])
    settings = os.environ.get("HERMES_CLAUDE_CODE_SETTINGS", "").strip()
    if settings:
        argv.extend(["--settings", settings])
    extra = os.environ.get("HERMES_CLAUDE_CODE_EXTRA_ARGS", "").strip()
    if extra:
        argv.extend(shlex.split(extra))
    return argv


def _looks_rate_limited(text: str) -> bool:
    lowered = (text or "").lower()
    return any(marker in lowered for marker in _RATE_LIMIT_MARKERS)


def _map_result(returncode: int, stdout_text: str):
    """Map a finished ``claude -p --output-format json`` run to a lifecycle
    transition.

    Returns ``(outcome, summary, result_text, metadata)`` where ``outcome``
    is ``"complete"`` or ``"block"``. Pure function — unit-tested directly.
    """
    stdout_text = (stdout_text or "").strip()
    data = None
    if stdout_text:
        # The result object is the last JSON document on stdout; tolerate
        # leading non-JSON noise (warnings from shells/wrappers).
        candidate = stdout_text
        idx = candidate.rfind("\n{")
        if not candidate.startswith("{") and idx != -1:
            candidate = candidate[idx + 1:]
        try:
            data = json.loads(candidate)
        except (json.JSONDecodeError, ValueError):
            data = None

    if returncode != 0:
        tail = stdout_text[-500:] if stdout_text else "(no output)"
        reason = f"claude exited with code {returncode}: {tail}"
        if _looks_rate_limited(stdout_text):
            reason = f"rate limit: {reason}"
        return ("block", reason, None, {"exit_code": returncode})

    if data is None:
        return (
            "block",
            "claude produced unparseable output: "
            + (stdout_text[-500:] or "(empty stdout)"),
            None,
            {"exit_code": returncode},
        )

    subtype = data.get("subtype")
    result_text = data.get("result") or ""
    metadata = {
        "subtype": subtype,
        "claude_session_id": data.get("session_id"),
        "total_cost_usd": data.get("total_cost_usd"),
        "duration_ms": data.get("duration_ms"),
        "num_turns": data.get("num_turns"),
    }
    metadata = {k: v for k, v in metadata.items() if v is not None}

    if data.get("is_error") or (subtype is not None and subtype != "success"):
        head = result_text.strip()[:500] or f"claude reported subtype={subtype!r}"
        reason = f"claude run failed ({subtype}): {head}"
        if _looks_rate_limited(result_text) or _looks_rate_limited(str(subtype)):
            reason = f"rate limit: {reason}"
        return ("block", reason, result_text or None, metadata)

    summary = result_text.strip().splitlines()[0][:200] if result_text.strip() else (
        f"claude completed task ({subtype})"
    )
    return ("complete", summary, result_text or None, metadata)


def _heartbeat_seconds() -> float:
    raw = os.environ.get("HERMES_CLAUDE_CODE_HEARTBEAT_SECONDS", "").strip()
    try:
        value = float(raw)
    except (TypeError, ValueError):
        return DEFAULT_HEARTBEAT_SECONDS
    return value if value > 0 else DEFAULT_HEARTBEAT_SECONDS


def _start_heartbeat(task_id: str, run_id: Optional[int]):
    """Heartbeat the claim while the CLI runs; returns a stop callable."""
    from hermes_cli import kanban_db as kb

    stop = threading.Event()
    interval = _heartbeat_seconds()

    def _loop():
        while not stop.wait(interval):
            try:
                with kb.connect_closing() as conn:
                    kb.heartbeat_worker(
                        conn, task_id,
                        note="claude-code lane",
                        expected_run_id=run_id,
                    )
            except Exception:
                # Heartbeat is a liveness nicety; the PID check and claim
                # TTL remain the real safety nets. Never kill the run over it.
                pass

    thread = threading.Thread(target=_loop, name="claude-lane-heartbeat", daemon=True)
    thread.start()
    return stop.set


def main() -> int:
    """Shim entry point (``python -m hermes_cli.claude_code_spawn``)."""
    from hermes_cli import kanban_db as kb

    task_id = os.environ.get("HERMES_KANBAN_TASK", "").strip()
    prompt = os.environ.get("HERMES_CLAUDE_TASK_PROMPT", "")
    workspace = os.environ.get("HERMES_KANBAN_WORKSPACE", "").strip() or os.getcwd()
    raw_run_id = os.environ.get("HERMES_KANBAN_RUN_ID", "").strip()
    run_id = int(raw_run_id) if raw_run_id.isdigit() else None
    if not task_id or not prompt:
        print(
            "claude-code lane shim: HERMES_KANBAN_TASK and "
            "HERMES_CLAUDE_TASK_PROMPT are required",
            file=sys.stderr,
        )
        return 2

    argv = _build_claude_argv(prompt)
    # A dispatcher-minted session id makes the Claude session resumable and
    # correlatable (`claude -r <id>`) from the task record.
    session_id = str(uuid.uuid4())
    argv.extend(["--session-id", session_id])

    child_env = dict(os.environ)
    config_dir = os.environ.get("HERMES_CLAUDE_CODE_CONFIG_DIR", "").strip()
    if config_dir:
        child_env["CLAUDE_CONFIG_DIR"] = config_dir

    raw_timeout = os.environ.get("HERMES_CLAUDE_MAX_RUNTIME_SECONDS", "").strip()
    timeout = int(raw_timeout) if raw_timeout.isdigit() else None

    stop_heartbeat = _start_heartbeat(task_id, run_id)
    try:
        try:
            proc = subprocess.run(  # noqa: S603 -- argv built from lane config
                argv,
                cwd=workspace if os.path.isdir(workspace) else None,
                stdin=subprocess.DEVNULL,
                stdout=subprocess.PIPE,
                stderr=None,  # inherit the worker log the dispatcher attached
                env=child_env,
                timeout=timeout,
                text=True,
                errors="replace",
            )
            returncode, stdout_text = proc.returncode, proc.stdout or ""
        except subprocess.TimeoutExpired as exc:
            partial = exc.stdout
            if isinstance(partial, bytes):
                partial = partial.decode("utf-8", errors="replace")
            returncode, stdout_text = -1, partial or ""
            outcome = (
                "block",
                f"claude run exceeded max runtime ({timeout}s)",
                None,
                {"timeout_seconds": timeout},
            )
        except FileNotFoundError:
            binary = _build_claude_argv("")[0]
            outcome = (
                "block",
                f"claude binary not found: {binary!r}. Install Claude Code or "
                "set HERMES_CLAUDE_CODE_BIN.",
                None,
                {},
            )
            returncode, stdout_text = -1, ""
        else:
            outcome = None
    finally:
        stop_heartbeat()

    # Echo the CLI's stdout into the worker log (our stdout) so
    # `hermes kanban log <id>` shows the full result JSON.
    if stdout_text:
        print(stdout_text)

    if outcome is None:
        outcome = _map_result(returncode, stdout_text)
    decision, summary, result_text, metadata = outcome
    metadata.setdefault("claude_session_id", session_id)
    metadata["lane"] = "claude-code"

    with kb.connect_closing() as conn:
        if decision == "complete":
            ok = kb.complete_task(
                conn, task_id,
                result=result_text,
                summary=summary,
                metadata=metadata,
                expected_run_id=run_id,
            )
        else:
            ok = kb.block_task(
                conn, task_id,
                reason=summary,
                expected_run_id=run_id,
            )
    if not ok:
        # Claim was reclaimed/re-dispatched while we ran; the transition
        # belongs to the newer run. Log and exit nonzero for the record.
        print(
            f"claude-code lane shim: task {task_id} transition ({decision}) "
            "was not applied (run superseded or state changed)",
            file=sys.stderr,
        )
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
