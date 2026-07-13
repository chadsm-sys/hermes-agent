"""Exact Olympus v3 authority and persistence contracts for Hermes Kanban."""

from __future__ import annotations

import copy
import hashlib
import json
import os
import shutil
import sqlite3
import threading
import time
from pathlib import Path

import pytest

from hermes_cli import kanban_db as kb


@pytest.fixture
def conn(tmp_path, monkeypatch):
    home = tmp_path / ".hermes"
    home.mkdir()
    monkeypatch.setenv("HERMES_HOME", str(home))
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    db_path = home / "olympus-kanban.db"
    kb._INITIALIZED_PATHS.discard(str(db_path.resolve()))
    connection = kb.connect(db_path)
    try:
        yield connection
    finally:
        connection.close()


def _context(
    *, now: int | None = None, lease_id: str = "lease-1",
    agent_id: str = "coding", authority_revision: int = 7,
    lease_revision: int = 11,
) -> dict:
    current = int(time.time()) if now is None else now
    return {
        "schema_version": 2,
        "goal_id": "goal-1",
        "program_id": "program-1",
        "milestone_id": "milestone-1",
        "mission_id": "mission-1",
        "workstream_id": "workstream-1",
        "authority": {
            "authority_id": "authority-1",
            "status": "ACTIVE",
            "scope": ["mission-1"],
            "capabilities": sorted(set(kb.KANBAN_TASK_ACTION_CAPABILITIES.values())),
            "revision": authority_revision,
            "source": "mission-control:test-authority",
            "expires_at": current + 3600,
        },
        "lease": {
            "lease_id": lease_id,
            "mission_id": "mission-1",
            "agent_id": agent_id,
            "holder": agent_id,
            "repository": "chadsm-sys/hermes-agent",
            "branch": "codex-mini/M-20260713-olympus-hermes-bind",
            "worktree": "/isolated/hermes-bind",
            "revision": lease_revision,
            "source": "acp:test-lease",
            "status": "ACTIVE",
            "expires_at": current + 1800,
        },
        "risk": "high",
        "agent_id": agent_id,
        "review_status": "pending",
        "evidence_refs": ["evidence://plan/1"],
    }


def _allow_at(request: dict, now: float) -> dict:
    emergency = request["action"] in kb.TELEGRAM_EMERGENCY_ACTIONS
    subjects = [request["authorization_root"]] if emergency else [request["target"]]
    if not emergency and request["authorization_root"] is not None:
        subjects.append(request["authorization_root"])
    expiry = min(
        value
        for subject in subjects
        for value in (subject["authority"]["expires_at"], subject["lease"]["expires_at"])
    )
    if request["principal"]["kind"] == "kanban_worker":
        expiry = min(expiry, request["principal"]["claim_expires"])
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
            None if request["authorization_root"] is None else {
                "authority_current": True,
                "containment_target": False,
                "subject": copy.deepcopy(request["authorization_root"]),
            }
        ),
    }


def _allow(request: dict) -> dict:
    return _allow_at(request, time.time())


def _auth(
    conn, context: dict, *, verifier=_allow, actor: str | None = None,
    operation_id: str = "test",
) -> kb.OlympusMutationAuth:
    board_id = kb._connection_board_identity(conn)
    dispatcher = "test-dispatcher"
    return kb.OlympusMutationAuth(
        verifier=verifier,
        principal_type="service",
        principal_id=f"kanban-service-dispatcher:{board_id}:{dispatcher}",
        principal_source=f"kanban-dispatcher:{board_id}:{dispatcher}",
        actor=actor if actor is not None else context["agent_id"],
        operation_id=operation_id,
    )


def _create(conn, context: dict | None = None, **kwargs) -> str:
    context = copy.deepcopy(context or _context())
    return kb.create_olympus_task(
        conn,
        olympus_context=context,
        olympus_auth=_auth(
            conn, context, operation_id=kwargs.pop("operation_id", "create:1")
        ),
        title=kwargs.pop("title", "governed task"),
        assignee=kwargs.pop("assignee", context["agent_id"]),
        **kwargs,
    )


def _registered_run(conn, monkeypatch, *, max_runtime_seconds=None):
    context = _context()
    task_id = _create(
        conn, context, max_runtime_seconds=max_runtime_seconds,
        operation_id=f"create:{time.time_ns()}",
    )
    auth = lambda action: _auth(
        conn, context, operation_id=f"lifecycle:{action}:{time.time_ns()}"
    )
    run = kb.reserve_worker_run(
        conn, task_id, claimer=kb._claimer_id(), olympus_auth=auth("claim"),
    )
    assert run is not None and run.launch_token
    assert kb.mark_worker_workspace_ready(
        conn, task_id=task_id, run_id=run.id, launch_token=run.launch_token,
        workspace_snapshot={"board_id": kb._connection_board_identity(conn), "path": "/tmp"},
        olympus_auth=auth("workspace"),
    )
    assert kb.mark_worker_starting(
        conn, task_id=task_id, run_id=run.id, launch_token=run.launch_token,
        olympus_auth=auth("starting"),
    )
    identity = kb.ProcessIdentity("host:test", "boot:test", 4242, "birth:test")
    monkeypatch.setattr(
        kb, "read_process_identity",
        lambda pid: identity if int(pid) == identity.pid else None,
    )
    assert kb.register_worker_process(
        conn, task_id=task_id, run_id=run.id, launch_token=run.launch_token,
        process_identity=identity, dispatcher_instance_id="test-dispatcher",
        olympus_auth=auth("register"),
    )
    return context, task_id, kb.get_run(conn, run.id), identity


def _golden_target(fixed: float) -> dict:
    cross_profile_capabilities = {
        "goal.write", "milestone.write", "mission.approval.record",
        "mission.certify", "mission.decision.record", "mission.evidence.record",
        "mission.transition", "mission.write", "program.authority.rebind",
        "program.write",
    }
    authority = {
        "authority_id": "authority:test", "status": "ACTIVE",
        "scope": ["goal:test", "program:test", "milestone:test", "mission:test"],
        "capabilities": sorted(
            set(kb.KANBAN_TASK_ACTION_CAPABILITIES.values())
            | cross_profile_capabilities
        ),
        "revision": 4, "source": "authority-source:test",
        "expires_at": fixed + 600,
    }
    lease = {
        "lease_id": "lease:test", "status": "ACTIVE",
        "mission_id": "mission:test", "agent_id": "agent:test",
        "holder": "agent:test", "repository": "mission-control-v0",
        "branch": "branch:test", "worktree": "/worktree/test",
        "revision": 2, "source": "lease-source:test",
        "expires_at": fixed + 500,
    }
    return {
        "subject_type": "kanban_task", "subject_id": "task:test",
        "subject_revision": 8, "subject_status": "running",
        "goal_id": "goal:test", "program_id": "program:test",
        "milestone_id": "milestone:test", "mission_id": "mission:test",
        "workstream_id": "workstream:test", "authority": authority,
        "lease": lease, "assignee": "agent:test",
    }


def _golden_principal(
    kind: str, target: dict, fixed: float, *, action: str | None = None,
) -> dict:
    if kind == "kanban_service_dispatcher":
        principal = {
            "kind": kind, "principal_type": "service",
            "principal_id": "kanban-service-dispatcher:board:test:dispatcher:test",
            "principal_source": "kanban-dispatcher:board:test:dispatcher:test",
            "board_id": "board:test", "dispatcher_instance_id": "dispatcher:test",
        }
        if action == "add_notification_subscription":
            principal["operation_binding"] = {
                "schema_version": kb.NOTIFICATION_SUBSCRIPTION_OPERATION_SCHEMA,
                "action": action,
                "board_id": "board:test",
                "task_id": target["subject_id"],
                "task_record_revision": target["subject_revision"],
                "platform": "telegram",
                "chat_id": "chat:test",
                "thread_id": "thread:test",
                "user_id": "user:test",
                "notifier_profile": "default",
            }
        return principal
    if kind == "kanban_worker":
        return {
            "kind": kind, "principal_type": "kanban_worker",
            "principal_id": (
                "kanban-worker:board:test:task:test:7:"
                "host:test:boot:test:42:start:test"
            ),
            "principal_source": "kanban-dispatcher:dispatcher:test",
            "board_id": "board:test", "worker_task_id": "task:test",
            "worker_task_revision": 8, "worker_status": "running",
            "worker_assignee": "agent:test", "run_id": 7,
            "run_subject_revision": 3, "run_status": "running",
            "claim_lock": "claim:test", "claim_expires": int(fixed) + 600,
            "process_state": "registered", "host_id": "host:test",
            "boot_id": "boot:test", "pid": 42, "start_token": "start:test",
            "dispatcher_instance_id": "dispatcher:test",
        }
    if kind == "kanban_notifier":
        return {
            "kind": kind, "principal_type": "kanban_notifier",
            "principal_id": (
                "kanban-notifier:board:test:task:test:telegram:chat:test:"
                "thread:test:user:test:effect:test"
            ),
            "principal_source": "kanban-gateway:host:test:boot:test:43:start:test",
            "board_id": "board:test", "task_id": "task:test",
            "task_record_revision": 8, "platform": "telegram",
            "chat_id": "chat:test", "thread_id": "thread:test",
            "user_id": "user:test", "notifier_profile": "default",
            "created_at": 1, "last_event_id": 6, "source_event_id": 7,
            "effect_id": "effect:test", "effect_state": "reserved",
            "gateway_host_id": "host:test", "gateway_boot_id": "boot:test",
            "gateway_pid": 43, "gateway_start_token": "start:test",
        }
    return {
        "kind": "telegram_user", "principal_type": "telegram_user",
        "principal_id": "telegram:bot:test:user:test",
        "principal_source": "telegram-bot:bot:test:profile:default",
        "bot_id": "bot:test", "profile": "default", "chat_id": "chat:test",
        "thread_id": "thread:test", "user_id": "user:test",
    }


