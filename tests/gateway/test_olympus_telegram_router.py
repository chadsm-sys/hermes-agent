"""Exact authority, delivery, control, and restart contracts for Telegram."""

from __future__ import annotations

import asyncio
import concurrent.futures
import hashlib
import json
import time
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

from gateway.config import GatewayConfig, Platform
from gateway.platforms.base import MessageEvent, MessageType
from gateway.session import SessionSource, SessionStore


MISSION_ID = "M-20260713-telegram-test"
BOT_ID = "9001"
PROFILE = "default"


def _allow(request: dict) -> dict:
    return {
        "schema_version": "olympus-authority-verification/1",
        "decision": "ALLOW",
        "current": True,
        "source": request["authority_source"],
        "source_revision": request["authority_revision"],
        "request_id": request["request_id"],
        "request": request,
        "verification_id": f"verified:{request['request_id']}",
    }


def _source(*, user_id: str = "operator-1", thread_id: str | None = None) -> SessionSource:
    return SessionSource(
        platform=Platform.TELEGRAM,
        chat_id="1001",
        user_id=user_id,
        thread_id=thread_id,
        chat_type="dm",
    )


def _event(
    text: str,
    update_id: int,
    *,
    user_id: str = "operator-1",
    thread_id: str | None = None,
) -> MessageEvent:
    return MessageEvent(
        text=text,
        message_type=MessageType.TEXT,
        source=_source(user_id=user_id, thread_id=thread_id),
        message_id=str(update_id),
        platform_update_id=update_id,
    )


def _context(
    *,
    mission_id: str = MISSION_ID,
    agent_id: str = "coding",
    authority_status: str = "ACTIVE",
    lease_status: str = "ACTIVE",
    authority_revision: int = 7,
    lease_revision: int = 11,
) -> dict:
    expires = int(time.time()) + 3600
    return {
        "schema_version": 2,
        "goal_id": "G-telegram-test",
        "program_id": "P-telegram-test",
        "milestone_id": "ML-telegram-test",
        "mission_id": mission_id,
        "workstream_id": "WS-telegram-test",
        "authority": {
            "authority_id": f"authority:{mission_id}",
            "status": authority_status,
            "scope": [mission_id],
            "capabilities": [
                "kanban.task.create",
                "telegram.olympus.select",
                "telegram.olympus.status",
                "telegram.olympus.clear",
                "telegram.olympus.intake",
                "telegram.olympus.control.pause",
                "telegram.olympus.control.resume",
                "telegram.olympus.emergency.interrupt",
                "telegram.olympus.emergency.cancel",
            ],
            "revision": authority_revision,
            "source": "issuer:test",
            "expires_at": expires,
        },
        "lease": {
            "lease_id": f"lease:{mission_id}:{agent_id}",
            "status": lease_status,
            "mission_id": mission_id,
            "agent_id": agent_id,
            "holder": agent_id,
            "repository": "hermes-agent",
            "branch": "test/telegram",
            "worktree": "/tmp/telegram-test",
            "revision": lease_revision,
            "source": "issuer:test",
            "expires_at": expires,
        },
        "risk": "low",
        "agent_id": agent_id,
        "review_status": "pending",
        "evidence_refs": [],
    }


def _source_identity(*, user_id: str = "operator-1") -> dict[str, str]:
    return {
        "platform": "telegram",
        "bot_id": BOT_ID,
        "profile": PROFILE,
        "chat_id": "1001",
        "thread_id": "",
        "user_id": user_id,
    }


