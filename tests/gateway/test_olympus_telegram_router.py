"""Behavior contracts for durable Olympus Telegram intake."""

from __future__ import annotations

import asyncio
import time
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

from gateway.config import GatewayConfig, Platform
from gateway.platforms.base import MessageEvent, MessageType
from gateway.session import SessionSource, SessionStore


MISSION_ID = "M-20260713-telegram-test"


def _source() -> SessionSource:
    return SessionSource(
        platform=Platform.TELEGRAM,
        chat_id="1001",
        user_id="operator-1",
        chat_type="dm",
    )


def _event(text: str, update_id: int) -> MessageEvent:
    return MessageEvent(
        text=text,
        message_type=MessageType.TEXT,
        source=_source(),
        message_id=str(update_id),
        platform_update_id=update_id,
    )


def _context(*, mission_id: str = MISSION_ID, agent_id: str = "coding") -> dict:
    expires = int(time.time()) + 3600
    return {
        "schema_version": 1,
        "goal_id": "G-telegram-test",
        "program_id": "P-telegram-test",
        "milestone_id": "ML-telegram-test",
        "mission_id": mission_id,
        "workstream_id": "WS-telegram-test",
        "authority": {
            "ref": "authority:test",
            "mission_id": mission_id,
            "status": "active",
            "expires_at": expires,
        },
        "lease": {
            "ref": "lease:test",
            "mission_id": mission_id,
            "holder": agent_id,
            "status": "active",
            "expires_at": expires,
        },
        "risk": "low",
        "agent_id": agent_id,
        "review_status": "pending",
        "evidence_refs": [],
    }


def _runner(store: SessionStore):
    from gateway.run import GatewayRunner

    runner = object.__new__(GatewayRunner)
    runner.config = store.config
    runner.session_store = store
    runner.adapters = {}
    runner._running_agents = {}
    runner._running_agents_ts = {}
    runner._busy_input_mode = "interrupt"
    runner._busy_text_mode = "interrupt"
    runner._busy_ack_ts = {}
    runner._background_tasks = set()
    runner._kanban_notifier_profile = "default"
    runner._draining = False
    runner._is_user_authorized = lambda source: True
    return runner


@pytest.fixture()
def session_store(tmp_path, monkeypatch):
    import hermes_state

    monkeypatch.setattr(hermes_state, "DEFAULT_DB_PATH", tmp_path / "state.db")
    config = GatewayConfig(sessions_dir=tmp_path / "sessions")
    return SessionStore(sessions_dir=config.sessions_dir, config=config)


@pytest.fixture()
def governed_board(tmp_path, monkeypatch):
    """Use the real Kanban DB with a narrow shim for Mission 2's API.

    Mission 3 is pinned to the common Hermes base, so its branch cannot copy
    Mission 2's schema patch. This shim exercises Mission 3 against that exact
    public contract; the program integration suite runs both real commits.
    """
    from hermes_cli import kanban_db as kb

    monkeypatch.setenv("HERMES_KANBAN_DB", str(tmp_path / "kanban.db"))
    real_create = kb.create_task
    real_get = kb.get_task
    contexts: dict[str, dict] = {}

    conn = kb.connect(board="default")
    try:
        root_id = real_create(
            conn,
            title="Olympus Telegram intake root",
            assignee="coding",
            created_by="test",
        )
    finally:
        conn.close()
    contexts[root_id] = _context()

    def normalize(context):
        if not isinstance(context, dict) or context.get("schema_version") != 1:
            raise ValueError("invalid Olympus context")
        return dict(context)

    def derive(context, *, agent_id):
        child = dict(context)
        child["agent_id"] = agent_id
        return child

    def get_task(conn, task_id):
        task = real_get(conn, task_id)
        if task is not None:
            task.olympus_context = contexts.get(task_id)
        return task

    def create_task(conn, **kwargs):
        context = kwargs.pop("olympus_context", None)
        task_id = real_create(conn, **kwargs)
        if context is not None:
            contexts.setdefault(task_id, dict(context))
        return task_id

    monkeypatch.setattr(kb, "normalize_olympus_context", normalize, raising=False)
    monkeypatch.setattr(kb, "derive_olympus_child_context", derive, raising=False)
    monkeypatch.setattr(kb, "get_task", get_task)
    monkeypatch.setattr(kb, "create_task", create_task)
    return SimpleNamespace(kb=kb, root_id=root_id, contexts=contexts)