def test_v3_registries_and_cross_repo_golden_vectors_are_exact():
    assert len(kb.HERMES_KANBAN_ACTION_CAPABILITIES) == 58
    assert len(kb.TELEGRAM_ACTION_CAPABILITIES) == 8
    assert kb.SUBSCRIPTION_REGISTRATION_ACTIONS == {
        "add_notification_subscription"
    }
    assert "add_notification_subscription" not in kb.NOTIFICATION_PRINCIPAL_ACTIONS
    assert kb.KANBAN_ACTION_PRINCIPAL_KINDS[
        "add_notification_subscription"
    ] == "kanban_service_dispatcher"
    fixed = 2_000_000_000.0
    target = _golden_target(fixed)
    vectors = {}
    for name, action, capability in (
        ("service_dispatcher", "schedule", "kanban.task.status"),
        ("worker", "complete", "kanban.task.complete"),
        ("notifier", "claim_notification_delivery", "kanban.task.notify"),
        ("telegram", "telegram-status", "telegram.olympus.status"),
    ):
        kind = kb.KANBAN_ACTION_PRINCIPAL_KINDS[action]
        principal = _golden_principal(kind, target, fixed, action=action)
        operation_id = "operation:test"
        if action == "add_notification_subscription":
            operation_id = kb.notification_subscription_operation_id(
                principal["operation_binding"]
            )
        request = kb.profile_authority_request(
            target=target, action=action, capability=capability,
            actor="agent:test", principal_binding=principal,
            operation_id=operation_id, now=fixed,
        )
        accepted = kb.validate_authority_verification(
            request, _allow_at(request, fixed), now=fixed,
        )
        assert accepted["valid"], accepted
        vectors[name] = {
            "request_id": request["request_id"],
            "result_sha256": hashlib.sha256(json.dumps(
                accepted["verification"], sort_keys=True,
                separators=(",", ":"), allow_nan=False,
            ).encode()).hexdigest(),
        }
    assert vectors == {
        "service_dispatcher": {
            "request_id": "authority-request:dda0e14b708bed6a5de99dcb5817fd59b624a0a88b7e2196053bbc90534ba82d",
            "result_sha256": "c13cf3b1018a0981d61dd7c32647460a99796ffd52bf033f9031fec73cca394f",
        },
        "worker": {
            "request_id": "authority-request:70b15cb5ed8ff50265652c3a4011998583b60c0e558e07119dd47279ada42b38",
            "result_sha256": "a889cd03d42e6a910c3f4123b010e3066fc73607a6f05d676dc97535a0b143c7",
        },
        "notifier": {
            "request_id": "authority-request:fde4b9911fbb0bcb458a7f17eb5626daca0ff6ba80d7a9aace4909c72c6a023d",
            "result_sha256": "56901caa679b8432862de89d91c747807507daea8929cc4de6e6b3d487fdb572",
        },
        "telegram": {
            "request_id": "authority-request:f501d6e8515191d4091480c73ce0ceadc7623ad102676b4730f0f5b840e7d9d4",
            "result_sha256": "6a12e62a01e91dfc2411cc2252015dfa45b8ac898109f208f60ff3352422026a",
        },
    }

    subscription_target = copy.deepcopy(target)
    subscription_target["authority"]["scope"] = ["mission:test"]
    subscription_target["authority"]["capabilities"] = ["kanban.task.notify"]
    principal = _golden_principal(
        "kanban_service_dispatcher",
        subscription_target,
        fixed,
        action="add_notification_subscription",
    )
    operation_id = kb.notification_subscription_operation_id(
        principal["operation_binding"]
    )
    subscription_request = kb.profile_authority_request(
        target=subscription_target,
        action="add_notification_subscription",
        capability="kanban.task.notify",
        actor="agent:test",
        principal_binding=principal,
        operation_id=operation_id,
        now=fixed,
    )
    accepted = kb.validate_authority_verification(
        subscription_request,
        _allow_at(subscription_request, fixed),
        now=fixed,
    )
    assert operation_id == (
        "kanban-notification-subscription:add:"
        "1b3fb3c12e26b0f76374f574bb0f87e676a31c28097f14725779a6349a97908b"
    )
    assert subscription_request["request_id"] == (
        "authority-request:"
        "a747338c51ca0a42b746b307af95e4a1ac9094b91cdf5416e6a8bfa515e5aaea"
    )
    assert hashlib.sha256(json.dumps(
        accepted["verification"],
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode()).hexdigest() == (
        "68a908a430be7ff31ece39c518733d42ffc723dc3a8676ec32be85e9de293cc4"
    )


def test_v3_request_result_are_strict_detached_and_non_mutating():
    fixed = 2_000_000_000.0
    target = _golden_target(fixed)
    request = kb.profile_authority_request(
        target=target, action="schedule", capability="kanban.task.status",
        actor="agent:test",
        principal_binding=_golden_principal("kanban_service_dispatcher", target, fixed),
        operation_id="operation:test", now=fixed,
    )
    bad = copy.deepcopy(request)
    bad["target"]["unknown"] = True
    assert not kb.validate_authority_request(bad, now=fixed)["valid"]
    result = _allow_at(request, fixed)
    result["unknown"] = True
    assert not kb.validate_authority_verification(request, result, now=fixed)["valid"]
    original = copy.deepcopy(request)

    def mutating_verifier(candidate):
        candidate["target"]["subject_id"] = "foreign"
        return _allow_at(candidate, fixed)

    context = _context(now=int(fixed))
    with pytest.raises(kb.OlympusContextError):
        kb.require_olympus_authority_verification(
            context, subject_id="task:test", subject_revision=8,
            assignee="coding", action="schedule", capability="kanban.task.status",
            actor="coding", operation_id="operation:test",
            principal=kb.OlympusMutationAuth(
                verifier=mutating_verifier, principal_type="service",
                principal_id="kanban-service-dispatcher:board:test:dispatcher:test",
                principal_source="kanban-dispatcher:board:test:dispatcher:test",
            ), expected_status="running", now=int(fixed), board_id="board:test",
        )
    assert request == original


@pytest.mark.parametrize("location", ["context", "authority", "lease"])
def test_context_rejects_unknown_fields_without_creating_rows(conn, location):
    context = _context()
    node = context if location == "context" else context[location]
    node["unknown"] = "unsafe"
    with pytest.raises(kb.OlympusContextError):
        _create(conn, context)
    assert kb.list_tasks(conn) == []


@pytest.mark.parametrize(
    "verifier",
    [
        None,
        lambda request: {**_allow(request), "decision": "DENY"},
        lambda request: {**_allow(request), "current": False},
        lambda request: {**_allow(request), "request_id": "foreign"},
        lambda request: {**_allow(request), "request": {"forged": True}},
        lambda request: (_ for _ in ()).throw(RuntimeError("issuer down")),
    ],
)
def test_create_fails_closed_on_missing_stale_or_contradictory_verifier(conn, verifier):
    context = _context()
    with pytest.raises(kb.OlympusContextError):
        kb.create_olympus_task(
            conn, olympus_context=context,
            olympus_auth=_auth(conn, context, verifier=verifier),
            title="must not exist", assignee="coding",
        )
    assert kb.list_tasks(conn) == []


@pytest.mark.parametrize(
    "mutation",
    [
        "missing-lease", "expired-lease", "revoked-lease", "foreign-lease",
        "context-agent", "lease-agent", "lease-holder", "expired-authority",
        "revoked-authority",
    ],
)
def test_creation_denies_missing_expired_revoked_foreign_or_identity_state(conn, mutation):
    context = _context()
    if mutation == "missing-lease":
        del context["lease"]
    elif mutation == "expired-lease":
        context["lease"]["expires_at"] = int(time.time()) - 1
    elif mutation == "revoked-lease":
        context["lease"]["status"] = "REVOKED"
    elif mutation == "foreign-lease":
        context["lease"]["mission_id"] = "mission-other"
    elif mutation == "context-agent":
        context["agent_id"] = "foreign"
    elif mutation == "lease-agent":
        context["lease"]["agent_id"] = "foreign"
    elif mutation == "lease-holder":
        context["lease"]["holder"] = "foreign"
    elif mutation == "expired-authority":
        context["authority"]["expires_at"] = int(time.time()) - 1
    elif mutation == "revoked-authority":
        context["authority"]["status"] = "REVOKED"
    with pytest.raises(kb.OlympusContextError):
        _create(conn, context, operation_id=f"invalid:{mutation}")
    assert kb.list_tasks(conn) == []


@pytest.mark.parametrize("mutation", ["actor", "capability", "scope"])
def test_create_denies_wrong_actor_capability_or_scope(conn, mutation):
    context = _context()
    actor = context["agent_id"]
    if mutation == "actor":
        actor = "dashboard"
    elif mutation == "capability":
        context["authority"]["capabilities"].remove(kb.OLYMPUS_CAPABILITY_CREATE)
    else:
        context["authority"]["scope"] = ["mission-other"]
    with pytest.raises(kb.OlympusContextError):
        kb.create_olympus_task(
            conn, olympus_context=context,
            olympus_auth=_auth(conn, context, actor=actor),
            title="denied", assignee="coding",
        )
    assert kb.list_tasks(conn) == []


def test_claim_and_dispatch_without_canonical_verifier_never_start_governed_work(
    conn, monkeypatch,
):
    task_id = _create(conn)
    assert kb.claim_task(conn, task_id, claimer="unverified") is None
    monkeypatch.setattr("hermes_cli.profiles.profile_exists", lambda _name: True)
    spawned = []
    result = kb.dispatch_once(
        conn, spawn_fn=lambda task, workspace: spawned.append(task.id), max_spawn=1,
    )
    assert result.spawned == [] and spawned == []
    assert kb.get_task(conn, task_id).status == "ready"


def test_review_claim_uses_the_same_canonical_gate(conn):
    context = _context()
    task_id = _create(conn, context)
    assert kb.set_task_status(
        conn, task_id, "review",
        olympus_auth=_auth(conn, context, operation_id="to-review"),
    )
    assert kb.claim_review_task(conn, task_id, claimer="unverified") is None
    claimed = kb.claim_review_task(
        conn, task_id, claimer="verified",
        olympus_auth=_auth(conn, context, operation_id="review-claim"),
    )
    assert claimed is not None


def test_restart_reinstalls_udfs_and_reverifies_exact_current_state(conn):
    context = _context()
    task_id = _create(conn, context)
    db_path = Path(conn.execute("PRAGMA database_list").fetchone()[2])
    conn.close()
    reopened = kb.connect(db_path)
    try:
        assert kb.claim_task(reopened, task_id, claimer="no-auth") is None
        assert kb.claim_task(
            reopened, task_id, claimer="verified",
            olympus_auth=_auth(reopened, context, operation_id="restart-claim"),
        ) is not None
    finally:
        reopened.close()


def test_guard_replacement_is_crash_atomic_and_reopens_complete(conn):
    def guards(connection):
        return {
            row["name"]: row["sql"]
            for row in connection.execute(
                "SELECT name,sql FROM sqlite_master WHERE type='trigger' "
                "AND (name LIKE 'olympus_%' OR name='effect_journal_immutable')"
            )
        }

    before = guards(conn)
    assert "olympus_tasks_update_guard" in before
    assert "olympus_effects_update_guard" in before

    def injected_failure():
        raise RuntimeError("injected guard replacement failure")

    kb._OLYMPUS_GUARD_INSTALL_FAILPOINT = injected_failure
    try:
        with pytest.raises(sqlite3.OperationalError):
            kb._install_olympus_write_guard(conn)
    finally:
        kb._OLYMPUS_GUARD_INSTALL_FAILPOINT = None
    assert guards(conn) == before

    db_path = Path(conn.execute("PRAGMA database_list").fetchone()[2])
    reopened = kb.connect(db_path)
    try:
        after = guards(reopened)
        assert set(after) == set(before)
        assert all(after.values())
    finally:
        reopened.close()


def test_generic_and_external_transaction_paths_cannot_inject_or_reuse_permits(conn):
    with pytest.raises(TypeError):
        kb.create_task(
            conn, title="generic", assignee="coding",
            olympus_context=_context(),  # type: ignore[call-arg]
        )
    task_id = _create(conn)
    context = _context()
    conn.execute("BEGIN")
    try:
        with pytest.raises(kb.OlympusContextError) as caught:
            kb.edit_task_fields(
                conn, task_id, priority=1,
                olympus_auth=_auth(conn, context, operation_id="external"),
            )
        assert caught.value.reason == "olympus_external_transaction_forbidden"
    finally:
        conn.rollback()
    assert conn._olympus_permit_registry == {}
    with pytest.raises(kb.OlympusContextError):
        kb.add_comment(conn, task_id, "coding", "no verifier")


def test_persistent_main_schema_guards_block_unmanaged_sql_after_restart(conn):
    task_id = _create(conn)
    db_path = Path(conn.execute("PRAGMA database_list").fetchone()[2])
    conn.close()
    raw = sqlite3.connect(db_path)
    try:
        with pytest.raises(sqlite3.OperationalError):
            raw.execute("UPDATE tasks SET status='done' WHERE id=?", (task_id,))
        with pytest.raises(sqlite3.OperationalError):
            raw.execute(
                "INSERT INTO task_comments(task_id,author,body,created_at) VALUES(?,?,?,?)",
                (task_id, "raw", "forged", int(time.time())),
            )
        raw.rollback()
    finally:
        raw.close()
    reopened = kb.connect(db_path)
    try:
        assert kb.get_task(reopened, task_id).status == "ready"
        triggers = {
            row[0] for row in reopened.execute(
                "SELECT name FROM sqlite_master WHERE type='trigger' AND name LIKE 'olympus_%'"
            )
        }
        assert "olympus_tasks_update_guard" in triggers
        assert "olympus_effects_update_guard" in triggers
    finally:
        reopened.close()


def test_registered_worker_session_rechecks_exact_runtime_each_operation(conn, monkeypatch):
    context, task_id, run, identity = _registered_run(conn, monkeypatch)
    runtime = kb.olympus_worker_runtime_snapshot(
        conn, worker_task_id=task_id, run_id=run.id, claim_lock=run.claim_lock,
    )
    session = kb.OlympusWorkerAuthSession(
        verifier=_allow, board_id=runtime["board_id"], task_id=task_id,
        run_id=run.id, run_subject_revision=runtime["run_subject_revision"],
        claim_lock=run.claim_lock, assignee="coding", process_identity=identity,
        dispatcher_instance_id="test-dispatcher",
    )
    assert kb.heartbeat_worker(
        conn, task_id, expected_run_id=run.id,
        olympus_auth=session.issue(conn, "heartbeat_worker", kb.OLYMPUS_CAPABILITY_HEARTBEAT),
    )
    foreign = kb.ProcessIdentity(identity.host_id, identity.boot_id, identity.pid, "reused")
    monkeypatch.setattr(kb, "read_process_identity", lambda _pid: foreign)
    with pytest.raises(kb.OlympusContextError):
        session.issue(conn, "complete", kb.OLYMPUS_CAPABILITY_COMPLETE)


def test_verified_status_binds_board_and_exact_fresh_state(conn):
    context = _context()
    task_id = _create(
        conn, context, initial_status="blocked", operation_id="status:create"
    )
    revision = kb.get_task(conn, task_id).record_revision
    captured = {}

    def capture(request):
        captured["request"] = copy.deepcopy(request)
        captured["result"] = _allow(request)
        return copy.deepcopy(captured["result"])

    status = kb.verified_olympus_task_status(
        conn,
        task_id,
        subject_revision=revision,
        olympus_auth=_auth(
            conn, context, verifier=capture, operation_id="status:inspect"
        ),
    )
    assert status["status"] == "blocked"
    assert captured["request"]["principal"]["board_id"] == (
        kb._connection_board_identity(conn)
    )

    def wrong_board(request):
        result = _allow(request)
        result["verified_principal"]["board_id"] = "foreign-board"
        return result

    with pytest.raises(kb.OlympusContextError) as caught:
        kb.verified_olympus_task_status(
            conn,
            task_id,
            subject_revision=revision,
            olympus_auth=_auth(
                conn,
                context,
                verifier=wrong_board,
                operation_id="status:wrong-board",
            ),
        )
    assert caught.value.reason == "olympus_authority_verification_denied"

    assert kb.archive_task(
        conn,
        task_id,
        olympus_auth=_auth(conn, context, operation_id="status:archive"),
    )
    current_revision = kb.get_task(conn, task_id).record_revision
    with pytest.raises(kb.OlympusContextError) as caught:
        kb.verified_olympus_task_status(
            conn,
            task_id,
            subject_revision=current_revision,
            olympus_auth=_auth(
                conn,
                context,
                verifier=lambda _request: copy.deepcopy(captured["result"]),
                operation_id="status:stale-result",
            ),
        )
    assert caught.value.reason == "olympus_authority_verification_denied"


def test_worker_registration_binds_persisted_dispatcher_to_verified_principal(
    conn, monkeypatch,
):
    context = _context()
    task_id = _create(conn, context, operation_id="dispatcher-bind:create")
    run = kb.reserve_worker_run(
        conn,
        task_id,
        claimer=kb._claimer_id(),
        olympus_auth=_auth(conn, context, operation_id="dispatcher-bind:claim"),
    )
    assert run is not None and run.launch_token
    assert kb.mark_worker_workspace_ready(
        conn,
        task_id=task_id,
        run_id=run.id,
        launch_token=run.launch_token,
        workspace_snapshot={"path": "/tmp/exact"},
        olympus_auth=_auth(conn, context, operation_id="dispatcher-bind:workspace"),
    )
    assert kb.mark_worker_starting(
        conn,
        task_id=task_id,
        run_id=run.id,
        launch_token=run.launch_token,
        olympus_auth=_auth(conn, context, operation_id="dispatcher-bind:starting"),
    )
    identity = kb.ProcessIdentity("host:worker", "boot:worker", 6262, "birth:worker")
    monkeypatch.setattr(
        kb,
        "read_process_identity",
        lambda pid: identity if int(pid) == identity.pid else None,
    )
    with pytest.raises(kb.OlympusContextError) as caught:
        kb.register_worker_process(
            conn,
            task_id=task_id,
            run_id=run.id,
            launch_token=run.launch_token,
            process_identity=identity,
            dispatcher_instance_id="foreign-dispatcher",
            olympus_auth=_auth(
                conn, context, operation_id="dispatcher-bind:mismatch"
            ),
        )
    assert caught.value.reason == "olympus_dispatcher_identity_conflict"
    assert kb.get_run(conn, run.id).process_state == "starting"

    revision = kb.get_task(conn, task_id).record_revision
    binding = {
        "schema_version": kb.WORKER_REGISTRATION_WRITE_SCHEMA,
        "action": "register_worker_process",
        "task_id": task_id,
        "task_record_revision": revision,
        "dispatcher_instance_id": "test-dispatcher",
    }
    with kb.write_txn(conn):
        with kb._task_mutation_permit(
            conn,
            task_id,
            action="register_worker_process",
            capability=kb.OLYMPUS_CAPABILITY_CLAIM,
            auth=_auth(conn, context, operation_id="dispatcher-bind:sql"),
            mutation_binding=binding,
        ):
            with pytest.raises(sqlite3.IntegrityError):
                conn.execute(
                    "UPDATE task_runs SET dispatcher_instance_id='foreign-dispatcher' "
                    "WHERE id=?",
                    (run.id,),
                )
    assert kb.register_worker_process(
        conn,
        task_id=task_id,
        run_id=run.id,
        launch_token=run.launch_token,
        process_identity=identity,
        dispatcher_instance_id="test-dispatcher",
        olympus_auth=_auth(conn, context, operation_id="dispatcher-bind:exact"),
    )


def test_process_fenced_manual_reclaim_stages_executes_and_settles(conn, monkeypatch):
    context, task_id, run, identity = _registered_run(conn, monkeypatch)
    signals = []
    assert kb.reclaim_task(
        conn, task_id, reason="operator containment",
        signal_fn=lambda pid, sig: signals.append((pid, sig)),
        olympus_auth=_auth(conn, context, operation_id="reclaim"),
    )
    assert signals and signals[0][0] == identity.pid
    assert kb.get_task(conn, task_id).status == "blocked"
    settled = conn.execute(
        "SELECT * FROM kanban_effect_journal WHERE task_id=?", (task_id,)
    ).fetchone()
    assert settled["state"] == "applied"
    assert settled["worker_start_token"] == identity.start_token
    assert kb.get_run(conn, run.id).process_state == "termination_sent"


def test_process_fence_never_signals_reused_pid(conn, monkeypatch):
    context, task_id, _run, identity = _registered_run(conn, monkeypatch)
    reused = kb.ProcessIdentity(identity.host_id, identity.boot_id, identity.pid, "new-birth")
    monkeypatch.setattr(kb, "read_process_identity", lambda _pid: reused)
    signals = []
    assert kb.reclaim_task(
        conn, task_id, signal_fn=lambda pid, sig: signals.append((pid, sig)),
        olympus_auth=_auth(conn, context, operation_id="pid-reuse"),
    )
    assert signals == []
    effect = conn.execute(
        "SELECT state FROM kanban_effect_journal WHERE task_id=?", (task_id,)
    ).fetchone()
    assert effect["state"] == "identity_mismatch"


def test_watchdog_timeout_uses_the_same_durable_process_fence(conn, monkeypatch):
    context, task_id, _run, identity = _registered_run(
        conn, monkeypatch, max_runtime_seconds=1,
    )
    original_time = time.time
    future = original_time() + 5
    monkeypatch.setattr(kb.time, "time", lambda: future)
    monkeypatch.setattr(
        kb, "read_process_identity", lambda pid: identity if pid == identity.pid else None,
    )
    signals = []
    assert kb.enforce_max_runtime(
        conn, signal_fn=lambda pid, sig: signals.append((pid, sig)),
        olympus_auth=_auth(conn, context, operation_id="timeout"),
    ) == [task_id]
    assert signals and kb.get_task(conn, task_id).status == "blocked"
    assert conn.execute(
        "SELECT state FROM kanban_effect_journal WHERE task_id=?", (task_id,)
    ).fetchone()["state"] == "applied"


@pytest.mark.parametrize(
    ("crash_stage", "expected_effect", "expected_signals", "expected_reconciled"),
    (
        ("after_stage", "pending", 0, 0),
        ("after_claim", "unknown", 0, 1),
        ("after_execute", "unknown", 1, 1),
        ("after_settle", "applied", 1, 0),
    ),
)
def test_worker_effect_crash_boundaries_reopen_and_reconcile_without_replay(
    conn, monkeypatch, crash_stage, expected_effect, expected_signals,
    expected_reconciled,
):
    context, task_id, run, identity = _registered_run(conn, monkeypatch)
    signals = []

    def failpoint(stage: str) -> None:
        if stage == crash_stage:
            raise RuntimeError(f"crash:{stage}")

    effect_id = None
    try:
        if crash_stage == "after_stage":
            kb._OLYMPUS_EFFECT_EXECUTION_FAILPOINT = failpoint
        with pytest.raises(RuntimeError, match=f"crash:{crash_stage}"):
            if crash_stage == "after_stage":
                kb.stage_worker_termination(
                    conn,
                    task_id=task_id,
                    run_id=run.id,
                    launch_token=run.launch_token,
                    process_identity=identity,
                    operation_id=f"crash-effect:{crash_stage}",
                    reason="injected crash",
                    source_identity={"dispatcher": "test"},
                    olympus_auth=_auth(
                        conn, context, operation_id=f"crash-stage:{crash_stage}"
                    ),
                )
            else:
                effect_id = kb.stage_worker_termination(
                    conn,
                    task_id=task_id,
                    run_id=run.id,
                    launch_token=run.launch_token,
                    process_identity=identity,
                    operation_id=f"crash-effect:{crash_stage}",
                    reason="injected crash",
                    source_identity={"dispatcher": "test"},
                    olympus_auth=_auth(
                        conn, context, operation_id=f"crash-stage:{crash_stage}"
                    ),
                )
                kb._OLYMPUS_EFFECT_EXECUTION_FAILPOINT = failpoint
                kb.execute_worker_termination_effect(
                    conn,
                    effect_id,
                    olympus_auth=_auth(
                        conn, context, operation_id=f"crash-execute:{crash_stage}"
                    ),
                    signal_fn=lambda pid, sig: signals.append((pid, sig)),
                )
    finally:
        kb._OLYMPUS_EFFECT_EXECUTION_FAILPOINT = None
    if effect_id is None:
        effect_id = int(conn.execute(
            "SELECT id FROM kanban_effect_journal WHERE task_id=?", (task_id,),
        ).fetchone()[0])
    db_path = Path(conn.execute("PRAGMA database_list").fetchone()[2])
    conn.close()
    kb._INITIALIZED_PATHS.discard(str(db_path.resolve()))
    with kb.connect(db_path) as reopened:
        result = kb.reconcile_restart_state(
            reopened,
            olympus_auth=_auth(
                reopened, context, operation_id=f"restart:{crash_stage}"
            ),
        )
        assert result == {"effects": expected_reconciled, "worker_runs": 0}
        assert reopened.execute(
            "SELECT state FROM kanban_effect_journal WHERE id=?", (effect_id,),
        ).fetchone()[0] == expected_effect
        process_state = reopened.execute(
            "SELECT process_state FROM task_runs WHERE id=?", (run.id,),
        ).fetchone()[0]
        assert process_state == (
            "termination_pending" if crash_stage == "after_stage"
            else "termination_sent" if crash_stage == "after_settle"
            else "identity_unverified"
        )
    assert len(signals) == expected_signals


def test_restart_reconciliation_blocks_unfinished_worker_start(conn, monkeypatch):
    context = _context()
    task_id = _create(conn, context, operation_id="restart-start:create")
    run = kb.reserve_worker_run(
        conn,
        task_id,
        claimer=kb._claimer_id(),
        olympus_auth=_auth(conn, context, operation_id="restart-start:reserve"),
    )
    assert run is not None and run.launch_token
    assert kb.mark_worker_workspace_ready(
        conn,
        task_id=task_id,
        run_id=run.id,
        launch_token=run.launch_token,
        workspace_snapshot={"path": "/tmp/restart"},
        olympus_auth=_auth(conn, context, operation_id="restart-start:workspace"),
    )
    assert kb.mark_worker_starting(
        conn,
        task_id=task_id,
        run_id=run.id,
        launch_token=run.launch_token,
        olympus_auth=_auth(conn, context, operation_id="restart-start:starting"),
    )
    monkeypatch.setattr(kb, "read_process_identity", lambda _pid: None)
    db_path = Path(conn.execute("PRAGMA database_list").fetchone()[2])
    conn.close()
    kb._INITIALIZED_PATHS.discard(str(db_path.resolve()))
    with kb.connect(db_path) as reopened:
        assert kb.reconcile_restart_state(
            reopened,
            olympus_auth=_auth(reopened, context, operation_id="restart-start:reconcile"),
        ) == {"effects": 0, "worker_runs": 1}
        assert kb.get_task(reopened, task_id).status == "blocked"
        assert kb.get_run(reopened, run.id).process_state == "identity_unverified"


def test_effect_transition_guards_and_post_cas_claim_row(conn, monkeypatch):
    ordinary = kb.create_task(conn, title="ordinary", assignee="coding")
    event_id = kb.list_events(conn, ordinary)[-1].id
    effect_id = kb.reserve_notification_effect(
        conn, task_id=ordinary, effect_kind="notify_text",
        operation_id="notify:ordinary:1", event_id=event_id,
        destination_key="telegram:chat", part="text", payload={"message": "hi"},
        source_identity={"gateway": "test"},
    )
    applying = kb.claim_notification_effect(conn, effect_id)
    assert applying is not None and applying["state"] == "applying"
    assert kb.finish_notification_effect(
        conn, effect_id, success=False, may_have_sent=True,
    ) == "unknown"

    context, task_id, run, identity = _registered_run(conn, monkeypatch)
    staged = kb.stage_worker_termination(
        conn, task_id=task_id, run_id=run.id, launch_token=run.launch_token,
        process_identity=identity, operation_id="effect:guarded:1", reason="test",
        source_identity={"dispatcher": "test"},
        olympus_auth=_auth(conn, context, operation_id="stage"),
    )
    raw = sqlite3.connect(conn.execute("PRAGMA database_list").fetchone()[2])
    try:
        with pytest.raises(sqlite3.OperationalError):
            raw.execute(
                "UPDATE kanban_effect_journal SET operation_id='forged' WHERE id=?",
                (staged,),
            )
        with pytest.raises(sqlite3.OperationalError):
            raw.execute("DELETE FROM kanban_effect_journal WHERE id=?", (staged,))
        raw.rollback()
    finally:
        raw.close()


def test_notification_effect_permit_binds_exact_row_and_transition_evidence(
    conn, monkeypatch,
):
    context = _context()
    task_id = _create(conn, context, operation_id="effect:create")
    assert kb.add_notify_sub(
        conn,
        task_id=task_id,
        platform="telegram",
        chat_id="effect-chat",
        user_id="effect-user",
        notifier_profile="default",
        olympus_auth=_auth(conn, context),
    )
    event_id = kb.list_events(conn, task_id)[-1].id
    effect_key = "notify:effect:exact:text"
    identity = kb.ProcessIdentity("host:gateway", "boot:gateway", 5252, "birth:gateway")
    monkeypatch.setattr(
        kb,
        "read_process_identity",
        lambda pid: identity if int(pid) == identity.pid else None,
    )

    def notifier_auth(action: str, state: str):
        return kb.olympus_notifier_auth(
            conn,
            verifier=_allow,
            task_id=task_id,
            platform="telegram",
            chat_id="effect-chat",
            thread_id="",
            source_event_id=event_id,
            effect_id=effect_key,
            effect_state=state,
            gateway_process_identity=identity,
            action=action,
        )

    reserve_auth = notifier_auth("reserve_notification_effect", "unreserved")
    with pytest.raises(kb.OlympusContextError) as caught:
        kb.reserve_notification_effect(
            conn,
            task_id=task_id,
            effect_kind="notify_text",
            operation_id=effect_key,
            event_id=event_id,
            destination_key="telegram:effect-chat:",
            part="text",
            payload={"message": "exact"},
            source_identity={"forged": True},
            olympus_auth=reserve_auth,
        )
    assert caught.value.reason == "olympus_effect_source_identity_conflict"

    payload, payload_sha256 = kb._canonical_effect_payload({"message": "exact"})
    source, _ = kb._canonical_effect_payload(
        kb._canonical_notifier_effect_source(reserve_auth)
    )
    revision = kb.get_task(conn, task_id).record_revision
    binding = {
        "schema_version": kb.NOTIFICATION_EFFECT_RESERVATION_SCHEMA,
        "action": "reserve_notification_effect",
        "task_id": task_id,
        "task_record_revision": revision,
        "effect_kind": "notify_text",
        "operation_id": effect_key,
        "event_id": event_id,
        "destination_key": "telegram:effect-chat:",
        "part": "text",
        "source_identity": source,
        "payload": payload,
        "payload_sha256": payload_sha256,
        "target_post_revision": revision,
    }

    def insert_effect(permit, **changes):
        values = {
            "effect_kind": "notify_text",
            "operation_id": effect_key,
            "part": "text",
            "source_identity": source,
            "payload": payload,
            "payload_sha256": payload_sha256,
            "target_post_revision": revision,
        }
        values.update(changes)
        return conn.execute(
            "INSERT INTO kanban_effect_journal (effect_kind,operation_id,task_id,"
            "event_id,destination_key,part,auth_root_id,auth_root_revision,"
            "target_pre_revision,target_post_revision,source_identity,payload,"
            "payload_sha256,state,created_at,updated_at) "
            "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,'pending',?,?)",
            (
                values["effect_kind"], values["operation_id"], task_id,
                event_id, "telegram:effect-chat:", values["part"],
                permit["auth_root_id"], permit["auth_root_revision"], revision,
                values["target_post_revision"], values["source_identity"],
                values["payload"], values["payload_sha256"],
                int(time.time()), int(time.time()),
            ),
        )

    with kb.write_txn(conn):
        with kb._task_mutation_permit(
            conn,
            task_id,
            action="reserve_notification_effect",
            capability=kb.OLYMPUS_CAPABILITY_NOTIFY,
            auth=reserve_auth,
            mutation_binding=binding,
        ):
            permit = kb._issued_permit_row(conn, task_id)
            assert permit is not None
            for changes in (
                {"payload_sha256": "0" * 64},
                {"source_identity": source.replace(":", ": ", 1)},
                {"source_identity": '{"forged":true}'},
                {"part": "artifact"},
                {"effect_kind": "notify_artifact"},
                {"target_post_revision": revision + 1},
            ):
                with pytest.raises(sqlite3.IntegrityError):
                    insert_effect(permit, **changes)
            inserted = insert_effect(permit)
            effect_id = int(inserted.lastrowid)
            with pytest.raises(sqlite3.IntegrityError):
                insert_effect(
                    permit,
                    effect_kind="notify_artifact",
                    operation_id=effect_key,
                    part="artifacts",
                )

    claim_auth = notifier_auth("claim_notification_effect", "pending")
    row = conn.execute(
        "SELECT * FROM kanban_effect_journal WHERE id=?", (effect_id,),
    ).fetchone()
    claim_at = int(time.time())
    claim_binding = {
        "schema_version": kb.NOTIFICATION_EFFECT_TRANSITION_SCHEMA,
        "action": "claim_notification_effect",
        "task_id": task_id,
        "task_record_revision": revision,
        "effect_row_id": effect_id,
        "effect_kind": "notify_text",
        "operation_id": effect_key,
        "event_id": event_id,
        "destination_key": "telegram:effect-chat:",
        "old_state": "pending",
        "new_state": "applying",
        "error": row["error"],
        "updated_at": claim_at,
        "applied_at": row["applied_at"],
    }
    with kb.write_txn(conn):
        with kb._task_mutation_permit(
            conn,
            task_id,
            action="claim_notification_effect",
            capability=kb.OLYMPUS_CAPABILITY_NOTIFY,
            auth=claim_auth,
            mutation_binding=claim_binding,
        ):
            with pytest.raises(sqlite3.IntegrityError):
                conn.execute(
                    "UPDATE kanban_effect_journal SET state='applying',error='forged',"
                    "updated_at=?,applied_at=? WHERE id=?",
                    (claim_at, claim_at, effect_id),
                )

    assert kb.claim_notification_effect(
        conn, effect_id, olympus_auth=claim_auth,
    )["state"] == "applying"
    finish_auth = notifier_auth("finish_notification_effect", "applying")
    finish_at = int(time.time())
    finish_binding = {
        "schema_version": kb.NOTIFICATION_EFFECT_TRANSITION_SCHEMA,
        "action": "finish_notification_effect",
        "task_id": task_id,
        "task_record_revision": revision,
        "effect_row_id": effect_id,
        "effect_kind": "notify_text",
        "operation_id": effect_key,
        "event_id": event_id,
        "destination_key": "telegram:effect-chat:",
        "old_state": "applying",
        "new_state": "applied",
        "error": None,
        "updated_at": finish_at,
        "applied_at": finish_at,
    }
    with kb.write_txn(conn):
        with kb._task_mutation_permit(
            conn,
            task_id,
            action="finish_notification_effect",
            capability=kb.OLYMPUS_CAPABILITY_NOTIFY,
            auth=finish_auth,
            mutation_binding=finish_binding,
        ):
            with pytest.raises(sqlite3.IntegrityError):
                conn.execute(
                    "UPDATE kanban_effect_journal SET state='applied',error='forged',"
                    "updated_at=?,applied_at=? WHERE id=?",
                    (finish_at, finish_at + 1, effect_id),
                )
    assert kb.finish_notification_effect(
        conn,
        effect_id,
        success=True,
        may_have_sent=False,
        olympus_auth=finish_auth,
    ) == "applied"


def test_notification_cursor_and_effect_permits_cannot_cross_destination_or_row(
    conn, monkeypatch,
):
    context = _context()
    task_id = _create(conn, context, operation_id="notify-cross:create")
    for chat_id in ("cross-a", "cross-b"):
        assert kb.add_notify_sub(
            conn,
            task_id=task_id,
            platform="telegram",
            chat_id=chat_id,
            user_id=f"user-{chat_id}",
            notifier_profile="default",
            olympus_auth=_auth(
                conn, context, operation_id=f"notify-cross:subscribe:{chat_id}"
            ),
        )
    event_id = kb.list_events(conn, task_id)[-1].id
    identity = kb.ProcessIdentity("host:cross", "boot:cross", 5353, "birth:cross")
    monkeypatch.setattr(
        kb,
        "read_process_identity",
        lambda pid: identity if int(pid) == identity.pid else None,
    )

    def notifier(action: str, chat_id: str, effect_id: str, state: str = "unreserved"):
        return kb.olympus_notifier_auth(
            conn,
            verifier=_allow,
            task_id=task_id,
            platform="telegram",
            chat_id=chat_id,
            thread_id="",
            source_event_id=event_id,
            effect_id=effect_id,
            effect_state=state,
            gateway_process_identity=identity,
            action=action,
        )

    claim_auth = notifier("claim_notification_delivery", "cross-a", "cursor:claim")
    old_cursor, claimed_cursor, events = kb.claim_unseen_events_for_sub(
        conn,
        task_id=task_id,
        platform="telegram",
        chat_id="cross-a",
        olympus_auth=claim_auth,
    )
    assert old_cursor == 0 and claimed_cursor == event_id and events
    with kb.write_txn(conn):
        with kb._task_mutation_permit(
            conn,
            task_id,
            action="rewind_notification_cursor",
            capability=kb.OLYMPUS_CAPABILITY_NOTIFY,
            auth=notifier(
                "rewind_notification_cursor", "cross-a", "cursor:rewind"
            ),
        ):
            with pytest.raises(sqlite3.IntegrityError):
                conn.execute(
                    "UPDATE kanban_notify_subs SET last_event_id=? "
                    "WHERE task_id=? AND platform='telegram' AND chat_id='cross-b'",
                    (event_id, task_id),
                )
    assert kb.rewind_notify_cursor(
        conn,
        task_id=task_id,
        platform="telegram",
        chat_id="cross-a",
        claimed_cursor=claimed_cursor,
        old_cursor=old_cursor,
        olympus_auth=notifier(
            "rewind_notification_cursor", "cross-a", "cursor:rewind:exact"
        ),
    )
    kb.advance_notify_cursor(
        conn,
        task_id=task_id,
        platform="telegram",
        chat_id="cross-a",
        new_cursor=event_id,
        olympus_auth=notifier(
            "advance_notification_cursor", "cross-a", "cursor:advance"
        ),
    )
    assert {
        row["chat_id"]: row["last_event_id"] for row in kb.list_notify_subs(conn, task_id)
    } == {"cross-a": event_id, "cross-b": 0}

    effects = {}
    for chat_id in ("cross-a", "cross-b"):
        operation_id = f"effect:{chat_id}"
        effects[chat_id] = kb.reserve_notification_effect(
            conn,
            task_id=task_id,
            effect_kind="notify_text",
            operation_id=operation_id,
            event_id=event_id,
            destination_key=f"telegram:{chat_id}:",
            part="text",
            payload={"message": chat_id},
            olympus_auth=notifier(
                "reserve_notification_effect", chat_id, operation_id
            ),
        )
    effect_a = conn.execute(
        "SELECT * FROM kanban_effect_journal WHERE id=?", (effects["cross-a"],),
    ).fetchone()
    transition_at = int(time.time())
    binding = {
        "schema_version": kb.NOTIFICATION_EFFECT_TRANSITION_SCHEMA,
        "action": "claim_notification_effect",
        "task_id": task_id,
        "task_record_revision": kb.get_task(conn, task_id).record_revision,
        "effect_row_id": int(effect_a["id"]),
        "effect_kind": str(effect_a["effect_kind"]),
        "operation_id": str(effect_a["operation_id"]),
        "event_id": int(effect_a["event_id"]),
        "destination_key": str(effect_a["destination_key"]),
        "old_state": "pending",
        "new_state": "applying",
        "error": effect_a["error"],
        "updated_at": transition_at,
        "applied_at": effect_a["applied_at"],
    }
    with kb.write_txn(conn):
        with kb._task_mutation_permit(
            conn,
            task_id,
            action="claim_notification_effect",
            capability=kb.OLYMPUS_CAPABILITY_NOTIFY,
            auth=notifier(
                "claim_notification_effect", "cross-a", "effect:cross-a", "pending"
            ),
            mutation_binding=binding,
        ):
            with pytest.raises(sqlite3.IntegrityError):
                conn.execute(
                    "UPDATE kanban_effect_journal SET state='applying',updated_at=? "
                    "WHERE id=?",
                    (transition_at, effects["cross-b"]),
                )
    states = {
        row["destination_key"]: row["state"]
        for row in conn.execute(
            "SELECT destination_key,state FROM kanban_effect_journal "
            "WHERE id IN (?,?)", (effects["cross-a"], effects["cross-b"]),
        )
    }
    assert states == {
        "telegram:cross-a:": "pending", "telegram:cross-b:": "pending",
    }


def test_v4_subscription_first_insert_exact_readd_and_conflict_semantics(conn):
    context = _context()
    task_id = _create(conn, context, operation_id="subscription:create")
    requests = []

    def verifier(request):
        requests.append(copy.deepcopy(request))
        return _allow(request)

    assert kb.add_notify_sub(
        conn,
        task_id=task_id,
        platform="telegram",
        chat_id="chat-1",
        thread_id=None,
        user_id="user-1",
        notifier_profile="default",
        olympus_auth=_auth(conn, context, verifier=verifier),
    )
    first = requests[-1]
    assert first["principal"]["kind"] == "kanban_service_dispatcher"
    assert first["principal"]["operation_binding"] == {
        "schema_version": kb.NOTIFICATION_SUBSCRIPTION_OPERATION_SCHEMA,
        "action": "add_notification_subscription",
        "board_id": kb._connection_board_identity(conn),
        "task_id": task_id,
        "task_record_revision": 1,
        "platform": "telegram",
        "chat_id": "chat-1",
        "thread_id": "",
        "user_id": "user-1",
        "notifier_profile": "default",
    }
    assert first["operation_id"] == kb.notification_subscription_operation_id(
        first["principal"]["operation_binding"]
    )
    sub = kb.list_notify_subs(conn, task_id)[0]
    assert sub["last_event_id"] == 0
    assert kb.get_task(conn, task_id).record_revision == 2

    assert not kb.add_notify_sub(
        conn,
        task_id=task_id,
        platform="telegram",
        chat_id="chat-1",
        user_id="user-1",
        notifier_profile="default",
        olympus_auth=_auth(conn, context, verifier=verifier),
    )
    assert requests[-1]["principal"]["operation_binding"][
        "task_record_revision"
    ] == 2
    assert kb.get_task(conn, task_id).record_revision == 2

    with pytest.raises(kb.OlympusContextError) as caught:
        kb.add_notify_sub(
            conn,
            task_id=task_id,
            platform="telegram",
            chat_id="chat-1",
            user_id="user-foreign",
            notifier_profile="default",
            olympus_auth=_auth(conn, context, verifier=verifier),
        )
    assert caught.value.reason == "notification_subscription_identity_conflict"
    assert kb.list_notify_subs(conn, task_id) == [sub]


def test_v4_subscription_denies_missing_stale_reused_and_generic_authority(conn):
    context = _context()
    task_id = _create(conn, context, operation_id="subscription:abuse:create")
    with pytest.raises(kb.OlympusContextError):
        kb.add_notify_sub(
            conn, task_id=task_id, platform="telegram", chat_id="generic",
        )
    with pytest.raises(kb.OlympusContextError):
        kb.add_notify_sub(
            conn,
            task_id=task_id,
            platform="telegram",
            chat_id="missing-verifier",
            olympus_auth=_auth(conn, context, verifier=None),
        )

    def stale_revision(request):
        result = _allow(request)
        result["request"]["target"]["subject_revision"] -= 1
        result["target_verification"]["subject"]["subject_revision"] -= 1
        return result

    with pytest.raises(kb.OlympusContextError):
        kb.add_notify_sub(
            conn,
            task_id=task_id,
            platform="telegram",
            chat_id="stale",
            olympus_auth=_auth(conn, context, verifier=stale_revision),
        )

    captured = {}

    def capture(request):
        captured["result"] = _allow(request)
        return copy.deepcopy(captured["result"])

    assert kb.add_notify_sub(
        conn,
        task_id=task_id,
        platform="telegram",
        chat_id="bound",
        olympus_auth=_auth(conn, context, verifier=capture),
    )
    with pytest.raises(kb.OlympusContextError):
        kb.add_notify_sub(
            conn,
            task_id=task_id,
            platform="telegram",
            chat_id="foreign",
            olympus_auth=_auth(
                conn,
                context,
                verifier=lambda _request: copy.deepcopy(captured["result"]),
            ),
        )
    assert {row["chat_id"] for row in kb.list_notify_subs(conn, task_id)} == {
        "bound"
    }


def test_v4_subscription_permit_and_sql_guards_bind_the_exact_tuple(conn):
    context = _context()
    task_id = _create(conn, context, operation_id="subscription:guard:create")
    assert kb.add_notify_sub(
        conn,
        task_id=task_id,
        platform="telegram",
        chat_id="bound",
        user_id="user-1",
        notifier_profile="default",
        olympus_auth=_auth(conn, context),
    )
    revision = kb.get_task(conn, task_id).record_revision

    def binding(chat_id: str) -> dict:
        return {
            "schema_version": kb.NOTIFICATION_SUBSCRIPTION_OPERATION_SCHEMA,
            "action": "add_notification_subscription",
            "board_id": kb._connection_board_identity(conn),
            "task_id": task_id,
            "task_record_revision": revision,
            "platform": "telegram",
            "chat_id": chat_id,
            "thread_id": "",
            "user_id": "user-1",
            "notifier_profile": "default",
        }

    with kb.write_txn(conn):
        with kb._task_mutation_permit(
            conn,
            task_id,
            action="add_notification_subscription",
            capability=kb.OLYMPUS_CAPABILITY_NOTIFY,
            auth=_auth(conn, context),
            operation_binding=binding("bound"),
        ):
            with pytest.raises(kb.OlympusContextError) as caught:
                kb._authorize_task_mutation(
                    conn,
                    task_id,
                    action="add_notification_subscription",
                    capability=kb.OLYMPUS_CAPABILITY_NOTIFY,
                    auth=_auth(conn, context),
                    operation_binding=binding("foreign"),
                )
            assert caught.value.reason == "olympus_permit_scope_conflict"
            with pytest.raises(sqlite3.IntegrityError):
                conn.execute(
                    "INSERT INTO kanban_notify_subs "
                    "(task_id,platform,chat_id,thread_id,user_id,"
                    "notifier_profile,created_at,last_event_id) "
                    "VALUES (?,?,?,?,?,?,?,?)",
                    (
                        task_id, "telegram", "foreign", "", "user-1",
                        "default", int(time.time()), 0,
                    ),
                )
            with pytest.raises(sqlite3.IntegrityError):
                conn.execute(
                    "UPDATE kanban_notify_subs SET user_id='foreign' "
                    "WHERE task_id=? AND platform='telegram' AND chat_id='bound'",
                    (task_id,),
                )
            with pytest.raises(sqlite3.IntegrityError):
                conn.execute(
                    "DELETE FROM kanban_notify_subs "
                    "WHERE task_id=? AND platform='telegram' AND chat_id='bound'",
                    (task_id,),
                )

    db_path = conn.execute("PRAGMA database_list").fetchone()[2]
    raw = sqlite3.connect(db_path)
    try:
        with pytest.raises(sqlite3.OperationalError):
            raw.execute(
                "INSERT INTO kanban_notify_subs "
                "(task_id,platform,chat_id,thread_id,created_at,last_event_id) "
                "VALUES (?,?,?,?,?,?)",
                (task_id, "telegram", "raw", "", int(time.time()), 0),
            )
        raw.rollback()
    finally:
        raw.close()


def test_v4_notifier_remove_is_bound_to_the_exact_persisted_destination(
    conn, monkeypatch,
):
    context = _context()
    task_id = _create(conn, context, operation_id="subscription:remove:create")
    for chat_id in ("chat-a", "chat-b"):
        assert kb.add_notify_sub(
            conn,
            task_id=task_id,
            platform="telegram",
            chat_id=chat_id,
            user_id=f"user-{chat_id}",
            notifier_profile="default",
            olympus_auth=_auth(conn, context),
        )
    event_id = kb.list_events(conn, task_id)[-1].id
    identity = kb.ProcessIdentity("host:test", "boot:test", 4343, "birth:test")
    monkeypatch.setattr(
        kb,
        "read_process_identity",
        lambda pid: identity if int(pid) == identity.pid else None,
    )
    auth = kb.olympus_notifier_auth(
        conn,
        verifier=_allow,
        task_id=task_id,
        platform="telegram",
        chat_id="chat-a",
        thread_id="",
        source_event_id=event_id,
        effect_id="effect:remove",
        effect_state="unreserved",
        gateway_process_identity=identity,
        action="remove_notification_subscription",
    )
    with pytest.raises(sqlite3.IntegrityError):
        kb.remove_notify_sub(
            conn,
            task_id=task_id,
            platform="telegram",
            chat_id="chat-b",
            olympus_auth=auth,
        )
    assert kb.remove_notify_sub(
        conn,
        task_id=task_id,
        platform="telegram",
        chat_id="chat-a",
        olympus_auth=auth,
    )
    assert [row["chat_id"] for row in kb.list_notify_subs(conn, task_id)] == [
        "chat-b"
    ]


def test_governed_create_idempotency_compares_complete_immutable_payload(conn):
    context = _context()
    parent_b = kb.create_task(conn, title="parent-b", assignee="coding")
    base = {
        "title": "  exact remediation  ",
        "body": "bounded body",
        "assignee": "coding",
        "created_by": "review-autonomy",
        "workspace_kind": "scratch",
        "workspace_path": None,
        "branch_name": None,
        "tenant": "olympus",
        "priority": 7,
        "parents": [],
        "triage": False,
        "idempotency_key": "remediation:exact:1",
        "max_runtime_seconds": 600,
        "skills": ["translation", "translation"],
        "max_retries": 2,
        "goal_mode": True,
        "goal_max_turns": 5,
        "initial_status": "blocked",
        "session_id": "review-cycle:1",
        "board": None,
    }
    task_id = kb.create_olympus_task(
        conn,
        olympus_context=context,
        olympus_auth=_auth(conn, context, operation_id="create:exact:first"),
        **base,
    )
    assert kb.create_olympus_task(
        conn,
        olympus_context=copy.deepcopy(context),
        olympus_auth=_auth(conn, context, operation_id="create:exact:replay"),
        **copy.deepcopy(base),
    ) == task_id
    receipt = conn.execute(
        "SELECT * FROM kanban_olympus_create_receipts WHERE idempotency_key=?",
        (base["idempotency_key"],),
    ).fetchone()
    assert receipt is not None and receipt["task_id"] == task_id
    with pytest.raises(sqlite3.IntegrityError):
        conn.execute(
            "UPDATE kanban_olympus_create_receipts SET payload='{}' "
            "WHERE idempotency_key=?",
            (base["idempotency_key"],),
        )
    with pytest.raises(sqlite3.IntegrityError):
        conn.execute(
            "DELETE FROM kanban_olympus_create_receipts WHERE idempotency_key=?",
            (base["idempotency_key"],),
        )

    mutations = {
        "title": "different remediation",
        "body": "different body",
        "assignee": "foreign-agent",
        "created_by": "foreign-reviewer",
        "workspace_kind": "dir",
        "workspace_path": "/tmp/foreign",
        "branch_name": "foreign-branch",
        "tenant": "foreign",
        "priority": 8,
        "parents": [parent_b],
        "triage": True,
        "max_runtime_seconds": 601,
        "skills": ["translation", "summarization"],
        "max_retries": 3,
        "goal_mode": False,
        "goal_max_turns": 6,
        "initial_status": "running",
        "session_id": "review-cycle:2",
        "board": "foreign-board",
    }
    for field, value in mutations.items():
        changed = copy.deepcopy(base)
        changed[field] = value
        with pytest.raises(kb.OlympusContextError) as caught:
            kb.create_olympus_task(
                conn,
                olympus_context=copy.deepcopy(context),
                olympus_auth=_auth(
                    conn, context, operation_id=f"create:collision:{field}"
                ),
                **changed,
            )
        assert caught.value.reason == "olympus_idempotency_payload_conflict"

    changed_context = copy.deepcopy(context)
    changed_context["authority"]["revision"] += 1
    with pytest.raises(kb.OlympusContextError) as caught:
        kb.create_olympus_task(
            conn,
            olympus_context=changed_context,
            olympus_auth=_auth(conn, changed_context),
            **copy.deepcopy(base),
        )
    assert caught.value.reason == "olympus_idempotency_payload_conflict"
    assert conn.execute(
        "SELECT COUNT(*) FROM tasks WHERE idempotency_key=?",
        (base["idempotency_key"],),
    ).fetchone()[0] == 1

    assert kb.archive_task(
        conn,
        task_id,
        olympus_auth=_auth(conn, context, operation_id="create:archive"),
    )
    assert kb.create_olympus_task(
        conn,
        olympus_context=copy.deepcopy(context),
        olympus_auth=_auth(conn, context, operation_id="create:archived-replay"),
        **copy.deepcopy(base),
    ) == task_id
    assert kb.delete_archived_task(
        conn,
        task_id,
        olympus_auth=_auth(conn, context, operation_id="create:delete"),
    )
    with pytest.raises(kb.OlympusContextError) as caught:
        kb.create_olympus_task(
            conn,
            olympus_context=copy.deepcopy(context),
            olympus_auth=_auth(conn, context, operation_id="create:deleted-reuse"),
            **copy.deepcopy(base),
        )
    assert caught.value.reason == "olympus_idempotency_receipt_orphaned"


def test_release_receipt_is_atomic_replayable_and_survives_dispatcher_claim(conn):
    context = _context()
    task_id = _create(
        conn,
        context,
        initial_status="blocked",
        operation_id="release:create",
    )
    original_revision = kb.get_task(conn, task_id).record_revision
    release_auth = _auth(conn, context, operation_id="release:stable")
    receipt = kb.release_olympus_task(
        conn,
        task_id,
        subject_revision=original_revision,
        olympus_auth=release_auth,
    )
    assert receipt["previous_status"] == "blocked"
    assert receipt["status"] == "ready"
    assert receipt["record_revision"] == original_revision + 1
    operation_id = kb.olympus_release_operation_id(
        task_id, original_revision, "release:stable"
    )
    db_path = conn.execute("PRAGMA database_list").fetchone()[2]
    reopened = kb.connect(Path(db_path))
    try:
        assert receipt == kb.get_olympus_release_receipt(
            reopened,
            task_id=task_id,
            subject_revision=original_revision,
            operation_id=operation_id,
        )

        with pytest.raises(kb.OlympusContextError) as caught:
            kb.release_olympus_task(
                reopened,
                task_id,
                subject_revision=original_revision,
                olympus_auth=_auth(
                    reopened, context, verifier=None, operation_id="release:stable"
                ),
            )
        assert caught.value.reason == "olympus_authority_verification_unavailable"

        def stale_verification(request):
            result = _allow(request)
            result["current"] = False
            return result

        with pytest.raises(kb.OlympusContextError) as caught:
            kb.release_olympus_task(
                reopened,
                task_id,
                subject_revision=original_revision,
                olympus_auth=_auth(
                    reopened,
                    context,
                    verifier=stale_verification,
                    operation_id="release:stable",
                ),
            )
        assert caught.value.reason == "olympus_authority_verification_denied"

        def revoked_verification(request):
            result = _allow(request)
            result["decision"] = "DENY"
            return result

        with pytest.raises(kb.OlympusContextError) as caught:
            kb.release_olympus_task(
                reopened,
                task_id,
                subject_revision=original_revision,
                olympus_auth=_auth(
                    reopened,
                    context,
                    verifier=revoked_verification,
                    operation_id="release:stable",
                ),
            )
        assert caught.value.reason == "olympus_authority_verification_denied"

        assert kb.release_olympus_task(
            reopened,
            task_id,
            subject_revision=original_revision,
            olympus_auth=_auth(
                reopened, context, operation_id="release:stable"
            ),
        ) == receipt

        claimed = kb.claim_task(
            reopened,
            task_id,
            claimer="dispatcher:after-release",
            olympus_auth=_auth(
                reopened, context, operation_id="release:claim"
            ),
        )
        assert claimed is not None and claimed.status == "running"
        event_count = len(kb.list_events(reopened, task_id))
        with pytest.raises(kb.OlympusContextError) as caught:
            kb.release_olympus_task(
                reopened,
                task_id,
                subject_revision=original_revision,
                olympus_auth=_auth(
                    reopened, context, operation_id="release:stable"
                ),
            )
        assert caught.value.reason == "olympus_release_replay_state_changed"
        assert receipt == kb.get_olympus_release_receipt(
            reopened,
            task_id=task_id,
            subject_revision=original_revision,
            operation_id=operation_id,
        )
        assert kb.get_task(reopened, task_id).status == "running"
        assert len(kb.list_events(reopened, task_id)) == event_count
        assert reopened.execute(
            "SELECT COUNT(*) FROM kanban_olympus_release_receipts WHERE task_id=?",
            (task_id,),
        ).fetchone()[0] == 1

        with pytest.raises(kb.OlympusContextError) as caught:
            kb.release_olympus_task(
                reopened,
                task_id,
                subject_revision=original_revision,
                olympus_auth=_auth(
                    reopened, context, operation_id="release:foreign"
                ),
            )
        assert caught.value.reason == "olympus_release_receipt_conflict"

        with pytest.raises(sqlite3.IntegrityError):
            reopened.execute(
                "UPDATE kanban_olympus_release_receipts SET receipt='{}' "
                "WHERE operation_id=?",
                (operation_id,),
            )
        with pytest.raises(sqlite3.IntegrityError):
            reopened.execute(
                "DELETE FROM kanban_olympus_release_receipts WHERE operation_id=?",
                (operation_id,),
            )
    finally:
        reopened.close()


def test_release_receipt_archived_deleted_and_corrupt_recovery_paths(conn):
    context = _context()
    task_id = _create(
        conn,
        context,
        initial_status="blocked",
        operation_id="release:lifecycle:create",
    )
    revision = kb.get_task(conn, task_id).record_revision
    receipt = kb.release_olympus_task(
        conn,
        task_id,
        subject_revision=revision,
        olympus_auth=_auth(
            conn, context, operation_id="release:lifecycle"
        ),
    )
    operation_id = kb.olympus_release_operation_id(
        task_id, revision, "release:lifecycle"
    )
    assert kb.archive_task(
        conn,
        task_id,
        olympus_auth=_auth(conn, context, operation_id="release:archive"),
    )
    with pytest.raises(kb.OlympusContextError) as caught:
        kb.release_olympus_task(
            conn,
            task_id,
            subject_revision=revision,
            olympus_auth=_auth(
                conn, context, operation_id="release:lifecycle"
            ),
        )
    assert caught.value.reason == "olympus_release_replay_state_changed"
    assert kb.get_olympus_release_receipt(
        conn,
        task_id=task_id,
        subject_revision=revision,
        operation_id=operation_id,
    ) == receipt
    assert kb.delete_archived_task(
        conn,
        task_id,
        olympus_auth=_auth(conn, context, operation_id="release:delete"),
    )
    with pytest.raises(kb.OlympusContextError) as caught:
        kb.release_olympus_task(
            conn,
            task_id,
            subject_revision=revision,
            olympus_auth=_auth(
                conn, context, operation_id="release:lifecycle"
            ),
        )
    assert caught.value.reason == "olympus_release_replay_orphaned"
    assert kb.get_olympus_release_receipt(
        conn,
        task_id=task_id,
        subject_revision=revision,
        operation_id=operation_id,
    ) == receipt

    corrupt_task = _create(
        conn,
        context,
        initial_status="blocked",
        operation_id="release:corrupt:create",
    )
    corrupt_revision = kb.get_task(conn, corrupt_task).record_revision
    kb.release_olympus_task(
        conn,
        corrupt_task,
        subject_revision=corrupt_revision,
        olympus_auth=_auth(conn, context, operation_id="release:corrupt"),
    )
    corrupt_operation = kb.olympus_release_operation_id(
        corrupt_task, corrupt_revision, "release:corrupt"
    )
    db_path = conn.execute("PRAGMA database_list").fetchone()[2]
    raw = sqlite3.connect(db_path)
    try:
        raw.execute("DROP TRIGGER olympus_release_receipt_update_guard")
        raw.execute(
            "UPDATE kanban_olympus_release_receipts SET receipt='{}' "
            "WHERE operation_id=?",
            (corrupt_operation,),
        )
        raw.commit()
    finally:
        raw.close()
    kb._install_olympus_write_guard(conn)
    with pytest.raises(kb.OlympusContextError) as caught:
        kb.get_olympus_release_receipt(
            conn,
            task_id=corrupt_task,
            subject_revision=corrupt_revision,
            operation_id=corrupt_operation,
        )
    assert caught.value.reason == "olympus_release_receipt_invalid"


def test_release_receipt_insert_is_bound_to_verified_identity_fields(conn):
    context = _context()
    task_id = _create(
        conn,
        context,
        initial_status="blocked",
        operation_id="release:binding:create",
    )
    revision = kb.get_task(conn, task_id).record_revision
    with kb.write_txn(conn):
        authorization, owns = kb._authorize_task_mutation(
            conn,
            task_id,
            action="release_blocked_task",
            capability=kb.OLYMPUS_CAPABILITY_RELEASE,
            auth=_auth(conn, context, operation_id="release:binding"),
        )
        try:
            created_at = int(time.time())
            request = authorization["request"]
            verified = authorization["verification"]
            canonical_context = authorization["context"]
            expected = {
                "schema_version": "olympus-task-release-receipt/1",
                "operation_id": request["operation_id"],
                "task_id": task_id,
                "previous_status": "blocked",
                "status": "ready",
                "previous_revision": revision,
                "record_revision": revision + 1,
                "verification_id": verified["verification_id"],
                "request_id": request["request_id"],
                "actor": request["actor"],
                "principal": request["principal"],
                "authority_id": canonical_context["authority"]["authority_id"],
                "authority_revision": canonical_context["authority"]["revision"],
                "authority_source": canonical_context["authority"]["source"],
                "lease_id": canonical_context["lease"]["lease_id"],
                "lease_revision": canonical_context["lease"]["revision"],
                "lease_source": canonical_context["lease"]["source"],
                "created_at": created_at,
            }
            encoded, digest = kb._canonical_json_record(expected)
            kb._bind_issued_permit_write(
                conn,
                task_id,
                {
                    "schema_version": kb.RELEASE_RECEIPT_WRITE_SCHEMA,
                    "operation_id": expected["operation_id"],
                    "task_id": task_id,
                    "subject_revision": revision,
                    "record_revision": revision + 1,
                    "verification_id": expected["verification_id"],
                    "request_id": expected["request_id"],
                    "receipt": encoded,
                    "receipt_sha256": digest,
                    "created_at": created_at,
                },
            )
            for field, value in (
                ("actor", "foreign-actor"),
                ("principal", {**expected["principal"], "principal_id": "forged"}),
                ("authority_id", "foreign-authority"),
                ("lease_id", "foreign-lease"),
            ):
                forged = copy.deepcopy(expected)
                forged[field] = value
                forged_encoded, forged_digest = kb._canonical_json_record(forged)
                with pytest.raises(sqlite3.IntegrityError):
                    conn.execute(
                        "INSERT INTO kanban_olympus_release_receipts "
                        "(operation_id,task_id,subject_revision,record_revision,"
                        "verification_id,request_id,receipt,receipt_sha256,created_at) "
                        "VALUES (?,?,?,?,?,?,?,?,?)",
                        (
                            expected["operation_id"], task_id, revision,
                            revision + 1, expected["verification_id"],
                            expected["request_id"], forged_encoded,
                            forged_digest, created_at,
                        ),
                    )
        finally:
            kb._release_task_mutation_permit(conn, task_id, owns)


def test_attachment_lifecycle_uses_no_follow_descriptors(conn, tmp_path, monkeypatch):
    root = tmp_path / "attachments"
    monkeypatch.setenv("HERMES_KANBAN_ATTACHMENTS_ROOT", str(root))
    task_id = kb.create_task(conn, title="ordinary", assignee="coding")
    opened, path = kb.open_attachment_for_write(task_id, "proof.txt")
    with opened:
        opened.write(b"proof")
    attachment_id = kb.add_attachment(
        conn, task_id, filename="proof.txt", stored_path=str(path), size=5,
    )
    with kb.open_attachment_for_read(task_id, str(path)) as handle:
        assert handle.read() == b"proof"
    assert kb.delete_attachment(conn, attachment_id) is not None
    assert not path.exists()
    with pytest.raises(ValueError):
        kb.validated_attachment_path(task_id, root / task_id / ".." / "escape")
    target = tmp_path / "outside"
    target.mkdir()
    symlink_task = "symlink-task"
    root.mkdir(exist_ok=True)
    (root / symlink_task).symlink_to(target, target_is_directory=True)
    with pytest.raises(OSError):
        kb.open_attachment_for_write(symlink_task, "escape.txt")


def test_board_removal_and_all_gc_surfaces_exclude_governed_state(tmp_path, monkeypatch):
    home = tmp_path / ".hermes"
    home.mkdir()
    monkeypatch.setenv("HERMES_HOME", str(home))
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    kb.create_board("governed")
    with kb.connect(board="governed") as board_conn:
        context = _context()
        governed_id = _create(board_conn, context)
        ordinary_id = kb.create_task(board_conn, title="ordinary", assignee="coding")
        assert kb.complete_task(board_conn, ordinary_id, result="done")
        assert kb.gc_events(board_conn, older_than_seconds=-1) > 0
        assert kb.list_events(board_conn, governed_id)
        assert kb.list_events(board_conn, ordinary_id) == []
    logs = kb.worker_logs_dir(board="governed")
    logs.mkdir(parents=True, exist_ok=True)
    governed_log = logs / f"{governed_id}.log"
    ordinary_log = logs / f"{ordinary_id}.log"
    governed_log.write_text("keep")
    ordinary_log.write_text("remove")
    old = time.time() - 10_000
    os.utime(governed_log, (old, old))
    os.utime(ordinary_log, (old, old))
    assert kb.gc_worker_logs(older_than_seconds=1, board="governed") == 1
    assert governed_log.exists() and not ordinary_log.exists()
    with pytest.raises(kb.OlympusContextError):
        kb.remove_board("governed", archive=False)


def test_additive_migration_preserves_legacy_rows_reinstalls_guards_and_rolls_back(
    tmp_path, monkeypatch,
):
    home = tmp_path / ".hermes"
    home.mkdir()
    monkeypatch.setenv("HERMES_HOME", str(home))
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    db_path = home / "legacy.db"
    raw = sqlite3.connect(db_path)
    raw.executescript(
        """
        CREATE TABLE tasks (
            id TEXT PRIMARY KEY, title TEXT NOT NULL, body TEXT, assignee TEXT,
            status TEXT NOT NULL, priority INTEGER DEFAULT 0, created_by TEXT,
            created_at INTEGER NOT NULL, started_at INTEGER, completed_at INTEGER,
            workspace_kind TEXT NOT NULL DEFAULT 'scratch', workspace_path TEXT,
            claim_lock TEXT, claim_expires INTEGER
        );
        CREATE TABLE task_events (
            id TEXT PRIMARY KEY, task_id TEXT NOT NULL, kind TEXT NOT NULL,
            payload TEXT, created_at INTEGER NOT NULL
        );
        CREATE TABLE task_runs (
            id TEXT PRIMARY KEY, task_id TEXT NOT NULL, profile TEXT, step_key TEXT,
            status TEXT NOT NULL, claim_lock TEXT, claim_expires INTEGER,
            worker_pid INTEGER, max_runtime_seconds INTEGER,
            last_heartbeat_at INTEGER, started_at INTEGER NOT NULL,
            ended_at INTEGER, outcome TEXT, summary TEXT, metadata TEXT, error TEXT
        );
        INSERT INTO tasks (id,title,status,created_at)
        VALUES ('legacy-1','preserve me','ready',1);
        """
    )
    raw.commit()
    raw.close()
    backup = tmp_path / "legacy.pre-olympus.bak"
    shutil.copy2(db_path, backup)
    backup_digest = hashlib.sha256(backup.read_bytes()).hexdigest()
    kb._INITIALIZED_PATHS.discard(str(db_path.resolve()))
    with kb.connect(db_path) as migrated:
        assert kb.get_task(migrated, "legacy-1").olympus_context is None
        assert migrated.execute(
            "SELECT 1 FROM sqlite_master WHERE type='trigger' "
            "AND name='olympus_tasks_update_guard'"
        ).fetchone()
        assert kb.claim_task(migrated, "legacy-1") is not None
    assert hashlib.sha256(backup.read_bytes()).hexdigest() == backup_digest
    for suffix in ("-wal", "-shm"):
        Path(str(db_path) + suffix).unlink(missing_ok=True)
    shutil.copy2(backup, db_path)
    restored = sqlite3.connect(db_path)
    try:
        assert "olympus_context" not in {
            row[1] for row in restored.execute("PRAGMA table_info(tasks)")
        }
        assert restored.execute(
            "SELECT title FROM tasks WHERE id='legacy-1'"
        ).fetchone()[0] == "preserve me"
    finally:
        restored.close()


def _logical_db_manifest(conn: sqlite3.Connection) -> tuple[str, dict]:
    """Return a physical-id-sensitive manifest of every application table."""
    tables = [
        row[0]
        for row in conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' "
            "AND name NOT LIKE 'sqlite_%' ORDER BY name"
        )
    ]
    manifest = {}
    for table in tables:
        rows = [dict(row) for row in conn.execute(f'SELECT * FROM "{table}"')]
        manifest[table] = sorted(
            rows,
            key=lambda row: json.dumps(
                row, sort_keys=True, separators=(",", ":"), default=str,
            ),
        )
    encoded = json.dumps(
        manifest, sort_keys=True, separators=(",", ":"), default=str,
    ).encode()
    return hashlib.sha256(encoded).hexdigest(), manifest