def _digest(value) -> str:
    raw = json.dumps(value, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(raw).hexdigest()


def _selection(root_id: str, context: dict | None = None) -> dict:
    context = context or _context()
    authority = context["authority"]
    lease = context["lease"]
    source_identity = _source_identity()
    return {
        "schema_version": 2,
        "board": "default",
        "root_task_id": root_id,
        "mission_id": context["mission_id"],
        "agent_id": context["agent_id"],
        "authority_id": authority["authority_id"],
        "authority_revision": authority["revision"],
        "authority_source": authority["source"],
        "lease_id": lease["lease_id"],
        "lease_revision": lease["revision"],
        "lease_source": lease["source"],
        "scope_digest": _digest(authority["scope"]),
        "bot_id": BOT_ID,
        "profile": PROFILE,
        "caller_fingerprint": _digest(source_identity),
    }


def _runner(store: SessionStore):
    from gateway.run import GatewayRunner

    runner = object.__new__(GatewayRunner)
    runner.config = store.config
    runner.session_store = store
    runner.adapters = {
        Platform.TELEGRAM: SimpleNamespace(_bot=SimpleNamespace(id=int(BOT_ID)))
    }
    runner._running_agents = {}
    runner._running_agents_ts = {}
    runner._busy_input_mode = "interrupt"
    runner._busy_text_mode = "interrupt"
    runner._busy_ack_ts = {}
    runner._background_tasks = set()
    runner._kanban_notifier_profile = PROFILE
    runner._olympus_authority_verifier = _allow
    runner._draining = False
    runner._is_user_authorized = lambda source: True
    runner._active_profile_name = lambda: PROFILE
    return runner


@pytest.fixture()
def session_store(tmp_path, monkeypatch):
    import hermes_state

    monkeypatch.setattr(hermes_state, "DEFAULT_DB_PATH", tmp_path / "state.db")
    config = GatewayConfig(sessions_dir=tmp_path / "sessions")
    return SessionStore(sessions_dir=config.sessions_dir, config=config)


@pytest.fixture()
def governed_board(tmp_path, monkeypatch):
    from hermes_cli import kanban_db as kb

    monkeypatch.setenv("HERMES_KANBAN_DB", str(tmp_path / "kanban.db"))
    context = _context()
    conn = kb.connect(board="default")
    try:
        root_id = kb.create_olympus_task(
            conn,
            olympus_context=context,
            authority_verifier=_allow,
            actor="coding",
            operation_id="test:create-root",
            expected_revision=context["authority"]["revision"],
            title="Olympus Telegram intake root",
            assignee="coding",
            created_by="test",
        )
    finally:
        conn.close()
    return SimpleNamespace(kb=kb, root_id=root_id, context=context)


def _create_target(board, *, context=None, status="ready", title="target") -> str:
    kb = board.kb
    context = context or _context()
    conn = kb.connect(board="default")
    try:
        task_id = kb.create_olympus_task(
            conn,
            olympus_context=context,
            authority_verifier=_allow,
            actor=context["agent_id"],
            operation_id=f"test:create:{title}:{time.time_ns()}",
            expected_revision=context["authority"]["revision"],
            title=title,
            assignee=context["agent_id"],
            created_by="test",
            initial_status="blocked" if status == "blocked" else "running",
        )
        if status != kb.get_task(conn, task_id).status:
            conn.execute("UPDATE tasks SET status = ? WHERE id = ?", (status, task_id))
            conn.commit()
        return task_id
    finally:
        conn.close()


def _set_selection(store: SessionStore, board) -> str:
    entry = store.get_or_create_session(_source())
    assert store.set_olympus_selection(
        entry.session_key, _selection(board.root_id, board.context)
    )
    return entry.session_key


def test_selection_v2_survives_reload_reset_and_switch(session_store):
    entry = session_store.get_or_create_session(_source())
    selected = _selection("t_abcdef12")
    assert session_store.set_olympus_selection(entry.session_key, selected)
    reloaded = SessionStore(session_store.config.sessions_dir, session_store.config)
    assert reloaded.get_olympus_selection(entry.session_key) == selected
    assert reloaded.reset_session(entry.session_key).olympus_selection == selected
    assert reloaded.switch_session(entry.session_key, "prior").olympus_selection == selected


def test_legacy_selection_is_not_a_compatibility_authority_path(session_store):
    entry = session_store.get_or_create_session(_source())
    with pytest.raises(ValueError, match="schema_version must be 2"):
        session_store.set_olympus_selection(
            entry.session_key,
            {"schema_version": 1, "board": "default", "root_task_id": "t_abcdef12"},
        )


@pytest.mark.asyncio
async def test_select_requires_exact_verifier_and_removes_arbitrary_agent(
    session_store, governed_board
):
    runner = _runner(session_store)
    selected = await runner._handle_olympus_command(
        _event(f"/olympus select {governed_board.root_id}", 1)
    )
    assert "durable intake selected" in selected
    assert runner._olympus_selection_for_event(_event("status", 2))["schema_version"] == 2

    other_store = SessionStore(session_store.config.sessions_dir / "other", session_store.config)
    other = _runner(other_store)
    refused = await other._handle_olympus_command(
        _event(f"/olympus select {governed_board.root_id} --agent attacker", 3)
    )
    assert refused.startswith("Usage:")
    assert other._olympus_selection_for_event(_event("status", 4)) is None

    other._olympus_authority_verifier = None
    denied = await other._handle_olympus_command(
        _event(f"/olympus select {governed_board.root_id}", 5)
    )
    assert "canonical authority verifier is unavailable" in denied


@pytest.mark.asyncio
async def test_selection_bot_profile_and_caller_bindings_fail_closed(
    session_store, governed_board
):
    runner = _runner(session_store)
    _set_selection(session_store, governed_board)
    runner.adapters[Platform.TELEGRAM]._bot.id = 9002
    assert "wrong-source" in await runner._route_olympus_telegram_intake(_event("job", 10))
    runner.adapters[Platform.TELEGRAM]._bot.id = int(BOT_ID)
    runner._active_profile_name = lambda: "foreign-profile"
    assert "wrong-source" in await runner._route_olympus_telegram_intake(_event("job", 11))
    runner._active_profile_name = lambda: PROFILE
    with pytest.raises(ValueError, match="caller-conflicted"):
        runner._validate_olympus_selection_binding(
            _selection(governed_board.root_id),
            governed_board.context,
            _source_identity(user_id="foreign-user"),
        )


@pytest.mark.asyncio
async def test_status_and_clear_reverify_instead_of_trusting_selection(
    session_store, governed_board
):
    runner = _runner(session_store)
    _set_selection(session_store, governed_board)
    runner._olympus_authority_verifier = None
    status = await runner._handle_olympus_command(_event("/olympus status", 12))
    clear = await runner._handle_olympus_command(_event("/olympus clear", 13))
    assert "canonical authority verifier is unavailable" in status
    assert "canonical authority verifier is unavailable" in clear
    assert runner._olympus_selection_for_event(_event("status", 14)) is not None


@pytest.mark.asyncio
async def test_duplicate_and_concurrent_delivery_create_exactly_one_task(
    session_store, governed_board
):
    runner = _runner(session_store)
    _set_selection(session_store, governed_board)
    event = _event("Investigate the durable queue", 44)
    results = await asyncio.gather(
        *(runner._route_olympus_telegram_intake(event) for _ in range(6))
    )
    assert len(set(results)) == 1
    conn = governed_board.kb.connect(board="default")
    try:
        rows = conn.execute(
            "SELECT id, idempotency_key FROM tasks WHERE id != ?",
            (governed_board.root_id,),
        ).fetchall()
        deliveries = conn.execute("SELECT * FROM olympus_telegram_deliveries").fetchall()
    finally:
        conn.close()
    assert len(rows) == len(deliveries) == 1
    assert rows[0]["idempotency_key"].startswith("olympus-telegram:v2:")


@pytest.mark.asyncio
async def test_same_delivery_with_changed_prompt_is_a_context_conflict(
    session_store, governed_board
):
    runner = _runner(session_store)
    _set_selection(session_store, governed_board)
    assert (await runner._route_olympus_telegram_intake(_event("first", 45))).startswith("Queued")
    denied = await runner._route_olympus_telegram_intake(_event("changed", 45))
    assert "different immutable submission" in denied


@pytest.mark.asyncio
async def test_notification_retry_heals_after_restart_delivery(
    session_store, governed_board, monkeypatch
):
    runner = _runner(session_store)
    _set_selection(session_store, governed_board)
    real_add = governed_board.kb.add_notify_sub
    calls = 0

    def flaky(*args, **kwargs):
        nonlocal calls
        calls += 1
        if calls == 1:
            raise RuntimeError("simulated subscription crash")
        return real_add(*args, **kwargs)

    monkeypatch.setattr(governed_board.kb, "add_notify_sub", flaky)
    event = _event("recover notification", 46)
    assert "Notification subscription failed" in await runner._route_olympus_telegram_intake(event)
    assert (await runner._route_olympus_telegram_intake(event)).startswith("Queued")
    conn = governed_board.kb.connect(board="default")
    try:
        assert conn.execute("SELECT count(*) FROM kanban_notify_subs").fetchone()[0] == 1
        assert conn.execute("SELECT count(*) FROM olympus_telegram_deliveries").fetchone()[0] == 1
    finally:
        conn.close()


@pytest.mark.asyncio
async def test_three_then_six_jobs_survive_store_and_database_reopen(
    session_store, governed_board
):
    runner = _runner(session_store)
    key = _set_selection(session_store, governed_board)
    first = await asyncio.gather(
        *(runner._route_olympus_telegram_intake(_event(f"job {i}", 100 + i)) for i in range(3))
    )
    assert all(result.startswith("Queued") for result in first)
    restarted = SessionStore(session_store.config.sessions_dir, session_store.config)
    assert restarted.get_olympus_selection(key) == _selection(governed_board.root_id)
    runner = _runner(restarted)
    second = await asyncio.gather(
        *(runner._route_olympus_telegram_intake(_event(f"job {i}", 103 + i)) for i in range(3, 6))
    )
    assert all(result.startswith("Queued") for result in second)
    conn = governed_board.kb.connect(board="default")
    try:
        assert conn.execute("SELECT count(*) FROM olympus_telegram_deliveries").fetchone()[0] == 6
        assert conn.execute("SELECT count(*) FROM tasks WHERE id != ?", (governed_board.root_id,)).fetchone()[0] == 6
        statuses = conn.execute(
            "SELECT DISTINCT status FROM tasks WHERE id != ?",
            (governed_board.root_id,),
        ).fetchall()
    finally:
        conn.close()
    assert [row["status"] for row in statuses] == ["ready"]


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("action", "starting", "expected"),
    [("interrupt", "running", "blocked"), ("pause", "ready", "blocked"),
     ("resume", "blocked", "ready"), ("cancel", "ready", "archived")],
)
async def test_controls_are_atomic_exactly_once_and_audited(
    session_store, governed_board, action, starting, expected
):
    target_id = _create_target(governed_board, status=starting, title=action)
    runner = _runner(session_store)
    _set_selection(session_store, governed_board)
    event = _event(f"/olympus {action} {target_id}", 200)
    first = await runner._handle_olympus_command(event)
    second = await runner._handle_olympus_command(event)
    assert f"{action} applied to `{target_id}`" in first == second
    conn = governed_board.kb.connect(board="default")
    try:
        assert governed_board.kb.get_task(conn, target_id).status == expected
        events = [e for e in governed_board.kb.list_events(conn, target_id) if e.kind == "olympus_telegram_control"]
        comments = governed_board.kb.list_comments(conn, target_id)
        controls = conn.execute("SELECT count(*) FROM olympus_telegram_controls").fetchone()[0]
    finally:
        conn.close()
    assert len(events) == len(comments) == controls == 1


