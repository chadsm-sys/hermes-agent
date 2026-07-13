"""Olympus authority binding contracts for the existing Hermes Kanban DB."""

from __future__ import annotations

import copy
import json
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
    *,
    now: int | None = None,
    lease_id: str = "lease-1",
    agent_id: str = "coding",
    authority_revision: int = 7,
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
            "capabilities": [
                kb.OLYMPUS_CAPABILITY_CREATE,
                kb.OLYMPUS_CAPABILITY_UPDATE,
                kb.OLYMPUS_CAPABILITY_CLAIM,
                kb.OLYMPUS_CAPABILITY_HEARTBEAT,
                kb.OLYMPUS_CAPABILITY_COMPLETE,
            ],
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


def _allow(request: dict) -> dict:
    return {
        "schema_version": kb.AUTHORITY_VERIFICATION_SCHEMA,
        "verification_id": f"verification:{request['request_id'].split(':', 1)[1]}",
        "decision": "ALLOW",
        "current": True,
        "source": request["authority_source"],
        "source_revision": request["authority_revision"],
        "request_id": request["request_id"],
        "request": request,
    }


def _create(conn, context: dict | None = None, **kwargs) -> str:
    context = copy.deepcopy(context or _context())
    return kb.create_olympus_task(
        conn,
        olympus_context=context,
        authority_verifier=_allow,
        actor=context["agent_id"],
        operation_id=kwargs.pop("operation_id", "create:1"),
        expected_revision=context["authority"]["revision"],
        title=kwargs.pop("title", "governed task"),
        assignee=kwargs.pop("assignee", context["agent_id"]),
        **kwargs,
    )


def _claim(conn, task_id: str, context: dict, **kwargs):
    return kb.claim_task(
        conn,
        task_id,
        authority_verifier=kwargs.pop("authority_verifier", _allow),
        actor=kwargs.pop("actor", context["agent_id"]),
        operation_id=kwargs.pop("operation_id", f"claim:{task_id}"),
        expected_revision=kwargs.pop(
            "expected_revision", context["authority"]["revision"]
        ),
        **kwargs,
    )


def _heartbeat(conn, task_id: str, context: dict, **kwargs) -> bool:
    return kb.heartbeat_claim(
        conn,
        task_id,
        authority_verifier=kwargs.pop("authority_verifier", _allow),
        actor=kwargs.pop("actor", context["agent_id"]),
        operation_id=kwargs.pop("operation_id", f"heartbeat:{task_id}"),
        expected_revision=kwargs.pop(
            "expected_revision", context["authority"]["revision"]
        ),
        **kwargs,
    )


def _complete(conn, task_id: str, context: dict, **kwargs) -> bool:
    return kb.complete_task(
        conn,
        task_id,
        authority_verifier=kwargs.pop("authority_verifier", _allow),
        actor=kwargs.pop("actor", context["agent_id"]),
        operation_id=kwargs.pop("operation_id", f"complete:{task_id}"),
        expected_revision=kwargs.pop(
            "expected_revision", context["authority"]["revision"]
        ),
        **kwargs,
    )


def _update(conn, task_id: str, context: dict, **kwargs) -> bool:
    return kb.update_task_olympus_context(
        conn,
        task_id,
        context,
        authority_verifier=kwargs.pop("authority_verifier", _allow),
        actor=kwargs.pop("actor", context["agent_id"]),
        operation_id=kwargs.pop("operation_id", f"update:{task_id}"),
        expected_revision=kwargs.pop(
            "expected_revision", context["authority"]["revision"]
        ),
        **kwargs,
    )


def _inject_raw_context(conn, context: dict, *, assignee: str = "coding") -> str:
    task_id = kb.create_task(conn, title="raw governed row", assignee=assignee)
    conn.execute(
        "UPDATE tasks SET olympus_context = ? WHERE id = ?",
        (json.dumps(context), task_id),
    )
    conn.commit()
    return task_id


def _rejection_reason(conn, task_id: str, kind: str = "claim_rejected") -> str:
    rejected = [e for e in kb.list_events(conn, task_id) if e.kind == kind]
    assert rejected
    return rejected[-1].payload["reason"]


