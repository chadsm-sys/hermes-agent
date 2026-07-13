"""Olympus authority binding contracts for the existing Hermes Kanban DB."""

from __future__ import annotations

import copy
import json
import shutil
import sqlite3
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


def _context(*, now: int | None = None, lease_ref: str = "lease-1") -> dict:
    current = int(time.time()) if now is None else now
    return {
        "schema_version": 1,
        "goal_id": "goal-1",
        "program_id": "program-1",
        "milestone_id": "milestone-1",
        "mission_id": "mission-1",
        "workstream_id": "workstream-1",
        "authority": {
            "ref": "authority-1",
            "mission_id": "mission-1",
            "status": "active",
            "expires_at": current + 3600,
        },
        "lease": {
            "ref": lease_ref,
            "mission_id": "mission-1",
            "holder": "olympus",
            "status": "active",
            "expires_at": current + 1800,
        },
        "risk": "high",
        "agent_id": "coding",
        "review_status": "pending",
        "evidence_refs": ["evidence://plan/1"],
    }


def _rejection_reason(conn, task_id: str) -> str:
    rejected = [e for e in kb.list_events(conn, task_id) if e.kind == "claim_rejected"]
    assert rejected
    return rejected[-1].payload["reason"]


def test_authorized_retry_completion_trace_is_attributable(conn):
    first_context = _context(lease_ref="lease-attempt-1")
    task_id = kb.create_task(
        conn,
        title="governed task",
        assignee="coding",
        olympus_context=first_context,
    )

    first = kb.claim_task(conn, task_id, claimer="worker:first", ttl_seconds=7200)
    assert first is not None
    first_run_id = first.current_run_id
    assert first.claim_expires <= first_context["lease"]["expires_at"]
    assert kb.reclaim_task(conn, task_id, reason="retry with renewed lease")

    renewed = _context(lease_ref="lease-attempt-2")
    assert kb.update_task_olympus_context(conn, task_id, renewed)
    second = kb.claim_task(conn, task_id, claimer="worker:second")
    assert second is not None
    second_run_id = second.current_run_id
    assert second_run_id != first_run_id
    assert kb.complete_task(
        conn,
        task_id,
        result="done",
        summary="evidence-backed completion",
        metadata={"evidence_refs": ["evidence://result/1"]},
        expected_run_id=second_run_id,
    )

    task = kb.get_task(conn, task_id)
    assert task is not None and task.status == "done"
    assert task.olympus_context["lease"]["ref"] == "lease-attempt-2"
    runs = kb.list_runs(conn, task_id)
    assert [run.outcome for run in runs] == ["reclaimed", "completed"]
    assert runs[0].olympus_context["lease"]["ref"] == "lease-attempt-1"
    assert runs[1].olympus_context["lease"]["ref"] == "lease-attempt-2"
    assert runs[1].olympus_context["mission_id"] == "mission-1"
    assert runs[1].olympus_context["agent_id"] == "coding"

    claimed = [e for e in kb.list_events(conn, task_id) if e.kind == "claimed"]
    assert [e.payload["olympus"]["lease_ref"] for e in claimed] == [
        "lease-attempt-1",
        "lease-attempt-2",
    ]
    completed = [e for e in kb.list_events(conn, task_id) if e.kind == "completed"][-1]
    assert completed.run_id == second_run_id
    assert completed.payload["olympus"]["mission_id"] == "mission-1"
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
        ("agent", "olympus_agent_mismatch"),
    ],
)
def test_claim_denies_missing_expired_revoked_foreign_or_wrong_agent(
    conn, mutation: str, reason: str
):
    context = _context()
    assignee = "coding"
    if mutation == "expired":
        context["lease"]["expires_at"] = int(time.time()) - 1
    elif mutation == "revoked":
        context["lease"]["status"] = "revoked"
    elif mutation == "foreign":
        context["lease"]["mission_id"] = "mission-other"
    elif mutation == "agent":
        context["agent_id"] = "reviewer"

    if mutation == "missing":
        task_id = kb.create_task(conn, title="missing lease", assignee=assignee)
        del context["lease"]
        conn.execute(
            "UPDATE tasks SET olympus_context = ? WHERE id = ?",
            (json.dumps(context), task_id),
        )
        conn.commit()
    else:
        task_id = kb.create_task(
            conn,
            title=f"denied {mutation}",
            assignee=assignee,
            olympus_context=context,
        )

    assert kb.claim_task(conn, task_id, claimer="worker:denied") is None
    task = kb.get_task(conn, task_id)
    assert task is not None and task.status == "ready"
    assert kb.list_runs(conn, task_id) == []
    assert _rejection_reason(conn, task_id) == reason


