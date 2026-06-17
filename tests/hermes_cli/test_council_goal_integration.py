"""RED tests for Council Gate V1 GoalManager integration."""

from __future__ import annotations

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
