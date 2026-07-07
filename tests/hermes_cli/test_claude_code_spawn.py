from __future__ import annotations

import json
import subprocess

import pytest


def _make_task(kb, *, assignee: str = "claude-code", **overrides):
    fields = dict(
        id="t_cc_lane",
        title="fix the flaky test",
        body="tests/test_x.py::test_y fails intermittently; make it deterministic.",
        assignee=assignee,
        status="running",
        priority=0,
        created_by="test",
        created_at=1,
        started_at=None,
        completed_at=None,
        workspace_kind="dir",
        workspace_path=None,
        claim_lock="lock",
        claim_expires=None,
        tenant=None,
        current_run_id=7,
    )
    fields.update(overrides)
    return kb.Task(**fields)


# ---------------------------------------------------------------------------
# resolve_spawn_fn routing
# ---------------------------------------------------------------------------

def test_resolve_spawn_fn_disabled_without_env(monkeypatch):
    from hermes_cli import claude_code_spawn as lane

    monkeypatch.delenv(lane.ASSIGNEES_ENV, raising=False)
    assert lane.resolve_spawn_fn() is None

    monkeypatch.setenv(lane.ASSIGNEES_ENV, "  ,  ")
    assert lane.resolve_spawn_fn() is None


def test_resolve_spawn_fn_routes_by_assignee(monkeypatch):
    from hermes_cli import claude_code_spawn as lane
    from hermes_cli import kanban_db as kb

    monkeypatch.setenv(lane.ASSIGNEES_ENV, "Claude-Code, builder-cc")

    calls = []
    monkeypatch.setattr(
        lane, "claude_code_spawn",
        lambda task, ws, *, board=None: calls.append(("claude", task.assignee, board)) or 111,
    )
    monkeypatch.setattr(
        kb, "_default_spawn",
        lambda task, ws, *, board=None: calls.append(("default", task.assignee, board)) or 222,
    )

    route = lane.resolve_spawn_fn()
    assert route is not None

    assert route(_make_task(kb, assignee="claude-code"), "/ws", board="b1") == 111
    assert route(_make_task(kb, assignee="BUILDER-CC"), "/ws") == 111
    assert route(_make_task(kb, assignee="elias"), "/ws", board="b1") == 222
    assert [c[0] for c in calls] == ["claude", "claude", "default"]


# ---------------------------------------------------------------------------
# claude_code_spawn (dispatcher-side half)
# ---------------------------------------------------------------------------

def test_claude_code_spawn_env_contract_and_detached_shim(monkeypatch, tmp_path):
    root = tmp_path / ".hermes"
    root.mkdir(parents=True)
    monkeypatch.setenv("HERMES_HOME", str(root))

    from hermes_cli import claude_code_spawn as lane
    from hermes_cli import kanban_db as kb

    captured = {}

    class FakeProc:
        pid = 4242

    def fake_popen(cmd, *args, **kwargs):
        captured["cmd"] = list(cmd)
        captured["env"] = dict(kwargs.get("env") or {})
        captured["cwd"] = kwargs.get("cwd")
        captured["start_new_session"] = kwargs.get("start_new_session")
        return FakeProc()

    monkeypatch.setattr(subprocess, "Popen", fake_popen)

    workspace = tmp_path / "workspace"
    workspace.mkdir()
    task = _make_task(kb, branch_name="task/t_cc_lane", model_override="claude-sonnet-5")

    pid = lane.claude_code_spawn(task, str(workspace))

    assert pid == 4242
    assert captured["start_new_session"] is True
    assert captured["cwd"] == str(workspace)
    # Shim, not the claude binary, is what the dispatcher tracks.
    assert captured["cmd"][-2:] == ["-m", "hermes_cli.claude_code_spawn"]

    env = captured["env"]
    assert env["HERMES_KANBAN_TASK"] == "t_cc_lane"
    assert env["HERMES_KANBAN_WORKSPACE"] == str(workspace)
    assert env["HERMES_KANBAN_RUN_ID"] == "7"
    assert env["HERMES_KANBAN_CLAIM_LOCK"] == "lock"
    assert env["HERMES_KANBAN_BRANCH"] == "task/t_cc_lane"
    assert env["HERMES_CLAUDE_MODEL_OVERRIDE"] == "claude-sonnet-5"
    assert "HERMES_KANBAN_DB" in env and "HERMES_KANBAN_BOARD" in env
    # Card content is embedded in the prompt (the CLI has no kanban tools).
    assert "fix the flaky test" in env["HERMES_CLAUDE_TASK_PROMPT"]
    assert "test_x.py" in env["HERMES_CLAUDE_TASK_PROMPT"]