@pytest.mark.parametrize("location", ["context", "authority", "lease"])
def test_context_v1_rejects_unknown_fields(conn, location: str):
    context = _context()
    if location == "context":
        context["typo_field"] = "unsafe"
    else:
        context[location]["typo_field"] = "unsafe"

    with pytest.raises(kb.OlympusContextError) as exc_info:
        kb.create_task(
            conn,
            title=f"unknown {location} field",
            assignee="coding",
            olympus_context=context,
        )

    assert exc_info.value.reason == "olympus_context_invalid"


def test_review_claim_uses_the_same_fail_closed_gate(conn):
    context = _context()
    context["lease"]["status"] = "revoked"
    task_id = kb.create_task(
        conn,
        title="review denied",
        assignee="coding",
        olympus_context=context,
    )
    conn.execute("UPDATE tasks SET status = 'review' WHERE id = ?", (task_id,))
    conn.commit()

    assert kb.claim_review_task(conn, task_id, claimer="reviewer:1") is None
    assert kb.get_task(conn, task_id).status == "review"
    assert _rejection_reason(conn, task_id) == "olympus_lease_revoked"


def test_revocation_stops_heartbeat_and_completion_but_preserves_run_snapshot(conn):
    context = _context()
    task_id = kb.create_task(
        conn,
        title="revoke in flight",
        assignee="coding",
        olympus_context=context,
    )
    claimed = kb.claim_task(conn, task_id, claimer="worker:active")
    assert claimed is not None
    run_id = claimed.current_run_id

    revoked = copy.deepcopy(context)
    revoked["lease"]["status"] = "revoked"
    assert kb.update_task_olympus_context(conn, task_id, revoked)
    assert not kb.heartbeat_claim(conn, task_id, claimer="worker:active")
    assert not kb.complete_task(conn, task_id, result="must not land")
    task = kb.get_task(conn, task_id)
    assert task.status == "running"
    assert task.claim_expires < int(time.time())
    run = kb.get_run(conn, run_id)
    assert run.olympus_context["lease"]["status"] == "active"
    rejection = [
        e for e in kb.list_events(conn, task_id) if e.kind == "completion_rejected"
    ][-1]
    assert rejection.payload["reason"] == "olympus_lease_revoked"


def test_new_lease_cannot_resurrect_an_attempt_revoked_in_flight(conn):
    context = _context(lease_ref="lease-before-revocation")
    task_id = kb.create_task(
        conn,
        title="revoked attempt stays stopped",
        assignee="coding",
        olympus_context=context,
    )
    claimed = kb.claim_task(conn, task_id, claimer="worker:revoked")
    assert claimed is not None

    revoked = copy.deepcopy(context)
    revoked["lease"]["status"] = "revoked"
    assert kb.update_task_olympus_context(conn, task_id, revoked)
    renewed = _context(lease_ref="lease-after-revocation")
    assert kb.update_task_olympus_context(conn, task_id, renewed)

    assert not kb.heartbeat_claim(conn, task_id, claimer="worker:revoked")
    assert not kb.complete_task(conn, task_id, result="must retry")
    reasons = [
        e.payload["reason"]
        for e in kb.list_events(conn, task_id)
        if e.kind in {"heartbeat_rejected", "completion_rejected"}
    ]
    assert reasons[-2:] == ["olympus_claim_expired", "olympus_claim_expired"]

    assert kb.release_stale_claims(conn) == 1
    retried = kb.claim_task(conn, task_id, claimer="worker:retried")
    assert retried is not None
    assert kb.complete_task(conn, task_id, result="new attempt authorized")