def _rewrite_linked_state_as_legacy_text_ids(path: Path) -> None:
    """Downgrade linked run/event identities without dropping any data."""
    raw = sqlite3.connect(path)
    raw.row_factory = sqlite3.Row
    try:
        raw.execute("PRAGMA foreign_keys=OFF")
        for row in raw.execute(
            "SELECT name FROM sqlite_master WHERE type='trigger'"
        ).fetchall():
            raw.execute(f'DROP TRIGGER "{row[0]}"')
        # Exercise both optional effect references in one production-like
        # synthetic row. Notification effects naturally carry event_id; bind
        # the active run as well so the migration must remap both identities.
        raw.execute(
            "UPDATE kanban_effect_journal SET run_id=(SELECT id FROM task_runs "
            "ORDER BY id LIMIT 1) WHERE event_id IS NOT NULL AND run_id IS NULL"
        )

        def rebuild_with_text_id(table: str, prefix: str) -> dict[int, str]:
            schema = raw.execute(
                "SELECT sql FROM sqlite_master WHERE type='table' AND name=?",
                (table,),
            ).fetchone()[0]
            rows = raw.execute(f'SELECT * FROM "{table}" ORDER BY rowid').fetchall()
            raw.execute(f'ALTER TABLE "{table}" RENAME TO "{table}_current"')
            raw.execute(
                schema.replace(
                    "INTEGER PRIMARY KEY AUTOINCREMENT", "TEXT PRIMARY KEY", 1,
                )
            )
            columns = [column[1] for column in raw.execute(f'PRAGMA table_info("{table}")')]
            placeholders = ",".join("?" for _ in columns)
            mapping = {}
            for row in rows:
                values = [row[column] for column in columns]
                old_id = int(row["id"])
                mapping[old_id] = f"{prefix}:{old_id}"
                values[columns.index("id")] = mapping[old_id]
                raw.execute(
                    f'INSERT INTO "{table}" ({",".join(columns)}) '
                    f'VALUES ({placeholders})',
                    values,
                )
            raw.execute(f'DROP TABLE "{table}_current"')
            return mapping

        run_map = rebuild_with_text_id("task_runs", "legacy-run")
        for old_id, legacy_id in run_map.items():
            raw.execute(
                "UPDATE tasks SET current_run_id=? WHERE current_run_id=?",
                (legacy_id, old_id),
            )
            raw.execute(
                "UPDATE task_events SET run_id=? WHERE run_id=?", (legacy_id, old_id),
            )
            raw.execute(
                "UPDATE kanban_effect_journal SET run_id=? WHERE run_id=?",
                (legacy_id, old_id),
            )

        event_map = rebuild_with_text_id("task_events", "legacy-event")
        for old_id, legacy_id in event_map.items():
            raw.execute(
                "UPDATE kanban_effect_journal SET event_id=? WHERE event_id=?",
                (legacy_id, old_id),
            )
            raw.execute(
                "UPDATE kanban_notify_subs SET last_event_id=? WHERE last_event_id=?",
                (legacy_id, old_id),
            )

        notify_schema = raw.execute(
            "SELECT sql FROM sqlite_master WHERE type='table' "
            "AND name='kanban_notify_subs'"
        ).fetchone()[0]
        notify_rows = raw.execute("SELECT * FROM kanban_notify_subs").fetchall()
        raw.execute(
            "ALTER TABLE kanban_notify_subs RENAME TO kanban_notify_subs_current"
        )
        raw.execute(notify_schema.replace("last_event_id INTEGER", "last_event_id TEXT"))
        columns = [
            column[1] for column in raw.execute("PRAGMA table_info(kanban_notify_subs)")
        ]
        placeholders = ",".join("?" for _ in columns)
        for row in notify_rows:
            raw.execute(
                f'INSERT INTO kanban_notify_subs ({",".join(columns)}) '
                f'VALUES ({placeholders})',
                [row[column] for column in columns],
            )
        raw.execute("DROP TABLE kanban_notify_subs_current")
        raw.commit()
        assert raw.execute("PRAGMA integrity_check").fetchone()[0] == "ok"
    finally:
        raw.close()