@pytest.mark.asyncio
async def test_duplicate_control_reverifies_the_identical_original_request(
    session_store, governed_board
):
    target_id = _create_target(governed_board, status="ready", title="replay")
    runner = _runner(session_store)
    _set_selection(session_store, governed_board)
    requests = []

    def record(request):
        requests.append(request)
        return _allow(request)

    runner._olympus_authority_verifier = record
    event = _event(f"/olympus pause {target_id}", 205)
    await runner._handle_olympus_command(event)
    await runner._handle_olympus_command(event)
    assert len(requests) == 2
    assert requests[0] == requests[1]


@pytest.mark.asyncio
async def test_emergency_capability_can_stop_stale_target_but_not_resume_it(
    session_store, governed_board
):
    target_id = _create_target(governed_board, status="running", title="stale")
    stale = _context(lease_status="REVOKED")
    conn = governed_board.kb.connect(board="default")
    try:
        conn.execute(
            "UPDATE tasks SET olympus_context = ? WHERE id = ?",
            (governed_board.kb._serialize_olympus_context(stale), target_id),
        )
        conn.commit()
    finally:
        conn.close()
    runner = _runner(session_store)
    _set_selection(session_store, governed_board)
    interrupt = await runner._handle_olympus_command(
        _event(f"/olympus interrupt {target_id}", 210)
    )
    assert "interrupt applied" in interrupt
    resume = await runner._handle_olympus_command(
        _event(f"/olympus resume {target_id}", 211)
    )
    assert "lease is revoked" in resume


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("action", "starting", "expected"),
    [("interrupt", "running", "blocked"), ("cancel", "ready", "archived")],
)
async def test_emergency_interrupt_and_cancel_accept_expired_target_lease(
    session_store, governed_board, action, starting, expected
):
    target_id = _create_target(
        governed_board, status=starting, title=f"expired-{action}"
    )
    expired = _context()
    expired["lease"]["expires_at"] = int(time.time()) - 1
    conn = governed_board.kb.connect(board="default")
    try:
        conn.execute(
            "UPDATE tasks SET olympus_context = ? WHERE id = ?",
            (governed_board.kb._serialize_olympus_context(expired), target_id),
        )
        conn.commit()
    finally:
        conn.close()
    runner = _runner(session_store)
    _set_selection(session_store, governed_board)
    result = await runner._handle_olympus_command(
        _event(f"/olympus {action} {target_id}", 213 if action == "interrupt" else 214)
    )
    assert f"{action} applied" in result

    # Reopen the database: terminal state and its exact audit must be durable.
    conn = governed_board.kb.connect(board="default")
    try:
        task = governed_board.kb.get_task(conn, target_id)
        comments = governed_board.kb.list_comments(conn, target_id)
        events = [
            event for event in governed_board.kb.list_events(conn, target_id)
            if event.kind == "olympus_telegram_control"
        ]
    finally:
        conn.close()
    assert task.status == expected
    assert len(comments) == len(events) == 1
    assert events[0].payload["action"] == action