def test_authorized_retry_completion_trace_is_attributable(conn):
    first_context = _context(lease_id="lease-attempt-1")
    task_id = _create(conn, first_context)

    first = _claim(
        conn, task_id, first_context, claimer="worker:first", ttl_seconds=7200
    )
    assert first is not None
    first_run_id = first.current_run_id
    assert first.claim_expires <= first_context["lease"]["expires_at"]
    assert kb.reclaim_task(conn, task_id, reason="retry with renewed lease")

    renewed = _context(
        lease_id="lease-attempt-2", authority_revision=8, lease_revision=12
    )
    assert _update(conn, task_id, renewed)
    second = _claim(conn, task_id, renewed, claimer="worker:second")
    assert second is not None
    second_run_id = second.current_run_id
    assert second_run_id != first_run_id
    assert _complete(
        conn,
        task_id,
        renewed,
        result="done",
        summary="evidence-backed completion",
        metadata={"evidence_refs": ["evidence://result/1"]},
        expected_run_id=second_run_id,
    )

    task = kb.get_task(conn, task_id)
    assert task is not None and task.status == "done"
    assert task.olympus_context["lease"]["lease_id"] == "lease-attempt-2"
    runs = kb.list_runs(conn, task_id)
    assert [run.outcome for run in runs] == ["reclaimed", "completed"]
    assert runs[0].olympus_context["lease"]["lease_id"] == "lease-attempt-1"
    assert runs[1].olympus_context["lease"]["lease_id"] == "lease-attempt-2"
    assert runs[1].olympus_context["authority"]["revision"] == 8
    assert runs[1].olympus_context["mission_id"] == "mission-1"

    claimed = [e for e in kb.list_events(conn, task_id) if e.kind == "claimed"]
    assert [e.payload["olympus"]["lease_ref"] for e in claimed] == [
        "lease-attempt-1",
        "lease-attempt-2",
    ]
    worker_context = kb.build_worker_context(conn, task_id)
    assert "## Olympus authority" in worker_context
    assert "lease-attempt-2" in worker_context


@pytest.mark.parametrize(
    ("mutation", "reason"),
    [
        ("missing", "olympus_lease_missing"),
        ("expired", "olympus_lease_expired"),
        ("revoked", "olympus_lease_revoked"),
        ("foreign", "olympus_lease_foreign_mission"),
        ("context-agent", "olympus_agent_mismatch"),
        ("lease-agent", "olympus_agent_mismatch"),
        ("holder", "olympus_agent_mismatch"),
    ],
)
def test_claim_denies_missing_stale_revoked_foreign_or_identity_conflict(
    conn, mutation: str, reason: str
):
    context = _context()
    if mutation == "missing":
        del context["lease"]
    elif mutation == "expired":
        context["lease"]["expires_at"] = int(time.time()) - 1
    elif mutation == "revoked":
        context["lease"]["status"] = "REVOKED"
    elif mutation == "foreign":
        context["lease"]["mission_id"] = "mission-other"
    elif mutation == "context-agent":
        context["agent_id"] = "reviewer"
    elif mutation == "lease-agent":
        context["lease"]["agent_id"] = "reviewer"
    elif mutation == "holder":
        context["lease"]["holder"] = "reviewer"
    task_id = _inject_raw_context(conn, context)

    assert _claim(conn, task_id, _context(), claimer="worker:denied") is None
    task = kb.get_task(conn, task_id)
    assert task is not None and task.status == "ready"
    assert kb.list_runs(conn, task_id) == []
    assert _rejection_reason(conn, task_id) == reason


@pytest.mark.parametrize("location", ["context", "authority", "lease"])
def test_context_v2_rejects_unknown_fields(conn, location: str):
    context = _context()
    if location == "context":
        context["typo_field"] = "unsafe"
    else:
        context[location]["typo_field"] = "unsafe"
    with pytest.raises(kb.OlympusContextError) as exc_info:
        _create(conn, context)
    assert exc_info.value.reason == "olympus_context_invalid"


@pytest.mark.parametrize(
    "verifier",
    [
        None,
        lambda request: {**_allow(request), "decision": "DENY"},
        lambda request: {**_allow(request), "current": False},
        lambda request: {**_allow(request), "source": "foreign:issuer"},
        lambda request: {**_allow(request), "source_revision": 999},
        lambda request: {**_allow(request), "request_id": "wrong"},
        lambda request: {**_allow(request), "request": {"forged": True}},
        lambda request: (_ for _ in ()).throw(RuntimeError("issuer down")),
    ],
)
def test_creation_denies_missing_stale_foreign_or_contradictory_verifier(
    conn, verifier
):
    context = _context()
    with pytest.raises(kb.OlympusContextError):
        kb.create_olympus_task(
            conn,
            olympus_context=context,
            authority_verifier=verifier,
            actor="coding",
            operation_id="create:abuse",
            expected_revision=7,
            title="must not exist",
            assignee="coding",
        )
    assert kb.list_tasks(conn) == []