def test_linked_production_like_migration_is_atomic_restartable_and_restorable(
    tmp_path, monkeypatch,
):
    """Run/event identities and every durable dependent survive exact rebuilds."""
    home = tmp_path / ".hermes"
    home.mkdir()
    monkeypatch.setenv("HERMES_HOME", str(home))
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    db_path = home / "linked-legacy.db"
    context = _context()
    kb._INITIALIZED_PATHS.discard(str(db_path.resolve()))
    with kb.connect(db_path) as setup:
        task_id = kb.create_olympus_task(
            setup,
            title="linked production-like state",
            assignee=context["agent_id"],
            initial_status="blocked",
            idempotency_key="migration:linked:1",
            olympus_context=context,
            olympus_auth=_auth(setup, context, operation_id="migration:create"),
        )
        revision = kb.get_task(setup, task_id).record_revision
        release = kb.release_olympus_task(
            setup,
            task_id,
            subject_revision=revision,
            olympus_auth=_auth(setup, context, operation_id="migration:release"),
        )
        run = kb.reserve_worker_run(
            setup,
            task_id,
            claimer=kb._claimer_id(),
            olympus_auth=_auth(setup, context, operation_id="migration:run"),
        )
        assert run is not None
        assert kb.mark_worker_workspace_ready(
            setup,
            task_id=task_id,
            run_id=run.id,
            launch_token=run.launch_token,
            workspace_snapshot={
                "board_id": kb._connection_board_identity(setup),
                "path": "/tmp/migration-worker",
            },
            olympus_auth=_auth(
                setup, context, operation_id="migration:workspace"
            ),
        )
        assert kb.mark_worker_starting(
            setup,
            task_id=task_id,
            run_id=run.id,
            launch_token=run.launch_token,
            olympus_auth=_auth(
                setup, context, operation_id="migration:starting"
            ),
        )
        worker_identity = kb.ProcessIdentity(
            "host:migration-worker", "boot:migration-worker", 5555,
            "birth:migration-worker",
        )
        monkeypatch.setattr(
            kb,
            "read_process_identity",
            lambda pid: worker_identity if int(pid) == worker_identity.pid else None,
        )
        assert kb.register_worker_process(
            setup,
            task_id=task_id,
            run_id=run.id,
            launch_token=run.launch_token,
            process_identity=worker_identity,
            dispatcher_instance_id="test-dispatcher",
            olympus_auth=_auth(
                setup, context, operation_id="migration:register"
            ),
        )
        run = kb.get_run(setup, run.id)
        runtime = kb.olympus_worker_runtime_snapshot(
            setup,
            worker_task_id=task_id,
            run_id=run.id,
            claim_lock=run.claim_lock,
        )
        worker_session = kb.OlympusWorkerAuthSession(
            verifier=_allow,
            board_id=runtime["board_id"],
            task_id=task_id,
            run_id=run.id,
            run_subject_revision=runtime["run_subject_revision"],
            claim_lock=run.claim_lock,
            assignee=context["agent_id"],
            process_identity=worker_identity,
            dispatcher_instance_id="test-dispatcher",
        )
        parent_id = kb.create_task(
            setup, title="migration parent", assignee="coding",
        )
        kb.link_tasks(
            setup,
            parent_id,
            task_id,
            olympus_auth=_auth(
                setup, context, operation_id="migration:link"
            ),
        )
        comment_id = kb.add_comment(
            setup,
            task_id,
            author="migration-reviewer",
            body="preserve linked comment",
            olympus_auth=worker_session.issue(
                setup, "comment", kb.OLYMPUS_CAPABILITY_COMMENT,
            ),
        )
        attachment_file, attachment_path = kb.open_attachment_for_write(
            task_id, "migration-proof.txt",
        )
        with attachment_file:
            attachment_file.write(b"migration-proof")
        attachment_id = kb.add_attachment(
            setup,
            task_id,
            filename="migration-proof.txt",
            stored_path=str(attachment_path),
            content_type="text/plain",
            size=len(b"migration-proof"),
            uploaded_by="migration-reviewer",
            olympus_auth=_auth(
                setup, context, operation_id="migration:attachment"
            ),
        )
        assert kb.add_notify_sub(
            setup,
            task_id=task_id,
            platform="telegram",
            chat_id="migration-chat",
            user_id="migration-user",
            notifier_profile="default",
            olympus_auth=_auth(setup, context, operation_id="migration:subscribe"),
        )
        event_id = kb.list_events(setup, task_id)[-1].id
        gateway_identity = kb.ProcessIdentity(
            "host:migration", "boot:migration", 5656, "birth:migration",
        )
        monkeypatch.setattr(
            kb,
            "read_process_identity",
            lambda pid: gateway_identity if int(pid) == gateway_identity.pid else None,
        )
        kb.advance_notify_cursor(
            setup,
            task_id=task_id,
            platform="telegram",
            chat_id="migration-chat",
            new_cursor=event_id,
            olympus_auth=kb.olympus_notifier_auth(
                setup,
                verifier=_allow,
                task_id=task_id,
                platform="telegram",
                chat_id="migration-chat",
                thread_id="",
                source_event_id=event_id,
                effect_id="migration:cursor",
                effect_state="unreserved",
                gateway_process_identity=gateway_identity,
                action="advance_notification_cursor",
            ),
        )
        effect_auth = kb.olympus_notifier_auth(
            setup,
            verifier=_allow,
            task_id=task_id,
            platform="telegram",
            chat_id="migration-chat",
            thread_id="",
            source_event_id=event_id,
            effect_id="migration:effect",
            effect_state="unreserved",
            gateway_process_identity=gateway_identity,
            action="reserve_notification_effect",
        )
        effect_id = kb.reserve_notification_effect(
            setup,
            task_id=task_id,
            effect_kind="notify_text",
            operation_id="migration:effect",
            event_id=event_id,
            destination_key="telegram:migration-chat:",
            part="text",
            payload={"message": "preserve"},
            olympus_auth=effect_auth,
        )
        assert effect_id > 0

    _rewrite_linked_state_as_legacy_text_ids(db_path)
    legacy_backup = tmp_path / "linked-legacy.sqlite3"
    source = sqlite3.connect(db_path)
    backup = sqlite3.connect(legacy_backup)
    try:
        source.backup(backup)
        assert backup.execute("PRAGMA integrity_check").fetchone()[0] == "ok"
    finally:
        backup.close()
        source.close()
    legacy_checksum = hashlib.sha256(legacy_backup.read_bytes()).hexdigest()

    def interrupt(table: str) -> None:
        if table == "task_runs":
            raise RuntimeError("injected migration interruption")

    kb._INITIALIZED_PATHS.discard(str(db_path.resolve()))
    kb._OLYMPUS_REBUILD_FAILPOINT = interrupt
    try:
        with pytest.raises(RuntimeError, match="injected migration interruption"):
            kb.connect(db_path)
    finally:
        kb._OLYMPUS_REBUILD_FAILPOINT = None
    raw = sqlite3.connect(db_path)
    try:
        assert raw.execute("PRAGMA integrity_check").fetchone()[0] == "ok"
        assert {
            row[1]: row[2].upper() for row in raw.execute("PRAGMA table_info(task_runs)")
        }["id"] == "TEXT"
        assert raw.execute(
            "SELECT parent_id,child_id FROM task_links "
            "WHERE parent_id=? AND child_id=?",
            (parent_id, task_id),
        ).fetchone() == (parent_id, task_id)
        assert raw.execute(
            "SELECT task_id,author,body FROM task_comments WHERE id=?",
            (comment_id,),
        ).fetchone() == (
            task_id, "migration-reviewer", "preserve linked comment",
        )
        assert raw.execute(
            "SELECT task_id,filename,stored_path,size FROM task_attachments WHERE id=?",
            (attachment_id,),
        ).fetchone() == (
            task_id, "migration-proof.txt", str(attachment_path),
            len(b"migration-proof"),
        )
    finally:
        raw.close()

    kb._INITIALIZED_PATHS.discard(str(db_path.resolve()))
    with kb.connect(db_path) as migrated:
        digest, manifest = _logical_db_manifest(migrated)
        task_row = migrated.execute(
            "SELECT current_run_id FROM tasks WHERE id=?", (task_id,),
        ).fetchone()
        run_id = int(task_row["current_run_id"])
        assert migrated.execute(
            "SELECT 1 FROM task_runs WHERE id=? AND task_id=?", (run_id, task_id),
        ).fetchone()
        event_row = migrated.execute(
            "SELECT event_id,run_id FROM kanban_effect_journal WHERE id=?", (effect_id,),
        ).fetchone()
        assert event_row["run_id"] == run_id
        assert migrated.execute(
            "SELECT 1 FROM task_events WHERE id=? AND task_id=?",
            (event_row["event_id"], task_id),
        ).fetchone()
        assert migrated.execute(
            "SELECT last_event_id FROM kanban_notify_subs WHERE task_id=?",
            (task_id,),
        ).fetchone()[0] == event_row["event_id"]
        assert tuple(migrated.execute(
            "SELECT parent_id,child_id FROM task_links "
            "WHERE parent_id=? AND child_id=?",
            (parent_id, task_id),
        ).fetchone()) == (parent_id, task_id)
        assert tuple(migrated.execute(
            "SELECT task_id,author,body FROM task_comments WHERE id=?",
            (comment_id,),
        ).fetchone()) == (
            task_id, "migration-reviewer", "preserve linked comment",
        )
        assert tuple(migrated.execute(
            "SELECT task_id,filename,stored_path,size FROM task_attachments WHERE id=?",
            (attachment_id,),
        ).fetchone()) == (
            task_id, "migration-proof.txt", str(attachment_path),
            len(b"migration-proof"),
        )
        assert release == kb.get_olympus_release_receipt(
            migrated,
            task_id=task_id,
            subject_revision=revision,
            operation_id=kb.olympus_release_operation_id(
                task_id, revision, "migration:release"
            ),
        )
        assert migrated.execute(
            "SELECT task_id FROM kanban_olympus_create_receipts "
            "WHERE idempotency_key='migration:linked:1'"
        ).fetchone()[0] == task_id
        assert migrated.execute("PRAGMA integrity_check").fetchone()[0] == "ok"

    kb._INITIALIZED_PATHS.discard(str(db_path.resolve()))
    with kb.connect(db_path) as reopened:
        assert _logical_db_manifest(reopened) == (digest, manifest)

    restored_path = home / "linked-restored.db"
    shutil.copy2(legacy_backup, restored_path)
    assert hashlib.sha256(legacy_backup.read_bytes()).hexdigest() == legacy_checksum
    kb._INITIALIZED_PATHS.discard(str(restored_path.resolve()))
    with kb.connect(restored_path) as remigrated:
        assert remigrated.execute("PRAGMA integrity_check").fetchone()[0] == "ok"
        assert _logical_db_manifest(remigrated) == (digest, manifest)