@pytest.mark.asyncio
@pytest.mark.parametrize(("action", "status"), [("pause", "ready"), ("resume", "blocked")])
async def test_non_emergency_controls_deny_expired_target_lease(
    session_store, governed_board, action, status
):
    target_id = _create_target(
        governed_board, status=status, title=f"expired-{action}"
    )
    expired = _context()
    expired["lease"]["expires_at"] = int(time.time()) - 1
    conn = governed_board.kb.connect(board="default")
    try:
        conn.execute(
            "UPDATE tasks SET olympus_context = ? WHERE id = ?",
            (governed_board.kb._serialize_olympus_context(expired), target_id),
        )
        conn.commit()
    finally:
        conn.close()
    runner = _runner(session_store)
    _set_selection(session_store, governed_board)
    denied = await runner._handle_olympus_command(
        _event(f"/olympus {action} {target_id}", 215 if action == "pause" else 216)
    )
    assert "lease is expired" in denied


@pytest.mark.asyncio
async def test_control_capabilities_are_not_interchangeable(
    session_store, governed_board
):
    target_id = _create_target(governed_board, status="blocked", title="capability")
    limited = _context()
    limited["authority"]["capabilities"].remove(
        "telegram.olympus.control.resume"
    )
    conn = governed_board.kb.connect(board="default")
    try:
        conn.execute(
            "UPDATE tasks SET olympus_context = ? WHERE id = ?",
            (governed_board.kb._serialize_olympus_context(limited), governed_board.root_id),
        )
        conn.commit()
    finally:
        conn.close()
    runner = _runner(session_store)
    _set_selection(session_store, governed_board)
    denied = await runner._handle_olympus_command(
        _event(f"/olympus resume {target_id}", 212)
    )
    assert "required canonical capability is absent" in denied


