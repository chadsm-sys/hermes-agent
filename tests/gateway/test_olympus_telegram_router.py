"""Exact v3 authority, delivery, control, and restart contracts for Telegram."""

from __future__ import annotations

import asyncio
import copy
import hashlib
import json
import sqlite3
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
DISPATCHER = "telegram-test-dispatcher"


def _allow_at(request: dict, now: float) -> dict:
    from hermes_cli import kanban_db as kb

    emergency = request["action"] in kb.TELEGRAM_EMERGENCY_ACTIONS
    subjects = [request["authorization_root"]] if emergency else [request["target"]]
    if not emergency and request["authorization_root"] is not None:
        subjects.append(request["authorization_root"])
    expiry = min(
        value
        for subject in subjects
        for value in (
            subject["authority"]["expires_at"],
            subject["lease"]["expires_at"],
        )
    )
    return {
        "schema_version": kb.AUTHORITY_VERIFICATION_SCHEMA,
        "verification_id": f"verification:{request['request_id'].split(':', 1)[1]}",
        "decision": "ALLOW",
        "current": True,
        "verified_at": now - 1,
        "valid_until": min(now + 60, expiry),
        "verified_principal": copy.deepcopy(request["principal"]),
        "verified_actor": request["actor"],
        "request_id": request["request_id"],
        "request": copy.deepcopy(request),
        "target_verification": {
            "authority_current": not emergency,
            "containment_target": emergency,
            "subject": copy.deepcopy(request["target"]),
        },
        "authorization_root_verification": (
            None
            if request["authorization_root"] is None
            else {
                "authority_current": True,
                "containment_target": False,
                "subject": copy.deepcopy(request["authorization_root"]),
            }
        ),
    }


def _allow(request: dict) -> dict:
    return _allow_at(request, time.time())


def _source(
    *,
    chat_id: str = "1001",
    user_id: str = "operator-1",
    thread_id: str | None = None,
):
    return SessionSource(
        platform=Platform.TELEGRAM,
        chat_id=chat_id,
        user_id=user_id,
        thread_id=thread_id,
        chat_type="dm",
    )


def _event(
    text: str,
    update_id: int,
    *,
    chat_id: str = "1001",
    user_id: str = "operator-1",
    thread_id: str | None = None,
) -> MessageEvent:
    return MessageEvent(
        text=text,
        message_type=MessageType.TEXT,
        source=_source(
            chat_id=chat_id, user_id=user_id, thread_id=thread_id
        ),
        message_id=str(update_id),
        platform_update_id=update_id,
    )


def _context(
    *,
    mission_id: str = MISSION_ID,
    agent_id: str = "coding",
    authority_status: str = "ACTIVE",
    lease_status: str = "ACTIVE",
) -> dict:
    from hermes_cli import kanban_db as kb

    expires = int(time.time()) + 3600
    return {
        "schema_version": 2,
        "goal_id": f"goal:{mission_id}",
        "program_id": f"program:{mission_id}",
        "milestone_id": f"milestone:{mission_id}",
        "mission_id": mission_id,
        "workstream_id": f"workstream:{mission_id}",
        "authority": {
            "authority_id": f"authority:{mission_id}",
            "status": authority_status,
            "scope": [mission_id],
            "capabilities": sorted(set(kb.KANBAN_TASK_ACTION_CAPABILITIES.values())),
            "revision": 7,
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
            "revision": 11,
            "source": "issuer:test",
            "expires_at": expires,
        },
        "risk": "high",
        "agent_id": agent_id,
        "review_status": "pending",
        "evidence_refs": ["evidence://telegram/test"],
    }


def _source_identity(
    *,
    chat_id: str = "1001",
    user_id: str = "operator-1",
    thread_id: str | None = None,
) -> dict[str, str]:
    return {
        "platform": "telegram",
        "bot_id": BOT_ID,
        "profile": PROFILE,
        "chat_id": chat_id,
        "thread_id": thread_id or "",
        "user_id": user_id,
    }


def _digest(value) -> str:
    raw = json.dumps(value, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(raw).hexdigest()


def _service_auth(conn, context: dict, operation_id: str):
    from hermes_cli import kanban_db as kb

    return kb.olympus_service_auth(
        conn,
        verifier=_allow,
        dispatcher_instance_id=DISPATCHER,
        actor=context["agent_id"],
        operation_id=operation_id,
    )


def _create_governed(
    conn,
    context: dict,
    *,
    title: str,
    initial_status: str = "running",
) -> str:
    from hermes_cli import kanban_db as kb

    return kb.create_olympus_task(
        conn,
        olympus_context=context,
        olympus_auth=_service_auth(conn, context, f"create:{title}:{time.time_ns()}"),
        title=title,
        assignee=context["agent_id"],
        created_by="test",
        initial_status=initial_status,
    )


def _selection(
    root_id: str,
    context: dict,
    *,
    source_identity: dict[str, str] | None = None,
) -> dict:
    authority = context["authority"]
    lease = context["lease"]
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
        "caller_fingerprint": _digest(source_identity or _source_identity()),
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
    runner._kanban_olympus_authority_verifier = _allow
    runner._kanban_dispatcher_instance_id = DISPATCHER
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

    db_path = tmp_path / "kanban.db"
    monkeypatch.setenv("HERMES_KANBAN_DB", str(db_path))
    kb._INITIALIZED_PATHS.discard(str(db_path.resolve()))
    context = _context()
    conn = kb.connect(board="default")
    try:
        root_id = _create_governed(conn, context, title="Telegram root")
    finally:
        conn.close()
    return SimpleNamespace(kb=kb, root_id=root_id, context=context)


def _set_selection(
    store: SessionStore,
    board,
    *,
    source: SessionSource | None = None,
) -> str:
    source = source or _source()
    entry = store.get_or_create_session(source)
    identity = _source_identity(
        chat_id=str(source.chat_id),
        user_id=str(source.user_id),
        thread_id=source.thread_id,
    )
    assert store.set_olympus_selection(
        entry.session_key,
        _selection(
            board.root_id, board.context, source_identity=identity
        ),
    )
    return entry.session_key


def _create_direct_telegram_delivery(
    conn,
    board,
    *,
    update_id: int = 700,
    delivery_identity_overrides: dict | None = None,
    delivery_key: str | None = None,
    destination_overrides: dict | None = None,
):
    kb = board.kb
    source = _source_identity()
    identity = {
        "platform": "telegram",
        "bot_id": BOT_ID,
        "profile": PROFILE,
        "update_id": update_id,
    }
    identity.update(delivery_identity_overrides or {})
    telegram_auth = kb.olympus_telegram_auth(
        conn,
        verifier=_allow,
        source_identity=source,
        authorization_task_id=board.root_id,
        target_task_id=board.root_id,
        action="telegram-intake",
        operation_id=f"direct-intake:{update_id}",
    )
    service_auth = kb.olympus_service_auth(
        conn,
        verifier=_allow,
        dispatcher_instance_id=DISPATCHER,
        actor=board.context["agent_id"],
        operation_id=f"direct-intake:{update_id}:service",
    )
    destination = {
        "platform": source["platform"],
        "chat_id": source["chat_id"],
        "thread_id": source["thread_id"] or None,
        "user_id": source["user_id"],
        "notifier_profile": source["profile"],
    }
    destination.update(destination_overrides or {})
    return kb.create_olympus_telegram_task(
        conn,
        telegram_auth=telegram_auth,
        service_auth=service_auth,
        delivery_key=(
            delivery_key
            if delivery_key is not None
            else f"olympus-telegram:v3:{_digest(identity)}"
        ),
        delivery_identity=identity,
        title=f"direct delivery {update_id}",
        body="exact destination",
        assignee=board.context["agent_id"],
        created_by="test",
        session_id="session-direct",
        board="default",
        **destination,
    )


def _install_pre_v3_telegram_tables(conn, root_task_id: str) -> None:
    conn.execute("DROP TABLE olympus_telegram_deliveries")
    conn.execute("DROP TABLE olympus_telegram_controls")
    conn.execute(
        "CREATE TABLE olympus_telegram_deliveries ("
        "delivery_key TEXT PRIMARY KEY, task_id TEXT NOT NULL UNIQUE, "
        "immutable_context TEXT NOT NULL, created_at INTEGER NOT NULL)"
    )
    conn.execute(
        "INSERT INTO olympus_telegram_deliveries VALUES (?,?,?,?)",
        ("olympus-telegram:v1:legacy", "t_legacy", "{}", 1),
    )
    conn.execute(
        "CREATE TABLE olympus_telegram_controls ("
        "operation_id TEXT PRIMARY KEY, action TEXT NOT NULL, "
        "authorization_task_id TEXT NOT NULL, target_task_id TEXT NOT NULL, "
        "source_identity TEXT NOT NULL, target_identity TEXT NOT NULL, "
        "verification_id TEXT NOT NULL, result_status TEXT NOT NULL, "
        "termination_state TEXT NOT NULL, previous_worker_pid INTEGER, "
        "previous_process_create_time REAL, previous_claim_lock TEXT, "
        "termination_result TEXT, created_at INTEGER NOT NULL, "
        "updated_at INTEGER NOT NULL)"
    )
    conn.execute(
        "INSERT INTO olympus_telegram_controls VALUES "
        "(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
        (
            "olympus-telegram-control:v1:legacy", "interrupt",
            root_task_id, "t_legacy", "{}", "{}", "v1", "blocked",
            "pending", 4242, 1.0, "claim:v1", None, 1, 1,
        ),
    )


def test_selection_survives_reload_and_rejects_legacy(session_store, governed_board):
    key = _set_selection(session_store, governed_board)
    reloaded = SessionStore(session_store.config.sessions_dir, session_store.config)
    assert reloaded.get_olympus_selection(key) == _selection(
        governed_board.root_id, governed_board.context
    )
    with pytest.raises(ValueError, match="schema_version must be 2"):
        reloaded.set_olympus_selection(
            key, {"schema_version": 1, "board": "default", "root_task_id": "t_bad"}
        )


def test_restart_preserves_pre_v3_wip_journals_without_executing_them(
    governed_board,
):
    kb = governed_board.kb
    db_path = kb.kanban_db_path(board="default")
    conn = kb.connect(board="default")
    try:
        conn.execute("DROP TABLE olympus_telegram_deliveries")
        conn.execute("DROP TABLE olympus_telegram_controls")
        conn.execute(
            "CREATE TABLE olympus_telegram_deliveries ("
            "delivery_key TEXT PRIMARY KEY, task_id TEXT NOT NULL UNIQUE, "
            "immutable_context TEXT NOT NULL, created_at INTEGER NOT NULL)"
        )
        conn.execute(
            "INSERT INTO olympus_telegram_deliveries VALUES (?,?,?,?)",
            ("olympus-telegram:v1:legacy", "t_legacy", "{}", 1),
        )
        conn.execute(
            "CREATE TABLE olympus_telegram_controls ("
            "operation_id TEXT PRIMARY KEY, action TEXT NOT NULL, "
            "authorization_task_id TEXT NOT NULL, target_task_id TEXT NOT NULL, "
            "source_identity TEXT NOT NULL, target_identity TEXT NOT NULL, "
            "verification_id TEXT NOT NULL, result_status TEXT NOT NULL, "
            "termination_state TEXT NOT NULL, previous_worker_pid INTEGER, "
            "previous_process_create_time REAL, previous_claim_lock TEXT, "
            "termination_result TEXT, created_at INTEGER NOT NULL, "
            "updated_at INTEGER NOT NULL)"
        )
        conn.execute(
            "INSERT INTO olympus_telegram_controls VALUES "
            "(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (
                "olympus-telegram-control:v1:legacy", "interrupt",
                governed_board.root_id, "t_legacy", "{}", "{}", "v1",
                "blocked", "pending", 4242, 1.0, "claim:v1", None, 1, 1,
            ),
        )
    finally:
        conn.close()

    kb._INITIALIZED_PATHS.discard(str(db_path.resolve()))
    reopened = kb.connect(board="default")
    try:
        assert reopened.execute(
            "SELECT immutable_context FROM "
            "olympus_telegram_deliveries_legacy_pre_v3 "
            "WHERE delivery_key='olympus-telegram:v1:legacy'"
        ).fetchone()[0] == "{}"
        assert reopened.execute(
            "SELECT previous_worker_pid FROM "
            "olympus_telegram_controls_legacy_pre_v3 "
            "WHERE operation_id='olympus-telegram-control:v1:legacy'"
        ).fetchone()[0] == 4242
        assert reopened.execute(
            "SELECT count(*) FROM olympus_telegram_deliveries"
        ).fetchone()[0] == 0
        assert reopened.execute(
            "SELECT count(*) FROM olympus_telegram_controls"
        ).fetchone()[0] == 0
    finally:
        reopened.close()


