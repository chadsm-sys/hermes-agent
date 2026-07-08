"""RED tests for Council Gate V1 GoalManager integration."""

from __future__ import annotations

import ast
from pathlib import Path
from unittest.mock import patch

import pytest


@pytest.fixture
def hermes_home(tmp_path, monkeypatch):
    home = tmp_path / ".hermes"
    home.mkdir()
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    monkeypatch.setenv("HERMES_HOME", str(home))

    from hermes_cli import goals

    goals._DB_CACHE.clear()
    yield home
    goals._DB_CACHE.clear()


def test_council_review_runs_on_done_verdict_when_enabled(hermes_home):
    from hermes_cli import goals
    from hermes_cli.goals import GoalManager
    from hermes_cli.council.models import CouncilReviewResult

    mgr = GoalManager(
        session_id="council-sess-1",
        council_config={"enabled": True, "mode": "mock", "triggers": ["done"]},
    )
    mgr.set("ship a safe change")

    fake_result = CouncilReviewResult(decision="needs_revision", summary="Missing rollback.")

    with patch.object(goals, "judge_goal", return_value=("done", "shipped", False)), patch(
        "hermes_cli.council.gate.review_goal_turn", return_value=fake_result
    ) as review_goal_turn:
        decision = mgr.evaluate_after_turn("I shipped it.")

    assert review_goal_turn.called
    assert decision["verdict"] == "council_needs_revision"
    assert decision["should_continue"] is True
    assert "Missing rollback" in decision["continuation_prompt"]
    assert mgr.state.status == "active"


def test_council_review_skipped_by_default(hermes_home):
    from hermes_cli import goals
    from hermes_cli.goals import GoalManager

    mgr = GoalManager(session_id="council-sess-2")
    mgr.set("ship a safe change")

    with patch.object(goals, "judge_goal", return_value=("done", "shipped", False)), patch(
        "hermes_cli.council.gate.review_goal_turn"
    ) as review_goal_turn:
        decision = mgr.evaluate_after_turn("I shipped it.")

    assert not review_goal_turn.called
    assert decision["verdict"] == "done"
    assert decision["should_continue"] is False


def test_runtime_council_config_reaches_goal_manager(hermes_home, monkeypatch):
    from hermes_cli import config as config_mod
    from hermes_cli.goals import GoalManager

    runtime_config = {
        "council": {
            "enabled": True,
            "mode": "manual",
            "triggers": ["delivery"],
            "artifact_dir": str(hermes_home / "council"),
        }
    }
    monkeypatch.setattr(config_mod, "load_config", lambda: runtime_config)

    mgr = GoalManager(session_id="council-runtime-config")

    assert mgr.council_config["enabled"] is True
    assert mgr.council_config["mode"] == "manual"
    assert mgr.council_config["triggers"] == ["delivery"]


def test_real_goal_manager_construction_paths_pass_council_config():
    """Every real runtime GoalManager call site must pass Council config."""

    repo_root = Path(__file__).resolve().parents[2]
    runtime_files = [
        repo_root / "cli.py",
        repo_root / "gateway" / "run.py",
        repo_root / "tui_gateway" / "server.py",
    ]
    call_sites = []
    missing = []

    for path in runtime_files:
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            func = node.func
            name = func.id if isinstance(func, ast.Name) else getattr(func, "attr", "")
            if name != "GoalManager":
                continue
            location = f"{path.relative_to(repo_root)}:{node.lineno}"
            call_sites.append(location)
            if not any(keyword.arg == "council_config" for keyword in node.keywords):
                missing.append(location)

    assert call_sites
    assert missing == []


def test_default_delivery_trigger_activates_done_checkpoint(hermes_home):
    from hermes_cli import goals
    from hermes_cli.goals import GoalManager
    from hermes_cli.council.models import CouncilReviewResult

    mgr = GoalManager(
        session_id="council-delivery-alias",
        council_config={"enabled": True, "mode": "manual", "triggers": ["delivery"]},
    )
    mgr.set("ship a safe change")

    fake_result = CouncilReviewResult(decision="needs_revision", summary="Delivery gate active.")

    with patch.object(goals, "judge_goal", return_value=("done", "shipped", False)), patch(
        "hermes_cli.council.gate.review_goal_turn", return_value=fake_result
    ) as review_goal_turn:
        decision = mgr.evaluate_after_turn("I shipped it.")

    assert review_goal_turn.called
    assert decision["verdict"] == "council_needs_revision"
    assert "Delivery gate active" in decision["continuation_prompt"]