@pytest.mark.asyncio
async def test_control_denies_foreign_mission_without_audit(
    session_store, governed_board
):
    foreign = _context(mission_id="M-20260713-foreign-test")
    target_id = _create_target(governed_board, context=foreign, title="foreign")
    runner = _runner(session_store)
    _set_selection(session_store, governed_board)
    denied = await runner._handle_olympus_command(
        _event(f"/olympus cancel {target_id}", 220)
    )
    assert "different Olympus mission" in denied
    conn = governed_board.kb.connect(board="default")
    try:
        assert governed_board.kb.list_comments(conn, target_id) == []
        assert conn.execute("SELECT count(*) FROM olympus_telegram_controls").fetchone()[0] == 0
    finally:
        conn.close()


def test_pending_termination_is_reconciled_after_reopen(governed_board):
    kb = governed_board.kb
    conn = kb.connect(board="default")
    try:
        conn.execute(
            "INSERT INTO olympus_telegram_controls "
            "(operation_id, action, authorization_task_id, target_task_id, source_identity, "
            "verification_id, result_status, termination_state, previous_worker_pid, "
            "previous_process_create_time, previous_claim_lock, created_at, updated_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            ("olympus-telegram-control:v2:recovery", "interrupt", governed_board.root_id,
             governed_board.root_id, json.dumps(_source_identity(), sort_keys=True, separators=(",", ":")),
             "verified:recovery", "blocked", "pending", 123, 100.5, "foreign-host:1", 1, 1),
        )
        conn.commit()
    finally:
        conn.close()
    calls = []
    conn = kb.connect(board="default")
    try:
        assert kb.reconcile_olympus_telegram_controls(
            conn,
            termination_fn=lambda pid, lock: calls.append((pid, lock)) or {"terminated": False},
            process_identity_reader=lambda pid: 100.5,
        ) == 1
        state = conn.execute(
            "SELECT termination_state FROM olympus_telegram_controls"
        ).fetchone()[0]
    finally:
        conn.close()
    assert calls == [(123, "foreign-host:1")]
    assert state == "applied"