def test_claude_code_spawn_requires_assignee(monkeypatch, tmp_path):
    monkeypatch.setenv("HERMES_HOME", str(tmp_path / ".hermes"))

    from hermes_cli import claude_code_spawn as lane
    from hermes_cli import kanban_db as kb

    with pytest.raises(ValueError):
        lane.claude_code_spawn(_make_task(kb, assignee=None), str(tmp_path))


# ---------------------------------------------------------------------------
# _build_claude_argv (lane config → CLI flags)
# ---------------------------------------------------------------------------

def test_build_claude_argv_defaults(monkeypatch):
    from hermes_cli import claude_code_spawn as lane

    for var in (
        "HERMES_CLAUDE_CODE_BIN", "HERMES_CLAUDE_CODE_PERMISSION_MODE",
        "HERMES_CLAUDE_CODE_ALLOWED_TOOLS", "HERMES_CLAUDE_CODE_MODEL",
        "HERMES_CLAUDE_MODEL_OVERRIDE", "HERMES_CLAUDE_CODE_MAX_BUDGET_USD",
        "HERMES_CLAUDE_CODE_EFFORT", "HERMES_CLAUDE_CODE_SETTINGS",
        "HERMES_CLAUDE_CODE_EXTRA_ARGS",
    ):
        monkeypatch.delenv(var, raising=False)

    argv = lane._build_claude_argv("do the thing")
    assert argv[:3] == ["claude", "-p", "do the thing"]
    assert argv[argv.index("--output-format") + 1] == "json"
    # Safe default: never bypassPermissions.
    assert argv[argv.index("--permission-mode") + 1] == "acceptEdits"
    assert "--allowedTools" not in argv and "--model" not in argv


def test_build_claude_argv_full_lane_config(monkeypatch):
    from hermes_cli import claude_code_spawn as lane

    monkeypatch.setenv("HERMES_CLAUDE_CODE_BIN", "/opt/bin/claude")
    monkeypatch.setenv("HERMES_CLAUDE_CODE_PERMISSION_MODE", "plan")
    monkeypatch.setenv("HERMES_CLAUDE_CODE_ALLOWED_TOOLS", "Read Edit Bash(git *)")
    monkeypatch.setenv("HERMES_CLAUDE_CODE_MODEL", "claude-sonnet-5")
    monkeypatch.setenv("HERMES_CLAUDE_MODEL_OVERRIDE", "claude-fable-5")
    monkeypatch.setenv("HERMES_CLAUDE_CODE_MAX_BUDGET_USD", "5")
    monkeypatch.setenv("HERMES_CLAUDE_CODE_EFFORT", "high")
    monkeypatch.setenv("HERMES_CLAUDE_CODE_EXTRA_ARGS", "--fallback-model claude-sonnet-5")

    argv = lane._build_claude_argv("p")
    assert argv[0] == "/opt/bin/claude"
    assert argv[argv.index("--permission-mode") + 1] == "plan"
    assert argv[argv.index("--allowedTools") + 1] == "Read Edit Bash(git *)"
    # Task-level model override wins over the lane default.
    assert argv[argv.index("--model") + 1] == "claude-fable-5"
    assert argv[argv.index("--max-budget-usd") + 1] == "5"
    assert argv[argv.index("--effort") + 1] == "high"
    assert argv[argv.index("--fallback-model") + 1] == "claude-sonnet-5"


