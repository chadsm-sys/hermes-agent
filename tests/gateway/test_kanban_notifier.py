import asyncio
from pathlib import Path


from gateway.config import Platform
from gateway.run import GatewayRunner
from hermes_cli import kanban_db as kb


class RecordingAdapter:
    def __init__(self):
        self.sent = []

    async def send(self, chat_id, text, metadata=None):
        self.sent.append({"chat_id": chat_id, "text": text, "metadata": metadata or {}})


class DisconnectedAdapters(dict):
    """Expose a platform during collection, then simulate disconnect on get()."""

    def get(self, key, default=None):
        return None


async def _run_one_notifier_tick(monkeypatch, runner):
    real_sleep = asyncio.sleep

    async def fake_sleep(delay):
        if delay == 5:
            return None
        runner._running = False
        await real_sleep(0)

    monkeypatch.setattr(asyncio, "sleep", fake_sleep)
    await runner._kanban_notifier_watcher(interval=1)


def _make_runner(adapter):
    runner = GatewayRunner.__new__(GatewayRunner)
    runner._running = True
    runner.adapters = {Platform.TELEGRAM: adapter}
    runner._kanban_sub_fail_counts = {}
    return runner


def _create_completed_subscription(summary="done once", artifacts=None):
    conn = kb.connect()
    try:
        tid = kb.create_task(conn, title="notify once", assignee="worker")
        kb.add_notify_sub(conn, task_id=tid, platform="telegram", chat_id="chat-1")
        kb.complete_task(
            conn,
            tid,
            summary=summary,
            metadata=({"artifacts": artifacts} if artifacts else None),
        )
        return tid
    finally:
        conn.close()


def _unseen_terminal_events(tid):
    conn = kb.connect()
    try:
        _, events = kb.unseen_events_for_sub(
            conn,
            task_id=tid,
            platform="telegram",
            chat_id="chat-1",
            kinds=["completed", "blocked", "gave_up", "crashed", "timed_out"],
        )
        return events
    finally:
        conn.close()


def test_kanban_notifier_dedupes_board_slugs_pointing_to_same_db(tmp_path, monkeypatch):
    db_path = tmp_path / "shared-kanban.db"
    monkeypatch.setenv("HERMES_KANBAN_DB", str(db_path))
    kb.init_db()
    kb.write_board_metadata("alias-a", name="Alias A")
    kb.write_board_metadata("alias-b", name="Alias B")

    tid = _create_completed_subscription()

    adapter = RecordingAdapter()
    runner = _make_runner(adapter)

    asyncio.run(_run_one_notifier_tick(monkeypatch, runner))

    assert len(adapter.sent) == 1
    assert "Kanban" in adapter.sent[0]["text"]
    assert tid in adapter.sent[0]["text"]


def test_kanban_notifier_claim_prevents_second_watcher_send(tmp_path, monkeypatch):
    db_path = tmp_path / "single-owner.db"
    monkeypatch.setenv("HERMES_KANBAN_DB", str(db_path))
    kb.init_db()

    tid = _create_completed_subscription()

    adapter1 = RecordingAdapter()
    adapter2 = RecordingAdapter()

    asyncio.run(_run_one_notifier_tick(monkeypatch, _make_runner(adapter1)))
    asyncio.run(_run_one_notifier_tick(monkeypatch, _make_runner(adapter2)))

    assert len(adapter1.sent) == 1
    assert adapter2.sent == []


def test_kanban_notifier_rewinds_claim_if_adapter_disconnects(tmp_path, monkeypatch):
    db_path = tmp_path / "adapter-disconnect.db"
    monkeypatch.setenv("HERMES_KANBAN_DB", str(db_path))
    kb.init_db()
    tid = _create_completed_subscription()

    runner = GatewayRunner.__new__(GatewayRunner)
    runner._running = True
    runner.adapters = DisconnectedAdapters({Platform.TELEGRAM: RecordingAdapter()})
    runner._kanban_sub_fail_counts = {}

    asyncio.run(_run_one_notifier_tick(monkeypatch, runner))

    assert [ev.kind for ev in _unseen_terminal_events(tid)] == ["completed"]