def _selection(root_id: str) -> dict:
    return {
        "schema_version": 1,
        "board": "default",
        "root_task_id": root_id,
        "mission_id": MISSION_ID,
        "agent_id": "coding",
    }


def test_selection_survives_store_reload_reset_and_switch(session_store):
    source = _source()
    entry = session_store.get_or_create_session(source)
    selected = _selection("t_abcdef12")
    assert session_store.set_olympus_selection(entry.session_key, selected)

    reloaded = SessionStore(
        sessions_dir=session_store.config.sessions_dir,
        config=session_store.config,
    )
    assert reloaded.get_olympus_selection(entry.session_key) == selected
    reset = reloaded.reset_session(entry.session_key)
    assert reset.olympus_selection == selected
    switched = reloaded.switch_session(entry.session_key, "prior-session")
    assert switched.olympus_selection == selected


@pytest.mark.asyncio
async def test_select_requires_current_governed_root(session_store, governed_board):
    runner = _runner(session_store)
    result = await runner._handle_olympus_command(
        _event(f"/olympus select {governed_board.root_id}", 1)
    )
    assert "durable intake selected" in result
    selection = runner._olympus_selection_for_event(_event("status", 2))
    assert selection == _selection(governed_board.root_id)


@pytest.mark.asyncio
async def test_unbound_or_expired_root_fails_closed(
    session_store, governed_board, monkeypatch
):
    runner = _runner(session_store)

    def canonical_gate(_context, *, assignee):
        assert assignee == "coding"
        raise ValueError("lease is expired")

    monkeypatch.setattr(
        governed_board.kb,
        "_require_current_olympus_context",
        canonical_gate,
        raising=False,
    )
    result = await runner._handle_olympus_command(
        _event(f"/olympus select {governed_board.root_id}", 3)
    )
    assert result == "Olympus selection blocked: target task lease is expired"
    entry = session_store.get_or_create_session(_source())
    assert session_store.get_olympus_selection(entry.session_key) is None


@pytest.mark.asyncio
async def test_unselected_message_stays_on_existing_gateway_path(session_store):
    runner = _runner(session_store)
    assert await runner._route_olympus_telegram_intake(_event("hello", 4)) is None


@pytest.mark.asyncio
async def test_duplicate_delivery_is_one_durable_task(session_store, governed_board):
    runner = _runner(session_store)
    entry = session_store.get_or_create_session(_source())
    session_store.set_olympus_selection(
        entry.session_key, _selection(governed_board.root_id)
    )
    event = _event("Investigate the durable queue", 44)

    first = await runner._route_olympus_telegram_intake(event)
    second = await runner._route_olympus_telegram_intake(event)
    assert first == second

    conn = governed_board.kb.connect(board="default")
    try:
        rows = conn.execute(
            "SELECT id, idempotency_key FROM tasks WHERE id != ?",
            (governed_board.root_id,),
        ).fetchall()
    finally:
        conn.close()
    assert len(rows) == 1
    assert rows[0]["idempotency_key"].startswith("olympus-telegram:v1:")


@pytest.mark.asyncio
async def test_three_jobs_survive_gateway_and_db_reopen(session_store, governed_board):
    runner = _runner(session_store)
    entry = session_store.get_or_create_session(_source())
    selected = _selection(governed_board.root_id)
    session_store.set_olympus_selection(entry.session_key, selected)

    results = await asyncio.gather(
        *(
            runner._route_olympus_telegram_intake(_event(f"job {i}", 100 + i))
            for i in range(3)
        )
    )
    assert all(result and result.startswith("Queued `t_") for result in results)

    restarted_store = SessionStore(
        sessions_dir=session_store.config.sessions_dir,
        config=session_store.config,
    )
    assert restarted_store.get_olympus_selection(entry.session_key) == selected
    conn = governed_board.kb.connect(board="default")
    try:
        rows = conn.execute(
            "SELECT status FROM tasks WHERE id != ? ORDER BY id",
            (governed_board.root_id,),
        ).fetchall()
    finally:
        conn.close()
    assert len(rows) == 3
    assert {row["status"] for row in rows} == {"ready"}