@pytest.mark.parametrize(
    "failed_table",
    ("olympus_telegram_deliveries", "olympus_telegram_controls"),
)
def test_interrupted_pre_v3_migration_rolls_back_then_reopens_idempotently(
    governed_board, failed_table
):
    kb = governed_board.kb
    db_path = kb.kanban_db_path(board="default")
    conn = kb.connect(board="default")
    try:
        _install_pre_v3_telegram_tables(conn, governed_board.root_id)
    finally:
        conn.close()

    def interrupt(table: str) -> None:
        if table == failed_table:
            raise RuntimeError(f"migration crash:{table}")

    kb._INITIALIZED_PATHS.discard(str(db_path.resolve()))
    kb._OLYMPUS_TELEGRAM_MIGRATION_FAILPOINT = interrupt
    try:
        with pytest.raises(RuntimeError, match="migration crash"):
            kb.connect(board="default")
    finally:
        kb._OLYMPUS_TELEGRAM_MIGRATION_FAILPOINT = None
    raw = sqlite3.connect(db_path)
    try:
        failed_columns = {
            row[1] for row in raw.execute(f"PRAGMA table_info({failed_table})")
        }
        assert (
            "immutable_context" in failed_columns
            if failed_table == "olympus_telegram_deliveries"
            else "termination_state" in failed_columns
        )
        assert raw.execute(
            f"SELECT count(*) FROM {failed_table}"
        ).fetchone()[0] == 1
        assert raw.execute(
            "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?",
            (f"{failed_table}_legacy_pre_v3",),
        ).fetchone() is None
    finally:
        raw.close()

    kb._INITIALIZED_PATHS.discard(str(db_path.resolve()))
    migrated = kb.connect(board="default")
    migrated.close()
    kb._INITIALIZED_PATHS.discard(str(db_path.resolve()))
    reopened = kb.connect(board="default")
    try:
        assert reopened.execute(
            "SELECT count(*) FROM olympus_telegram_deliveries_legacy_pre_v3"
        ).fetchone()[0] == 1
        assert reopened.execute(
            "SELECT count(*) FROM olympus_telegram_controls_legacy_pre_v3"
        ).fetchone()[0] == 1
        assert reopened.execute(
            "SELECT count(*) FROM olympus_telegram_deliveries"
        ).fetchone()[0] == 0
        assert reopened.execute(
            "SELECT count(*) FROM olympus_telegram_controls"
        ).fetchone()[0] == 0
        with pytest.raises(sqlite3.IntegrityError, match="authority"):
            reopened.execute(
                "INSERT INTO olympus_telegram_deliveries VALUES "
                "(?,?,?,?,?,?,?)",
                (
                    "olympus-telegram:v3:" + "8" * 64,
                    governed_board.root_id,
                    1,
                    "t_88888888",
                    "{}",
                    "8" * 64,
                    8,
                ),
            )
        reopened.rollback()
        with pytest.raises(sqlite3.IntegrityError, match="authority"):
            reopened.execute(
                "INSERT INTO olympus_telegram_controls VALUES "
                "(?,?,?,?,?,?,?,?,?,?,?,?,?)",
                (
                    "olympus-telegram-control:v3:" + "9" * 64,
                    "telegram-control:pause",
                    governed_board.root_id,
                    1,
                    governed_board.root_id,
                    1,
                    "{}",
                    "{}",
                    "9" * 64,
                    "forged",
                    "blocked",
                    None,
                    9,
                ),
            )
        reopened.rollback()

        _create_direct_telegram_delivery(
            reopened, governed_board, update_id=8090
        )
        target_id = _create_governed(
            reopened,
            governed_board.context,
            title=f"migration-guard-{failed_table}",
        )
        control_auth = kb.olympus_telegram_auth(
            reopened,
            verifier=_allow,
            source_identity=_source_identity(),
            authorization_task_id=governed_board.root_id,
            target_task_id=target_id,
            action="telegram-control:pause",
            operation_id="olympus-telegram-control:v3:" + "a" * 64,
        )
        kb.apply_olympus_telegram_control(
            reopened,
            telegram_auth=control_auth,
            service_auth=_service_auth(
                reopened, governed_board.context, "migration-guard:service"
            ),
            target_task_id=target_id,
            action="pause",
            operator_tag="telegram:migration-guard",
        )
        delivery_key = reopened.execute(
            "SELECT delivery_key FROM olympus_telegram_deliveries"
        ).fetchone()[0]
        control_id = reopened.execute(
            "SELECT operation_id FROM olympus_telegram_controls"
        ).fetchone()[0]
        for statement, params in (
            (
                "UPDATE olympus_telegram_deliveries SET payload='{}' "
                "WHERE delivery_key=?",
                (delivery_key,),
            ),
            (
                "DELETE FROM olympus_telegram_deliveries WHERE delivery_key=?",
                (delivery_key,),
            ),
            (
                "UPDATE olympus_telegram_controls SET result_status='ready' "
                "WHERE operation_id=?",
                (control_id,),
            ),
            (
                "DELETE FROM olympus_telegram_controls WHERE operation_id=?",
                (control_id,),
            ),
        ):
            with pytest.raises(sqlite3.DatabaseError):
                reopened.execute(statement, params)
            reopened.rollback()
    finally:
        reopened.close()