def test_restart_pid_reuse_refuses_to_signal_unrelated_process(governed_board):
    kb = governed_board.kb
    target_id = _create_target(governed_board, status="blocked", title="pid-reuse")
    conn = kb.connect(board="default")
    try:
        conn.execute(
            "INSERT INTO olympus_telegram_controls "
            "(operation_id, action, authorization_task_id, target_task_id, source_identity, "
            "verification_id, result_status, termination_state, previous_worker_pid, "
            "previous_process_create_time, previous_claim_lock, created_at, updated_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            ("olympus-telegram-control:v2:pid-reuse", "interrupt", governed_board.root_id,
             target_id, json.dumps(_source_identity(), sort_keys=True, separators=(",", ":")),
             "verified:pid-reuse", "blocked", "pending", 456, 10.0, "local:456", 1, 1),
        )
        conn.commit()
    finally:
        conn.close()
    terminate = MagicMock(return_value={"terminated": True})
    conn = kb.connect(board="default")
    try:
        assert kb.reconcile_olympus_telegram_controls(
            conn,
            termination_fn=terminate,
            process_identity_reader=lambda pid: 20.0,
        ) == 1
        row = conn.execute(
            "SELECT termination_state FROM olympus_telegram_controls "
            "WHERE operation_id = 'olympus-telegram-control:v2:pid-reuse'"
        ).fetchone()
        task = kb.get_task(conn, target_id)
        audit = [
            event for event in kb.list_events(conn, target_id)
            if event.kind == "olympus_telegram_termination"
        ]
    finally:
        conn.close()
    terminate.assert_not_called()
    assert row["termination_state"] == "identity_mismatch"
    assert task.status == "blocked"
    assert audit[-1].payload["state"] == "identity_mismatch"


def test_restart_gone_process_is_stable_and_does_not_duplicate_audit(governed_board):
    kb = governed_board.kb
    target_id = _create_target(governed_board, status="blocked", title="pid-gone")
    conn = kb.connect(board="default")
    try:
        conn.execute(
            "INSERT INTO olympus_telegram_controls "
            "(operation_id, action, authorization_task_id, target_task_id, source_identity, "
            "verification_id, result_status, termination_state, previous_worker_pid, "
            "previous_process_create_time, previous_claim_lock, created_at, updated_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            ("olympus-telegram-control:v2:pid-gone", "interrupt", governed_board.root_id,
             target_id, json.dumps(_source_identity(), sort_keys=True, separators=(",", ":")),
             "verified:pid-gone", "blocked", "pending", 457, 10.0, "local:457", 1, 1),
        )
        conn.commit()
    finally:
        conn.close()
    terminate = MagicMock(return_value={"terminated": True})
    conn = kb.connect(board="default")
    try:
        kwargs = {
            "termination_fn": terminate,
            "process_identity_reader": lambda pid: None,
        }
        assert kb.reconcile_olympus_telegram_controls(conn, **kwargs) == 1
        assert kb.reconcile_olympus_telegram_controls(conn, **kwargs) == 0
        row = conn.execute(
            "SELECT termination_state FROM olympus_telegram_controls "
            "WHERE operation_id = 'olympus-telegram-control:v2:pid-gone'"
        ).fetchone()
        task = kb.get_task(conn, target_id)
        audit = [
            event for event in kb.list_events(conn, target_id)
            if event.kind == "olympus_telegram_termination"
        ]
    finally:
        conn.close()
    terminate.assert_not_called()
    assert row["termination_state"] == "identity_unverified"
    assert task.status == "blocked"
    assert len(audit) == 1