def test_kanban_db_path_is_test_isolated_from_real_home():
    hermes_home = Path(kb.kanban_home())
    production_db = Path.home() / ".hermes" / "kanban.db"
    assert kb.kanban_db_path().resolve() != production_db.resolve()

    conn = kb.connect()
    try:
        tid = kb.create_task(conn, title="x", assignee="worker")
        kb.add_notify_sub(conn, task_id=tid, platform="telegram", chat_id="chat-1")
    finally:
        conn.close()

    assert kb.kanban_db_path().resolve().is_relative_to(hermes_home.resolve())
    assert kb.kanban_db_path().resolve() != production_db.resolve()


class FailingAdapter:
    """Adapter whose send() always raises, simulating a transient send error."""

    def __init__(self):
        self.attempts = 0

    async def send(self, chat_id, text, metadata=None):
        self.attempts += 1
        raise RuntimeError("simulated send failure")


class ArtifactAdapter(RecordingAdapter):
    def __init__(self, *, fail=False):
        super().__init__()
        self.fail = fail
        self.artifact_attempts = 0

    def extract_local_files(self, text):
        return [], text

    async def send_document(self, chat_id, file_path, metadata=None):
        self.artifact_attempts += 1
        if self.fail:
            raise RuntimeError("simulated artifact failure")

    async def send_image_file(self, chat_id, image_path, metadata=None):
        return await self.send_document(chat_id, image_path, metadata)

    async def send_multiple_images(self, chat_id, images, metadata=None):
        for image, _caption in images:
            await self.send_document(chat_id, image, metadata)

    async def send_video(self, chat_id, video_path, metadata=None):
        return await self.send_document(chat_id, video_path, metadata)


def test_kanban_notifier_marks_ambiguous_send_unknown_without_retry(tmp_path, monkeypatch):
    """A raising adapter is delivery-ambiguous and must not auto-redeliver."""
    db_path = tmp_path / "send-failure.db"
    monkeypatch.setenv("HERMES_KANBAN_DB", str(db_path))
    kb.init_db()
    tid = _create_completed_subscription()

    adapter = FailingAdapter()
    runner = _make_runner(adapter)

    asyncio.run(_run_one_notifier_tick(monkeypatch, runner))

    # A platform may accept the message before the transport raises. Persist
    # UNKNOWN and advance deliberately so a restart cannot duplicate it.
    assert adapter.attempts >= 1, "send should have been attempted at least once"
    assert _unseen_terminal_events(tid) == []
    conn = kb.connect()
    try:
        effect = conn.execute(
            "SELECT state FROM kanban_effect_journal WHERE task_id=?", (tid,)
        ).fetchone()
        assert effect["state"] == "unknown"
    finally:
        conn.close()


def test_artifact_has_independent_effect_and_failure_holds_cursor(
    tmp_path, monkeypatch,
):
    from gateway.platforms.base import BasePlatformAdapter

    db_path = tmp_path / "artifact-failure.db"
    artifact = tmp_path / "evidence.txt"
    artifact.write_text("evidence")
    monkeypatch.setenv("HERMES_KANBAN_DB", str(db_path))
    monkeypatch.setattr(
        BasePlatformAdapter,
        "filter_local_delivery_paths",
        staticmethod(lambda paths: list(paths)),
    )
    kb.init_db()
    tid = _create_completed_subscription(artifacts=[str(artifact)])
    adapter = ArtifactAdapter(fail=True)

    asyncio.run(_run_one_notifier_tick(monkeypatch, _make_runner(adapter)))
    assert len(adapter.sent) == 1
    assert adapter.artifact_attempts == 1
    assert [ev.kind for ev in _unseen_terminal_events(tid)] == ["completed"]
    conn = kb.connect()
    try:
        effects = conn.execute(
            "SELECT effect_kind,state,part FROM kanban_effect_journal "
            "WHERE task_id=? ORDER BY id",
            (tid,),
        ).fetchall()
        assert [tuple(row) for row in effects] == [
            ("notify_text", "applied", "text"),
            ("notify_artifact", "unknown", "artifacts"),
        ]
    finally:
        conn.close()

    asyncio.run(_run_one_notifier_tick(monkeypatch, _make_runner(adapter)))
    assert len(adapter.sent) == 1
    assert adapter.artifact_attempts == 1
    assert [ev.kind for ev in _unseen_terminal_events(tid)] == ["completed"]