@pytest.mark.parametrize(
    "collision_table",
    ("olympus_telegram_deliveries", "olympus_telegram_controls"),
)
def test_pre_v3_preservation_name_collision_fails_closed_without_data_loss(
    governed_board, collision_table
):
    kb = governed_board.kb
    db_path = kb.kanban_db_path(board="default")
    conn = kb.connect(board="default")
    try:
        _install_pre_v3_telegram_tables(conn, governed_board.root_id)
        legacy = f"{collision_table}_legacy_pre_v3"
        conn.execute(f"CREATE TABLE {legacy} (marker TEXT NOT NULL)")
        conn.execute(
            f"INSERT INTO {legacy} VALUES ('collision-evidence')"
        )
    finally:
        conn.close()
    kb._INITIALIZED_PATHS.discard(str(db_path.resolve()))
    with pytest.raises(sqlite3.IntegrityError, match="already exists"):
        kb.connect(board="default")
    raw = sqlite3.connect(db_path)
    try:
        current_columns = {
            row[1] for row in raw.execute(
                f"PRAGMA table_info({collision_table})"
            )
        }
        assert (
            "immutable_context" in current_columns
            if collision_table == "olympus_telegram_deliveries"
            else "termination_state" in current_columns
        )
        assert raw.execute(
            f"SELECT count(*) FROM {collision_table}"
        ).fetchone()[0] == 1
        assert raw.execute(
            f"SELECT marker FROM {collision_table}_legacy_pre_v3"
        ).fetchone()[0] == "collision-evidence"
        other = (
            "olympus_telegram_controls"
            if collision_table == "olympus_telegram_deliveries"
            else "olympus_telegram_deliveries_legacy_pre_v3"
        )
        assert raw.execute(f"SELECT count(*) FROM {other}").fetchone()[0] == 1
    finally:
        raw.close()


@pytest.mark.asyncio
async def test_select_status_clear_require_v3_verifier(session_store, governed_board):
    runner = _runner(session_store)
    selected = await runner._handle_olympus_command(
        _event(f"/olympus select {governed_board.root_id}", 1)
    )
    assert "durable intake selected" in selected
    assert "authority current" in await runner._handle_olympus_command(
        _event("/olympus status", 2)
    )
    runner._kanban_olympus_authority_verifier = None
    denied = await runner._handle_olympus_command(_event("/olympus clear", 3))
    assert "canonical authority verifier is unavailable" in denied
    assert runner._olympus_selection_for_event(_event("status", 4)) is not None


@pytest.mark.asyncio
async def test_clear_cas_preserves_concurrent_replacement(
    session_store, governed_board, monkeypatch
):
    runner = _runner(session_store)
    key = _set_selection(session_store, governed_board)
    captured = session_store.get_olympus_selection(key)
    replacement = dict(captured)
    replacement["root_task_id"] = "t_deadbeef"
    original_verify = runner._verify_olympus_root

    def replace_during_verification(*args, **kwargs):
        result = original_verify(*args, **kwargs)
        assert session_store.set_olympus_selection(key, replacement)
        return result

    monkeypatch.setattr(
        runner, "_verify_olympus_root", replace_during_verification
    )
    result = await runner._handle_olympus_command(_event("/olympus clear", 5))
    assert "selection changed" in result
    assert session_store.get_olympus_selection(key) == replacement


@pytest.mark.asyncio
async def test_source_and_selection_identity_conflicts_fail_closed(
    session_store, governed_board
):
    runner = _runner(session_store)
    _set_selection(session_store, governed_board)
    runner.adapters[Platform.TELEGRAM]._bot.id = 9002
    assert "wrong-source" in await runner._route_olympus_telegram_intake(
        _event("job", 10)
    )
    runner.adapters[Platform.TELEGRAM]._bot.id = int(BOT_ID)
    with pytest.raises(ValueError, match="caller-conflicted"):
        runner._validate_olympus_selection_binding(
            _selection(governed_board.root_id, governed_board.context),
            governed_board.context,
            _source_identity(user_id="foreign"),
        )


@pytest.mark.parametrize(
    ("identity_overrides", "destination_overrides", "forced_key"),
    (
        ({"bot_id": "foreign-bot"}, None, None),
        ({"profile": "foreign-profile"}, None, None),
        ({"platform": "webhook"}, None, None),
        (None, {"chat_id": "unrelated-chat"}, None),
        (None, {"thread_id": "unrelated-thread"}, None),
        (None, {"user_id": "unrelated-user"}, None),
        (None, {"notifier_profile": "unrelated-profile"}, None),
        (None, None, "olympus-telegram:v3:" + "0" * 64),
    ),
)
def test_delivery_and_destination_containment_matrix(
    governed_board, identity_overrides, destination_overrides, forced_key
):
    conn = governed_board.kb.connect(board="default")
    try:
        with pytest.raises(
            governed_board.kb.OlympusContextError,
            match="delivery|notification|authenticated",
        ):
            _create_direct_telegram_delivery(
                conn,
                governed_board,
                update_id=701,
                delivery_identity_overrides=identity_overrides,
                destination_overrides=destination_overrides,
                delivery_key=forced_key,
            )
        assert conn.execute(
            "SELECT count(*) FROM olympus_telegram_deliveries"
        ).fetchone()[0] == 0
        assert conn.execute(
            "SELECT count(*) FROM tasks WHERE id != ?", (governed_board.root_id,)
        ).fetchone()[0] == 0
        assert conn.execute(
            "SELECT count(*) FROM kanban_notify_subs"
        ).fetchone()[0] == 0
    finally:
        conn.close()


@pytest.mark.asyncio
async def test_duplicate_concurrent_delivery_is_one_atomic_task_and_subscription(
    session_store, governed_board
):
    runner = _runner(session_store)
    _set_selection(session_store, governed_board)
    event = _event("Investigate durable routing", 44)
    results = await asyncio.gather(
        *(runner._route_olympus_telegram_intake(event) for _ in range(6))
    )
    assert len(set(results)) == 1
    conn = governed_board.kb.connect(board="default")
    try:
        assert conn.execute(
            "SELECT count(*) FROM olympus_telegram_deliveries"
        ).fetchone()[0] == 1
        assert conn.execute(
            "SELECT count(*) FROM tasks WHERE id != ?", (governed_board.root_id,)
        ).fetchone()[0] == 1
        assert conn.execute(
            "SELECT count(*) FROM kanban_notify_subs"
        ).fetchone()[0] == 1
        assert conn.execute(
            "SELECT count(*) FROM kanban_olympus_create_receipts"
        ).fetchone()[0] == 1
    finally:
        conn.close()


@pytest.mark.asyncio
async def test_delivery_payload_collision_is_denied(session_store, governed_board):
    runner = _runner(session_store)
    _set_selection(session_store, governed_board)
    assert (await runner._route_olympus_telegram_intake(
        _event("first", 45)
    )).startswith("Queued")
    denied = await runner._route_olympus_telegram_intake(_event("changed", 45))
    assert "immutable" in denied or "payload" in denied


@pytest.mark.asyncio
async def test_subscription_failure_rolls_back_delivery_and_task(
    session_store, governed_board, monkeypatch
):
    runner = _runner(session_store)
    _set_selection(session_store, governed_board)
    original_add = governed_board.kb.add_notify_sub
    monkeypatch.setattr(
        governed_board.kb,
        "add_notify_sub",
        lambda *args, **kwargs: (_ for _ in ()).throw(RuntimeError("subscription crash")),
    )
    denied = await runner._route_olympus_telegram_intake(_event("atomic", 46))
    assert "subscription crash" in denied
    conn = governed_board.kb.connect(board="default")
    try:
        assert conn.execute(
            "SELECT count(*) FROM olympus_telegram_deliveries"
        ).fetchone()[0] == 0
        assert conn.execute(
            "SELECT count(*) FROM tasks WHERE id != ?", (governed_board.root_id,)
        ).fetchone()[0] == 0
    finally:
        conn.close()
    monkeypatch.setattr(governed_board.kb, "add_notify_sub", original_add)
    assert (await runner._route_olympus_telegram_intake(
        _event("atomic", 46)
    )).startswith("Queued")
    reopened = governed_board.kb.connect(board="default")
    try:
        assert reopened.execute(
            "SELECT count(*) FROM olympus_telegram_deliveries"
        ).fetchone()[0] == 1
        assert reopened.execute(
            "SELECT count(*) FROM kanban_olympus_create_receipts"
        ).fetchone()[0] == 1
        assert reopened.execute(
            "SELECT count(*) FROM kanban_notify_subs"
        ).fetchone()[0] == 1
    finally:
        reopened.close()