@pytest.mark.parametrize(
    ("mutation", "reason"),
    [
        ("actor", "olympus_actor_mismatch"),
        ("revision", "olympus_revision_mismatch"),
        ("capability", "olympus_capability_missing"),
        ("scope", "olympus_scope_mismatch"),
    ],
)
def test_creation_denies_wrong_actor_revision_capability_or_scope(
    conn, mutation: str, reason: str
):
    context = _context()
    actor = "coding"
    revision = 7
    if mutation == "actor":
        actor = "dashboard"
    elif mutation == "revision":
        revision = 6
    elif mutation == "capability":
        context["authority"]["capabilities"].remove(kb.OLYMPUS_CAPABILITY_CREATE)
    elif mutation == "scope":
        context["authority"]["scope"] = ["mission-other"]
    with pytest.raises(kb.OlympusContextError) as exc_info:
        kb.create_olympus_task(
            conn,
            olympus_context=context,
            authority_verifier=_allow,
            actor=actor,
            operation_id="create:local-denial",
            expected_revision=revision,
            title="must not exist",
            assignee="coding",
        )
    assert exc_info.value.reason == reason


def test_generic_create_and_legacy_update_cannot_inject_olympus_context(conn):
    with pytest.raises(TypeError):
        kb.create_task(
            conn,
            title="generic injection",
            assignee="coding",
            olympus_context=_context(),  # type: ignore[call-arg]
        )
    legacy_id = kb.create_task(conn, title="legacy", assignee="coding")
    with pytest.raises(kb.OlympusContextError) as exc_info:
        _update(conn, legacy_id, _context())
    assert exc_info.value.reason == "olympus_legacy_opt_in_forbidden"


def test_claim_requires_callable_canonical_verifier(conn):
    context = _context()
    task_id = _create(conn, context)
    assert kb.claim_task(conn, task_id, claimer="unverified") is None
    assert _rejection_reason(conn, task_id) == "olympus_authority_verification_unavailable"
    assert kb.get_task(conn, task_id).status == "ready"


def test_review_claim_uses_the_same_canonical_gate(conn):
    context = _context()
    task_id = _create(conn, context)
    conn.execute("UPDATE tasks SET status = 'review' WHERE id = ?", (task_id,))
    conn.commit()
    assert kb.claim_review_task(conn, task_id, claimer="reviewer:1") is None
    assert _rejection_reason(conn, task_id) == "olympus_authority_verification_unavailable"
    claimed = kb.claim_review_task(
        conn,
        task_id,
        claimer="reviewer:2",
        authority_verifier=_allow,
        actor="coding",
        operation_id="review-claim:1",
        expected_revision=7,
    )
    assert claimed is not None


def test_revocation_stops_heartbeat_and_completion_and_preserves_snapshot(conn):
    context = _context()
    task_id = _create(conn, context)
    claimed = _claim(conn, task_id, context, claimer="worker:active")
    assert claimed is not None
    run_id = claimed.current_run_id

    revoked = copy.deepcopy(context)
    revoked["lease"]["status"] = "REVOKED"
    revoked["authority"]["revision"] = 8
    revoked["lease"]["revision"] = 12
    assert _update(conn, task_id, revoked)
    assert not _heartbeat(conn, task_id, revoked, claimer="worker:active")
    assert not _complete(conn, task_id, revoked, result="must not land")
    task = kb.get_task(conn, task_id)
    assert task.status == "running"
    assert task.claim_expires < int(time.time())
    run = kb.get_run(conn, run_id)
    assert run.olympus_context["lease"]["status"] == "ACTIVE"
    assert _rejection_reason(conn, task_id, "completion_rejected") == "olympus_lease_revoked"