def test_concurrent_reconciliation_signals_exactly_once(governed_board):
    kb = governed_board.kb
    target_id = _create_target(governed_board, status="blocked", title="reconcile-race")
    operation_id = "olympus-telegram-control:v2:reconcile-race"
    conn = kb.connect(board="default")
    try:
        conn.execute(
            "INSERT INTO olympus_telegram_controls "
            "(operation_id, action, authorization_task_id, target_task_id, source_identity, "
            "verification_id, result_status, termination_state, previous_worker_pid, "
            "previous_process_create_time, previous_claim_lock, created_at, updated_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (operation_id, "interrupt", governed_board.root_id, target_id,
             json.dumps(_source_identity(), sort_keys=True, separators=(",", ":")),
             "verified:race", "blocked", "pending", 458, 10.0, "local:458", 1, 1),
        )
        conn.commit()
    finally:
        conn.close()
    calls = []

    def finish():
        connection = kb.connect(board="default")
        try:
            return kb._finish_olympus_control_termination(
                connection,
                operation_id,
                termination_fn=lambda pid, lock: calls.append((pid, lock)) or {"terminated": True},
                process_identity_reader=lambda pid: 10.0,
            )
        finally:
            connection.close()

    with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(lambda _: finish(), range(2)))
    conn = kb.connect(board="default")
    try:
        audit = [
            event for event in kb.list_events(conn, target_id)
            if event.kind == "olympus_telegram_termination"
        ]
    finally:
        conn.close()
    assert calls == [(458, "local:458")]
    assert {result["state"] for result in results} == {"applied"}
    assert len(audit) == 1


def test_missing_process_identity_blocks_task_without_signaling(governed_board):
    kb = governed_board.kb
    target_id = _create_target(governed_board, status="running", title="no-identity")
    terminate = MagicMock(return_value={"terminated": True})
    conn = kb.connect(board="default")
    try:
        conn.execute(
            "UPDATE tasks SET worker_pid = 789, claim_lock = 'local:789' WHERE id = ?",
            (target_id,),
        )
        conn.commit()
        result = kb.apply_olympus_telegram_control(
            conn,
            authorization_task_id=governed_board.root_id,
            target_task_id=target_id,
            action="interrupt",
            authority_verifier=_allow,
            source_identity=_source_identity(),
            operation_id="olympus-telegram-control:v2:no-identity",
            expected_revision=governed_board.context["authority"]["revision"],
            operator_tag="telegram:test",
            termination_fn=terminate,
            process_identity_reader=lambda pid: None,
        )
        state = conn.execute(
            "SELECT termination_state FROM olympus_telegram_controls "
            "WHERE operation_id = 'olympus-telegram-control:v2:no-identity'"
        ).fetchone()[0]
        task = kb.get_task(conn, target_id)
    finally:
        conn.close()
    terminate.assert_not_called()
    assert result["status"] == task.status == "blocked"
    assert state == "identity_unverified"


@pytest.mark.asyncio
async def test_busy_selected_message_never_interrupts_active_agent(session_store):
    runner = _runner(session_store)
    agent = MagicMock()
    key = runner._session_key_for_source(_source())
    runner._running_agents[key] = agent
    runner._route_olympus_telegram_intake = AsyncMock(return_value="Queued `t_abc12345`")
    adapter = MagicMock()
    adapter._send_with_retry = AsyncMock()
    runner.adapters[Platform.TELEGRAM] = adapter
    assert await runner._handle_active_session_busy_message(_event("new work", 300), key)
    agent.interrupt.assert_not_called()


@pytest.mark.asyncio
async def test_telegram_background_requires_durable_or_explicit_ephemeral(session_store):
    runner = _runner(session_store)
    assert "requires an Olympus selection" in await runner._handle_background_command(
        _event("/background research this", 310)
    )
    runner._run_background_task = AsyncMock()
    assert "Background task started" in await runner._handle_background_command(
        _event("/background --ephemeral research this", 311)
    )


def test_olympus_command_bypasses_active_session_guard():
    from hermes_cli.commands import should_bypass_active_session

    assert should_bypass_active_session("olympus") is True