@pytest.mark.asyncio
async def test_three_then_six_durable_submissions_survive_reopen(
    session_store, governed_board
):
    runner = _runner(session_store)
    key = _set_selection(session_store, governed_board)
    first = await asyncio.gather(
        *(runner._route_olympus_telegram_intake(_event(f"job {i}", 100 + i)) for i in range(3))
    )
    assert all(result.startswith("Queued") for result in first)
    restarted = SessionStore(session_store.config.sessions_dir, session_store.config)
    assert restarted.get_olympus_selection(key) is not None
    runner = _runner(restarted)
    second = await asyncio.gather(
        *(
            runner._route_olympus_telegram_intake(
                _event(f"job {i}", 100 + i)
            )
            for i in range(3, 9)
        )
    )
    assert all(result.startswith("Queued") for result in second)
    conn = governed_board.kb.connect(board="default")
    try:
        assert conn.execute(
            "SELECT count(*) FROM olympus_telegram_deliveries"
        ).fetchone()[0] == 9
        assert conn.execute(
            "SELECT count(DISTINCT delivery_key) "
            "FROM olympus_telegram_deliveries"
        ).fetchone()[0] == 9
        assert conn.execute("PRAGMA integrity_check").fetchone()[0] == "ok"
    finally:
        conn.close()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("action", "starting", "expected"),
    [("pause", "ready", "blocked"), ("resume", "blocked", "ready"), ("cancel", "ready", "archived")],
)
async def test_nonrunning_controls_are_exactly_once(
    session_store, governed_board, action, starting, expected
):
    conn = governed_board.kb.connect(board="default")
    try:
        target_id = _create_governed(
            conn,
            governed_board.context,
            title=f"control-{action}",
            initial_status="blocked" if starting == "blocked" else "running",
        )
    finally:
        conn.close()
    runner = _runner(session_store)
    _set_selection(session_store, governed_board)
    event = _event(f"/olympus {action} {target_id}", 200)
    first = await runner._handle_olympus_command(event)
    second = await runner._handle_olympus_command(event)
    assert first == second
    assert f"status is `{expected}`" in first
    conn = governed_board.kb.connect(board="default")
    try:
        assert governed_board.kb.get_task(conn, target_id).status == expected
        assert conn.execute(
            "SELECT count(*) FROM olympus_telegram_controls"
        ).fetchone()[0] == 1
        events = [
            event
            for event in governed_board.kb.list_events(conn, target_id)
            if event.kind == "olympus_telegram_control"
        ]
        assert len(events) == 1
    finally:
        conn.close()


@pytest.mark.asyncio
async def test_concurrent_duplicate_control_serializes_to_one_receipt(
    session_store, governed_board
):
    conn = governed_board.kb.connect(board="default")
    try:
        target_id = _create_governed(
            conn, governed_board.context, title="concurrent-pause"
        )
    finally:
        conn.close()
    runner = _runner(session_store)
    _set_selection(session_store, governed_board)
    event = _event(f"/olympus pause {target_id}", 201)
    results = await asyncio.gather(
        *(runner._handle_olympus_command(event) for _ in range(6))
    )
    assert len(set(results)) == 1
    assert "status is `blocked`" in results[0]
    conn = governed_board.kb.connect(board="default")
    try:
        assert conn.execute(
            "SELECT count(*) FROM olympus_telegram_controls"
        ).fetchone()[0] == 1
        assert governed_board.kb.get_task(conn, target_id).status == "blocked"
    finally:
        conn.close()


@pytest.mark.asyncio
async def test_control_operation_id_collision_cannot_change_action_or_target(
    session_store, governed_board
):
    conn = governed_board.kb.connect(board="default")
    try:
        first_id = _create_governed(
            conn, governed_board.context, title="collision-first"
        )
        second_id = _create_governed(
            conn, governed_board.context, title="collision-second"
        )
    finally:
        conn.close()
    runner = _runner(session_store)
    _set_selection(session_store, governed_board)
    assert "status is `blocked`" in await runner._handle_olympus_command(
        _event(f"/olympus pause {first_id}", 202)
    )
    denied = await runner._handle_olympus_command(
        _event(f"/olympus cancel {second_id}", 202)
    )
    assert "identity belongs to another" in denied
    conn = governed_board.kb.connect(board="default")
    try:
        assert conn.execute(
            "SELECT count(*) FROM olympus_telegram_controls"
        ).fetchone()[0] == 1
        assert governed_board.kb.get_task(conn, first_id).status == "blocked"
        assert governed_board.kb.get_task(conn, second_id).status == "ready"
    finally:
        conn.close()


@pytest.mark.asyncio
async def test_control_operation_collision_changed_action_only(
    session_store, governed_board
):
    conn = governed_board.kb.connect(board="default")
    try:
        target_id = _create_governed(
            conn, governed_board.context, title="collision-action"
        )
    finally:
        conn.close()
    runner = _runner(session_store)
    _set_selection(session_store, governed_board)
    assert "status is `blocked`" in await runner._handle_olympus_command(
        _event(f"/olympus pause {target_id}", 2021)
    )
    denied = await runner._handle_olympus_command(
        _event(f"/olympus resume {target_id}", 2021)
    )
    assert "identity belongs to another" in denied


@pytest.mark.asyncio
async def test_control_operation_collision_changed_target_only(
    session_store, governed_board
):
    conn = governed_board.kb.connect(board="default")
    try:
        first_id = _create_governed(
            conn, governed_board.context, title="collision-target-first"
        )
        second_id = _create_governed(
            conn, governed_board.context, title="collision-target-second"
        )
    finally:
        conn.close()
    runner = _runner(session_store)
    _set_selection(session_store, governed_board)
    assert "status is `blocked`" in await runner._handle_olympus_command(
        _event(f"/olympus pause {first_id}", 2022)
    )
    denied = await runner._handle_olympus_command(
        _event(f"/olympus pause {second_id}", 2022)
    )
    assert "identity belongs to another" in denied
    conn = governed_board.kb.connect(board="default")
    try:
        assert governed_board.kb.get_task(conn, second_id).status == "ready"
    finally:
        conn.close()


@pytest.mark.asyncio
async def test_control_operation_collision_changed_source_only(
    session_store, governed_board
):
    conn = governed_board.kb.connect(board="default")
    try:
        target_id = _create_governed(
            conn, governed_board.context, title="collision-source"
        )
    finally:
        conn.close()
    runner = _runner(session_store)
    _set_selection(session_store, governed_board)
    assert "status is `blocked`" in await runner._handle_olympus_command(
        _event(f"/olympus pause {target_id}", 2023)
    )
    foreign_source = _source(user_id="operator-2")
    _set_selection(session_store, governed_board, source=foreign_source)
    denied = await runner._handle_olympus_command(
        _event(f"/olympus pause {target_id}", 2023, user_id="operator-2")
    )
    assert "identity belongs to another" in denied


@pytest.mark.asyncio
async def test_control_operation_collision_changed_payload_only(
    session_store, governed_board
):
    conn = governed_board.kb.connect(board="default")
    try:
        target_id = _create_governed(
            conn, governed_board.context, title="collision-payload"
        )
    finally:
        conn.close()
    runner = _runner(session_store)
    _set_selection(session_store, governed_board)
    update_id = 2024
    assert "status is `blocked`" in await runner._handle_olympus_command(
        _event(f"/olympus pause {target_id}", update_id)
    )
    conn = governed_board.kb.connect(board="default")
    try:
        operation_id = (
            "olympus-telegram-control:v3:"
            + _digest(
                {
                    "platform": "telegram",
                    "bot_id": BOT_ID,
                    "profile": PROFILE,
                    "update_id": update_id,
                }
            )
        )
        telegram_auth = governed_board.kb.olympus_telegram_auth(
            conn,
            verifier=_allow,
            source_identity=_source_identity(),
            authorization_task_id=governed_board.root_id,
            target_task_id=target_id,
            action="telegram-control:pause",
            operation_id=operation_id,
        )
        with pytest.raises(
            governed_board.kb.OlympusContextError,
            match="identity belongs to another",
        ):
            governed_board.kb.apply_olympus_telegram_control(
                conn,
                telegram_auth=telegram_auth,
                service_auth=_service_auth(
                    conn, governed_board.context, "collision-payload:service"
                ),
                target_task_id=target_id,
                action="pause",
                operator_tag="telegram:changed-control-payload",
            )
    finally:
        conn.close()