def test_revoked_attempt_reconciles_to_fresh_verified_retry(conn):
    context = _context(lease_id="lease-before-revocation")
    task_id = _create(conn, context)
    assert _claim(conn, task_id, context, claimer="worker:old") is not None

    revoked = copy.deepcopy(context)
    revoked["lease"]["status"] = "REVOKED"
    revoked["authority"]["revision"] = 8
    revoked["lease"]["revision"] = 12
    assert _update(conn, task_id, revoked)
    renewed = _context(
        lease_id="lease-after-revocation", authority_revision=9, lease_revision=13
    )
    assert _update(conn, task_id, renewed)
    assert not _heartbeat(conn, task_id, renewed, claimer="worker:old")

    # A sweep without a canonical verifier may reclaim the stopped attempt,
    # but may never extend or resume it.
    assert kb.release_stale_claims(conn) == 1
    retried = _claim(conn, task_id, renewed, claimer="worker:new")
    assert retried is not None
    assert _complete(conn, task_id, renewed, result="fresh attempt completed")


def test_attempt_snapshot_requires_exact_authority_and_lease_identity(conn):
    context = _context()
    task_id = _create(conn, context)
    claimed = _claim(conn, task_id, context, claimer="worker:exact")
    run = kb.get_run(conn, claimed.current_run_id)
    forged = copy.deepcopy(run.olympus_context)
    forged["lease"]["lease_id"] = "foreign-attempt"
    forged["authority"]["revision"] = 999
    conn.execute(
        "UPDATE task_runs SET olympus_context = ? WHERE id = ?",
        (kb._serialize_olympus_context(forged), claimed.current_run_id),
    )
    conn.commit()
    assert not _heartbeat(conn, task_id, context, claimer="worker:exact")
    assert _rejection_reason(conn, task_id, "heartbeat_rejected") == "olympus_run_context_mismatch"


def test_cross_agent_derivation_denied_but_verified_delegated_child_allowed(conn):
    parent_context = _context()
    parent_id = _create(conn, parent_context, title="parent")
    assert kb.derive_olympus_child_context(parent_context, agent_id="coding") == kb.normalize_olympus_context(parent_context)
    with pytest.raises(kb.OlympusContextError) as exc_info:
        kb.derive_olympus_child_context(parent_context, agent_id="reviewer")
    assert exc_info.value.reason == "olympus_delegation_requires_verification"
    with pytest.raises(kb.OlympusContextError) as exc_info:
        kb.create_task(conn, title="generic child", assignee="coding", parents=[parent_id])
    assert exc_info.value.reason == "olympus_verified_context_required"

    delegated = _context(
        lease_id="lease-reviewer", agent_id="reviewer", authority_revision=8, lease_revision=12
    )
    child_id = _create(
        conn,
        delegated,
        title="verified delegated child",
        assignee="reviewer",
        parents=[parent_id],
        operation_id="create:delegated-child",
    )
    child = kb.get_task(conn, child_id)
    assert child.olympus_context["agent_id"] == "reviewer"
    assert child.olympus_context["lease"]["holder"] == "reviewer"
    assert child.olympus_context["lease"]["lease_id"] == "lease-reviewer"


def test_direct_completion_cannot_bypass_governed_claim_start(conn):
    context = _context()
    task_id = _create(conn, context)
    assert not _complete(conn, task_id, context, result="bypass")
    assert kb.get_task(conn, task_id).status == "ready"
    assert _rejection_reason(conn, task_id, "completion_rejected") == "olympus_completion_without_active_run"


def test_ordinary_kanban_compatibility_is_unchanged(conn):
    claimed_id = kb.create_task(conn, title="legacy claim", assignee="coding")
    claimed = kb.claim_task(conn, claimed_id, claimer="legacy:worker")
    assert claimed is not None and claimed.olympus_context is None
    assert kb.complete_task(conn, claimed_id, result="ok")
    assert kb.list_runs(conn, claimed_id)[0].olympus_context is None
    manual_id = kb.create_task(conn, title="legacy manual")
    assert kb.complete_task(conn, manual_id, result="still supported")


def test_dispatcher_without_canonical_issuer_never_spawns_governed_work(
    conn, monkeypatch
):
    context = _context()
    task_id = _create(conn, context)
    monkeypatch.setattr("hermes_cli.profiles.profile_exists", lambda _: True)
    spawned: list[str] = []
    result = kb.dispatch_once(
        conn,
        spawn_fn=lambda task, workspace: spawned.append(task.id),
        max_spawn=1,
    )
    assert result.spawned == []
    assert spawned == []
    assert kb.get_task(conn, task_id).status == "ready"
    assert _rejection_reason(conn, task_id) == "olympus_authority_verification_unavailable"