def test_three_then_six_concurrent_claimers_admit_exactly_one(tmp_path, monkeypatch):
    home = tmp_path / ".hermes"
    home.mkdir()
    monkeypatch.setenv("HERMES_HOME", str(home))
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    db_path = home / "concurrency.db"
    kb._INITIALIZED_PATHS.discard(str(db_path.resolve()))
    context = _context()

    def race(contenders: int, task_id: str) -> list[bool]:
        barrier = threading.Barrier(contenders)
        results = [False] * contenders

        def worker(index: int):
            local = kb.connect(db_path)
            try:
                barrier.wait()
                results[index] = kb.claim_task(
                    local, task_id, claimer=f"race:{contenders}:{index}",
                    olympus_auth=_auth(
                        local, context, operation_id=f"race:{contenders}:{index}"
                    ),
                ) is not None
            finally:
                local.close()

        threads = [threading.Thread(target=worker, args=(i,)) for i in range(contenders)]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join()
        return results

    setup = kb.connect(db_path)
    try:
        first = _create(setup, context, operation_id="create:three")
        second = _create(setup, context, operation_id="create:six")
    finally:
        setup.close()
    assert sum(race(3, first)) == 1
    assert sum(race(6, second)) == 1


def test_three_then_six_governed_create_submissions_are_durable_and_idempotent(
    tmp_path, monkeypatch,
):
    home = tmp_path / ".hermes"
    home.mkdir()
    monkeypatch.setenv("HERMES_HOME", str(home))
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    db_path = home / "create-concurrency.db"
    kb._INITIALIZED_PATHS.discard(str(db_path.resolve()))
    with kb.connect(db_path):
        pass
    context = _context()

    def submit(contenders: int, key: str) -> str:
        barrier = threading.Barrier(contenders)
        results: list[str | None] = [None] * contenders
        errors: list[BaseException | None] = [None] * contenders

        def worker(index: int) -> None:
            local = kb.connect(db_path)
            try:
                barrier.wait(timeout=10)
                results[index] = kb.create_olympus_task(
                    local,
                    title=f"durable governed submission {key}",
                    body="exact immutable create payload",
                    assignee=context["agent_id"],
                    initial_status="blocked",
                    idempotency_key=key,
                    max_runtime_seconds=600,
                    skills=["translation"],
                    olympus_context=copy.deepcopy(context),
                    olympus_auth=_auth(
                        local,
                        context,
                        operation_id=f"create-race:{contenders}:{index}",
                    ),
                )
            except BaseException as exc:  # surfaced after every thread joins
                errors[index] = exc
            finally:
                local.close()

        threads = [
            threading.Thread(target=worker, args=(index,))
            for index in range(contenders)
        ]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join(timeout=20)
        assert not any(thread.is_alive() for thread in threads)
        assert errors == [None] * contenders
        assert None not in results and len(set(results)) == 1
        return str(results[0])

    expected = {
        "create-race:three": submit(3, "create-race:three"),
        "create-race:six": submit(6, "create-race:six"),
    }
    kb._INITIALIZED_PATHS.discard(str(db_path.resolve()))
    with kb.connect(db_path) as reopened:
        for key, task_id in expected.items():
            assert reopened.execute(
                "SELECT COUNT(*) FROM tasks WHERE idempotency_key=? AND id=?",
                (key, task_id),
            ).fetchone()[0] == 1
            receipt = reopened.execute(
                "SELECT task_id,payload,payload_sha256 "
                "FROM kanban_olympus_create_receipts WHERE idempotency_key=?",
                (key,),
            ).fetchone()
            assert receipt is not None and receipt["task_id"] == task_id
            assert hashlib.sha256(receipt["payload"].encode()).hexdigest() \
                == receipt["payload_sha256"]
            assert reopened.execute(
                "SELECT COUNT(*) FROM task_events WHERE task_id=? AND kind='created'",
                (task_id,),
            ).fetchone()[0] == 1
            assert kb.get_task(reopened, task_id).status == "blocked"


def test_native_process_identity_is_strong_on_darwin():
    identity = kb.read_process_identity(os.getpid())
    assert identity is not None and identity.pid == os.getpid()
    if os.sys.platform == "darwin":
        assert identity.start_token.startswith("darwin:")
        assert len(identity.start_token.split(":")) == 3


def test_ordinary_kanban_compatibility_is_unchanged(conn):
    task_id = kb.create_task(conn, title="ordinary", assignee="coding")
    claimed = kb.claim_task(conn, task_id, claimer="legacy:worker")
    assert claimed is not None and claimed.olympus_context is None
    assert kb.complete_task(conn, task_id, result="ok")