@pytest.mark.asyncio
async def test_concurrent_interrupt_cancel_operation_collision_admits_one(
    session_store, governed_board, monkeypatch
):
    target_id, _ = _register_running_target(
        governed_board, monkeypatch, title="collision-interrupt-cancel"
    )
    runner = _runner(session_store)
    _set_selection(session_store, governed_board)
    results = await asyncio.gather(
        runner._handle_olympus_command(
            _event(f"/olympus interrupt {target_id}", 2025)
        ),
        runner._handle_olympus_command(
            _event(f"/olympus cancel {target_id}", 2025)
        ),
    )
    assert sum("status is `blocked`" in result for result in results) == 1
    assert sum("identity belongs to another" in result for result in results) == 1
    conn = governed_board.kb.connect(board="default")
    try:
        assert conn.execute(
            "SELECT count(*) FROM olympus_telegram_controls"
        ).fetchone()[0] == 1
        assert conn.execute(
            "SELECT count(*) FROM kanban_effect_journal "
            "WHERE effect_kind='terminate_worker'"
        ).fetchone()[0] == 1
    finally:
        conn.close()


@pytest.mark.asyncio
async def test_nonrunning_control_fault_rolls_back_receipt_then_retry_succeeds(
    session_store, governed_board, monkeypatch
):
    conn = governed_board.kb.connect(board="default")
    try:
        target_id = _create_governed(
            conn, governed_board.context, title="fault-nonrunning"
        )
    finally:
        conn.close()
    runner = _runner(session_store)
    _set_selection(session_store, governed_board)
    event = _event(f"/olympus pause {target_id}", 203)
    original = governed_board.kb.set_task_status
    monkeypatch.setattr(
        governed_board.kb,
        "set_task_status",
        lambda *args, **kwargs: (_ for _ in ()).throw(
            RuntimeError("nonrunning mutation crash")
        ),
    )
    assert "nonrunning mutation crash" in await runner._handle_olympus_command(event)
    conn = governed_board.kb.connect(board="default")
    try:
        assert conn.execute(
            "SELECT count(*) FROM olympus_telegram_controls"
        ).fetchone()[0] == 0
        assert governed_board.kb.get_task(conn, target_id).status == "ready"
    finally:
        conn.close()
    monkeypatch.setattr(governed_board.kb, "set_task_status", original)
    assert "status is `blocked`" in await runner._handle_olympus_command(event)


@pytest.mark.asyncio
async def test_running_control_stage_fault_rolls_back_then_retry_succeeds(
    session_store, governed_board, monkeypatch
):
    target_id, _ = _register_running_target(
        governed_board, monkeypatch, title="fault-effect-stage"
    )
    runner = _runner(session_store)
    _set_selection(session_store, governed_board)
    event = _event(f"/olympus interrupt {target_id}", 204)

    def fail_after_stage(stage: str) -> None:
        if stage == "after_stage":
            raise RuntimeError("effect stage crash")

    governed_board.kb._OLYMPUS_EFFECT_EXECUTION_FAILPOINT = fail_after_stage
    try:
        assert "effect stage crash" in await runner._handle_olympus_command(event)
    finally:
        governed_board.kb._OLYMPUS_EFFECT_EXECUTION_FAILPOINT = None
    conn = governed_board.kb.connect(board="default")
    try:
        assert conn.execute(
            "SELECT count(*) FROM olympus_telegram_controls"
        ).fetchone()[0] == 0
        assert conn.execute(
            "SELECT count(*) FROM kanban_effect_journal "
            "WHERE effect_kind='terminate_worker'"
        ).fetchone()[0] == 0
        assert governed_board.kb.get_task(conn, target_id).status == "running"
    finally:
        conn.close()
    assert "status is `blocked`" in await runner._handle_olympus_command(event)
    reopened = governed_board.kb.connect(board="default")
    try:
        assert reopened.execute(
            "SELECT count(*) FROM olympus_telegram_controls"
        ).fetchone()[0] == 1
        assert reopened.execute(
            "SELECT state FROM kanban_effect_journal "
            "WHERE effect_kind='terminate_worker'"
        ).fetchone()[0] == "pending"
    finally:
        reopened.close()


def _register_running_target(
    board,
    monkeypatch,
    *,
    title: str,
    context: dict | None = None,
    pid: int = 4242,
):
    kb = board.kb
    context = context or board.context
    conn = kb.connect(board="default")
    target_id = _create_governed(conn, context, title=title)
    run = kb.reserve_worker_run(
        conn,
        target_id,
        claimer=kb._claimer_id(),
        olympus_auth=_service_auth(conn, context, f"{title}:claim"),
    )
    assert run is not None and run.launch_token
    assert kb.mark_worker_workspace_ready(
        conn,
        task_id=target_id,
        run_id=run.id,
        launch_token=run.launch_token,
        workspace_snapshot={"board_id": kb._connection_board_identity(conn)},
        olympus_auth=_service_auth(conn, context, f"{title}:workspace"),
    )
    assert kb.mark_worker_starting(
        conn,
        task_id=target_id,
        run_id=run.id,
        launch_token=run.launch_token,
        olympus_auth=_service_auth(conn, context, f"{title}:starting"),
    )
    identity = kb.ProcessIdentity(
        "host:test", "boot:test", pid, f"birth:{title}"
    )
    monkeypatch.setattr(
        kb,
        "read_process_identity",
        lambda pid: identity if int(pid) == identity.pid else None,
    )
    assert kb.register_worker_process(
        conn,
        task_id=target_id,
        run_id=run.id,
        launch_token=run.launch_token,
        process_identity=identity,
        dispatcher_instance_id=DISPATCHER,
        olympus_auth=_service_auth(conn, context, f"{title}:register"),
    )
    conn.close()
    return target_id, identity


@pytest.mark.asyncio
async def test_interrupt_stages_certified_effect_without_signaling(
    session_store, governed_board, monkeypatch
):
    target_id, _ = _register_running_target(
        governed_board, monkeypatch, title="interrupt"
    )
    runner = _runner(session_store)
    _set_selection(session_store, governed_board)
    result = await runner._handle_olympus_command(
        _event(f"/olympus interrupt {target_id}", 210)
    )
    assert "status is `blocked`" in result
    conn = governed_board.kb.connect(board="default")
    try:
        effect = conn.execute(
            "SELECT effect_kind,state FROM kanban_effect_journal"
        ).fetchone()
        assert dict(effect) == {"effect_kind": "terminate_worker", "state": "pending"}
        control = conn.execute(
            "SELECT effect_operation_id FROM olympus_telegram_controls"
        ).fetchone()
        assert control["effect_operation_id"]
    finally:
        conn.close()


@pytest.mark.asyncio
@pytest.mark.parametrize("next_action", ("resume", "cancel"))
async def test_interrupt_denies_resume_or_nonrunning_cancel_while_effect_active(
    session_store, governed_board, monkeypatch, next_action
):
    target_id, _ = _register_running_target(
        governed_board, monkeypatch, title=f"interrupt-then-{next_action}"
    )
    runner = _runner(session_store)
    _set_selection(session_store, governed_board)
    assert "status is `blocked`" in await runner._handle_olympus_command(
        _event(f"/olympus interrupt {target_id}", 2110)
    )
    denied = await runner._handle_olympus_command(
        _event(f"/olympus {next_action} {target_id}", 2111)
    )
    assert "active worker-termination generation" in denied
    conn = governed_board.kb.connect(board="default")
    try:
        assert governed_board.kb.get_task(conn, target_id).status == "blocked"
        assert conn.execute(
            "SELECT count(*) FROM olympus_telegram_controls"
        ).fetchone()[0] == 1
        assert conn.execute(
            "SELECT state FROM kanban_effect_journal "
            "WHERE effect_kind='terminate_worker'"
        ).fetchone()[0] == "pending"
    finally:
        conn.close()


@pytest.mark.asyncio
async def test_registered_process_pause_preserves_unrelated_running_process(
    session_store, governed_board, monkeypatch
):
    target_id, target_identity = _register_running_target(
        governed_board, monkeypatch, title="registered-pause", pid=4242
    )
    unrelated_id, unrelated_identity = _register_running_target(
        governed_board, monkeypatch, title="unrelated-running", pid=4343
    )
    identities = {
        target_identity.pid: target_identity,
        unrelated_identity.pid: unrelated_identity,
    }
    monkeypatch.setattr(
        governed_board.kb,
        "read_process_identity",
        lambda pid: identities.get(int(pid)),
    )
    runner = _runner(session_store)
    _set_selection(session_store, governed_board)
    assert "status is `blocked`" in await runner._handle_olympus_command(
        _event(f"/olympus pause {target_id}", 2112)
    )
    signaled = []
    conn = governed_board.kb.connect(board="default")
    try:
        result = governed_board.kb.process_pending_worker_termination_effects(
            conn,
            olympus_auth=_service_auth(
                conn, governed_board.context, "registered-pause:dispatch"
            ),
            signal_fn=lambda pid, sig: signaled.append((pid, sig)),
        )
        assert result["executed"] == 1
        assert [pid for pid, _sig in signaled] == [target_identity.pid]
        assert governed_board.kb.get_task(conn, target_id).status == "blocked"
        assert governed_board.kb.get_task(conn, unrelated_id).status == "running"
        unrelated_run = conn.execute(
            "SELECT r.process_state,r.worker_pid FROM tasks t "
            "JOIN task_runs r ON r.id=t.current_run_id WHERE t.id=?",
            (unrelated_id,),
        ).fetchone()
        assert dict(unrelated_run) == {
            "process_state": "registered",
            "worker_pid": unrelated_identity.pid,
        }
        assert conn.execute(
            "SELECT count(*) FROM kanban_effect_journal WHERE task_id=?",
            (unrelated_id,),
        ).fetchone()[0] == 0
    finally:
        conn.close()