def test_restart_reloads_exact_context_and_reverifies(conn):
    context = _context()
    task_id = _create(conn, context)
    db_path = conn.execute("PRAGMA database_list").fetchone()[2]
    conn.close()
    reopened = kb.connect(Path(db_path))
    try:
        assert kb.claim_task(
            reopened,
            task_id,
            claimer="restart:denied",
            authority_verifier=lambda request: {**_allow(request), "source_revision": 999},
            actor="coding",
            operation_id="restart:claim:denied",
            expected_revision=7,
        ) is None
        claimed = _claim(
            reopened,
            task_id,
            context,
            claimer="restart:allowed",
            operation_id="restart:claim:allowed",
        )
        assert claimed is not None
        assert claimed.olympus_context == kb.normalize_olympus_context(context)
    finally:
        reopened.close()


def test_three_then_six_concurrent_claimers_admit_exactly_one(tmp_path, monkeypatch):
    home = tmp_path / ".hermes"
    home.mkdir()
    monkeypatch.setenv("HERMES_HOME", str(home))
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    db_path = home / "concurrency.db"
    kb._INITIALIZED_PATHS.discard(str(db_path.resolve()))
    context = _context()

    def run_race(contenders: int, task_id: str) -> list[bool]:
        barrier = threading.Barrier(contenders)
        results = [False] * contenders

        def worker(index: int) -> None:
            with kb.connect(db_path) as local:
                barrier.wait()
                results[index] = _claim(
                    local,
                    task_id,
                    context,
                    claimer=f"race:{contenders}:{index}",
                    operation_id=f"race:{contenders}:{index}",
                ) is not None

        threads = [threading.Thread(target=worker, args=(i,)) for i in range(contenders)]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join()
        return results

    with kb.connect(db_path) as setup:
        first = _create(setup, context, title="three-way", operation_id="create:three")
    assert sum(run_race(3, first)) == 1
    with kb.connect(db_path) as setup:
        second = _create(setup, context, title="six-way", operation_id="create:six")
    assert sum(run_race(6, second)) == 1


def test_additive_migration_preserves_legacy_rows_and_backup_rolls_back(
    tmp_path, monkeypatch
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
            id INTEGER PRIMARY KEY AUTOINCREMENT, task_id TEXT NOT NULL,
            kind TEXT NOT NULL, payload TEXT, created_at INTEGER NOT NULL
        );
        CREATE TABLE task_runs (
            id INTEGER PRIMARY KEY AUTOINCREMENT, task_id TEXT NOT NULL,
            profile TEXT, step_key TEXT, status TEXT NOT NULL,
            claim_lock TEXT, claim_expires INTEGER, worker_pid INTEGER,
            max_runtime_seconds INTEGER, last_heartbeat_at INTEGER,
            started_at INTEGER NOT NULL, ended_at INTEGER, outcome TEXT,
            summary TEXT, metadata TEXT, error TEXT
        );
        INSERT INTO tasks (id, title, status, created_at)
        VALUES ('legacy-1', 'preserve me', 'ready', 1);
        """
    )
    raw.commit()
    raw.close()
    backup = tmp_path / "legacy.pre-olympus.bak"
    shutil.copy2(db_path, backup)
    backup_digest = backup.read_bytes()

    kb._INITIALIZED_PATHS.discard(str(db_path.resolve()))
    with kb.connect(db_path) as migrated:
        task_cols = {r["name"] for r in migrated.execute("PRAGMA table_info(tasks)")}
        run_cols = {r["name"] for r in migrated.execute("PRAGMA table_info(task_runs)")}
        task = kb.get_task(migrated, "legacy-1")
        assert "olympus_context" in task_cols
        assert "olympus_context" in run_cols
        assert task is not None and task.olympus_context is None
        assert kb.claim_task(migrated, "legacy-1") is not None
    assert backup.read_bytes() == backup_digest

    for suffix in ("-wal", "-shm"):
        Path(str(db_path) + suffix).unlink(missing_ok=True)
    shutil.copy2(backup, db_path)
    raw = sqlite3.connect(db_path)
    try:
        task_cols = {row[1] for row in raw.execute("PRAGMA table_info(tasks)")}
        assert "olympus_context" not in task_cols
        assert raw.execute(
            "SELECT title FROM tasks WHERE id='legacy-1'"
        ).fetchone()[0] == "preserve me"
    finally:
        raw.close()