def test_artifact_effect_applies_before_cursor_advance(tmp_path, monkeypatch):
    from gateway.platforms.base import BasePlatformAdapter

    db_path = tmp_path / "artifact-success.db"
    artifact = tmp_path / "evidence.txt"
    artifact.write_text("evidence")
    monkeypatch.setenv("HERMES_KANBAN_DB", str(db_path))
    monkeypatch.setattr(
        BasePlatformAdapter,
        "filter_local_delivery_paths",
        staticmethod(lambda paths: list(paths)),
    )
    kb.init_db()
    tid = _create_completed_subscription(artifacts=[str(artifact)])
    adapter = ArtifactAdapter()
    asyncio.run(_run_one_notifier_tick(monkeypatch, _make_runner(adapter)))
    assert adapter.artifact_attempts == 1
    assert _unseen_terminal_events(tid) == []
    conn = kb.connect()
    try:
        effects = conn.execute(
            "SELECT effect_kind,state FROM kanban_effect_journal "
            "WHERE task_id=? ORDER BY id",
            (tid,),
        ).fetchall()
        assert [tuple(row) for row in effects] == [
            ("notify_text", "applied"),
            ("notify_artifact", "applied"),
        ]
    finally:
        conn.close()


def test_notifier_redelivers_same_kind_on_dispatch_cycle(tmp_path, monkeypatch):
    """A retry cycle (crashed → reclaimed → crashed) notifies the user twice.

    Before #21398 the notifier auto-unsubscribed on any terminal event kind
    (gave_up / crashed / timed_out), so the second crash in a respawn cycle
    silently dropped — the subscription was already gone. This test pins the
    new contract: subscription survives non-final terminal events; the
    cursor handles dedup.

    Two crashes ten seconds apart on the same task — both should land on
    the adapter.
    """
    db_path = tmp_path / "redeliver-cycle.db"
    monkeypatch.setenv("HERMES_KANBAN_DB", str(db_path))
    kb.init_db()

    conn = kb.connect()
    try:
        tid = kb.create_task(conn, title="cycle test", assignee="worker")
        kb.add_notify_sub(conn, task_id=tid, platform="telegram", chat_id="chat-1")
        # First crash — fired by the dispatcher when the worker PID dies.
        kb._append_event(conn, tid, kind="crashed")
    finally:
        conn.close()

    adapter = RecordingAdapter()
    runner = _make_runner(adapter)
    asyncio.run(_run_one_notifier_tick(monkeypatch, runner))

    # First crash delivered.
    assert len(adapter.sent) == 1
    assert "crashed" in adapter.sent[0]["text"].lower()

    # Subscription survives — the cursor advanced past event #1, but the
    # row is still there.
    conn = kb.connect()
    try:
        subs = kb.list_notify_subs(conn, tid)
        assert len(subs) == 1, (
            "Subscription must survive a crashed event so a respawn-cycle "
            "second crash also notifies the user (issue #21398)."
        )

        # Second crash — same task, same dispatcher (or a respawn). Append
        # another event to simulate the dispatcher firing crashed a second
        # time during retry.
        kb._append_event(conn, tid, kind="crashed")
    finally:
        conn.close()

    # New tick: the second event has a fresh id past the cursor advance,
    # so it gets claimed and delivered.
    runner = _make_runner(adapter)
    asyncio.run(_run_one_notifier_tick(monkeypatch, runner))

    assert len(adapter.sent) == 2, (
        f"Second crashed event should also notify; got {len(adapter.sent)} "
        f"deliveries (texts: {[d['text'] for d in adapter.sent]})"
    )
    assert "crashed" in adapter.sent[1]["text"].lower()