@pytest.mark.asyncio
async def test_busy_selected_message_never_interrupts_active_agent(session_store):
    runner = _runner(session_store)
    agent = MagicMock()
    source = _source()
    key = runner._session_key_for_source(source)
    runner._running_agents[key] = agent
    runner._route_olympus_telegram_intake = AsyncMock(
        return_value="Queued `t_abc12345`"
    )
    adapter = MagicMock()
    adapter._send_with_retry = AsyncMock()
    runner.adapters[Platform.TELEGRAM] = adapter

    handled = await runner._handle_active_session_busy_message(
        _event("unrelated new work", 77), key
    )
    assert handled is True
    agent.interrupt.assert_not_called()
    adapter._send_with_retry.assert_awaited_once()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("action", "starting_status", "expected_status"),
    [
        ("interrupt", "running", "ready"),
        ("pause", "ready", "blocked"),
        ("resume", "blocked", "ready"),
        ("cancel", "ready", "archived"),
    ],
)
async def test_controls_are_explicitly_targeted_and_audited(
    session_store,
    governed_board,
    action,
    starting_status,
    expected_status,
):
    kb = governed_board.kb
    conn = kb.connect(board="default")
    try:
        target_id = kb.create_task(
            conn,
            title=f"target {action}",
            assignee="coding",
            created_by="test",
            olympus_context=_context(),
            initial_status="blocked" if starting_status == "blocked" else "running",
        )
        if starting_status == "running":
            conn.execute(
                "UPDATE tasks SET status = 'running' WHERE id = ?", (target_id,)
            )
            conn.commit()
    finally:
        conn.close()

    runner = _runner(session_store)
    entry = session_store.get_or_create_session(_source())
    session_store.set_olympus_selection(
        entry.session_key, _selection(governed_board.root_id)
    )
    result = await runner._handle_olympus_command(
        _event(f"/olympus {action} {target_id}", 200)
    )
    assert f"{action} applied to `{target_id}`" in result

    conn = kb.connect(board="default")
    try:
        target = kb.get_task(conn, target_id)
        comments = kb.list_comments(conn, target_id)
    finally:
        conn.close()
    assert target.status == expected_status
    assert comments[-1].body == f"Olympus Telegram targeted action: {action}"
    assert comments[-1].author.startswith("telegram:")


@pytest.mark.asyncio
async def test_control_without_task_id_is_rejected_without_mutation(
    session_store, governed_board, monkeypatch
):
    runner = _runner(session_store)
    entry = session_store.get_or_create_session(_source())
    session_store.set_olympus_selection(
        entry.session_key, _selection(governed_board.root_id)
    )
    archive = MagicMock()
    monkeypatch.setattr(governed_board.kb, "archive_task", archive)
    result = await runner._handle_olympus_command(_event("/olympus cancel", 250))
    assert result.startswith("Usage:")
    archive.assert_not_called()


@pytest.mark.asyncio
async def test_control_cannot_cross_mission_boundary(session_store, governed_board):
    kb = governed_board.kb
    conn = kb.connect(board="default")
    try:
        foreign_id = kb.create_task(
            conn,
            title="foreign mission task",
            assignee="coding",
            created_by="test",
            olympus_context=_context(mission_id="M-20260713-foreign-test"),
        )
    finally:
        conn.close()

    runner = _runner(session_store)
    entry = session_store.get_or_create_session(_source())
    session_store.set_olympus_selection(
        entry.session_key, _selection(governed_board.root_id)
    )
    result = await runner._handle_olympus_command(
        _event(f"/olympus cancel {foreign_id}", 251)
    )
    assert result == (
        "Olympus cancel blocked: target task belongs to a different Olympus mission"
    )
    conn = kb.connect(board="default")
    try:
        assert kb.get_task(conn, foreign_id).status == "ready"
        assert kb.list_comments(conn, foreign_id) == []
    finally:
        conn.close()


@pytest.mark.asyncio
async def test_telegram_background_requires_durable_or_explicit_ephemeral(
    session_store,
):
    runner = _runner(session_store)
    no_selection = await runner._handle_background_command(
        _event("/background research this", 300)
    )
    assert "requires an Olympus selection" in no_selection

    runner._run_background_task = AsyncMock()
    result = await runner._handle_background_command(
        _event("/background --ephemeral research this", 301)
    )
    assert "Background task started" in result


def test_olympus_command_bypasses_active_session_guard():
    from hermes_cli.commands import should_bypass_active_session

    assert should_bypass_active_session("olympus") is True