@pytest.mark.asyncio
async def test_dispatcher_concurrently_executes_once_then_confirms_gone(
    session_store, governed_board, monkeypatch
):
    target_id, identity = _register_running_target(
        governed_board, monkeypatch, title="dispatcher-effect"
    )
    runner = _runner(session_store)
    _set_selection(session_store, governed_board)
    assert "status is `blocked`" in await runner._handle_olympus_command(
        _event(f"/olympus interrupt {target_id}", 213)
    )
    calls = []

    def process_once(operation: str):
        conn = governed_board.kb.connect(board="default")
        try:
            return governed_board.kb.process_pending_worker_termination_effects(
                conn,
                olympus_auth=_service_auth(
                    conn, governed_board.context, operation
                ),
                signal_fn=lambda pid, sig: calls.append((pid, sig)),
            )
        finally:
            conn.close()

    await asyncio.gather(
        *(asyncio.to_thread(process_once, f"effect:concurrent:{i}") for i in range(6))
    )
    assert len(calls) == 1 and calls[0][0] == identity.pid
    conn = governed_board.kb.connect(board="default")
    try:
        assert conn.execute(
            "SELECT state FROM kanban_effect_journal "
            "WHERE effect_kind='terminate_worker'"
        ).fetchone()[0] == "applied"
    finally:
        conn.close()
    monkeypatch.setattr(
        governed_board.kb, "read_process_identity", lambda _pid: None
    )
    monkeypatch.setattr(governed_board.kb, "_pid_alive", lambda _pid: False)
    confirmations = await asyncio.gather(
        *(asyncio.to_thread(process_once, f"effect:confirm:{i}") for i in range(6))
    )
    assert sum(result["confirmed"] for result in confirmations) == 1
    conn = governed_board.kb.connect(board="default")
    try:
        assert conn.execute(
            "SELECT state FROM kanban_effect_journal "
            "WHERE effect_kind='terminate_worker'"
        ).fetchone()[0] == "gone"
        assert governed_board.kb.get_task(conn, target_id).status == "blocked"
    finally:
        conn.close()


@pytest.mark.asyncio
async def test_failed_effect_is_not_replayed_or_finalized(
    session_store, governed_board, monkeypatch
):
    target_id, _ = _register_running_target(
        governed_board, monkeypatch, title="failed-effect"
    )
    runner = _runner(session_store)
    _set_selection(session_store, governed_board)
    assert "status is `blocked`" in await runner._handle_olympus_command(
        _event(f"/olympus cancel {target_id}", 214)
    )
    calls = []

    def fail_signal(pid, sig):
        calls.append((pid, sig))
        raise RuntimeError("signal failure")

    conn = governed_board.kb.connect(board="default")
    try:
        result = governed_board.kb.process_pending_worker_termination_effects(
            conn,
            olympus_auth=_service_auth(
                conn, governed_board.context, "effect:failed:first"
            ),
            signal_fn=fail_signal,
        )
        assert result["executed"] == 1
        assert conn.execute(
            "SELECT state FROM kanban_effect_journal "
            "WHERE effect_kind='terminate_worker'"
        ).fetchone()[0] == "failed"
        governed_board.kb.process_pending_worker_termination_effects(
            conn,
            olympus_auth=_service_auth(
                conn, governed_board.context, "effect:failed:retry"
            ),
            signal_fn=lambda pid, sig: calls.append((pid, sig)),
        )
        assert len(calls) == 1
        assert governed_board.kb.reconcile_olympus_telegram_controls(
            conn,
            service_auth=_service_auth(
                conn, governed_board.context, "effect:failed:reconcile"
            ),
        ) == 0
        assert governed_board.kb.get_task(conn, target_id).status == "blocked"
    finally:
        conn.close()


@pytest.mark.asyncio
async def test_cancel_reconciles_only_after_effect_terminal_and_reopen(
    session_store, governed_board, monkeypatch
):
    target_id, identity = _register_running_target(
        governed_board, monkeypatch, title="cancel"
    )
    runner = _runner(session_store)
    _set_selection(session_store, governed_board)
    result = await runner._handle_olympus_command(
        _event(f"/olympus cancel {target_id}", 211)
    )
    assert "status is `blocked`" in result
    conn = governed_board.kb.connect(board="default")
    try:
        assert governed_board.kb.reconcile_olympus_telegram_controls(
            conn,
            service_auth=_service_auth(conn, governed_board.context, "cancel:reconcile"),
        ) == 0
        effect_id = conn.execute(
            "SELECT id FROM kanban_effect_journal WHERE effect_kind='terminate_worker'"
        ).fetchone()[0]
        calls = []
        assert governed_board.kb.execute_worker_termination_effect(
            conn,
            effect_id,
            olympus_auth=_service_auth(conn, governed_board.context, "cancel:execute"),
            signal_fn=lambda pid, sig: calls.append((pid, sig)),
        ) == "applied"
        assert calls and calls[0][0] == identity.pid
        assert governed_board.kb.reconcile_olympus_telegram_controls(
            conn,
            service_auth=_service_auth(
                conn, governed_board.context, "cancel:still-running"
            ),
        ) == 0
    finally:
        conn.close()
    monkeypatch.setattr(
        governed_board.kb, "read_process_identity", lambda _pid: None
    )
    monkeypatch.setattr(governed_board.kb, "_pid_alive", lambda _pid: False)
    reopened = governed_board.kb.connect(board="default")
    try:
        assert governed_board.kb.confirm_applied_worker_termination_effects(
            reopened,
            olympus_auth=_service_auth(
                reopened, governed_board.context, "cancel:confirm-gone"
            ),
        ) == 1
        assert governed_board.kb.reconcile_olympus_telegram_controls(
            reopened,
            service_auth=_service_auth(
                reopened, governed_board.context, "cancel:reconcile"
            ),
        ) == 1
        assert governed_board.kb.get_task(reopened, target_id).status == "archived"
        assert governed_board.kb.reconcile_olympus_telegram_controls(
            reopened,
            service_auth=_service_auth(reopened, governed_board.context, "cancel:reconcile"),
        ) == 0
    finally:
        reopened.close()


@pytest.mark.asyncio
async def test_running_cancel_stale_containment_generation_cannot_archive(
    session_store, governed_board, monkeypatch
):
    target_id, _ = _register_running_target(
        governed_board, monkeypatch, title="cancel-stale-finalizer"
    )
    runner = _runner(session_store)
    _set_selection(session_store, governed_board)
    assert "status is `blocked`" in await runner._handle_olympus_command(
        _event(f"/olympus cancel {target_id}", 2150)
    )
    monkeypatch.setattr(
        governed_board.kb, "read_process_identity", lambda _pid: None
    )
    monkeypatch.setattr(governed_board.kb, "_pid_alive", lambda _pid: False)
    conn = governed_board.kb.connect(board="default")
    try:
        effect = conn.execute(
            "SELECT id,target_post_revision FROM kanban_effect_journal "
            "WHERE effect_kind='terminate_worker'"
        ).fetchone()
        assert governed_board.kb.execute_worker_termination_effect(
            conn,
            int(effect["id"]),
            olympus_auth=_service_auth(
                conn, governed_board.context, "cancel-stale:execute"
            ),
        ) == "gone"
        assert governed_board.kb.set_task_status(
            conn,
            target_id,
            "ready",
            olympus_auth=_service_auth(
                conn, governed_board.context, "cancel-stale:ready"
            ),
        )
        assert governed_board.kb.set_task_status(
            conn,
            target_id,
            "blocked",
            olympus_auth=_service_auth(
                conn, governed_board.context, "cancel-stale:blocked"
            ),
        )
        task = governed_board.kb.get_task(conn, target_id)
        assert task.record_revision > int(effect["target_post_revision"])
        assert governed_board.kb.reconcile_olympus_telegram_controls(
            conn,
            service_auth=_service_auth(
                conn, governed_board.context, "cancel-stale:reconcile"
            ),
        ) == 0
        assert governed_board.kb.get_task(conn, target_id).status == "blocked"
    finally:
        conn.close()