# ---------------------------------------------------------------------------
# _map_result (result JSON → lifecycle transition)
# ---------------------------------------------------------------------------

def _success_json(**overrides):
    data = {
        "type": "result",
        "subtype": "success",
        "is_error": False,
        "result": "Fixed the flaky test.\nDetails: pinned the random seed.",
        "session_id": "abc-123",
        "total_cost_usd": 0.42,
        "duration_ms": 61000,
        "num_turns": 9,
    }
    data.update(overrides)
    return json.dumps(data)


def test_map_result_success_completes_with_metadata():
    from hermes_cli import claude_code_spawn as lane

    decision, summary, result_text, metadata = lane._map_result(0, _success_json())
    assert decision == "complete"
    assert summary == "Fixed the flaky test."
    assert "pinned the random seed" in result_text
    assert metadata["claude_session_id"] == "abc-123"
    assert metadata["total_cost_usd"] == 0.42
    assert metadata["num_turns"] == 9


def test_map_result_tolerates_leading_noise():
    from hermes_cli import claude_code_spawn as lane

    noisy = "npm warn something\n" + _success_json()
    decision, summary, _, _ = lane._map_result(0, noisy)
    assert decision == "complete"
    assert summary == "Fixed the flaky test."


def test_map_result_error_subtype_blocks():
    from hermes_cli import claude_code_spawn as lane

    out = _success_json(subtype="error_max_turns", is_error=True, result="ran out of turns")
    decision, reason, _, metadata = lane._map_result(0, out)
    assert decision == "block"
    assert "error_max_turns" in reason
    assert metadata["subtype"] == "error_max_turns"


def test_map_result_rate_limit_is_prefixed():
    from hermes_cli import claude_code_spawn as lane

    out = _success_json(
        subtype="error_during_execution", is_error=True,
        result="You've hit your session limit; resets at 5pm",
    )
    decision, reason, _, _ = lane._map_result(0, out)
    assert decision == "block"
    assert reason.startswith("rate limit:")


def test_map_result_nonzero_exit_blocks():
    from hermes_cli import claude_code_spawn as lane

    decision, reason, _, metadata = lane._map_result(1, "boom")
    assert decision == "block"
    assert "exited with code 1" in reason
    assert metadata["exit_code"] == 1


def test_map_result_unparseable_output_blocks():
    from hermes_cli import claude_code_spawn as lane

    decision, reason, _, _ = lane._map_result(0, "not json at all")
    assert decision == "block"
    assert "unparseable" in reason


# ---------------------------------------------------------------------------
# shim main() wiring (fake claude, recorded lifecycle calls)
# ---------------------------------------------------------------------------

class _FakeConn:
    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


def _wire_shim_env(monkeypatch, tmp_path):
    monkeypatch.setenv("HERMES_KANBAN_TASK", "t_cc_lane")
    monkeypatch.setenv("HERMES_CLAUDE_TASK_PROMPT", "do the thing")
    monkeypatch.setenv("HERMES_KANBAN_WORKSPACE", str(tmp_path))
    monkeypatch.setenv("HERMES_KANBAN_RUN_ID", "7")
    # Keep the heartbeat thread from touching a real DB during the test.
    monkeypatch.setenv("HERMES_CLAUDE_CODE_HEARTBEAT_SECONDS", "3600")