def test_direct_completion_cannot_bypass_governed_claim_start(conn):
    task_id = kb.create_task(
        conn,
        title="no direct completion",
        assignee="coding",
        olympus_context=_context(),
    )
    assert not kb.complete_task(conn, task_id, result="bypass")
    assert kb.get_task(conn, task_id).status == "ready"
    rejected = [
        e for e in kb.list_events(conn, task_id) if e.kind == "completion_rejected"
    ][-1]
    assert rejected.payload["reason"] == "olympus_completion_without_active_run"


def test_ordinary_kanban_task_keeps_legacy_claim_and_manual_completion(conn):
    claimed_id = kb.create_task(conn, title="legacy claim", assignee="coding")
    claimed = kb.claim_task(conn, claimed_id, claimer="legacy:worker")
    assert claimed is not None and claimed.olympus_context is None
    assert kb.complete_task(conn, claimed_id, result="ok")
    assert kb.list_runs(conn, claimed_id)[0].olympus_context is None

    manual_id = kb.create_task(conn, title="legacy manual")
    assert kb.complete_task(conn, manual_id, result="still supported")
    assert kb.get_task(conn, manual_id).status == "done"


def test_dispatcher_claim_gate_prevents_spawn(conn, monkeypatch):
    context = _context()
    context["lease"]["status"] = "revoked"
    task_id = kb.create_task(
        conn,
        title="dispatcher denied",
        assignee="coding",
        olympus_context=context,
    )
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
    assert _rejection_reason(conn, task_id) == "olympus_lease_revoked"


def test_dispatcher_revalidates_authority_after_workspace_setup(
    conn, monkeypatch, tmp_path
):
    context = _context()
    task_id = kb.create_task(
        conn,
        title="revoke between claim and spawn",
        assignee="coding",
        olympus_context=context,
    )
    monkeypatch.setattr("hermes_cli.profiles.profile_exists", lambda _: True)
    spawned: list[str] = []

    def revoke_during_workspace(task, *, board=None):
        revoked = copy.deepcopy(context)
        revoked["lease"]["status"] = "revoked"
        assert kb.update_task_olympus_context(conn, task.id, revoked)
        return tmp_path

    monkeypatch.setattr(kb, "resolve_workspace", revoke_during_workspace)
    result = kb.dispatch_once(
        conn,
        spawn_fn=lambda task, workspace: spawned.append(task.id),
        max_spawn=1,
    )

    assert result.spawned == []
    assert spawned == []
    task = kb.get_task(conn, task_id)
    assert task.status == "ready"
    assert task.current_run_id is None
    events = kb.list_events(conn, task_id)
    assert any(e.kind == "heartbeat_rejected" for e in events)
    assert any(e.kind == "spawn_rejected" for e in events)


def test_governed_child_inherits_mission_and_rebinds_agent(conn):
    parent_id = kb.create_task(
        conn,
        title="parent",
        assignee="coding",
        olympus_context=_context(),
    )
    child_id = kb.create_task(
        conn,
        title="child",
        assignee="reviewer",
        parents=[parent_id],
    )
    child = kb.get_task(conn, child_id)
    assert child.olympus_context["mission_id"] == "mission-1"
    assert child.olympus_context["agent_id"] == "reviewer"
    assert child.olympus_context["lease"]["ref"] == "lease-1"


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
        assert raw.execute("SELECT title FROM tasks WHERE id='legacy-1'").fetchone()[0] == "preserve me"
    finally:
        raw.close()