@pytest.mark.asyncio
async def test_concurrent_cancel_finalization_archives_exactly_once(
    session_store, governed_board, monkeypatch
):
    target_id, _ = _register_running_target(
        governed_board, monkeypatch, title="cancel-concurrent-finalizer"
    )
    runner = _runner(session_store)
    _set_selection(session_store, governed_board)
    assert "status is `blocked`" in await runner._handle_olympus_command(
        _event(f"/olympus cancel {target_id}", 2151)
    )
    monkeypatch.setattr(
        governed_board.kb, "read_process_identity", lambda _pid: None
    )
    monkeypatch.setattr(governed_board.kb, "_pid_alive", lambda _pid: False)
    conn = governed_board.kb.connect(board="default")
    try:
        effect_id = conn.execute(
            "SELECT id FROM kanban_effect_journal "
            "WHERE effect_kind='terminate_worker'"
        ).fetchone()[0]
        assert governed_board.kb.execute_worker_termination_effect(
            conn,
            effect_id,
            olympus_auth=_service_auth(
                conn, governed_board.context, "cancel-concurrent:execute"
            ),
        ) == "gone"
    finally:
        conn.close()

    def finalize(index: int) -> int:
        isolated = governed_board.kb.connect(board="default")
        try:
            return governed_board.kb.reconcile_olympus_telegram_controls(
                isolated,
                service_auth=_service_auth(
                    isolated,
                    governed_board.context,
                    f"cancel-concurrent:finalize:{index}",
                ),
            )
        finally:
            isolated.close()

    results = await asyncio.gather(
        *(asyncio.to_thread(finalize, index) for index in range(6))
    )
    assert sum(results) == 1
    reopened = governed_board.kb.connect(board="default")
    try:
        assert governed_board.kb.get_task(reopened, target_id).status == "archived"
    finally:
        reopened.close()


@pytest.mark.asyncio
@pytest.mark.parametrize("action", ("pause", "interrupt", "cancel"))
async def test_running_control_without_registered_process_fails_closed(
    session_store, governed_board, action
):
    conn = governed_board.kb.connect(board="default")
    try:
        target_id = _create_governed(
            conn, governed_board.context, title=f"unregistered-{action}"
        )
        assert governed_board.kb.reserve_worker_run(
            conn,
            target_id,
            claimer=governed_board.kb._claimer_id(),
            olympus_auth=_service_auth(conn, governed_board.context, "unregistered:claim"),
        ) is not None
    finally:
        conn.close()
    runner = _runner(session_store)
    _set_selection(session_store, governed_board)
    denied = await runner._handle_olympus_command(
        _event(f"/olympus {action} {target_id}", 212)
    )
    assert "lacks an exact registered process" in denied
    conn = governed_board.kb.connect(board="default")
    try:
        assert conn.execute(
            "SELECT count(*) FROM olympus_telegram_controls"
        ).fetchone()[0] == 0
    finally:
        conn.close()


@pytest.mark.asyncio
async def test_expired_and_foreign_targets_deny_without_receipt(
    session_store, governed_board
):
    foreign = _context(mission_id="M-foreign")
    conn = governed_board.kb.connect(board="default")
    try:
        expired = copy.deepcopy(governed_board.context)
        expired_id = _create_governed(
            conn, expired, title="expired", initial_status="blocked"
        )
        # Represent a previously valid row observed after its persisted lease
        # and authority have expired.  The migration guard is the only path
        # allowed to install historical authority state without a live permit.
        expired["authority"]["expires_at"] = int(time.time()) - 1
        expired["lease"]["expires_at"] = int(time.time()) - 1
        conn._olympus_schema_migration_depth = 1
        try:
            conn.execute(
                "UPDATE tasks SET olympus_context = ? WHERE id = ?",
                (
                    json.dumps(
                        expired, sort_keys=True, separators=(",", ":")
                    ),
                    expired_id,
                ),
            )
        finally:
            conn._olympus_schema_migration_depth = 0
        foreign_id = _create_governed(conn, foreign, title="foreign")
    finally:
        conn.close()
    runner = _runner(session_store)
    _set_selection(session_store, governed_board)
    assert "expired" in await runner._handle_olympus_command(
        _event(f"/olympus resume {expired_id}", 220)
    )
    assert "outside the selected" in await runner._handle_olympus_command(
        _event(f"/olympus cancel {foreign_id}", 221)
    )
    conn = governed_board.kb.connect(board="default")
    try:
        assert conn.execute(
            "SELECT count(*) FROM olympus_telegram_controls"
        ).fetchone()[0] == 0
    finally:
        conn.close()


@pytest.mark.asyncio
@pytest.mark.parametrize("action", ("pause", "resume", "interrupt", "cancel"))
@pytest.mark.parametrize("threat", ("expired", "revoked", "foreign"))
async def test_all_controls_deny_stale_revoked_or_foreign_authority_matrix(
    session_store, governed_board, monkeypatch, action, threat
):
    context = (
        _context(mission_id="M-foreign-matrix")
        if threat == "foreign"
        else copy.deepcopy(governed_board.context)
    )
    if action == "interrupt":
        target_id, _ = _register_running_target(
            governed_board,
            monkeypatch,
            title=f"matrix-{threat}-{action}",
            context=context,
        )
        conn = governed_board.kb.connect(board="default")
    else:
        conn = governed_board.kb.connect(board="default")
        target_id = _create_governed(
            conn,
            context,
            title=f"matrix-{threat}-{action}",
            initial_status="blocked" if action == "resume" else "running",
        )
    try:
        if threat != "foreign":
            if threat == "expired":
                context["authority"]["expires_at"] = int(time.time()) - 1
                context["lease"]["expires_at"] = int(time.time()) - 1
            else:
                context["authority"]["status"] = "REVOKED"
                context["lease"]["status"] = "REVOKED"
            conn._olympus_schema_migration_depth = 1
            try:
                conn.execute(
                    "UPDATE tasks SET olympus_context=? WHERE id=?",
                    (
                        json.dumps(
                            context, sort_keys=True, separators=(",", ":")
                        ),
                        target_id,
                    ),
                )
            finally:
                conn._olympus_schema_migration_depth = 0
    finally:
        conn.close()
    runner = _runner(session_store)
    _set_selection(session_store, governed_board)
    denied = await runner._handle_olympus_command(
        _event(f"/olympus {action} {target_id}", 225)
    )
    assert "blocked" in denied
    conn = governed_board.kb.connect(board="default")
    try:
        assert conn.execute(
            "SELECT count(*) FROM olympus_telegram_controls"
        ).fetchone()[0] == 0
    finally:
        conn.close()


@pytest.mark.asyncio
async def test_direct_sql_insert_update_delete_matrix(
    session_store, governed_board
):
    runner = _runner(session_store)
    _set_selection(session_store, governed_board)
    assert (await runner._route_olympus_telegram_intake(
        _event("journal guard", 240)
    )).startswith("Queued")
    conn = governed_board.kb.connect(board="default")
    try:
        target_id = _create_governed(
            conn, governed_board.context, title="journal-control"
        )
        db_path = conn.execute("PRAGMA database_list").fetchone()[2]
    finally:
        conn.close()
    assert "status is `blocked`" in await runner._handle_olympus_command(
        _event(f"/olympus pause {target_id}", 241)
    )
    raw = sqlite3.connect(db_path)
    try:
        delivery_key = raw.execute(
            "SELECT delivery_key FROM olympus_telegram_deliveries"
        ).fetchone()[0]
        operation_id = raw.execute(
            "SELECT operation_id FROM olympus_telegram_controls"
        ).fetchone()[0]
        statements = (
            (
                "INSERT INTO olympus_telegram_deliveries VALUES "
                "(?,?,?,?,?,?,?)",
                (
                    "olympus-telegram:v3:forged", governed_board.root_id, 1,
                    "t_forged", "{}", "0" * 64, 1,
                ),
            ),
            (
                "UPDATE olympus_telegram_deliveries SET payload='{}' "
                "WHERE delivery_key=?",
                (delivery_key,),
            ),
            (
                "DELETE FROM olympus_telegram_deliveries WHERE delivery_key=?",
                (delivery_key,),
            ),
            (
                "INSERT INTO olympus_telegram_controls VALUES "
                "(?,?,?,?,?,?,?,?,?,?,?,?,?)",
                (
                    "olympus-telegram-control:v3:forged", "telegram-control:pause",
                    governed_board.root_id, 1, target_id, 1, "{}", "{}",
                    "0" * 64, "forged", "blocked", None, 1,
                ),
            ),
            (
                "UPDATE olympus_telegram_controls SET result_status='ready' "
                "WHERE operation_id=?",
                (operation_id,),
            ),
            (
                "DELETE FROM olympus_telegram_controls WHERE operation_id=?",
                (operation_id,),
            ),
        )
        for statement, params in statements:
            with pytest.raises(sqlite3.DatabaseError):
                raw.execute(statement, params)
            raw.rollback()
        assert raw.execute(
            "SELECT count(*) FROM olympus_telegram_deliveries"
        ).fetchone()[0] == 1
        assert raw.execute(
            "SELECT count(*) FROM olympus_telegram_controls"
        ).fetchone()[0] == 1
    finally:
        raw.close()