def test_shim_main_success_calls_complete_task(monkeypatch, tmp_path):
    from hermes_cli import claude_code_spawn as lane
    from hermes_cli import kanban_db as kb

    _wire_shim_env(monkeypatch, tmp_path)

    recorded = {}

    def fake_run(argv, **kwargs):
        recorded["argv"] = list(argv)
        recorded["cwd"] = kwargs.get("cwd")
        return subprocess.CompletedProcess(argv, 0, stdout=_success_json(), stderr=None)

    monkeypatch.setattr(subprocess, "run", fake_run)
    monkeypatch.setattr(kb, "connect_closing", lambda: _FakeConn())
    monkeypatch.setattr(
        kb, "complete_task",
        lambda conn, task_id, **kw: recorded.update(complete=(task_id, kw)) or True,
    )
    monkeypatch.setattr(
        kb, "block_task",
        lambda conn, task_id, **kw: recorded.update(block=(task_id, kw)) or True,
    )

    assert lane.main() == 0
    assert "block" not in recorded
    task_id, kw = recorded["complete"]
    assert task_id == "t_cc_lane"
    assert kw["expected_run_id"] == 7
    assert kw["summary"] == "Fixed the flaky test."
    assert kw["metadata"]["lane"] == "claude-code"
    # The CLI's own session_id from the result JSON is what lands in
    # metadata (in real runs it equals the minted --session-id).
    assert kw["metadata"]["claude_session_id"] == "abc-123"
    # A dispatcher-minted UUID --session-id is always passed to the CLI.
    argv = recorded["argv"]
    minted = argv[argv.index("--session-id") + 1]
    import uuid as _uuid
    assert _uuid.UUID(minted)
    assert recorded["cwd"] == str(tmp_path)


def test_shim_main_failure_calls_block_task(monkeypatch, tmp_path):
    from hermes_cli import claude_code_spawn as lane
    from hermes_cli import kanban_db as kb

    _wire_shim_env(monkeypatch, tmp_path)

    recorded = {}
    monkeypatch.setattr(
        subprocess, "run",
        lambda argv, **kw: subprocess.CompletedProcess(argv, 3, stdout="fatal: no api key", stderr=None),
    )
    monkeypatch.setattr(kb, "connect_closing", lambda: _FakeConn())
    monkeypatch.setattr(
        kb, "complete_task",
        lambda conn, task_id, **kw: recorded.update(complete=(task_id, kw)) or True,
    )
    monkeypatch.setattr(
        kb, "block_task",
        lambda conn, task_id, **kw: recorded.update(block=(task_id, kw)) or True,
    )

    assert lane.main() == 0
    assert "complete" not in recorded
    task_id, kw = recorded["block"]
    assert task_id == "t_cc_lane"
    assert kw["expected_run_id"] == 7
    assert "exited with code 3" in kw["reason"]


def test_shim_main_missing_binary_blocks(monkeypatch, tmp_path):
    from hermes_cli import claude_code_spawn as lane
    from hermes_cli import kanban_db as kb

    _wire_shim_env(monkeypatch, tmp_path)

    recorded = {}

    def fake_run(argv, **kwargs):
        raise FileNotFoundError(argv[0])

    monkeypatch.setattr(subprocess, "run", fake_run)
    monkeypatch.setattr(kb, "connect_closing", lambda: _FakeConn())
    monkeypatch.setattr(kb, "block_task", lambda conn, task_id, **kw: recorded.update(block=(task_id, kw)) or True)

    assert lane.main() == 0
    _, kw = recorded["block"]
    assert "not found" in kw["reason"]


def test_shim_main_superseded_run_exits_nonzero(monkeypatch, tmp_path):
    from hermes_cli import claude_code_spawn as lane
    from hermes_cli import kanban_db as kb

    _wire_shim_env(monkeypatch, tmp_path)

    monkeypatch.setattr(
        subprocess, "run",
        lambda argv, **kw: subprocess.CompletedProcess(argv, 0, stdout=_success_json(), stderr=None),
    )
    monkeypatch.setattr(kb, "connect_closing", lambda: _FakeConn())
    # Reclaimed while we ran: the guarded transition reports False.
    monkeypatch.setattr(kb, "complete_task", lambda conn, task_id, **kw: False)

    assert lane.main() == 1


def test_shim_main_requires_task_and_prompt(monkeypatch):
    from hermes_cli import claude_code_spawn as lane

    monkeypatch.delenv("HERMES_KANBAN_TASK", raising=False)
    monkeypatch.delenv("HERMES_CLAUDE_TASK_PROMPT", raising=False)
    assert lane.main() == 2