def test_valid_permit_cannot_be_reused_for_another_journal_tuple(
    governed_board,
):
    kb = governed_board.kb
    conn = kb.connect(board="default")
    try:
        root = kb.get_task(conn, governed_board.root_id)
        revision = root.record_revision
        source = _source_identity()
        source_json, _ = kb._canonical_json_record(source)

        delivery_auth = kb.olympus_telegram_auth(
            conn,
            verifier=_allow,
            source_identity=source,
            authorization_task_id=root.id,
            target_task_id=root.id,
            action="telegram-intake",
            operation_id="cross-tuple:intake",
        )
        delivery_payload, delivery_sha = kb._canonical_json_record(
            {"schema_version": "cross-tuple/1", "tuple": "authorized"}
        )
        delivery_binding = {
            "schema_version": kb.TELEGRAM_DELIVERY_WRITE_SCHEMA,
            "action": "telegram-intake",
            "task_id": root.id,
            "task_record_revision": revision,
            "delivery_key": "olympus-telegram:v3:" + "1" * 64,
            "authorization_task_id": root.id,
            "authorization_task_revision": revision,
            "created_task_id": "t_11111111",
            "payload": delivery_payload,
            "payload_sha256": delivery_sha,
            "created_at": 1,
        }
        with kb.write_txn(conn), kb.olympus_mutation_scope(delivery_auth):
            _, owns = kb._authorize_task_mutation(
                conn,
                root.id,
                action="telegram-intake",
                capability=kb.TELEGRAM_ACTION_CAPABILITIES["telegram-intake"],
                auth=delivery_auth,
                mutation_binding=delivery_binding,
            )
            try:
                with pytest.raises(sqlite3.IntegrityError):
                    conn.execute(
                        "INSERT INTO olympus_telegram_deliveries VALUES "
                        "(?,?,?,?,?,?,?)",
                        (
                            "olympus-telegram:v3:" + "2" * 64,
                            root.id,
                            revision,
                            "t_11111111",
                            delivery_payload,
                            delivery_sha,
                            1,
                        ),
                    )
            finally:
                kb._release_task_mutation_permit(conn, root.id, owns)

        control_auth = kb.olympus_telegram_auth(
            conn,
            verifier=_allow,
            source_identity=source,
            authorization_task_id=root.id,
            target_task_id=root.id,
            action="telegram-control:pause",
            operation_id="olympus-telegram-control:v3:" + "3" * 64,
        )
        request_payload, request_sha = kb._canonical_json_record(
            {"schema_version": "cross-tuple-control/1"}
        )
        control_binding = {
            "schema_version": kb.TELEGRAM_CONTROL_WRITE_SCHEMA,
            "action": "telegram-control:pause",
            "task_id": root.id,
            "task_record_revision": revision,
            "operation_id": control_auth.operation_id,
            "authorization_task_id": root.id,
            "authorization_task_revision": revision,
            "source_identity": source_json,
            "request_payload": request_payload,
            "payload_sha256": request_sha,
            "result_status": "blocked",
            "effect_operation_id": None,
            "created_at": 2,
        }
        with kb.write_txn(conn), kb.olympus_mutation_scope(control_auth):
            authorization, owns = kb._authorize_task_mutation(
                conn,
                root.id,
                action="telegram-control:pause",
                capability=kb.TELEGRAM_ACTION_CAPABILITIES[
                    "telegram-control:pause"
                ],
                auth=control_auth,
                mutation_binding=control_binding,
            )
            try:
                with pytest.raises(sqlite3.IntegrityError):
                    conn.execute(
                        "INSERT INTO olympus_telegram_controls VALUES "
                        "(?,?,?,?,?,?,?,?,?,?,?,?,?)",
                        (
                            "olympus-telegram-control:v3:" + "4" * 64,
                            "telegram-control:pause", root.id, revision,
                            root.id, revision, source_json, request_payload,
                            request_sha,
                            authorization["verification"]["verification_id"],
                            "blocked", None, 2,
                        ),
                    )
            finally:
                kb._release_task_mutation_permit(conn, root.id, owns)
    finally:
        conn.close()


@pytest.mark.asyncio
async def test_busy_selected_message_never_interrupts_active_agent(session_store):
    runner = _runner(session_store)
    agent = MagicMock()
    key = runner._session_key_for_source(_source())
    runner._running_agents[key] = agent
    runner._route_olympus_telegram_intake = AsyncMock(
        return_value="Queued `t_abc12345`"
    )
    adapter = MagicMock()
    adapter._send_with_retry = AsyncMock()
    runner.adapters[Platform.TELEGRAM] = adapter
    assert await runner._handle_active_session_busy_message(_event("new work", 300), key)
    agent.interrupt.assert_not_called()


@pytest.mark.asyncio
async def test_busy_selected_intake_routes_only_to_exact_chat_thread_and_user(
    session_store, governed_board
):
    source = _source(
        chat_id="chat-selected",
        thread_id="thread-selected",
        user_id="user-selected",
    )
    event = _event(
        "durable selected work",
        301,
        chat_id="chat-selected",
        thread_id="thread-selected",
        user_id="user-selected",
    )
    runner = _runner(session_store)
    _set_selection(session_store, governed_board, source=source)
    agent = MagicMock()
    key = runner._session_key_for_source(source)
    runner._running_agents[key] = agent
    adapter = MagicMock()
    adapter._bot = SimpleNamespace(id=int(BOT_ID))
    adapter._send_with_retry = AsyncMock()
    runner.adapters[Platform.TELEGRAM] = adapter

    assert await runner._handle_active_session_busy_message(event, key)
    agent.interrupt.assert_not_called()
    adapter._send_with_retry.assert_awaited_once()
    assert adapter._send_with_retry.await_args.kwargs["chat_id"] == "chat-selected"

    conn = governed_board.kb.connect(board="default")
    try:
        assert conn.execute(
            "SELECT count(*) FROM olympus_telegram_deliveries"
        ).fetchone()[0] == 1
        assert conn.execute(
            "SELECT count(*) FROM tasks WHERE id != ?",
            (governed_board.root_id,),
        ).fetchone()[0] == 1
        subscription = conn.execute(
            "SELECT platform,chat_id,thread_id,user_id,notifier_profile "
            "FROM kanban_notify_subs"
        ).fetchone()
        assert dict(subscription) == {
            "platform": "telegram",
            "chat_id": "chat-selected",
            "thread_id": "thread-selected",
            "user_id": "user-selected",
            "notifier_profile": PROFILE,
        }
        assert conn.execute(
            "SELECT count(*) FROM kanban_notify_subs "
            "WHERE chat_id IN ('chat-unrelated','1001') "
            "OR thread_id='thread-unrelated' OR user_id='user-unrelated'"
        ).fetchone()[0] == 0
    finally:
        conn.close()


@pytest.mark.asyncio
async def test_telegram_background_requires_selection_or_explicit_ephemeral(session_store):
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


def _install_message_dispatch_stubs(runner):
    runner._scale_to_zero_note_real_inbound = lambda: None
    runner._route_olympus_telegram_intake = AsyncMock(return_value=None)
    runner._check_slash_access = lambda *_args, **_kwargs: None
    runner.hooks = SimpleNamespace(
        emit=AsyncMock(),
        emit_collect=AsyncMock(return_value=[]),
        loaded_hooks=False,
    )


@pytest.mark.asyncio
async def test_cold_runner_dispatches_olympus_command(session_store):
    runner = _runner(session_store)
    _install_message_dispatch_stubs(runner)
    runner._handle_olympus_command = AsyncMock(return_value="olympus:cold")
    event = _event("/olympus status", 320)

    assert await runner._handle_message(event) == "olympus:cold"
    runner._handle_olympus_command.assert_awaited_once_with(event)


@pytest.mark.asyncio
async def test_active_runner_dispatches_olympus_command(session_store):
    runner = _runner(session_store)
    _install_message_dispatch_stubs(runner)
    runner._handle_olympus_command = AsyncMock(return_value="olympus:active")
    event = _event("/olympus status", 321)
    key = runner._session_key_for_source(event.source)
    agent = MagicMock()
    agent.get_activity_summary.return_value = {
        "seconds_since_activity": 0,
        "last_activity_desc": "synthetic active command",
        "api_call_count": 1,
        "max_iterations": 10,
    }
    runner._running_agents[key] = agent
    runner._running_agents_ts[key] = time.time()

    assert await runner._handle_message(event) == "olympus:active"
    runner._handle_olympus_command.assert_awaited_once_with(event)
    agent.interrupt.assert_not_called()
