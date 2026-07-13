"""SQLite-backed Kanban board for multi-profile, multi-project collaboration.

In a fresh install the board lives at ``<root>/kanban.db`` where
``<root>`` is the **shared Hermes root** (the parent of any active
profile). Profiles intentionally collapse onto a shared board: it IS
the cross-profile coordination primitive. A worker spawned with
``hermes -p <profile>`` joins the same board as the dispatcher that
claimed the task. The same applies to ``<root>/kanban/workspaces/`` and
``<root>/kanban/logs/``.

**Multiple boards (projects):** users can create additional boards to
separate unrelated streams of work (e.g. one per project / repo / domain).
Each board is a directory under ``<root>/kanban/boards/<slug>/`` with
its own ``kanban.db``, ``workspaces/``, and ``logs/``. All boards share
the profile's Hermes home but are otherwise isolated: a worker spawned
for a task on board ``atm10-server`` sees only that board's tasks,
cannot enumerate other boards, and its dispatcher ticks don't touch
other boards' DBs.

The first (and for single-project users, only) board is ``default``.
For back-compat its on-disk DB is ``<root>/kanban.db`` (not
``boards/default/kanban.db``), so installs that predate the boards
feature keep working with zero migration. See :func:`kanban_db_path`.

Board resolution order (highest precedence first, all optional):

* ``board=`` argument passed directly to :func:`connect` / :func:`init_db`
  (explicit — used by the CLI ``--board`` flag and the dashboard
  ``?board=...`` query param).
* ``HERMES_KANBAN_BOARD`` env var (used by the dispatcher to pin workers
  to the board their task lives on — workers cannot see other boards).
* ``HERMES_KANBAN_DB`` env var (pins the DB file path directly — legacy
  override still honoured; highest precedence when the file path itself
  is what the caller wants to force).
* ``<root>/kanban/current`` — a one-line text file holding the slug of
  the "currently selected" board. Written by ``hermes kanban boards
  switch <slug>``. When absent, the active board is ``default``.

In standard installs ``<root>`` is ``~/.hermes``. In Docker / custom
deployments where ``HERMES_HOME`` points outside ``~/.hermes`` (e.g.
``/opt/hermes``), ``<root>`` is ``HERMES_HOME``. Legacy env-var
overrides still work:

* ``HERMES_KANBAN_DB`` — pin the database file path directly.
* ``HERMES_KANBAN_WORKSPACES_ROOT`` — pin the workspaces root directly.
* ``HERMES_KANBAN_HOME`` — pin the umbrella root that anchors kanban
  paths. Useful for tests and unusual deployments.

The dispatcher injects ``HERMES_KANBAN_DB``,
``HERMES_KANBAN_WORKSPACES_ROOT``, and ``HERMES_KANBAN_BOARD`` into
worker subprocess env so workers converge on the exact DB the
dispatcher used to claim their task — even under unusual symlink or
Docker layouts.

Schema is intentionally small: tasks, task_links, task_comments,
task_events.  The ``workspace_kind`` field decouples coordination from git
worktrees so that research / ops / digital-twin workloads work alongside
coding workloads.  See ``docs/hermes-kanban-v1-spec.pdf`` for the full
design specification.

Concurrency strategy: WAL mode + ``BEGIN IMMEDIATE`` for write
transactions + compare-and-swap (CAS) updates on ``tasks.status`` and
``tasks.claim_lock``.  SQLite serializes writers via its WAL lock, so at
most one claimer can win any given task.  Losers observe zero affected
rows and move on -- no retry loops, no distributed-lock machinery.
The CAS coordination is **per-board** — each board is a separate DB,
so multi-board installs get the same atomicity guarantees without any
new locking.
"""

from __future__ import annotations

import contextlib
import functools
import hashlib
import inspect
import json
import math
import os
import re
import secrets
import shutil
import sqlite3
import stat
import subprocess
import sys
import threading
import logging
import time
from contextvars import ContextVar, Token
from dataclasses import dataclass, field, replace
from pathlib import Path
from typing import Any, Callable, Iterable, Mapping, Optional

from toolsets import get_toolset_names

_log = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

VALID_STATUSES = {"triage", "todo", "scheduled", "ready", "running", "blocked", "review", "done", "archived"}
VALID_INITIAL_STATUSES = {"running", "blocked"}
VALID_WORKSPACE_KINDS = {"scratch", "worktree", "dir"}
KNOWN_TOOLSET_NAMES = frozenset(name.casefold() for name in get_toolset_names())
_IS_WINDOWS = sys.platform == "win32"

# Olympus does not get a second task, run, lease, or authority store inside
# Hermes.  Instead, an Olympus-authored task carries one versioned context
# document in the existing Kanban row.  The same immutable snapshot is copied
# onto every run so retries remain attributable even after Olympus renews or
# revokes the task's current lease reference.
OLYMPUS_CONTEXT_VERSION = 2
AUTHORITY_REQUEST_SCHEMA = "olympus-authority-request/3"
AUTHORITY_VERIFICATION_SCHEMA = "olympus-authority-verification/3"
AuthorityVerifier = Callable[[dict[str, Any]], dict[str, Any]]
MAX_AUTHORITY_VERIFICATION_TTL = 300.0
VALID_OLYMPUS_AUTHORITY_STATUSES = {"ACTIVE", "CONSUMED", "REVOKED"}
VALID_OLYMPUS_LEASE_STATUSES = {"ACTIVE", "RELEASED", "REVOKED"}
VALID_OLYMPUS_RISKS = {"low", "medium", "high", "critical"}
VALID_PROCESS_STATES = {
    "legacy", "workspace_pending", "launch_reserved", "starting",
    "registered", "termination_pending", "terminal", "spawn_failed",
    "identity_unverified",
}
VALID_EFFECT_KINDS = {"terminate_worker", "notify_text", "notify_artifact"}
VALID_EFFECT_STATES = {
    "pending", "applying", "applied", "gone", "not_sent", "unknown",
    "identity_unverified", "identity_mismatch", "authority_stale", "failed",
}
OLYMPUS_CONTEXT_KEYS = {
    "schema_version",
    "goal_id",
    "program_id",
    "milestone_id",
    "mission_id",
    "workstream_id",
    "authority",
    "lease",
    "risk",
    "agent_id",
    "review_status",
    "evidence_refs",
}
OLYMPUS_AUTHORITY_KEYS = {
    "authority_id",
    "status",
    "scope",
    "capabilities",
    "revision",
    "source",
    "expires_at",
}
OLYMPUS_LEASE_KEYS = {
    "lease_id",
    "status",
    "mission_id",
    "agent_id",
    "holder",
    "repository",
    "branch",
    "worktree",
    "revision",
    "source",
    "expires_at",
}
OLYMPUS_SOURCE_IDENTITY_KEYS = {
    "platform", "bot_id", "profile", "chat_id", "thread_id", "user_id",
}
OLYMPUS_TARGET_IDENTITY_KEYS = {
    "authorization_subject_id", "authorization_subject_revision",
    "authorization_subject_status", "control_action", "task_id",
    "task_record_revision", "goal_id", "program_id", "milestone_id",
    "mission_id", "workstream_id",
    "agent_id", "assignee", "status", "authority_id", "authority_revision",
    "authority_status", "authority_source", "lease_id", "lease_revision",
    "lease_status", "lease_source", "lease_agent_id", "lease_holder",
}

OLYMPUS_CAPABILITY_CREATE = "kanban.task.create"
OLYMPUS_CAPABILITY_UPDATE = "kanban.task.authority.update"
OLYMPUS_CAPABILITY_CLAIM = "kanban.task.claim"
OLYMPUS_CAPABILITY_HEARTBEAT = "kanban.task.heartbeat"
OLYMPUS_CAPABILITY_COMPLETE = "kanban.task.complete"
OLYMPUS_CAPABILITY_EDIT = "kanban.task.edit"
OLYMPUS_CAPABILITY_ASSIGN = "kanban.task.assign"
OLYMPUS_CAPABILITY_LINK = "kanban.task.link"
OLYMPUS_CAPABILITY_COMMENT = "kanban.task.comment"
OLYMPUS_CAPABILITY_ATTACHMENT = "kanban.task.attachment"
OLYMPUS_CAPABILITY_STATUS = "kanban.task.status"
OLYMPUS_CAPABILITY_TRIAGE = "kanban.task.triage"
OLYMPUS_CAPABILITY_ARCHIVE = "kanban.task.archive"
OLYMPUS_CAPABILITY_DELETE = "kanban.task.delete"
OLYMPUS_CAPABILITY_WORKSPACE = "kanban.task.workspace"
OLYMPUS_CAPABILITY_RECOVER = "kanban.task.recover"
OLYMPUS_CAPABILITY_NOTIFY = "kanban.task.notify"
OLYMPUS_CAPABILITY_INSPECT = "kanban.task.inspect"
OLYMPUS_CAPABILITY_RELEASE = "kanban.task.release"

# Frozen Mission Control v4 wire registry (foundation head
# 439523c332f1b86a9fae45992d983b66238a40b1).  This is deliberately explicit:
# an ALLOW for one action can never be substituted onto another action that
# happens to use the same local mutator or touch the same columns.
HERMES_KANBAN_ACTION_CAPABILITIES = dict((
    ("add_attachment", "kanban.task.attachment"),
    ("add_notification_subscription", "kanban.task.notify"),
    ("advance_notification_cursor", "kanban.task.notify"),
    ("archive", "kanban.task.archive"),
    ("assign", "kanban.task.assign"),
    ("block", "kanban.task.status"),
    ("claim", "kanban.task.claim"),
    ("claim_notification_delivery", "kanban.task.notify"),
    ("claim_notification_effect", "kanban.task.notify"),
    ("claim_review", "kanban.task.claim"),
    ("comment", "kanban.task.comment"),
    ("complete", "kanban.task.complete"),
    ("create", "kanban.task.create"),
    ("create_idempotent", "kanban.task.create"),
    ("decompose_triage", "kanban.task.triage"),
    ("delete", "kanban.task.delete"),
    ("delete_archived", "kanban.task.delete"),
    ("delete_attachment", "kanban.task.attachment"),
    ("demote_parent_reopened", "kanban.task.status"),
    ("edit_result", "kanban.task.edit"),
    ("edit_task", "kanban.task.edit"),
    ("enforce_max_runtime", "kanban.task.recover"),
    ("execute_worker_termination_effect", "kanban.task.recover"),
    ("extend_stale_claim", "kanban.task.recover"),
    ("fail_worker_launch", "kanban.task.recover"),
    ("finish_notification_effect", "kanban.task.notify"),
    ("heartbeat", "kanban.task.heartbeat"),
    ("heartbeat_worker", "kanban.task.heartbeat"),
    ("inspect_governed_status", "kanban.task.inspect"),
    ("link", "kanban.task.link"),
    ("link_governed_child", "kanban.task.link"),
    ("mark_worker_starting", "kanban.task.claim"),
    ("mark_worker_workspace_ready", "kanban.task.workspace"),
    ("promote", "kanban.task.status"),
    ("reclaim", "kanban.task.recover"),
    ("reconcile_effect_journal", "kanban.task.recover"),
    ("reconcile_worker_run", "kanban.task.recover"),
    ("record_failure", "kanban.task.recover"),
    ("recover_crashed_worker", "kanban.task.recover"),
    ("recover_stale_claim", "kanban.task.recover"),
    ("recover_stale_running", "kanban.task.recover"),
    ("register_worker_process", "kanban.task.claim"),
    ("release_blocked_task", "kanban.task.release"),
    ("release_unspawned_claim", "kanban.task.recover"),
    ("remove_notification_subscription", "kanban.task.notify"),
    ("reserve_notification_effect", "kanban.task.notify"),
    ("rewind_notification_cursor", "kanban.task.notify"),
    ("schedule", "kanban.task.status"),
    ("set_direct_status", "kanban.task.status"),
    ("set_worker_pid", "kanban.task.claim"),
    ("set_workspace", "kanban.task.workspace"),
    ("settle_worker_termination", "kanban.task.recover"),
    ("specify_triage", "kanban.task.triage"),
    ("stage_worker_termination", "kanban.task.recover"),
    ("unblock", "kanban.task.status"),
    ("unlink", "kanban.task.link"),
    ("unlink_deleted_task", "kanban.task.link"),
    ("update_authority_context", "kanban.task.authority.update"),
))

TELEGRAM_ACTION_CAPABILITIES = {
    "telegram-select": "telegram.olympus.select",
    "telegram-status": "telegram.olympus.status",
    "telegram-clear": "telegram.olympus.clear",
    "telegram-intake": "telegram.olympus.intake",
    "telegram-control:pause": "telegram.olympus.control.pause",
    "telegram-control:resume": "telegram.olympus.control.resume",
    "telegram-control:interrupt": "telegram.olympus.emergency.interrupt",
    "telegram-control:cancel": "telegram.olympus.emergency.cancel",
}
OLYMPUS_CAPABILITY_TELEGRAM_SELECT = TELEGRAM_ACTION_CAPABILITIES["telegram-select"]
OLYMPUS_CAPABILITY_TELEGRAM_STATUS = TELEGRAM_ACTION_CAPABILITIES["telegram-status"]
OLYMPUS_CAPABILITY_TELEGRAM_CLEAR = TELEGRAM_ACTION_CAPABILITIES["telegram-clear"]
OLYMPUS_CAPABILITY_TELEGRAM_INTAKE = TELEGRAM_ACTION_CAPABILITIES["telegram-intake"]
TELEGRAM_EMERGENCY_ACTIONS = frozenset({
    "telegram-control:interrupt", "telegram-control:cancel",
})
KANBAN_TASK_ACTION_CAPABILITIES = {
    **HERMES_KANBAN_ACTION_CAPABILITIES,
    **TELEGRAM_ACTION_CAPABILITIES,
}
SUBSCRIPTION_REGISTRATION_ACTIONS = frozenset({
    "add_notification_subscription",
})
NOTIFICATION_PRINCIPAL_ACTIONS = frozenset({
    "advance_notification_cursor",
    "claim_notification_delivery", "claim_notification_effect",
    "finish_notification_effect", "remove_notification_subscription",
    "reserve_notification_effect", "rewind_notification_cursor",
})
WORKER_PRINCIPAL_ACTIONS = frozenset({
    "complete", "block", "comment", "heartbeat", "heartbeat_worker",
})
KANBAN_ACTION_PRINCIPAL_KINDS = {
    action: (
        "telegram_user" if action in TELEGRAM_ACTION_CAPABILITIES
        else "kanban_notifier" if action in NOTIFICATION_PRINCIPAL_ACTIONS
        else "kanban_worker" if action in WORKER_PRINCIPAL_ACTIONS
        else "kanban_service_dispatcher"
    )
    for action in KANBAN_TASK_ACTION_CAPABILITIES
}

# DB-enforced write intents.  The canonical verifier authorizes an exact
# action/capability pair; these maps constrain what that permit may physically
# change after it is issued.  A permit for a comment or notification therefore
# cannot be confused for a task-status or run-lifecycle permit even on the same
# connection and revision.
_OLYMPUS_TASK_WRITE_COLUMNS: dict[tuple[str, str], frozenset[str]] = {
    ("create_idempotent", OLYMPUS_CAPABILITY_CREATE): frozenset(),
    ("update_authority_context", OLYMPUS_CAPABILITY_UPDATE): frozenset({
        "olympus_context", "claim_expires",
    }),
    ("release_blocked_task", OLYMPUS_CAPABILITY_RELEASE): frozenset({
        "status", "claim_lock", "claim_expires", "worker_pid",
    }),
    ("assign", OLYMPUS_CAPABILITY_ASSIGN): frozenset({
        "assignee", "consecutive_failures", "last_failure_error",
    }),
    ("link", OLYMPUS_CAPABILITY_LINK): frozenset({"status"}),
    ("unlink", OLYMPUS_CAPABILITY_LINK): frozenset(),
    ("link_governed_child", OLYMPUS_CAPABILITY_LINK): frozenset(),
    ("unlink_deleted_task", OLYMPUS_CAPABILITY_LINK): frozenset(),
    ("comment", OLYMPUS_CAPABILITY_COMMENT): frozenset(),
    ("add_attachment", OLYMPUS_CAPABILITY_ATTACHMENT): frozenset(),
    ("delete_attachment", OLYMPUS_CAPABILITY_ATTACHMENT): frozenset(),
    ("promote", OLYMPUS_CAPABILITY_STATUS): frozenset({"status"}),
    ("claim", OLYMPUS_CAPABILITY_CLAIM): frozenset({
        "status", "claim_lock", "claim_expires", "started_at",
        "current_run_id",
    }),
    ("claim_review", OLYMPUS_CAPABILITY_CLAIM): frozenset({
        "status", "claim_lock", "claim_expires", "started_at",
        "current_run_id",
    }),
    ("heartbeat", OLYMPUS_CAPABILITY_HEARTBEAT): frozenset({"claim_expires"}),
    ("extend_stale_claim", OLYMPUS_CAPABILITY_RECOVER): frozenset({
        "claim_expires",
    }),
    ("recover_stale_claim", OLYMPUS_CAPABILITY_RECOVER): frozenset({
        "status", "claim_lock", "claim_expires", "worker_pid",
        "current_run_id",
    }),
    ("reclaim", OLYMPUS_CAPABILITY_RECOVER): frozenset({
        "status", "claim_lock", "claim_expires", "worker_pid",
        "current_run_id", "consecutive_failures", "last_failure_error",
    }),
    ("complete", OLYMPUS_CAPABILITY_COMPLETE): frozenset({
        "status", "result", "completed_at", "claim_lock", "claim_expires",
        "worker_pid", "current_run_id", "consecutive_failures",
        "last_failure_error",
    }),
    ("edit_result", OLYMPUS_CAPABILITY_EDIT): frozenset({"result"}),
    ("block", OLYMPUS_CAPABILITY_STATUS): frozenset({
        "status", "claim_lock", "claim_expires", "worker_pid",
        "current_run_id",
    }),
    ("unblock", OLYMPUS_CAPABILITY_STATUS): frozenset({
        "status", "current_run_id", "consecutive_failures",
        "last_failure_error",
    }),
    ("specify_triage", OLYMPUS_CAPABILITY_TRIAGE): frozenset({
        "title", "body", "assignee", "status",
    }),
    ("decompose_triage", OLYMPUS_CAPABILITY_TRIAGE): frozenset({
        "assignee", "status",
    }),
    ("archive", OLYMPUS_CAPABILITY_ARCHIVE): frozenset({
        "status", "claim_lock", "claim_expires", "worker_pid",
        "current_run_id",
    }),
    ("delete_archived", OLYMPUS_CAPABILITY_DELETE): frozenset(),
    ("delete", OLYMPUS_CAPABILITY_DELETE): frozenset(),
    ("edit_task", OLYMPUS_CAPABILITY_EDIT): frozenset({
        "title", "body", "priority",
    }),
    ("set_direct_status", OLYMPUS_CAPABILITY_STATUS): frozenset({
        "status", "claim_lock", "claim_expires", "worker_pid",
        "current_run_id", "completed_at",
    }),
    ("demote_parent_reopened", OLYMPUS_CAPABILITY_STATUS): frozenset({"status"}),
    ("set_workspace", OLYMPUS_CAPABILITY_WORKSPACE): frozenset({"workspace_path"}),
    ("schedule", OLYMPUS_CAPABILITY_STATUS): frozenset({
        "status", "claim_lock", "claim_expires", "worker_pid",
    }),
    ("heartbeat_worker", OLYMPUS_CAPABILITY_HEARTBEAT): frozenset({
        "last_heartbeat_at",
    }),
    ("enforce_max_runtime", OLYMPUS_CAPABILITY_RECOVER): frozenset({
        "status", "claim_lock", "claim_expires", "worker_pid",
        "current_run_id",
    }),
    ("recover_stale_running", OLYMPUS_CAPABILITY_RECOVER): frozenset({
        "status", "claim_lock", "claim_expires", "worker_pid",
        "current_run_id",
    }),
    ("recover_crashed_worker", OLYMPUS_CAPABILITY_RECOVER): frozenset({
        "status", "claim_lock", "claim_expires", "worker_pid",
        "current_run_id", "last_failure_error",
    }),
    ("record_failure", OLYMPUS_CAPABILITY_RECOVER): frozenset({
        "status", "claim_lock", "claim_expires", "worker_pid",
        "current_run_id", "consecutive_failures", "last_failure_error",
    }),
    ("set_worker_pid", OLYMPUS_CAPABILITY_CLAIM): frozenset({"worker_pid"}),
    ("release_unspawned_claim", OLYMPUS_CAPABILITY_RECOVER): frozenset({
        "status", "claim_lock", "claim_expires", "worker_pid",
        "current_run_id",
    }),
    ("mark_worker_workspace_ready", OLYMPUS_CAPABILITY_WORKSPACE): frozenset(),
    ("mark_worker_starting", OLYMPUS_CAPABILITY_CLAIM): frozenset(),
    ("register_worker_process", OLYMPUS_CAPABILITY_CLAIM): frozenset({"worker_pid"}),
    ("fail_worker_launch", OLYMPUS_CAPABILITY_RECOVER): frozenset({
        "status", "claim_lock", "claim_expires", "worker_pid",
        "current_run_id", "consecutive_failures", "last_failure_error",
    }),
    ("stage_worker_termination", OLYMPUS_CAPABILITY_RECOVER): frozenset({
        "status", "claim_lock", "claim_expires", "worker_pid",
        "current_run_id",
    }),
    ("settle_worker_termination", OLYMPUS_CAPABILITY_RECOVER): frozenset(),
    ("execute_worker_termination_effect", OLYMPUS_CAPABILITY_RECOVER): frozenset(),
    ("reconcile_worker_run", OLYMPUS_CAPABILITY_RECOVER): frozenset({
        "status", "claim_lock", "claim_expires", "worker_pid",
        "current_run_id",
    }),
    ("add_notification_subscription", OLYMPUS_CAPABILITY_NOTIFY): frozenset(),
    ("remove_notification_subscription", OLYMPUS_CAPABILITY_NOTIFY): frozenset(),
    ("claim_notification_delivery", OLYMPUS_CAPABILITY_NOTIFY): frozenset(),
    ("advance_notification_cursor", OLYMPUS_CAPABILITY_NOTIFY): frozenset(),
    ("rewind_notification_cursor", OLYMPUS_CAPABILITY_NOTIFY): frozenset(),
    ("reserve_notification_effect", OLYMPUS_CAPABILITY_NOTIFY): frozenset(),
    ("claim_notification_effect", OLYMPUS_CAPABILITY_NOTIFY): frozenset(),
    ("finish_notification_effect", OLYMPUS_CAPABILITY_NOTIFY): frozenset(),
    ("reconcile_effect_journal", OLYMPUS_CAPABILITY_RECOVER): frozenset(),
    # Telegram permits authorize only immutable intake/control journals or a
    # read-only verification.  They never authorize task-column mutation;
    # the trusted service dispatcher obtains a separate action-specific
    # permit for any resulting Kanban state transition.
    **{
        (action, capability): frozenset()
        for action, capability in TELEGRAM_ACTION_CAPABILITIES.items()
    },
}

_OLYMPUS_RUN_WRITE_COLUMNS: dict[tuple[str, str], frozenset[str]] = {
    ("update_authority_context", OLYMPUS_CAPABILITY_UPDATE): frozenset({"claim_expires"}),
    ("claim", OLYMPUS_CAPABILITY_CLAIM): frozenset({"__insert__", "status", "outcome", "summary", "ended_at", "claim_lock", "claim_expires", "worker_pid"}),
    ("claim_review", OLYMPUS_CAPABILITY_CLAIM): frozenset({"__insert__"}),
    ("heartbeat", OLYMPUS_CAPABILITY_HEARTBEAT): frozenset({"claim_expires"}),
    ("extend_stale_claim", OLYMPUS_CAPABILITY_RECOVER): frozenset({"claim_expires"}),
    ("recover_stale_claim", OLYMPUS_CAPABILITY_RECOVER): frozenset({"status", "outcome", "summary", "metadata", "error", "ended_at", "claim_lock", "claim_expires", "worker_pid"}),
    ("reclaim", OLYMPUS_CAPABILITY_RECOVER): frozenset({"status", "outcome", "summary", "metadata", "error", "ended_at", "claim_lock", "claim_expires", "worker_pid"}),
    ("complete", OLYMPUS_CAPABILITY_COMPLETE): frozenset({"__insert__", "status", "outcome", "summary", "metadata", "error", "ended_at", "claim_lock", "claim_expires", "worker_pid"}),
    ("edit_result", OLYMPUS_CAPABILITY_EDIT): frozenset({"__insert__", "summary", "metadata"}),
    ("block", OLYMPUS_CAPABILITY_STATUS): frozenset({"__insert__", "status", "outcome", "summary", "metadata", "error", "ended_at", "claim_lock", "claim_expires", "worker_pid"}),
    ("unblock", OLYMPUS_CAPABILITY_STATUS): frozenset({"status", "outcome", "summary", "ended_at", "claim_lock", "claim_expires", "worker_pid"}),
    ("archive", OLYMPUS_CAPABILITY_ARCHIVE): frozenset({"status", "outcome", "summary", "ended_at", "claim_lock", "claim_expires", "worker_pid"}),
    ("set_direct_status", OLYMPUS_CAPABILITY_STATUS): frozenset({"__insert__", "status", "outcome", "summary", "metadata", "error", "ended_at", "claim_lock", "claim_expires", "worker_pid"}),
    ("heartbeat_worker", OLYMPUS_CAPABILITY_HEARTBEAT): frozenset({"last_heartbeat_at"}),
    ("enforce_max_runtime", OLYMPUS_CAPABILITY_RECOVER): frozenset({"status", "outcome", "summary", "metadata", "error", "ended_at", "claim_lock", "claim_expires", "worker_pid"}),
    ("recover_stale_running", OLYMPUS_CAPABILITY_RECOVER): frozenset({"status", "outcome", "summary", "metadata", "error", "ended_at", "claim_lock", "claim_expires", "worker_pid"}),
    ("recover_crashed_worker", OLYMPUS_CAPABILITY_RECOVER): frozenset({"status", "outcome", "summary", "metadata", "error", "ended_at", "claim_lock", "claim_expires", "worker_pid"}),
    ("record_failure", OLYMPUS_CAPABILITY_RECOVER): frozenset({"status", "outcome", "summary", "metadata", "error", "ended_at", "claim_lock", "claim_expires", "worker_pid"}),
    ("set_worker_pid", OLYMPUS_CAPABILITY_CLAIM): frozenset({"worker_pid"}),
    ("release_unspawned_claim", OLYMPUS_CAPABILITY_RECOVER): frozenset({"status", "outcome", "summary", "metadata", "error", "ended_at", "claim_lock", "claim_expires", "worker_pid"}),
    ("mark_worker_workspace_ready", OLYMPUS_CAPABILITY_WORKSPACE): frozenset({"process_state", "workspace_snapshot"}),
    ("mark_worker_starting", OLYMPUS_CAPABILITY_CLAIM): frozenset({"process_state"}),
    ("register_worker_process", OLYMPUS_CAPABILITY_CLAIM): frozenset({"process_state", "worker_pid", "worker_host_id", "worker_boot_id", "worker_start_token", "worker_registered_at", "dispatcher_instance_id"}),
    ("fail_worker_launch", OLYMPUS_CAPABILITY_RECOVER): frozenset({"process_state", "status", "outcome", "error", "ended_at", "claim_lock", "claim_expires"}),
    ("stage_worker_termination", OLYMPUS_CAPABILITY_RECOVER): frozenset({"process_state", "status", "outcome", "error", "ended_at", "claim_lock", "claim_expires"}),
    ("settle_worker_termination", OLYMPUS_CAPABILITY_RECOVER): frozenset({"process_state"}),
    ("execute_worker_termination_effect", OLYMPUS_CAPABILITY_RECOVER): frozenset({"process_state"}),
    ("reconcile_worker_run", OLYMPUS_CAPABILITY_RECOVER): frozenset({"process_state", "status", "outcome", "error", "ended_at", "claim_lock", "claim_expires"}),
    ("reconcile_effect_journal", OLYMPUS_CAPABILITY_RECOVER): frozenset({"process_state"}),
}

_OLYMPUS_FORCE_TOUCH_ACTIONS = frozenset({
    "link", "unlink", "link_governed_child", "unlink_deleted_task",
    "comment", "add_attachment", "delete_attachment",
    "add_notification_subscription", "remove_notification_subscription",
    "claim_notification_delivery", "advance_notification_cursor",
    "rewind_notification_cursor",
})

_OLYMPUS_TASK_MUTABLE_COLUMNS = (
    "title", "body", "assignee", "status", "priority", "created_by",
    "created_at", "started_at", "completed_at", "workspace_kind",
    "workspace_path", "branch_name", "claim_lock", "claim_expires", "tenant",
    "result", "idempotency_key", "consecutive_failures", "worker_pid",
    "last_failure_error", "max_runtime_seconds", "last_heartbeat_at",
    "current_run_id", "workflow_template_id", "current_step_key", "skills",
    "model_override", "max_retries", "goal_mode", "goal_max_turns",
    "session_id", "olympus_context",
)

_OLYMPUS_RUN_MUTABLE_COLUMNS = (
    "profile", "step_key", "status", "claim_lock", "claim_expires",
    "worker_pid", "max_runtime_seconds", "last_heartbeat_at", "started_at",
    "ended_at", "outcome", "summary", "metadata", "error", "process_state",
    "launch_token", "workspace_snapshot", "auth_root_id",
    "auth_root_revision", "verification_id", "worker_host_id",
    "worker_boot_id", "worker_start_token", "worker_registered_at",
    "dispatcher_instance_id",
)

_OLYMPUS_PROTECTED_AUDIT_KINDS = frozenset({
    "claim_rejected", "heartbeat_rejected", "completion_rejected",
    "promotion_rejected", "authority_contained",
    "completion_blocked_hallucination", "spawn_rejected",
})

OLYMPUS_RUNTIME_IDENTITY_KEYS = frozenset({
    "board_id", "worker_task_id", "worker_task_revision", "worker_status",
    "worker_assignee", "run_id", "run_subject_revision", "run_status",
    "claim_lock", "claim_expires", "process_state", "host_id", "boot_id",
    "pid", "start_token", "dispatcher_instance_id",
})
OLYMPUS_NOTIFIER_IDENTITY_KEYS = frozenset({
    "board_id", "task_id", "task_record_revision", "platform", "chat_id",
    "thread_id", "user_id", "notifier_profile", "created_at", "last_event_id",
    "source_event_id", "effect_id", "effect_state", "gateway_host_id",
    "gateway_boot_id", "gateway_pid", "gateway_start_token",
})

_AUTHORITY_KEYS = frozenset({
    "authority_id", "status", "scope", "capabilities", "revision", "source",
    "expires_at",
})
_LEASE_KEYS = frozenset({
    "lease_id", "status", "mission_id", "agent_id", "holder", "repository",
    "branch", "worktree", "revision", "source", "expires_at",
})
_KANBAN_SUBJECT_KEYS = frozenset({
    "subject_type", "subject_id", "subject_revision", "subject_status",
    "authority", "lease", "goal_id", "program_id", "milestone_id",
    "mission_id", "workstream_id", "assignee",
})
_AUTHORITY_REQUEST_KEYS = frozenset({
    "schema_version", "profile", "target", "authorization_root", "action",
    "capability", "actor", "principal", "operation_id", "request_id",
})
_AUTHORITY_RESULT_KEYS = frozenset({
    "schema_version", "verification_id", "decision", "current", "verified_at",
    "valid_until", "verified_principal", "verified_actor", "request_id",
    "request", "target_verification", "authorization_root_verification",
})
_SUBJECT_PROOF_KEYS = frozenset({
    "authority_current", "containment_target", "subject",
})
_PRINCIPAL_COMMON_KEYS = frozenset({
    "kind", "principal_type", "principal_id", "principal_source",
})
_PRINCIPAL_KEYS_BY_KIND = {
    "kanban_service_dispatcher": _PRINCIPAL_COMMON_KEYS | {
        "board_id", "dispatcher_instance_id",
    },
    "kanban_worker": _PRINCIPAL_COMMON_KEYS | {
        "board_id", "worker_task_id", "worker_task_revision", "worker_status",
        "worker_assignee", "run_id", "run_subject_revision", "run_status",
        "claim_lock", "claim_expires", "process_state", "host_id", "boot_id",
        "pid", "start_token", "dispatcher_instance_id",
    },
    "kanban_notifier": _PRINCIPAL_COMMON_KEYS | {
        "board_id", "task_id", "task_record_revision", "platform", "chat_id",
        "thread_id", "user_id", "notifier_profile", "created_at",
        "last_event_id", "source_event_id", "effect_id", "effect_state",
        "gateway_host_id", "gateway_boot_id", "gateway_pid",
        "gateway_start_token",
    },
    "telegram_user": _PRINCIPAL_COMMON_KEYS | {
        "bot_id", "profile", "chat_id", "thread_id", "user_id",
    },
}
_NOTIFICATION_SUBSCRIPTION_OPERATION_KEYS = frozenset({
    "schema_version", "action", "board_id", "task_id",
    "task_record_revision", "platform", "chat_id", "thread_id", "user_id",
    "notifier_profile",
})
NOTIFICATION_SUBSCRIPTION_OPERATION_SCHEMA = (
    "kanban-notification-subscription-operation/1"
)
NOTIFICATION_EFFECT_RESERVATION_SCHEMA = (
    "kanban-notification-effect-reservation/1"
)
NOTIFICATION_EFFECT_TRANSITION_SCHEMA = (
    "kanban-notification-effect-transition/1"
)
NOTIFIER_MUTATION_WRITE_SCHEMA = "kanban-notifier-mutation-write/1"
WORKER_REGISTRATION_WRITE_SCHEMA = "kanban-worker-registration-write/1"
CREATE_RECEIPT_WRITE_SCHEMA = "kanban-create-receipt-write/1"
RELEASE_RECEIPT_WRITE_SCHEMA = "kanban-release-receipt-write/1"
TELEGRAM_DELIVERY_WRITE_SCHEMA = "kanban-telegram-delivery-write/1"
TELEGRAM_CONTROL_WRITE_SCHEMA = "kanban-telegram-control-write/1"
_OLYMPUS_RELEASE_RECEIPT_KEYS = frozenset({
    "schema_version", "operation_id", "task_id", "previous_status", "status",
    "previous_revision", "record_revision", "verification_id", "request_id",
    "actor", "principal", "authority_id", "authority_revision",
    "authority_source", "lease_id", "lease_revision", "lease_source",
    "created_at",
})
_NOTIFICATION_EFFECT_RESERVATION_KEYS = frozenset({
    "schema_version", "action", "task_id", "task_record_revision",
    "effect_kind", "operation_id", "event_id", "destination_key", "part",
    "source_identity", "payload", "payload_sha256", "target_post_revision",
})
_NOTIFICATION_EFFECT_TRANSITION_KEYS = frozenset({
    "schema_version", "action", "task_id", "task_record_revision",
    "effect_row_id", "effect_kind", "operation_id", "event_id",
    "destination_key", "old_state", "new_state", "error", "updated_at",
    "applied_at",
})
_WORKER_REGISTRATION_WRITE_KEYS = frozenset({
    "schema_version", "action", "task_id", "task_record_revision",
    "dispatcher_instance_id",
})
_TELEGRAM_DELIVERY_WRITE_KEYS = frozenset({
    "schema_version", "action", "task_id", "task_record_revision",
    "delivery_key", "authorization_task_id", "authorization_task_revision",
    "created_task_id", "payload", "payload_sha256", "created_at",
})
_TELEGRAM_CONTROL_WRITE_KEYS = frozenset({
    "schema_version", "action", "task_id", "task_record_revision",
    "operation_id", "authorization_task_id", "authorization_task_revision",
    "source_identity", "request_payload", "payload_sha256",
    "result_status", "effect_operation_id", "created_at",
})
_EXACT_MUTATION_BINDING_ACTIONS = frozenset({
    "reserve_notification_effect", "claim_notification_effect",
    "finish_notification_effect", "register_worker_process",
    "telegram-intake", "telegram-control:pause", "telegram-control:resume",
    "telegram-control:interrupt", "telegram-control:cancel",
})


class AuthorityContractError(ValueError):
    """Stable fail-closed error for malformed frozen v3 wire data."""


@dataclass(frozen=True)
class OlympusMutationAuth:
    """Trusted, process-local authority-verification binding.

    Generic CLI, dashboard, and tool payloads never construct this object.
    The embedding composition root supplies the callable and authenticated
    principal; every other value remains an input that the canonical issuer
    must independently verify.
    """

    verifier: AuthorityVerifier
    principal_type: str
    principal_id: str
    principal_source: str
    actor: Optional[str] = None
    operation_id: Optional[str] = None
    source_identity: Optional[dict[str, Any]] = None
    target_identity: Optional[dict[str, Any]] = None
    runtime_identity: Optional[dict[str, Any]] = None
    notifier_identity: Optional[dict[str, Any]] = None


@dataclass(frozen=True)
class ProcessIdentity:
    """Exact OS process instance; PID alone is never a safe identity."""

    host_id: str
    boot_id: str
    pid: int
    start_token: str


@dataclass(frozen=True)
class OlympusWorkerAuthSession:
    """Trusted process-local binding installed after worker registration."""

    verifier: AuthorityVerifier
    board_id: str
    task_id: str
    run_id: int
    run_subject_revision: int
    claim_lock: str
    assignee: str
    process_identity: ProcessIdentity
    dispatcher_instance_id: str

    def issue(
        self,
        conn: sqlite3.Connection,
        action: str,
        capability: str,
    ) -> OlympusMutationAuth:
        runtime = olympus_worker_runtime_snapshot(
            conn,
            worker_task_id=self.task_id,
            run_id=self.run_id,
            claim_lock=self.claim_lock,
        )
        observed_process = ProcessIdentity(
            host_id=runtime["host_id"],
            boot_id=runtime["boot_id"],
            pid=runtime["pid"],
            start_token=runtime["start_token"],
        )
        if (
            runtime["board_id"] != self.board_id
            or runtime["worker_task_id"] != self.task_id
            or runtime["run_id"] != self.run_id
            or runtime["run_subject_revision"] != self.run_subject_revision
            or runtime["worker_assignee"] != self.assignee
            or observed_process != self.process_identity
            or runtime["dispatcher_instance_id"] != self.dispatcher_instance_id
        ):
            raise OlympusContextError(
                "olympus_runtime_identity_conflict",
                "worker authorization session no longer matches canonical state",
            )
        process_instance = (
            f"{observed_process.host_id}:{observed_process.boot_id}:"
            f"{observed_process.pid}:{observed_process.start_token}"
        )
        return OlympusMutationAuth(
            verifier=self.verifier,
            principal_type="kanban_worker",
            principal_id=(
                f"kanban-worker:{self.board_id}:{self.task_id}:"
                f"{self.run_id}:{process_instance}"
            ),
            principal_source=f"kanban-dispatcher:{self.dispatcher_instance_id}",
            actor=self.assignee,
            operation_id=(
                f"worker:{self.run_id}:{action}:{runtime['worker_task_revision']}"
            ),
            runtime_identity=runtime,
        )


_OLYMPUS_MUTATION_AUTH: ContextVar[Optional[OlympusMutationAuth]] = ContextVar(
    "olympus_mutation_auth", default=None
)
_OLYMPUS_WORKER_AUTH_SESSION: ContextVar[
    Optional[OlympusWorkerAuthSession]
] = ContextVar("olympus_worker_auth_session", default=None)


def install_olympus_worker_auth_session(
    session: OlympusWorkerAuthSession,
):
    """Install a trusted worker session and return its ContextVar token."""
    return _OLYMPUS_WORKER_AUTH_SESSION.set(session)


def current_olympus_worker_auth_session() -> Optional[OlympusWorkerAuthSession]:
    return _OLYMPUS_WORKER_AUTH_SESSION.get()


def reset_olympus_worker_auth_session(token) -> None:
    _OLYMPUS_WORKER_AUTH_SESSION.reset(token)


def install_olympus_worker_auth_session_from_env(
    conn: sqlite3.Connection,
    verifier: AuthorityVerifier,
):
    """Bind the current registered worker process at a trusted composition root.

    Environment values locate the dispatcher reservation; none of them grant
    authority.  The live DB row, exact OS process instance, and canonical
    verifier are rechecked before the process-local session is installed.
    """
    if not callable(verifier):
        raise TypeError("verifier must be callable")
    task_id = os.environ.get("HERMES_KANBAN_TASK", "").strip()
    claim_lock = os.environ.get("HERMES_KANBAN_CLAIM_LOCK", "").strip()
    dispatcher = os.environ.get(
        "HERMES_KANBAN_DISPATCHER_INSTANCE", ""
    ).strip()
    try:
        run_id = int(os.environ.get("HERMES_KANBAN_RUN_ID", ""))
    except (TypeError, ValueError) as exc:
        raise OlympusContextError(
            "olympus_runtime_identity_invalid",
            "registered worker run id is missing",
        ) from exc
    runtime = olympus_worker_runtime_snapshot(
        conn,
        worker_task_id=task_id,
        run_id=run_id,
        claim_lock=claim_lock,
    )
    process_identity = read_process_identity(os.getpid())
    if (
        process_identity is None
        or process_identity.host_id != runtime["host_id"]
        or process_identity.boot_id != runtime["boot_id"]
        or process_identity.pid != runtime["pid"]
        or process_identity.start_token != runtime["start_token"]
        or dispatcher != runtime["dispatcher_instance_id"]
    ):
        raise OlympusContextError(
            "olympus_runtime_process_mismatch",
            "current process does not match the registered worker",
        )
    session = OlympusWorkerAuthSession(
        verifier=verifier,
        board_id=runtime["board_id"],
        task_id=runtime["worker_task_id"],
        run_id=runtime["run_id"],
        run_subject_revision=runtime["run_subject_revision"],
        claim_lock=runtime["claim_lock"],
        assignee=runtime["worker_assignee"],
        process_identity=process_identity,
        dispatcher_instance_id=dispatcher,
    )
    return install_olympus_worker_auth_session(session)


class OlympusContextError(ValueError):
    """A fail-closed Olympus context validation error.

    ``reason`` is stable and intentionally safe for task events and operator
    diagnostics.  The raw context is never included in the exception or event.
    """

    def __init__(self, reason: str, message: str):
        self.reason = reason
        super().__init__(message)


def _olympus_required_text(
    value: Any,
    *,
    reason: str,
    field_name: str,
) -> str:
    if not isinstance(value, str) or not value.strip():
        raise OlympusContextError(reason, f"{field_name} is required")
    cleaned = value.strip()
    if len(cleaned) > 512:
        raise OlympusContextError(
            "olympus_context_invalid", f"{field_name} exceeds 512 characters"
        )
    return cleaned


def _olympus_required_epoch(
    value: Any,
    *,
    reason: str,
    field_name: str,
) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
        raise OlympusContextError(reason, f"{field_name} must be a positive epoch")
    return int(value)


def _olympus_required_revision(
    value: Any,
    *,
    field_name: str,
) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 1:
        raise OlympusContextError(
            "olympus_context_invalid", f"{field_name} must be a positive integer"
        )
    return int(value)


def _olympus_required_text_list(
    value: Any,
    *,
    field_name: str,
) -> list[str]:
    if not isinstance(value, (list, tuple)) or not value:
        raise OlympusContextError(
            "olympus_context_invalid", f"{field_name} must be a non-empty list"
        )
    result: list[str] = []
    seen: set[str] = set()
    for item in value:
        cleaned = _olympus_required_text(
            item,
            reason="olympus_context_invalid",
            field_name=f"{field_name}[]",
        )
        if cleaned not in seen:
            seen.add(cleaned)
            result.append(cleaned)
    return result


def _reject_unknown_olympus_keys(
    value: dict[str, Any], *, allowed: set[str], field_name: str
) -> None:
    unknown = sorted(set(value) - allowed)
    if unknown:
        raise OlympusContextError(
            "olympus_context_invalid",
            f"{field_name} contains unknown field(s): {', '.join(unknown)}",
        )


def normalize_olympus_context(context: Any) -> dict[str, Any]:
    """Validate and canonicalize the versioned Olympus task context.

    This is deliberately a reference contract, not a second authority or lease
    engine.  Olympus owns issuance and revocation; Hermes persists the explicit
    current references and independently refuses claim/start when they are
    absent, foreign, revoked, or expired.
    """
    if not isinstance(context, dict):
        raise OlympusContextError(
            "olympus_context_invalid", "olympus_context must be an object"
        )
    if context.get("schema_version") != OLYMPUS_CONTEXT_VERSION:
        raise OlympusContextError(
            "olympus_context_invalid",
            f"olympus_context.schema_version must be {OLYMPUS_CONTEXT_VERSION}",
        )
    _reject_unknown_olympus_keys(
        context, allowed=OLYMPUS_CONTEXT_KEYS, field_name="olympus_context"
    )

    normalized: dict[str, Any] = {"schema_version": OLYMPUS_CONTEXT_VERSION}
    for key in (
        "goal_id",
        "program_id",
        "milestone_id",
        "mission_id",
        "workstream_id",
    ):
        normalized[key] = _olympus_required_text(
            context.get(key),
            reason=f"olympus_{key}_missing",
            field_name=f"olympus_context.{key}",
        )

    authority = context.get("authority")
    if not isinstance(authority, dict):
        raise OlympusContextError(
            "olympus_authority_missing", "olympus_context.authority is required"
        )
    _reject_unknown_olympus_keys(
        authority,
        allowed=OLYMPUS_AUTHORITY_KEYS,
        field_name="olympus_context.authority",
    )
    authority_status = _olympus_required_text(
        authority.get("status"),
        reason="olympus_authority_status_missing",
        field_name="olympus_context.authority.status",
    ).upper()
    if authority_status not in VALID_OLYMPUS_AUTHORITY_STATUSES:
        raise OlympusContextError(
            "olympus_authority_status_invalid",
            "olympus_context.authority.status is not recognized",
        )
    normalized["authority"] = {
        "authority_id": _olympus_required_text(
            authority.get("authority_id"),
            reason="olympus_authority_missing",
            field_name="olympus_context.authority.authority_id",
        ),
        "status": authority_status,
        "scope": _olympus_required_text_list(
            authority.get("scope"),
            field_name="olympus_context.authority.scope",
        ),
        "capabilities": _olympus_required_text_list(
            authority.get("capabilities"),
            field_name="olympus_context.authority.capabilities",
        ),
        "revision": _olympus_required_revision(
            authority.get("revision"),
            field_name="olympus_context.authority.revision",
        ),
        "source": _olympus_required_text(
            authority.get("source"),
            reason="olympus_authority_source_missing",
            field_name="olympus_context.authority.source",
        ),
        "expires_at": _olympus_required_epoch(
            authority.get("expires_at"),
            reason="olympus_authority_expiry_missing",
            field_name="olympus_context.authority.expires_at",
        ),
    }

    lease = context.get("lease")
    if not isinstance(lease, dict):
        raise OlympusContextError(
            "olympus_lease_missing", "olympus_context.lease is required"
        )
    _reject_unknown_olympus_keys(
        lease,
        allowed=OLYMPUS_LEASE_KEYS,
        field_name="olympus_context.lease",
    )
    lease_status = _olympus_required_text(
        lease.get("status"),
        reason="olympus_lease_status_missing",
        field_name="olympus_context.lease.status",
    ).upper()
    if lease_status not in VALID_OLYMPUS_LEASE_STATUSES:
        raise OlympusContextError(
            "olympus_lease_status_invalid",
            "olympus_context.lease.status is not recognized",
        )
    normalized["lease"] = {
        "lease_id": _olympus_required_text(
            lease.get("lease_id"),
            reason="olympus_lease_missing",
            field_name="olympus_context.lease.lease_id",
        ),
        "mission_id": _olympus_required_text(
            lease.get("mission_id"),
            reason="olympus_lease_mission_missing",
            field_name="olympus_context.lease.mission_id",
        ),
        "holder": _olympus_required_text(
            lease.get("holder"),
            reason="olympus_lease_holder_missing",
            field_name="olympus_context.lease.holder",
        ),
        "status": lease_status,
        "agent_id": _olympus_required_text(
            lease.get("agent_id"),
            reason="olympus_lease_agent_missing",
            field_name="olympus_context.lease.agent_id",
        ),
        "repository": _olympus_required_text(
            lease.get("repository"),
            reason="olympus_lease_repository_missing",
            field_name="olympus_context.lease.repository",
        ),
        "branch": _olympus_required_text(
            lease.get("branch"),
            reason="olympus_lease_branch_missing",
            field_name="olympus_context.lease.branch",
        ),
        "worktree": _olympus_required_text(
            lease.get("worktree"),
            reason="olympus_lease_worktree_missing",
            field_name="olympus_context.lease.worktree",
        ),
        "revision": _olympus_required_revision(
            lease.get("revision"),
            field_name="olympus_context.lease.revision",
        ),
        "source": _olympus_required_text(
            lease.get("source"),
            reason="olympus_lease_source_missing",
            field_name="olympus_context.lease.source",
        ),
        "expires_at": _olympus_required_epoch(
            lease.get("expires_at"),
            reason="olympus_lease_expiry_missing",
            field_name="olympus_context.lease.expires_at",
        ),
    }

    risk = _olympus_required_text(
        context.get("risk"),
        reason="olympus_risk_missing",
        field_name="olympus_context.risk",
    ).lower()
    if risk not in VALID_OLYMPUS_RISKS:
        raise OlympusContextError(
            "olympus_risk_invalid",
            f"olympus_context.risk must be one of {sorted(VALID_OLYMPUS_RISKS)}",
        )
    normalized["risk"] = risk
    normalized["agent_id"] = _olympus_required_text(
        context.get("agent_id"),
        reason="olympus_agent_missing",
        field_name="olympus_context.agent_id",
    )
    normalized["review_status"] = _olympus_required_text(
        context.get("review_status"),
        reason="olympus_review_status_missing",
        field_name="olympus_context.review_status",
    )

    evidence_refs = context.get("evidence_refs")
    if not isinstance(evidence_refs, (list, tuple)):
        raise OlympusContextError(
            "olympus_evidence_refs_missing",
            "olympus_context.evidence_refs must be a list",
        )
    normalized_refs: list[str] = []
    seen_refs: set[str] = set()
    for value in evidence_refs:
        ref = _olympus_required_text(
            value,
            reason="olympus_evidence_ref_invalid",
            field_name="olympus_context.evidence_refs[]",
        )
        if ref not in seen_refs:
            seen_refs.add(ref)
            normalized_refs.append(ref)
        if len(normalized_refs) > 100:
            raise OlympusContextError(
                "olympus_evidence_ref_invalid",
                "olympus_context.evidence_refs exceeds 100 entries",
            )
    normalized["evidence_refs"] = normalized_refs
    return normalized


def _serialize_olympus_context(context: Any) -> str:
    return json.dumps(
        normalize_olympus_context(context),
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )


def _decode_olympus_context(raw: Any) -> Optional[dict[str, Any]]:
    if raw is None:
        return None
    try:
        parsed = json.loads(raw) if isinstance(raw, str) else raw
        return parsed if isinstance(parsed, dict) else {"_invalid": True}
    except Exception:
        return {"_invalid": True}


def _olympus_trace(context: dict[str, Any]) -> dict[str, Any]:
    """Return the bounded, non-secret subset safe for events and summaries."""
    return {
        "goal_id": context["goal_id"],
        "program_id": context["program_id"],
        "milestone_id": context["milestone_id"],
        "mission_id": context["mission_id"],
        "workstream_id": context["workstream_id"],
        "authority_ref": context["authority"]["authority_id"],
        "authority_revision": context["authority"]["revision"],
        "authority_source": context["authority"]["source"],
        "lease_ref": context["lease"]["lease_id"],
        "lease_revision": context["lease"]["revision"],
        "lease_source": context["lease"]["source"],
        "lease_holder": context["lease"]["holder"],
        "risk": context["risk"],
        "agent_id": context["agent_id"],
        "review_status": context["review_status"],
        "evidence_refs": list(context["evidence_refs"]),
    }


def _require_current_olympus_context(
    raw: Any,
    *,
    assignee: Optional[str],
    now: Optional[int] = None,
) -> Optional[dict[str, Any]]:
    """Return a current context, or raise with a stable denial reason.

    ``None`` is the explicit legacy compatibility path: ordinary Kanban tasks
    continue to claim exactly as before.  Once a row carries Olympus context,
    malformed or stale state never falls back to that legacy path.
    """
    if raw is None:
        return None
    try:
        parsed = json.loads(raw) if isinstance(raw, str) else raw
    except Exception as exc:
        raise OlympusContextError(
            "olympus_context_invalid", "olympus_context is not valid JSON"
        ) from exc
    context = normalize_olympus_context(parsed)
    current = int(time.time()) if now is None else int(now)
    mission_id = context["mission_id"]
    authority = context["authority"]
    lease = context["lease"]
    if authority["status"] != "ACTIVE":
        raise OlympusContextError(
            "olympus_authority_revoked", "authority reference is revoked"
        )
    if authority["expires_at"] <= current:
        raise OlympusContextError(
            "olympus_authority_expired", "authority reference is expired"
        )
    if lease["mission_id"] != mission_id:
        raise OlympusContextError(
            "olympus_lease_foreign_mission",
            "lease mission does not match task mission",
        )
    if lease["status"] != "ACTIVE":
        raise OlympusContextError("olympus_lease_revoked", "lease is revoked")
    if lease["expires_at"] <= current:
        raise OlympusContextError("olympus_lease_expired", "lease is expired")
    if assignee is None or not (
        context["agent_id"] == lease["agent_id"] == lease["holder"] == assignee
    ):
        raise OlympusContextError(
            "olympus_agent_mismatch",
            "lease holder, lease agent, context agent, and task assignee must match exactly",
        )
    return context


def _strict_text(value: Any, field_name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise AuthorityContractError(f"{field_name} must be a non-empty string")
    cleaned = value.strip()
    if len(cleaned) > 2048:
        raise AuthorityContractError(f"{field_name} is too long")
    return cleaned


def _strict_string(
    value: Any, field_name: str, *, allow_empty: bool = False,
) -> str:
    if not isinstance(value, str) or (not allow_empty and not value.strip()):
        expected = "a string" if allow_empty else "a non-empty string"
        raise AuthorityContractError(f"{field_name} must be {expected}")
    if len(value) > 2048:
        raise AuthorityContractError(f"{field_name} is too long")
    return value if allow_empty else value.strip()


def _strict_optional_string(value: Any, field_name: str) -> Optional[str]:
    if value is None:
        return None
    return _strict_string(value, field_name, allow_empty=True)


def _strict_int(value: Any, field_name: str, *, minimum: int) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < minimum:
        raise AuthorityContractError(
            f"{field_name} must be an integer >= {minimum}, not a boolean"
        )
    return value


def _strict_time(value: Any, field_name: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise AuthorityContractError(f"{field_name} must be a finite timestamp")
    normalized = float(value)
    if not math.isfinite(normalized) or normalized <= 0:
        raise AuthorityContractError(
            f"{field_name} must be a positive finite timestamp"
        )
    return normalized


def _strict_text_list(value: Any, field_name: str) -> list[str]:
    if not isinstance(value, list) or not value:
        raise AuthorityContractError(f"{field_name} must be a non-empty list")
    cleaned = [_strict_text(item, f"{field_name}[]") for item in value]
    if len(set(cleaned)) != len(cleaned):
        raise AuthorityContractError(f"{field_name} contains duplicate values")
    return sorted(cleaned)


def _require_exact_keys(
    value: Any, expected: frozenset[str], field_name: str,
) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise AuthorityContractError(f"{field_name} must be an object")
    actual = set(value)
    if actual != expected:
        missing = sorted(expected - actual)
        unknown = sorted(repr(item) for item in actual - expected)
        raise AuthorityContractError(
            f"{field_name} fields are not exact; missing={missing}, unknown={unknown}"
        )
    return value


def _normalize_v3_authority(
    value: Any, *, field_name: str, now: Optional[float], require_current: bool,
) -> dict[str, Any]:
    raw = _require_exact_keys(value, _AUTHORITY_KEYS, field_name)
    status = _strict_text(raw["status"], f"{field_name}.status")
    if status not in VALID_OLYMPUS_AUTHORITY_STATUSES:
        raise AuthorityContractError(f"{field_name}.status is not recognized")
    expiry = _strict_time(raw["expires_at"], f"{field_name}.expires_at")
    if require_current and status != "ACTIVE":
        raise AuthorityContractError(f"{field_name} must be ACTIVE")
    if require_current and now is not None and expiry <= now:
        raise AuthorityContractError(f"{field_name} is expired")
    return {
        "authority_id": _strict_text(
            raw["authority_id"], f"{field_name}.authority_id"
        ),
        "status": status,
        "scope": _strict_text_list(raw["scope"], f"{field_name}.scope"),
        "capabilities": _strict_text_list(
            raw["capabilities"], f"{field_name}.capabilities"
        ),
        "revision": _strict_int(
            raw["revision"], f"{field_name}.revision", minimum=1
        ),
        "source": _strict_text(raw["source"], f"{field_name}.source"),
        "expires_at": expiry,
    }


def _normalize_v3_lease(
    value: Any, *, field_name: str, now: Optional[float], require_current: bool,
) -> dict[str, Any]:
    raw = _require_exact_keys(value, _LEASE_KEYS, field_name)
    status = _strict_text(raw["status"], f"{field_name}.status")
    if status not in VALID_OLYMPUS_LEASE_STATUSES:
        raise AuthorityContractError(f"{field_name}.status is not recognized")
    expiry = _strict_time(raw["expires_at"], f"{field_name}.expires_at")
    if require_current and status != "ACTIVE":
        raise AuthorityContractError(f"{field_name} must be ACTIVE")
    if require_current and now is not None and expiry <= now:
        raise AuthorityContractError(f"{field_name} is expired")
    return {
        "lease_id": _strict_text(raw["lease_id"], f"{field_name}.lease_id"),
        "status": status,
        "mission_id": _strict_text(raw["mission_id"], f"{field_name}.mission_id"),
        "agent_id": _strict_text(raw["agent_id"], f"{field_name}.agent_id"),
        "holder": _strict_text(raw["holder"], f"{field_name}.holder"),
        "repository": _strict_text(raw["repository"], f"{field_name}.repository"),
        "branch": _strict_text(raw["branch"], f"{field_name}.branch"),
        "worktree": _strict_text(raw["worktree"], f"{field_name}.worktree"),
        "revision": _strict_int(
            raw["revision"], f"{field_name}.revision", minimum=1
        ),
        "source": _strict_text(raw["source"], f"{field_name}.source"),
        "expires_at": expiry,
    }


def _normalize_kanban_subject(
    value: Any, *, field_name: str, now: float, require_current: bool,
) -> dict[str, Any]:
    raw = _require_exact_keys(value, _KANBAN_SUBJECT_KEYS, field_name)
    if _strict_text(raw["subject_type"], f"{field_name}.subject_type") \
            != "kanban_task":
        raise AuthorityContractError(
            f"{field_name}.subject_type does not match profile"
        )
    status = _strict_text(raw["subject_status"], f"{field_name}.subject_status")
    if status not in VALID_STATUSES:
        raise AuthorityContractError(f"{field_name}.subject_status is not recognized")
    authority = _normalize_v3_authority(
        raw["authority"], field_name=f"{field_name}.authority", now=now,
        require_current=require_current,
    )
    lease = _normalize_v3_lease(
        raw["lease"], field_name=f"{field_name}.lease", now=now,
        require_current=require_current,
    )
    result = {
        "subject_type": "kanban_task",
        "subject_id": _strict_text(raw["subject_id"], f"{field_name}.subject_id"),
        "subject_revision": _strict_int(
            raw["subject_revision"], f"{field_name}.subject_revision", minimum=0
        ),
        "subject_status": status,
        "authority": authority,
        "lease": lease,
    }
    for key in (
        "goal_id", "program_id", "milestone_id", "mission_id", "workstream_id",
    ):
        result[key] = _strict_text(raw[key], f"{field_name}.{key}")
    if lease["mission_id"] != result["mission_id"]:
        raise AuthorityContractError(
            f"{field_name}.lease.mission_id does not match subject"
        )
    assignee = _strict_text(raw["assignee"], f"{field_name}.assignee")
    if not (assignee == lease["agent_id"] == lease["holder"]):
        raise AuthorityContractError(
            f"{field_name} assignee, lease agent, and lease holder must match"
        )
    result["assignee"] = assignee
    return result


def _request_digest(request_without_id: dict[str, Any]) -> str:
    encoded = json.dumps(
        request_without_id, sort_keys=True, separators=(",", ":"), allow_nan=False,
    ).encode()
    return hashlib.sha256(encoded).hexdigest()


def _wire_equal(left: Any, right: Any) -> bool:
    return json.dumps(
        left, sort_keys=True, separators=(",", ":"), allow_nan=False,
    ) == json.dumps(
        right, sort_keys=True, separators=(",", ":"), allow_nan=False,
    )


def _scope_allows(authority: dict[str, Any], subject: dict[str, Any]) -> bool:
    subject_scopes = {
        subject[key]
        for key in (
            "subject_id", "goal_id", "program_id", "milestone_id", "mission_id",
        )
    }
    return "*" in authority["scope"] or bool(
        subject_scopes.intersection(authority["scope"])
    )


def _normalize_notification_subscription_operation_binding(
    value: Any,
    *,
    target: Optional[dict[str, Any]] = None,
    board_id: Optional[str] = None,
) -> dict[str, Any]:
    """Canonicalize the v4 add-only notification destination binding."""
    raw = _require_exact_keys(
        value,
        _NOTIFICATION_SUBSCRIPTION_OPERATION_KEYS,
        "principal.operation_binding",
    )
    if raw["schema_version"] != NOTIFICATION_SUBSCRIPTION_OPERATION_SCHEMA:
        raise AuthorityContractError(
            "principal.operation_binding schema is not notification subscription v1"
        )
    if raw["action"] != "add_notification_subscription":
        raise AuthorityContractError(
            "principal.operation_binding action is not add_notification_subscription"
        )
    normalized = {
        "schema_version": NOTIFICATION_SUBSCRIPTION_OPERATION_SCHEMA,
        "action": "add_notification_subscription",
        "board_id": _strict_text(
            raw["board_id"], "principal.operation_binding.board_id"
        ),
        "task_id": _strict_text(
            raw["task_id"], "principal.operation_binding.task_id"
        ),
        "task_record_revision": _strict_int(
            raw["task_record_revision"],
            "principal.operation_binding.task_record_revision",
            minimum=1,
        ),
        "platform": _strict_text(
            raw["platform"], "principal.operation_binding.platform"
        ),
        "chat_id": _strict_text(
            raw["chat_id"], "principal.operation_binding.chat_id"
        ),
        "thread_id": _strict_string(
            raw["thread_id"],
            "principal.operation_binding.thread_id",
            allow_empty=True,
        ),
        "user_id": _strict_optional_string(
            raw["user_id"], "principal.operation_binding.user_id"
        ),
        "notifier_profile": _strict_optional_string(
            raw["notifier_profile"],
            "principal.operation_binding.notifier_profile",
        ),
    }
    if board_id is not None and normalized["board_id"] != board_id:
        raise AuthorityContractError(
            "subscription operation board does not match service dispatcher"
        )
    if target is not None and (
        normalized["task_id"] != target["subject_id"]
        or normalized["task_record_revision"] != target["subject_revision"]
    ):
        raise AuthorityContractError(
            "subscription operation task or revision does not match target"
        )
    return normalized


def notification_subscription_operation_id(operation_binding: Any) -> str:
    """Return the canonical idempotency identity for one exact subscription."""
    normalized = _normalize_notification_subscription_operation_binding(
        operation_binding
    )
    digest = hashlib.sha256(json.dumps(
        normalized,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")).hexdigest()
    return f"kanban-notification-subscription:add:{digest}"


def _canonical_json_text(value: Any, field_name: str) -> str:
    if not isinstance(value, str) or not value:
        raise AuthorityContractError(f"{field_name} must be canonical JSON text")
    try:
        decoded = json.loads(value)
        canonical = json.dumps(
            decoded, sort_keys=True, separators=(",", ":"),
            ensure_ascii=False, allow_nan=False,
        )
    except (TypeError, ValueError, json.JSONDecodeError) as exc:
        raise AuthorityContractError(
            f"{field_name} must be canonical JSON text"
        ) from exc
    if canonical != value:
        raise AuthorityContractError(f"{field_name} is not canonical JSON")
    return canonical


def _normalize_exact_mutation_binding(
    value: Any, *, action: str, task_id: str, task_record_revision: int,
) -> dict[str, Any]:
    """Canonicalize one process-local exact SQL write intent."""
    if action == "reserve_notification_effect":
        raw = _require_exact_keys(
            value, _NOTIFICATION_EFFECT_RESERVATION_KEYS, "mutation_binding",
        )
        if (
            raw["schema_version"] != NOTIFICATION_EFFECT_RESERVATION_SCHEMA
            or raw["action"] != action
        ):
            raise AuthorityContractError(
                "notification effect reservation binding has the wrong schema/action"
            )
        source = _canonical_json_text(
            raw["source_identity"], "mutation_binding.source_identity"
        )
        payload = _canonical_json_text(
            raw["payload"], "mutation_binding.payload"
        )
        digest = _strict_text(
            raw["payload_sha256"], "mutation_binding.payload_sha256"
        )
        if (
            not re.fullmatch(r"[0-9a-f]{64}", digest)
            or hashlib.sha256(payload.encode("utf-8")).hexdigest() != digest
        ):
            raise AuthorityContractError(
                "mutation_binding.payload_sha256 does not match canonical payload"
            )
        normalized = {
            "schema_version": NOTIFICATION_EFFECT_RESERVATION_SCHEMA,
            "action": action,
            "task_id": _strict_text(raw["task_id"], "mutation_binding.task_id"),
            "task_record_revision": _strict_int(
                raw["task_record_revision"],
                "mutation_binding.task_record_revision", minimum=1,
            ),
            "effect_kind": _strict_text(
                raw["effect_kind"], "mutation_binding.effect_kind"
            ),
            "operation_id": _strict_text(
                raw["operation_id"], "mutation_binding.operation_id"
            ),
            "event_id": _strict_int(
                raw["event_id"], "mutation_binding.event_id", minimum=1,
            ),
            "destination_key": _strict_text(
                raw["destination_key"], "mutation_binding.destination_key"
            ),
            "part": _strict_text(raw["part"], "mutation_binding.part"),
            "source_identity": source,
            "payload": payload,
            "payload_sha256": digest,
            "target_post_revision": _strict_int(
                raw["target_post_revision"],
                "mutation_binding.target_post_revision", minimum=1,
            ),
        }
        if normalized["effect_kind"] not in {"notify_text", "notify_artifact"}:
            raise AuthorityContractError(
                "mutation_binding.effect_kind is not a notification effect"
            )
    elif action in {"claim_notification_effect", "finish_notification_effect"}:
        raw = _require_exact_keys(
            value, _NOTIFICATION_EFFECT_TRANSITION_KEYS, "mutation_binding",
        )
        if (
            raw["schema_version"] != NOTIFICATION_EFFECT_TRANSITION_SCHEMA
            or raw["action"] != action
        ):
            raise AuthorityContractError(
                "notification effect transition binding has the wrong schema/action"
            )
        error = raw["error"]
        if error is not None and not isinstance(error, str):
            raise AuthorityContractError("mutation_binding.error must be text or null")
        applied_at = raw["applied_at"]
        if applied_at is not None:
            applied_at = _strict_int(
                applied_at, "mutation_binding.applied_at", minimum=0,
            )
        normalized = {
            "schema_version": NOTIFICATION_EFFECT_TRANSITION_SCHEMA,
            "action": action,
            "task_id": _strict_text(raw["task_id"], "mutation_binding.task_id"),
            "task_record_revision": _strict_int(
                raw["task_record_revision"],
                "mutation_binding.task_record_revision", minimum=1,
            ),
            "effect_row_id": _strict_int(
                raw["effect_row_id"], "mutation_binding.effect_row_id", minimum=1,
            ),
            "effect_kind": _strict_text(
                raw["effect_kind"], "mutation_binding.effect_kind"
            ),
            "operation_id": _strict_text(
                raw["operation_id"], "mutation_binding.operation_id"
            ),
            "event_id": _strict_int(
                raw["event_id"], "mutation_binding.event_id", minimum=1,
            ),
            "destination_key": _strict_text(
                raw["destination_key"], "mutation_binding.destination_key"
            ),
            "old_state": _strict_text(
                raw["old_state"], "mutation_binding.old_state"
            ),
            "new_state": _strict_text(
                raw["new_state"], "mutation_binding.new_state"
            ),
            "error": error,
            "updated_at": _strict_int(
                raw["updated_at"], "mutation_binding.updated_at", minimum=0,
            ),
            "applied_at": applied_at,
        }
        if normalized["effect_kind"] not in {"notify_text", "notify_artifact"}:
            raise AuthorityContractError(
                "mutation_binding.effect_kind is not a notification effect"
            )
    elif action == "register_worker_process":
        raw = _require_exact_keys(
            value, _WORKER_REGISTRATION_WRITE_KEYS, "mutation_binding",
        )
        if (
            raw["schema_version"] != WORKER_REGISTRATION_WRITE_SCHEMA
            or raw["action"] != action
        ):
            raise AuthorityContractError(
                "worker registration binding has the wrong schema/action"
            )
        normalized = {
            "schema_version": WORKER_REGISTRATION_WRITE_SCHEMA,
            "action": action,
            "task_id": _strict_text(raw["task_id"], "mutation_binding.task_id"),
            "task_record_revision": _strict_int(
                raw["task_record_revision"],
                "mutation_binding.task_record_revision", minimum=1,
            ),
            "dispatcher_instance_id": _strict_text(
                raw["dispatcher_instance_id"],
                "mutation_binding.dispatcher_instance_id",
            ),
        }
    elif action == "telegram-intake":
        raw = _require_exact_keys(
            value, _TELEGRAM_DELIVERY_WRITE_KEYS, "mutation_binding",
        )
        if (
            raw["schema_version"] != TELEGRAM_DELIVERY_WRITE_SCHEMA
            or raw["action"] != action
        ):
            raise AuthorityContractError(
                "Telegram delivery binding has the wrong schema/action"
            )
        payload = _canonical_json_text(
            raw["payload"], "mutation_binding.payload"
        )
        digest = _strict_text(
            raw["payload_sha256"], "mutation_binding.payload_sha256"
        )
        if (
            not re.fullmatch(r"[0-9a-f]{64}", digest)
            or hashlib.sha256(payload.encode("utf-8")).hexdigest() != digest
        ):
            raise AuthorityContractError(
                "mutation_binding.payload_sha256 does not match canonical payload"
            )
        normalized = {
            "schema_version": TELEGRAM_DELIVERY_WRITE_SCHEMA,
            "action": action,
            "task_id": _strict_text(raw["task_id"], "mutation_binding.task_id"),
            "task_record_revision": _strict_int(
                raw["task_record_revision"],
                "mutation_binding.task_record_revision", minimum=1,
            ),
            "delivery_key": _strict_text(
                raw["delivery_key"], "mutation_binding.delivery_key"
            ),
            "authorization_task_id": _strict_text(
                raw["authorization_task_id"],
                "mutation_binding.authorization_task_id",
            ),
            "authorization_task_revision": _strict_int(
                raw["authorization_task_revision"],
                "mutation_binding.authorization_task_revision", minimum=1,
            ),
            "created_task_id": _strict_text(
                raw["created_task_id"], "mutation_binding.created_task_id"
            ),
            "payload": payload,
            "payload_sha256": digest,
            "created_at": _strict_int(
                raw["created_at"], "mutation_binding.created_at", minimum=0,
            ),
        }
        if normalized["authorization_task_id"] != normalized["task_id"] or (
            normalized["authorization_task_revision"]
            != normalized["task_record_revision"]
        ):
            raise AuthorityContractError(
                "Telegram delivery authorization root is not the exact target"
            )
    elif action.startswith("telegram-control:"):
        raw = _require_exact_keys(
            value, _TELEGRAM_CONTROL_WRITE_KEYS, "mutation_binding",
        )
        if (
            raw["schema_version"] != TELEGRAM_CONTROL_WRITE_SCHEMA
            or raw["action"] != action
        ):
            raise AuthorityContractError(
                "Telegram control binding has the wrong schema/action"
            )
        source = _canonical_json_text(
            raw["source_identity"], "mutation_binding.source_identity"
        )
        payload = _canonical_json_text(
            raw["request_payload"], "mutation_binding.request_payload"
        )
        digest = _strict_text(
            raw["payload_sha256"], "mutation_binding.payload_sha256"
        )
        if (
            not re.fullmatch(r"[0-9a-f]{64}", digest)
            or hashlib.sha256(payload.encode("utf-8")).hexdigest() != digest
        ):
            raise AuthorityContractError(
                "mutation_binding.payload_sha256 does not match canonical payload"
            )
        result_status = raw["result_status"]
        if result_status is not None:
            result_status = _strict_text(
                result_status, "mutation_binding.result_status"
            )
        effect_operation_id = raw["effect_operation_id"]
        if effect_operation_id is not None:
            effect_operation_id = _strict_text(
                effect_operation_id, "mutation_binding.effect_operation_id"
            )
        normalized = {
            "schema_version": TELEGRAM_CONTROL_WRITE_SCHEMA,
            "action": action,
            "task_id": _strict_text(raw["task_id"], "mutation_binding.task_id"),
            "task_record_revision": _strict_int(
                raw["task_record_revision"],
                "mutation_binding.task_record_revision", minimum=1,
            ),
            "operation_id": _strict_text(
                raw["operation_id"], "mutation_binding.operation_id"
            ),
            "authorization_task_id": _strict_text(
                raw["authorization_task_id"],
                "mutation_binding.authorization_task_id",
            ),
            "authorization_task_revision": _strict_int(
                raw["authorization_task_revision"],
                "mutation_binding.authorization_task_revision", minimum=1,
            ),
            "source_identity": source,
            "request_payload": payload,
            "payload_sha256": digest,
            "result_status": result_status,
            "effect_operation_id": effect_operation_id,
            "created_at": _strict_int(
                raw["created_at"], "mutation_binding.created_at", minimum=0,
            ),
        }
    else:
        raise AuthorityContractError(
            f"action {action!r} does not accept an exact mutation binding"
        )
    if (
        normalized["task_id"] != task_id
        or normalized["task_record_revision"] != task_record_revision
    ):
        raise AuthorityContractError(
            "mutation binding task or revision does not match the exact target"
        )
    if (
        action == "reserve_notification_effect"
        and normalized["target_post_revision"] != task_record_revision
    ):
        raise AuthorityContractError(
            "notification effect target_post_revision is not exact"
        )
    return normalized


def _normalize_kanban_principal(
    value: Any, *, action: str, target: dict[str, Any], now: float,
) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise AuthorityContractError("principal must be an object")
    kind = _strict_text(value.get("kind"), "principal.kind")
    expected_keys = _PRINCIPAL_KEYS_BY_KIND.get(kind)
    if expected_keys is None:
        raise AuthorityContractError(f"principal.kind {kind!r} is not recognized")
    if (
        kind == "kanban_service_dispatcher"
        and action in SUBSCRIPTION_REGISTRATION_ACTIONS
    ):
        expected_keys = expected_keys | {"operation_binding"}
    raw = _require_exact_keys(value, expected_keys, "principal")
    required_kind = KANBAN_ACTION_PRINCIPAL_KINDS.get(action)
    if required_kind is None:
        raise AuthorityContractError(f"action {action!r} has no principal-kind binding")
    if kind != required_kind:
        raise AuthorityContractError(
            f"action {action!r} requires principal kind {required_kind!r}"
        )
    result = {
        "kind": kind,
        "principal_type": _strict_text(raw["principal_type"], "principal.principal_type"),
        "principal_id": _strict_text(raw["principal_id"], "principal.principal_id"),
        "principal_source": _strict_text(
            raw["principal_source"], "principal.principal_source"
        ),
    }
    if kind == "kanban_service_dispatcher":
        board_id = _strict_text(raw["board_id"], "principal.board_id")
        dispatcher = _strict_text(
            raw["dispatcher_instance_id"], "principal.dispatcher_instance_id"
        )
        expected = (
            "service",
            f"kanban-service-dispatcher:{board_id}:{dispatcher}",
            f"kanban-dispatcher:{board_id}:{dispatcher}",
        )
        if (
            result["principal_type"], result["principal_id"],
            result["principal_source"],
        ) != expected:
            raise AuthorityContractError(
                "service-dispatcher principal triple is not canonically derived"
            )
        result.update({"board_id": board_id, "dispatcher_instance_id": dispatcher})
        if action in SUBSCRIPTION_REGISTRATION_ACTIONS:
            result["operation_binding"] = (
                _normalize_notification_subscription_operation_binding(
                    raw["operation_binding"],
                    target=target,
                    board_id=board_id,
                )
            )
    elif kind == "kanban_worker":
        result.update({
            "board_id": _strict_text(raw["board_id"], "principal.board_id"),
            "worker_task_id": _strict_text(
                raw["worker_task_id"], "principal.worker_task_id"
            ),
            "worker_task_revision": _strict_int(
                raw["worker_task_revision"], "principal.worker_task_revision", minimum=1
            ),
            "worker_status": _strict_text(
                raw["worker_status"], "principal.worker_status"
            ),
            "worker_assignee": _strict_text(
                raw["worker_assignee"], "principal.worker_assignee"
            ),
            "run_id": _strict_int(raw["run_id"], "principal.run_id", minimum=1),
            "run_subject_revision": _strict_int(
                raw["run_subject_revision"], "principal.run_subject_revision", minimum=1
            ),
            "run_status": _strict_text(raw["run_status"], "principal.run_status"),
            "claim_lock": _strict_text(raw["claim_lock"], "principal.claim_lock"),
            "claim_expires": _strict_int(
                raw["claim_expires"], "principal.claim_expires", minimum=1
            ),
            "process_state": _strict_text(
                raw["process_state"], "principal.process_state"
            ),
            "host_id": _strict_text(raw["host_id"], "principal.host_id"),
            "boot_id": _strict_text(raw["boot_id"], "principal.boot_id"),
            "pid": _strict_int(raw["pid"], "principal.pid", minimum=1),
            "start_token": _strict_text(raw["start_token"], "principal.start_token"),
            "dispatcher_instance_id": _strict_text(
                raw["dispatcher_instance_id"], "principal.dispatcher_instance_id"
            ),
        })
        if result["worker_task_id"] != target["subject_id"] \
                or result["worker_task_revision"] != target["subject_revision"] \
                or result["worker_status"] != target["subject_status"] \
                or result["worker_assignee"] != target["assignee"]:
            raise AuthorityContractError(
                "worker task identity must match the exact target revision"
            )
        if result["run_subject_revision"] > result["worker_task_revision"]:
            raise AuthorityContractError(
                "worker run origin may not be newer than the exact task revision"
            )
        if result["claim_expires"] <= now:
            raise AuthorityContractError("worker claim is expired")
        expected = (
            "kanban_worker",
            f"kanban-worker:{result['board_id']}:{result['worker_task_id']}:"
            f"{result['run_id']}:{result['host_id']}:{result['boot_id']}:"
            f"{result['pid']}:{result['start_token']}",
            f"kanban-dispatcher:{result['dispatcher_instance_id']}",
        )
        if (
            result["principal_type"], result["principal_id"],
            result["principal_source"],
        ) != expected:
            raise AuthorityContractError(
                "worker principal triple is not canonically derived"
            )
    elif kind == "kanban_notifier":
        result.update({
            "board_id": _strict_text(raw["board_id"], "principal.board_id"),
            "task_id": _strict_text(raw["task_id"], "principal.task_id"),
            "task_record_revision": _strict_int(
                raw["task_record_revision"], "principal.task_record_revision", minimum=1
            ),
            "platform": _strict_text(raw["platform"], "principal.platform"),
            "chat_id": _strict_text(raw["chat_id"], "principal.chat_id"),
            "thread_id": _strict_optional_string(
                raw["thread_id"], "principal.thread_id"
            ),
            "user_id": _strict_optional_string(raw["user_id"], "principal.user_id"),
            "notifier_profile": _strict_optional_string(
                raw["notifier_profile"], "principal.notifier_profile"
            ),
            "created_at": _strict_int(raw["created_at"], "principal.created_at", minimum=0),
            "last_event_id": _strict_int(
                raw["last_event_id"], "principal.last_event_id", minimum=0
            ),
            "source_event_id": _strict_int(
                raw["source_event_id"], "principal.source_event_id", minimum=0
            ),
            "effect_id": _strict_text(raw["effect_id"], "principal.effect_id"),
            "effect_state": _strict_text(raw["effect_state"], "principal.effect_state"),
            "gateway_host_id": _strict_text(
                raw["gateway_host_id"], "principal.gateway_host_id"
            ),
            "gateway_boot_id": _strict_text(
                raw["gateway_boot_id"], "principal.gateway_boot_id"
            ),
            "gateway_pid": _strict_int(
                raw["gateway_pid"], "principal.gateway_pid", minimum=1
            ),
            "gateway_start_token": _strict_text(
                raw["gateway_start_token"], "principal.gateway_start_token"
            ),
        })
        if result["task_id"] != target["subject_id"] \
                or result["task_record_revision"] != target["subject_revision"]:
            raise AuthorityContractError(
                "notifier task identity must match the exact target revision"
            )
        destination = ":".join((
            result["platform"], result["chat_id"], result["thread_id"] or "",
            result["user_id"] or "",
        ))
        expected = (
            "kanban_notifier",
            f"kanban-notifier:{result['board_id']}:{result['task_id']}:"
            f"{destination}:{result['effect_id']}",
            f"kanban-gateway:{result['gateway_host_id']}:"
            f"{result['gateway_boot_id']}:{result['gateway_pid']}:"
            f"{result['gateway_start_token']}",
        )
        if (
            result["principal_type"], result["principal_id"],
            result["principal_source"],
        ) != expected:
            raise AuthorityContractError(
                "notifier principal triple is not canonically derived"
            )
    else:
        result.update({
            "bot_id": _strict_text(raw["bot_id"], "principal.bot_id"),
            "profile": _strict_text(raw["profile"], "principal.profile"),
            "chat_id": _strict_text(raw["chat_id"], "principal.chat_id"),
            "thread_id": _strict_string(
                raw["thread_id"], "principal.thread_id", allow_empty=True
            ),
            "user_id": _strict_text(raw["user_id"], "principal.user_id"),
        })
        expected = (
            "telegram_user",
            f"telegram:{result['bot_id']}:{result['user_id']}",
            f"telegram-bot:{result['bot_id']}:profile:{result['profile']}",
        )
        if (
            result["principal_type"], result["principal_id"],
            result["principal_source"],
        ) != expected:
            raise AuthorityContractError(
                "Telegram principal triple is not canonically derived"
            )
    return result


def _normalize_authority_request_parts(
    *, target: Any, authorization_root: Any, action: Any, capability: Any,
    actor: Any, principal: Any, operation_id: Any, now: float,
) -> dict[str, Any]:
    normalized_action = _strict_text(action, "action")
    normalized_capability = _strict_text(capability, "capability")
    expected_capability = KANBAN_TASK_ACTION_CAPABILITIES.get(normalized_action)
    if expected_capability is None:
        raise AuthorityContractError(
            f"action {normalized_action!r} is not registered for profile 'kanban_task'"
        )
    if normalized_capability != expected_capability:
        raise AuthorityContractError(
            f"action {normalized_action!r} requires capability {expected_capability!r}"
        )
    emergency = normalized_action in TELEGRAM_EMERGENCY_ACTIONS
    normalized_target = _normalize_kanban_subject(
        target, field_name="target", now=now, require_current=not emergency,
    )
    normalized_root = None
    if authorization_root is not None:
        normalized_root = _normalize_kanban_subject(
            authorization_root, field_name="authorization_root", now=now,
            require_current=True,
        )
        for key in (
            "mission_id", "goal_id", "program_id", "milestone_id", "workstream_id",
        ):
            if normalized_root[key] != normalized_target[key]:
                raise AuthorityContractError(
                    f"authorization_root.{key} does not match target"
                )
        if normalized_root["subject_revision"] < 1:
            raise AuthorityContractError(
                "authorization_root must identify an existing subject revision"
            )
    if emergency and normalized_root is None:
        raise AuthorityContractError(
            "emergency containment requires a current authorization_root"
        )
    if normalized_action == "create":
        if normalized_target["subject_revision"] != 0:
            raise AuthorityContractError(
                "create requires absent target subject_revision 0"
            )
    elif normalized_target["subject_revision"] < 1:
        raise AuthorityContractError(
            "non-create operations require an existing target revision"
        )
    for name, subject in (
        ("target", normalized_target), ("authorization_root", normalized_root),
    ):
        if subject is None or (emergency and name == "target"):
            continue
        if normalized_capability not in subject["authority"]["capabilities"]:
            raise AuthorityContractError(f"{name} authority lacks capability")
        if not _scope_allows(subject["authority"], subject):
            raise AuthorityContractError(f"{name} is outside authority scope")
    normalized_actor = _strict_text(actor, "actor")
    actor_subject = normalized_root or normalized_target
    if normalized_actor != actor_subject["lease"]["holder"]:
        raise AuthorityContractError(
            "actor must match the exact authorizing lease holder"
        )
    normalized_principal = _normalize_kanban_principal(
        principal, action=normalized_action, target=normalized_target, now=now,
    )
    normalized_operation_id = _strict_text(operation_id, "operation_id")
    if normalized_action in SUBSCRIPTION_REGISTRATION_ACTIONS:
        expected_operation_id = notification_subscription_operation_id(
            normalized_principal["operation_binding"]
        )
        if normalized_operation_id != expected_operation_id:
            raise AuthorityContractError(
                "subscription operation_id is not canonically derived"
            )
    return {
        "schema_version": AUTHORITY_REQUEST_SCHEMA,
        "profile": "kanban_task",
        "target": normalized_target,
        "authorization_root": normalized_root,
        "action": normalized_action,
        "capability": normalized_capability,
        "actor": normalized_actor,
        "principal": normalized_principal,
        "operation_id": normalized_operation_id,
    }


def profile_authority_request(
    *, target: dict[str, Any], action: str, capability: str, actor: str,
    principal_binding: dict[str, Any], operation_id: str,
    authorization_root: Optional[dict[str, Any]] = None,
    now: Optional[float] = None,
) -> dict[str, Any]:
    current = _strict_time(time.time() if now is None else now, "now")
    request = _normalize_authority_request_parts(
        target=target, authorization_root=authorization_root, action=action,
        capability=capability, actor=actor, principal=principal_binding,
        operation_id=operation_id, now=current,
    )
    return {**request, "request_id": f"authority-request:{_request_digest(request)}"}


def validate_authority_request(
    request: Any, *, now: Optional[float] = None,
) -> dict[str, Any]:
    try:
        raw = _require_exact_keys(request, _AUTHORITY_REQUEST_KEYS, "request")
        if raw["schema_version"] != AUTHORITY_REQUEST_SCHEMA:
            raise AuthorityContractError("authority request schema is not v3")
        if raw["profile"] != "kanban_task":
            raise AuthorityContractError("authority request profile is not kanban_task")
        current = _strict_time(time.time() if now is None else now, "now")
        normalized = _normalize_authority_request_parts(
            target=raw["target"], authorization_root=raw["authorization_root"],
            action=raw["action"], capability=raw["capability"], actor=raw["actor"],
            principal=raw["principal"], operation_id=raw["operation_id"], now=current,
        )
        expected_id = f"authority-request:{_request_digest(normalized)}"
        if raw["request_id"] != expected_id:
            raise AuthorityContractError("authority request digest does not match")
        canonical = {**normalized, "request_id": expected_id}
        if not _wire_equal(raw, canonical):
            raise AuthorityContractError("authority request is not canonical")
    except (AuthorityContractError, TypeError, ValueError, OverflowError) as exc:
        return {"valid": False, "reason": str(exc)}
    return {"valid": True, "request": canonical}


def validate_authority_verification(
    request: dict[str, Any], result: Any, *, now: Optional[float] = None,
) -> dict[str, Any]:
    try:
        current = _strict_time(time.time() if now is None else now, "now")
    except Exception as exc:
        return {"valid": False, "reason": f"invalid validation time: {type(exc).__name__}"}
    if not isinstance(result, dict):
        return {
            "valid": False,
            "reason": "canonical authority verifier returned no structured result",
        }
    try:
        detached = json.loads(json.dumps(
            result, sort_keys=True, separators=(",", ":"), allow_nan=False,
        ))
    except Exception as exc:
        return {
            "valid": False,
            "reason": f"authority verification is not detached JSON: {type(exc).__name__}",
        }
    request_check = validate_authority_request(request, now=current)
    if not request_check["valid"]:
        return {"valid": False, "reason": request_check["reason"]}
    canonical_request = request_check["request"]
    contradictory = (
        any(detached.get(key) is False for key in (
            "allowed", "authorized", "granted", "valid",
        ))
        or any(detached.get(key) is True for key in (
            "denied", "revoked", "expired", "stale", "ambiguous", "contradictory",
        ))
        or str(detached.get("status", "")).upper() in {
            "DENY", "DENIED", "REVOKED", "EXPIRED", "STALE", "INVALID",
        }
        or str(detached.get("state", "")).upper() in {
            "DENY", "DENIED", "REVOKED", "EXPIRED", "STALE", "INVALID",
        }
    )
    if contradictory:
        return {"valid": False, "reason": "authority verification is contradictory"}
    try:
        raw = _require_exact_keys(detached, _AUTHORITY_RESULT_KEYS, "verification")
        if raw["schema_version"] != AUTHORITY_VERIFICATION_SCHEMA:
            raise AuthorityContractError("authority verification schema is not v3")
        if raw["decision"] != "ALLOW" or raw["current"] is not True:
            raise AuthorityContractError("authority verification is stale or not ALLOW")
        verification_id = _strict_text(raw["verification_id"], "verification_id")
        verified_at = _strict_time(raw["verified_at"], "verified_at")
        valid_until = _strict_time(raw["valid_until"], "valid_until")
        if not verified_at <= current < valid_until:
            raise AuthorityContractError("authority verification window is not current")
        if valid_until - verified_at > MAX_AUTHORITY_VERIFICATION_TTL:
            raise AuthorityContractError("authority verification TTL exceeds the bound")
        emergency = canonical_request["action"] in TELEGRAM_EMERGENCY_ACTIONS
        subjects = (
            [canonical_request["authorization_root"]]
            if emergency else [canonical_request["target"]]
        )
        if not emergency and canonical_request["authorization_root"] is not None:
            subjects.append(canonical_request["authorization_root"])
        expiries = [
            expiry
            for subject in subjects
            for expiry in (
                subject["authority"]["expires_at"], subject["lease"]["expires_at"],
            )
        ]
        if canonical_request["principal"]["kind"] == "kanban_worker":
            expiries.append(float(canonical_request["principal"]["claim_expires"]))
        if any(expiry <= current for expiry in expiries):
            raise AuthorityContractError(
                "authority or lease expired before verification acceptance"
            )
        if valid_until > min(expiries):
            raise AuthorityContractError(
                "verification validity exceeds authority, lease, or worker claim expiry"
            )
        expected_target_current = not emergency
        expected_target = {
            "authority_current": expected_target_current,
            "containment_target": emergency,
            "subject": canonical_request["target"],
        }
        target_proof = _require_exact_keys(
            raw["target_verification"], _SUBJECT_PROOF_KEYS, "target_verification"
        )
        if target_proof["authority_current"] is not expected_target_current \
                or target_proof["containment_target"] is not emergency:
            raise AuthorityContractError(
                "target verification currentness contradicts the action"
            )
        if not _wire_equal(target_proof["subject"], canonical_request["target"]):
            raise AuthorityContractError(
                "raw target verification subject is not the canonical target"
            )
        normalized_target = _normalize_kanban_subject(
            target_proof["subject"], field_name="target_verification.subject",
            now=current, require_current=expected_target_current,
        )
        if {
            "authority_current": expected_target_current,
            "containment_target": emergency,
            "subject": normalized_target,
        } != expected_target:
            raise AuthorityContractError("target verification is stale or foreign")
        expected_root = canonical_request["authorization_root"]
        root_proof = raw["authorization_root_verification"]
        if expected_root is None:
            if root_proof is not None:
                raise AuthorityContractError("unexpected authorization root verification")
        else:
            proof = _require_exact_keys(
                root_proof, _SUBJECT_PROOF_KEYS, "authorization_root_verification"
            )
            if proof["authority_current"] is not True \
                    or proof["containment_target"] is not False:
                raise AuthorityContractError(
                    "authorization root verification is not current"
                )
            if not _wire_equal(proof["subject"], expected_root):
                raise AuthorityContractError(
                    "raw authorization root subject is not canonical"
                )
            if _normalize_kanban_subject(
                proof["subject"], field_name="authorization_root_verification.subject",
                now=current, require_current=True,
            ) != expected_root:
                raise AuthorityContractError(
                    "authorization root verification is stale or foreign"
                )
        echoed = validate_authority_request(raw["request"], now=current)
        if not echoed["valid"] or echoed["request"] != canonical_request:
            raise AuthorityContractError(
                "authority verification request echo is malformed or foreign"
            )
        if not _wire_equal(raw["verified_principal"], canonical_request["principal"]) \
                or _strict_text(raw["verified_actor"], "verified_actor") \
                != canonical_request["actor"] \
                or raw["request_id"] != canonical_request["request_id"]:
            raise AuthorityContractError(
                "authority verification principal, actor, or request is foreign"
            )
        canonical = {
            "schema_version": AUTHORITY_VERIFICATION_SCHEMA,
            "verification_id": verification_id,
            "decision": "ALLOW",
            "current": True,
            "verified_at": verified_at,
            "valid_until": valid_until,
            "verified_principal": canonical_request["principal"],
            "verified_actor": canonical_request["actor"],
            "request_id": canonical_request["request_id"],
            "request": canonical_request,
            "target_verification": expected_target,
            "authorization_root_verification": (
                None if expected_root is None else {
                    "authority_current": True,
                    "containment_target": False,
                    "subject": expected_root,
                }
            ),
        }
        if not _wire_equal(raw, canonical):
            raise AuthorityContractError(
                "authority verification is not the exact canonical result"
            )
        accepted = json.loads(json.dumps(
            canonical, sort_keys=True, separators=(",", ":"), allow_nan=False,
        ))
    except (AuthorityContractError, TypeError, ValueError, OverflowError) as exc:
        return {"valid": False, "reason": str(exc)}
    return {"valid": True, "verification": accepted}


def _olympus_subject(
    context: dict[str, Any], *, subject_id: str, subject_revision: int,
    subject_status: str, assignee: str,
) -> dict[str, Any]:
    return {
        "subject_type": "kanban_task",
        "subject_id": subject_id,
        "subject_revision": subject_revision,
        "subject_status": subject_status,
        "goal_id": context["goal_id"],
        "program_id": context["program_id"],
        "milestone_id": context["milestone_id"],
        "mission_id": context["mission_id"],
        "workstream_id": context["workstream_id"],
        "assignee": assignee,
        "authority": context["authority"],
        "lease": context["lease"],
    }


def _olympus_principal_binding(
    principal: OlympusMutationAuth, *, board_id: str,
    operation_binding: Optional[dict[str, Any]] = None,
) -> dict[str, Any]:
    bindings = tuple(
        value for value in (
            principal.source_identity, principal.runtime_identity,
            principal.notifier_identity,
        ) if value is not None
    )
    if len(bindings) > 1:
        raise AuthorityContractError(
            "a principal cannot combine Telegram, worker, and notifier bindings"
        )
    common = {
        "principal_type": principal.principal_type,
        "principal_id": principal.principal_id,
        "principal_source": principal.principal_source,
    }
    if principal.runtime_identity is not None:
        return {"kind": "kanban_worker", **common, **principal.runtime_identity}
    if principal.notifier_identity is not None:
        return {"kind": "kanban_notifier", **common, **principal.notifier_identity}
    if principal.source_identity is not None:
        source = _require_exact_keys(
            principal.source_identity,
            frozenset(OLYMPUS_SOURCE_IDENTITY_KEYS),
            "source_identity",
        )
        if source["platform"] != "telegram":
            raise AuthorityContractError(
                "governed Telegram operations require platform=telegram"
            )
        if principal.target_identity is None:
            raise AuthorityContractError(
                "Telegram source and target identity must be supplied together"
            )
        return {
            "kind": "telegram_user", **common,
            "bot_id": source["bot_id"], "profile": source["profile"],
            "chat_id": source["chat_id"],
            "thread_id": source["thread_id"] or "", "user_id": source["user_id"],
        }
    if principal.target_identity is not None:
        raise AuthorityContractError(
            "Telegram source and target identity must be supplied together"
        )
    source_prefix = f"kanban-dispatcher:{board_id}:"
    if not principal.principal_source.startswith(source_prefix):
        raise AuthorityContractError(
            "service dispatcher source is not canonically derived"
        )
    dispatcher = principal.principal_source[len(source_prefix):]
    binding = {
        "kind": "kanban_service_dispatcher", **common,
        "board_id": board_id, "dispatcher_instance_id": dispatcher,
    }
    if operation_binding is not None:
        binding["operation_binding"] = (
            _normalize_notification_subscription_operation_binding(
                operation_binding, board_id=board_id,
            )
        )
    return binding


def _olympus_authority_request(
    context: dict[str, Any], *, subject_id: str, subject_revision: int,
    assignee: str, action: str, capability: str, actor: str,
    principal: OlympusMutationAuth, operation_id: str, expected_status: str,
    board_id: str, authorization_root: Optional[dict[str, Any]] = None,
    operation_binding: Optional[dict[str, Any]] = None,
    now: Optional[float] = None,
) -> dict[str, Any]:
    target = _olympus_subject(
        context, subject_id=subject_id, subject_revision=subject_revision,
        subject_status=expected_status, assignee=assignee,
    )
    root = None
    if authorization_root is not None:
        root = _olympus_subject(
            authorization_root["context"],
            subject_id=authorization_root["id"],
            subject_revision=authorization_root["record_revision"],
            subject_status=authorization_root["status"],
            assignee=authorization_root["assignee"],
        )
    return profile_authority_request(
        target=target, authorization_root=root, action=action,
        capability=capability, actor=actor,
        principal_binding=_olympus_principal_binding(
            principal,
            board_id=board_id,
            operation_binding=operation_binding,
        ),
        operation_id=operation_id, now=now,
    )


def require_olympus_authority_verification(
    context: Any, *, subject_id: str, subject_revision: int, assignee: str,
    action: str, capability: str, actor: str, operation_id: str,
    principal: Optional[OlympusMutationAuth], expected_status: str,
    authorization_root: Optional[dict[str, Any]] = None,
    mutation_target: Optional[dict[str, Any]] = None,
    operation_binding: Optional[dict[str, Any]] = None,
    now: Optional[int] = None, allow_inactive: bool = False,
    board_id: Optional[str] = None,
) -> dict[str, Any]:
    """Require one exact nested v3 request/result with no v1/v2 fallback."""
    del mutation_target  # v3 binds the canonical target directly in the request.
    emergency = action in TELEGRAM_EMERGENCY_ACTIONS
    if allow_inactive and not emergency:
        raise OlympusContextError(
            "olympus_inactive_authority_forbidden",
            "inactive authority is valid only for interrupt/cancel containment",
        )
    if emergency:
        normalized = normalize_olympus_context(context)
        lease = normalized["lease"]
        if lease["mission_id"] != normalized["mission_id"]:
            raise OlympusContextError(
                "olympus_lease_foreign_mission", "lease mission does not match task mission"
            )
        if not (
            normalized["agent_id"] == lease["agent_id"] == lease["holder"] == assignee
        ):
            raise OlympusContextError(
                "olympus_agent_mismatch",
                "lease holder, lease agent, context agent, and task assignee must match exactly",
            )
    else:
        normalized = _require_current_olympus_context(
            context, assignee=assignee, now=now
        )
    if normalized is None:
        raise OlympusContextError(
            "olympus_context_missing", "a governed operation requires Olympus context"
        )
    if principal is None or not callable(principal.verifier):
        raise OlympusContextError(
            "olympus_authority_verification_unavailable",
            "canonical authority verifier is unavailable",
        )
    expected_capability = KANBAN_TASK_ACTION_CAPABILITIES.get(action)
    if expected_capability is None or capability != expected_capability:
        raise OlympusContextError(
            "olympus_action_capability_mismatch",
            "action and capability are not the frozen v3 pair",
        )
    actor_subject = authorization_root or {
        "assignee": assignee, "context": normalized,
    }
    if actor != actor_subject["context"]["lease"]["holder"]:
        raise OlympusContextError(
            "olympus_actor_mismatch", "actor must match the authorizing lease holder"
        )
    authority = normalized["authority"]
    if not emergency and capability not in authority["capabilities"]:
        raise OlympusContextError(
            "olympus_capability_missing", "required canonical capability is absent"
        )
    if not emergency and "*" not in authority["scope"] \
            and not {
                subject_id, normalized["mission_id"], normalized["program_id"],
                normalized["goal_id"], normalized["milestone_id"],
            }.intersection(authority["scope"]):
        raise OlympusContextError(
            "olympus_scope_mismatch", "task mission is outside authority scope"
        )
    current = float(int(time.time()) if now is None else now)
    try:
        request = _olympus_authority_request(
            normalized, subject_id=subject_id, subject_revision=subject_revision,
            assignee=assignee, action=action, capability=capability, actor=actor,
            principal=principal, operation_id=operation_id,
            expected_status=expected_status,
            board_id=board_id or "unbound-board",
            authorization_root=authorization_root, now=current,
            operation_binding=operation_binding,
        )
    except (AuthorityContractError, TypeError, ValueError) as exc:
        raise OlympusContextError(
            "olympus_authority_request_invalid", str(exc)
        ) from exc
    try:
        issuer_request = json.loads(json.dumps(
            request, sort_keys=True, separators=(",", ":"), allow_nan=False,
        ))
        result = principal.verifier(issuer_request)
    except Exception as exc:
        raise OlympusContextError(
            "olympus_authority_verification_failed",
            f"canonical authority verification failed: {type(exc).__name__}",
        ) from exc
    accepted = validate_authority_verification(request, result, now=current)
    if not accepted["valid"]:
        raise OlympusContextError(
            "olympus_authority_verification_denied", accepted["reason"]
        )
    return {
        "request": request,
        "verification": accepted["verification"],
        "context": normalized,
    }


def _require_matching_olympus_run_context(
    raw: Any,
    *,
    task_context: Optional[dict[str, Any]],
    assignee: Optional[str],
    now: int,
    run_subject_revision: Optional[int],
    task_record_revision: int,
) -> Optional[dict[str, Any]]:
    """Validate the immutable attempt snapshot against current task scope."""
    if task_context is None:
        if raw is not None:
            raise OlympusContextError(
                "olympus_run_context_mismatch",
                "legacy task unexpectedly carries a governed run context",
            )
        return None
    run_context = _require_current_olympus_context(
        raw, assignee=assignee, now=now
    )
    if (
        run_subject_revision is None
        or int(run_subject_revision) < 1
        or int(run_subject_revision) > int(task_record_revision)
    ):
        raise OlympusContextError(
            "olympus_run_revision_mismatch",
            "active governed run origin is missing or newer than the task aggregate",
        )
    if run_context is None or any(
        run_context[key] != task_context[key]
        for key in (
            "goal_id",
            "program_id",
            "milestone_id",
            "mission_id",
            "workstream_id",
            "agent_id",
        )
    ) or run_context["authority"] != task_context["authority"] \
            or run_context["lease"] != task_context["lease"]:
        raise OlympusContextError(
            "olympus_run_context_mismatch",
            "active run authority does not match the task mission scope",
        )
    return run_context


def derive_olympus_child_context(
    parent_context: Any,
    *,
    agent_id: str,
    workstream_id: Optional[str] = None,
) -> dict[str, Any]:
    """Derive a governed child-task context without changing authority."""
    context = normalize_olympus_context(parent_context)
    normalized_agent = _olympus_required_text(
        agent_id,
        reason="olympus_agent_missing",
        field_name="agent_id",
    )
    if normalized_agent != context["agent_id"]:
        raise OlympusContextError(
            "olympus_delegation_requires_verification",
            "cross-agent delegation requires a separately verified child authority and lease",
        )
    derived = dict(context)
    derived["authority"] = dict(context["authority"])
    derived["lease"] = dict(context["lease"])
    derived["evidence_refs"] = list(context["evidence_refs"])
    derived["agent_id"] = normalized_agent
    if workstream_id is not None:
        derived["workstream_id"] = _olympus_required_text(
            workstream_id,
            reason="olympus_workstream_id_missing",
            field_name="workstream_id",
        )
    return normalize_olympus_context(derived)

# A running task's claim is valid for 15 minutes by default; after that the
# next dispatcher tick reclaims it. Workers that outlive this window should
# call ``heartbeat_claim(task_id)`` periodically. In practice most kanban
# workloads either finish within 15m, set a longer claim explicitly, or use
# ``HERMES_KANBAN_CLAIM_TTL_SECONDS`` to raise the default claim window for
# long single-call MCP workflows.
DEFAULT_CLAIM_TTL_SECONDS = 15 * 60

# If a worker's PID is still alive but its ``last_heartbeat_at`` is
# older than this when ``release_stale_claims`` runs, treat the worker
# as wedged and reclaim regardless of PID liveness (#29747 gap 3).
# This catches the logic-loop case where the process is technically
# running but not making observable progress.  ``_touch_activity``
# bridges chunk-level liveness into ``last_heartbeat_at`` via #31752,
# so any genuinely active worker keeps its heartbeat fresh as a side
# effect of normal API traffic.
DEFAULT_CLAIM_HEARTBEAT_MAX_STALE_SECONDS = 60 * 60


def _resolve_claim_ttl_seconds(ttl_seconds: Optional[int] = None) -> int:
    """Return the effective claim TTL, honoring the kanban env override.

    Explicit call-site values win. Otherwise a positive integer from
    ``HERMES_KANBAN_CLAIM_TTL_SECONDS`` overrides the built-in default.
    Invalid or non-positive env values fall back silently so existing
    installs keep working.
    """
    if ttl_seconds is not None:
        return max(1, int(ttl_seconds))

    raw = os.environ.get("HERMES_KANBAN_CLAIM_TTL_SECONDS", "").strip()
    if raw:
        try:
            parsed = int(raw)
        except ValueError:
            parsed = 0
        if parsed > 0:
            return parsed

    return DEFAULT_CLAIM_TTL_SECONDS


# Grace period after a task transitions to ``running`` during which
# ``detect_crashed_workers`` skips the ``_pid_alive`` check. Covers the
# fork() → /proc-visibility window where liveness can transiently report
# False for a freshly-spawned worker. The 15-minute claim TTL still
# catches genuinely-crashed workers; this only suppresses false positives
# during the launch window.
DEFAULT_CRASH_GRACE_SECONDS = 30


# Sentinel exit code a kanban worker uses to signal "I bailed because the
# provider rate-limited / exhausted quota, not because the task failed."
# The dispatcher's reap classifier maps this to a ``rate_limited`` exit kind
# so ``detect_crashed_workers`` can release the task back to ``ready``
# WITHOUT counting a failure (the circuit breaker must never trip on a
# transient throttle). 75 == BSD ``EX_TEMPFAIL`` (sysexits.h) — the
# conventional "temporary failure, retry later" code, and well clear of the
# 0/1/2 codes the worker uses for success / generic failure / usage error.
KANBAN_RATE_LIMIT_EXIT_CODE = 75


def _resolve_crash_grace_seconds() -> int:
    """Return the crash-detection grace period in seconds.

    Reads ``HERMES_KANBAN_CRASH_GRACE_SECONDS`` from the environment;
    falls back to ``DEFAULT_CRASH_GRACE_SECONDS`` when absent, empty,
    non-integer, or negative. A value of 0 restores immediate-reclaim
    behaviour (useful for tests).
    """
    raw = os.environ.get("HERMES_KANBAN_CRASH_GRACE_SECONDS", "").strip()
    if raw:
        try:
            parsed = int(raw)
        except ValueError:
            parsed = -1
        if parsed >= 0:
            return parsed
    return DEFAULT_CRASH_GRACE_SECONDS


def _resolve_rate_limit_cooldown_seconds() -> int:
    """Return the rate-limit requeue cooldown in seconds.

    Reads ``HERMES_KANBAN_RATE_LIMIT_COOLDOWN_SECONDS`` from the environment;
    falls back to ``DEFAULT_RATE_LIMIT_COOLDOWN_SECONDS`` when absent, empty,
    non-integer, or negative. A value of 0 disables the cooldown (re-spawn on
    the next tick) — useful for tests that want to assert the task becomes
    spawnable again immediately.
    """
    raw = os.environ.get(
        "HERMES_KANBAN_RATE_LIMIT_COOLDOWN_SECONDS", ""
    ).strip()
    if raw:
        try:
            parsed = int(raw)
        except ValueError:
            parsed = -1
        if parsed >= 0:
            return parsed
    return DEFAULT_RATE_LIMIT_COOLDOWN_SECONDS


# Worker-context caps so build_worker_context() stays bounded on
# pathological boards (retry-heavy tasks, comment storms, giant
# summaries). Values chosen to fit a typical 100k-char LLM prompt with
# plenty of headroom. Each constant is tuned independently so users
# who need to relax one don't have to relax all of them.
_CTX_MAX_PRIOR_ATTEMPTS = 10      # most recent N prior runs shown in full
_CTX_MAX_COMMENTS       = 30      # most recent N comments shown in full
_CTX_MAX_FIELD_BYTES    = 4 * 1024   # 4 KB per summary/error/metadata/result
_CTX_MAX_BODY_BYTES     = 8 * 1024   # 8 KB per task.body (opening post)
_CTX_MAX_COMMENT_BYTES  = 2 * 1024   # 2 KB per comment


# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------

DEFAULT_BOARD = "default"
_CURRENT_BOARD_OVERRIDE: ContextVar[str | None] = ContextVar(
    "hermes_kanban_current_board_override",
    default=None,
)


@contextlib.contextmanager
def scoped_current_board(slug: str):
    """Temporarily pin the active board for the current context only."""
    token: Token[str | None] = _CURRENT_BOARD_OVERRIDE.set(slug)
    try:
        yield
    finally:
        _CURRENT_BOARD_OVERRIDE.reset(token)

# Slug validator: lowercase alphanumerics, digits, hyphens; 1–64 chars.
# Strict enough to stop traversal (`..`) and embedded path separators, loose
# enough that kebab-case names like ``atm10-server`` or ``hermes-agent``
# pass without fuss. Board names with display formatting (spaces, emoji)
# live in ``board.json``; the slug is just the directory name.
_BOARD_SLUG_RE = re.compile(r"^[a-z0-9][a-z0-9\-_]{0,63}$")


def _normalize_board_slug(slug: Optional[str]) -> Optional[str]:
    """Lowercase + strip a slug; validate; return ``None`` for empty."""
    if slug is None:
        return None
    s = str(slug).strip().lower()
    if not s:
        return None
    if not _BOARD_SLUG_RE.match(s):
        raise ValueError(
            f"invalid board slug {slug!r}: must be 1-64 chars, lowercase "
            f"alphanumerics / hyphens / underscores, not starting with '-' or '_'"
        )
    return s


def kanban_home() -> Path:
    """Return the shared Hermes root that anchors the kanban board.

    Resolution order:

    1. ``HERMES_KANBAN_HOME`` env var when set and non-empty (explicit
       override for tests and unusual deployments).
    2. ``get_default_hermes_root()``, which already returns ``<root>``
       when ``HERMES_HOME`` is ``<root>/profiles/<name>``, and returns
       ``HERMES_HOME`` directly for Docker / custom deployments.

    The kanban board is shared across profiles **by design** (see the
    module docstring). Resolving the kanban paths through the active
    profile's ``HERMES_HOME`` would silently fork the board per profile,
    which breaks the dispatcher / worker handoff.
    """
    override = os.environ.get("HERMES_KANBAN_HOME", "").strip()
    if override:
        return Path(override).expanduser()
    from hermes_constants import get_default_hermes_root
    return get_default_hermes_root()


def boards_root() -> Path:
    """Return ``<root>/kanban/boards`` — the parent of non-default board dirs.

    ``default`` is intentionally NOT under this directory — its DB lives at
    ``<root>/kanban.db`` for back-compat with pre-boards installs. This
    function returns the directory where *additional* named boards live,
    used by :func:`list_boards` to enumerate them.
    """
    return kanban_home() / "kanban" / "boards"


def current_board_path() -> Path:
    """Return the path to ``<root>/kanban/current``.

    One-line text file written by ``hermes kanban boards switch <slug>``
    to persist the user's board selection across CLI invocations. Absent
    by default (meaning: active board is ``default``).
    """
    return kanban_home() / "kanban" / "current"


def get_current_board() -> str:
    """Return the active board slug, honouring the resolution chain.

    Order (highest precedence first):

    1. ``HERMES_KANBAN_BOARD`` env var (set by the dispatcher on worker
       spawn, or manually for ad-hoc overrides).
    2. ``<root>/kanban/current`` on disk (set by ``hermes kanban boards
       switch``), but only when that board still exists.
    3. ``DEFAULT_BOARD`` (``"default"``).

    A malformed or stale slug at any step falls through to the next layer
    with a best-effort warning — the dispatcher must never crash because a
    user hand-edited a file or removed a board directory.
    """
    scoped = (_CURRENT_BOARD_OVERRIDE.get() or "").strip()
    if scoped:
        try:
            normed = _normalize_board_slug(scoped)
            if normed and board_exists(normed):
                return normed
        except ValueError:
            pass

    env = os.environ.get("HERMES_KANBAN_BOARD", "").strip()
    if env:
        try:
            normed = _normalize_board_slug(env)
            if normed and board_exists(normed):
                return normed
        except ValueError:
            pass
    try:
        f = current_board_path()
        if f.exists():
            val = f.read_text(encoding="utf-8").strip()
            if val:
                try:
                    normed = _normalize_board_slug(val)
                    if normed and board_exists(normed):
                        return normed
                except ValueError:
                    pass
    except OSError:
        pass
    return DEFAULT_BOARD


def set_current_board(slug: str) -> Path:
    """Persist ``slug`` as the active board. Returns the file written.

    Writes ``<root>/kanban/current``. The caller should validate the slug
    exists first (via :func:`board_exists`) — this function does not —
    so that ``hermes kanban boards switch <typo>`` returns an error
    instead of silently pointing at nothing.
    """
    normed = _normalize_board_slug(slug)
    if not normed:
        raise ValueError("board slug is required")
    path = current_board_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(normed + "\n", encoding="utf-8")
    return path


def clear_current_board() -> None:
    """Remove ``<root>/kanban/current`` so the active board reverts to ``default``."""
    try:
        current_board_path().unlink()
    except FileNotFoundError:
        pass


def board_dir(board: Optional[str] = None) -> Path:
    """Return the on-disk directory for ``board``.

    ``default`` is ``<root>/kanban/boards/default/`` **for metadata only**
    (board.json + workspaces/ + logs/). Its DB file stays at
    ``<root>/kanban.db`` for back-compat — see :func:`kanban_db_path`.

    All other boards live at ``<root>/kanban/boards/<slug>/`` with
    everything inside that directory including the ``kanban.db``.
    """
    slug = _normalize_board_slug(board) or DEFAULT_BOARD
    return boards_root() / slug


def board_exists(board: Optional[str] = None) -> bool:
    """Return True if the board has persisted metadata or a DB on disk.

    ``default`` is considered to always exist — its DB is created
    on first :func:`connect` and there's no way for it to be missing
    in a configuration where the kanban feature is usable at all.
    """
    slug = _normalize_board_slug(board) or DEFAULT_BOARD
    if slug == DEFAULT_BOARD:
        return True
    d = board_dir(slug)
    return (d / "board.json").exists() or (d / "kanban.db").exists()


def kanban_db_path(board: Optional[str] = None) -> Path:
    """Return the path to the ``kanban.db`` for ``board``.

    Resolution (highest precedence first):

    1. ``HERMES_KANBAN_DB`` env var — pins the path directly. Honoured for
       back-compat and for the dispatcher→worker handoff (defense in
       depth: dispatcher injects this into worker env so workers are
       immune to any path-resolution disagreement).
    2. When ``board`` arg is None, the active board from
       :func:`get_current_board` is used.
    3. Board ``default`` → ``<root>/kanban.db`` (back-compat path).
       Other boards → ``<root>/kanban/boards/<slug>/kanban.db``.
    """
    override = os.environ.get("HERMES_KANBAN_DB", "").strip()
    if override:
        return Path(override).expanduser()
    slug = _normalize_board_slug(board)
    if slug is None:
        slug = get_current_board()
    if slug == DEFAULT_BOARD:
        return kanban_home() / "kanban.db"
    return board_dir(slug) / "kanban.db"


def workspaces_root(board: Optional[str] = None) -> Path:
    """Return the directory under which ``scratch`` workspaces are created.

    Anchored per-board so workspaces don't leak between projects.
    ``HERMES_KANBAN_WORKSPACES_ROOT`` pins the path directly (highest
    precedence) — the dispatcher injects this into worker env.

    ``default`` keeps the legacy path ``<root>/kanban/workspaces/`` so
    that existing scratch workspaces from before the boards feature are
    preserved. Other boards use ``<root>/kanban/boards/<slug>/workspaces/``.
    """
    override = os.environ.get("HERMES_KANBAN_WORKSPACES_ROOT", "").strip()
    if override:
        return Path(override).expanduser()
    slug = _normalize_board_slug(board)
    if slug is None:
        slug = get_current_board()
    if slug == DEFAULT_BOARD:
        return kanban_home() / "kanban" / "workspaces"
    return board_dir(slug) / "workspaces"


def attachments_root(board: Optional[str] = None) -> Path:
    """Return the directory under which task file attachments are stored.

    Mirrors :func:`worker_logs_dir` / :func:`workspaces_root`: anchored
    per-board so attachments don't leak between projects. Each task gets
    its own ``<root>/.../attachments/<task_id>/`` subdirectory.

    ``HERMES_KANBAN_ATTACHMENTS_ROOT`` pins the path directly (highest
    precedence) for tests and unusual deployments.

    ``default`` uses ``<root>/kanban/attachments/``; other boards use
    ``<root>/kanban/boards/<slug>/attachments/``.

    Workers (which run with full file-tool access) read attached files
    by the absolute path surfaced in :func:`build_worker_context`. On the
    local terminal backend — the default for kanban — that path resolves
    directly. Remote backends (Docker/Modal) need this directory mounted;
    see the kanban docs.
    """
    override = os.environ.get("HERMES_KANBAN_ATTACHMENTS_ROOT", "").strip()
    if override:
        return Path(override).expanduser()
    slug = _normalize_board_slug(board)
    if slug is None:
        slug = get_current_board()
    if slug == DEFAULT_BOARD:
        return kanban_home() / "kanban" / "attachments"
    return board_dir(slug) / "attachments"


def task_attachments_dir(task_id: str, board: Optional[str] = None) -> Path:
    """Return the per-task attachment directory ``<root>/<task_id>/``."""
    task_component = str(task_id).strip()
    if (
        not task_component
        or task_component in {".", ".."}
        or Path(task_component).name != task_component
        or "/" in task_component
        or "\\" in task_component
    ):
        raise ValueError("invalid attachment task id")
    return attachments_root(board=board) / task_component


def validated_attachment_path(
    task_id: str,
    stored_path: str | Path,
    *,
    board: Optional[str] = None,
    require_file: bool = False,
) -> Path:
    """Return a canonical non-symlink attachment path for one task.

    Metadata may never name an arbitrary absolute file.  The path must be a
    direct child of the task's directory beneath the selected board root;
    ``..`` traversal and every symlinked path component are rejected.  The
    board root itself may resolve through an operator-configured symlink, but
    stored metadata is always canonicalized to the resolved root.
    """
    root = attachments_root(board=board).expanduser().resolve(strict=False)
    task_root = (root / task_attachments_dir(task_id, board=board).name).resolve(
        strict=False
    )
    if task_root.parent != root:
        raise ValueError("attachment task directory escapes the board root")
    candidate = Path(stored_path).expanduser()
    if not candidate.is_absolute():
        raise ValueError("attachment stored_path must be absolute")
    lexical = Path(os.path.abspath(str(candidate)))
    resolved = candidate.resolve(strict=False)
    if lexical != resolved:
        raise ValueError("attachment stored_path may not traverse a symlink")
    if resolved.parent != task_root:
        raise ValueError("attachment stored_path is outside the task attachment root")
    if require_file and (not resolved.is_file() or resolved.is_symlink()):
        raise ValueError("attachment file is missing or is a symlink")
    return resolved


def _open_attachment_task_dir(
    task_id: str,
    *,
    board: Optional[str] = None,
    create: bool = False,
) -> tuple[int, Path]:
    """Open the exact task attachment directory without following links.

    The returned descriptor pins the directory for a subsequent ``openat`` or
    ``unlinkat`` operation, closing the validation/use race that exists when a
    path is resolved and opened later.  The operator-configured attachment root
    itself may be a symlink; everything below its resolved target may not be.
    """
    task_component = task_attachments_dir(task_id, board=board).name
    root = attachments_root(board=board).expanduser().resolve(strict=False)
    if create:
        root.mkdir(parents=True, exist_ok=True)
    flags = os.O_RDONLY | getattr(os, "O_DIRECTORY", 0)
    root_fd = os.open(root, flags)
    try:
        if create:
            try:
                os.mkdir(task_component, mode=0o700, dir_fd=root_fd)
            except FileExistsError:
                pass
        task_flags = flags | getattr(os, "O_NOFOLLOW", 0)
        task_fd = os.open(task_component, task_flags, dir_fd=root_fd)
    finally:
        os.close(root_fd)
    return task_fd, root / task_component


def open_attachment_for_write(
    task_id: str,
    filename: str,
    *,
    board: Optional[str] = None,
):
    """Exclusively create one regular attachment via ``openat``/NOFOLLOW."""
    name = str(filename).strip()
    if not name or Path(name).name != name or name in {".", ".."}:
        raise ValueError("attachment filename must be a single path component")
    task_fd, task_root = _open_attachment_task_dir(
        task_id, board=board, create=True,
    )
    try:
        flags = (
            os.O_WRONLY | os.O_CREAT | os.O_EXCL
            | getattr(os, "O_NOFOLLOW", 0)
        )
        fd = os.open(name, flags, 0o600, dir_fd=task_fd)
    finally:
        os.close(task_fd)
    return os.fdopen(fd, "wb"), task_root / name


def open_attachment_for_read(
    task_id: str,
    stored_path: str | Path,
    *,
    board: Optional[str] = None,
):
    """Open and pin one regular attachment without a path-based TOCTOU gap."""
    canonical = validated_attachment_path(
        task_id, stored_path, board=board, require_file=False,
    )
    task_fd, _ = _open_attachment_task_dir(task_id, board=board, create=False)
    try:
        fd = os.open(
            canonical.name,
            os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0),
            dir_fd=task_fd,
        )
    finally:
        os.close(task_fd)
    try:
        if not stat.S_ISREG(os.fstat(fd).st_mode):
            raise ValueError("attachment is not a regular file")
        return os.fdopen(fd, "rb")
    except Exception:
        os.close(fd)
        raise


def unlink_attachment_blob(
    task_id: str,
    stored_path: str | Path,
    *,
    board: Optional[str] = None,
) -> None:
    """Unlink the exact direct-child name via a pinned task directory."""
    canonical = validated_attachment_path(
        task_id, stored_path, board=board, require_file=False,
    )
    try:
        task_fd, _ = _open_attachment_task_dir(task_id, board=board, create=False)
    except FileNotFoundError:
        return
    try:
        try:
            os.unlink(canonical.name, dir_fd=task_fd)
        except FileNotFoundError:
            pass
    finally:
        os.close(task_fd)


def worker_logs_dir(board: Optional[str] = None) -> Path:
    """Return the directory under which per-task worker logs are written.

    ``default`` keeps the legacy path ``<root>/kanban/logs/``. Other
    boards use ``<root>/kanban/boards/<slug>/logs/``. Logs follow the
    board — makes ``hermes kanban log`` unambiguous even when multiple
    boards have tasks with the same id.
    """
    slug = _normalize_board_slug(board)
    if slug is None:
        slug = get_current_board()
    if slug == DEFAULT_BOARD:
        return kanban_home() / "kanban" / "logs"
    return board_dir(slug) / "logs"


def board_metadata_path(board: Optional[str] = None) -> Path:
    """Return the path to ``board.json`` for ``board``.

    Stores display metadata (display name, description, icon, color,
    created_at). The on-disk slug is the canonical identity; this file
    is purely for presentation in the CLI / dashboard.
    """
    slug = _normalize_board_slug(board) or DEFAULT_BOARD
    return board_dir(slug) / "board.json"


def _default_board_display_name(slug: str) -> str:
    """Turn a slug into a reasonable default display name.

    ``atm10-server`` → ``Atm10 Server``. Users can override via
    ``board.json`` but the default should look presentable in the
    dashboard without any follow-up editing.
    """
    return " ".join(part.capitalize() for part in slug.replace("_", "-").split("-") if part) or slug


def read_board_metadata(board: Optional[str] = None) -> dict:
    """Return ``board.json`` contents (or synthesized defaults).

    Never raises — a missing / malformed ``board.json`` falls back to a
    synthesised entry so the dashboard always has something to render.
    Includes the canonical ``slug`` and ``db_path`` so the caller
    doesn't need to reconstruct them.
    """
    slug = _normalize_board_slug(board) or DEFAULT_BOARD
    meta: dict[str, Any] = {
        "slug": slug,
        "name": _default_board_display_name(slug),
        "description": "",
        "icon": "",
        "color": "",
        "default_workdir": None,
        "created_at": None,
        "archived": False,
    }
    try:
        p = board_metadata_path(slug)
        if p.exists():
            raw = json.loads(p.read_text(encoding="utf-8"))
            if isinstance(raw, dict):
                # Never let the metadata file claim a different slug than
                # its directory — trust the filesystem.
                raw["slug"] = slug
                meta.update(raw)
    except (OSError, json.JSONDecodeError):
        pass
    meta["db_path"] = str(kanban_db_path(slug))
    return meta


def write_board_metadata(
    board: Optional[str],
    *,
    name: Optional[str] = None,
    description: Optional[str] = None,
    icon: Optional[str] = None,
    color: Optional[str] = None,
    archived: Optional[bool] = None,
    default_workdir: Optional[str] = None,
) -> dict:
    """Create / update ``board.json`` for ``board``.

    Preserves any existing fields not mentioned in the call. Sets
    ``created_at`` on first write. Returns the resulting metadata dict.
    """
    slug = _normalize_board_slug(board) or DEFAULT_BOARD
    meta = read_board_metadata(slug)
    # Preserve existing DB-derived fields — they get re-computed each
    # read but shouldn't be written into board.json.
    meta.pop("db_path", None)
    if name is not None:
        meta["name"] = str(name).strip() or _default_board_display_name(slug)
    if description is not None:
        meta["description"] = str(description)
    if icon is not None:
        meta["icon"] = str(icon)
    if color is not None:
        meta["color"] = str(color)
    if archived is not None:
        meta["archived"] = bool(archived)
    if default_workdir is not None:
        meta["default_workdir"] = str(default_workdir) if default_workdir else None
    if not meta.get("created_at"):
        meta["created_at"] = int(time.time())
    path = board_metadata_path(slug)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(meta, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    meta["db_path"] = str(kanban_db_path(slug))
    return meta


def create_board(
    slug: str,
    *,
    name: Optional[str] = None,
    description: Optional[str] = None,
    icon: Optional[str] = None,
    color: Optional[str] = None,
    default_workdir: Optional[str] = None,
) -> dict:
    """Create a new board directory + DB + metadata. Idempotent.

    Returns the resulting metadata. Raises :class:`ValueError` for a
    malformed slug; returns the existing metadata (not an error) if the
    board already exists — matching ``mkdir -p`` semantics.
    """
    normed = _normalize_board_slug(slug)
    if not normed:
        raise ValueError("board slug is required")
    meta = write_board_metadata(
        normed,
        name=name,
        description=description,
        icon=icon,
        color=color,
        default_workdir=default_workdir,
    )
    # Touch the DB so list_boards() sees it immediately.
    init_db(board=normed)
    return meta


def list_boards(*, include_archived: bool = True) -> list[dict]:
    """Enumerate all boards that exist on disk.

    Always includes ``default`` (even when the ``boards/default/``
    metadata dir doesn't exist, because its DB is at the legacy path).
    Other boards are discovered by scanning ``boards/`` for subdirectories
    that either contain a ``kanban.db`` or a ``board.json``.

    Returns a list of metadata dicts, sorted with ``default`` first and
    the rest alphabetically.
    """
    entries: list[dict] = []
    seen: set[str] = set()

    # Default board is always first.
    entries.append(read_board_metadata(DEFAULT_BOARD))
    seen.add(DEFAULT_BOARD)

    root = boards_root()
    if root.is_dir():
        for child in sorted(root.iterdir(), key=lambda p: p.name.lower()):
            if not child.is_dir():
                continue
            slug = child.name
            # Keep slug normalisation soft for discovery — but skip dirs
            # that don't parse as valid slugs so we don't surface junk.
            try:
                normed = _normalize_board_slug(slug)
            except ValueError:
                continue
            if not normed or normed in seen:
                continue
            has_db = (child / "kanban.db").exists()
            has_meta = (child / "board.json").exists()
            if not (has_db or has_meta):
                continue
            meta = read_board_metadata(normed)
            if meta.get("archived") and not include_archived:
                continue
            entries.append(meta)
            seen.add(normed)
    return entries


def remove_board(slug: str, *, archive: bool = True) -> dict:
    """Remove or archive a board.

    ``archive=True`` (default) moves the board's directory to
    ``<root>/kanban/boards/_archived/<slug>-<timestamp>/`` so the data
    is recoverable. ``archive=False`` deletes the directory outright.

    The ``default`` board cannot be removed — raises :class:`ValueError`.
    Returns a summary dict describing what happened (``{"slug", "action",
    "new_path"}``).
    """
    normed = _normalize_board_slug(slug)
    if not normed:
        raise ValueError("board slug is required")
    if normed == DEFAULT_BOARD:
        raise ValueError("the 'default' board cannot be removed")
    d = board_dir(normed)
    if not d.exists():
        raise ValueError(f"board {normed!r} does not exist")

    # Board removal has filesystem and active-board side effects before any
    # normal Kanban transaction exists. Inspect the existing DB read-only and
    # refuse a generic removal if it contains governed state. Failure to read
    # governance state also fails closed and leaves the directory, selector,
    # and initialization cache untouched.
    db_file = d / "kanban.db"
    if db_file.exists():
        try:
            ro = sqlite3.connect(
                f"{db_file.resolve().as_uri()}?mode=ro",
                uri=True,
            )
            try:
                has_tasks = ro.execute(
                    "SELECT 1 FROM sqlite_master "
                    "WHERE type = 'table' AND name = 'tasks'"
                ).fetchone() is not None
                columns = (
                    {row[1] for row in ro.execute("PRAGMA table_info(tasks)")}
                    if has_tasks else set()
                )
                governed = (
                    ro.execute(
                        "SELECT 1 FROM tasks "
                        "WHERE olympus_context IS NOT NULL LIMIT 1"
                    ).fetchone() is not None
                    if "olympus_context" in columns else False
                )
            finally:
                ro.close()
        except sqlite3.Error as exc:
            raise OlympusContextError(
                "olympus_board_governance_unreadable",
                "cannot prove that board removal contains no governed state",
            ) from exc
        if governed:
            raise OlympusContextError(
                "olympus_board_removal_forbidden",
                "generic board removal cannot archive or delete governed state",
            )

    # If the user removed the currently-active board, revert to default.
    if get_current_board() == normed:
        clear_current_board()

    # A concurrent connect(board=normed) after the rename/delete recreates
    # an empty sqlite file via mkdir(exist_ok=True); the cache entry must be
    # dropped first so the schema init pass re-runs on that fresh file.
    _INITIALIZED_PATHS.discard(str((d / "kanban.db").resolve()))

    if archive:
        archive_root = boards_root() / "_archived"
        archive_root.mkdir(parents=True, exist_ok=True)
        ts = int(time.time())
        target = archive_root / f"{normed}-{ts}"
        # Avoid collision on rapid double-archives.
        suffix = 1
        while target.exists():
            target = archive_root / f"{normed}-{ts}-{suffix}"
            suffix += 1
        d.rename(target)
        return {"slug": normed, "action": "archived", "new_path": str(target)}
    else:
        import shutil
        shutil.rmtree(d)
        return {"slug": normed, "action": "deleted", "new_path": ""}


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------

@dataclass
class Task:
    """In-memory view of a row from the ``tasks`` table."""

    id: str
    title: str
    body: Optional[str]
    assignee: Optional[str]
    status: str
    priority: int
    created_by: Optional[str]
    created_at: int
    started_at: Optional[int]
    completed_at: Optional[int]
    workspace_kind: str
    workspace_path: Optional[str]
    claim_lock: Optional[str]
    claim_expires: Optional[int]
    tenant: Optional[str]
    branch_name: Optional[str] = None
    result: Optional[str] = None
    idempotency_key: Optional[str] = None
    # Unified non-success counter. Incremented on any of:
    #   * spawn failure (dispatcher couldn't launch the worker)
    #   * timed_out outcome (worker exceeded max_runtime_seconds)
    #   * crashed outcome (worker PID vanished)
    # Reset to 0 only on a successful completion. See
    # ``_record_task_failure`` for the circuit-breaker trip rule.
    # (Pre-rename column: ``spawn_failures``.)
    consecutive_failures: int = 0
    worker_pid: Optional[int] = None
    # Short excerpt of the last failure's error text (any outcome, not
    # just spawn). Pre-rename column: ``last_spawn_error``.
    last_failure_error: Optional[str] = None
    max_runtime_seconds: Optional[int] = None
    last_heartbeat_at: Optional[int] = None
    current_run_id: Optional[int] = None
    workflow_template_id: Optional[str] = None
    current_step_key: Optional[str] = None
    # Force-loaded skills for the worker on this task (appended to the
    # dispatcher's built-in `kanban-worker` via --skills). Stored as a
    # JSON array of skill names. None = use only the defaults; empty
    # list = explicitly no extra skills.
    skills: Optional[list] = None
    model_override: Optional[str] = None
    # Per-task override for the consecutive-failure circuit breaker.
    # The value is the failure count at which the breaker trips — e.g.
    # ``max_retries=1`` blocks on the first failure (zero retries),
    # ``max_retries=3`` blocks on the third (two retries allowed).
    # ``None`` (the common case) falls through to the dispatcher-level
    # ``kanban.failure_limit`` config, and then to ``DEFAULT_FAILURE_LIMIT``.
    # Name matches the ``--max-retries`` CLI flag on ``kanban create``.
    max_retries: Optional[int] = None
    # When True, the dispatched worker runs in a Ralph-style goal loop
    # (the same engine behind the ``/goal`` slash command): after each
    # turn an auxiliary judge model evaluates the worker's response
    # against this card's title/body (treated as the goal). If the judge
    # says "not done" and budget remains, the worker is fed a
    # continuation prompt IN THE SAME SESSION and keeps working until the
    # judge agrees, the goal-turn budget is exhausted (→ kanban_block),
    # or the worker explicitly blocks/completes. ``False`` (default) =
    # the classic single-shot worker. ``goal_max_turns`` bounds the loop.
    goal_mode: bool = False
    # Goal-loop turn budget for ``goal_mode`` workers. ``None`` falls
    # through to the goals engine default (``goals.DEFAULT_MAX_TURNS``).
    goal_max_turns: Optional[int] = None
    # Originating chat/agent session id, when the task was created from
    # within an agent loop that propagated ``HERMES_SESSION_ID``. NULL for
    # tasks created from the CLI, the dashboard, or any path that doesn't
    # set the env var. Lets clients render a per-session board without
    # relying on tenant + time-window heuristics.
    session_id: Optional[str] = None
    # Versioned Olympus authority context. NULL is the explicit legacy path;
    # a present-but-invalid document stays visibly invalid and is denied by
    # every governed claim/start gate rather than silently becoming legacy.
    olympus_context: Optional[dict] = None
    # Current revision of the local Kanban task aggregate. This is distinct
    # from both MissionStore mission revision and authority/lease revisions.
    record_revision: int = 0

    @classmethod
    def from_row(cls, row: sqlite3.Row) -> "Task":
        keys = set(row.keys())
        # Parse skills JSON blob if present
        skills_value: Optional[list] = None
        if "skills" in keys and row["skills"]:
            try:
                parsed = json.loads(row["skills"])
                if isinstance(parsed, list):
                    skills_value = [str(s) for s in parsed if s]
            except Exception:
                skills_value = None
        return cls(
            id=row["id"],
            title=row["title"],
            body=row["body"],
            assignee=row["assignee"],
            status=row["status"],
            priority=row["priority"],
            created_by=row["created_by"],
            created_at=row["created_at"],
            started_at=row["started_at"],
            completed_at=row["completed_at"],
            workspace_kind=row["workspace_kind"],
            workspace_path=row["workspace_path"],
            branch_name=row["branch_name"] if "branch_name" in keys else None,
            claim_lock=row["claim_lock"],
            claim_expires=row["claim_expires"],
            tenant=row["tenant"] if "tenant" in keys else None,
            result=row["result"] if "result" in keys else None,
            idempotency_key=row["idempotency_key"] if "idempotency_key" in keys else None,
            consecutive_failures=(
                row["consecutive_failures"] if "consecutive_failures" in keys
                # Pre-migration fallback: ``_migrate_add_optional_columns`` always
                # adds ``consecutive_failures`` now, so this branch is only reachable
                # on a DB that was never opened since pre-#20410 code ran. Keep for
                # belt-and-suspenders safety; in practice it is dead code post-migration.
                else (row["spawn_failures"] if "spawn_failures" in keys else 0)
            ),
            worker_pid=row["worker_pid"] if "worker_pid" in keys else None,
            last_failure_error=(
                row["last_failure_error"] if "last_failure_error" in keys
                # Same belt-and-suspenders fallback as consecutive_failures above.
                else (row["last_spawn_error"] if "last_spawn_error" in keys else None)
            ),
            max_runtime_seconds=(
                row["max_runtime_seconds"] if "max_runtime_seconds" in keys else None
            ),
            last_heartbeat_at=(
                row["last_heartbeat_at"] if "last_heartbeat_at" in keys else None
            ),
            current_run_id=(
                row["current_run_id"] if "current_run_id" in keys else None
            ),
            workflow_template_id=(
                row["workflow_template_id"] if "workflow_template_id" in keys else None
            ),
            current_step_key=(
                row["current_step_key"] if "current_step_key" in keys else None
            ),
            skills=skills_value,
            model_override=row["model_override"] if "model_override" in keys and row["model_override"] else None,
            max_retries=(
                row["max_retries"] if "max_retries" in keys else None
            ),
            goal_mode=(
                bool(row["goal_mode"]) if "goal_mode" in keys and row["goal_mode"] else False
            ),
            goal_max_turns=(
                row["goal_max_turns"] if "goal_max_turns" in keys and row["goal_max_turns"] else None
            ),
            session_id=(
                row["session_id"] if "session_id" in keys else None
            ),
            olympus_context=(
                _decode_olympus_context(row["olympus_context"])
                if "olympus_context" in keys else None
            ),
            record_revision=(
                int(row["record_revision"])
                if "record_revision" in keys else 0
            ),
        )


@dataclass
class Run:
    """In-memory view of a ``task_runs`` row.

    A run is one attempt to execute a task — created on claim, closed
    on complete/block/crash/timeout/spawn_failure/reclaim. Multiple runs
    per task when retries happen. Carries the claim machinery, PID,
    heartbeat, and the structured handoff summary that downstream workers
    read via ``build_worker_context``.
    """

    id: int
    task_id: str
    profile: Optional[str]
    step_key: Optional[str]
    status: str
    claim_lock: Optional[str]
    claim_expires: Optional[int]
    worker_pid: Optional[int]
    max_runtime_seconds: Optional[int]
    last_heartbeat_at: Optional[int]
    started_at: int
    ended_at: Optional[int]
    outcome: Optional[str]
    summary: Optional[str]
    metadata: Optional[dict]
    error: Optional[str]
    olympus_context: Optional[dict] = None
    subject_revision: Optional[int] = None
    process_state: str = "legacy"
    launch_token: Optional[str] = None
    workspace_snapshot: Optional[dict] = None
    auth_root_id: Optional[str] = None
    auth_root_revision: Optional[int] = None
    verification_id: Optional[str] = None
    worker_host_id: Optional[str] = None
    worker_boot_id: Optional[str] = None
    worker_start_token: Optional[str] = None
    worker_registered_at: Optional[int] = None
    dispatcher_instance_id: Optional[str] = None

    @classmethod
    def from_row(cls, row: sqlite3.Row) -> "Run":
        try:
            meta = json.loads(row["metadata"]) if row["metadata"] else None
        except Exception:
            meta = None
        try:
            workspace_snapshot = (
                json.loads(row["workspace_snapshot"])
                if "workspace_snapshot" in row.keys()
                and row["workspace_snapshot"] else None
            )
        except Exception:
            workspace_snapshot = None
        return cls(
            id=int(row["id"]),
            task_id=row["task_id"],
            profile=row["profile"],
            step_key=row["step_key"],
            status=row["status"],
            claim_lock=row["claim_lock"],
            claim_expires=row["claim_expires"],
            worker_pid=row["worker_pid"],
            max_runtime_seconds=row["max_runtime_seconds"],
            last_heartbeat_at=row["last_heartbeat_at"],
            started_at=int(row["started_at"]),
            ended_at=(int(row["ended_at"]) if row["ended_at"] is not None else None),
            outcome=row["outcome"],
            summary=row["summary"],
            metadata=meta,
            error=row["error"],
            olympus_context=(
                _decode_olympus_context(row["olympus_context"])
                if "olympus_context" in row.keys() else None
            ),
            subject_revision=(
                int(row["subject_revision"])
                if "subject_revision" in row.keys()
                and row["subject_revision"] is not None else None
            ),
            process_state=(
                str(row["process_state"])
                if "process_state" in row.keys() and row["process_state"]
                else "legacy"
            ),
            launch_token=(
                row["launch_token"] if "launch_token" in row.keys() else None
            ),
            workspace_snapshot=workspace_snapshot,
            auth_root_id=(
                row["auth_root_id"] if "auth_root_id" in row.keys() else None
            ),
            auth_root_revision=(
                int(row["auth_root_revision"])
                if "auth_root_revision" in row.keys()
                and row["auth_root_revision"] is not None else None
            ),
            verification_id=(
                row["verification_id"]
                if "verification_id" in row.keys() else None
            ),
            worker_host_id=(
                row["worker_host_id"]
                if "worker_host_id" in row.keys() else None
            ),
            worker_boot_id=(
                row["worker_boot_id"]
                if "worker_boot_id" in row.keys() else None
            ),
            worker_start_token=(
                row["worker_start_token"]
                if "worker_start_token" in row.keys() else None
            ),
            worker_registered_at=(
                int(row["worker_registered_at"])
                if "worker_registered_at" in row.keys()
                and row["worker_registered_at"] is not None else None
            ),
            dispatcher_instance_id=(
                row["dispatcher_instance_id"]
                if "dispatcher_instance_id" in row.keys() else None
            ),
        )


@dataclass
class Comment:
    id: int
    task_id: str
    author: str
    body: str
    created_at: int


@dataclass
class Attachment:
    """In-memory view of a row from the ``task_attachments`` table."""

    id: int
    task_id: str
    filename: str
    stored_path: str
    content_type: Optional[str]
    size: int
    uploaded_by: Optional[str]
    created_at: int


@dataclass
class Event:
    id: int
    task_id: str
    kind: str
    payload: Optional[dict]
    created_at: int
    run_id: Optional[int] = None


# ---------------------------------------------------------------------------
# Schema
# ---------------------------------------------------------------------------

SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS tasks (
    id                   TEXT PRIMARY KEY,
    title                TEXT NOT NULL,
    body                 TEXT,
    assignee             TEXT,
    status               TEXT NOT NULL,
    priority             INTEGER DEFAULT 0,
    created_by           TEXT,
    created_at           INTEGER NOT NULL,
    started_at           INTEGER,
    completed_at         INTEGER,
    workspace_kind       TEXT NOT NULL DEFAULT 'scratch',
    workspace_path       TEXT,
    branch_name          TEXT,
    claim_lock           TEXT,
    claim_expires        INTEGER,
    tenant               TEXT,
    result               TEXT,
    idempotency_key      TEXT,
    -- Unified consecutive-failure counter. Incremented on spawn
    -- failure, timeout, or crash; reset only on successful completion.
    -- The circuit breaker in _record_task_failure trips when this
    -- exceeds DEFAULT_FAILURE_LIMIT consecutive non-successes.
    consecutive_failures INTEGER NOT NULL DEFAULT 0,
    worker_pid           INTEGER,
    -- Short excerpt of the most recent failure's error text.
    last_failure_error   TEXT,
    max_runtime_seconds  INTEGER,
    last_heartbeat_at    INTEGER,
    -- Pointer into task_runs for the currently-active run (NULL if no
    -- run is in-flight). Denormalised for cheap reads.
    current_run_id       INTEGER,
    -- Forward-compat for v2 workflow routing. In v1 the kernel writes
    -- these when the task is opted into a template but otherwise ignores
    -- them; the dispatcher doesn't consult them for routing yet.
    workflow_template_id TEXT,
    current_step_key     TEXT,
    -- Force-loaded skills for the worker on this task, stored as JSON.
    -- Appended to the dispatcher's built-in `--skills kanban-worker`.
    -- NULL or empty array = no extras.
    skills               TEXT,
    -- Per-task model override. When set, the dispatcher passes -m <model>
    -- to the worker, overriding the profile's default model. NULL = use
    -- the profile default.
    model_override       TEXT,
    -- Per-task override for the consecutive-failure circuit breaker.
    -- The value is the failure count at which the breaker trips — e.g.
    -- ``max_retries=1`` blocks on the first failure. NULL (the common
    -- case) falls through to the dispatcher-level ``kanban.failure_limit``
    -- config and then ``DEFAULT_FAILURE_LIMIT``.
    max_retries          INTEGER,
    -- When 1, the dispatched worker runs in a Ralph-style goal loop: an
    -- auxiliary judge re-evaluates the worker's response against the
    -- card title/body after each turn and feeds a continuation prompt
    -- back into the SAME session until the judge agrees the work is done
    -- or ``goal_max_turns`` is exhausted. NULL/0 = classic single-shot
    -- worker (the default).
    goal_mode            INTEGER NOT NULL DEFAULT 0,
    -- Goal-loop turn budget for ``goal_mode`` workers. NULL = use the
    -- goals-engine default.
    goal_max_turns       INTEGER,
    -- Originating chat/agent session id when the task was created from
    -- inside an agent loop that propagated ``HERMES_SESSION_ID``. NULL
    -- for tasks created from the CLI, dashboard, or any path that doesn't
    -- set the env var. Indexed so per-session list queries stay cheap on
    -- larger boards.
    session_id           TEXT,
    -- Versioned Olympus goal/program/mission, authority, lease, risk,
    -- agent, review, and evidence references. NULL preserves ordinary Kanban
    -- compatibility; any non-NULL value is fail-closed at claim/start.
    olympus_context      TEXT,
    -- CAS revision for the Kanban task aggregate. Ordinary/legacy rows retain
    -- zero; a governed row starts at one and every authorized aggregate
    -- mutation advances it exactly once.
    record_revision      INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS task_links (
    parent_id  TEXT NOT NULL,
    child_id   TEXT NOT NULL,
    PRIMARY KEY (parent_id, child_id)
);

CREATE TABLE IF NOT EXISTS task_comments (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    task_id    TEXT NOT NULL,
    author     TEXT NOT NULL,
    body       TEXT NOT NULL,
    created_at INTEGER NOT NULL
);

CREATE TABLE IF NOT EXISTS task_events (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    task_id    TEXT NOT NULL,
    run_id     INTEGER,
    kind       TEXT NOT NULL,
    payload    TEXT,
    created_at INTEGER NOT NULL
);

-- Historical attempt record. Each time the dispatcher claims a task, a
-- new row is created here; claim state, PID, heartbeat, runtime cap,
-- and structured summary all live on the run, not the task. Multiple
-- rows per task id when the task was retried after crash/timeout/block.
-- v2 of the kanban schema will use ``step_key`` to drive per-stage
-- workflow routing; in v1 the column is nullable and unused (kernel
-- ignores it).
CREATE TABLE IF NOT EXISTS task_runs (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    task_id             TEXT NOT NULL,
    profile             TEXT,
    step_key            TEXT,
    status              TEXT NOT NULL,
    -- status: running | done | blocked | crashed | timed_out | failed | released
    claim_lock          TEXT,
    claim_expires       INTEGER,
    worker_pid          INTEGER,
    max_runtime_seconds INTEGER,
    last_heartbeat_at   INTEGER,
    started_at          INTEGER NOT NULL,
    ended_at            INTEGER,
    outcome             TEXT,
    -- outcome: completed | blocked | crashed | timed_out | spawn_failed |
    --          gave_up | reclaimed | (null while still running)
    summary             TEXT,
    metadata            TEXT,
    error               TEXT,
    -- Immutable Olympus task-context snapshot at the start of this attempt.
    -- Later lease renewal/revocation updates the task row, not history.
    olympus_context     TEXT,
    -- Exact governed task revision that admitted this run.
    subject_revision   INTEGER,
    -- Durable process fence. Legacy rows never acquire signal authority.
    process_state      TEXT NOT NULL DEFAULT 'legacy',
    launch_token       TEXT,
    workspace_snapshot TEXT,
    auth_root_id       TEXT,
    auth_root_revision INTEGER,
    verification_id   TEXT,
    worker_host_id     TEXT,
    worker_boot_id     TEXT,
    worker_start_token TEXT,
    worker_registered_at INTEGER,
    dispatcher_instance_id TEXT
);

-- Files attached to a task (PDFs, images, source documents). The blob
-- lives on disk under ``attachments_root(board)/<task_id>/<stored_name>``;
-- this row carries metadata + the absolute ``stored_path`` so the
-- dashboard can list/download and ``build_worker_context`` can surface
-- the absolute path to the worker (which has full file-tool access). See
-- #35338.
CREATE TABLE IF NOT EXISTS task_attachments (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    task_id      TEXT NOT NULL,
    filename     TEXT NOT NULL,
    stored_path  TEXT NOT NULL,
    content_type TEXT,
    size         INTEGER NOT NULL DEFAULT 0,
    uploaded_by  TEXT,
    created_at   INTEGER NOT NULL
);

-- Subscription from a gateway source (platform + chat + thread) to a
-- task. The gateway's kanban-notifier watcher tails task_events and
-- pushes ``completed`` / ``blocked`` / ``spawn_auto_blocked`` events to
-- the original requester so human-in-the-loop workflows close the loop.
CREATE TABLE IF NOT EXISTS kanban_notify_subs (
    task_id       TEXT NOT NULL,
    platform      TEXT NOT NULL,
    chat_id       TEXT NOT NULL,
    thread_id     TEXT NOT NULL DEFAULT '',
    user_id       TEXT,
    notifier_profile TEXT,
    created_at    INTEGER NOT NULL,
    last_event_id INTEGER NOT NULL DEFAULT 0,
    PRIMARY KEY (task_id, platform, chat_id, thread_id)
);

-- Durable exact request identity for governed idempotent creation. The task
-- row is mutable after creation, so replay safety cannot be reconstructed from
-- its current status or dispatcher-owned fields.
CREATE TABLE IF NOT EXISTS kanban_olympus_create_receipts (
    idempotency_key TEXT PRIMARY KEY,
    task_id         TEXT NOT NULL UNIQUE,
    payload         TEXT NOT NULL,
    payload_sha256  TEXT NOT NULL,
    created_at      INTEGER NOT NULL
);

-- Crash-safe release evidence. A retry reads this immutable receipt even when
-- the dispatcher has already claimed the newly-ready task.
CREATE TABLE IF NOT EXISTS kanban_olympus_release_receipts (
    operation_id      TEXT PRIMARY KEY,
    task_id           TEXT NOT NULL,
    subject_revision  INTEGER NOT NULL,
    record_revision   INTEGER NOT NULL,
    verification_id   TEXT NOT NULL,
    request_id        TEXT NOT NULL,
    receipt            TEXT NOT NULL,
    receipt_sha256     TEXT NOT NULL,
    created_at         INTEGER NOT NULL,
    UNIQUE(task_id, subject_revision)
);

-- One immutable Telegram delivery may create exactly one governed task. The
-- payload includes the authenticated source, selected authorization root,
-- delegated agent, task request, and notification destination.
CREATE TABLE IF NOT EXISTS olympus_telegram_deliveries (
    delivery_key                 TEXT PRIMARY KEY,
    authorization_task_id        TEXT NOT NULL,
    authorization_task_revision  INTEGER NOT NULL,
    task_id                      TEXT NOT NULL UNIQUE,
    payload                      TEXT NOT NULL,
    payload_sha256               TEXT NOT NULL,
    created_at                   INTEGER NOT NULL
);

-- Immutable request/result receipt for an operator control. Running-task
-- interruption is represented by the certified worker effect journal; this
-- table never owns PIDs or process execution state.
CREATE TABLE IF NOT EXISTS olympus_telegram_controls (
    operation_id                 TEXT PRIMARY KEY,
    action                       TEXT NOT NULL,
    authorization_task_id        TEXT NOT NULL,
    authorization_task_revision  INTEGER NOT NULL,
    target_task_id               TEXT NOT NULL,
    target_task_revision         INTEGER NOT NULL,
    source_identity              TEXT NOT NULL,
    request_payload              TEXT NOT NULL,
    payload_sha256               TEXT NOT NULL,
    verification_id              TEXT NOT NULL,
    result_status                TEXT,
    effect_operation_id          TEXT,
    created_at                   INTEGER NOT NULL
);

-- Durable completion markers for migrations whose columns and data backfills
-- must be treated as one crash-recoverable unit.
CREATE TABLE IF NOT EXISTS kanban_schema_migrations (
    name         TEXT PRIMARY KEY,
    completed_at INTEGER NOT NULL
);

-- Fixed-purpose side-effect journal.  It is intentionally not a general job
-- queue: only worker termination and notification delivery may be recorded.
CREATE TABLE IF NOT EXISTS kanban_effect_journal (
    id                   INTEGER PRIMARY KEY AUTOINCREMENT,
    effect_kind          TEXT NOT NULL,
    operation_id         TEXT NOT NULL,
    task_id              TEXT NOT NULL,
    run_id               INTEGER,
    event_id             INTEGER,
    destination_key      TEXT,
    part                 TEXT,
    auth_root_id         TEXT,
    auth_root_revision   INTEGER,
    target_pre_revision  INTEGER NOT NULL,
    target_post_revision INTEGER,
    worker_host_id       TEXT,
    worker_boot_id       TEXT,
    worker_pid           INTEGER,
    worker_start_token   TEXT,
    source_identity      TEXT,
    payload              TEXT NOT NULL,
    payload_sha256       TEXT NOT NULL,
    state                TEXT NOT NULL,
    error                TEXT,
    created_at           INTEGER NOT NULL,
    updated_at           INTEGER NOT NULL,
    applied_at           INTEGER,
    UNIQUE(effect_kind, operation_id)
);

CREATE INDEX IF NOT EXISTS idx_tasks_assignee_status ON tasks(assignee, status);
CREATE INDEX IF NOT EXISTS idx_tasks_status          ON tasks(status);
CREATE INDEX IF NOT EXISTS idx_links_child           ON task_links(child_id);
CREATE INDEX IF NOT EXISTS idx_links_parent          ON task_links(parent_id);
CREATE INDEX IF NOT EXISTS idx_comments_task         ON task_comments(task_id, created_at);
CREATE INDEX IF NOT EXISTS idx_events_task           ON task_events(task_id, created_at);
CREATE INDEX IF NOT EXISTS idx_runs_task             ON task_runs(task_id, started_at);
CREATE INDEX IF NOT EXISTS idx_runs_status           ON task_runs(status);
CREATE INDEX IF NOT EXISTS idx_attachments_task      ON task_attachments(task_id, created_at);
CREATE INDEX IF NOT EXISTS idx_notify_task           ON kanban_notify_subs(task_id);
CREATE INDEX IF NOT EXISTS idx_effects_state          ON kanban_effect_journal(state, effect_kind);
CREATE INDEX IF NOT EXISTS idx_effects_task_event     ON kanban_effect_journal(task_id, event_id, id);

CREATE TRIGGER IF NOT EXISTS effect_journal_immutable
BEFORE UPDATE ON kanban_effect_journal
WHEN olympus_schema_migration_active() != 1 AND (
  NEW.effect_kind IS NOT OLD.effect_kind
  OR NEW.operation_id IS NOT OLD.operation_id
  OR NEW.task_id IS NOT OLD.task_id
  OR NEW.run_id IS NOT OLD.run_id
  OR NEW.event_id IS NOT OLD.event_id
  OR NEW.destination_key IS NOT OLD.destination_key
  OR NEW.part IS NOT OLD.part
  OR NEW.auth_root_id IS NOT OLD.auth_root_id
  OR NEW.auth_root_revision IS NOT OLD.auth_root_revision
  OR NEW.target_pre_revision IS NOT OLD.target_pre_revision
  OR NEW.target_post_revision IS NOT OLD.target_post_revision
  OR NEW.worker_host_id IS NOT OLD.worker_host_id
  OR NEW.worker_boot_id IS NOT OLD.worker_boot_id
  OR NEW.worker_pid IS NOT OLD.worker_pid
  OR NEW.worker_start_token IS NOT OLD.worker_start_token
  OR NEW.source_identity IS NOT OLD.source_identity
  OR NEW.payload IS NOT OLD.payload
  OR NEW.payload_sha256 IS NOT OLD.payload_sha256
  OR NEW.created_at IS NOT OLD.created_at
)
BEGIN
    SELECT RAISE(ABORT, 'kanban_effect_identity_immutable');
END;
"""


# ---------------------------------------------------------------------------
# Connection helpers
# ---------------------------------------------------------------------------

_INITIALIZED_PATHS: set[str] = set()
_INIT_LOCK = threading.RLock()
_OLYMPUS_GUARD_INSTALL_FAILPOINT: Optional[Callable[[], None]] = None
_OLYMPUS_REBUILD_FAILPOINT: Optional[Callable[[str], None]] = None
_OLYMPUS_EFFECT_EXECUTION_FAILPOINT: Optional[Callable[[str], None]] = None
_OLYMPUS_TELEGRAM_MIGRATION_FAILPOINT: Optional[
    Callable[[str], None]
] = None
_SQLITE_HEADER = b"SQLite format 3\x00"
DEFAULT_BUSY_TIMEOUT_MS = 120_000


def _resolve_busy_timeout_ms() -> int:
    """Return the SQLite busy timeout for Kanban connections.

    Kanban is the shared cross-profile dispatch bus, so worker stampedes are
    expected.  A long busy timeout lets SQLite serialize writers via WAL rather
    than surfacing transient ``database is locked`` failures during bursts.
    """
    raw = os.environ.get("HERMES_KANBAN_BUSY_TIMEOUT_MS", "").strip()
    if raw:
        try:
            parsed = int(raw)
        except ValueError:
            parsed = 0
        if parsed > 0:
            return parsed
    return DEFAULT_BUSY_TIMEOUT_MS


class _KanbanConnection(sqlite3.Connection):
    """Connection carrying process-local, SQL-inaccessible permit state."""


def _connection_board_identity(conn: sqlite3.Connection) -> str:
    row = conn.execute("PRAGMA database_list").fetchone()
    path = row[2] if row is not None else ""
    if not path:
        return "memory"
    return str(Path(path).expanduser().resolve(strict=False))


def _local_host_id() -> str:
    import socket
    raw = socket.gethostname() or "unknown-host"
    return hashlib.sha256(raw.encode()).hexdigest()[:32]


def _local_boot_id() -> Optional[str]:
    candidates = (Path("/proc/sys/kernel/random/boot_id"),)
    for candidate in candidates:
        try:
            value = candidate.read_text(encoding="utf-8").strip()
        except OSError:
            continue
        if value:
            return value
    try:
        proc = subprocess.run(
            ["sysctl", "-n", "kern.boottime"],
            check=True,
            capture_output=True,
            text=True,
            timeout=2,
        )
        value = proc.stdout.strip()
    except (OSError, subprocess.SubprocessError):
        value = ""
    if not value:
        return None
    return hashlib.sha256(value.encode()).hexdigest()


def _process_start_token(pid: int) -> Optional[str]:
    if sys.platform == "darwin":
        # `ps -o lstart` is only second-granular and can alias after a fast
        # PID recycle.  libproc exposes the kernel's timeval start instant,
        # including microseconds, without trusting command output.
        try:
            import ctypes

            class _ProcBsdInfo(ctypes.Structure):
                _fields_ = [
                    ("pbi_flags", ctypes.c_uint32),
                    ("pbi_status", ctypes.c_uint32),
                    ("pbi_xstatus", ctypes.c_uint32),
                    ("pbi_pid", ctypes.c_uint32),
                    ("pbi_ppid", ctypes.c_uint32),
                    ("pbi_uid", ctypes.c_uint32),
                    ("pbi_gid", ctypes.c_uint32),
                    ("pbi_ruid", ctypes.c_uint32),
                    ("pbi_rgid", ctypes.c_uint32),
                    ("pbi_svuid", ctypes.c_uint32),
                    ("pbi_svgid", ctypes.c_uint32),
                    ("rfu_1", ctypes.c_uint32),
                    ("pbi_comm", ctypes.c_char * 16),
                    ("pbi_name", ctypes.c_char * 32),
                    ("pbi_nfiles", ctypes.c_uint32),
                    ("pbi_pgid", ctypes.c_uint32),
                    ("pbi_pjobc", ctypes.c_uint32),
                    ("e_tdev", ctypes.c_uint32),
                    ("e_tpgid", ctypes.c_uint32),
                    ("pbi_nice", ctypes.c_int32),
                    ("pbi_start_tvsec", ctypes.c_uint64),
                    ("pbi_start_tvusec", ctypes.c_uint64),
                ]

            libproc = ctypes.CDLL("/usr/lib/libproc.dylib", use_errno=True)
            libproc.proc_pidinfo.argtypes = [
                ctypes.c_int, ctypes.c_int, ctypes.c_uint64,
                ctypes.c_void_p, ctypes.c_int,
            ]
            libproc.proc_pidinfo.restype = ctypes.c_int
            info = _ProcBsdInfo()
            copied = libproc.proc_pidinfo(
                int(pid), 3, 0, ctypes.byref(info), ctypes.sizeof(info)
            )
            if copied == ctypes.sizeof(info) and info.pbi_start_tvsec:
                return (
                    f"darwin:{int(info.pbi_start_tvsec)}:"
                    f"{int(info.pbi_start_tvusec)}"
                )
        except (OSError, TypeError, ValueError):
            pass
        # Never weaken Darwin identity to the second-granular `ps` value.
        return None
    stat_path = Path(f"/proc/{pid}/stat")
    try:
        raw = stat_path.read_text(encoding="utf-8")
        closing = raw.rfind(")")
        fields = raw[closing + 2:].split()
        if closing >= 0 and len(fields) > 19:
            return fields[19]
    except OSError:
        pass
    try:
        proc = subprocess.run(
            ["ps", "-o", "lstart=", "-p", str(pid)],
            check=True,
            capture_output=True,
            text=True,
            timeout=2,
        )
        value = proc.stdout.strip()
    except (OSError, subprocess.SubprocessError):
        value = ""
    if not value:
        return None
    return hashlib.sha256(value.encode()).hexdigest()


def read_process_identity(pid: int) -> Optional[ProcessIdentity]:
    """Read an exact live process identity or return ``None`` fail-closed."""
    if isinstance(pid, bool) or not isinstance(pid, int) or pid <= 0:
        return None
    boot_id = _local_boot_id()
    start_token = _process_start_token(pid)
    if not boot_id or not start_token:
        return None
    return ProcessIdentity(
        host_id=_local_host_id(),
        boot_id=boot_id,
        pid=int(pid),
        start_token=start_token,
    )


def _sqlite_connect(path: Path) -> sqlite3.Connection:
    """Open a Kanban SQLite connection with consistent lock waiting."""
    busy_timeout_ms = _resolve_busy_timeout_ms()
    conn = sqlite3.connect(
        str(path),
        isolation_level=None,
        timeout=busy_timeout_ms / 1000.0,
        factory=_KanbanConnection,
    )
    conn._olympus_permit_registry = {}
    conn._olympus_audit_registry = set()
    conn._olympus_managed_txn_depth = 0
    conn._olympus_external_txn = False
    # ``sqlite3.connect(timeout=...)`` normally maps to busy_timeout, but set
    # the PRAGMA explicitly so it is observable and survives future wrapper
    # changes. Parameter binding is not supported for PRAGMA assignments.
    conn.execute(f"PRAGMA busy_timeout={busy_timeout_ms}")
    return conn


@contextlib.contextmanager
def _cross_process_init_lock(path: Path):
    """Serialize first-connect WAL/schema/integrity setup across processes.

    ``_INIT_LOCK`` only protects threads inside one Python process. During a
    dispatcher burst, many worker processes can all hit a fresh/legacy board at
    once and each process has an empty ``_INITIALIZED_PATHS`` cache. This file
    lock keeps header validation, integrity probing, WAL activation, and
    additive migrations single-file/single-writer across the whole host while
    leaving normal post-init DB usage concurrent under SQLite WAL.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    lock_path = path.with_name(path.name + ".init.lock")
    handle = lock_path.open("a+b")
    try:
        if _IS_WINDOWS:
            import msvcrt

            # Lock a single byte in the sidecar file. ``msvcrt.locking`` starts
            # at the current file position, so seek explicitly before both
            # lock and unlock.  The file is opened in append/read binary mode so
            # it always exists but the byte-range lock is the synchronization
            # primitive; no payload needs to be written.
            handle.seek(0)
            locking = getattr(msvcrt, "locking")
            lock_mode = getattr(msvcrt, "LK_LOCK")
            locking(handle.fileno(), lock_mode, 1)
        else:
            import fcntl

            fcntl.flock(handle.fileno(), fcntl.LOCK_EX)
        yield
    finally:
        try:
            if _IS_WINDOWS:
                import msvcrt

                handle.seek(0)
                locking = getattr(msvcrt, "locking")
                unlock_mode = getattr(msvcrt, "LK_UNLCK")
                locking(handle.fileno(), unlock_mode, 1)
            else:
                import fcntl

                fcntl.flock(handle.fileno(), fcntl.LOCK_UN)
        finally:
            handle.close()


def _looks_like_tls_record_at(data: bytes, offset: int) -> bool:
    """Return True for a TLS record header at ``data[offset:]``."""
    if len(data) < offset + 5:
        return False
    content_type = data[offset]
    major = data[offset + 1]
    minor = data[offset + 2]
    length = int.from_bytes(data[offset + 3:offset + 5], "big")
    return (
        content_type in {0x14, 0x15, 0x16, 0x17}
        and major == 0x03
        and minor in {0x00, 0x01, 0x02, 0x03, 0x04}
        and 0 < length <= 18432
    )


def _validate_sqlite_header(path: Path) -> None:
    """Fail early with an actionable error for non-SQLite Kanban DB files.

    ``sqlite3.connect()`` creates missing and zero-byte files, so those are
    allowed. Existing non-empty files must have the SQLite header before we
    hand them to SQLite/WAL setup. This keeps corrupted page-0 failures from
    being collapsed into a generic PRAGMA error and lets the gateway's corrupt
    board handling identify the board by fingerprint.
    """
    try:
        stat = path.stat()
    except FileNotFoundError:
        return
    except OSError:
        return
    if stat.st_size == 0:
        return
    try:
        with path.open("rb") as handle:
            head = handle.read(64)
    except OSError:
        return
    if head.startswith(_SQLITE_HEADER):
        return
    signature = ""
    if head.startswith(b"SQLit") and _looks_like_tls_record_at(head, 5):
        signature = " (TLS record header detected at byte offset 5)"
    elif _looks_like_tls_record_at(head, 0):
        signature = " (TLS record header detected at byte offset 0)"
    raise sqlite3.DatabaseError(
        "file is not a database: invalid SQLite header for "
        f"{path}{signature}; first_32={head[:32].hex(' ')}"
    )


class KanbanDbCorruptError(RuntimeError):
    """Raised when an existing kanban DB file fails integrity checks.

    Fail-closed guard against silent recreation of a corrupt board file,
    which would otherwise destroy the user's tasks. Carries both the
    original path and the timestamped backup we made before refusing.
    """

    def __init__(self, db_path: Path, backup_path: Optional[Path], reason: str):
        self.db_path = db_path
        self.backup_path = backup_path
        self.reason = reason
        backup_str = str(backup_path) if backup_path is not None else "<backup failed>"
        super().__init__(
            f"Refusing to open corrupt kanban DB at {db_path}: {reason}. "
            f"Original preserved; backup at {backup_str}."
        )


def _backup_corrupt_db(path: Path) -> Optional[Path]:
    """Copy a corrupt DB (and its WAL/SHM sidecars) to a content-addressed backup.

    The backup filename is deterministic in the main DB's sha256, so repeated
    quarantines of the same corrupt bytes (gateway restarts, dispatcher retries,
    multi-profile fleets all hitting the same shared DB) reuse one backup
    instead of amplifying disk usage by N. If the corrupt bytes actually
    change between attempts — e.g. a partial repair or further damage — the
    fingerprint changes and a separate backup is preserved.

    Returns the backup path of the main DB file, or ``None`` if the copy
    itself failed (the caller still raises loudly in that case).

    Writes are confined to the original DB's parent directory. The backup
    basename is derived purely from ``path.name`` and a content hash, never
    from caller-supplied directory segments — no traversal is possible.
    """
    # Resolve once and pin the parent so subsequent path operations cannot
    # escape it. ``Path.resolve()`` collapses any ``..`` segments and
    # symlinks, and we only ever write inside ``parent``.
    resolved = path.resolve()
    parent = resolved.parent
    base_name = resolved.name  # basename only
    digest = hashlib.sha256()
    try:
        with resolved.open("rb") as handle:
            for chunk in iter(lambda: handle.read(1024 * 1024), b""):
                digest.update(chunk)
    except OSError:
        return None
    token = digest.hexdigest()[:16]
    candidate = parent / f"{base_name}.corrupt.{token}.bak"
    # Defensive: candidate must still be inside parent after construction.
    if candidate.parent != parent:
        return None
    if not candidate.exists():
        try:
            shutil.copy2(resolved, candidate)
        except OSError:
            return None
    for suffix in ("-wal", "-shm"):
        sidecar = parent / (base_name + suffix)
        if sidecar.parent != parent or not sidecar.exists():
            continue
        sidecar_backup = parent / (candidate.name + suffix)
        if sidecar_backup.parent != parent or sidecar_backup.exists():
            continue
        try:
            shutil.copy2(sidecar, sidecar_backup)
        except OSError:
            pass
    return candidate


def _guard_existing_db_is_healthy(path: Path) -> None:
    """Run ``PRAGMA integrity_check`` on an existing non-empty DB file.

    Opens the probe in read/write mode so SQLite can recover or
    checkpoint a healthy WAL/hot-journal DB before we declare it
    corrupt. If the file is malformed, copy it (and any WAL/SHM
    sidecars) to a timestamped backup and raise
    :class:`KanbanDbCorruptError` so callers cannot silently recreate
    the schema on top of a damaged DB.

    Transient lock/busy errors (``sqlite3.OperationalError``) are NOT
    treated as corruption; they propagate raw so the caller sees a
    normal lock failure and no spurious ``.corrupt`` backup is made.

    No-op for missing files, zero-byte files (treated as fresh), and
    paths already proven healthy this process (cache hit).

    Path-trust note: ``path`` arrives via :func:`connect`, which itself
    resolves it from an explicit ``db_path`` argument, the
    :func:`kanban_db_path` env-var chain, or the kanban-home default —
    all sources Hermes treats as user-controlled-but-trusted on the
    user's own machine. We additionally resolve the path here and
    confine all filesystem writes to its parent directory so any
    accidental ``..`` segments are collapsed before any I/O happens.
    """
    # Resolve before any I/O. ``Path.resolve()`` normalizes ``..`` and
    # symlinks, giving us a canonical path whose parent dir we can pin.
    try:
        resolved = path.resolve()
    except OSError:
        return
    try:
        if not resolved.exists() or resolved.stat().st_size == 0:
            return
    except OSError:
        return
    if str(resolved) in _INITIALIZED_PATHS:
        return
    reason: Optional[str] = None
    try:
        probe = _sqlite_connect(resolved)
        try:
            row = probe.execute("PRAGMA integrity_check").fetchone()
        finally:
            probe.close()
        if not row or (row[0] or "").lower() != "ok":
            reason = f"integrity_check returned {row[0] if row else '<no row>'!r}"
    except sqlite3.OperationalError:
        # Lock contention, busy, transient IO — not corruption. Let it propagate.
        raise
    except sqlite3.DatabaseError as exc:
        reason = f"sqlite refused to open file: {exc}"
    if reason is None:
        return
    backup = _backup_corrupt_db(resolved)
    raise KanbanDbCorruptError(resolved, backup, reason)


def connect(
    db_path: Optional[Path] = None,
    *,
    board: Optional[str] = None,
) -> sqlite3.Connection:
    """Open (and initialize if needed) the kanban DB.

    WAL mode is enabled on every connection; it's a no-op after the first
    time but keeps the code robust if the DB file is ever re-created.

    The first connection to a given path auto-runs :func:`init_db` so
    fresh installs and test harnesses that construct `connect()`
    directly don't have to remember a separate init step. Subsequent
    connections skip the schema check via a module-level path cache.

    Path resolution:

    * ``db_path`` explicit → used as-is (legacy callers, tests).
    * ``board`` explicit → resolves to that board's DB.
    * Neither → :func:`kanban_db_path` resolves via
      ``HERMES_KANBAN_DB`` env → ``HERMES_KANBAN_BOARD`` env →
      ``<root>/kanban/current`` → ``default``.
    """
    if db_path is not None:
        path = db_path
    else:
        path = kanban_db_path(board=board)
    path.parent.mkdir(parents=True, exist_ok=True)
    with _cross_process_init_lock(path):
        # Cheap byte-level check first — catches the #29507 TLS-overwrite shape
        # and other invalid-header cases without opening a sqlite connection.
        _validate_sqlite_header(path)
        # Full integrity probe — catches corruption past the header (malformed
        # pages, broken internal metadata). Cached per-path after first success
        # via _INITIALIZED_PATHS so it only runs once per process per path.
        _guard_existing_db_is_healthy(path)
        resolved = str(path.resolve())
        conn = _sqlite_connect(path)
        try:
            conn.row_factory = sqlite3.Row
            # SCHEMA_SQL installs a fail-closed immutable-effect trigger before
            # the full Olympus guard set is available on a legacy database.
            # Register only its migration-state predicate up front so an exact
            # transactional identity remap can proceed; external connections
            # lack this UDF and therefore still fail closed.
            conn.create_function(
                "olympus_schema_migration_active",
                0,
                lambda: int(
                    int(getattr(conn, "_olympus_schema_migration_depth", 0)) > 0
                ),
            )
            with _INIT_LOCK:
                # WAL activation can take an exclusive lock while SQLite creates the
                # sidecar files for a fresh database. Keep it in the same process-local
                # critical section as schema initialization so concurrent gateway
                # startup threads do not race before _INITIALIZED_PATHS is populated.
                # WAL doesn't work on network filesystems (NFS/SMB/FUSE). Shared helper
                # falls back to DELETE with one WARNING so kanban stays usable there.
                # See hermes_state._WAL_INCOMPAT_MARKERS for detection logic.
                from hermes_state import apply_wal_with_fallback
                apply_wal_with_fallback(conn, db_label=f"kanban.db ({path.name})")
                # FULL (was NORMAL): fsync before each checkpoint to narrow the
                # crash window that can leave a b-tree page header torn.
                conn.execute("PRAGMA synchronous=FULL")
                conn.execute("PRAGMA wal_autocheckpoint=100")
                conn.execute("PRAGMA foreign_keys=ON")
                # Zero freed pages so a later torn write cannot expose stale
                # cell content; persisted in the DB header for new DBs.
                conn.execute("PRAGMA secure_delete=ON")
                # Surface corrupt cells as read errors instead of silent
                # wrong-data returns.
                conn.execute("PRAGMA cell_size_check=ON")
                needs_init = resolved not in _INITIALIZED_PATHS
                if needs_init:
                    # Idempotent: runs CREATE TABLE IF NOT EXISTS + the additive
                    # migrations. Cached so subsequent connect() calls in the same
                    # process are cheap. The lock prevents same-process dispatcher
                    # threads from racing through the additive ALTER TABLE pass with
                    # stale PRAGMA snapshots during gateway startup.
                    conn.executescript(SCHEMA_SQL)
                    # Persistent Olympus triggers survive process restart and
                    # call connection-local UDFs.  If this DB already has the
                    # guard, register those UDFs before any migration write;
                    # otherwise SQLite would fail with "no such function" (or,
                    # worse, a migration author might be tempted to drop the
                    # guard). Fresh legacy DBs have no guard and migrate first.
                    has_persistent_guard = conn.execute(
                        "SELECT 1 FROM sqlite_master WHERE type='trigger' "
                        "AND name='olympus_tasks_update_guard'"
                    ).fetchone() is not None
                    if has_persistent_guard:
                        _install_olympus_write_guard(conn)
                    _migrate_add_optional_columns(conn)
                    _INITIALIZED_PATHS.add(resolved)
                _install_olympus_write_guard(conn)
        except Exception:
            conn.close()
            raise
    return conn


def _olympus_telegram_journal_guard_sql(
    conn: sqlite3.Connection,
) -> str:
    """Build v3 journal guards only after their exact schemas exist.

    A pre-v3 WIP database can already have persistent task guards, which means
    :func:`connect` must register the general guard UDFs before migration.  It
    must not create v3 ``NEW.column`` triggers against the legacy Telegram
    table shape, however, because SQLite then cannot rename that table.  Schema
    migration preserves/replaces the legacy tables first; the second guard
    installation pass calls this helper again and installs these triggers.
    """
    expected = {
        "olympus_telegram_deliveries": {
            "delivery_key", "authorization_task_id",
            "authorization_task_revision", "task_id", "payload",
            "payload_sha256", "created_at",
        },
        "olympus_telegram_controls": {
            "operation_id", "action", "authorization_task_id",
            "authorization_task_revision", "target_task_id",
            "target_task_revision", "source_identity", "request_payload",
            "payload_sha256", "verification_id", "result_status",
            "effect_operation_id", "created_at",
        },
    }
    exact = {
        table: {
            row["name"]
            for row in conn.execute(f"PRAGMA table_info({table})")
        } == columns
        for table, columns in expected.items()
    }
    statements: list[str] = []
    if exact["olympus_telegram_deliveries"]:
        statements.extend((
            "CREATE TRIGGER olympus_telegram_delivery_insert_guard "
            "BEFORE INSERT ON olympus_telegram_deliveries "
            "WHEN olympus_telegram_delivery_insert_allowed("
            "NEW.delivery_key,NEW.authorization_task_id,"
            "NEW.authorization_task_revision,NEW.task_id,NEW.payload,"
            "NEW.payload_sha256,NEW.created_at) != 1 "
            "BEGIN SELECT RAISE(ABORT, "
            "'olympus_telegram_delivery_authority_required'); END;",
            "CREATE TRIGGER olympus_telegram_delivery_update_guard "
            "BEFORE UPDATE ON olympus_telegram_deliveries "
            "BEGIN SELECT RAISE(ABORT, "
            "'olympus_telegram_delivery_immutable'); END;",
            "CREATE TRIGGER olympus_telegram_delivery_delete_guard "
            "BEFORE DELETE ON olympus_telegram_deliveries "
            "BEGIN SELECT RAISE(ABORT, "
            "'olympus_telegram_delivery_immutable'); END;",
        ))
    if exact["olympus_telegram_controls"]:
        statements.extend((
            "CREATE TRIGGER olympus_telegram_control_insert_guard "
            "BEFORE INSERT ON olympus_telegram_controls "
            "WHEN olympus_telegram_control_insert_allowed("
            "NEW.operation_id,NEW.action,NEW.authorization_task_id,"
            "NEW.authorization_task_revision,NEW.target_task_id,"
            "NEW.target_task_revision,NEW.source_identity,"
            "NEW.request_payload,NEW.payload_sha256,NEW.verification_id,"
            "NEW.result_status,NEW.effect_operation_id,NEW.created_at) != 1 "
            "BEGIN SELECT RAISE(ABORT, "
            "'olympus_telegram_control_authority_required'); END;",
            "CREATE TRIGGER olympus_telegram_control_update_guard "
            "BEFORE UPDATE ON olympus_telegram_controls "
            "BEGIN SELECT RAISE(ABORT, "
            "'olympus_telegram_control_immutable'); END;",
            "CREATE TRIGGER olympus_telegram_control_delete_guard "
            "BEFORE DELETE ON olympus_telegram_controls "
            "BEGIN SELECT RAISE(ABORT, "
            "'olympus_telegram_control_immutable'); END;",
        ))
    return "\n".join(statements)


def _install_olympus_write_guard(conn: sqlite3.Connection) -> None:
    """Install persistent main-schema guards backed by process-local UDFs.

    The triggers live in ``sqlite_master``.  A plain external ``sqlite3``
    connection therefore reaches the same boundary but has no registered UDF
    and aborts instead of bypassing governance.  The permit itself never lives
    in SQL: it is one process-local exact revision/action/capability tuple.
    """
    registry = getattr(conn, "_olympus_permit_registry", None)
    if registry is None:
        raise RuntimeError("Kanban connection lacks process-local permit state")

    def _schema_migration_active() -> int:
        return int(int(getattr(conn, "_olympus_schema_migration_depth", 0)) > 0)

    def _guard_install_failpoint() -> int:
        hook = _OLYMPUS_GUARD_INSTALL_FAILPOINT
        if callable(hook):
            hook()
        return 0

    def _permit(task_id: Any):
        return registry.get(str(task_id))

    def _permit_write_binding(issued: Any) -> Optional[dict[str, Any]]:
        if issued is None or len(issued) < 8 or issued[7] is None:
            return None
        try:
            decoded = json.loads(str(issued[7]))
        except (TypeError, ValueError, json.JSONDecodeError):
            return None
        return decoded if isinstance(decoded, dict) else None

    def _permit_allows(
        task_id: Any, subject_revision: Any, capability: Any, actions_csv: Any,
    ) -> int:
        issued = _permit(task_id)
        if issued is None:
            return 0
        try:
            revision = int(subject_revision)
        except (TypeError, ValueError):
            return 0
        actions = {item for item in str(actions_csv).split(",") if item}
        return int(
            revision in {issued[0], issued[0] + 1}
            and issued[2] in actions
            and issued[3] == str(capability)
        )

    def _task_insert_allowed(
        task_id: Any, record_revision: Any, status: Any, assignee: Any,
        olympus_context: Any,
    ) -> int:
        issued = _permit(task_id)
        return int(
            issued is not None
            and issued[0] == 0
            and issued[2:4] == ("create", OLYMPUS_CAPABILITY_CREATE)
            and record_revision == 1
            and isinstance(status, str) and status in VALID_STATUSES
            and isinstance(assignee, str) and bool(assignee.strip())
            and isinstance(olympus_context, str) and bool(olympus_context)
        )

    def _columns_allowed(
        mapping: Mapping[tuple[str, str], frozenset[str]],
        columns: tuple[str, ...], task_id: Any, subject_revision: Any,
        values: tuple[Any, ...],
    ) -> int:
        issued = _permit(task_id)
        if issued is None or len(values) != 2 * len(columns):
            return 0
        try:
            if int(subject_revision) not in {issued[0], issued[0] + 1}:
                return 0
        except (TypeError, ValueError):
            return 0
        allowed = mapping.get((issued[2], issued[3]))
        if allowed is None:
            return 0
        changed = {
            column
            for index, column in enumerate(columns)
            if values[index * 2] != values[index * 2 + 1]
        }
        return int(changed.issubset(allowed))

    def _task_update_allowed(task_id: Any, subject_revision: Any, *values: Any) -> int:
        return _columns_allowed(
            _OLYMPUS_TASK_WRITE_COLUMNS, _OLYMPUS_TASK_MUTABLE_COLUMNS,
            task_id, subject_revision, values,
        )

    def _revision_advance_allowed(
        task_id: Any, old_revision: Any, new_revision: Any, *values: Any,
    ) -> int:
        """Admit only the trigger-generated one-step revision CAS.

        The AFTER UPDATE revision trigger necessarily re-enters the persistent
        BEFORE UPDATE guard.  Its second statement is safe only when the exact
        verified permit still binds the old revision and no task payload column
        changes in that statement.
        """
        issued = _permit(task_id)
        if issued is None or len(values) != 2 * len(_OLYMPUS_TASK_MUTABLE_COLUMNS):
            return 0
        try:
            exact_revision = (
                issued[0] == int(old_revision)
                and int(new_revision) == int(old_revision) + 1
            )
        except (TypeError, ValueError):
            return 0
        unchanged = all(
            values[index * 2] == values[index * 2 + 1]
            for index in range(len(_OLYMPUS_TASK_MUTABLE_COLUMNS))
        )
        return int(exact_revision and unchanged)

    def _run_update_allowed(task_id: Any, subject_revision: Any, *values: Any) -> int:
        allowed = _columns_allowed(
            _OLYMPUS_RUN_WRITE_COLUMNS, _OLYMPUS_RUN_MUTABLE_COLUMNS,
            task_id, subject_revision, values,
        )
        issued = _permit(task_id)
        if not allowed or issued is None or issued[2] != "register_worker_process":
            return allowed
        binding = _permit_write_binding(issued)
        dispatcher_index = _OLYMPUS_RUN_MUTABLE_COLUMNS.index(
            "dispatcher_instance_id"
        )
        return int(
            binding == {
                "schema_version": WORKER_REGISTRATION_WRITE_SCHEMA,
                "action": "register_worker_process",
                "task_id": str(task_id),
                "task_record_revision": int(issued[0]),
                "dispatcher_instance_id": values[dispatcher_index * 2 + 1],
            }
        )

    def _run_insert_allowed(
        task_id: Any, subject_revision: Any, olympus_context: Any,
        auth_root_id: Any, auth_root_revision: Any, verification_id: Any,
        process_state: Any, launch_token: Any,
    ) -> int:
        issued = _permit(task_id)
        if issued is None:
            return 0
        allowed = _OLYMPUS_RUN_WRITE_COLUMNS.get((issued[2], issued[3]))
        try:
            exact = (
                issued[0] == int(subject_revision)
                and issued[4] == str(auth_root_id)
                and issued[5] == int(auth_root_revision)
                and issued[6] == str(verification_id)
            )
        except (TypeError, ValueError):
            return 0
        return int(
            exact and allowed is not None and "__insert__" in allowed
            and isinstance(olympus_context, str) and bool(olympus_context)
            and process_state in {"workspace_pending", "terminal"}
            and (
                process_state == "terminal"
                or (isinstance(launch_token, str) and bool(launch_token))
            )
        )

    def _task_should_advance(
        task_id: Any, subject_revision: Any, *values: Any,
    ) -> int:
        if not _task_update_allowed(task_id, subject_revision, *values):
            return 0
        issued = _permit(task_id)
        try:
            if issued is None or int(subject_revision) != issued[0]:
                return 0
        except (TypeError, ValueError):
            return 0
        changed = any(
            values[index * 2] != values[index * 2 + 1]
            for index in range(len(_OLYMPUS_TASK_MUTABLE_COLUMNS))
        )
        return int(changed or (issued is not None and issued[2] in _OLYMPUS_FORCE_TOUCH_ACTIONS))

    def _audit_allowed(task_id: Any, run_id: Any, kind: Any, payload: Any, created_at: Any) -> int:
        audit_registry = getattr(conn, "_olympus_audit_registry", set())
        key = (
            str(task_id), int(run_id) if run_id is not None else None,
            str(kind), str(payload) if payload is not None else None,
            int(created_at),
        )
        if str(kind) in _OLYMPUS_PROTECTED_AUDIT_KINDS:
            return int(key in audit_registry)
        return int(_permit(task_id) is not None)

    def _notify_insert_allowed(
        task_id: Any, platform: Any, chat_id: Any, thread_id: Any,
        user_id: Any, notifier_profile: Any, created_at: Any,
        last_event_id: Any,
    ) -> int:
        issued = _permit(task_id)
        binding = _permit_write_binding(issued)
        if issued is None or binding is None:
            return 0
        try:
            exact = (
                issued[2:4] == (
                    "add_notification_subscription", OLYMPUS_CAPABILITY_NOTIFY,
                )
                and binding == {
                    "schema_version": NOTIFICATION_SUBSCRIPTION_OPERATION_SCHEMA,
                    "action": "add_notification_subscription",
                    "board_id": _connection_board_identity(conn),
                    "task_id": str(task_id),
                    "task_record_revision": int(issued[0]),
                    "platform": platform,
                    "chat_id": chat_id,
                    "thread_id": thread_id,
                    "user_id": user_id,
                    "notifier_profile": notifier_profile,
                }
                and isinstance(created_at, int)
                and created_at >= 0
                and isinstance(last_event_id, int)
                and last_event_id == 0
            )
        except (TypeError, ValueError):
            return 0
        return int(exact)

    def _notifier_row_matches(
        binding: Optional[dict[str, Any]],
        *,
        task_id: Any,
        platform: Any,
        chat_id: Any,
        thread_id: Any,
        user_id: Any,
        notifier_profile: Any,
        created_at: Any,
        last_event_id: Any,
    ) -> bool:
        if binding is None:
            return False
        return bool(
            binding.get("task_id") == str(task_id)
            and binding.get("platform") == platform
            and binding.get("chat_id") == chat_id
            and binding.get("thread_id") == thread_id
            and binding.get("user_id") == user_id
            and binding.get("notifier_profile") == notifier_profile
            and binding.get("created_at") == created_at
            and binding.get("last_event_id") == last_event_id
        )

    def _notify_update_allowed(
        old_task_id: Any, old_platform: Any, old_chat_id: Any,
        old_thread_id: Any, old_user_id: Any, old_notifier_profile: Any,
        old_created_at: Any, old_last_event_id: Any,
        new_task_id: Any, new_platform: Any, new_chat_id: Any,
        new_thread_id: Any, new_user_id: Any, new_notifier_profile: Any,
        new_created_at: Any, new_last_event_id: Any,
    ) -> int:
        issued = _permit(old_task_id)
        binding = _permit_write_binding(issued)
        if issued is None or issued[3] != OLYMPUS_CAPABILITY_NOTIFY:
            return 0
        action = issued[2]
        if action not in {
            "claim_notification_delivery", "advance_notification_cursor",
            "rewind_notification_cursor",
        }:
            return 0
        if not _notifier_row_matches(
            binding,
            task_id=old_task_id,
            platform=old_platform,
            chat_id=old_chat_id,
            thread_id=old_thread_id,
            user_id=old_user_id,
            notifier_profile=old_notifier_profile,
            created_at=old_created_at,
            last_event_id=old_last_event_id,
        ):
            return 0
        immutable = (
            new_task_id == old_task_id
            and new_platform == old_platform
            and new_chat_id == old_chat_id
            and new_thread_id == old_thread_id
            and new_user_id == old_user_id
            and new_notifier_profile == old_notifier_profile
            and new_created_at == old_created_at
        )
        if not immutable:
            return 0
        try:
            old_cursor = int(old_last_event_id)
            new_cursor = int(new_last_event_id)
        except (TypeError, ValueError):
            return 0
        if action == "rewind_notification_cursor":
            return int(new_cursor <= old_cursor)
        return int(new_cursor >= old_cursor)

    def _notify_delete_allowed(
        task_id: Any, platform: Any, chat_id: Any, thread_id: Any,
        user_id: Any, notifier_profile: Any, created_at: Any,
        last_event_id: Any,
    ) -> int:
        issued = _permit(task_id)
        if (
            issued is None
            or issued[2:4] != (
                "remove_notification_subscription", OLYMPUS_CAPABILITY_NOTIFY,
            )
        ):
            return 0
        return int(_notifier_row_matches(
            _permit_write_binding(issued),
            task_id=task_id,
            platform=platform,
            chat_id=chat_id,
            thread_id=thread_id,
            user_id=user_id,
            notifier_profile=notifier_profile,
            created_at=created_at,
            last_event_id=last_event_id,
        ))

    def _canonical_receipt_payload(
        payload: Any, payload_sha256: Any,
    ) -> Optional[dict[str, Any]]:
        if not isinstance(payload, str) or not isinstance(payload_sha256, str):
            return None
        if hashlib.sha256(payload.encode("utf-8")).hexdigest() != payload_sha256:
            return None
        try:
            decoded = json.loads(payload)
        except (TypeError, ValueError, json.JSONDecodeError):
            return None
        if not isinstance(decoded, dict):
            return None
        canonical = json.dumps(
            decoded, sort_keys=True, separators=(",", ":"), allow_nan=False,
        )
        return decoded if canonical == payload else None

    def _create_receipt_insert_allowed(
        idempotency_key: Any, task_id: Any, payload: Any,
        payload_sha256: Any, created_at: Any,
    ) -> int:
        issued = _permit(task_id)
        decoded = _canonical_receipt_payload(payload, payload_sha256)
        binding = _permit_write_binding(issued)
        return int(
            issued is not None
            and issued[0] == 0
            and issued[2:4] == ("create", OLYMPUS_CAPABILITY_CREATE)
            and decoded is not None
            and decoded.get("schema_version") == "olympus-task-create-request/1"
            and decoded.get("idempotency_key") == idempotency_key
            and decoded.get("task_id") == task_id
            and isinstance(created_at, int)
            and created_at >= 0
            and binding == {
                "schema_version": CREATE_RECEIPT_WRITE_SCHEMA,
                "idempotency_key": idempotency_key,
                "task_id": task_id,
                "payload": payload,
                "payload_sha256": payload_sha256,
                "created_at": created_at,
            }
        )

    def _release_receipt_insert_allowed(
        operation_id: Any, task_id: Any, subject_revision: Any,
        record_revision: Any, verification_id: Any, request_id: Any,
        receipt: Any, receipt_sha256: Any, created_at: Any,
    ) -> int:
        issued = _permit(task_id)
        decoded = _canonical_receipt_payload(receipt, receipt_sha256)
        binding = _permit_write_binding(issued)
        try:
            exact = (
                issued is not None
                and issued[2:4] == (
                    "release_blocked_task", OLYMPUS_CAPABILITY_RELEASE,
                )
                and issued[0] == int(subject_revision)
                and int(record_revision) == issued[0] + 1
                and str(operation_id) == issued[1]
                and str(verification_id) == issued[6]
                and decoded is not None
                and decoded.get("schema_version") == "olympus-task-release-receipt/1"
                and decoded.get("operation_id") == operation_id
                and decoded.get("task_id") == task_id
                and decoded.get("previous_revision") == int(subject_revision)
                and decoded.get("record_revision") == int(record_revision)
                and decoded.get("verification_id") == verification_id
                and decoded.get("request_id") == request_id
                and isinstance(created_at, int)
                and created_at >= 0
                and binding == {
                    "schema_version": RELEASE_RECEIPT_WRITE_SCHEMA,
                    "operation_id": operation_id,
                    "task_id": task_id,
                    "subject_revision": int(subject_revision),
                    "record_revision": int(record_revision),
                    "verification_id": verification_id,
                    "request_id": request_id,
                    "receipt": receipt,
                    "receipt_sha256": receipt_sha256,
                    "created_at": created_at,
                }
            )
        except (TypeError, ValueError):
            return 0
        return int(exact)

    def _telegram_delivery_insert_allowed(
        delivery_key: Any, authorization_task_id: Any,
        authorization_task_revision: Any, task_id: Any, payload: Any,
        payload_sha256: Any, created_at: Any,
    ) -> int:
        issued = _permit(authorization_task_id)
        binding = _permit_write_binding(issued)
        try:
            exact = (
                issued is not None
                and issued[2:4] == (
                    "telegram-intake", TELEGRAM_ACTION_CAPABILITIES["telegram-intake"],
                )
                and issued[0] == int(authorization_task_revision)
                and binding == {
                    "schema_version": TELEGRAM_DELIVERY_WRITE_SCHEMA,
                    "action": "telegram-intake",
                    "task_id": str(authorization_task_id),
                    "task_record_revision": int(authorization_task_revision),
                    "delivery_key": delivery_key,
                    "authorization_task_id": authorization_task_id,
                    "authorization_task_revision": int(
                        authorization_task_revision
                    ),
                    "created_task_id": task_id,
                    "payload": payload,
                    "payload_sha256": payload_sha256,
                    "created_at": int(created_at),
                }
            )
        except (TypeError, ValueError):
            return 0
        return int(exact)

    def _telegram_control_insert_allowed(
        operation_id: Any, action: Any, authorization_task_id: Any,
        authorization_task_revision: Any, target_task_id: Any,
        target_task_revision: Any, source_identity: Any,
        request_payload: Any, payload_sha256: Any, verification_id: Any,
        result_status: Any, effect_operation_id: Any, created_at: Any,
    ) -> int:
        issued = _permit(target_task_id)
        binding = _permit_write_binding(issued)
        try:
            exact = (
                issued is not None
                and issued[2] == action
                and issued[3] == TELEGRAM_ACTION_CAPABILITIES.get(str(action))
                and issued[0] == int(target_task_revision)
                and issued[6] == verification_id
                and binding == {
                    "schema_version": TELEGRAM_CONTROL_WRITE_SCHEMA,
                    "action": action,
                    "task_id": str(target_task_id),
                    "task_record_revision": int(target_task_revision),
                    "operation_id": operation_id,
                    "authorization_task_id": authorization_task_id,
                    "authorization_task_revision": int(
                        authorization_task_revision
                    ),
                    "source_identity": source_identity,
                    "request_payload": request_payload,
                    "payload_sha256": payload_sha256,
                    "result_status": result_status,
                    "effect_operation_id": effect_operation_id,
                    "created_at": int(created_at),
                }
            )
        except (TypeError, ValueError):
            return 0
        return int(exact)

    def _notifier_effect_matches(
        issued: Any, *, task_id: Any, event_id: Any,
        operation_id: Any, destination_key: Any, effect_state: Any,
    ) -> bool:
        binding = _permit_write_binding(issued)
        if binding is None:
            return False
        if binding.get("schema_version") == NOTIFIER_MUTATION_WRITE_SCHEMA:
            binding = binding.get("notifier")
        if not isinstance(binding, dict):
            return False
        expected_destination = ":".join((
            str(binding.get("platform", "")),
            str(binding.get("chat_id", "")),
            str(binding.get("thread_id") or ""),
        ))
        return bool(
            binding.get("task_id") == str(task_id)
            and binding.get("source_event_id") == event_id
            and binding.get("effect_id") == operation_id
            and binding.get("effect_state") == effect_state
            and destination_key == expected_destination
        )

    def _effect_insert_allowed(
        task_id: Any, state: Any, effect_kind: Any, auth_root_id: Any,
        auth_root_revision: Any, target_pre_revision: Any,
        target_post_revision: Any, run_id: Any, event_id: Any,
        operation_id: Any, destination_key: Any, part: Any,
        worker_host_id: Any, worker_boot_id: Any, worker_pid: Any,
        worker_start_token: Any, source_identity: Any, payload: Any,
        payload_sha256: Any,
    ) -> int:
        issued = _permit(task_id)
        if issued is None or state != "pending":
            return 0
        expected = {
            "terminate_worker": {"stage_worker_termination"},
            "notify_text": {"reserve_notification_effect"},
            "notify_artifact": {"reserve_notification_effect"},
        }.get(str(effect_kind), set())
        try:
            exact_authority = (
                str(auth_root_id) == issued[4]
                and int(auth_root_revision) == issued[5]
                and int(target_pre_revision) == issued[0]
            )
        except (TypeError, ValueError):
            return 0
        common = (
            exact_authority
            and issued[2] in expected
            and isinstance(operation_id, str) and bool(operation_id)
            and isinstance(source_identity, str) and bool(source_identity)
            and isinstance(payload, str) and bool(payload)
            and isinstance(payload_sha256, str)
            and bool(re.fullmatch(r"[0-9a-f]{64}", payload_sha256))
        )
        if not common:
            return 0
        if effect_kind == "terminate_worker":
            return int(
                int(target_post_revision) in {issued[0], issued[0] + 1}
                and run_id is not None and event_id is None
                and destination_key is None and part is None
                and isinstance(worker_host_id, str) and bool(worker_host_id)
                and isinstance(worker_boot_id, str) and bool(worker_boot_id)
                and isinstance(worker_pid, int) and worker_pid > 0
                and isinstance(worker_start_token, str) and bool(worker_start_token)
            )
        binding = _permit_write_binding(issued)
        mutation = (
            binding.get("mutation")
            if isinstance(binding, dict)
            and binding.get("schema_version") == NOTIFIER_MUTATION_WRITE_SCHEMA
            else None
        )
        try:
            decoded_source = json.loads(source_identity)
            canonical_source = json.dumps(
                decoded_source, sort_keys=True, separators=(",", ":"),
                ensure_ascii=False, allow_nan=False,
            )
            decoded_payload = json.loads(payload)
            canonical_payload = json.dumps(
                decoded_payload, sort_keys=True, separators=(",", ":"),
                ensure_ascii=False, allow_nan=False,
            )
        except (TypeError, ValueError, json.JSONDecodeError):
            return 0
        exact_effect = {
            "schema_version": NOTIFICATION_EFFECT_RESERVATION_SCHEMA,
            "action": "reserve_notification_effect",
            "task_id": str(task_id),
            "task_record_revision": int(issued[0]),
            "effect_kind": effect_kind,
            "operation_id": operation_id,
            "event_id": event_id,
            "destination_key": destination_key,
            "part": part,
            "source_identity": source_identity,
            "payload": payload,
            "payload_sha256": payload_sha256,
            "target_post_revision": target_post_revision,
        }
        return int(
            run_id is None and isinstance(event_id, int) and event_id > 0
            and isinstance(destination_key, str) and bool(destination_key)
            and isinstance(part, str) and bool(part)
            and worker_host_id is None and worker_boot_id is None
            and worker_pid is None and worker_start_token is None
            and int(target_post_revision) == issued[0]
            and canonical_source == source_identity
            and canonical_payload == payload
            and hashlib.sha256(payload.encode("utf-8")).hexdigest()
                == payload_sha256
            and mutation == exact_effect
            and _notifier_effect_matches(
                issued,
                task_id=task_id,
                event_id=event_id,
                operation_id=operation_id,
                destination_key=destination_key,
                effect_state="unreserved",
            )
        )

    def _effect_update_allowed(
        task_id: Any, effect_row_id: Any, effect_kind: Any,
        old_state: Any, new_state: Any, event_id: Any, operation_id: Any,
        destination_key: Any, old_error: Any, new_error: Any,
        old_updated_at: Any, new_updated_at: Any,
        old_applied_at: Any, new_applied_at: Any,
    ) -> int:
        issued = _permit(task_id)
        if issued is None:
            return 0
        transition = (str(old_state), str(new_state))
        action = issued[2]
        allowed = {
            "claim_notification_effect": {("pending", "applying")},
            "execute_worker_termination_effect": {
                ("pending", "applying"), ("applying", "applied"),
                ("applying", "gone"), ("applying", "unknown"),
                ("applying", "failed"),
                ("applying", "identity_mismatch"),
                ("applying", "identity_unverified"),
            },
            "finish_notification_effect": {
                ("applying", "applied"), ("applying", "not_sent"),
                ("applying", "unknown"),
            },
            "reconcile_effect_journal": {
                ("applying", "unknown"), ("applying", "gone"),
                ("applying", "identity_mismatch"),
                ("applying", "identity_unverified"),
            },
            "settle_worker_termination": {
                ("applying", "applied"), ("applying", "gone"),
                ("applying", "unknown"), ("applied", "gone"),
                ("applied", "identity_mismatch"),
            },
        }.get(action, set())
        if str(effect_kind).startswith("notify_") and action.startswith("execute_worker"):
            return 0
        if action in {"claim_notification_effect", "finish_notification_effect"}:
            if not _notifier_effect_matches(
                issued,
                task_id=task_id,
                event_id=event_id,
                operation_id=operation_id,
                destination_key=destination_key,
                effect_state=old_state,
            ):
                return 0
            binding = _permit_write_binding(issued)
            mutation = (
                binding.get("mutation")
                if isinstance(binding, dict)
                and binding.get("schema_version") == NOTIFIER_MUTATION_WRITE_SCHEMA
                else None
            )
            exact_transition = {
                "schema_version": NOTIFICATION_EFFECT_TRANSITION_SCHEMA,
                "action": action,
                "task_id": str(task_id),
                "task_record_revision": int(issued[0]),
                "effect_row_id": effect_row_id,
                "effect_kind": effect_kind,
                "operation_id": operation_id,
                "event_id": event_id,
                "destination_key": destination_key,
                "old_state": old_state,
                "new_state": new_state,
                "error": new_error,
                "updated_at": new_updated_at,
                "applied_at": new_applied_at,
            }
            return int(
                transition in allowed
                and mutation == exact_transition
                and new_updated_at >= old_updated_at
            )
        evidence_unchanged = (
            new_error == old_error and new_applied_at == old_applied_at
        )
        if action == "reconcile_effect_journal" and not evidence_unchanged:
            return 0
        return int(transition in allowed and new_updated_at >= old_updated_at)

    conn.create_function("olympus_permit_allows", 4, _permit_allows)
    conn.create_function("olympus_task_insert_allowed", 5, _task_insert_allowed)
    conn.create_function("olympus_task_update_allowed", -1, _task_update_allowed)
    conn.create_function(
        "olympus_revision_advance_allowed", -1, _revision_advance_allowed
    )
    conn.create_function("olympus_task_should_advance", -1, _task_should_advance)
    conn.create_function("olympus_run_insert_allowed", 8, _run_insert_allowed)
    conn.create_function("olympus_run_update_allowed", -1, _run_update_allowed)
    conn.create_function("olympus_audit_allowed", 5, _audit_allowed)
    conn.create_function("olympus_notify_insert_allowed", 8, _notify_insert_allowed)
    conn.create_function("olympus_notify_update_allowed", 16, _notify_update_allowed)
    conn.create_function("olympus_notify_delete_allowed", 8, _notify_delete_allowed)
    conn.create_function(
        "olympus_create_receipt_insert_allowed", 5,
        _create_receipt_insert_allowed,
    )
    conn.create_function(
        "olympus_release_receipt_insert_allowed", 9,
        _release_receipt_insert_allowed,
    )
    conn.create_function(
        "olympus_telegram_delivery_insert_allowed", 7,
        _telegram_delivery_insert_allowed,
    )
    conn.create_function(
        "olympus_telegram_control_insert_allowed", 13,
        _telegram_control_insert_allowed,
    )
    conn.create_function("olympus_effect_insert_allowed", 19, _effect_insert_allowed)
    conn.create_function("olympus_effect_update_allowed", 14, _effect_update_allowed)
    conn.create_function(
        "olympus_schema_migration_active", 0, _schema_migration_active
    )
    conn.create_function(
        "olympus_guard_install_failpoint", 0, _guard_install_failpoint
    )
    task_values = ", ".join(
        f"OLD.{column}, NEW.{column}" for column in _OLYMPUS_TASK_MUTABLE_COLUMNS
    )
    run_values = ", ".join(
        f"OLD.{column}, NEW.{column}" for column in _OLYMPUS_RUN_MUTABLE_COLUMNS
    )
    telegram_guard_sql = _olympus_telegram_journal_guard_sql(conn)
    script = f"""
        BEGIN IMMEDIATE;
        DROP TRIGGER IF EXISTS effect_journal_immutable;
        DROP TRIGGER IF EXISTS olympus_tasks_insert_guard;
        DROP TRIGGER IF EXISTS olympus_tasks_update_guard;
        DROP TRIGGER IF EXISTS olympus_tasks_opt_in_guard;
        DROP TRIGGER IF EXISTS olympus_tasks_revision_advance;
        DROP TRIGGER IF EXISTS olympus_tasks_delete_guard;
        DROP TRIGGER IF EXISTS olympus_links_insert_guard;
        DROP TRIGGER IF EXISTS olympus_links_delete_guard;
        DROP TRIGGER IF EXISTS olympus_links_update_guard;
        DROP TRIGGER IF EXISTS olympus_comments_insert_guard;
        DROP TRIGGER IF EXISTS olympus_comments_delete_guard;
        DROP TRIGGER IF EXISTS olympus_comments_update_guard;
        DROP TRIGGER IF EXISTS olympus_attachments_insert_guard;
        DROP TRIGGER IF EXISTS olympus_attachments_delete_guard;
        DROP TRIGGER IF EXISTS olympus_attachments_update_guard;
        DROP TRIGGER IF EXISTS olympus_notify_insert_guard;
        DROP TRIGGER IF EXISTS olympus_notify_update_guard;
        DROP TRIGGER IF EXISTS olympus_notify_delete_guard;
        DROP TRIGGER IF EXISTS olympus_create_receipt_insert_guard;
        DROP TRIGGER IF EXISTS olympus_create_receipt_update_guard;
        DROP TRIGGER IF EXISTS olympus_create_receipt_delete_guard;
        DROP TRIGGER IF EXISTS olympus_release_receipt_insert_guard;
        DROP TRIGGER IF EXISTS olympus_release_receipt_update_guard;
        DROP TRIGGER IF EXISTS olympus_release_receipt_delete_guard;
        DROP TRIGGER IF EXISTS olympus_telegram_delivery_insert_guard;
        DROP TRIGGER IF EXISTS olympus_telegram_delivery_update_guard;
        DROP TRIGGER IF EXISTS olympus_telegram_delivery_delete_guard;
        DROP TRIGGER IF EXISTS olympus_telegram_control_insert_guard;
        DROP TRIGGER IF EXISTS olympus_telegram_control_update_guard;
        DROP TRIGGER IF EXISTS olympus_telegram_control_delete_guard;
        DROP TRIGGER IF EXISTS olympus_runs_insert_guard;
        DROP TRIGGER IF EXISTS olympus_runs_update_guard;
        DROP TRIGGER IF EXISTS olympus_runs_delete_guard;
        DROP TRIGGER IF EXISTS olympus_events_insert_guard;
        DROP TRIGGER IF EXISTS olympus_events_update_guard;
        DROP TRIGGER IF EXISTS olympus_events_delete_guard;
        DROP TRIGGER IF EXISTS olympus_effects_insert_guard;
        DROP TRIGGER IF EXISTS olympus_effects_update_guard;
        DROP TRIGGER IF EXISTS olympus_effects_delete_guard;

        SELECT olympus_guard_install_failpoint();

        CREATE TRIGGER effect_journal_immutable
        BEFORE UPDATE ON kanban_effect_journal
        WHEN olympus_schema_migration_active() != 1 AND (
          NEW.effect_kind IS NOT OLD.effect_kind
          OR NEW.operation_id IS NOT OLD.operation_id
          OR NEW.task_id IS NOT OLD.task_id
          OR NEW.run_id IS NOT OLD.run_id
          OR NEW.event_id IS NOT OLD.event_id
          OR NEW.destination_key IS NOT OLD.destination_key
          OR NEW.part IS NOT OLD.part
          OR NEW.auth_root_id IS NOT OLD.auth_root_id
          OR NEW.auth_root_revision IS NOT OLD.auth_root_revision
          OR NEW.target_pre_revision IS NOT OLD.target_pre_revision
          OR NEW.target_post_revision IS NOT OLD.target_post_revision
          OR NEW.worker_host_id IS NOT OLD.worker_host_id
          OR NEW.worker_boot_id IS NOT OLD.worker_boot_id
          OR NEW.worker_pid IS NOT OLD.worker_pid
          OR NEW.worker_start_token IS NOT OLD.worker_start_token
          OR NEW.source_identity IS NOT OLD.source_identity
          OR NEW.payload IS NOT OLD.payload
          OR NEW.payload_sha256 IS NOT OLD.payload_sha256
          OR NEW.created_at IS NOT OLD.created_at
        )
        BEGIN SELECT RAISE(ABORT, 'kanban_effect_identity_immutable'); END;

        CREATE TRIGGER olympus_tasks_insert_guard BEFORE INSERT ON tasks
        WHEN NEW.olympus_context IS NOT NULL AND olympus_task_insert_allowed(
            NEW.id, NEW.record_revision, NEW.status, NEW.assignee,
            NEW.olympus_context
        ) != 1
        BEGIN SELECT RAISE(ABORT, 'olympus_authority_required'); END;

        CREATE TRIGGER olympus_tasks_opt_in_guard BEFORE UPDATE ON tasks
        WHEN OLD.olympus_context IS NULL AND NEW.olympus_context IS NOT NULL
        BEGIN SELECT RAISE(ABORT, 'olympus_legacy_opt_in_forbidden'); END;

        CREATE TRIGGER olympus_tasks_update_guard BEFORE UPDATE ON tasks
        WHEN OLD.olympus_context IS NOT NULL
         AND olympus_schema_migration_active() != 1
        BEGIN
            SELECT CASE WHEN NEW.id != OLD.id
                THEN RAISE(ABORT, 'olympus_task_identity_change_forbidden') END;
            SELECT CASE WHEN NEW.olympus_context IS NULL
                THEN RAISE(ABORT, 'olympus_governance_downgrade_forbidden') END;
            SELECT CASE WHEN OLD.record_revision != NEW.record_revision
                AND olympus_revision_advance_allowed(
                    OLD.id, OLD.record_revision, NEW.record_revision, {task_values}
                ) != 1
                THEN RAISE(ABORT, 'olympus_subject_revision_invalid') END;
            SELECT CASE WHEN OLD.record_revision = NEW.record_revision
                AND olympus_task_update_allowed(
                OLD.id, OLD.record_revision, {task_values}
            ) != 1 THEN RAISE(ABORT, 'olympus_authority_required') END;
        END;

        CREATE TRIGGER olympus_tasks_revision_advance AFTER UPDATE ON tasks
        WHEN OLD.olympus_context IS NOT NULL
         AND olympus_schema_migration_active() != 1
         AND NEW.record_revision = OLD.record_revision
         AND olympus_task_should_advance(
             OLD.id, OLD.record_revision, {task_values}
         ) = 1
        BEGIN
            UPDATE tasks SET record_revision = OLD.record_revision + 1
             WHERE id = OLD.id AND record_revision = OLD.record_revision;
        END;

        CREATE TRIGGER olympus_tasks_delete_guard BEFORE DELETE ON tasks
        WHEN OLD.olympus_context IS NOT NULL AND olympus_permit_allows(
            OLD.id, OLD.record_revision, 'kanban.task.delete',
            'delete,delete_archived'
        ) != 1
        BEGIN SELECT RAISE(ABORT, 'olympus_authority_required'); END;

        CREATE TRIGGER olympus_links_insert_guard BEFORE INSERT ON task_links
        WHEN (
            EXISTS (SELECT 1 FROM tasks WHERE id=NEW.parent_id AND olympus_context IS NOT NULL)
            AND olympus_permit_allows(NEW.parent_id,
                (SELECT record_revision FROM tasks WHERE id=NEW.parent_id),
                'kanban.task.link','link,link_governed_child') != 1
        ) OR (
            EXISTS (SELECT 1 FROM tasks WHERE id=NEW.child_id AND olympus_context IS NOT NULL)
            AND olympus_permit_allows(NEW.child_id,
                (SELECT record_revision FROM tasks WHERE id=NEW.child_id),
                'kanban.task.link','link,link_governed_child') != 1
        )
        BEGIN SELECT RAISE(ABORT, 'olympus_link_authority_required'); END;

        CREATE TRIGGER olympus_links_delete_guard BEFORE DELETE ON task_links
        WHEN EXISTS (
            SELECT 1 FROM tasks t WHERE t.id IN (OLD.parent_id,OLD.child_id)
             AND t.olympus_context IS NOT NULL
             AND olympus_permit_allows(t.id,t.record_revision,'kanban.task.link',
                 'unlink,unlink_deleted_task') != 1
             AND olympus_permit_allows(t.id,t.record_revision,'kanban.task.delete',
                 'delete,delete_archived') != 1
        )
        BEGIN SELECT RAISE(ABORT, 'olympus_link_authority_required'); END;

        CREATE TRIGGER olympus_links_update_guard BEFORE UPDATE ON task_links
        WHEN EXISTS (SELECT 1 FROM tasks t WHERE t.id IN (
            OLD.parent_id,OLD.child_id,NEW.parent_id,NEW.child_id
        ) AND t.olympus_context IS NOT NULL)
        BEGIN SELECT RAISE(ABORT, 'olympus_link_update_forbidden'); END;

        CREATE TRIGGER olympus_comments_insert_guard BEFORE INSERT ON task_comments
        WHEN EXISTS (SELECT 1 FROM tasks WHERE id=NEW.task_id AND olympus_context IS NOT NULL)
         AND olympus_permit_allows(NEW.task_id,
             (SELECT record_revision FROM tasks WHERE id=NEW.task_id),
             'kanban.task.comment','comment') != 1
        BEGIN SELECT RAISE(ABORT, 'olympus_comment_authority_required'); END;
        CREATE TRIGGER olympus_comments_update_guard BEFORE UPDATE ON task_comments
        WHEN EXISTS (SELECT 1 FROM tasks WHERE id IN (OLD.task_id,NEW.task_id)
            AND olympus_context IS NOT NULL)
        BEGIN SELECT RAISE(ABORT, 'olympus_comment_update_forbidden'); END;
        CREATE TRIGGER olympus_comments_delete_guard BEFORE DELETE ON task_comments
        WHEN EXISTS (SELECT 1 FROM tasks WHERE id=OLD.task_id AND olympus_context IS NOT NULL)
         AND olympus_permit_allows(OLD.task_id,
             (SELECT record_revision FROM tasks WHERE id=OLD.task_id),
             'kanban.task.delete','delete,delete_archived') != 1
        BEGIN SELECT RAISE(ABORT, 'olympus_comment_authority_required'); END;

        CREATE TRIGGER olympus_attachments_insert_guard BEFORE INSERT ON task_attachments
        WHEN EXISTS (SELECT 1 FROM tasks WHERE id=NEW.task_id AND olympus_context IS NOT NULL)
         AND olympus_permit_allows(NEW.task_id,
             (SELECT record_revision FROM tasks WHERE id=NEW.task_id),
             'kanban.task.attachment','add_attachment') != 1
        BEGIN SELECT RAISE(ABORT, 'olympus_attachment_authority_required'); END;
        CREATE TRIGGER olympus_attachments_update_guard BEFORE UPDATE ON task_attachments
        WHEN EXISTS (SELECT 1 FROM tasks WHERE id IN (OLD.task_id,NEW.task_id)
            AND olympus_context IS NOT NULL)
        BEGIN SELECT RAISE(ABORT, 'olympus_attachment_update_forbidden'); END;
        CREATE TRIGGER olympus_attachments_delete_guard BEFORE DELETE ON task_attachments
        WHEN EXISTS (SELECT 1 FROM tasks WHERE id=OLD.task_id AND olympus_context IS NOT NULL)
         AND olympus_permit_allows(OLD.task_id,
             (SELECT record_revision FROM tasks WHERE id=OLD.task_id),
             'kanban.task.attachment','delete_attachment') != 1
         AND olympus_permit_allows(OLD.task_id,
             (SELECT record_revision FROM tasks WHERE id=OLD.task_id),
             'kanban.task.delete','delete,delete_archived') != 1
        BEGIN SELECT RAISE(ABORT, 'olympus_attachment_authority_required'); END;

        CREATE TRIGGER olympus_notify_insert_guard BEFORE INSERT ON kanban_notify_subs
        WHEN EXISTS (SELECT 1 FROM tasks WHERE id=NEW.task_id AND olympus_context IS NOT NULL)
         AND olympus_notify_insert_allowed(
             NEW.task_id,NEW.platform,NEW.chat_id,NEW.thread_id,NEW.user_id,
             NEW.notifier_profile,NEW.created_at,NEW.last_event_id
         ) != 1
        BEGIN SELECT RAISE(ABORT, 'olympus_notify_authority_required'); END;
        CREATE TRIGGER olympus_notify_update_guard BEFORE UPDATE ON kanban_notify_subs
        WHEN EXISTS (SELECT 1 FROM tasks WHERE id IN (OLD.task_id,NEW.task_id)
            AND olympus_context IS NOT NULL)
         AND olympus_schema_migration_active() != 1
         AND olympus_notify_update_allowed(
             OLD.task_id,OLD.platform,OLD.chat_id,OLD.thread_id,OLD.user_id,
             OLD.notifier_profile,OLD.created_at,OLD.last_event_id,
             NEW.task_id,NEW.platform,NEW.chat_id,NEW.thread_id,NEW.user_id,
             NEW.notifier_profile,NEW.created_at,NEW.last_event_id
         ) != 1
        BEGIN SELECT RAISE(ABORT, 'olympus_notify_authority_required'); END;
        CREATE TRIGGER olympus_notify_delete_guard BEFORE DELETE ON kanban_notify_subs
        WHEN EXISTS (SELECT 1 FROM tasks WHERE id=OLD.task_id AND olympus_context IS NOT NULL)
         AND olympus_notify_delete_allowed(
             OLD.task_id,OLD.platform,OLD.chat_id,OLD.thread_id,OLD.user_id,
             OLD.notifier_profile,OLD.created_at,OLD.last_event_id
         ) != 1
         AND olympus_permit_allows(OLD.task_id,
             (SELECT record_revision FROM tasks WHERE id=OLD.task_id),
             'kanban.task.delete','delete,delete_archived') != 1
        BEGIN SELECT RAISE(ABORT, 'olympus_notify_authority_required'); END;

        CREATE TRIGGER olympus_create_receipt_insert_guard
        BEFORE INSERT ON kanban_olympus_create_receipts
        WHEN olympus_create_receipt_insert_allowed(
            NEW.idempotency_key,NEW.task_id,NEW.payload,NEW.payload_sha256,
            NEW.created_at
        ) != 1
        BEGIN SELECT RAISE(ABORT, 'olympus_create_receipt_authority_required'); END;
        CREATE TRIGGER olympus_create_receipt_update_guard
        BEFORE UPDATE ON kanban_olympus_create_receipts
        BEGIN SELECT RAISE(ABORT, 'olympus_create_receipt_immutable'); END;
        CREATE TRIGGER olympus_create_receipt_delete_guard
        BEFORE DELETE ON kanban_olympus_create_receipts
        BEGIN SELECT RAISE(ABORT, 'olympus_create_receipt_immutable'); END;

        CREATE TRIGGER olympus_release_receipt_insert_guard
        BEFORE INSERT ON kanban_olympus_release_receipts
        WHEN olympus_release_receipt_insert_allowed(
            NEW.operation_id,NEW.task_id,NEW.subject_revision,
            NEW.record_revision,NEW.verification_id,NEW.request_id,
            NEW.receipt,NEW.receipt_sha256,NEW.created_at
        ) != 1
        BEGIN SELECT RAISE(ABORT, 'olympus_release_receipt_authority_required'); END;
        CREATE TRIGGER olympus_release_receipt_update_guard
        BEFORE UPDATE ON kanban_olympus_release_receipts
        BEGIN SELECT RAISE(ABORT, 'olympus_release_receipt_immutable'); END;
        CREATE TRIGGER olympus_release_receipt_delete_guard
        BEFORE DELETE ON kanban_olympus_release_receipts
        BEGIN SELECT RAISE(ABORT, 'olympus_release_receipt_immutable'); END;

        {telegram_guard_sql}

        CREATE TRIGGER olympus_runs_insert_guard BEFORE INSERT ON task_runs
        WHEN EXISTS (SELECT 1 FROM tasks WHERE id=NEW.task_id AND olympus_context IS NOT NULL)
         AND olympus_run_insert_allowed(
             NEW.task_id,NEW.subject_revision,NEW.olympus_context,
             NEW.auth_root_id,NEW.auth_root_revision,NEW.verification_id,
             NEW.process_state,NEW.launch_token
         ) != 1
        BEGIN SELECT RAISE(ABORT, 'olympus_run_authority_required'); END;
        CREATE TRIGGER olympus_runs_update_guard BEFORE UPDATE ON task_runs
        WHEN EXISTS (SELECT 1 FROM tasks WHERE id=OLD.task_id AND olympus_context IS NOT NULL)
        BEGIN
            SELECT CASE WHEN NEW.id != OLD.id OR NEW.task_id != OLD.task_id
                THEN RAISE(ABORT, 'olympus_run_identity_change_forbidden') END;
            SELECT CASE WHEN NEW.subject_revision IS NOT OLD.subject_revision
                OR NEW.olympus_context IS NOT OLD.olympus_context
                THEN RAISE(ABORT, 'olympus_run_snapshot_change_forbidden') END;
            SELECT CASE WHEN olympus_run_update_allowed(
                OLD.task_id,(SELECT record_revision FROM tasks WHERE id=OLD.task_id),
                {run_values}
            ) != 1 THEN RAISE(ABORT, 'olympus_run_authority_required') END;
        END;
        CREATE TRIGGER olympus_runs_delete_guard BEFORE DELETE ON task_runs
        WHEN EXISTS (SELECT 1 FROM tasks WHERE id=OLD.task_id AND olympus_context IS NOT NULL)
         AND olympus_permit_allows(OLD.task_id,
             (SELECT record_revision FROM tasks WHERE id=OLD.task_id),
             'kanban.task.delete','delete,delete_archived') != 1
        BEGIN SELECT RAISE(ABORT, 'olympus_run_delete_authority_required'); END;

        CREATE TRIGGER olympus_events_insert_guard BEFORE INSERT ON task_events
        WHEN EXISTS (SELECT 1 FROM tasks WHERE id=NEW.task_id AND olympus_context IS NOT NULL)
         AND olympus_audit_allowed(
             NEW.task_id,NEW.run_id,NEW.kind,NEW.payload,NEW.created_at
         ) != 1
        BEGIN SELECT RAISE(ABORT, 'olympus_event_authority_required'); END;
        CREATE TRIGGER olympus_events_update_guard BEFORE UPDATE ON task_events
        WHEN EXISTS (SELECT 1 FROM tasks WHERE id IN (OLD.task_id,NEW.task_id)
            AND olympus_context IS NOT NULL)
        BEGIN SELECT RAISE(ABORT, 'olympus_event_update_forbidden'); END;
        CREATE TRIGGER olympus_events_delete_guard BEFORE DELETE ON task_events
        WHEN EXISTS (SELECT 1 FROM tasks WHERE id=OLD.task_id AND olympus_context IS NOT NULL)
         AND olympus_permit_allows(OLD.task_id,
             (SELECT record_revision FROM tasks WHERE id=OLD.task_id),
             'kanban.task.delete','delete,delete_archived') != 1
        BEGIN SELECT RAISE(ABORT, 'olympus_event_delete_authority_required'); END;

        CREATE TRIGGER olympus_effects_insert_guard BEFORE INSERT ON kanban_effect_journal
        WHEN EXISTS (SELECT 1 FROM tasks WHERE id=NEW.task_id AND olympus_context IS NOT NULL)
         AND olympus_effect_insert_allowed(
             NEW.task_id,NEW.state,NEW.effect_kind,NEW.auth_root_id,
             NEW.auth_root_revision,NEW.target_pre_revision,NEW.target_post_revision,
             NEW.run_id,NEW.event_id,NEW.operation_id,NEW.destination_key,NEW.part,
             NEW.worker_host_id,NEW.worker_boot_id,NEW.worker_pid,
             NEW.worker_start_token,NEW.source_identity,NEW.payload,NEW.payload_sha256
         ) != 1
        BEGIN SELECT RAISE(ABORT, 'olympus_effect_authority_required'); END;
        CREATE TRIGGER olympus_effects_update_guard BEFORE UPDATE ON kanban_effect_journal
        WHEN EXISTS (SELECT 1 FROM tasks WHERE id=OLD.task_id AND olympus_context IS NOT NULL)
         AND olympus_schema_migration_active() != 1
        BEGIN
            SELECT CASE WHEN
                NEW.id IS NOT OLD.id OR NEW.effect_kind IS NOT OLD.effect_kind
                OR NEW.operation_id IS NOT OLD.operation_id
                OR NEW.task_id IS NOT OLD.task_id OR NEW.run_id IS NOT OLD.run_id
                OR NEW.event_id IS NOT OLD.event_id
                OR NEW.destination_key IS NOT OLD.destination_key
                OR NEW.part IS NOT OLD.part OR NEW.auth_root_id IS NOT OLD.auth_root_id
                OR NEW.auth_root_revision IS NOT OLD.auth_root_revision
                OR NEW.target_pre_revision IS NOT OLD.target_pre_revision
                OR NEW.target_post_revision IS NOT OLD.target_post_revision
                OR NEW.worker_host_id IS NOT OLD.worker_host_id
                OR NEW.worker_boot_id IS NOT OLD.worker_boot_id
                OR NEW.worker_pid IS NOT OLD.worker_pid
                OR NEW.worker_start_token IS NOT OLD.worker_start_token
                OR NEW.source_identity IS NOT OLD.source_identity
                OR NEW.payload IS NOT OLD.payload
                OR NEW.payload_sha256 IS NOT OLD.payload_sha256
                OR NEW.created_at IS NOT OLD.created_at
                THEN RAISE(ABORT, 'olympus_effect_identity_change_forbidden') END;
            SELECT CASE WHEN NEW.updated_at < OLD.updated_at
                THEN RAISE(ABORT, 'olympus_effect_time_regression') END;
            SELECT CASE WHEN olympus_effect_update_allowed(
                OLD.task_id,OLD.id,OLD.effect_kind,OLD.state,NEW.state,
                OLD.event_id,OLD.operation_id,OLD.destination_key,
                OLD.error,NEW.error,OLD.updated_at,NEW.updated_at,
                OLD.applied_at,NEW.applied_at
            ) != 1 THEN RAISE(ABORT, 'olympus_effect_transition_forbidden') END;
        END;
        CREATE TRIGGER olympus_effects_delete_guard BEFORE DELETE ON kanban_effect_journal
        WHEN EXISTS (SELECT 1 FROM tasks WHERE id=OLD.task_id AND olympus_context IS NOT NULL)
         AND olympus_permit_allows(OLD.task_id,
             (SELECT record_revision FROM tasks WHERE id=OLD.task_id),
             'kanban.task.delete','delete,delete_archived') != 1
        BEGIN SELECT RAISE(ABORT, 'olympus_effect_delete_forbidden'); END;
        COMMIT;
    """
    try:
        conn.executescript(script)
    except Exception:
        if conn.in_transaction:
            conn.execute("ROLLBACK")
        raise


@contextlib.contextmanager
def connect_closing(
    db_path: Optional[Path] = None,
    *,
    board: Optional[str] = None,
):
    """Open a kanban DB connection and guarantee it is closed on exit.

    Use this instead of ``with kb.connect() as conn:`` — sqlite3's
    built-in connection context manager only commits/rollbacks the
    transaction; it does NOT close the file descriptor. In long-lived
    processes (gateway, dashboard) that route every kanban operation
    through ``connect()`` (e.g. ``run_slash`` dispatching ``/kanban …``
    commands, ``decompose_task_endpoint`` calling
    ``kanban_decompose.decompose_task``), the unclosed connections
    accumulate as open FDs to ``kanban.db`` and ``kanban.db-wal``. After
    enough operations the process hits the kernel FD limit and dies
    with ``[Errno 24] Too many open files``.

    See #33159 for the production incident.

    The ``connect()`` function itself remains unchanged so callers that
    intentionally manage the connection lifetime (tests, long-lived
    callers) continue to work.
    """
    conn = connect(db_path=db_path, board=board)
    try:
        yield conn
    finally:
        try:
            conn.close()
        except Exception:
            pass


def init_db(
    db_path: Optional[Path] = None,
    *,
    board: Optional[str] = None,
) -> Path:
    """Create the schema if it doesn't exist; return the path used.

    Kept as a public entry point so CLI ``hermes kanban init`` and the
    daemon have something explicit to call. Unlike :func:`connect`'s
    first-time auto-init (which caches by path), ``init_db`` always
    re-runs the migration pass. Callers that know the on-disk schema
    may have drifted — tests that write legacy event kinds directly,
    external tools that upgrade an old DB file — can call this to
    force re-migration.
    """
    if db_path is not None:
        path = db_path
    else:
        path = kanban_db_path(board=board)
    path.parent.mkdir(parents=True, exist_ok=True)
    resolved = str(path.resolve())
    # Clear the cache entry so the underlying connect() re-runs the
    # schema + migration pass unconditionally.
    with _INIT_LOCK:
        _INITIALIZED_PATHS.discard(resolved)
    with contextlib.closing(connect(path)):
        pass
    return path


def _add_column_if_missing(
    conn: sqlite3.Connection, table: str, column: str, ddl: str
) -> bool:
    """Run ``ALTER TABLE <table> ADD COLUMN <ddl>``, idempotent across races.

    Returns ``True`` when the column was actually added by this call.
    Swallows ``duplicate column name`` errors so a concurrent connection
    that ran the same migration first does not crash the dispatcher tick
    (issue #21708).
    """
    try:
        conn.execute(f"ALTER TABLE {table} ADD COLUMN {ddl}")
        return True
    except sqlite3.OperationalError as exc:
        if "duplicate column name" in str(exc).lower():
            return False
        raise


def _migrate_add_optional_columns(conn: sqlite3.Connection) -> None:
    """Add columns that were introduced after v1 release to legacy DBs.

    Called by ``init_db`` so opening an old DB is always safe.
    """
    # Direct migration callers and very old/partial schemas predate the
    # migration ledger itself. Create it before consulting the atomic Olympus
    # revision marker; this is idempotent on fully initialized databases.
    conn.execute(
        "CREATE TABLE IF NOT EXISTS kanban_schema_migrations ("
        "name TEXT PRIMARY KEY, completed_at INTEGER NOT NULL)"
    )
    cols = {row["name"] for row in conn.execute("PRAGMA table_info(tasks)")}
    if "tenant" not in cols:
        _add_column_if_missing(conn, "tasks", "tenant", "tenant TEXT")
    if "result" not in cols:
        _add_column_if_missing(conn, "tasks", "result", "result TEXT")
    if "branch_name" not in cols:
        _add_column_if_missing(conn, "tasks", "branch_name", "branch_name TEXT")
    if "idempotency_key" not in cols:
        _add_column_if_missing(
            conn, "tasks", "idempotency_key", "idempotency_key TEXT"
        )
    # ``idx_tasks_idempotency`` is created unconditionally below alongside
    # the other additive-column indexes — see the block after the
    # legacy-column migration. Creating it here too would be redundant.

    # Refresh after early additive migrations above. Some existing DBs were
    # partially migrated in older releases and can already contain the later
    # columns (for example ``consecutive_failures``) even when this function's
    # initial snapshot did not. Re-snapshot here so the legacy-column migration
    # below is truly idempotent and never re-adds columns that already exist.
    cols = {row["name"] for row in conn.execute("PRAGMA table_info(tasks)")}

    # Legacy column migration: ``spawn_failures`` → ``consecutive_failures``
    # and ``last_spawn_error`` → ``last_failure_error``.
    #
    # Avoid ``ALTER TABLE ... RENAME COLUMN`` for two reasons:
    #   1. Primary: very old DBs may never have had ``spawn_failures`` at
    #      all, so RENAME raises OperationalError: no such column (the crash
    #      reported in issue #20842 after the #20410 update).
    #   2. Secondary: SQLite reparses the whole schema on any RENAME, which
    #      fails if related objects (views, triggers) reference the old name.
    #
    # ADD-first-then-copy is tolerant of both shapes and preserves
    # historical counter values when the legacy columns do exist.
    if "consecutive_failures" not in cols:
        added = _add_column_if_missing(
            conn,
            "tasks",
            "consecutive_failures",
            "consecutive_failures INTEGER NOT NULL DEFAULT 0",
        )
        if added and "spawn_failures" in cols:
            conn.execute(
                "UPDATE tasks SET consecutive_failures = COALESCE(spawn_failures, 0)"
            )
    if "worker_pid" not in cols:
        _add_column_if_missing(conn, "tasks", "worker_pid", "worker_pid INTEGER")
    if "last_failure_error" not in cols:
        added = _add_column_if_missing(
            conn, "tasks", "last_failure_error", "last_failure_error TEXT"
        )
        if added and "last_spawn_error" in cols:
            conn.execute(
                "UPDATE tasks SET last_failure_error = last_spawn_error"
            )
    if "max_runtime_seconds" not in cols:
        _add_column_if_missing(
            conn, "tasks", "max_runtime_seconds", "max_runtime_seconds INTEGER"
        )
    if "last_heartbeat_at" not in cols:
        _add_column_if_missing(
            conn, "tasks", "last_heartbeat_at", "last_heartbeat_at INTEGER"
        )
    if "current_run_id" not in cols:
        _add_column_if_missing(
            conn, "tasks", "current_run_id", "current_run_id INTEGER"
        )
    if "workflow_template_id" not in cols:
        _add_column_if_missing(
            conn, "tasks", "workflow_template_id", "workflow_template_id TEXT"
        )
    if "current_step_key" not in cols:
        _add_column_if_missing(
            conn, "tasks", "current_step_key", "current_step_key TEXT"
        )
    if "skills" not in cols:
        # JSON array of skill names the dispatcher force-loads into the
        # worker (additive to the built-in `kanban-worker`). NULL is fine
        # for existing rows.
        _add_column_if_missing(conn, "tasks", "skills", "skills TEXT")

    if "max_retries" not in cols:
        # Per-task override for the consecutive-failure circuit breaker.
        # NULL = fall through to the dispatcher-level ``kanban.failure_limit``
        # config, then ``DEFAULT_FAILURE_LIMIT``. Existing rows get NULL,
        # which is the correct default (they keep the global behaviour
        # they were getting before the column existed).
        _add_column_if_missing(conn, "tasks", "max_retries", "max_retries INTEGER")

    if "model_override" not in cols:
        conn.execute("ALTER TABLE tasks ADD COLUMN model_override TEXT")

    if "goal_mode" not in cols:
        # Ralph-style goal loop toggle for the dispatched worker. 0 (the
        # default) = classic single-shot worker, preserving the behaviour
        # existing rows had before the column existed.
        _add_column_if_missing(
            conn, "tasks", "goal_mode", "goal_mode INTEGER NOT NULL DEFAULT 0"
        )

    if "goal_max_turns" not in cols:
        # Per-task goal-loop turn budget. NULL = goals-engine default.
        _add_column_if_missing(
            conn, "tasks", "goal_max_turns", "goal_max_turns INTEGER"
        )

    if "session_id" not in cols:
        # Originating agent/chat session id, populated when the task is
        # created from within an agent loop that propagated
        # ``HERMES_SESSION_ID`` (e.g. ACP). NULL on legacy rows and on any
        # creation path that doesn't set the env var (CLI, dashboard).
        _add_column_if_missing(
            conn, "tasks", "session_id", "session_id TEXT"
        )

    if "olympus_context" not in cols:
        # NULL is the only legacy/ungoverned representation. No backfill is
        # attempted: Hermes must never infer Olympus authority from an old
        # task's title, tenant, branch, assignee, or mere existence.
        _add_column_if_missing(
            conn, "tasks", "olympus_context", "olympus_context TEXT"
        )

    runs_table_exists = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name='task_runs'"
    ).fetchone() is not None
    revision_migration = "olympus_task_run_revisions_v1"
    revision_migration_done = conn.execute(
        "SELECT 1 FROM kanban_schema_migrations WHERE name = ?",
        (revision_migration,),
    ).fetchone() is not None
    if not revision_migration_done:
        # ALTER TABLE and both backfills are transactional in SQLite.  The
        # completion marker is committed in that same transaction, so a crash
        # can never leave a column-only state that later code mistakes for a
        # completed revision migration.
        with write_txn(conn):
            task_cols = {
                row["name"] for row in conn.execute("PRAGMA table_info(tasks)")
            }
            if "record_revision" not in task_cols:
                _add_column_if_missing(
                    conn,
                    "tasks",
                    "record_revision",
                    "record_revision INTEGER NOT NULL DEFAULT 0",
                )
            if runs_table_exists:
                run_cols = {
                    row["name"]
                    for row in conn.execute("PRAGMA table_info(task_runs)")
                }
                if "olympus_context" not in run_cols:
                    _add_column_if_missing(
                        conn,
                        "task_runs",
                        "olympus_context",
                        "olympus_context TEXT",
                    )
                if "subject_revision" not in run_cols:
                    _add_column_if_missing(
                        conn,
                        "task_runs",
                        "subject_revision",
                        "subject_revision INTEGER",
                    )
            ambiguous = conn.execute(
                "SELECT id FROM tasks WHERE olympus_context IS NOT NULL "
                "AND record_revision NOT IN (0, 1) LIMIT 1"
            ).fetchone()
            if ambiguous is not None:
                raise sqlite3.DatabaseError(
                    "incomplete Olympus revision migration has advanced governed data"
                )
            conn.execute(
                "UPDATE tasks SET record_revision = 1 "
                "WHERE olympus_context IS NOT NULL AND record_revision = 0"
            )
            if runs_table_exists:
                conn.execute(
                    "UPDATE task_runs SET subject_revision = 1 "
                    "WHERE olympus_context IS NOT NULL "
                    "AND subject_revision IS NULL "
                    "AND EXISTS (SELECT 1 FROM tasks t "
                    "WHERE t.id = task_runs.task_id "
                    "AND t.olympus_context IS NOT NULL "
                    "AND t.record_revision = 1)"
                )
                incomplete_run = conn.execute(
                    "SELECT r.id FROM task_runs r JOIN tasks t ON t.id = r.task_id "
                    "WHERE r.olympus_context IS NOT NULL "
                    "AND t.olympus_context IS NOT NULL "
                    "AND r.subject_revision IS NULL LIMIT 1"
                ).fetchone()
                if incomplete_run is not None:
                    raise sqlite3.DatabaseError(
                        "Olympus run revision backfill did not complete"
                    )
            conn.execute(
                "INSERT INTO kanban_schema_migrations(name, completed_at) "
                "VALUES (?, ?)",
                (revision_migration, int(time.time())),
            )
    else:
        task_cols = {
            row["name"] for row in conn.execute("PRAGMA table_info(tasks)")
        }
        run_cols = (
            {row["name"] for row in conn.execute("PRAGMA table_info(task_runs)")}
            if runs_table_exists else set()
        )
        if "record_revision" not in task_cols or (
            runs_table_exists and "subject_revision" not in run_cols
        ):
            raise sqlite3.DatabaseError(
                "Olympus revision migration marker contradicts the live schema"
            )

    if runs_table_exists:
        process_columns = {
            "process_state": "process_state TEXT NOT NULL DEFAULT 'legacy'",
            "launch_token": "launch_token TEXT",
            "workspace_snapshot": "workspace_snapshot TEXT",
            "auth_root_id": "auth_root_id TEXT",
            "auth_root_revision": "auth_root_revision INTEGER",
            "verification_id": "verification_id TEXT",
            "worker_host_id": "worker_host_id TEXT",
            "worker_boot_id": "worker_boot_id TEXT",
            "worker_start_token": "worker_start_token TEXT",
            "worker_registered_at": "worker_registered_at INTEGER",
            "dispatcher_instance_id": "dispatcher_instance_id TEXT",
        }
        run_cols = {
            row["name"] for row in conn.execute("PRAGMA table_info(task_runs)")
        }
        for column, ddl in process_columns.items():
            if column not in run_cols:
                _add_column_if_missing(conn, "task_runs", column, ddl)
        conn.execute(
            "CREATE UNIQUE INDEX IF NOT EXISTS idx_runs_launch_token "
            "ON task_runs(launch_token) WHERE launch_token IS NOT NULL"
        )

    # Indexes over additive ``tasks`` columns must be created after the
    # columns exist. Keeping them in SCHEMA_SQL breaks legacy boards: SQLite
    # parses each statement in ``executescript`` against the live schema, so a
    # ``CREATE INDEX`` over a missing column aborts initialization before the
    # additive ``ALTER TABLE`` migrations below can run. Re-running them here
    # is cheap thanks to ``IF NOT EXISTS`` and stays correct on fresh DBs
    # (where the columns already exist from SCHEMA_SQL).
    conn.execute("CREATE INDEX IF NOT EXISTS idx_tasks_tenant ON tasks(tenant)")
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_tasks_idempotency ON tasks(idempotency_key)"
    )
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_tasks_session_id ON tasks(session_id)"
    )

    # task_events gained a run_id column; back-fill it as NULL for
    # historical events (they predate runs and can't be attributed).
    ev_cols = {row["name"] for row in conn.execute("PRAGMA table_info(task_events)")}
    if "run_id" not in ev_cols:
        _add_column_if_missing(conn, "task_events", "run_id", "run_id INTEGER")

    # Same ordering rule as the additive ``tasks`` indexes above: create the
    # index after the additive column migration so legacy ``task_events``
    # tables don't fail during SCHEMA_SQL execution before ``run_id`` exists.
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_events_run "
        "ON task_events(run_id, id)"
    )

    notify_table_exists = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name='kanban_notify_subs'"
    ).fetchone() is not None
    if notify_table_exists:
        notify_cols = {
            row["name"] for row in conn.execute("PRAGMA table_info(kanban_notify_subs)")
        }
        if "notifier_profile" not in notify_cols:
            _add_column_if_missing(
                conn, "kanban_notify_subs", "notifier_profile", "notifier_profile TEXT"
            )

    # Pre-v3 Telegram WIP tables carried caller-asserted authority and, for
    # controls, PID-owned recovery state. Preserve those rows as immutable
    # legacy evidence but never treat them as executable v3 receipts.
    telegram_specs = {
        "olympus_telegram_deliveries": (
            {
                "delivery_key", "authorization_task_id",
                "authorization_task_revision", "task_id", "payload",
                "payload_sha256", "created_at",
            },
            "CREATE TABLE olympus_telegram_deliveries ("
            "delivery_key TEXT PRIMARY KEY, authorization_task_id TEXT NOT NULL, "
            "authorization_task_revision INTEGER NOT NULL, task_id TEXT NOT NULL UNIQUE, "
            "payload TEXT NOT NULL, payload_sha256 TEXT NOT NULL, "
            "created_at INTEGER NOT NULL)",
        ),
        "olympus_telegram_controls": (
            {
                "operation_id", "action", "authorization_task_id",
                "authorization_task_revision", "target_task_id",
                "target_task_revision", "source_identity", "request_payload",
                "payload_sha256", "verification_id", "result_status",
                "effect_operation_id", "created_at",
            },
            "CREATE TABLE olympus_telegram_controls ("
            "operation_id TEXT PRIMARY KEY, action TEXT NOT NULL, "
            "authorization_task_id TEXT NOT NULL, "
            "authorization_task_revision INTEGER NOT NULL, "
            "target_task_id TEXT NOT NULL, target_task_revision INTEGER NOT NULL, "
            "source_identity TEXT NOT NULL, request_payload TEXT NOT NULL, "
            "payload_sha256 TEXT NOT NULL, verification_id TEXT NOT NULL, "
            "result_status TEXT, effect_operation_id TEXT, created_at INTEGER NOT NULL)",
        ),
    }
    for table, (expected_columns, create_sql) in telegram_specs.items():
        columns = {
            row["name"] for row in conn.execute(f"PRAGMA table_info({table})")
        }
        if not columns:
            conn.execute(create_sql)
        elif columns != expected_columns:
            legacy = f"{table}_legacy_pre_v3"
            with write_txn(conn):
                if conn.execute(
                    "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?",
                    (legacy,),
                ).fetchone() is not None:
                    raise sqlite3.IntegrityError(
                        f"kanban migration: preserved legacy table {legacy} already exists"
                    )
                conn.execute(f"ALTER TABLE {table} RENAME TO {legacy}")
                failpoint = _OLYMPUS_TELEGRAM_MIGRATION_FAILPOINT
                if callable(failpoint):
                    failpoint(table)
                conn.execute(create_sql)
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_olympus_telegram_control_target "
        "ON olympus_telegram_controls(target_task_id, created_at)"
    )

    # One-shot backfill: any task that is 'running' before runs existed
    # had its claim_lock / claim_expires / worker_pid on the task row.
    # Synthesize a matching task_runs row so subsequent end-run / heartbeat
    # calls have something to write to. Wrapped in write_txn to serialize
    # against any concurrent dispatcher, and the per-row UPDATE uses
    # ``current_run_id IS NULL`` as a CAS guard so a racing claim can't
    # produce an orphaned row if it interleaves with the backfill pass.
    runs_exist = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name='task_runs'"
    ).fetchone() is not None
    if runs_exist:
        with write_txn(conn):
            inflight = conn.execute(
                "SELECT id, assignee, claim_lock, claim_expires, worker_pid, "
                "       max_runtime_seconds, last_heartbeat_at, started_at, "
                "       olympus_context, record_revision "
                "FROM tasks "
                "WHERE status = 'running' AND current_run_id IS NULL"
            ).fetchall()
            for row in inflight:
                started = row["started_at"] or int(time.time())
                cur = conn.execute(
                    """
                    INSERT INTO task_runs (
                        task_id, profile, status,
                        claim_lock, claim_expires, worker_pid,
                        max_runtime_seconds, last_heartbeat_at,
                        started_at, olympus_context, subject_revision
                    ) VALUES (?, ?, 'running', ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        row["id"], row["assignee"], row["claim_lock"],
                        row["claim_expires"], row["worker_pid"],
                        row["max_runtime_seconds"], row["last_heartbeat_at"],
                        started, row["olympus_context"],
                        (
                            int(row["record_revision"])
                            if row["olympus_context"] is not None else None
                        ),
                    ),
                )
                # CAS: only install the pointer if nothing else claimed
                # the task between our SELECT and here (shouldn't happen
                # under the write_txn, but belt-and-suspenders). If the
                # CAS fails we've got an orphan run_row — mark it
                # reclaimed so it doesn't look in-flight.
                upd = conn.execute(
                    "UPDATE tasks SET current_run_id = ? "
                    "WHERE id = ? AND current_run_id IS NULL",
                    (cur.lastrowid, row["id"]),
                )
                if upd.rowcount != 1:
                    conn.execute(
                        "UPDATE task_runs SET status = 'reclaimed', "
                        "    outcome = 'reclaimed', ended_at = ? "
                        "WHERE id = ?",
                        (int(time.time()), cur.lastrowid),
                    )

    # One-shot event-kind rename pass. The old names ("ready", "priority",
    # "spawn_auto_blocked") still worked but were awkward on the wire;
    # rename them in-place so existing DBs migrate cleanly. Fires once
    # per DB because after the UPDATE no rows match the old kinds.
    _EVENT_RENAMES = (
        # (old, new)
        ("ready",              "promoted"),
        ("priority",           "reprioritized"),
        ("spawn_auto_blocked", "gave_up"),
    )
    for old, new in _EVENT_RENAMES:
        conn.execute(
            "UPDATE task_events SET kind = ? WHERE kind = ?",
            (new, old),
        )

    _rebuild_drifted_tables(conn)


# Legacy DBs defined these tables with a ``TEXT PRIMARY KEY`` id (or, for
# ``kanban_notify_subs``, a nullable ``TEXT last_event_id``). The current
# schema uses ``INTEGER PRIMARY KEY AUTOINCREMENT`` / ``INTEGER NOT NULL
# DEFAULT 0``. ``CREATE TABLE IF NOT EXISTS`` skips existing tables
# regardless of schema and ``_add_column_if_missing`` only adds columns, so
# neither can fix a drifted column type — the table must be rebuilt. See
# #35096.
#
# Each entry pairs the canonical CREATE TABLE with the CREATE INDEX
# statements that DROP TABLE would otherwise take down with it (including
# ``idx_events_run``, added by the additive pass above). To guard against
# this list drifting from SCHEMA_SQL, ``test_rebuilt_schema_matches_fresh``
# asserts a rebuilt legacy DB is byte-identical to a fresh one.
_REBUILD_SPECS = {
    "task_events": (
        "CREATE TABLE task_events ("
        " id INTEGER PRIMARY KEY AUTOINCREMENT,"
        " task_id TEXT NOT NULL, run_id INTEGER, kind TEXT NOT NULL,"
        " payload TEXT, created_at INTEGER NOT NULL)",
        (
            "CREATE INDEX idx_events_task ON task_events(task_id, created_at)",
            "CREATE INDEX idx_events_run ON task_events(run_id, id)",
        ),
    ),
    "task_comments": (
        "CREATE TABLE task_comments ("
        " id INTEGER PRIMARY KEY AUTOINCREMENT,"
        " task_id TEXT NOT NULL, author TEXT NOT NULL, body TEXT NOT NULL,"
        " created_at INTEGER NOT NULL)",
        ("CREATE INDEX idx_comments_task ON task_comments(task_id, created_at)",),
    ),
    "task_runs": (
        "CREATE TABLE task_runs ("
        " id INTEGER PRIMARY KEY AUTOINCREMENT,"
        " task_id TEXT NOT NULL, profile TEXT, step_key TEXT,"
        " status TEXT NOT NULL, claim_lock TEXT, claim_expires INTEGER,"
        " worker_pid INTEGER, max_runtime_seconds INTEGER,"
        " last_heartbeat_at INTEGER, started_at INTEGER NOT NULL,"
        " ended_at INTEGER, outcome TEXT, summary TEXT, metadata TEXT,"
        " error TEXT, olympus_context TEXT, subject_revision INTEGER,"
        " process_state TEXT NOT NULL DEFAULT 'legacy', launch_token TEXT,"
        " workspace_snapshot TEXT, auth_root_id TEXT, auth_root_revision INTEGER,"
        " verification_id TEXT, worker_host_id TEXT, worker_boot_id TEXT,"
        " worker_start_token TEXT, worker_registered_at INTEGER,"
        " dispatcher_instance_id TEXT)",
        (
            "CREATE INDEX idx_runs_task ON task_runs(task_id, started_at)",
            "CREATE INDEX idx_runs_status ON task_runs(status)",
            "CREATE UNIQUE INDEX idx_runs_launch_token ON task_runs(launch_token) "
            "WHERE launch_token IS NOT NULL",
        ),
    ),
    "kanban_notify_subs": (
        "CREATE TABLE kanban_notify_subs ("
        " task_id TEXT NOT NULL, platform TEXT NOT NULL, chat_id TEXT NOT NULL,"
        " thread_id TEXT NOT NULL DEFAULT '', user_id TEXT,"
        " notifier_profile TEXT, created_at INTEGER NOT NULL,"
        " last_event_id INTEGER NOT NULL DEFAULT 0,"
        " PRIMARY KEY (task_id, platform, chat_id, thread_id))",
        ("CREATE INDEX idx_notify_task ON kanban_notify_subs(task_id)",),
    ),
}


def _table_has_drifted(conn: sqlite3.Connection, table: str) -> bool:
    """True when ``table`` still carries the legacy (pre-AUTOINCREMENT) shape."""
    info = conn.execute(f"PRAGMA table_info({table})").fetchall()
    if not info:
        return False  # table absent — nothing to rebuild
    if table == "kanban_notify_subs":
        lei = next((c for c in info if c["name"] == "last_event_id"), None)
        return lei is not None and (lei["type"] or "").upper() != "INTEGER"
    # task_events / task_comments / task_runs: id must be INTEGER and a PK.
    id_col = next((c for c in info if c["name"] == "id"), None)
    if id_col is None:
        return False
    return not ((id_col["type"] or "").upper() == "INTEGER" and id_col["pk"])


def _rebuild_drifted_tables(conn: sqlite3.Connection) -> None:
    """Rebuild any kanban table whose column types drifted from SCHEMA_SQL.

    Every legacy run/event id is mapped deterministically in rowid order and
    every dependent reference is remapped in the same transaction. Missing,
    duplicate, or otherwise unmappable identities abort the whole migration;
    notification cursors are preserved exactly instead of replaying history.
    """
    order = ("task_runs", "task_events", "task_comments", "kanban_notify_subs")
    drifted = [table for table in order if _table_has_drifted(conn, table)]
    if not drifted:
        return

    def identity_key(value: Any, *, table: str) -> str:
        if value is None:
            raise sqlite3.IntegrityError(
                f"kanban migration: {table} contains an unmappable NULL id"
            )
        return str(value)

    legacy_ids: dict[str, set[str]] = {}
    for table in ("task_runs", "task_events"):
        if table not in drifted:
            continue
        keys: set[str] = set()
        for row in conn.execute(f"SELECT id FROM {table} ORDER BY rowid"):
            key = identity_key(row["id"], table=table)
            if key in keys:
                raise sqlite3.IntegrityError(
                    f"kanban migration: {table} contains duplicate id {key!r}"
                )
            keys.add(key)
        legacy_ids[table] = keys

    def require_mappable(
        query: str, keys: set[str], *, label: str,
    ) -> None:
        for row in conn.execute(query):
            value = row[0]
            if value is not None and str(value) not in keys:
                raise sqlite3.IntegrityError(
                    f"kanban migration: unmappable {label} reference {value!r}"
                )

    if "task_runs" in drifted:
        run_keys = legacy_ids["task_runs"]
        require_mappable(
            "SELECT current_run_id FROM tasks WHERE current_run_id IS NOT NULL",
            run_keys,
            label="tasks.current_run_id",
        )
        require_mappable(
            "SELECT run_id FROM task_events WHERE run_id IS NOT NULL",
            run_keys,
            label="task_events.run_id",
        )
        require_mappable(
            "SELECT run_id FROM kanban_effect_journal WHERE run_id IS NOT NULL",
            run_keys,
            label="kanban_effect_journal.run_id",
        )
    if "task_events" in drifted:
        event_keys = legacy_ids["task_events"]
        require_mappable(
            "SELECT event_id FROM kanban_effect_journal WHERE event_id IS NOT NULL",
            event_keys,
            label="kanban_effect_journal.event_id",
        )
        require_mappable(
            "SELECT last_event_id FROM kanban_notify_subs "
            "WHERE last_event_id IS NOT NULL AND CAST(last_event_id AS TEXT) != '0'",
            event_keys,
            label="kanban_notify_subs.last_event_id",
        )

    conn._olympus_schema_migration_depth = (
        int(getattr(conn, "_olympus_schema_migration_depth", 0)) + 1
    )
    conn.execute("BEGIN IMMEDIATE")
    maps: dict[str, dict[str, int]] = {}
    try:
        for table in drifted:
            create_sql, index_sqls = _REBUILD_SPECS[table]
            old_cols = [c["name"] for c in conn.execute(f"PRAGMA table_info({table})")]
            _log.info("kanban migration: rebuilding %s to match current schema", table)
            conn.execute(f"ALTER TABLE {table} RENAME TO {table}_legacy")
            conn.execute(create_sql)
            new_cols = {c["name"] for c in conn.execute(f"PRAGMA table_info({table})")}
            shared = [column for column in old_cols if column in new_cols]
            if table in {"task_runs", "task_events", "task_comments"}:
                shared = [column for column in shared if column != "id"]
            table_map: dict[str, int] = {}
            rows = conn.execute(
                f"SELECT rowid AS __legacy_rowid, * FROM {table}_legacy "
                "ORDER BY rowid"
            ).fetchall()
            for row in rows:
                values = []
                for column in shared:
                    value = row[column]
                    if table == "task_events" and column == "run_id" \
                            and value is not None and "task_runs" in maps:
                        value = maps["task_runs"][str(value)]
                    if table == "kanban_notify_subs" and column == "last_event_id":
                        if value is None or str(value) == "0":
                            value = 0
                        elif "task_events" in maps:
                            value = maps["task_events"][str(value)]
                        else:
                            try:
                                value = int(value)
                            except (TypeError, ValueError) as exc:
                                raise sqlite3.IntegrityError(
                                    "kanban migration: notification cursor is not integer"
                                ) from exc
                    values.append(value)
                columns_csv = ", ".join(shared)
                placeholders = ", ".join("?" for _ in shared)
                cur = conn.execute(
                    f"INSERT INTO {table} ({columns_csv}) VALUES ({placeholders})",
                    values,
                )
                if table in {"task_runs", "task_events"}:
                    table_map[identity_key(row["id"], table=table)] = int(
                        cur.lastrowid
                    )
            if table_map:
                maps[table] = table_map
            conn.execute(f"DROP TABLE {table}_legacy")
            for index_sql in index_sqls:
                conn.execute(index_sql)

            failpoint = _OLYMPUS_REBUILD_FAILPOINT
            if callable(failpoint):
                failpoint(table)

        if "task_runs" in maps:
            for old_id, new_id in maps["task_runs"].items():
                conn.execute(
                    "UPDATE tasks SET current_run_id=? "
                    "WHERE CAST(current_run_id AS TEXT)=?",
                    (new_id, old_id),
                )
                if "task_events" not in maps:
                    conn.execute(
                        "UPDATE task_events SET run_id=? WHERE CAST(run_id AS TEXT)=?",
                        (new_id, old_id),
                    )
                conn.execute(
                    "UPDATE kanban_effect_journal SET run_id=? "
                    "WHERE CAST(run_id AS TEXT)=?",
                    (new_id, old_id),
                )
        if "task_events" in maps:
            for old_id, new_id in maps["task_events"].items():
                conn.execute(
                    "UPDATE kanban_effect_journal SET event_id=? "
                    "WHERE CAST(event_id AS TEXT)=?",
                    (new_id, old_id),
                )
                if "kanban_notify_subs" not in drifted:
                    conn.execute(
                        "UPDATE kanban_notify_subs SET last_event_id=? "
                        "WHERE CAST(last_event_id AS TEXT)=?",
                        (new_id, old_id),
                    )
        conn.execute("COMMIT")
    except Exception:
        try:
            conn.execute("ROLLBACK")
        except sqlite3.OperationalError:
            pass
        raise
    finally:
        conn._olympus_schema_migration_depth = max(
            0, int(getattr(conn, "_olympus_schema_migration_depth", 1)) - 1,
        )
    _install_olympus_write_guard(conn)


def _check_file_length_invariant(conn: sqlite3.Connection) -> None:
    """Read the SQLite header page_count and compare against actual file size.

    Raises sqlite3.DatabaseError if the file is shorter than the header claims
    (torn-extend corruption).
    """
    try:
        row = conn.execute("PRAGMA database_list").fetchone()
        if row is None:
            return
        path_str = row[2]  # column 2 is the file path; empty for in-memory DBs
        if not path_str:
            return  # in-memory or unnamed DB; skip
        path = path_str
        page_size = conn.execute("PRAGMA page_size").fetchone()[0]
        file_size = os.path.getsize(path)
        with open(path, "rb") as f:
            f.seek(28)
            header_bytes = f.read(4)
        if len(header_bytes) < 4:
            return  # can't read header; skip
        header_page_count = int.from_bytes(header_bytes, "big")
        if header_page_count == 0:
            return  # new/empty DB; skip
        actual_pages = file_size // page_size
        if actual_pages < header_page_count:
            raise sqlite3.DatabaseError(
                f"torn-extend detected: page count mismatch on {path}: "
                f"header claims {header_page_count} pages, "
                f"file has {actual_pages} pages "
                f"(missing {header_page_count - actual_pages} pages, "
                f"file_size={file_size}, page_size={page_size})"
            )
    except sqlite3.DatabaseError:
        raise
    except Exception:
        pass  # I/O errors during check are non-fatal; let normal ops continue


@contextlib.contextmanager
def write_txn(conn: sqlite3.Connection):
    """Context manager for an IMMEDIATE write transaction.

    Use for any multi-statement write (creating a task + link, claiming a
    task + recording an event, etc.).  A claim CAS inside this context is
    atomic -- at most one concurrent writer can succeed.

    The explicit ROLLBACK on exception is wrapped in try/except so that
    a SQLite auto-rollback (which leaves no active transaction) does not
    shadow the original exception with a spurious rollback error.
    """
    managed_connection = isinstance(conn, _KanbanConnection)
    depth = int(getattr(conn, "_olympus_managed_txn_depth", 0))
    if conn.in_transaction:
        if depth <= 0:
            if not managed_connection:
                # Migration utilities historically accept a plain stdlib
                # connection. Such a connection cannot hold Olympus intents;
                # preserve its caller-owned transaction without attaching
                # attributes that the C extension type does not support.
                yield conn
                return
            # Preserve ordinary external transaction compatibility, but mark
            # it so governed permit issuance fails closed.  A caller-owned
            # transaction may not retain an ALLOW after a helper returns.
            previous = bool(getattr(conn, "_olympus_external_txn", False))
            conn._olympus_external_txn = True
            try:
                yield conn
            finally:
                conn._olympus_external_txn = previous
            return
        conn._olympus_managed_txn_depth = depth + 1
        try:
            yield conn
        finally:
            conn._olympus_managed_txn_depth = depth
        return
    registry = getattr(conn, "_olympus_permit_registry", None)
    audit_registry = getattr(conn, "_olympus_audit_registry", None)
    if registry:
        registry.clear()
        raise OlympusContextError(
            "olympus_permit_lifecycle_invalid",
            "an authority permit survived its composing transaction",
        )
    if audit_registry:
        audit_registry.clear()
        raise OlympusContextError(
            "olympus_audit_lifecycle_invalid",
            "a protected audit permit survived its composing transaction",
        )
    conn.execute("BEGIN IMMEDIATE")
    if managed_connection:
        conn._olympus_managed_txn_depth = 1
    try:
        yield conn
    except Exception:
        try:
            conn.execute("ROLLBACK")
        except sqlite3.OperationalError:
            # SQLite has already auto-rolled-back the transaction (typical
            # under EIO, lock contention, or corruption). Nothing to undo;
            # do not let this secondary failure shadow the real one.
            pass
        if registry is not None:
            registry.clear()
        if audit_registry is not None:
            audit_registry.clear()
        raise
    else:
        # Intents are process-local and transaction-scoped.  They may cover a
        # composed operation with several guarded statements, but they must
        # never survive the outer transaction boundary where a later caller
        # could reuse an old ALLOW.
        if registry is not None:
            registry.clear()
        if audit_registry is not None:
            audit_registry.clear()
        conn.execute("COMMIT")
        # Post-commit file-length check: header page_count must match actual file pages.
        # A discrepancy means a torn-extend — raise now rather than silently corrupt.
        _check_file_length_invariant(conn)
    finally:
        if managed_connection:
            conn._olympus_managed_txn_depth = 0


@contextlib.contextmanager
def olympus_mutation_scope(auth: Optional[OlympusMutationAuth]):
    """Bind trusted authority context for one composed Kanban operation."""
    token = _OLYMPUS_MUTATION_AUTH.set(auth)
    try:
        yield
    finally:
        _OLYMPUS_MUTATION_AUTH.reset(token)


def _load_authorization_root(
    conn: sqlite3.Connection,
    *,
    root_id: str,
    target_context: dict[str, Any],
) -> dict[str, Any]:
    """Load and bind a Telegram-selected authorization root transactionally."""
    root_id = str(root_id).strip()
    if not root_id:
        raise OlympusContextError(
            "olympus_authorization_root_invalid",
            "Telegram authorization root id is required",
        )
    row = conn.execute(
        "SELECT id, assignee, status, record_revision, olympus_context "
        "FROM tasks WHERE id = ?",
        (root_id,),
    ).fetchone()
    if row is None or row["olympus_context"] is None:
        raise OlympusContextError(
            "olympus_authorization_root_missing",
            "Telegram authorization root is missing or ungoverned",
        )
    root_context = _require_current_olympus_context(
        row["olympus_context"], assignee=row["assignee"],
    )
    if root_context is None:
        raise OlympusContextError(
            "olympus_authorization_root_missing",
            "Telegram authorization root is ungoverned",
        )
    if any(
        root_context[key] != target_context[key]
        for key in ("goal_id", "program_id", "milestone_id", "mission_id")
    ):
        raise OlympusContextError(
            "olympus_authorization_root_foreign",
            "Telegram target is outside the selected authorization hierarchy",
        )
    return {
        "id": str(row["id"]),
        "record_revision": int(row["record_revision"]),
        "status": str(row["status"]),
        "assignee": str(row["assignee"] or ""),
        "context": root_context,
    }


def _telegram_target_identity(
    conn: sqlite3.Connection,
    *,
    authorization_task_id: str,
    target_task_id: str,
    action: str,
    target_context: dict[str, Any],
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Return the exact live Telegram authorization-root/target binding."""
    root = _load_authorization_root(
        conn,
        root_id=authorization_task_id,
        target_context=target_context,
    )
    target = conn.execute(
        "SELECT id, assignee, status, record_revision, olympus_context "
        "FROM tasks WHERE id = ?",
        (str(target_task_id).strip(),),
    ).fetchone()
    if target is None or target["olympus_context"] is None:
        raise OlympusContextError(
            "olympus_control_target_missing",
            "Telegram target is missing or ungoverned",
        )
    raw_target_context: Any = target["olympus_context"]
    if isinstance(raw_target_context, str):
        try:
            raw_target_context = json.loads(raw_target_context)
        except (TypeError, ValueError, json.JSONDecodeError) as exc:
            raise OlympusContextError(
                "olympus_context_invalid",
                "Telegram target context is not valid JSON",
            ) from exc
    target_normalized = normalize_olympus_context(raw_target_context)
    if any(
        target_normalized[key] != root["context"][key]
        for key in (
            "goal_id", "program_id", "milestone_id", "mission_id",
            "workstream_id",
        )
    ):
        raise OlympusContextError(
            "olympus_authorization_root_foreign",
            "Telegram target is outside the selected authorization hierarchy",
        )
    target_lease = target_normalized["lease"]
    target_assignee = str(target["assignee"] or "")
    if not (
        target_normalized["agent_id"]
        == target_lease["agent_id"]
        == target_lease["holder"]
        == target_assignee
    ):
        raise OlympusContextError(
            "olympus_agent_mismatch",
            "Telegram target lease, delegated agent, and assignee do not match",
        )
    authority = target_normalized["authority"]
    identity = {
        "authorization_subject_id": root["id"],
        "authorization_subject_revision": root["record_revision"],
        "authorization_subject_status": root["status"],
        "control_action": action,
        "task_id": str(target["id"]),
        "task_record_revision": int(target["record_revision"]),
        "goal_id": target_normalized["goal_id"],
        "program_id": target_normalized["program_id"],
        "milestone_id": target_normalized["milestone_id"],
        "mission_id": target_normalized["mission_id"],
        "workstream_id": target_normalized["workstream_id"],
        "agent_id": target_normalized["agent_id"],
        "assignee": target_assignee,
        "status": str(target["status"]),
        "authority_id": authority["authority_id"],
        "authority_revision": authority["revision"],
        "authority_status": authority["status"],
        "authority_source": authority["source"],
        "lease_id": target_lease["lease_id"],
        "lease_revision": target_lease["revision"],
        "lease_status": target_lease["status"],
        "lease_source": target_lease["source"],
        "lease_agent_id": target_lease["agent_id"],
        "lease_holder": target_lease["holder"],
    }
    return identity, root


def _authorization_root_snapshot(
    conn: sqlite3.Connection,
    *,
    principal: OlympusMutationAuth,
    target_context: dict[str, Any],
    target_task_id: str,
    target_record_revision: int,
    target_status: str,
    target_assignee: str,
    action: str,
) -> Optional[dict[str, Any]]:
    if principal.target_identity is None:
        return None
    try:
        supplied = _require_exact_keys(
            principal.target_identity,
            frozenset(OLYMPUS_TARGET_IDENTITY_KEYS),
            "target_identity",
        )
    except AuthorityContractError as exc:
        raise OlympusContextError(
            "olympus_target_identity_invalid", str(exc)
        ) from exc
    expected, root = _telegram_target_identity(
        conn,
        authorization_task_id=str(supplied["authorization_subject_id"]),
        target_task_id=target_task_id,
        action=action,
        target_context=target_context,
    )
    if (
        supplied != expected
        or expected["task_record_revision"] != int(target_record_revision)
        or expected["status"] != target_status
        or expected["assignee"] != target_assignee
    ):
        raise OlympusContextError(
            "olympus_target_identity_conflict",
            "Telegram target identity is stale, foreign, or contradictory",
        )
    return root


def olympus_telegram_auth(
    conn: sqlite3.Connection,
    *,
    verifier: AuthorityVerifier,
    source_identity: Mapping[str, Any],
    authorization_task_id: str,
    target_task_id: str,
    action: str,
    operation_id: str,
) -> OlympusMutationAuth:
    """Build one canonical Telegram principal from authenticated/live state."""
    if action not in TELEGRAM_ACTION_CAPABILITIES:
        raise OlympusContextError(
            "olympus_telegram_action_invalid",
            "Telegram action is not registered in the frozen authority profile",
        )
    if not callable(verifier):
        raise OlympusContextError(
            "olympus_authority_verification_unavailable",
            "canonical authority verifier is unavailable",
        )
    try:
        source = _require_exact_keys(
            dict(source_identity), frozenset(OLYMPUS_SOURCE_IDENTITY_KEYS),
            "source_identity",
        )
        normalized_source = {
            "platform": _strict_text(source["platform"], "source_identity.platform"),
            "bot_id": _strict_text(source["bot_id"], "source_identity.bot_id"),
            "profile": _strict_text(source["profile"], "source_identity.profile"),
            "chat_id": _strict_text(source["chat_id"], "source_identity.chat_id"),
            "thread_id": _strict_string(
                source["thread_id"], "source_identity.thread_id", allow_empty=True,
            ),
            "user_id": _strict_text(source["user_id"], "source_identity.user_id"),
        }
    except (AuthorityContractError, TypeError, ValueError) as exc:
        raise OlympusContextError(
            "olympus_source_identity_invalid", str(exc)
        ) from exc
    if normalized_source["platform"] != "telegram":
        raise OlympusContextError(
            "olympus_source_identity_invalid",
            "governed Telegram operations require platform=telegram",
        )
    target = conn.execute(
        "SELECT assignee, olympus_context FROM tasks WHERE id = ?",
        (str(target_task_id).strip(),),
    ).fetchone()
    if target is None or target["olympus_context"] is None:
        raise OlympusContextError(
            "olympus_control_target_missing",
            "Telegram target is missing or ungoverned",
        )
    target_context = _require_current_olympus_context(
        target["olympus_context"], assignee=target["assignee"]
    )
    if target_context is None:
        raise OlympusContextError(
            "olympus_control_target_missing",
            "Telegram target is missing or ungoverned",
        )
    target_identity, root = _telegram_target_identity(
        conn,
        authorization_task_id=authorization_task_id,
        target_task_id=target_task_id,
        action=action,
        target_context=target_context,
    )
    return OlympusMutationAuth(
        verifier=verifier,
        principal_type="telegram_user",
        principal_id=(
            f"telegram:{normalized_source['bot_id']}:"
            f"{normalized_source['user_id']}"
        ),
        principal_source=(
            f"telegram-bot:{normalized_source['bot_id']}:"
            f"profile:{normalized_source['profile']}"
        ),
        actor=str(root["assignee"]),
        operation_id=_strict_text(operation_id, "operation_id"),
        source_identity=normalized_source,
        target_identity=target_identity,
    )


def olympus_service_auth(
    conn: sqlite3.Connection,
    *,
    verifier: AuthorityVerifier,
    dispatcher_instance_id: str,
    actor: str,
    operation_id: str,
) -> OlympusMutationAuth:
    """Build the exact trusted service-dispatcher principal for this board."""
    if not callable(verifier):
        raise OlympusContextError(
            "olympus_authority_verification_unavailable",
            "canonical authority verifier is unavailable",
        )
    board_id = _connection_board_identity(conn)
    dispatcher = _strict_text(
        dispatcher_instance_id, "dispatcher_instance_id"
    )
    return OlympusMutationAuth(
        verifier=verifier,
        principal_type="service",
        principal_id=f"kanban-service-dispatcher:{board_id}:{dispatcher}",
        principal_source=f"kanban-dispatcher:{board_id}:{dispatcher}",
        actor=_strict_text(actor, "actor"),
        operation_id=_strict_text(operation_id, "operation_id"),
    )


def verify_olympus_telegram_task(
    conn: sqlite3.Connection,
    *,
    authorization_task_id: str,
    target_task_id: str,
    action: str,
    verifier: AuthorityVerifier,
    source_identity: Mapping[str, Any],
    operation_id: str,
) -> dict[str, Any]:
    """Freshly verify one exact Telegram action without mutating task state."""
    auth = olympus_telegram_auth(
        conn,
        verifier=verifier,
        source_identity=source_identity,
        authorization_task_id=authorization_task_id,
        target_task_id=target_task_id,
        action=action,
        operation_id=operation_id,
    )
    with olympus_mutation_scope(auth), write_txn(conn):
        authorization, owns = _authorize_task_mutation(
            conn,
            target_task_id,
            action=action,
            capability=TELEGRAM_ACTION_CAPABILITIES[action],
            auth=auth,
            allow_inactive_target=action in TELEGRAM_EMERGENCY_ACTIONS,
        )
        try:
            row = conn.execute(
                "SELECT id, status, record_revision, assignee, olympus_context "
                "FROM tasks WHERE id = ?",
                (target_task_id,),
            ).fetchone()
            if row is None:
                raise OlympusContextError(
                    "olympus_task_missing", "verified Telegram target disappeared"
                )
            current_context = _require_current_olympus_context(
                row["olympus_context"], assignee=row["assignee"]
            )
            if current_context is None:
                raise OlympusContextError(
                    "olympus_control_target_missing",
                    "verified Telegram target became ungoverned",
                )
            return {
                "task_id": str(row["id"]),
                "status": str(row["status"]),
                "record_revision": int(row["record_revision"]),
                "assignee": str(row["assignee"] or ""),
                "context": current_context,
                "verification": authorization["verification"],
                "request": authorization["request"],
            }
        finally:
            _release_task_mutation_permit(conn, target_task_id, owns)


def _insert_issued_permit(
    conn: sqlite3.Connection,
    *,
    task_id: str,
    subject_revision: int,
    operation_id: str,
    action: str,
    capability: str,
    auth_root_id: str,
    auth_root_revision: int,
    verification_id: str,
    write_binding: Optional[Mapping[str, Any]] = None,
) -> None:
    registry = getattr(conn, "_olympus_permit_registry", None)
    if registry is None:
        raise OlympusContextError(
            "olympus_permit_registry_missing",
            "process-local permit registry is unavailable",
        )
    if bool(getattr(conn, "_olympus_external_txn", False)) \
            or int(getattr(conn, "_olympus_managed_txn_depth", 0)) <= 0:
        raise OlympusContextError(
            "olympus_external_transaction_forbidden",
            "governed permits require one Hermes-owned composing transaction",
        )
    encoded_binding = None
    if write_binding is not None:
        try:
            encoded_binding = json.dumps(
                dict(write_binding),
                sort_keys=True,
                separators=(",", ":"),
                allow_nan=False,
            )
        except (TypeError, ValueError) as exc:
            raise OlympusContextError(
                "olympus_permit_binding_invalid",
                "process-local permit binding is not canonical JSON",
            ) from exc
    issued = (
        int(subject_revision), str(operation_id), str(action), str(capability),
        str(auth_root_id), int(auth_root_revision), str(verification_id),
        encoded_binding,
    )
    existing = registry.get(str(task_id))
    if existing is not None and existing != issued:
        raise OlympusContextError(
            "olympus_permit_scope_conflict",
            "an issued permit cannot be retained or rebound",
        )
    registry[str(task_id)] = issued


def _bind_issued_permit_write(
    conn: sqlite3.Connection,
    task_id: str,
    write_binding: Mapping[str, Any],
) -> None:
    """Attach one exact immutable SQL row intent to an active permit."""
    registry = getattr(conn, "_olympus_permit_registry", None)
    issued = None if registry is None else registry.get(str(task_id))
    if issued is None:
        raise OlympusContextError(
            "olympus_permit_registry_missing",
            "receipt binding requires an active exact permit",
        )
    try:
        encoded = json.dumps(
            dict(write_binding), sort_keys=True, separators=(",", ":"),
            allow_nan=False,
        )
    except (TypeError, ValueError) as exc:
        raise OlympusContextError(
            "olympus_permit_binding_invalid",
            "receipt binding is not canonical JSON",
        ) from exc
    if issued[7] is not None and issued[7] != encoded:
        raise OlympusContextError(
            "olympus_permit_scope_conflict",
            "an issued permit cannot be rebound to another SQL row",
        )
    registry[str(task_id)] = (*issued[:7], encoded)


def _issued_permit_row(
    conn: sqlite3.Connection, task_id: str,
) -> Optional[dict[str, Any]]:
    registry = getattr(conn, "_olympus_permit_registry", None)
    issued = None if registry is None else registry.get(str(task_id))
    if issued is None:
        return None
    return {
        "subject_revision": int(issued[0]), "operation_id": str(issued[1]),
        "action": str(issued[2]), "capability": str(issued[3]),
        "auth_root_id": str(issued[4]), "auth_root_revision": int(issued[5]),
        "verification_id": str(issued[6]),
        "write_binding": (
            None if issued[7] is None else json.loads(str(issued[7]))
        ),
    }


def olympus_worker_runtime_snapshot(
    conn: sqlite3.Connection,
    *,
    worker_task_id: str,
    run_id: int,
    claim_lock: str,
    now: Optional[int] = None,
) -> dict[str, Any]:
    """Return the exact live worker identity used by trusted tool hooks.

    All inputs come from dispatcher-owned process state, never a model tool
    payload.  The returned snapshot is revalidated inside every governed
    mutation so a reclaimed or superseded worker cannot reuse an old binding.
    """
    if (
        not isinstance(worker_task_id, str)
        or not worker_task_id.strip()
        or isinstance(run_id, bool)
        or not isinstance(run_id, int)
        or run_id <= 0
        or not isinstance(claim_lock, str)
        or not claim_lock.strip()
    ):
        raise OlympusContextError(
            "olympus_runtime_identity_invalid",
            "worker task, run, and claim identities are required",
        )
    row = conn.execute(
        "SELECT t.id AS worker_task_id, t.record_revision AS worker_task_revision, "
        "t.status AS worker_status, t.assignee AS worker_assignee, "
        "t.claim_lock, t.claim_expires, t.current_run_id, t.olympus_context, "
        "r.id AS run_id, r.subject_revision AS run_subject_revision, "
        "r.status AS run_status, r.claim_lock AS run_claim_lock, "
        "r.claim_expires AS run_claim_expires, r.ended_at, "
        "r.olympus_context AS run_olympus_context, r.process_state, "
        "r.worker_pid, r.worker_host_id, r.worker_boot_id, "
        "r.worker_start_token, r.dispatcher_instance_id "
        "FROM tasks t JOIN task_runs r ON r.id = t.current_run_id "
        "WHERE t.id = ? AND r.id = ?",
        (worker_task_id.strip(), int(run_id)),
    ).fetchone()
    current = int(time.time()) if now is None else int(now)
    if (
        row is None
        or row["olympus_context"] is None
        or row["worker_status"] != "running"
        or row["run_status"] != "running"
        or row["process_state"] != "registered"
        or row["ended_at"] is not None
        or row["claim_lock"] != claim_lock
        or row["run_claim_lock"] != claim_lock
        or row["claim_expires"] is None
        or row["run_claim_expires"] is None
        or int(row["claim_expires"]) <= current
        or int(row["run_claim_expires"]) <= current
        or row["run_subject_revision"] is None
        or row["worker_pid"] is None
        or not row["worker_host_id"]
        or not row["worker_boot_id"]
        or not row["worker_start_token"]
        or not row["dispatcher_instance_id"]
    ):
        raise OlympusContextError(
            "olympus_runtime_identity_stale",
            "worker task, run, or claim identity is no longer current",
        )
    task_context = _require_current_olympus_context(
        row["olympus_context"],
        assignee=row["worker_assignee"],
        now=current,
    )
    assert task_context is not None
    run_context = _require_matching_olympus_run_context(
        row["run_olympus_context"],
        task_context=task_context,
        assignee=row["worker_assignee"],
        now=current,
        run_subject_revision=row["run_subject_revision"],
        task_record_revision=int(row["worker_task_revision"]),
    )
    if run_context is None:
        raise OlympusContextError(
            "olympus_run_context_mismatch",
            "registered worker run lacks governed context",
        )
    stored_process = ProcessIdentity(
        host_id=str(row["worker_host_id"]),
        boot_id=str(row["worker_boot_id"]),
        pid=int(row["worker_pid"]),
        start_token=str(row["worker_start_token"]),
    )
    if read_process_identity(stored_process.pid) != stored_process:
        raise OlympusContextError(
            "olympus_runtime_process_mismatch",
            "registered worker process identity is no longer live",
        )
    return {
        "board_id": _connection_board_identity(conn),
        "worker_task_id": str(row["worker_task_id"]),
        "worker_task_revision": int(row["worker_task_revision"]),
        "worker_status": str(row["worker_status"]),
        "worker_assignee": str(row["worker_assignee"] or ""),
        "run_id": int(row["run_id"]),
        "run_subject_revision": int(row["run_subject_revision"]),
        "run_status": str(row["run_status"]),
        "claim_lock": str(row["claim_lock"]),
        "claim_expires": min(
            int(row["claim_expires"]), int(row["run_claim_expires"]),
        ),
        "process_state": str(row["process_state"]),
        "host_id": stored_process.host_id,
        "boot_id": stored_process.boot_id,
        "pid": stored_process.pid,
        "start_token": stored_process.start_token,
        "dispatcher_instance_id": str(row["dispatcher_instance_id"]),
    }


def olympus_notifier_identity_snapshot(
    conn: sqlite3.Connection,
    *,
    task_id: str,
    platform: str,
    chat_id: str,
    thread_id: Optional[str] = None,
    source_event_id: int,
    effect_id: str,
    effect_state: str,
    gateway_process_identity: ProcessIdentity,
) -> dict[str, Any]:
    """Return one exact subscription/event/effect/gateway identity."""
    if read_process_identity(gateway_process_identity.pid) != gateway_process_identity:
        raise OlympusContextError(
            "olympus_notifier_process_mismatch",
            "notifier gateway process identity is not live",
        )
    row = conn.execute(
        "SELECT s.*, t.record_revision AS task_record_revision, "
        "t.olympus_context FROM kanban_notify_subs s "
        "JOIN tasks t ON t.id = s.task_id "
        "WHERE s.task_id = ? AND s.platform = ? AND s.chat_id = ? "
        "AND s.thread_id = ?",
        (task_id, platform, chat_id, thread_id or ""),
    ).fetchone()
    if row is None or row["olympus_context"] is None:
        raise OlympusContextError(
            "olympus_notifier_identity_missing",
            "governed notification subscription is missing",
        )
    event = conn.execute(
        "SELECT 1 FROM task_events WHERE id = ? AND task_id = ?",
        (int(source_event_id), task_id),
    ).fetchone()
    if event is None:
        raise OlympusContextError(
            "olympus_notifier_event_missing",
            "notification source event does not belong to the task",
        )
    if effect_state == "unreserved":
        effect = None
    else:
        effect = conn.execute(
            "SELECT state, event_id FROM kanban_effect_journal "
            "WHERE operation_id = ? AND task_id = ? "
            "AND effect_kind IN ('notify_text','notify_artifact')",
            (effect_id, task_id),
        ).fetchone()
        if (
            effect is None
            or str(effect["state"]) != effect_state
            or int(effect["event_id"]) != int(source_event_id)
        ):
            raise OlympusContextError(
                "olympus_notifier_effect_conflict",
                "notification effect identity is not current",
            )
    return {
        "board_id": _connection_board_identity(conn),
        "task_id": str(row["task_id"]),
        "task_record_revision": int(row["task_record_revision"]),
        "platform": str(row["platform"]),
        "chat_id": str(row["chat_id"]),
        "thread_id": str(row["thread_id"] or ""),
        "user_id": (str(row["user_id"]) if row["user_id"] is not None else None),
        "notifier_profile": (
            str(row["notifier_profile"])
            if row["notifier_profile"] is not None else None
        ),
        "created_at": int(row["created_at"]),
        "last_event_id": int(row["last_event_id"]),
        "source_event_id": int(source_event_id),
        "effect_id": str(effect_id),
        "effect_state": str(effect_state),
        "gateway_host_id": gateway_process_identity.host_id,
        "gateway_boot_id": gateway_process_identity.boot_id,
        "gateway_pid": gateway_process_identity.pid,
        "gateway_start_token": gateway_process_identity.start_token,
    }


def olympus_notifier_auth(
    conn: sqlite3.Connection,
    *,
    verifier: AuthorityVerifier,
    task_id: str,
    platform: str,
    chat_id: str,
    thread_id: Optional[str],
    source_event_id: int,
    effect_id: str,
    effect_state: str,
    gateway_process_identity: ProcessIdentity,
    action: str,
) -> OlympusMutationAuth:
    """Build the canonical notifier principal from persisted/live identity."""
    if action not in NOTIFICATION_PRINCIPAL_ACTIONS:
        raise OlympusContextError(
            "olympus_notifier_action_invalid",
            "action is not bound to the canonical notifier principal",
        )
    identity = olympus_notifier_identity_snapshot(
        conn,
        task_id=task_id,
        platform=platform,
        chat_id=chat_id,
        thread_id=thread_id,
        source_event_id=source_event_id,
        effect_id=effect_id,
        effect_state=effect_state,
        gateway_process_identity=gateway_process_identity,
    )
    destination = ":".join((
        identity["platform"], identity["chat_id"],
        identity["thread_id"] or "", identity["user_id"] or "",
    ))
    return OlympusMutationAuth(
        verifier=verifier,
        principal_type="kanban_notifier",
        principal_id=(
            f"kanban-notifier:{identity['board_id']}:{task_id}:"
            f"{destination}:{effect_id}"
        ),
        principal_source=(
            f"kanban-gateway:{identity['gateway_host_id']}:"
            f"{identity['gateway_boot_id']}:{identity['gateway_pid']}:"
            f"{identity['gateway_start_token']}"
        ),
        operation_id=f"notifier:{effect_id}:{action}",
        notifier_identity=identity,
    )


def _authorize_task_mutation(
    conn: sqlite3.Connection,
    task_id: str,
    *,
    action: str,
    capability: str,
    auth: Optional[OlympusMutationAuth] = None,
    context_override: Optional[dict[str, Any]] = None,
    operation_binding: Optional[dict[str, Any]] = None,
    mutation_binding: Optional[dict[str, Any]] = None,
    allow_inactive: bool = False,
    allow_inactive_target: bool = False,
) -> tuple[Optional[dict[str, Any]], bool]:
    """Issue a DB-enforced permit for one exact governed task revision.

    Returns ``(authorization, owns_permit)``. Ordinary tasks return
    ``(None, False)`` without consulting an issuer. A nested helper reuses the
    permit belonging to the same composed operation, never across calls.
    """
    row = conn.execute(
        "SELECT id, assignee, status, record_revision, olympus_context "
        "FROM tasks WHERE id = ?",
        (task_id,),
    ).fetchone()
    if row is None or row["olympus_context"] is None:
        return None, False
    bound = auth or _OLYMPUS_MUTATION_AUTH.get()
    if bound is None:
        raise OlympusContextError(
            "olympus_authority_verification_unavailable",
            "canonical authority verifier is unavailable",
        )
    revision = int(row["record_revision"])
    write_binding: Optional[dict[str, Any]] = None
    exact_mutation_binding: Optional[dict[str, Any]] = None
    if action in SUBSCRIPTION_REGISTRATION_ACTIONS:
        if operation_binding is None:
            raise OlympusContextError(
                "olympus_subscription_binding_missing",
                "governed subscription registration requires exact add intent",
            )
        try:
            write_binding = _normalize_notification_subscription_operation_binding(
                operation_binding,
                target={
                    "subject_id": task_id,
                    "subject_revision": revision,
                },
                board_id=_connection_board_identity(conn),
            )
        except (AuthorityContractError, TypeError, ValueError) as exc:
            raise OlympusContextError(
                "olympus_subscription_binding_invalid", str(exc)
            ) from exc
    elif operation_binding is not None:
        raise OlympusContextError(
            "olympus_subscription_binding_forbidden",
            "an add-only subscription binding cannot authorize another action",
        )
    if mutation_binding is not None:
        try:
            exact_mutation_binding = _normalize_exact_mutation_binding(
                mutation_binding,
                action=action,
                task_id=task_id,
                task_record_revision=revision,
            )
        except (AuthorityContractError, TypeError, ValueError) as exc:
            raise OlympusContextError(
                "olympus_mutation_binding_invalid", str(exc)
            ) from exc
    elif action in _EXACT_MUTATION_BINDING_ACTIONS:
        raise OlympusContextError(
            "olympus_mutation_binding_missing",
            "governed mutation requires an exact process-local write binding",
        )
    intent_key = (action, capability)
    if intent_key not in _OLYMPUS_TASK_WRITE_COLUMNS:
        raise OlympusContextError(
            "olympus_write_intent_unknown",
            "governed mutation has no registered task write intent",
        )
    if bound.runtime_identity is not None:
        runtime = bound.runtime_identity
        try:
            live_runtime = olympus_worker_runtime_snapshot(
                conn,
                worker_task_id=str(runtime.get("worker_task_id", "")),
                run_id=runtime.get("run_id"),
                claim_lock=str(runtime.get("claim_lock", "")),
            )
        except (AttributeError, TypeError, ValueError) as exc:
            raise OlympusContextError(
                "olympus_runtime_identity_invalid",
                "worker runtime identity is invalid",
            ) from exc
        if runtime != live_runtime or live_runtime["worker_task_id"] != task_id:
            raise OlympusContextError(
                "olympus_runtime_identity_conflict",
                "worker runtime binding changed or targeted a different task",
            )
    if bound.notifier_identity is not None:
        notifier = bound.notifier_identity
        try:
            live_notifier = olympus_notifier_identity_snapshot(
                conn,
                task_id=str(notifier.get("task_id", "")),
                platform=str(notifier.get("platform", "")),
                chat_id=str(notifier.get("chat_id", "")),
                thread_id=notifier.get("thread_id"),
                source_event_id=notifier.get("source_event_id"),
                effect_id=str(notifier.get("effect_id", "")),
                effect_state=str(notifier.get("effect_state", "")),
                gateway_process_identity=ProcessIdentity(
                    host_id=str(notifier.get("gateway_host_id", "")),
                    boot_id=str(notifier.get("gateway_boot_id", "")),
                    pid=int(notifier.get("gateway_pid", 0)),
                    start_token=str(notifier.get("gateway_start_token", "")),
                ),
            )
        except (AttributeError, TypeError, ValueError) as exc:
            raise OlympusContextError(
                "olympus_notifier_identity_invalid",
                "notifier identity is invalid",
            ) from exc
        if notifier != live_notifier or live_notifier["task_id"] != task_id:
            raise OlympusContextError(
                "olympus_notifier_identity_conflict",
                "notifier binding changed before the governed mutation",
            )
        if action == "reserve_notification_effect":
            expected_source, _ = _canonical_effect_payload(
                _canonical_notifier_effect_source_identity(live_notifier)
            )
            expected_destination = ":".join((
                live_notifier["platform"], live_notifier["chat_id"],
                live_notifier["thread_id"] or "",
            ))
            if (
                exact_mutation_binding is None
                or exact_mutation_binding["source_identity"] != expected_source
                or exact_mutation_binding["event_id"]
                    != live_notifier["source_event_id"]
                or exact_mutation_binding["operation_id"]
                    != live_notifier["effect_id"]
                or exact_mutation_binding["destination_key"]
                    != expected_destination
            ):
                raise OlympusContextError(
                    "olympus_effect_binding_conflict",
                    "effect write intent does not match the live notifier identity",
                )
        if exact_mutation_binding is not None:
            write_binding = {
                "schema_version": NOTIFIER_MUTATION_WRITE_SCHEMA,
                "notifier": live_notifier,
                "mutation": exact_mutation_binding,
            }
        else:
            write_binding = live_notifier
    elif action in NOTIFICATION_PRINCIPAL_ACTIONS:
        raise OlympusContextError(
            "olympus_notifier_identity_missing",
            "notification delivery mutations require exact notifier identity",
        )
    elif exact_mutation_binding is not None:
        write_binding = exact_mutation_binding
    existing = _issued_permit_row(conn, task_id)
    if existing is not None:
        if (
            existing["action"] != action
            or existing["capability"] != capability
            or existing["write_binding"] != write_binding
        ):
            raise OlympusContextError(
                "olympus_permit_scope_conflict",
                "an authority permit cannot authorize another action or bound tuple",
            )
        return {
            "subject_revision": int(existing["subject_revision"]),
            "operation_id": existing["operation_id"],
            "action": existing["action"],
        }, False
    raw_context: Any = context_override
    if raw_context is None:
        raw_context = row["olympus_context"]
    if isinstance(raw_context, str):
        try:
            raw_context = json.loads(raw_context)
        except Exception as exc:
            raise OlympusContextError(
                "olympus_context_invalid",
                "stored Olympus context is not valid JSON",
            ) from exc
    normalized_context = normalize_olympus_context(raw_context)
    authorization_root = _authorization_root_snapshot(
        conn,
        principal=bound,
        target_context=normalized_context,
        target_task_id=task_id,
        target_record_revision=revision,
        target_status=str(row["status"]),
        target_assignee=str(row["assignee"] or ""),
        action=action,
    )
    target_assignee = str(row["assignee"] or "")
    if authorization_root is not None:
        if allow_inactive_target and action not in TELEGRAM_EMERGENCY_ACTIONS:
            raise OlympusContextError(
                "olympus_inactive_authority_forbidden",
                "only interrupt/cancel may contain an inactive target",
            )
        if allow_inactive_target:
            target_lease = normalized_context["lease"]
            if target_lease["mission_id"] != normalized_context["mission_id"]:
                raise OlympusContextError(
                    "olympus_lease_foreign_mission",
                    "target lease mission does not match target mission",
                )
            if not (
                normalized_context["agent_id"]
                == target_lease["agent_id"]
                == target_lease["holder"]
                == target_assignee
            ):
                raise OlympusContextError(
                    "olympus_agent_mismatch",
                    "target lease and assignee identities must match exactly",
                )
        else:
            normalized_context = _require_current_olympus_context(
                normalized_context,
                assignee=target_assignee,
            )
            assert normalized_context is not None
    root_id = authorization_root["id"] if authorization_root is not None else task_id
    root_revision = (
        int(authorization_root["record_revision"])
        if authorization_root is not None else revision
    )
    actor = str(
        bound.actor
        or (
            authorization_root["context"]["lease"]["holder"]
            if authorization_root is not None
            else target_assignee
        )
    )
    if action in SUBSCRIPTION_REGISTRATION_ACTIONS:
        operation_id = notification_subscription_operation_id(write_binding)
    else:
        operation_prefix = str(bound.operation_id or "kanban")
        operation_id = (
            f"{operation_prefix}:{action}:{root_id}:"
            f"r{root_revision}:target:{task_id}:r{revision}"
        )
    authorization = require_olympus_authority_verification(
        normalized_context,
        subject_id=task_id,
        subject_revision=revision,
        assignee=target_assignee,
        action=action,
        capability=capability,
        actor=actor,
        operation_id=operation_id,
        principal=bound,
        expected_status=str(row["status"]),
        authorization_root=authorization_root,
        allow_inactive=allow_inactive_target,
        board_id=_connection_board_identity(conn),
        operation_binding=write_binding if action in SUBSCRIPTION_REGISTRATION_ACTIONS else None,
    )
    if action == "register_worker_process":
        verified_dispatcher = authorization["request"]["principal"].get(
            "dispatcher_instance_id"
        )
        if (
            exact_mutation_binding is None
            or verified_dispatcher
            != exact_mutation_binding["dispatcher_instance_id"]
        ):
            raise OlympusContextError(
                "olympus_dispatcher_identity_conflict",
                "persisted dispatcher identity does not match verified principal",
            )
    _insert_issued_permit(
        conn,
        task_id=task_id,
        subject_revision=revision,
        operation_id=operation_id,
        action=action,
        capability=capability,
        auth_root_id=root_id,
        auth_root_revision=root_revision,
        verification_id=str(
            authorization["verification"]["verification_id"]
        ),
        write_binding=write_binding,
    )
    return authorization, True


def _release_task_mutation_permit(
    conn: sqlite3.Connection, task_id: str, owns_permit: bool,
) -> None:
    if owns_permit:
        registry = getattr(conn, "_olympus_permit_registry", None)
        if registry is not None:
            registry.pop(str(task_id), None)


@contextlib.contextmanager
def _task_mutation_permit(
    conn: sqlite3.Connection,
    task_id: str,
    *,
    action: str,
    capability: str,
    auth: Optional[OlympusMutationAuth] = None,
    context_override: Optional[dict[str, Any]] = None,
    operation_binding: Optional[dict[str, Any]] = None,
    mutation_binding: Optional[dict[str, Any]] = None,
    allow_inactive: bool = False,
    allow_inactive_target: bool = False,
):
    authorization, owns = _authorize_task_mutation(
        conn,
        task_id,
        action=action,
        capability=capability,
        auth=auth,
        context_override=context_override,
        operation_binding=operation_binding,
        mutation_binding=mutation_binding,
        allow_inactive=allow_inactive,
        allow_inactive_target=allow_inactive_target,
    )
    try:
        yield authorization
    finally:
        _release_task_mutation_permit(conn, task_id, owns)


def _guarded_task_mutation(
    *,
    action: str,
    capability: str,
    task_params: tuple[str, ...] = ("task_id",),
    touch_aggregate: bool = False,
    success: Optional[Callable[[Any], bool]] = None,
):
    """Decorate a public mutator with the central governed write boundary."""
    def decorate(fn):
        signature = inspect.signature(fn)

        @functools.wraps(fn)
        def wrapped(*args, **kwargs):
            explicit_auth = kwargs.pop("olympus_auth", None)
            bound_args = signature.bind(*args, **kwargs)
            bound_args.apply_defaults()
            conn = bound_args.arguments.get("conn")
            if not isinstance(conn, sqlite3.Connection):
                raise TypeError("guarded Kanban mutation requires a SQLite connection")
            task_ids = [
                str(bound_args.arguments[name])
                for name in task_params
                if bound_args.arguments.get(name) is not None
            ]
            with olympus_mutation_scope(
                explicit_auth or _OLYMPUS_MUTATION_AUTH.get()
            ):
                with write_txn(conn):
                    permits: list[tuple[str, bool, Optional[dict[str, Any]]]] = []
                    try:
                        for tid in dict.fromkeys(task_ids):
                            operation_binding = None
                            if action in SUBSCRIPTION_REGISTRATION_ACTIONS:
                                task_row = conn.execute(
                                    "SELECT record_revision, olympus_context "
                                    "FROM tasks WHERE id = ?",
                                    (tid,),
                                ).fetchone()
                                if (
                                    task_row is not None
                                    and task_row["olympus_context"] is not None
                                ):
                                    operation_binding = {
                                        "schema_version": (
                                            NOTIFICATION_SUBSCRIPTION_OPERATION_SCHEMA
                                        ),
                                        "action": action,
                                        "board_id": _connection_board_identity(conn),
                                        "task_id": tid,
                                        "task_record_revision": int(
                                            task_row["record_revision"]
                                        ),
                                        "platform": bound_args.arguments["platform"],
                                        "chat_id": bound_args.arguments["chat_id"],
                                        "thread_id": (
                                            bound_args.arguments.get("thread_id") or ""
                                        ),
                                        "user_id": bound_args.arguments.get("user_id"),
                                        "notifier_profile": bound_args.arguments.get(
                                            "notifier_profile"
                                        ),
                                    }
                            authorization, owns = _authorize_task_mutation(
                                conn,
                                tid,
                                action=action,
                                capability=capability,
                                auth=explicit_auth,
                                operation_binding=operation_binding,
                            )
                            permits.append((tid, owns, authorization))
                        result = fn(*args, **kwargs)
                        changed = success(result) if success is not None else result is not False
                        if touch_aggregate and changed:
                            for tid, _, authorization in permits:
                                if authorization is not None:
                                    conn.execute(
                                        "UPDATE tasks SET record_revision = record_revision "
                                        "WHERE id = ?",
                                        (tid,),
                                    )
                        return result
                    finally:
                        for tid, owns, _ in reversed(permits):
                            _release_task_mutation_permit(conn, tid, owns)

        return wrapped
    return decorate


# ---------------------------------------------------------------------------
# ID generation
# ---------------------------------------------------------------------------

def _new_task_id() -> str:
    """Generate a short, URL-safe task id.

    4 hex bytes = ~4.3B possibilities. At 10k tasks the collision
    probability is ~1.2e-5; at 100k it's ~1.2e-3. Previously we used 2
    hex bytes (65k possibilities) which hit the birthday paradox hard:
    ~5% collision probability at 1k tasks, ~50% at 10k. Callers that
    care about idempotency should pass ``idempotency_key`` to
    :func:`create_task` rather than rely on id uniqueness.
    """
    return "t_" + secrets.token_hex(4)


def _claimer_id() -> str:
    """Return a ``host:pid`` string that identifies this claimer."""
    import socket
    try:
        host = socket.gethostname() or "unknown"
    except Exception:
        host = "unknown"
    return f"{host}:{os.getpid()}"


# ---------------------------------------------------------------------------
# Task creation / mutation
# ---------------------------------------------------------------------------

def _canonical_assignee(assignee: Optional[str]) -> Optional[str]:
    """Lowercase-assignee normalization for Kanban rows (dashboard/CLI parity)."""
    if assignee is None:
        return None
    from hermes_cli.profiles import normalize_profile_name

    return normalize_profile_name(assignee)


def _initial_task_status(
    conn: sqlite3.Connection,
    *,
    parents: Iterable[str],
    triage: bool,
    initial_status: str,
) -> str:
    """Resolve and validate the exact status a new task will persist."""
    parent_ids = tuple(parents)
    if initial_status == "blocked":
        task_status = "blocked"
    elif triage:
        task_status = "triage"
    else:
        task_status = "ready"
    if parent_ids:
        missing = _find_missing_parents(conn, parent_ids)
        if missing:
            raise ValueError(f"unknown parent task(s): {', '.join(missing)}")
        if task_status == "ready":
            rows = conn.execute(
                "SELECT status FROM tasks WHERE id IN ("
                + ",".join("?" * len(parent_ids)) + ")",
                parent_ids,
            ).fetchall()
            if any(row["status"] != "done" for row in rows):
                task_status = "todo"
    return task_status


def _normalize_task_skills(skills: Optional[Iterable[str]]) -> Optional[list[str]]:
    """Return the exact effective per-task skill list used by persistence."""
    if skills is None:
        return None
    cleaned: list[str] = []
    seen: set[str] = set()
    toolset_typos: list[str] = []
    for skill in skills:
        if not skill:
            continue
        name = str(skill).strip()
        if not name:
            continue
        if "," in name:
            raise ValueError(
                f"skill name cannot contain comma: {name!r} "
                "(pass a list of separate names instead of a comma-joined string)"
            )
        if name.casefold() in KNOWN_TOOLSET_NAMES:
            toolset_typos.append(name)
            continue
        if name in seen:
            continue
        seen.add(name)
        cleaned.append(name)
    if toolset_typos:
        quoted = ", ".join(repr(name) for name in toolset_typos)
        noun = "is a toolset name" if len(toolset_typos) == 1 else "are toolset names"
        raise ValueError(
            f"{quoted} {noun}, not skill name(s). "
            "Put toolsets in the assignee profile's `toolsets:` config "
            "instead of per-task skills. Skills are named skill bundles "
            "(e.g. `kanban-worker`, `blogwatcher`); toolsets are runtime "
            "capabilities (e.g. `web`, `browser`, `terminal`)."
        )
    return cleaned


def _create_task_internal(
    conn: sqlite3.Connection,
    *,
    title: str,
    body: Optional[str] = None,
    assignee: Optional[str] = None,
    created_by: Optional[str] = None,
    workspace_kind: str = "scratch",
    workspace_path: Optional[str] = None,
    branch_name: Optional[str] = None,
    tenant: Optional[str] = None,
    priority: int = 0,
    parents: Iterable[str] = (),
    triage: bool = False,
    idempotency_key: Optional[str] = None,
    max_runtime_seconds: Optional[int] = None,
    skills: Optional[Iterable[str]] = None,
    max_retries: Optional[int] = None,
    goal_mode: bool = False,
    goal_max_turns: Optional[int] = None,
    initial_status: str = "running",
    session_id: Optional[str] = None,
    board: Optional[str] = None,
    olympus_context: Optional[dict[str, Any]] = None,
    _task_id: Optional[str] = None,
) -> str:
    """Create a new task and optionally link it under parent tasks.

    Returns the new task id.  Status is ``ready`` when there are no
    parents (or all parents already ``done``), otherwise ``todo``.
    If ``triage=True``, status is forced to ``triage`` regardless of
    parents — a specifier/triager is expected to promote the task to
    ``todo`` once the spec is fleshed out.

    If ``idempotency_key`` is provided and a non-archived task with the
    same key already exists, returns the existing task's id instead of
    creating a duplicate. Useful for retried webhooks / automation that
    should not double-write.

    ``max_runtime_seconds`` caps how long a worker may run before the
    dispatcher SIGTERMs (then SIGKILLs after a grace window) and
    re-queues the task. ``None`` means no cap (default).

    ``skills`` is an optional list of skill names to force-load into
    the worker when dispatched. Stored as JSON; the dispatcher passes
    each name to ``hermes --skills ...`` alongside the built-in
    ``kanban-worker``. Use this to pin a task to a specialist skill
    (e.g. ``skills=["translation"]`` so the worker loads the
    translation skill regardless of the profile's default config).
    """
    assignee = _canonical_assignee(assignee)
    if not title or not title.strip():
        raise ValueError("title is required")
    if initial_status not in VALID_INITIAL_STATUSES:
        raise ValueError(
            f"initial_status must be one of {sorted(VALID_INITIAL_STATUSES)}"
        )
    if workspace_kind not in VALID_WORKSPACE_KINDS:
        raise ValueError(
            f"workspace_kind must be one of {sorted(VALID_WORKSPACE_KINDS)}, "
            f"got {workspace_kind!r}"
        )
    if branch_name is not None:
        branch_name = str(branch_name).strip() or None
    if branch_name and workspace_kind != "worktree":
        raise ValueError("branch_name is only valid for worktree workspaces")
    parents = tuple(p for p in parents if p)

    # Only the dedicated verified wrapper may provide Olympus context.  Generic
    # callers cannot opt a task in, renew authority, or inherit a privileged
    # parent context merely by knowing row identifiers.
    normalized_olympus: Optional[dict[str, Any]] = None
    if olympus_context is not None:
        normalized_olympus = normalize_olympus_context(olympus_context)
    if parents:
        placeholders = ",".join("?" * len(parents))
        parent_rows = conn.execute(
            f"SELECT id, olympus_context FROM tasks WHERE id IN ({placeholders})",
            parents,
        ).fetchall()
        governed_parents = [r for r in parent_rows if r["olympus_context"] is not None]
        if normalized_olympus is None and governed_parents:
            raise OlympusContextError(
                "olympus_verified_context_required",
                "a governed child requires the dedicated canonical-verification path",
            )
        if normalized_olympus is not None and governed_parents:
            hierarchy_keys = (
                "goal_id", "program_id", "milestone_id", "mission_id"
            )
            for row in governed_parents:
                parent_context = normalize_olympus_context(
                    json.loads(row["olympus_context"])
                )
                if any(
                    normalized_olympus[key] != parent_context[key]
                    for key in hierarchy_keys
                ):
                    raise OlympusContextError(
                        "olympus_parent_context_conflict",
                        "child context does not match its Olympus parent mission",
                    )
    olympus_json = (
        _serialize_olympus_context(normalized_olympus)
        if normalized_olympus is not None else None
    )

    # Normalise + validate skills: strip whitespace, drop empties, dedupe
    # (preserving order). Refuse commas inside a single name so we don't
    # invisibly splatter a comma-joined string into one argv slot — the
    # `hermes --skills X,Y` comma syntax is handled in the dispatcher,
    # not here.
    # Collect all toolset-name confusions up front so the user sees the whole
    # list at once, and reuse the same canonical list in governed create
    # receipts so replay comparison cannot drift from persistence.
    skills_list = _normalize_task_skills(skills)

    # Idempotency check — return the existing task instead of creating a
    # duplicate. Done BEFORE entering write_txn to keep the fast path fast
    # and to avoid holding a write lock during the lookup. Race is
    # acceptable: two concurrent creators with the same key might both
    # insert, at which point both rows exist but the next lookup stabilises.
    if idempotency_key:
        row = conn.execute(
            "SELECT id, olympus_context FROM tasks WHERE idempotency_key = ? "
            "AND status != 'archived' "
            "ORDER BY created_at DESC LIMIT 1",
            (idempotency_key,),
        ).fetchone()
        if row:
            if row["olympus_context"] != olympus_json:
                raise OlympusContextError(
                    "olympus_idempotency_context_conflict",
                    "idempotency key already belongs to a different authority context",
                )
            return row["id"]

    now = int(time.time())

    # Resolve workspace_path from board-level default_workdir when the
    # caller did not specify one explicitly. Board defaults represent
    # persistent project checkouts, so only persistent workspace kinds may
    # inherit them. Scratch workspaces are auto-deleted on completion and
    # must stay under the per-board scratch root created by
    # ``resolve_workspace``; inheriting ``default_workdir`` for a scratch
    # task would point cleanup at the user's source tree (#28818). The
    # containment guard in ``_cleanup_workspace`` is the safety rail, but
    # we also stop the bad state from being created in the first place.
    if workspace_path is None and workspace_kind in {"dir", "worktree"}:
        board_slug = board if board else get_current_board()
        board_meta = read_board_metadata(board_slug)
        board_default = board_meta.get("default_workdir")
        if board_default:
            workspace_path = str(board_default)

    # Retry once on the extremely unlikely id collision.
    for attempt in range(1 if _task_id is not None else 2):
        task_id = _task_id or _new_task_id()
        try:
            with write_txn(conn):
                # Determine task status from parent status, unless the caller
                # parks it directly in blocked for human-ops review or in
                # triage for a specifier.
                task_status = _initial_task_status(
                    conn,
                    parents=parents,
                    triage=triage,
                    initial_status=initial_status,
                )

                conn.execute(
                    """
                    INSERT INTO tasks (
                        id, title, body, assignee, status, priority,
                        created_by, created_at, workspace_kind, workspace_path,
                        branch_name, tenant, idempotency_key, max_runtime_seconds,
                        skills, max_retries, goal_mode, goal_max_turns, session_id,
                        olympus_context, record_revision
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        task_id,
                        title.strip(),
                        body,
                        assignee,
                        task_status,
                        priority,
                        created_by,
                        now,
                        workspace_kind,
                        workspace_path,
                        branch_name,
                        tenant,
                        idempotency_key,
                        int(max_runtime_seconds) if max_runtime_seconds is not None else None,
                        json.dumps(skills_list) if skills_list is not None else None,
                        int(max_retries) if max_retries is not None else None,
                        1 if goal_mode else 0,
                        int(goal_max_turns) if goal_max_turns is not None else None,
                        session_id,
                        olympus_json,
                        1 if normalized_olympus is not None else 0,
                    ),
                )
                for pid in parents:
                    conn.execute(
                        "INSERT OR IGNORE INTO task_links (parent_id, child_id) VALUES (?, ?)",
                        (pid, task_id),
                    )
                _append_event(
                    conn,
                    task_id,
                    "created",
                    {
                        "assignee": assignee,
                        "status": task_status,
                        "parents": list(parents),
                        "tenant": tenant,
                        "branch_name": branch_name,
                        "skills": list(skills_list) if skills_list else None,
                        "goal_mode": bool(goal_mode) or None,
                        "olympus": (
                            _olympus_trace(normalized_olympus)
                            if normalized_olympus is not None else None
                        ),
                    },
                )
            return task_id
        except sqlite3.IntegrityError:
            if _task_id is not None or attempt == 1:
                raise
            # Retry with a fresh id.
            continue
    raise RuntimeError("unreachable")


def create_task(
    conn: sqlite3.Connection,
    *,
    title: str,
    body: Optional[str] = None,
    assignee: Optional[str] = None,
    created_by: Optional[str] = None,
    workspace_kind: str = "scratch",
    workspace_path: Optional[str] = None,
    branch_name: Optional[str] = None,
    tenant: Optional[str] = None,
    priority: int = 0,
    parents: Iterable[str] = (),
    triage: bool = False,
    idempotency_key: Optional[str] = None,
    max_runtime_seconds: Optional[int] = None,
    skills: Optional[Iterable[str]] = None,
    max_retries: Optional[int] = None,
    goal_mode: bool = False,
    goal_max_turns: Optional[int] = None,
    initial_status: str = "running",
    session_id: Optional[str] = None,
    board: Optional[str] = None,
) -> str:
    """Create an ordinary task; Olympus context is never caller-injectable."""
    return _create_task_internal(
        conn,
        title=title,
        body=body,
        assignee=assignee,
        created_by=created_by,
        workspace_kind=workspace_kind,
        workspace_path=workspace_path,
        branch_name=branch_name,
        tenant=tenant,
        priority=priority,
        parents=parents,
        triage=triage,
        idempotency_key=idempotency_key,
        max_runtime_seconds=max_runtime_seconds,
        skills=skills,
        max_retries=max_retries,
        goal_mode=goal_mode,
        goal_max_turns=goal_max_turns,
        initial_status=initial_status,
        session_id=session_id,
        board=board,
        olympus_context=None,
    )


def _canonical_json_record(value: Mapping[str, Any]) -> tuple[str, str]:
    try:
        encoded = json.dumps(
            dict(value), sort_keys=True, separators=(",", ":"), allow_nan=False,
        )
    except (TypeError, ValueError) as exc:
        raise OlympusContextError(
            "olympus_idempotency_payload_invalid",
            "governed idempotency payload is not canonical JSON",
        ) from exc
    return encoded, hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def _olympus_create_request_payload(
    *, task_id: str, board_id: str, idempotency_key: str,
    olympus_context: dict[str, Any], title: str, body: Optional[str],
    assignee: str, created_by: Optional[str], workspace_kind: str,
    workspace_path: Optional[str], branch_name: Optional[str],
    tenant: Optional[str], priority: int, parents: tuple[str, ...],
    triage: bool, max_runtime_seconds: Optional[int],
    skills: Optional[list[str]], max_retries: Optional[int], goal_mode: bool,
    goal_max_turns: Optional[int], initial_status: str,
    session_id: Optional[str], board: Optional[str],
) -> dict[str, Any]:
    """Return the complete immutable governed-create replay identity."""
    return {
        "schema_version": "olympus-task-create-request/1",
        "task_id": str(task_id),
        "board_id": str(board_id),
        "board": board,
        "subject_revision": 0,
        "idempotency_key": str(idempotency_key),
        "title": title.strip(),
        "body": body,
        "assignee": assignee,
        "created_by": created_by,
        "workspace_kind": workspace_kind,
        "workspace_path": workspace_path,
        "branch_name": (
            str(branch_name).strip() or None if branch_name is not None else None
        ),
        "tenant": tenant,
        "priority": priority,
        "parents": list(parents),
        "triage": bool(triage),
        "max_runtime_seconds": (
            int(max_runtime_seconds) if max_runtime_seconds is not None else None
        ),
        "skills": skills,
        "max_retries": int(max_retries) if max_retries is not None else None,
        "goal_mode": bool(goal_mode),
        "goal_max_turns": (
            int(goal_max_turns) if goal_max_turns is not None else None
        ),
        "initial_status": initial_status,
        "session_id": session_id,
        "olympus_context": olympus_context,
    }


def _load_olympus_create_receipt(
    conn: sqlite3.Connection, idempotency_key: str,
) -> Optional[dict[str, Any]]:
    row = conn.execute(
        "SELECT * FROM kanban_olympus_create_receipts WHERE idempotency_key = ?",
        (idempotency_key,),
    ).fetchone()
    if row is None:
        return None
    payload = str(row["payload"])
    digest = hashlib.sha256(payload.encode("utf-8")).hexdigest()
    if digest != row["payload_sha256"]:
        raise OlympusContextError(
            "olympus_idempotency_receipt_invalid",
            "governed create receipt checksum does not match",
        )
    try:
        decoded = json.loads(payload)
    except (TypeError, ValueError, json.JSONDecodeError) as exc:
        raise OlympusContextError(
            "olympus_idempotency_receipt_invalid",
            "governed create receipt is not valid JSON",
        ) from exc
    encoded, _ = _canonical_json_record(decoded)
    if (
        encoded != payload
        or decoded.get("schema_version") != "olympus-task-create-request/1"
        or decoded.get("idempotency_key") != idempotency_key
        or decoded.get("task_id") != row["task_id"]
    ):
        raise OlympusContextError(
            "olympus_idempotency_receipt_invalid",
            "governed create receipt is not exact canonical evidence",
        )
    return decoded


def create_olympus_task(
    conn: sqlite3.Connection,
    *,
    olympus_context: dict[str, Any],
    olympus_auth: OlympusMutationAuth,
    subject_revision: int = 0,
    title: str,
    body: Optional[str] = None,
    assignee: Optional[str] = None,
    created_by: Optional[str] = None,
    workspace_kind: str = "scratch",
    workspace_path: Optional[str] = None,
    branch_name: Optional[str] = None,
    tenant: Optional[str] = None,
    priority: int = 0,
    parents: Iterable[str] = (),
    triage: bool = False,
    idempotency_key: Optional[str] = None,
    max_runtime_seconds: Optional[int] = None,
    skills: Optional[Iterable[str]] = None,
    max_retries: Optional[int] = None,
    goal_mode: bool = False,
    goal_max_turns: Optional[int] = None,
    initial_status: str = "running",
    session_id: Optional[str] = None,
    board: Optional[str] = None,
) -> str:
    """Persist a governed task only after exact canonical verification."""
    if olympus_auth.source_identity is not None or olympus_auth.target_identity is not None:
        raise OlympusContextError(
            "olympus_telegram_create_api_required",
            "Telegram creation requires the dedicated journaled intake API",
        )
    canonical_assignee = _canonical_assignee(assignee)
    if canonical_assignee is None:
        raise OlympusContextError(
            "olympus_agent_missing", "a governed task requires an assignee"
        )
    normalized = normalize_olympus_context(olympus_context)
    parent_ids = tuple(str(parent) for parent in parents if parent)
    skills_list = _normalize_task_skills(skills)
    if initial_status not in VALID_INITIAL_STATUSES:
        raise ValueError(
            f"initial_status must be one of {sorted(VALID_INITIAL_STATUSES)}"
        )
    if subject_revision != 0:
        raise OlympusContextError(
            "olympus_subject_revision_mismatch",
            "a new governed task must begin at subject revision zero",
        )
    with olympus_mutation_scope(olympus_auth), write_txn(conn):
        if idempotency_key:
            receipt = _load_olympus_create_receipt(conn, idempotency_key)
            existing = conn.execute(
                "SELECT id, record_revision, olympus_context FROM tasks "
                "WHERE idempotency_key = ? "
                "ORDER BY created_at DESC LIMIT 1",
                (idempotency_key,),
            ).fetchone()
            if existing is None and receipt is not None:
                raise OlympusContextError(
                    "olympus_idempotency_receipt_orphaned",
                    "idempotency key belongs to a deleted governed task",
                )
            if existing is not None:
                if receipt is None or receipt["task_id"] != existing["id"]:
                    raise OlympusContextError(
                        "olympus_idempotency_receipt_missing",
                        "idempotency key has no exact governed create receipt",
                    )
                desired = _olympus_create_request_payload(
                    task_id=str(existing["id"]),
                    board_id=_connection_board_identity(conn),
                    idempotency_key=idempotency_key,
                    olympus_context=normalized,
                    title=title,
                    body=body,
                    assignee=canonical_assignee,
                    created_by=created_by,
                    workspace_kind=workspace_kind,
                    workspace_path=workspace_path,
                    branch_name=branch_name,
                    tenant=tenant,
                    priority=priority,
                    parents=parent_ids,
                    triage=triage,
                    max_runtime_seconds=max_runtime_seconds,
                    skills=skills_list,
                    max_retries=max_retries,
                    goal_mode=goal_mode,
                    goal_max_turns=goal_max_turns,
                    initial_status=initial_status,
                    session_id=session_id,
                    board=board,
                )
                if receipt != desired:
                    raise OlympusContextError(
                        "olympus_idempotency_payload_conflict",
                        "idempotency key belongs to a different governed create payload",
                    )
                _, owns = _authorize_task_mutation(
                    conn,
                    existing["id"],
                    action="create_idempotent",
                    capability=OLYMPUS_CAPABILITY_CREATE,
                    auth=olympus_auth,
                )
                _release_task_mutation_permit(conn, existing["id"], owns)
                return str(existing["id"])
        task_id = _new_task_id()
        for parent_id in parent_ids:
            _authorize_task_mutation(
                conn,
                parent_id,
                action="link_governed_child",
                capability=OLYMPUS_CAPABILITY_LINK,
                auth=olympus_auth,
            )
        intended_status = _initial_task_status(
            conn,
            parents=parent_ids,
            triage=triage,
            initial_status=initial_status,
        )
        operation_prefix = str(olympus_auth.operation_id or "kanban")
        operation_id = f"{operation_prefix}:create:{task_id}:r0"
        authorization = require_olympus_authority_verification(
            normalized,
            subject_id=task_id,
            subject_revision=0,
            assignee=canonical_assignee,
            action="create",
            capability=OLYMPUS_CAPABILITY_CREATE,
            actor=str(olympus_auth.actor or canonical_assignee),
            operation_id=operation_id,
            principal=olympus_auth,
            expected_status=intended_status,
            board_id=_connection_board_identity(conn),
        )
        _insert_issued_permit(
            conn,
            task_id=task_id,
            subject_revision=0,
            operation_id=operation_id,
            action="create",
            capability=OLYMPUS_CAPABILITY_CREATE,
            auth_root_id=task_id,
            auth_root_revision=0,
            verification_id=str(
                authorization["verification"]["verification_id"]
            ),
        )
        try:
            created_task_id = _create_task_internal(
                conn,
                title=title,
                body=body,
                assignee=canonical_assignee,
                created_by=created_by,
                workspace_kind=workspace_kind,
                workspace_path=workspace_path,
                branch_name=branch_name,
                tenant=tenant,
                priority=priority,
                parents=parent_ids,
                triage=triage,
                idempotency_key=idempotency_key,
                max_runtime_seconds=max_runtime_seconds,
                skills=skills_list,
                max_retries=max_retries,
                goal_mode=goal_mode,
                goal_max_turns=goal_max_turns,
                initial_status=initial_status,
                session_id=session_id,
                board=board,
                olympus_context=normalized,
                _task_id=task_id,
            )
            if idempotency_key:
                payload = _olympus_create_request_payload(
                    task_id=created_task_id,
                    board_id=_connection_board_identity(conn),
                    idempotency_key=idempotency_key,
                    olympus_context=normalized,
                    title=title,
                    body=body,
                    assignee=canonical_assignee,
                    created_by=created_by,
                    workspace_kind=workspace_kind,
                    workspace_path=workspace_path,
                    branch_name=branch_name,
                    tenant=tenant,
                    priority=priority,
                    parents=parent_ids,
                    triage=triage,
                    max_runtime_seconds=max_runtime_seconds,
                    skills=skills_list,
                    max_retries=max_retries,
                    goal_mode=goal_mode,
                    goal_max_turns=goal_max_turns,
                    initial_status=initial_status,
                    session_id=session_id,
                    board=board,
                )
                encoded_payload, payload_sha256 = _canonical_json_record(payload)
                receipt_created_at = int(time.time())
                _bind_issued_permit_write(
                    conn,
                    task_id,
                    {
                        "schema_version": CREATE_RECEIPT_WRITE_SCHEMA,
                        "idempotency_key": idempotency_key,
                        "task_id": created_task_id,
                        "payload": encoded_payload,
                        "payload_sha256": payload_sha256,
                        "created_at": receipt_created_at,
                    },
                )
                conn.execute(
                    "INSERT INTO kanban_olympus_create_receipts "
                    "(idempotency_key,task_id,payload,payload_sha256,created_at) "
                    "VALUES (?,?,?,?,?)",
                    (
                        idempotency_key, created_task_id, encoded_payload,
                        payload_sha256, receipt_created_at,
                    ),
                )
            return created_task_id
        finally:
            _release_task_mutation_permit(conn, task_id, True)


def _canonical_olympus_telegram_delivery_identity(
    delivery_identity: Mapping[str, Any],
    *,
    source_identity: Mapping[str, Any],
) -> tuple[dict[str, Any], str, str]:
    """Bind one Telegram delivery key to the authenticated bot/source tuple."""
    try:
        raw = dict(delivery_identity)
        base_keys = {"platform", "bot_id", "profile"}
        if set(raw) == base_keys | {"update_id"}:
            normalized = {
                "platform": _strict_text(
                    raw["platform"], "delivery_identity.platform"
                ),
                "bot_id": _strict_text(
                    raw["bot_id"], "delivery_identity.bot_id"
                ),
                "profile": _strict_text(
                    raw["profile"], "delivery_identity.profile"
                ),
                "update_id": _strict_int(
                    raw["update_id"], "delivery_identity.update_id", minimum=0
                ),
            }
        elif set(raw) == base_keys | {"chat_id", "message_id"}:
            normalized = {
                "platform": _strict_text(
                    raw["platform"], "delivery_identity.platform"
                ),
                "bot_id": _strict_text(
                    raw["bot_id"], "delivery_identity.bot_id"
                ),
                "profile": _strict_text(
                    raw["profile"], "delivery_identity.profile"
                ),
                "chat_id": _strict_text(
                    raw["chat_id"], "delivery_identity.chat_id"
                ),
                "message_id": _strict_text(
                    raw["message_id"], "delivery_identity.message_id"
                ),
            }
        else:
            raise AuthorityContractError(
                "delivery_identity must contain exactly bot/profile/platform "
                "plus update_id or chat_id/message_id"
            )
    except (AuthorityContractError, TypeError, ValueError) as exc:
        raise OlympusContextError(
            "olympus_delivery_identity_invalid", str(exc)
        ) from exc
    expected = {
        "platform": source_identity["platform"],
        "bot_id": source_identity["bot_id"],
        "profile": source_identity["profile"],
    }
    if any(normalized[key] != value for key, value in expected.items()):
        raise OlympusContextError(
            "olympus_delivery_identity_conflict",
            "delivery bot, profile, and platform must match the authenticated source",
        )
    if "chat_id" in normalized \
            and normalized["chat_id"] != source_identity["chat_id"]:
        raise OlympusContextError(
            "olympus_delivery_identity_conflict",
            "fallback delivery chat must match the authenticated source",
        )
    encoded, digest = _canonical_json_record(normalized)
    return normalized, encoded, digest


def create_olympus_telegram_task(
    conn: sqlite3.Connection,
    *,
    telegram_auth: OlympusMutationAuth,
    service_auth: OlympusMutationAuth,
    delivery_key: str,
    delivery_identity: Mapping[str, Any],
    title: str,
    body: Optional[str],
    assignee: str,
    created_by: Optional[str],
    session_id: Optional[str],
    platform: str,
    chat_id: str,
    thread_id: Optional[str],
    user_id: Optional[str],
    notifier_profile: Optional[str],
    workspace_kind: str = "scratch",
    workspace_path: Optional[str] = None,
    branch_name: Optional[str] = None,
    tenant: Optional[str] = None,
    priority: int = 0,
    max_runtime_seconds: Optional[int] = None,
    skills: Optional[Iterable[str]] = None,
    max_retries: Optional[int] = None,
    goal_mode: bool = False,
    goal_max_turns: Optional[int] = None,
    board: Optional[str] = None,
) -> str:
    """Atomically verify, create, journal, and subscribe one Telegram task."""
    if telegram_auth.source_identity is None or telegram_auth.target_identity is None:
        raise OlympusContextError(
            "olympus_telegram_principal_invalid",
            "Telegram intake requires an authenticated source and exact target",
        )
    target_identity = telegram_auth.target_identity
    if target_identity.get("control_action") != "telegram-intake":
        raise OlympusContextError(
            "olympus_telegram_action_invalid",
            "Telegram intake authorization is not bound to intake",
        )
    authorization_task_id = str(
        target_identity.get("authorization_subject_id", "")
    )
    if target_identity.get("task_id") != authorization_task_id:
        raise OlympusContextError(
            "olympus_target_identity_conflict",
            "Telegram intake must target the selected authorization root",
        )
    if (
        service_auth.source_identity is not None
        or service_auth.target_identity is not None
        or service_auth.runtime_identity is not None
        or service_auth.notifier_identity is not None
    ):
        raise OlympusContextError(
            "olympus_service_principal_invalid",
            "Telegram persistence requires the trusted service dispatcher",
        )
    canonical_assignee = _canonical_assignee(assignee)
    if canonical_assignee is None:
        raise OlympusContextError(
            "olympus_agent_missing", "Telegram intake requires a delegated agent"
        )
    source = telegram_auth.source_identity
    source_json, _ = _canonical_json_record(source)
    normalized_delivery, delivery_identity_json, delivery_digest = (
        _canonical_olympus_telegram_delivery_identity(
            delivery_identity, source_identity=source
        )
    )
    expected_delivery_key = f"olympus-telegram:v3:{delivery_digest}"
    if delivery_key != expected_delivery_key:
        raise OlympusContextError(
            "olympus_delivery_identity_conflict",
            "delivery_key must be the SHA-256 of canonical delivery_identity",
        )
    notification_identity = {
        "platform": platform,
        "chat_id": chat_id,
        "thread_id": thread_id or "",
        "user_id": user_id,
        "notifier_profile": notifier_profile,
    }
    expected_notification = {
        "platform": source["platform"],
        "chat_id": source["chat_id"],
        "thread_id": source["thread_id"],
        "user_id": source["user_id"],
        "notifier_profile": source["profile"],
    }
    if notification_identity != expected_notification:
        raise OlympusContextError(
            "olympus_notification_destination_conflict",
            "notification destination must exactly match the authenticated "
            "Telegram chat, thread, user, and profile",
        )
    with write_txn(conn):
        # A read-only preflight is deliberately a separate action. The intake
        # permit below is exact-write-bound and cannot be issued until the
        # generated task id and complete immutable payload are known.
        preflight = olympus_telegram_auth(
            conn,
            verifier=telegram_auth.verifier,
            source_identity=telegram_auth.source_identity,
            authorization_task_id=authorization_task_id,
            target_task_id=authorization_task_id,
            action="telegram-status",
            operation_id=f"{telegram_auth.operation_id}:preflight",
        )
        with olympus_mutation_scope(preflight):
            _, preflight_owns = _authorize_task_mutation(
                conn,
                authorization_task_id,
                action="telegram-status",
                capability=TELEGRAM_ACTION_CAPABILITIES["telegram-status"],
                auth=preflight,
            )
            _release_task_mutation_permit(
                conn, authorization_task_id, preflight_owns
            )
        root = conn.execute(
            "SELECT assignee, record_revision, olympus_context FROM tasks WHERE id = ?",
            (authorization_task_id,),
        ).fetchone()
        if root is None or root["olympus_context"] is None:
            raise OlympusContextError(
                "olympus_authorization_root_missing",
                "Telegram authorization root disappeared before intake",
            )
        root_context = _require_current_olympus_context(
            root["olympus_context"], assignee=root["assignee"],
        )
        assert root_context is not None
        child_context = derive_olympus_child_context(
            root_context, agent_id=canonical_assignee,
        )
        if canonical_assignee != str(service_auth.actor or ""):
            raise OlympusContextError(
                "olympus_actor_mismatch",
                "service dispatcher actor must match the delegated agent",
            )
        existing = conn.execute(
            "SELECT * FROM olympus_telegram_deliveries WHERE delivery_key = ?",
            (delivery_key,),
        ).fetchone()
        if existing is not None:
            task_id = str(existing["task_id"])
        else:
            task_id = create_olympus_task(
                conn,
                olympus_context=child_context,
                olympus_auth=service_auth,
                title=title,
                body=body,
                assignee=canonical_assignee,
                created_by=created_by,
                workspace_kind=workspace_kind,
                workspace_path=workspace_path,
                branch_name=branch_name,
                tenant=tenant,
                priority=priority,
                parents=(),
                idempotency_key=delivery_key,
                max_runtime_seconds=max_runtime_seconds,
                skills=skills,
                max_retries=max_retries,
                goal_mode=goal_mode,
                goal_max_turns=goal_max_turns,
                initial_status="running",
                session_id=session_id,
                board=board,
            )
        payload = {
            "schema_version": "olympus-telegram-delivery/3",
            "delivery_key": delivery_key,
            "delivery_identity": normalized_delivery,
            "source_identity": json.loads(source_json),
            "authorization_task_id": authorization_task_id,
            "authorization_task_revision": int(root["record_revision"]),
            "mission_id": root_context["mission_id"],
            "delegated_agent": canonical_assignee,
            "task_id": task_id,
            "title": title.strip(),
            "body": body,
            "created_by": created_by,
            "session_id": session_id,
            "workspace_kind": workspace_kind,
            "workspace_path": workspace_path,
            "branch_name": branch_name,
            "tenant": tenant,
            "priority": priority,
            "max_runtime_seconds": max_runtime_seconds,
            "skills": _normalize_task_skills(skills),
            "max_retries": max_retries,
            "goal_mode": bool(goal_mode),
            "goal_max_turns": goal_max_turns,
            "notification": notification_identity,
        }
        payload_json, payload_sha256 = _canonical_json_record(payload)
        if existing is not None:
            if (
                str(existing["payload"]) != payload_json
                or str(existing["payload_sha256"]) != payload_sha256
                or str(existing["authorization_task_id"])
                    != authorization_task_id
                or int(existing["authorization_task_revision"])
                    != int(root["record_revision"])
            ):
                raise OlympusContextError(
                    "olympus_delivery_identity_conflict",
                    "Telegram delivery identity belongs to another immutable submission",
                )
        else:
            created_at = int(time.time())
            binding = {
                "schema_version": TELEGRAM_DELIVERY_WRITE_SCHEMA,
                "action": "telegram-intake",
                "task_id": authorization_task_id,
                "task_record_revision": int(root["record_revision"]),
                "delivery_key": delivery_key,
                "authorization_task_id": authorization_task_id,
                "authorization_task_revision": int(root["record_revision"]),
                "created_task_id": task_id,
                "payload": payload_json,
                "payload_sha256": payload_sha256,
                "created_at": created_at,
            }
            with olympus_mutation_scope(telegram_auth):
                authorization, owns = _authorize_task_mutation(
                    conn,
                    authorization_task_id,
                    action="telegram-intake",
                    capability=TELEGRAM_ACTION_CAPABILITIES["telegram-intake"],
                    auth=telegram_auth,
                    mutation_binding=binding,
                )
                try:
                    conn.execute(
                        "INSERT INTO olympus_telegram_deliveries "
                        "(delivery_key,authorization_task_id,"
                        "authorization_task_revision,task_id,payload,"
                        "payload_sha256,created_at) VALUES (?,?,?,?,?,?,?)",
                        (
                            delivery_key, authorization_task_id,
                            int(root["record_revision"]), task_id, payload_json,
                            payload_sha256, created_at,
                        ),
                    )
                    _append_event(
                        conn,
                        authorization_task_id,
                        "olympus_telegram_intake",
                        {
                            "task_id": task_id,
                            "delivery_key": delivery_key,
                            "verification_id": authorization["verification"][
                                "verification_id"
                            ],
                        },
                    )
                finally:
                    _release_task_mutation_permit(
                        conn, authorization_task_id, owns
                    )
        # The same outer transaction contains delivery, task, create receipt,
        # and destination subscription. A crash exposes all four or none.
        add_notify_sub(
            conn,
            task_id=task_id,
            platform=platform,
            chat_id=chat_id,
            thread_id=thread_id,
            user_id=user_id,
            notifier_profile=notifier_profile,
            olympus_auth=service_auth,
        )
        return task_id


def apply_olympus_telegram_control(
    conn: sqlite3.Connection,
    *,
    telegram_auth: OlympusMutationAuth,
    service_auth: OlympusMutationAuth,
    target_task_id: str,
    action: str,
    operator_tag: str,
) -> dict[str, Any]:
    """Authorize and apply one exact Telegram control without PID ownership."""
    wire_action = f"telegram-control:{action}"
    if wire_action not in TELEGRAM_ACTION_CAPABILITIES:
        raise OlympusContextError(
            "olympus_control_invalid", "Telegram control action is invalid"
        )
    operation_id = str(telegram_auth.operation_id or "")
    if not operation_id.startswith("olympus-telegram-control:v3:"):
        raise OlympusContextError(
            "olympus_control_identity_invalid",
            "Telegram control operation identity is not canonical v3",
        )
    if (
        telegram_auth.source_identity is None
        or telegram_auth.target_identity is None
        or telegram_auth.target_identity.get("control_action") != wire_action
        or telegram_auth.target_identity.get("task_id") != target_task_id
    ):
        raise OlympusContextError(
            "olympus_target_identity_conflict",
            "Telegram control is not bound to the exact requested target",
        )
    authorization_task_id = str(
        telegram_auth.target_identity["authorization_subject_id"]
    )
    source_json, _ = _canonical_json_record(telegram_auth.source_identity)
    operator_identity = _strict_text(operator_tag, "operator_tag")

    def _replay(existing: sqlite3.Row) -> dict[str, Any]:
        """Validate and replay one immutable control receipt."""
        try:
            prior = json.loads(str(existing["request_payload"]))
        except (TypeError, ValueError, json.JSONDecodeError) as exc:
            raise OlympusContextError(
                "olympus_control_receipt_invalid",
                "Telegram control receipt is not valid JSON",
            ) from exc
        prior_target = prior.get("target_identity")
        current_target = telegram_auth.target_identity
        stable_target_keys = frozenset(OLYMPUS_TARGET_IDENTITY_KEYS) - {
            "task_record_revision", "status",
        }
        stable_target_exact = (
            isinstance(prior_target, dict)
            and isinstance(current_target, dict)
            and all(
                prior_target.get(key) == current_target.get(key)
                for key in stable_target_keys
            )
        )
        exact = (
            existing["action"] == wire_action
            and existing["authorization_task_id"] == authorization_task_id
            and existing["target_task_id"] == target_task_id
            and existing["source_identity"] == source_json
            and prior.get("schema_version") == "olympus-telegram-control/3"
            and prior.get("operation_id") == operation_id
            and prior.get("action") == wire_action
            and prior.get("authorization_task_id") == authorization_task_id
            and prior.get("authorization_task_revision")
                == int(existing["authorization_task_revision"])
            and prior.get("target_task_id") == target_task_id
            and prior.get("target_task_revision")
                == int(existing["target_task_revision"])
            and prior.get("source_identity") == telegram_auth.source_identity
            and stable_target_exact
            and prior.get("operator_tag") == operator_identity
            and prior.get("planned_status") == existing["result_status"]
            and prior.get("effect_operation_id")
                == existing["effect_operation_id"]
            and hashlib.sha256(
                str(existing["request_payload"]).encode("utf-8")
            ).hexdigest() == existing["payload_sha256"]
        )
        if not exact:
            raise OlympusContextError(
                "olympus_control_identity_conflict",
                "control operation identity belongs to another immutable request",
            )
        verified = verify_olympus_telegram_task(
            conn,
            authorization_task_id=authorization_task_id,
            target_task_id=target_task_id,
            action="telegram-status",
            verifier=telegram_auth.verifier,
            source_identity=telegram_auth.source_identity,
            operation_id=f"{operation_id}:replay-status",
        )
        return {
            "operation_id": operation_id,
            "status": verified["status"],
            "replayed": True,
            "effect_operation_id": existing["effect_operation_id"],
        }

    existing = conn.execute(
        "SELECT * FROM olympus_telegram_controls WHERE operation_id = ?",
        (operation_id,),
    ).fetchone()
    if existing is not None:
        return _replay(existing)
    row = conn.execute(
        "SELECT t.*, r.id AS run_id, r.launch_token, r.process_state, "
        "r.worker_host_id, r.worker_boot_id, r.worker_pid AS run_worker_pid, "
        "r.worker_start_token FROM tasks t LEFT JOIN task_runs r "
        "ON r.id = t.current_run_id WHERE t.id = ?",
        (target_task_id,),
    ).fetchone()
    if row is None or row["olympus_context"] is None:
        raise OlympusContextError(
            "olympus_control_target_missing",
            "Telegram control target is missing or ungoverned",
        )
    current_status = str(row["status"])
    valid_states = {
        "pause": {"ready", "running"},
        "resume": {"blocked"},
        "interrupt": {"running"},
        "cancel": {"triage", "todo", "ready", "scheduled", "running", "blocked"},
    }
    if current_status not in valid_states[action]:
        raise OlympusContextError(
            "olympus_control_state_invalid",
            f"Telegram {action} is invalid from {current_status}",
        )
    # Even emergency authority cannot invent a process effect from stale or
    # revoked task state. The frozen v3 issuer may authorize containment, but
    # Hermes still requires a current exact target before service execution.
    _require_current_olympus_context(
        row["olympus_context"], assignee=row["assignee"],
    )
    effect_operation_id = None
    if current_status == "running":
        if (
            row["run_id"] is None
            or row["process_state"] != "registered"
            or not row["launch_token"]
            or not row["worker_host_id"]
            or not row["worker_boot_id"]
            or not row["worker_start_token"]
            or int(row["run_worker_pid"] or 0) <= 0
        ):
            raise OlympusContextError(
                "olympus_runtime_identity_stale",
                "running control target lacks an exact registered process",
            )
        result_status = "blocked"
        effect_operation_id = f"{operation_id}:terminate-worker"
    elif action == "resume":
        undone = conn.execute(
            "SELECT 1 FROM task_links l JOIN tasks p ON p.id = l.parent_id "
            "WHERE l.child_id = ? AND p.status != 'done' LIMIT 1",
            (target_task_id,),
        ).fetchone()
        result_status = "todo" if undone else "ready"
    elif action == "cancel":
        result_status = "archived"
    else:
        result_status = "blocked"
    request_payload = {
        "schema_version": "olympus-telegram-control/3",
        "operation_id": operation_id,
        "action": wire_action,
        "authorization_task_id": authorization_task_id,
        "authorization_task_revision": int(
            telegram_auth.target_identity["authorization_subject_revision"]
        ),
        "target_task_id": target_task_id,
        "target_task_revision": int(row["record_revision"]),
        "source_identity": telegram_auth.source_identity,
        "target_identity": telegram_auth.target_identity,
        "operator_tag": operator_identity,
        "planned_status": result_status,
        "effect_operation_id": effect_operation_id,
    }
    request_json, request_sha256 = _canonical_json_record(request_payload)
    created_at = int(time.time())
    binding = {
        "schema_version": TELEGRAM_CONTROL_WRITE_SCHEMA,
        "action": wire_action,
        "task_id": target_task_id,
        "task_record_revision": int(row["record_revision"]),
        "operation_id": operation_id,
        "authorization_task_id": authorization_task_id,
        "authorization_task_revision": int(
            telegram_auth.target_identity["authorization_subject_revision"]
        ),
        "source_identity": source_json,
        "request_payload": request_json,
        "payload_sha256": request_sha256,
        "result_status": result_status,
        "effect_operation_id": effect_operation_id,
        "created_at": created_at,
    }
    with write_txn(conn), olympus_mutation_scope(telegram_auth):
        # The optimistic read above avoids taking a write lock for ordinary
        # replays.  Recheck after BEGIN IMMEDIATE so simultaneous first
        # deliveries serialize to one receipt and every loser replays it.
        concurrent = conn.execute(
            "SELECT * FROM olympus_telegram_controls WHERE operation_id = ?",
            (operation_id,),
        ).fetchone()
        if concurrent is not None:
            return _replay(concurrent)
        if action in {"resume", "cancel"} and current_status != "running":
            nonterminal_effect = conn.execute(
                "SELECT 1 FROM kanban_effect_journal "
                "WHERE effect_kind='terminate_worker' AND task_id=? "
                "AND state NOT IN "
                "('gone','failed','identity_mismatch','identity_unverified') "
                "LIMIT 1",
                (target_task_id,),
            ).fetchone()
            if nonterminal_effect is not None:
                raise OlympusContextError(
                    "olympus_control_termination_in_progress",
                    "resume or non-running cancel cannot cross an active "
                    "worker-termination generation",
                )
        authorization, owns = _authorize_task_mutation(
            conn,
            target_task_id,
            action=wire_action,
            capability=TELEGRAM_ACTION_CAPABILITIES[wire_action],
            auth=telegram_auth,
            mutation_binding=binding,
            allow_inactive_target=wire_action in TELEGRAM_EMERGENCY_ACTIONS,
        )
        try:
            conn.execute(
                "INSERT INTO olympus_telegram_controls "
                "(operation_id,action,authorization_task_id,"
                "authorization_task_revision,target_task_id,target_task_revision,"
                "source_identity,request_payload,payload_sha256,verification_id,"
                "result_status,effect_operation_id,created_at) "
                "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)",
                (
                    operation_id, wire_action, authorization_task_id,
                    int(telegram_auth.target_identity[
                        "authorization_subject_revision"
                    ]),
                    target_task_id, int(row["record_revision"]), source_json,
                    request_json, request_sha256,
                    authorization["verification"]["verification_id"],
                    result_status, effect_operation_id, created_at,
                ),
            )
            _append_event(
                conn,
                target_task_id,
                "olympus_telegram_control",
                {
                    "action": action,
                    "operation_id": operation_id,
                    "planned_status": result_status,
                    "effect_operation_id": effect_operation_id,
                    "operator": operator_tag,
                },
            )
        finally:
            _release_task_mutation_permit(conn, target_task_id, owns)
        service_operation = replace(
            service_auth,
            actor=str(row["assignee"] or ""),
            operation_id=f"{operation_id}:service",
        )
        if current_status == "running":
            stage_worker_termination(
                conn,
                task_id=target_task_id,
                run_id=int(row["run_id"]),
                launch_token=str(row["launch_token"]),
                process_identity=ProcessIdentity(
                    host_id=str(row["worker_host_id"]),
                    boot_id=str(row["worker_boot_id"]),
                    pid=int(row["run_worker_pid"]),
                    start_token=str(row["worker_start_token"]),
                ),
                operation_id=str(effect_operation_id),
                reason=f"governed Telegram {action} by {operator_tag}",
                source_identity={
                    "schema_version": "olympus-telegram-control-source/3",
                    "operation_id": operation_id,
                    "verification_id": authorization["verification"][
                        "verification_id"
                    ],
                },
                outcome="reclaimed",
                event_kind="termination_staged",
                olympus_auth=service_operation,
            )
        elif action == "pause":
            # ``block`` is a worker-only action in the certified #16
            # principal contract.  Telegram never impersonates that worker;
            # the trusted service dispatcher performs the explicit direct
            # status transition under its own separately verified permit.
            if not set_task_status(
                conn, target_task_id, "blocked", olympus_auth=service_operation
            ):
                raise OlympusContextError(
                    "olympus_control_cas_failed", "pause lost its exact state CAS"
                )
        elif action == "resume":
            if not unblock_task(
                conn, target_task_id, olympus_auth=service_operation
            ):
                raise OlympusContextError(
                    "olympus_control_cas_failed", "resume lost its exact state CAS"
                )
        elif action == "cancel":
            if not archive_task(
                conn, target_task_id, olympus_auth=service_operation
            ):
                raise OlympusContextError(
                    "olympus_control_cas_failed", "cancel lost its exact state CAS"
                )
        observed = conn.execute(
            "SELECT status FROM tasks WHERE id = ?", (target_task_id,)
        ).fetchone()
        if observed is None or observed["status"] != result_status:
            raise OlympusContextError(
                "olympus_control_result_conflict",
                "control result does not match its immutable receipt",
            )
    return {
        "operation_id": operation_id,
        "status": result_status,
        "replayed": False,
        "effect_operation_id": effect_operation_id,
    }


def reconcile_olympus_telegram_controls(
    conn: sqlite3.Connection,
    *,
    service_auth: OlympusMutationAuth,
) -> int:
    """Finalize staged cancel only after #16's effect journal is terminal."""
    rows = conn.execute(
        "SELECT c.operation_id,c.target_task_id,c.effect_operation_id,"
        "e.state,e.target_post_revision,t.status,t.record_revision,t.assignee "
        "FROM olympus_telegram_controls c "
        "JOIN tasks t ON t.id=c.target_task_id "
        "JOIN kanban_effect_journal e ON e.effect_kind='terminate_worker' "
        "AND e.operation_id=c.effect_operation_id "
        "WHERE c.action='telegram-control:cancel' "
        "AND c.effect_operation_id IS NOT NULL",
    ).fetchall()
    changed = 0
    for row in rows:
        if row["status"] == "archived":
            continue
        # A successful SIGTERM call (``applied``) is not proof that the exact
        # process exited.  Only the dispatcher-owned birth-identity check may
        # advance the effect to ``gone`` and permit a running cancel to archive.
        if row["state"] != "gone" or row["status"] != "blocked":
            continue
        containment_revision = int(row["target_post_revision"] or 0)
        if containment_revision < 1 \
                or int(row["record_revision"]) != containment_revision:
            continue
        auth = replace(
            service_auth,
            actor=str(row["assignee"] or ""),
            operation_id=f"{row['operation_id']}:finalize-cancel",
        )
        if archive_task(
            conn,
            str(row["target_task_id"]),
            expected_record_revision=containment_revision,
            olympus_auth=auth,
        ):
            changed += 1
    return changed


def _find_missing_parents(conn: sqlite3.Connection, parents: Iterable[str]) -> list[str]:
    parents = list(parents)
    if not parents:
        return []
    placeholders = ",".join("?" * len(parents))
    rows = conn.execute(
        f"SELECT id FROM tasks WHERE id IN ({placeholders})",
        parents,
    ).fetchall()
    present = {r["id"] for r in rows}
    return [p for p in parents if p not in present]


def get_task(conn: sqlite3.Connection, task_id: str) -> Optional[Task]:
    row = conn.execute("SELECT * FROM tasks WHERE id = ?", (task_id,)).fetchone()
    return Task.from_row(row) if row else None


def update_task_olympus_context(
    conn: sqlite3.Connection,
    task_id: str,
    context: dict[str, Any],
    *,
    olympus_auth: OlympusMutationAuth,
    subject_revision: int,
) -> bool:
    """Renew or revoke a governed task through canonical verification.

    Legacy tasks cannot be opted in here.  Updating never rewrites an active or
    historical run: each attempt keeps the immutable snapshot captured at
    claim/start.
    """
    normalized = normalize_olympus_context(context)
    encoded = _serialize_olympus_context(normalized)
    with olympus_mutation_scope(olympus_auth), write_txn(conn):
        row = conn.execute(
            "SELECT status, assignee, claim_lock, claim_expires, current_run_id, "
            "record_revision, olympus_context FROM tasks WHERE id = ?",
            (task_id,),
        ).fetchone()
        if row is None:
            return False
        if row["olympus_context"] is None:
            raise OlympusContextError(
                "olympus_legacy_opt_in_forbidden",
                "legacy tasks cannot be opted into Olympus through an update",
            )
        if subject_revision != int(row["record_revision"]):
            raise OlympusContextError(
                "olympus_subject_revision_mismatch",
                "exact governed task revision is required",
            )
        if row["status"] in {"done", "archived"}:
            raise OlympusContextError(
                "olympus_context_update_forbidden",
                "Olympus context cannot change after terminal state",
            )
        stored = normalize_olympus_context(json.loads(row["olympus_context"]))
        hierarchy = ("goal_id", "program_id", "milestone_id", "mission_id", "workstream_id")
        if any(stored[key] != normalized[key] for key in hierarchy):
            raise OlympusContextError(
                "olympus_context_scope_change_forbidden",
                "authority updates cannot move a task to another mission hierarchy",
            )
        _, owns_permit = _authorize_task_mutation(
            conn,
            task_id,
            action="update_authority_context",
            capability=OLYMPUS_CAPABILITY_UPDATE,
            auth=olympus_auth,
            context_override=normalized,
            allow_inactive=True,
        )
        try:
            if not (
                normalized["agent_id"]
                == normalized["lease"]["agent_id"]
                == normalized["lease"]["holder"]
                == row["assignee"]
            ):
                raise OlympusContextError(
                    "olympus_agent_mismatch",
                    "updated lease holder, lease agent, context agent, and assignee must match",
                )
            if row["olympus_context"] == encoded:
                return True
            if row["status"] == "running":
                now = int(time.time())
                authority = normalized["authority"]
                lease = normalized["lease"]
                current_limit = min(
                    int(authority["expires_at"]), int(lease["expires_at"])
                )
                if authority["status"] != "ACTIVE" or lease["status"] != "ACTIVE":
                    current_limit = now - 1
                prior_expires = row["claim_expires"]
                bounded_expires = (
                    min(int(prior_expires), current_limit)
                    if prior_expires is not None else current_limit
                )
                conn.execute(
                    "UPDATE tasks SET olympus_context = ?, claim_expires = ? "
                    "WHERE id = ? AND record_revision = ?",
                    (encoded, bounded_expires, task_id, subject_revision),
                )
                if row["current_run_id"] is not None:
                    conn.execute(
                        "UPDATE task_runs SET claim_expires = ? WHERE id = ?",
                        (bounded_expires, int(row["current_run_id"])),
                    )
            else:
                conn.execute(
                    "UPDATE tasks SET olympus_context = ? "
                    "WHERE id = ? AND record_revision = ?",
                    (encoded, task_id, subject_revision),
                )
            _append_event(
                conn,
                task_id,
                "olympus_context_updated",
                {"olympus": _olympus_trace(normalized)},
                run_id=_current_run_id(conn, task_id),
            )
        finally:
            _release_task_mutation_permit(conn, task_id, owns_permit)
    return True


def verified_olympus_task_status(
    conn: sqlite3.Connection,
    task_id: str,
    *,
    subject_revision: int,
    olympus_auth: OlympusMutationAuth,
) -> dict[str, Any]:
    """Return one exact governed task status after canonical verification."""
    if isinstance(subject_revision, bool) or not isinstance(subject_revision, int):
        raise OlympusContextError(
            "olympus_subject_revision_mismatch",
            "verified status requires an exact integer task revision",
        )
    with olympus_mutation_scope(olympus_auth), write_txn(conn):
        row = conn.execute(
            "SELECT id, assignee, status, record_revision, olympus_context "
            "FROM tasks WHERE id = ?",
            (task_id,),
        ).fetchone()
        if row is None or row["olympus_context"] is None:
            raise OlympusContextError(
                "olympus_task_missing",
                "verified Olympus status requires a governed task",
            )
        if int(row["record_revision"]) != subject_revision:
            raise OlympusContextError(
                "olympus_subject_revision_mismatch",
                "task revision changed before verified status inspection",
            )
        if olympus_auth.source_identity is not None or olympus_auth.target_identity is not None:
            raise OlympusContextError(
                "olympus_review_principal_invalid",
                "review status inspection requires a direct canonical principal",
            )
        context = _require_current_olympus_context(
            row["olympus_context"],
            assignee=row["assignee"],
        )
        assert context is not None
        actor = str(olympus_auth.actor or context["agent_id"])
        operation_id = (
            f"{olympus_auth.operation_id or 'kanban'}:inspect_governed_status:"
            f"{task_id}:r{subject_revision}"
        )
        authorization = require_olympus_authority_verification(
            context,
            subject_id=task_id,
            subject_revision=subject_revision,
            assignee=str(row["assignee"] or ""),
            action="inspect_governed_status",
            capability=OLYMPUS_CAPABILITY_INSPECT,
            actor=actor,
            operation_id=operation_id,
            principal=olympus_auth,
            expected_status=str(row["status"]),
            board_id=_connection_board_identity(conn),
        )
        return {
            "task_id": str(row["id"]),
            "record_revision": int(row["record_revision"]),
            "status": str(row["status"]),
            "mission_id": context["mission_id"],
            "verification_id": authorization["verification"]["verification_id"],
        }


def olympus_release_operation_id(
    task_id: str, subject_revision: int, operation_prefix: str,
) -> str:
    """Return the stable canonical mutation identity for one blocked release."""
    if (
        not isinstance(task_id, str)
        or not task_id.strip()
        or isinstance(subject_revision, bool)
        or not isinstance(subject_revision, int)
        or subject_revision < 1
        or not isinstance(operation_prefix, str)
        or not operation_prefix.strip()
    ):
        raise OlympusContextError(
            "olympus_release_identity_invalid",
            "release identity requires task, revision, and operation prefix",
        )
    task_id = task_id.strip()
    operation_prefix = operation_prefix.strip()
    return (
        f"{operation_prefix}:release_blocked_task:{task_id}:"
        f"r{subject_revision}:target:{task_id}:r{subject_revision}"
    )


def _decode_olympus_release_receipt(row: sqlite3.Row) -> dict[str, Any]:
    encoded = str(row["receipt"])
    digest = hashlib.sha256(encoded.encode("utf-8")).hexdigest()
    if digest != row["receipt_sha256"]:
        raise OlympusContextError(
            "olympus_release_receipt_invalid",
            "release receipt checksum does not match",
        )
    try:
        receipt = json.loads(encoded)
    except (TypeError, ValueError, json.JSONDecodeError) as exc:
        raise OlympusContextError(
            "olympus_release_receipt_invalid",
            "release receipt is not valid JSON",
        ) from exc
    canonical, _ = _canonical_json_record(receipt)
    if (
        canonical != encoded
        or set(receipt) != _OLYMPUS_RELEASE_RECEIPT_KEYS
        or receipt.get("schema_version") != "olympus-task-release-receipt/1"
        or receipt.get("operation_id") != row["operation_id"]
        or receipt.get("task_id") != row["task_id"]
        or receipt.get("previous_revision") != int(row["subject_revision"])
        or receipt.get("record_revision") != int(row["record_revision"])
        or receipt.get("verification_id") != row["verification_id"]
        or receipt.get("request_id") != row["request_id"]
        or receipt.get("created_at") != int(row["created_at"])
    ):
        raise OlympusContextError(
            "olympus_release_receipt_invalid",
            "release receipt is not exact canonical evidence",
        )
    return receipt


def get_olympus_release_receipt(
    conn: sqlite3.Connection,
    *,
    task_id: str,
    subject_revision: int,
    operation_id: str,
) -> Optional[dict[str, Any]]:
    """Look up and checksum-verify one exact immutable release receipt."""
    row = conn.execute(
        "SELECT * FROM kanban_olympus_release_receipts "
        "WHERE operation_id = ? OR (task_id = ? AND subject_revision = ?)",
        (operation_id, task_id, subject_revision),
    ).fetchone()
    if row is None:
        return None
    if (
        row["operation_id"] != operation_id
        or row["task_id"] != task_id
        or int(row["subject_revision"]) != subject_revision
    ):
        raise OlympusContextError(
            "olympus_release_receipt_conflict",
            "release operation identity was reused for another task or revision",
        )
    return _decode_olympus_release_receipt(row)


def _verify_olympus_release_replay(
    conn: sqlite3.Connection,
    *,
    task_id: str,
    receipt: dict[str, Any],
    olympus_auth: OlympusMutationAuth,
) -> None:
    """Freshly verify the exact live post-release state before API replay."""
    row = conn.execute(
        "SELECT status, record_revision, assignee, olympus_context "
        "FROM tasks WHERE id = ?",
        (task_id,),
    ).fetchone()
    if row is None or row["olympus_context"] is None:
        raise OlympusContextError(
            "olympus_release_replay_orphaned",
            "release receipt no longer has a live governed task",
        )
    if (
        int(row["record_revision"]) != int(receipt["record_revision"])
        or row["status"] != receipt["status"]
        or receipt["status"] != "ready"
    ):
        raise OlympusContextError(
            "olympus_release_replay_state_changed",
            "live task no longer matches the exact release receipt state",
        )
    raw_context: Any = row["olympus_context"]
    if isinstance(raw_context, str):
        try:
            raw_context = json.loads(raw_context)
        except (TypeError, ValueError, json.JSONDecodeError) as exc:
            raise OlympusContextError(
                "olympus_context_invalid",
                "stored Olympus context is not valid JSON",
            ) from exc
    actor = str(olympus_auth.actor or row["assignee"] or "")
    authorization = require_olympus_authority_verification(
        raw_context,
        subject_id=task_id,
        subject_revision=int(row["record_revision"]),
        assignee=str(row["assignee"] or ""),
        action="inspect_governed_status",
        capability=OLYMPUS_CAPABILITY_INSPECT,
        actor=actor,
        operation_id=(
            f"{receipt['operation_id']}:verify_receipt_replay:"
            f"r{int(row['record_revision'])}"
        ),
        principal=olympus_auth,
        expected_status=str(row["status"]),
        board_id=_connection_board_identity(conn),
    )
    context = authorization["context"]
    exact_identity = (
        authorization["request"]["principal"] == receipt["principal"]
        and authorization["request"]["actor"] == receipt["actor"]
        and context["authority"]["authority_id"] == receipt["authority_id"]
        and context["authority"]["revision"] == receipt["authority_revision"]
        and context["authority"]["source"] == receipt["authority_source"]
        and context["lease"]["lease_id"] == receipt["lease_id"]
        and context["lease"]["revision"] == receipt["lease_revision"]
        and context["lease"]["source"] == receipt["lease_source"]
    )
    if not exact_identity:
        raise OlympusContextError(
            "olympus_release_replay_principal_conflict",
            "fresh replay verification does not match the durable release identity",
        )


def release_olympus_task(
    conn: sqlite3.Connection,
    task_id: str,
    *,
    subject_revision: int,
    olympus_auth: OlympusMutationAuth,
) -> dict[str, Any]:
    """Release once, or replay the exact durable receipt after a crash."""
    if isinstance(subject_revision, bool) or not isinstance(subject_revision, int):
        raise OlympusContextError(
            "olympus_subject_revision_mismatch",
            "governed release requires an exact integer task revision",
        )
    operation_id = olympus_release_operation_id(
        task_id,
        subject_revision,
        str(olympus_auth.operation_id or "kanban"),
    )
    with olympus_mutation_scope(olympus_auth), write_txn(conn):
        replay = get_olympus_release_receipt(
            conn,
            task_id=task_id,
            subject_revision=subject_revision,
            operation_id=operation_id,
        )
        if replay is not None:
            _verify_olympus_release_replay(
                conn,
                task_id=task_id,
                receipt=replay,
                olympus_auth=olympus_auth,
            )
            return replay
        row = conn.execute(
            "SELECT status, record_revision, olympus_context FROM tasks WHERE id = ?",
            (task_id,),
        ).fetchone()
        if row is None or row["olympus_context"] is None:
            raise OlympusContextError(
                "olympus_task_missing",
                "governed release requires an existing governed task",
            )
        if int(row["record_revision"]) != subject_revision:
            raise OlympusContextError(
                "olympus_subject_revision_mismatch",
                "task revision changed before governed release",
            )
        if row["status"] != "blocked":
            raise OlympusContextError(
                "olympus_release_status_invalid",
                "governed release requires exact blocked status",
            )
        if conn.execute(
            "SELECT 1 FROM task_links l JOIN tasks p ON p.id = l.parent_id "
            "WHERE l.child_id = ? AND p.status NOT IN ('done', 'archived') LIMIT 1",
            (task_id,),
        ).fetchone() is not None:
            raise OlympusContextError(
                "olympus_release_dependencies_incomplete",
                "governed task cannot release before all dependencies complete",
            )
        authorization, owns = _authorize_task_mutation(
            conn,
            task_id,
            action="release_blocked_task",
            capability=OLYMPUS_CAPABILITY_RELEASE,
            auth=olympus_auth,
        )
        try:
            if authorization["request"]["operation_id"] != operation_id:
                raise OlympusContextError(
                    "olympus_release_identity_conflict",
                    "release request operation identity is not stable",
                )
            cur = conn.execute(
                "UPDATE tasks SET status = 'ready', claim_lock = NULL, "
                "claim_expires = NULL, worker_pid = NULL "
                "WHERE id = ? AND status = 'blocked' AND record_revision = ?",
                (task_id, subject_revision),
            )
            if cur.rowcount != 1:
                raise OlympusContextError(
                    "olympus_release_cas_failed",
                    "governed release lost its exact revision CAS",
                )
            new_revision = int(conn.execute(
                "SELECT record_revision FROM tasks WHERE id = ?", (task_id,),
            ).fetchone()["record_revision"])
            _append_event(
                conn,
                task_id,
                "unblocked",
                {
                    "governed_release": True,
                    "from_revision": subject_revision,
                    "operation_id": operation_id,
                    "request_id": authorization["request"]["request_id"],
                },
            )
            created_at = int(time.time())
            context = authorization["context"]
            receipt = {
                "schema_version": "olympus-task-release-receipt/1",
                "operation_id": operation_id,
                "task_id": task_id,
                "previous_status": "blocked",
                "status": "ready",
                "previous_revision": int(subject_revision),
                "record_revision": new_revision,
                "verification_id": authorization["verification"]["verification_id"],
                "request_id": authorization["request"]["request_id"],
                "actor": authorization["request"]["actor"],
                "principal": authorization["request"]["principal"],
                "authority_id": context["authority"]["authority_id"],
                "authority_revision": context["authority"]["revision"],
                "authority_source": context["authority"]["source"],
                "lease_id": context["lease"]["lease_id"],
                "lease_revision": context["lease"]["revision"],
                "lease_source": context["lease"]["source"],
                "created_at": created_at,
            }
            encoded_receipt, receipt_sha256 = _canonical_json_record(receipt)
            _bind_issued_permit_write(
                conn,
                task_id,
                {
                    "schema_version": RELEASE_RECEIPT_WRITE_SCHEMA,
                    "operation_id": operation_id,
                    "task_id": task_id,
                    "subject_revision": subject_revision,
                    "record_revision": new_revision,
                    "verification_id": receipt["verification_id"],
                    "request_id": receipt["request_id"],
                    "receipt": encoded_receipt,
                    "receipt_sha256": receipt_sha256,
                    "created_at": created_at,
                },
            )
            conn.execute(
                "INSERT INTO kanban_olympus_release_receipts "
                "(operation_id,task_id,subject_revision,record_revision,"
                "verification_id,request_id,receipt,receipt_sha256,created_at) "
                "VALUES (?,?,?,?,?,?,?,?,?)",
                (
                    operation_id, task_id, subject_revision, new_revision,
                    receipt["verification_id"], receipt["request_id"],
                    encoded_receipt, receipt_sha256, created_at,
                ),
            )
            return receipt
        finally:
            _release_task_mutation_permit(conn, task_id, owns)


# Canonical sort-order mappings for ``hermes kanban list --sort``.
# Each value is a raw SQL fragment appended after ``ORDER BY``.
VALID_SORT_ORDERS: dict[str, str] = {
    "created": "created_at ASC, id ASC",
    "created-desc": "created_at DESC, id DESC",
    "priority": "priority DESC, created_at ASC",
    "priority-desc": "priority ASC, created_at ASC",
    "status": "status ASC, created_at ASC",
    "assignee": "assignee ASC, created_at ASC",
    "title": "title ASC, id ASC",
    "updated": "started_at DESC NULLS LAST, created_at DESC",
}


def list_tasks(
    conn: sqlite3.Connection,
    *,
    assignee: Optional[str] = None,
    status: Optional[str] = None,
    tenant: Optional[str] = None,
    session_id: Optional[str] = None,
    include_archived: bool = False,
    limit: Optional[int] = None,
    order_by: Optional[str] = None,
    workflow_template_id: Optional[str] = None,
    current_step_key: Optional[str] = None,
) -> list[Task]:
    query = "SELECT * FROM tasks WHERE 1=1"
    params: list[Any] = []
    if assignee is not None:
        query += " AND assignee = ?"
        params.append(_canonical_assignee(assignee))
    if status is not None:
        if status not in VALID_STATUSES:
            raise ValueError(f"status must be one of {sorted(VALID_STATUSES)}")
        query += " AND status = ?"
        params.append(status)
    if tenant is not None:
        query += " AND tenant = ?"
        params.append(tenant)
    if session_id is not None:
        query += " AND session_id = ?"
        params.append(session_id)
    if workflow_template_id is not None:
        query += " AND workflow_template_id = ?"
        params.append(workflow_template_id)
    if current_step_key is not None:
        query += " AND current_step_key = ?"
        params.append(current_step_key)
    if not include_archived and status != "archived":
        query += " AND status != 'archived'"
    if order_by is not None:
        order_by = order_by.strip().lower()
        if order_by not in VALID_SORT_ORDERS:
            raise ValueError(
                f"order_by must be one of {sorted(VALID_SORT_ORDERS.keys())}"
            )
        query += f" ORDER BY {VALID_SORT_ORDERS[order_by]}"
    else:
        query += " ORDER BY priority DESC, created_at ASC"
    if limit:
        query += f" LIMIT {int(limit)}"
    rows = conn.execute(query, params).fetchall()
    return [Task.from_row(r) for r in rows]


@_guarded_task_mutation(action="assign", capability=OLYMPUS_CAPABILITY_ASSIGN)
def assign_task(conn: sqlite3.Connection, task_id: str, profile: Optional[str]) -> bool:
    """Assign or reassign a task.  Returns True on success.

    Refuses to reassign a task that's currently running (claim_lock set).
    Reassign after the current run completes if needed.
    """
    profile = _canonical_assignee(profile)
    with write_txn(conn):
        row = conn.execute(
            "SELECT status, claim_lock, assignee, olympus_context "
            "FROM tasks WHERE id = ?", (task_id,)
        ).fetchone()
        if not row:
            return False
        if row["claim_lock"] is not None and row["status"] == "running":
            raise RuntimeError(
                f"cannot reassign {task_id}: currently running (claimed). "
                "Wait for completion or reclaim the stale lock first."
            )
        if row["olympus_context"] is not None:
            context = normalize_olympus_context(row["olympus_context"])
            lease = context["lease"]
            if not (
                profile
                == context["agent_id"]
                == lease["agent_id"]
                == lease["holder"]
                == row["assignee"]
            ):
                raise OlympusContextError(
                    "olympus_reassignment_requires_rebind",
                    "governed reassignment requires a new canonically verified context and lease",
                )
            return True
        if row["assignee"] != profile:
            # The retry guard is scoped to the task/profile combination. A
            # human reassigning the task is an explicit recovery action, so the
            # new profile should not inherit the previous profile's streak.
            conn.execute(
                "UPDATE tasks SET assignee = ?, consecutive_failures = 0, "
                "last_failure_error = NULL WHERE id = ?",
                (profile, task_id),
            )
        else:
            conn.execute("UPDATE tasks SET assignee = ? WHERE id = ?", (profile, task_id))
        _append_event(conn, task_id, "assigned", {"assignee": profile})
        return True


# ---------------------------------------------------------------------------
# Links
# ---------------------------------------------------------------------------

@_guarded_task_mutation(
    action="link",
    capability=OLYMPUS_CAPABILITY_LINK,
    task_params=("parent_id", "child_id"),
)
def link_tasks(conn: sqlite3.Connection, parent_id: str, child_id: str) -> None:
    if parent_id == child_id:
        raise ValueError("a task cannot depend on itself")
    with write_txn(conn):
        missing = _find_missing_parents(conn, [parent_id, child_id])
        if missing:
            raise ValueError(f"unknown task(s): {', '.join(missing)}")
        if _would_cycle(conn, parent_id, child_id):
            raise ValueError(
                f"linking {parent_id} -> {child_id} would create a cycle"
            )
        inserted = conn.execute(
            "INSERT OR IGNORE INTO task_links (parent_id, child_id) VALUES (?, ?)",
            (parent_id, child_id),
        )
        if inserted.rowcount != 1:
            return
        # If child was ready but parent is not yet done, demote child to todo.
        parent_status = conn.execute(
            "SELECT status FROM tasks WHERE id = ?", (parent_id,)
        ).fetchone()["status"]
        if parent_status != "done":
            conn.execute(
                "UPDATE tasks SET status = 'todo' WHERE id = ? AND status = 'ready'",
                (child_id,),
            )
        _append_event(
            conn, child_id, "linked",
            {"parent": parent_id, "child": child_id},
        )
        for linked_task_id in dict.fromkeys((parent_id, child_id)):
            if conn.execute(
                "SELECT 1 FROM tasks WHERE id = ? AND olympus_context IS NOT NULL",
                (linked_task_id,),
            ).fetchone() is not None:
                conn.execute(
                    "UPDATE tasks SET record_revision = record_revision WHERE id = ?",
                    (linked_task_id,),
                )


def _would_cycle(conn: sqlite3.Connection, parent_id: str, child_id: str) -> bool:
    """Return True if adding parent->child creates a cycle.

    A cycle exists iff ``parent_id`` is already a descendant of
    ``child_id`` via existing parent->child links.  We walk downward
    from ``child_id`` and check whether we reach ``parent_id``.
    """
    seen = set()
    stack = [child_id]
    while stack:
        node = stack.pop()
        if node == parent_id:
            return True
        if node in seen:
            continue
        seen.add(node)
        rows = conn.execute(
            "SELECT child_id FROM task_links WHERE parent_id = ?", (node,)
        ).fetchall()
        stack.extend(r["child_id"] for r in rows)
    return False


def unlink_tasks(
    conn: sqlite3.Connection,
    parent_id: str,
    child_id: str,
    *,
    olympus_auth: Optional[OlympusMutationAuth] = None,
) -> bool:
    bound_auth = olympus_auth or _OLYMPUS_MUTATION_AUTH.get()
    with olympus_mutation_scope(bound_auth), write_txn(conn):
        permits: list[tuple[str, bool, Optional[dict[str, Any]]]] = []
        authorization: Optional[dict[str, Any]] = None
        try:
            for task_id in dict.fromkeys((parent_id, child_id)):
                authorization, owns = _authorize_task_mutation(
                    conn,
                    task_id,
                    action="unlink",
                    capability=OLYMPUS_CAPABILITY_LINK,
                    auth=bound_auth,
                )
                permits.append((task_id, owns, authorization))
            cur = conn.execute(
                "DELETE FROM task_links WHERE parent_id = ? AND child_id = ?",
                (parent_id, child_id),
            )
            if cur.rowcount:
                _append_event(
                    conn, child_id, "unlinked",
                    {"parent": parent_id, "child": child_id},
                )
                for task_id, _, authorization in permits:
                    if authorization is not None:
                        conn.execute(
                            "UPDATE tasks SET record_revision = record_revision "
                            "WHERE id = ?",
                            (task_id,),
                        )
            removed = cur.rowcount > 0
        finally:
            for task_id, owns, _ in reversed(permits):
                _release_task_mutation_permit(conn, task_id, owns)
    if removed:
        # Dependency edge removed — re-evaluate promotion eligibility for the
        # child immediately.  Matches the contract of complete_task and
        # unblock_task; without this the child stays stuck in todo until the
        # next dispatcher tick or a manual `hermes kanban recompute` (issue #22459).
        recompute_ready(conn, olympus_auth=bound_auth)
    return removed


def parent_ids(conn: sqlite3.Connection, task_id: str) -> list[str]:
    rows = conn.execute(
        "SELECT parent_id FROM task_links WHERE child_id = ? ORDER BY parent_id",
        (task_id,),
    ).fetchall()
    return [r["parent_id"] for r in rows]


def child_ids(conn: sqlite3.Connection, task_id: str) -> list[str]:
    rows = conn.execute(
        "SELECT child_id FROM task_links WHERE parent_id = ? ORDER BY child_id",
        (task_id,),
    ).fetchall()
    return [r["child_id"] for r in rows]


def parent_results(conn: sqlite3.Connection, task_id: str) -> list[tuple[str, Optional[str]]]:
    """Return ``(parent_id, result)`` for every done parent of ``task_id``."""
    rows = conn.execute(
        """
        SELECT t.id AS id, t.result AS result
        FROM tasks t
        JOIN task_links l ON l.parent_id = t.id
        WHERE l.child_id = ? AND t.status = 'done'
        ORDER BY t.completed_at ASC
        """,
        (task_id,),
    ).fetchall()
    return [(r["id"], r["result"]) for r in rows]


# ---------------------------------------------------------------------------
# Comments & events
# ---------------------------------------------------------------------------

@_guarded_task_mutation(
    action="comment",
    capability=OLYMPUS_CAPABILITY_COMMENT,
    touch_aggregate=True,
)
def add_comment(
    conn: sqlite3.Connection, task_id: str, author: str, body: str
) -> int:
    if not body or not body.strip():
        raise ValueError("comment body is required")
    if not author or not author.strip():
        raise ValueError("comment author is required")
    now = int(time.time())
    with write_txn(conn):
        if not conn.execute(
            "SELECT 1 FROM tasks WHERE id = ?", (task_id,)
        ).fetchone():
            raise ValueError(f"unknown task {task_id}")
        cur = conn.execute(
            "INSERT INTO task_comments (task_id, author, body, created_at) "
            "VALUES (?, ?, ?, ?)",
            (task_id, author.strip(), body.strip(), now),
        )
        _append_event(conn, task_id, "commented", {"author": author, "len": len(body)})
        return int(cur.lastrowid or 0)


def list_comments(conn: sqlite3.Connection, task_id: str) -> list[Comment]:
    rows = conn.execute(
        "SELECT * FROM task_comments WHERE task_id = ? ORDER BY created_at ASC",
        (task_id,),
    ).fetchall()
    return [
        Comment(
            id=r["id"],
            task_id=r["task_id"],
            author=r["author"],
            body=r["body"],
            created_at=r["created_at"],
        )
        for r in rows
    ]


# ---------------------------------------------------------------------------
# Attachments
# ---------------------------------------------------------------------------

@_guarded_task_mutation(
    action="add_attachment",
    capability=OLYMPUS_CAPABILITY_ATTACHMENT,
    touch_aggregate=True,
)
def add_attachment(
    conn: sqlite3.Connection,
    task_id: str,
    *,
    filename: str,
    stored_path: str,
    content_type: Optional[str] = None,
    size: int = 0,
    uploaded_by: Optional[str] = None,
    board: Optional[str] = None,
) -> int:
    """Record a file attachment for a task. Returns the new attachment id.

    The caller is responsible for writing the blob to ``stored_path``
    first (under :func:`task_attachments_dir`); this only persists the
    metadata row and appends an ``attached`` event.
    """
    if not filename or not filename.strip():
        raise ValueError("attachment filename is required")
    if not stored_path or not stored_path.strip():
        raise ValueError("attachment stored_path is required")
    cleaned_filename = filename.strip()
    if Path(cleaned_filename).name != cleaned_filename:
        raise ValueError("attachment filename must be a single path component")
    canonical_path = validated_attachment_path(
        task_id, stored_path, board=board, require_file=False,
    )
    if canonical_path.name != cleaned_filename:
        raise ValueError("attachment filename must match stored_path")
    with open_attachment_for_read(
        task_id, canonical_path, board=board,
    ) as attachment_file:
        actual_size = int(os.fstat(attachment_file.fileno()).st_size)
    if int(size) != actual_size:
        raise ValueError("attachment size does not match the stored regular file")
    now = int(time.time())
    with write_txn(conn):
        if not conn.execute(
            "SELECT 1 FROM tasks WHERE id = ?", (task_id,)
        ).fetchone():
            raise ValueError(f"unknown task {task_id}")
        cur = conn.execute(
            "INSERT INTO task_attachments "
            "(task_id, filename, stored_path, content_type, size, uploaded_by, created_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            (
                task_id,
                cleaned_filename,
                str(canonical_path),
                content_type,
                actual_size,
                uploaded_by,
                now,
            ),
        )
        _append_event(
            conn,
            task_id,
            "attached",
            {"filename": cleaned_filename, "size": actual_size, "by": uploaded_by},
        )
        return int(cur.lastrowid or 0)


def list_attachments(conn: sqlite3.Connection, task_id: str) -> list[Attachment]:
    rows = conn.execute(
        "SELECT * FROM task_attachments WHERE task_id = ? ORDER BY created_at ASC, id ASC",
        (task_id,),
    ).fetchall()
    return [
        Attachment(
            id=r["id"],
            task_id=r["task_id"],
            filename=r["filename"],
            stored_path=r["stored_path"],
            content_type=r["content_type"],
            size=r["size"] or 0,
            uploaded_by=r["uploaded_by"],
            created_at=r["created_at"],
        )
        for r in rows
    ]


def get_attachment(conn: sqlite3.Connection, attachment_id: int) -> Optional[Attachment]:
    r = conn.execute(
        "SELECT * FROM task_attachments WHERE id = ?", (attachment_id,)
    ).fetchone()
    if r is None:
        return None
    return Attachment(
        id=r["id"],
        task_id=r["task_id"],
        filename=r["filename"],
        stored_path=r["stored_path"],
        content_type=r["content_type"],
        size=r["size"] or 0,
        uploaded_by=r["uploaded_by"],
        created_at=r["created_at"],
    )


def delete_attachment(
    conn: sqlite3.Connection,
    attachment_id: int,
    *,
    olympus_auth: Optional[OlympusMutationAuth] = None,
    board: Optional[str] = None,
) -> Optional[Attachment]:
    """Delete an attachment row and its on-disk blob. Returns the removed row.

    Returns ``None`` when no row matched. The blob is removed best-effort
    (a missing file is not an error); the metadata row is the source of
    truth for whether an attachment "exists".
    """
    with olympus_mutation_scope(olympus_auth), write_txn(conn):
        att = get_attachment(conn, attachment_id)
        if att is None:
            return None
        canonical_path = validated_attachment_path(
            att.task_id, att.stored_path, board=board, require_file=False,
        )
        _authorize_task_mutation(
            conn,
            att.task_id,
            action="delete_attachment",
            capability=OLYMPUS_CAPABILITY_ATTACHMENT,
            auth=olympus_auth,
        )
        conn.execute("DELETE FROM task_attachments WHERE id = ?", (attachment_id,))
        conn.execute(
            "UPDATE tasks SET record_revision = record_revision WHERE id = ?",
            (att.task_id,),
        )
        _append_event(
            conn, att.task_id, "attachment_removed", {"filename": att.filename}
        )
    try:
        unlink_attachment_blob(att.task_id, canonical_path, board=board)
    except (OSError, ValueError):
        pass
    return att


def list_events(conn: sqlite3.Connection, task_id: str) -> list[Event]:
    rows = conn.execute(
        "SELECT * FROM task_events WHERE task_id = ? ORDER BY created_at ASC, id ASC",
        (task_id,),
    ).fetchall()
    out = []
    for r in rows:
        try:
            payload = json.loads(r["payload"]) if r["payload"] else None
        except Exception:
            payload = None
        out.append(
            Event(
                id=r["id"],
                task_id=r["task_id"],
                kind=r["kind"],
                payload=payload,
                created_at=r["created_at"],
                run_id=(int(r["run_id"]) if "run_id" in r.keys() and r["run_id"] is not None else None),
            )
        )
    return out


def _append_event(
    conn: sqlite3.Connection,
    task_id: str,
    kind: str,
    payload: Optional[dict] = None,
    *,
    run_id: Optional[int] = None,
) -> None:
    """Record an event row.  Called from within an already-open txn.

    ``run_id`` is optional: pass the current run id so UIs can group
    events by attempt. For events that aren't scoped to a single run
    (task created/edited/archived, dependency promotion) leave it None
    and the row carries NULL.
    """
    now = int(time.time())
    pl = json.dumps(payload, ensure_ascii=False) if payload else None
    audit_registry = getattr(conn, "_olympus_audit_registry", None)
    protected_audit = False
    if kind in _OLYMPUS_PROTECTED_AUDIT_KINDS:
        governed = conn.execute(
            "SELECT 1 FROM tasks WHERE id = ? AND olympus_context IS NOT NULL",
            (task_id,),
        ).fetchone() is not None
        has_permit = _issued_permit_row(conn, task_id) is not None
        if governed and not has_permit:
            if audit_registry is None:
                raise OlympusContextError(
                    "olympus_audit_registry_missing",
                    "protected audit registry is unavailable",
                )
            token = (
                str(task_id), int(run_id) if run_id is not None else None,
                str(kind), str(pl) if pl is not None else None, int(now),
            )
            audit_registry.add(token)
            protected_audit = True
    try:
        conn.execute(
            "INSERT INTO task_events (task_id, run_id, kind, payload, created_at) "
            "VALUES (?, ?, ?, ?, ?)",
            (task_id, run_id, kind, pl, now),
        )
    finally:
        if protected_audit:
            audit_registry.discard(token)


def _end_run(
    conn: sqlite3.Connection,
    task_id: str,
    *,
    outcome: str,
    summary: Optional[str] = None,
    error: Optional[str] = None,
    metadata: Optional[dict] = None,
    status: Optional[str] = None,
) -> Optional[int]:
    """Close the currently-active run for ``task_id`` and clear the pointer.

    ``outcome`` is the semantic result (completed / blocked / crashed /
    timed_out / spawn_failed / gave_up / reclaimed). ``status`` is the
    run-row status (usually just ``outcome``, but callers can pass it
    explicitly). Returns the closed run_id or ``None`` if no active run
    existed (e.g. a CLI user calling ``hermes kanban complete`` on a
    task that was never claimed).
    """
    now = int(time.time())
    row = conn.execute(
        "SELECT current_run_id FROM tasks WHERE id = ?", (task_id,),
    ).fetchone()
    if not row or not row["current_run_id"]:
        return None
    run_id = int(row["current_run_id"])
    conn.execute(
        """
        UPDATE task_runs
           SET status        = ?,
               outcome       = ?,
               summary       = ?,
               error         = ?,
               metadata      = ?,
               ended_at      = ?,
               claim_lock    = NULL,
               claim_expires = NULL,
               worker_pid    = NULL
         WHERE id = ?
           AND ended_at IS NULL
        """,
        (
            status or outcome,
            outcome,
            summary,
            error,
            json.dumps(metadata, ensure_ascii=False) if metadata else None,
            now,
            run_id,
        ),
    )
    conn.execute(
        "UPDATE tasks SET current_run_id = NULL WHERE id = ?", (task_id,),
    )
    return run_id


def _current_run_id(conn: sqlite3.Connection, task_id: str) -> Optional[int]:
    row = conn.execute(
        "SELECT current_run_id FROM tasks WHERE id = ?", (task_id,),
    ).fetchone()
    return int(row["current_run_id"]) if row and row["current_run_id"] else None


def _synthesize_ended_run(
    conn: sqlite3.Connection,
    task_id: str,
    *,
    outcome: str,
    summary: Optional[str] = None,
    error: Optional[str] = None,
    metadata: Optional[dict] = None,
) -> int:
    """Insert a zero-duration, already-closed run row.

    Used when a terminal transition happens on a task that was never
    claimed (CLI user calling ``hermes kanban complete <ready-task>
    --summary X``, or dashboard "mark done" on a ready task). Without
    this, the handoff fields (summary / metadata / error) would be
    silently dropped: ``_end_run`` is a no-op because there's no
    current run.

    The synthetic run has ``started_at == ended_at == now`` so it
    shows up in attempt history as "instant" and doesn't skew elapsed
    stats. Caller is responsible for leaving ``current_run_id`` NULL
    (or for clearing it elsewhere in the same txn) since this
    function does NOT touch the tasks row.
    """
    now = int(time.time())
    trow = conn.execute(
        "SELECT assignee, current_step_key, olympus_context, record_revision "
        "FROM tasks WHERE id = ?",
        (task_id,),
    ).fetchone()
    profile = trow["assignee"] if trow else None
    step_key = trow["current_step_key"] if trow else None
    olympus_context = trow["olympus_context"] if trow else None
    subject_revision = (
        int(trow["record_revision"])
        if trow and olympus_context is not None else None
    )
    auth_root_id = None
    auth_root_revision = None
    verification_id = None
    if olympus_context is not None:
        permit = _issued_permit_row(conn, task_id)
        if permit is None:
            raise OlympusContextError(
                "olympus_authority_verification_unavailable",
                "governed terminal run requires an active exact permit",
            )
        subject_revision = int(permit["subject_revision"])
        auth_root_id = str(permit["auth_root_id"])
        auth_root_revision = int(permit["auth_root_revision"])
        verification_id = str(permit["verification_id"])
    cur = conn.execute(
        """
        INSERT INTO task_runs (
            task_id, profile, step_key,
            status, outcome,
            summary, error, metadata,
            started_at, ended_at, olympus_context, subject_revision,
            process_state, auth_root_id, auth_root_revision, verification_id
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            task_id, profile, step_key,
            outcome, outcome,
            summary, error,
            json.dumps(metadata, ensure_ascii=False) if metadata else None,
            now, now, olympus_context, subject_revision,
            "terminal", auth_root_id, auth_root_revision, verification_id,
        ),
    )
    return int(cur.lastrowid or 0)


# ---------------------------------------------------------------------------
# Dependency resolution (todo -> ready)
# ---------------------------------------------------------------------------

def _has_sticky_block(conn: sqlite3.Connection, task_id: str) -> bool:
    """Return True when ``task_id`` is sticky-blocked by an explicit
    worker/operator ``kanban_block`` call (#28712).

    A ``blocked`` status can come from two very different sources:

    * **Worker- or operator-initiated** — a worker called
      ``kanban_block(reason="review-required: ...")`` (or somebody ran
      ``hermes kanban block <id>``).  This is a deliberate handoff that
      should stay blocked until an operator unblocks it.  The block tool
      emits a ``"blocked"`` event row in ``task_events``.

    * **Circuit-breaker** — ``_record_task_failure`` tripped after
      repeated crashes / spawn failures / timeouts.  This emits
      ``"gave_up"``, *not* ``"blocked"``, and is meant to recover
      automatically once the underlying conditions change (e.g. parents
      finish, transient infra error clears).

    The cheapest signal that distinguishes the two is the most recent
    ``"blocked"`` / ``"unblocked"`` event for the task.  If the most
    recent one is ``"blocked"`` (or there is a ``"blocked"`` event and
    no ``"unblocked"`` event has fired since), the task is sticky and
    ``recompute_ready`` must *not* auto-promote it.

    Returns ``False`` when there is no such event at all (e.g. the task
    was set to ``status='blocked'`` by the circuit breaker or by direct
    DB manipulation) — preserves the pre-#28712 auto-recover semantics
    for that path.
    """
    row = conn.execute(
        "SELECT kind FROM task_events "
        "WHERE task_id = ? AND kind IN ('blocked', 'unblocked') "
        "ORDER BY id DESC LIMIT 1",
        (task_id,),
    ).fetchone()
    return bool(row) and row["kind"] == "blocked"


def recompute_ready(
    conn: sqlite3.Connection,
    failure_limit: int = None,
    *,
    olympus_auth: Optional[OlympusMutationAuth] = None,
) -> int:
    """Promote ``todo`` tasks to ``ready`` when all parents are ``done`` or ``archived``.

    Returns the number of tasks promoted.  Safe to call inside or outside
    an existing transaction; it opens its own IMMEDIATE txn.

    ``blocked`` tasks are also considered for promotion (so a task
    blocked purely by a parent dependency unblocks itself when the
    parent completes), *except* in two cases:

    1. The most recent block event was a worker-initiated
       ``kanban_block`` — those stay blocked until an explicit
       ``kanban_unblock`` (#28712).

    2. The task's ``consecutive_failures`` has reached the effective
       failure limit.  This prevents infinite retry loops when a task
       repeatedly exhausts its iteration budget: without this guard the
       counter would reset on every recovery cycle and the circuit
       breaker could never trip (#35072).

    The effective failure limit resolves in the same order as the
    circuit breaker in ``_record_task_failure`` so the two never
    disagree about when a task is permanently blocked:

      1. per-task ``max_retries`` if set
      2. caller-supplied ``failure_limit`` (the dispatcher passes the
         ``kanban.failure_limit`` config value through ``dispatch_once``)
      3. ``DEFAULT_FAILURE_LIMIT``
    """
    if failure_limit is None:
        failure_limit = DEFAULT_FAILURE_LIMIT
    promoted = 0
    with write_txn(conn):
        todo_rows = conn.execute(
            "SELECT id, status, consecutive_failures, max_retries, olympus_context "
            "FROM tasks WHERE status IN ('todo', 'blocked')"
        ).fetchall()
        for row in todo_rows:
            task_id = row["id"]
            cur_status = row["status"]
            if cur_status == "blocked" and _has_sticky_block(conn, task_id):
                # Worker / operator asked for human review — do not
                # silently auto-recover.  ``unblock_task`` is the only
                # legitimate exit (it emits ``"unblocked"`` which flips
                # this predicate back).
                continue
            parents = conn.execute(
                "SELECT t.status FROM tasks t "
                "JOIN task_links l ON l.parent_id = t.id "
                "WHERE l.child_id = ?",
                (task_id,),
            ).fetchall()
            if all(p["status"] in ("done", "archived") for p in parents):
                try:
                    _authorize_task_mutation(
                        conn,
                        task_id,
                        action="promote",
                        capability=OLYMPUS_CAPABILITY_STATUS,
                        auth=olympus_auth,
                    )
                except OlympusContextError as exc:
                    _append_event(
                        conn,
                        task_id,
                        "promotion_rejected",
                        {"reason": exc.reason, "governance": "olympus"},
                    )
                    continue
                if cur_status == "blocked":
                    # Don't auto-recover tasks that have hit the
                    # circuit-breaker failure limit.  Without this
                    # guard, a task that repeatedly exhausts its
                    # iteration budget would cycle forever:
                    # block → auto-recover → respawn → budget
                    # exhausted → block → …  The counter must also
                    # be preserved so the breaker can accumulate
                    # across recovery cycles.
                    failures = int(row["consecutive_failures"] or 0)
                    task_limit = row["max_retries"]
                    effective_limit = (
                        int(task_limit) if task_limit is not None
                        else int(failure_limit)
                    )
                    if failures >= effective_limit:
                        continue
                    conn.execute(
                        "UPDATE tasks SET status = 'ready' "
                        "WHERE id = ? AND status = 'blocked'",
                        (task_id,),
                    )
                else:
                    conn.execute(
                        "UPDATE tasks SET status = 'ready' WHERE id = ? AND status = 'todo'",
                        (task_id,),
                    )
                _append_event(conn, task_id, "promoted", None)
                promoted += 1
    return promoted


# ---------------------------------------------------------------------------
# Claim / complete / block
# ---------------------------------------------------------------------------

def claim_task(
    conn: sqlite3.Connection,
    task_id: str,
    *,
    ttl_seconds: Optional[int] = None,
    claimer: Optional[str] = None,
    olympus_auth: Optional[OlympusMutationAuth] = None,
) -> Optional[Task]:
    """Atomically transition ``ready -> running``.

    Returns the claimed ``Task`` on success, ``None`` if the task was
    already claimed (or is not in ``ready`` status).
    """
    now = int(time.time())
    lock = claimer or _claimer_id()
    expires = now + _resolve_claim_ttl_seconds(ttl_seconds)
    with write_txn(conn):
        authorization: Optional[dict[str, Any]] = None
        gate_row = conn.execute(
            "SELECT status, assignee, olympus_context FROM tasks WHERE id = ?",
            (task_id,),
        ).fetchone()
        if gate_row is None or gate_row["status"] != "ready":
            return None
        try:
            olympus = _require_current_olympus_context(
                gate_row["olympus_context"],
                assignee=gate_row["assignee"],
                now=now,
            )
            if olympus is not None:
                authorization, _ = _authorize_task_mutation(
                    conn,
                    task_id,
                    action="claim",
                    capability=OLYMPUS_CAPABILITY_CLAIM,
                    auth=olympus_auth,
                )
        except OlympusContextError as exc:
            _append_event(
                conn,
                task_id,
                "claim_rejected",
                {"reason": exc.reason, "governance": "olympus"},
            )
            return None
        olympus_json = (
            _serialize_olympus_context(olympus) if olympus is not None else None
        )
        if olympus is not None:
            expires = min(expires, int(olympus["lease"]["expires_at"]))
        launch_token = secrets.token_urlsafe(32)
        run_origin_revision: Optional[int] = None
        auth_root_id: Optional[str] = None
        auth_root_revision: Optional[int] = None
        verification_id: Optional[str] = None
        if authorization is not None:
            permit = _issued_permit_row(conn, task_id)
            if permit is None:
                raise OlympusContextError(
                    "olympus_authority_verification_unavailable",
                    "governed claim requires an active exact permit",
                )
            run_origin_revision = int(permit["subject_revision"])
            authorization_subject = (
                authorization["request"]["authorization_root"]
                or authorization["request"]["target"]
            )
            auth_root_id = str(authorization_subject["subject_id"])
            auth_root_revision = int(authorization_subject["subject_revision"])
            verification_id = str(
                authorization["verification"]["verification_id"]
            )
        # Structural invariant: never transition ready -> running while any
        # parent is not yet 'done'. This is the single enforcement point
        # regardless of which writer (create_task, link_tasks, unblock_task,
        # release_stale_claims, manual SQL) set status='ready'. If a racy
        # writer promoted a task with undone parents, demote it back to
        # 'todo' here — recompute_ready will re-promote when the parents
        # actually finish. See RCA at
        # kanban/boards/cookai/workspaces/t_a6acd07d/root-cause.md.
        undone = conn.execute(
            "SELECT 1 FROM task_links l "
            "JOIN tasks p ON p.id = l.parent_id "
            "WHERE l.child_id = ? AND p.status NOT IN ('done', 'archived') LIMIT 1",
            (task_id,),
        ).fetchone()
        if undone:
            conn.execute(
                "UPDATE tasks SET status = 'todo' "
                "WHERE id = ? AND status = 'ready'",
                (task_id,),
            )
            _append_event(
                conn, task_id, "claim_rejected",
                {"reason": "parents_not_done"},
            )
            return None
        # Defensive: if a prior run somehow leaked (invariant violation from
        # an unknown code path), close it as 'reclaimed' so we don't strand
        # it when the CAS resets the pointer below. No-op when the invariant
        # holds (the common case).
        stale = conn.execute(
            "SELECT current_run_id FROM tasks WHERE id = ? AND status = 'ready'",
            (task_id,),
        ).fetchone()
        if stale and stale["current_run_id"]:
            conn.execute(
                """
                UPDATE task_runs
                   SET status = 'reclaimed', outcome = 'reclaimed',
                       summary = COALESCE(summary, 'invariant recovery on re-claim'),
                       ended_at = ?,
                       claim_lock = NULL, claim_expires = NULL, worker_pid = NULL
                 WHERE id = ? AND ended_at IS NULL
                """,
                (now, int(stale["current_run_id"])),
            )
        cur = conn.execute(
            """
            UPDATE tasks
               SET status        = 'running',
                   claim_lock    = ?,
                   claim_expires = ?,
                   started_at    = COALESCE(started_at, ?)
             WHERE id = ?
               AND status = 'ready'
               AND claim_lock IS NULL
            """,
            (lock, expires, now, task_id),
        )
        if cur.rowcount != 1:
            return None
        # Look up the current task row so we can populate the run with
        # its assignee / step / runtime cap.
        trow = conn.execute(
            "SELECT assignee, max_runtime_seconds, current_step_key, "
            "olympus_context, record_revision "
            "FROM tasks WHERE id = ?",
            (task_id,),
        ).fetchone()
        run_cur = conn.execute(
            """
            INSERT INTO task_runs (
                task_id, profile, step_key, status,
                claim_lock, claim_expires, max_runtime_seconds,
                started_at, olympus_context, subject_revision,
                process_state, launch_token, auth_root_id,
                auth_root_revision, verification_id
            ) VALUES (?, ?, ?, 'running', ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                task_id,
                trow["assignee"] if trow else None,
                trow["current_step_key"] if trow else None,
                lock,
                expires,
                trow["max_runtime_seconds"] if trow else None,
                now,
                olympus_json,
                run_origin_revision,
                "workspace_pending",
                launch_token,
                auth_root_id,
                auth_root_revision,
                verification_id,
            ),
        )
        run_id = run_cur.lastrowid
        conn.execute(
            "UPDATE tasks SET current_run_id = ? WHERE id = ?",
            (run_id, task_id),
        )
        claimed_payload: dict[str, Any] = {
            "lock": lock, "expires": expires, "run_id": run_id
        }
        if olympus is not None:
            claimed_payload["olympus"] = _olympus_trace(olympus)
        _append_event(
            conn, task_id, "claimed",
            claimed_payload,
            run_id=run_id,
        )
        return get_task(conn, task_id)


def claim_review_task(
    conn: sqlite3.Connection,
    task_id: str,
    *,
    ttl_seconds: Optional[int] = None,
    claimer: Optional[str] = None,
    olympus_auth: Optional[OlympusMutationAuth] = None,
) -> Optional[Task]:
    """Atomically transition ``review -> running``.

    Returns the claimed ``Task`` on success, ``None`` if the task was
    already claimed (or is not in ``review`` status).

    Unlike ``claim_task`` (which handles ``ready -> running``), this
    does NOT check parent dependencies — the task already passed that
    gate on its original ``todo -> ready -> running`` transition.

    Creates a new run entry so the review agent's lifecycle is tracked
    independently from the original worker run.
    """
    now = int(time.time())
    lock = claimer or _claimer_id()
    expires = now + _resolve_claim_ttl_seconds(ttl_seconds)
    with write_txn(conn):
        authorization: Optional[dict[str, Any]] = None
        gate_row = conn.execute(
            "SELECT status, assignee, olympus_context FROM tasks WHERE id = ?",
            (task_id,),
        ).fetchone()
        if gate_row is None or gate_row["status"] != "review":
            return None
        try:
            olympus = _require_current_olympus_context(
                gate_row["olympus_context"],
                assignee=gate_row["assignee"],
                now=now,
            )
            if olympus is not None:
                authorization, _ = _authorize_task_mutation(
                    conn,
                    task_id,
                    action="claim_review",
                    capability=OLYMPUS_CAPABILITY_CLAIM,
                    auth=olympus_auth,
                )
        except OlympusContextError as exc:
            _append_event(
                conn,
                task_id,
                "claim_rejected",
                {
                    "reason": exc.reason,
                    "governance": "olympus",
                    "source_status": "review",
                },
            )
            return None
        olympus_json = (
            _serialize_olympus_context(olympus) if olympus is not None else None
        )
        if olympus is not None:
            expires = min(expires, int(olympus["lease"]["expires_at"]))
        launch_token = secrets.token_urlsafe(32)
        run_origin_revision: Optional[int] = None
        auth_root_id: Optional[str] = None
        auth_root_revision: Optional[int] = None
        verification_id: Optional[str] = None
        if authorization is not None:
            permit = _issued_permit_row(conn, task_id)
            if permit is None:
                raise OlympusContextError(
                    "olympus_authority_verification_unavailable",
                    "governed review claim requires an active exact permit",
                )
            run_origin_revision = int(permit["subject_revision"])
            authorization_subject = (
                authorization["request"]["authorization_root"]
                or authorization["request"]["target"]
            )
            auth_root_id = str(authorization_subject["subject_id"])
            auth_root_revision = int(authorization_subject["subject_revision"])
            verification_id = str(
                authorization["verification"]["verification_id"]
            )
        cur = conn.execute(
            """
            UPDATE tasks
               SET status        = 'running',
                   claim_lock    = ?,
                   claim_expires = ?,
                   started_at    = COALESCE(started_at, ?)
             WHERE id = ?
               AND status = 'review'
               AND claim_lock IS NULL
            """,
            (lock, expires, now, task_id),
        )
        if cur.rowcount != 1:
            return None
        trow = conn.execute(
            "SELECT assignee, max_runtime_seconds, current_step_key, "
            "olympus_context, record_revision "
            "FROM tasks WHERE id = ?",
            (task_id,),
        ).fetchone()
        run_cur = conn.execute(
            """
            INSERT INTO task_runs (
                task_id, profile, step_key, status,
                claim_lock, claim_expires, max_runtime_seconds,
                started_at, olympus_context, subject_revision,
                process_state, launch_token, auth_root_id,
                auth_root_revision, verification_id
            ) VALUES (?, ?, ?, 'running', ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                task_id,
                trow["assignee"] if trow else None,
                trow["current_step_key"] if trow else None,
                lock,
                expires,
                trow["max_runtime_seconds"] if trow else None,
                now,
                olympus_json,
                run_origin_revision,
                "workspace_pending",
                launch_token,
                auth_root_id,
                auth_root_revision,
                verification_id,
            ),
        )
        run_id = run_cur.lastrowid
        conn.execute(
            "UPDATE tasks SET current_run_id = ? WHERE id = ?",
            (run_id, task_id),
        )
        claimed_payload = {
            "lock": lock, "expires": expires, "run_id": run_id,
            "source_status": "review"
        }
        if olympus is not None:
            claimed_payload["olympus"] = _olympus_trace(olympus)
        _append_event(
            conn, task_id, "claimed",
            claimed_payload,
            run_id=run_id,
        )
        return get_task(conn, task_id)


def reserve_worker_run(
    conn: sqlite3.Connection,
    task_id: str,
    *,
    review: bool = False,
    ttl_seconds: Optional[int] = None,
    claimer: Optional[str] = None,
    olympus_auth: Optional[OlympusMutationAuth] = None,
) -> Optional[Run]:
    """Claim a task and durably reserve its unique worker launch token."""
    claim = claim_review_task if review else claim_task
    task = claim(
        conn,
        task_id,
        ttl_seconds=ttl_seconds,
        claimer=claimer,
        olympus_auth=olympus_auth,
    )
    if task is None or task.current_run_id is None:
        return None
    return get_run(conn, int(task.current_run_id))


def _worker_run_gate(
    conn: sqlite3.Connection,
    *,
    task_id: str,
    run_id: int,
    launch_token: str,
) -> sqlite3.Row:
    row = conn.execute(
        "SELECT r.*, t.status AS task_status, t.current_run_id, "
        "t.claim_lock AS task_claim_lock, t.olympus_context AS task_context "
        "FROM task_runs r JOIN tasks t ON t.id = r.task_id "
        "WHERE r.id = ? AND r.task_id = ?",
        (int(run_id), task_id),
    ).fetchone()
    if (
        row is None
        or not launch_token
        or row["launch_token"] != launch_token
        or row["current_run_id"] != int(run_id)
        or row["task_status"] != "running"
        or row["status"] != "running"
        or row["ended_at"] is not None
        or row["task_claim_lock"] != row["claim_lock"]
    ):
        raise OlympusContextError(
            "worker_run_identity_mismatch",
            "worker run is not the current exact launch reservation",
        )
    return row


def mark_worker_workspace_ready(
    conn: sqlite3.Connection,
    *,
    task_id: str,
    run_id: int,
    launch_token: str,
    workspace_snapshot: Mapping[str, Any],
    olympus_auth: Optional[OlympusMutationAuth] = None,
) -> bool:
    """CAS a reserved run to workspace-ready with an immutable snapshot."""
    if not isinstance(workspace_snapshot, Mapping) or not workspace_snapshot:
        raise ValueError("workspace_snapshot must be a non-empty mapping")
    snapshot = json.dumps(
        dict(workspace_snapshot), sort_keys=True, separators=(",", ":"),
    )
    with write_txn(conn):
        _worker_run_gate(
            conn, task_id=task_id, run_id=run_id, launch_token=launch_token,
        )
        with _task_mutation_permit(
            conn,
            task_id,
            action="mark_worker_workspace_ready",
            capability=OLYMPUS_CAPABILITY_WORKSPACE,
            auth=olympus_auth,
        ):
            cur = conn.execute(
                "UPDATE task_runs SET process_state = 'launch_reserved', "
                "workspace_snapshot = ? WHERE id = ? AND task_id = ? "
                "AND launch_token = ? AND process_state = 'workspace_pending'",
                (snapshot, int(run_id), task_id, launch_token),
            )
    return cur.rowcount == 1


def mark_worker_starting(
    conn: sqlite3.Connection,
    *,
    task_id: str,
    run_id: int,
    launch_token: str,
    olympus_auth: Optional[OlympusMutationAuth] = None,
) -> bool:
    """Commit the launch-reserved to starting CAS before spawning."""
    with write_txn(conn):
        _worker_run_gate(
            conn, task_id=task_id, run_id=run_id, launch_token=launch_token,
        )
        with _task_mutation_permit(
            conn,
            task_id,
            action="mark_worker_starting",
            capability=OLYMPUS_CAPABILITY_CLAIM,
            auth=olympus_auth,
        ):
            cur = conn.execute(
                "UPDATE task_runs SET process_state = 'starting' "
                "WHERE id = ? AND task_id = ? AND launch_token = ? "
                "AND process_state = 'launch_reserved' "
                "AND workspace_snapshot IS NOT NULL",
                (int(run_id), task_id, launch_token),
            )
    return cur.rowcount == 1


def register_worker_process(
    conn: sqlite3.Connection,
    *,
    task_id: str,
    run_id: int,
    launch_token: str,
    process_identity: ProcessIdentity,
    dispatcher_instance_id: str,
    olympus_auth: Optional[OlympusMutationAuth] = None,
) -> bool:
    """Register the bootstrap's exact live process identity before work."""
    if (
        read_process_identity(process_identity.pid) != process_identity
        or not dispatcher_instance_id.strip()
    ):
        raise OlympusContextError(
            "worker_process_identity_unverified",
            "worker bootstrap process identity could not be verified",
        )
    now = int(time.time())
    with write_txn(conn):
        _worker_run_gate(
            conn, task_id=task_id, run_id=run_id, launch_token=launch_token,
        )
        task_revision = int(conn.execute(
            "SELECT record_revision FROM tasks WHERE id = ?", (task_id,),
        ).fetchone()["record_revision"])
        mutation_binding = {
            "schema_version": WORKER_REGISTRATION_WRITE_SCHEMA,
            "action": "register_worker_process",
            "task_id": task_id,
            "task_record_revision": task_revision,
            "dispatcher_instance_id": dispatcher_instance_id.strip(),
        }
        with _task_mutation_permit(
            conn,
            task_id,
            action="register_worker_process",
            capability=OLYMPUS_CAPABILITY_CLAIM,
            auth=olympus_auth,
            mutation_binding=mutation_binding,
        ):
            cur = conn.execute(
                "UPDATE task_runs SET process_state = 'registered', worker_pid = ?, "
                "worker_host_id = ?, worker_boot_id = ?, worker_start_token = ?, "
                "worker_registered_at = ?, dispatcher_instance_id = ? "
                "WHERE id = ? AND task_id = ? AND launch_token = ? "
                "AND process_state = 'starting'",
                (
                    process_identity.pid, process_identity.host_id,
                    process_identity.boot_id, process_identity.start_token,
                    now, dispatcher_instance_id.strip(), int(run_id), task_id,
                    launch_token,
                ),
            )
            if cur.rowcount == 1:
                conn.execute(
                    "UPDATE tasks SET worker_pid = ? WHERE id = ? "
                    "AND current_run_id = ?",
                    (process_identity.pid, task_id, int(run_id)),
                )
    return cur.rowcount == 1


def fail_worker_launch(
    conn: sqlite3.Connection,
    *,
    task_id: str,
    run_id: int,
    launch_token: str,
    error: str,
    olympus_auth: Optional[OlympusMutationAuth] = None,
) -> bool:
    """Fail closed when bootstrap registration cannot complete."""
    now = int(time.time())
    with write_txn(conn):
        _worker_run_gate(
            conn, task_id=task_id, run_id=run_id, launch_token=launch_token,
        )
        with _task_mutation_permit(
            conn,
            task_id,
            action="fail_worker_launch",
            capability=OLYMPUS_CAPABILITY_RECOVER,
            auth=olympus_auth,
        ):
            cur = conn.execute(
                "UPDATE task_runs SET process_state = 'spawn_failed', "
                "status = 'failed', outcome = 'spawn_failed', error = ?, "
                "ended_at = ?, claim_lock = NULL, claim_expires = NULL "
                "WHERE id = ? AND task_id = ? AND launch_token = ? "
                "AND process_state IN ('workspace_pending','launch_reserved','starting')",
                (str(error)[:2000], now, int(run_id), task_id, launch_token),
            )
            if cur.rowcount == 1:
                conn.execute(
                    "UPDATE tasks SET status = 'blocked', claim_lock = NULL, "
                    "claim_expires = NULL, worker_pid = NULL, current_run_id = NULL, "
                    "last_failure_error = ? WHERE id = ? AND current_run_id = ?",
                    (str(error)[:2000], task_id, int(run_id)),
                )
    return cur.rowcount == 1


def _canonical_effect_payload(payload: Mapping[str, Any]) -> tuple[str, str]:
    encoded = json.dumps(
        dict(payload), sort_keys=True, separators=(",", ":"),
        ensure_ascii=False, allow_nan=False,
    )
    return encoded, hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def _canonical_notifier_effect_source_identity(
    notifier: Mapping[str, Any],
) -> dict[str, Any]:
    """Derive persisted effect-source evidence from a live notifier snapshot."""
    return {
        "schema_version": "kanban-notifier-effect-source/1",
        "board_id": notifier["board_id"],
        "task_id": notifier["task_id"],
        "platform": notifier["platform"],
        "chat_id": notifier["chat_id"],
        "thread_id": notifier["thread_id"],
        "user_id": notifier["user_id"],
        "notifier_profile": notifier["notifier_profile"],
        "gateway_host_id": notifier["gateway_host_id"],
        "gateway_boot_id": notifier["gateway_boot_id"],
        "gateway_pid": notifier["gateway_pid"],
        "gateway_start_token": notifier["gateway_start_token"],
    }


def _canonical_notifier_effect_source(
    auth: OlympusMutationAuth,
) -> dict[str, Any]:
    notifier = auth.notifier_identity
    if not isinstance(notifier, dict):
        raise OlympusContextError(
            "olympus_notifier_identity_missing",
            "governed notification effect requires canonical notifier identity",
        )
    return _canonical_notifier_effect_source_identity(notifier)


def stage_worker_termination(
    conn: sqlite3.Connection,
    *,
    task_id: str,
    run_id: int,
    launch_token: str,
    process_identity: ProcessIdentity,
    operation_id: str,
    reason: str,
    source_identity: Mapping[str, Any],
    outcome: str = "reclaimed",
    event_kind: str = "termination_staged",
    olympus_auth: Optional[OlympusMutationAuth] = None,
) -> int:
    """Contain a run and journal one exact termination effect atomically."""
    if outcome not in {"reclaimed", "stale", "timed_out", "crashed"}:
        raise ValueError("invalid governed recovery outcome")
    if event_kind not in {
        "reclaimed", "stale", "timed_out", "crashed", "termination_staged",
    }:
        raise ValueError("invalid governed recovery event kind")
    now = int(time.time())
    effect_payload = {
        "reason": str(reason)[:2000],
        "outcome": outcome,
        "event_kind": event_kind,
    }
    payload, digest = _canonical_effect_payload(effect_payload)
    source = json.dumps(
        dict(source_identity), sort_keys=True, separators=(",", ":"),
    )
    with write_txn(conn):
        row = _worker_run_gate(
            conn, task_id=task_id, run_id=run_id, launch_token=launch_token,
        )
        stored = ProcessIdentity(
            host_id=str(row["worker_host_id"] or ""),
            boot_id=str(row["worker_boot_id"] or ""),
            pid=int(row["worker_pid"] or 0),
            start_token=str(row["worker_start_token"] or ""),
        )
        if row["process_state"] != "registered" or stored != process_identity:
            raise OlympusContextError(
                "worker_process_identity_mismatch",
                "termination target does not match the registered process",
            )
        with _task_mutation_permit(
            conn,
            task_id,
            action="stage_worker_termination",
            capability=OLYMPUS_CAPABILITY_RECOVER,
            auth=olympus_auth,
        ):
            permit = _issued_permit_row(conn, task_id)
            if permit is None:
                raise OlympusContextError(
                    "olympus_authority_verification_unavailable",
                    "worker termination requires an active exact permit",
                )
            cur = conn.execute(
                "UPDATE task_runs SET process_state = 'termination_pending', "
                "status = ?, outcome = ?, error = ?, ended_at = ?, "
                "claim_lock = NULL, claim_expires = NULL WHERE id = ? "
                "AND process_state = 'registered'",
                (outcome, outcome, str(reason)[:2000], now, int(run_id)),
            )
            if cur.rowcount != 1:
                raise OlympusContextError(
                    "worker_termination_race", "worker run changed before containment",
                )
            conn.execute(
                "UPDATE tasks SET status = 'blocked', claim_lock = NULL, "
                "claim_expires = NULL, worker_pid = NULL, current_run_id = NULL "
                "WHERE id = ? AND current_run_id = ?",
                (task_id, int(run_id)),
            )
            post = conn.execute(
                "SELECT record_revision FROM tasks WHERE id = ?", (task_id,),
            ).fetchone()
            effect = conn.execute(
                "INSERT INTO kanban_effect_journal ("
                "effect_kind, operation_id, task_id, run_id, auth_root_id, "
                "auth_root_revision, target_pre_revision, target_post_revision, "
                "worker_host_id, worker_boot_id, worker_pid, worker_start_token, "
                "source_identity, payload, payload_sha256, state, created_at, updated_at"
                ") VALUES ('terminate_worker', ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, "
                "'pending', ?, ?)",
                (
                    operation_id, task_id, int(run_id), permit["auth_root_id"],
                    permit["auth_root_revision"], permit["subject_revision"],
                    int(post["record_revision"]), stored.host_id, stored.boot_id,
                    stored.pid, stored.start_token, source, payload, digest, now, now,
                ),
            )
            _append_event(
                conn,
                task_id,
                event_kind,
                {
                    **effect_payload,
                    "effect_id": int(effect.lastrowid),
                    "worker_pid": stored.pid,
                    "process_identity": "exact",
                },
                run_id=int(run_id),
            )
    effect_id = int(effect.lastrowid)
    failpoint = _OLYMPUS_EFFECT_EXECUTION_FAILPOINT
    if callable(failpoint):
        failpoint("after_stage")
    return effect_id


def execute_worker_termination_effect(
    conn: sqlite3.Connection,
    effect_id: int,
    *,
    olympus_auth: Optional[OlympusMutationAuth] = None,
    signal_fn=None,
) -> str:
    """Apply one termination effect exactly once; never signal by PID alone."""
    import signal

    with write_txn(conn):
        row = conn.execute(
            "SELECT * FROM kanban_effect_journal WHERE id = ? "
            "AND effect_kind = 'terminate_worker'",
            (int(effect_id),),
        ).fetchone()
        if row is None:
            raise KeyError(effect_id)
        if row["state"] != "pending":
            return str(row["state"])
        task_id = str(row["task_id"])
        with _task_mutation_permit(
            conn,
            task_id,
            action="execute_worker_termination_effect",
            capability=OLYMPUS_CAPABILITY_RECOVER,
            auth=olympus_auth,
        ):
            cur = conn.execute(
                "UPDATE kanban_effect_journal SET state = 'applying', updated_at = ? "
                "WHERE id = ? AND state = 'pending'",
                (int(time.time()), int(effect_id)),
            )
            if cur.rowcount != 1:
                return "unknown"
    failpoint = _OLYMPUS_EFFECT_EXECUTION_FAILPOINT
    if callable(failpoint):
        failpoint("after_claim")
    target = ProcessIdentity(
        host_id=str(row["worker_host_id"]),
        boot_id=str(row["worker_boot_id"]),
        pid=int(row["worker_pid"]),
        start_token=str(row["worker_start_token"]),
    )
    live = read_process_identity(target.pid)
    state = "identity_mismatch"
    error = None
    if live is None:
        state = "identity_unverified" if _pid_alive(target.pid) else "gone"
    elif live == target:
        try:
            (signal_fn or os.kill)(target.pid, signal.SIGTERM)
            state = "applied"
        except ProcessLookupError:
            state = "gone"
        except Exception as exc:
            state = "failed"
            error = type(exc).__name__
    failpoint = _OLYMPUS_EFFECT_EXECUTION_FAILPOINT
    if callable(failpoint):
        failpoint("after_execute")
    with write_txn(conn):
        with _task_mutation_permit(
            conn,
            task_id,
            action="execute_worker_termination_effect",
            capability=OLYMPUS_CAPABILITY_RECOVER,
            auth=olympus_auth,
        ):
            conn.execute(
                "UPDATE kanban_effect_journal SET state = ?, error = ?, "
                "updated_at = ?, applied_at = ? WHERE id = ? AND state = 'applying'",
                (state, error, int(time.time()), int(time.time()), int(effect_id)),
            )
            conn.execute(
                "UPDATE task_runs SET process_state = ? WHERE id = ? "
                "AND process_state = 'termination_pending'",
                (
                    "terminal" if state == "gone"
                    else "termination_sent" if state == "applied"
                    else "identity_unverified",
                    row["run_id"],
                ),
            )
    failpoint = _OLYMPUS_EFFECT_EXECUTION_FAILPOINT
    if callable(failpoint):
        failpoint("after_settle")
    return state


def confirm_applied_worker_termination_effects(
    conn: sqlite3.Connection,
    *,
    olympus_auth: Optional[OlympusMutationAuth] = None,
) -> int:
    """Confirm exact process exit after a previously applied SIGTERM.

    ``applied`` proves only that the signal call succeeded.  It is not exit
    evidence and therefore cannot authorize running-cancel archival.  A later
    dispatcher tick compares the current process birth identity with the
    journaled exact target and advances only to ``gone`` (verified absent) or
    ``identity_mismatch`` (PID now belongs to another process).
    """
    rows = conn.execute(
        "SELECT * FROM kanban_effect_journal "
        "WHERE effect_kind='terminate_worker' AND state='applied' "
        "ORDER BY id"
    ).fetchall()
    changed = 0
    for row in rows:
        target = ProcessIdentity(
            host_id=str(row["worker_host_id"] or ""),
            boot_id=str(row["worker_boot_id"] or ""),
            pid=int(row["worker_pid"] or 0),
            start_token=str(row["worker_start_token"] or ""),
        )
        live = read_process_identity(target.pid)
        new_state = None
        if live is None and not _pid_alive(target.pid):
            new_state = "gone"
        elif live is not None and live != target:
            new_state = "identity_mismatch"
        if new_state is None:
            continue
        try:
            with write_txn(conn):
                with _task_mutation_permit(
                    conn,
                    str(row["task_id"]),
                    action="settle_worker_termination",
                    capability=OLYMPUS_CAPABILITY_RECOVER,
                    auth=olympus_auth,
                ):
                    cur = conn.execute(
                        "UPDATE kanban_effect_journal SET state=?, updated_at=? "
                        "WHERE id=? AND state='applied'",
                        (new_state, int(time.time()), int(row["id"])),
                    )
                    if cur.rowcount:
                        conn.execute(
                            "UPDATE task_runs SET process_state=? WHERE id=? "
                            "AND process_state IN "
                            "('termination_pending','termination_sent','terminal')",
                            (
                                "terminal" if new_state == "gone"
                                else "identity_unverified",
                                int(row["run_id"]),
                            ),
                        )
                        changed += 1
        except OlympusContextError:
            continue
    return changed


def process_pending_worker_termination_effects(
    conn: sqlite3.Connection,
    *,
    olympus_auth: Optional[OlympusMutationAuth] = None,
    signal_fn=None,
) -> dict[str, int]:
    """Dispatcher-owned executor for pending exact worker effects.

    Telegram never calls this function and never owns a PID.  The production
    dispatcher invokes it on every board tick/restart using its canonical
    service principal.  Each pending row is independently claimed by the #16
    effect CAS, rechecks the registered process birth identity, and signals at
    most once.  Applied signals are then checked for verified exit.
    """
    pending = conn.execute(
        "SELECT id FROM kanban_effect_journal "
        "WHERE effect_kind='terminate_worker' AND state='pending' ORDER BY id"
    ).fetchall()
    executed = 0
    for row in pending:
        try:
            state = execute_worker_termination_effect(
                conn,
                int(row["id"]),
                olympus_auth=olympus_auth,
                signal_fn=signal_fn,
            )
        except (KeyError, OlympusContextError):
            continue
        if state != "pending":
            executed += 1
    confirmed = confirm_applied_worker_termination_effects(
        conn, olympus_auth=olympus_auth
    )
    return {"executed": executed, "confirmed": confirmed}


def _stage_execute_governed_recovery(
    conn: sqlite3.Connection,
    *,
    task_id: str,
    run_id: int,
    reason: str,
    outcome: str,
    event_kind: str,
    olympus_auth: Optional[OlympusMutationAuth],
    signal_fn=None,
) -> Optional[str]:
    """Stage, externally reverify/apply, and settle one governed recovery.

    No signal is emitted from the transaction that contains the task/run
    transition. The durable effect carries the exact registered host, boot,
    PID and native process-birth token; execution re-reads that live identity
    after the staging transaction commits, and settlement performs a second
    canonical authority verification in a new transaction.
    """
    row = conn.execute(
        "SELECT t.status, t.current_run_id, t.olympus_context, "
        "r.launch_token, r.process_state, r.worker_host_id, r.worker_boot_id, "
        "r.worker_pid, r.worker_start_token "
        "FROM tasks t JOIN task_runs r ON r.id = t.current_run_id "
        "WHERE t.id = ? AND r.id = ?",
        (task_id, int(run_id)),
    ).fetchone()
    if (
        row is None
        or row["olympus_context"] is None
        or row["status"] != "running"
        or int(row["current_run_id"] or 0) != int(run_id)
        or row["process_state"] != "registered"
        or not row["launch_token"]
    ):
        return None
    identity = ProcessIdentity(
        host_id=str(row["worker_host_id"] or ""),
        boot_id=str(row["worker_boot_id"] or ""),
        pid=int(row["worker_pid"] or 0),
        start_token=str(row["worker_start_token"] or ""),
    )
    if not all((identity.host_id, identity.boot_id, identity.start_token)) \
            or identity.pid <= 0:
        return None
    token_digest = hashlib.sha256(
        str(row["launch_token"]).encode("utf-8")
    ).hexdigest()
    operation_id = (
        f"worker-recovery:{event_kind}:{task_id}:{int(run_id)}:{token_digest}"
    )
    source_identity = {
        "principal_type": (
            olympus_auth.principal_type if olympus_auth is not None else ""
        ),
        "principal_id": (
            olympus_auth.principal_id if olympus_auth is not None else ""
        ),
        "principal_source": (
            olympus_auth.principal_source if olympus_auth is not None else ""
        ),
    }
    effect_id = stage_worker_termination(
        conn,
        task_id=task_id,
        run_id=int(run_id),
        launch_token=str(row["launch_token"]),
        process_identity=identity,
        operation_id=operation_id,
        reason=reason,
        source_identity=source_identity,
        outcome=outcome,
        event_kind=event_kind,
        olympus_auth=olympus_auth,
    )
    return execute_worker_termination_effect(
        conn,
        effect_id,
        olympus_auth=olympus_auth,
        signal_fn=signal_fn,
    )


def reconcile_worker_runs(
    conn: sqlite3.Connection,
    *,
    olympus_auth: Optional[OlympusMutationAuth] = None,
) -> int:
    """Fail closed on unfinished launches or stale registered identities."""
    rows = conn.execute(
        "SELECT r.id, r.task_id, r.process_state, r.worker_pid, r.worker_host_id, "
        "r.worker_boot_id, r.worker_start_token FROM task_runs r "
        "JOIN tasks t ON t.id = r.task_id WHERE r.ended_at IS NULL "
        "AND r.process_state IN ('starting','registered')",
    ).fetchall()
    changed = 0
    for row in rows:
        live = read_process_identity(int(row["worker_pid"] or 0))
        stored = ProcessIdentity(
            host_id=str(row["worker_host_id"] or ""),
            boot_id=str(row["worker_boot_id"] or ""),
            pid=int(row["worker_pid"] or 0),
            start_token=str(row["worker_start_token"] or ""),
        )
        if row["process_state"] == "registered" and live == stored:
            continue
        try:
            with write_txn(conn):
                with _task_mutation_permit(
                    conn,
                    str(row["task_id"]),
                    action="reconcile_worker_run",
                    capability=OLYMPUS_CAPABILITY_RECOVER,
                    auth=olympus_auth,
                ):
                    cur = conn.execute(
                        "UPDATE task_runs SET process_state = 'identity_unverified' "
                        "WHERE id = ? AND process_state = ?",
                        (int(row["id"]), row["process_state"]),
                    )
                    if cur.rowcount:
                        conn.execute(
                            "UPDATE tasks SET status = 'blocked', claim_lock = NULL, "
                            "claim_expires = NULL, worker_pid = NULL, current_run_id = NULL "
                            "WHERE id = ? AND current_run_id = ?",
                            (row["task_id"], row["id"]),
                        )
                        changed += 1
        except OlympusContextError:
            continue
    return changed


def heartbeat_claim(
    conn: sqlite3.Connection,
    task_id: str,
    *,
    ttl_seconds: Optional[int] = None,
    claimer: Optional[str] = None,
    olympus_auth: Optional[OlympusMutationAuth] = None,
) -> bool:
    """Extend a running claim.  Returns True if we still own it.

    Workers that know they'll exceed 15 minutes should call this every
    few minutes to keep ownership.
    """
    now = int(time.time())
    expires = now + _resolve_claim_ttl_seconds(ttl_seconds)
    lock = claimer or _claimer_id()
    with write_txn(conn):
        gate_row = conn.execute(
            "SELECT assignee, claim_expires, current_run_id, olympus_context, "
            "record_revision "
            "FROM tasks "
            "WHERE id = ? AND status = 'running' AND claim_lock = ?",
            (task_id, lock),
        ).fetchone()
        if gate_row is None:
            return False
        try:
            olympus = _require_current_olympus_context(
                gate_row["olympus_context"],
                assignee=gate_row["assignee"],
                now=now,
            )
            if olympus is not None:
                _authorize_task_mutation(
                    conn,
                    task_id,
                    action="heartbeat",
                    capability=OLYMPUS_CAPABILITY_HEARTBEAT,
                    auth=olympus_auth,
                )
            if (
                olympus is not None
                and (
                    gate_row["claim_expires"] is None
                    or int(gate_row["claim_expires"]) <= now
                )
            ):
                raise OlympusContextError(
                    "olympus_claim_expired",
                    "a governed claim cannot be renewed after it expires",
                )
            run_olympus = None
            if olympus is not None and gate_row["current_run_id"] is None:
                raise OlympusContextError(
                    "olympus_run_context_mismatch",
                    "governed running task has no active run",
                )
            if gate_row["current_run_id"] is not None:
                run_row = conn.execute(
                    "SELECT olympus_context, subject_revision FROM task_runs WHERE id = ?",
                    (int(gate_row["current_run_id"]),),
                ).fetchone()
                if run_row is None:
                    raise OlympusContextError(
                        "olympus_run_context_mismatch",
                        "active task has no matching run",
                    )
                run_olympus = _require_matching_olympus_run_context(
                    run_row["olympus_context"],
                    task_context=olympus,
                    assignee=gate_row["assignee"],
                    now=now,
                    run_subject_revision=run_row["subject_revision"],
                    task_record_revision=int(gate_row["record_revision"]),
                )
        except OlympusContextError as exc:
            _append_event(
                conn,
                task_id,
                "heartbeat_rejected",
                {"reason": exc.reason, "governance": "olympus"},
                run_id=_current_run_id(conn, task_id),
            )
            return False
        if olympus is not None:
            expires = min(expires, int(olympus["lease"]["expires_at"]))
        if run_olympus is not None:
            expires = min(expires, int(run_olympus["lease"]["expires_at"]))
        cur = conn.execute(
            "UPDATE tasks SET claim_expires = ? "
            "WHERE id = ? AND status = 'running' AND claim_lock = ?",
            (expires, task_id, lock),
        )
        if cur.rowcount == 1:
            run_id = _current_run_id(conn, task_id)
            if run_id is not None:
                conn.execute(
                    "UPDATE task_runs SET claim_expires = ? WHERE id = ?",
                    (expires, run_id),
                )
            return True
        return False


def release_stale_claims(
    conn: sqlite3.Connection,
    *,
    signal_fn=None,
    olympus_auth: Optional[OlympusMutationAuth] = None,
) -> int:
    """Reset any ``running`` task whose claim has expired.

    A stale-by-TTL claim whose host-local worker PID is still alive is
    *extended* (with a ``claim_extended`` event) instead of being
    reclaimed. Reclaiming a live worker mid-flight produces the spawn-
    then-immediately-reclaim loop seen on slow models that spend longer
    than ``DEFAULT_CLAIM_TTL_SECONDS`` inside a single tool-free LLM
    call (#23025): no tool calls means no ``kanban_heartbeat``, even
    though the subprocess is healthy.

    Backstop (#29747 gap 3): if the worker's PID is still alive but its
    ``last_heartbeat_at`` is stale by more than
    ``DEFAULT_CLAIM_HEARTBEAT_MAX_STALE_SECONDS`` (1h), the worker has
    been making no observable progress and we reclaim anyway — even if
    ``_pid_alive`` is still true. This catches the wedged-in-a-logic-loop
    case where the process is technically running but accomplishing
    nothing. ``_touch_activity`` (run_agent.py) bridges chunk-level
    liveness into ``last_heartbeat_at`` via #31752, so any genuinely
    active worker keeps its heartbeat fresh as a side effect of normal
    API traffic. ``enforce_max_runtime`` and ``detect_crashed_workers``
    remain the upper bounds for genuinely wedged or dead workers.

    Returns the number of stale claims actually reclaimed (live-pid
    extensions don't count). Safe to call often.
    """
    now = int(time.time())
    reclaimed = 0
    host_prefix = f"{_claimer_id().split(':', 1)[0]}:"
    stale = conn.execute(
        "SELECT t.id, t.assignee, t.claim_lock, t.worker_pid, t.claim_expires, "
        "t.last_heartbeat_at, t.current_run_id, t.olympus_context, "
        "t.record_revision, r.launch_token, r.process_state, "
        "r.worker_host_id, r.worker_boot_id, r.worker_start_token "
        "FROM tasks t LEFT JOIN task_runs r ON r.id = t.current_run_id "
        "WHERE t.status = 'running' AND t.claim_expires IS NOT NULL "
        "  AND t.claim_expires < ?",
        (now,),
    ).fetchall()
    for row in stale:
        lock = row["claim_lock"] or ""
        host_local = lock.startswith(host_prefix)
        hb = row["last_heartbeat_at"]
        # Heartbeat staleness backstop: if we have a heartbeat at all
        # and it's older than the max-stale threshold, the worker is
        # not making observable progress.  Reclaim instead of extending,
        # even if the PID is still alive (it's likely in a logic loop).
        heartbeat_stale = (
            hb is not None
            and (now - int(hb)) > DEFAULT_CLAIM_HEARTBEAT_MAX_STALE_SECONDS
        )
        olympus_current = True
        olympus: Optional[dict[str, Any]] = None
        run_olympus: Optional[dict[str, Any]] = None
        try:
            olympus = _require_current_olympus_context(
                row["olympus_context"], assignee=row["assignee"], now=now
            )
            if olympus is not None and row["current_run_id"] is None:
                raise OlympusContextError(
                    "olympus_run_context_mismatch",
                    "governed running task has no active run",
                )
            if row["current_run_id"] is not None:
                run_row = conn.execute(
                    "SELECT olympus_context, subject_revision FROM task_runs WHERE id = ?",
                    (int(row["current_run_id"]),),
                ).fetchone()
                if run_row is None:
                    raise OlympusContextError(
                        "olympus_run_context_mismatch",
                        "active task has no matching run",
                    )
                run_olympus = _require_matching_olympus_run_context(
                    run_row["olympus_context"],
                    task_context=olympus,
                    assignee=row["assignee"],
                    now=now,
                    run_subject_revision=run_row["subject_revision"],
                    task_record_revision=int(row["record_revision"]),
                )
        except OlympusContextError:
            olympus_current = False
        governed = row["olympus_context"] is not None
        registered_identity = None
        if governed and row["process_state"] == "registered":
            candidate = ProcessIdentity(
                host_id=str(row["worker_host_id"] or ""),
                boot_id=str(row["worker_boot_id"] or ""),
                pid=int(row["worker_pid"] or 0),
                start_token=str(row["worker_start_token"] or ""),
            )
            if all((candidate.host_id, candidate.boot_id, candidate.start_token)) \
                    and candidate.pid > 0:
                registered_identity = candidate
        live_identity = (
            read_process_identity(registered_identity.pid)
            if registered_identity is not None else None
        )
        if (
            host_local
            and row["worker_pid"]
            and (
                live_identity == registered_identity
                if governed else _pid_alive(row["worker_pid"])
            )
            and not heartbeat_stale
            and olympus_current
        ):
            new_expires = now + _resolve_claim_ttl_seconds()
            if olympus is not None:
                new_expires = min(
                    new_expires, int(olympus["lease"]["expires_at"])
                )
            if run_olympus is not None:
                new_expires = min(
                    new_expires, int(run_olympus["lease"]["expires_at"])
                )
            try:
                with write_txn(conn):
                    _authorize_task_mutation(
                        conn,
                        row["id"],
                        action="extend_stale_claim",
                        capability=OLYMPUS_CAPABILITY_RECOVER,
                        auth=olympus_auth,
                    )
                    cur = conn.execute(
                        "UPDATE tasks SET claim_expires = ? "
                        "WHERE id = ? AND status = 'running' "
                        "  AND claim_lock IS ? "
                        "  AND claim_expires IS NOT NULL "
                        "  AND claim_expires < ?",
                        (new_expires, row["id"], row["claim_lock"], now),
                    )
                    if cur.rowcount != 1:
                        continue
                    run_id = _current_run_id(conn, row["id"])
                    if run_id is not None:
                        conn.execute(
                            "UPDATE task_runs SET claim_expires = ? WHERE id = ?",
                            (new_expires, run_id),
                        )
                    _append_event(
                        conn, row["id"], "claim_extended",
                        {
                            "reason": "pid_alive",
                            "worker_pid": int(row["worker_pid"]),
                            "claim_lock": row["claim_lock"],
                            "claim_expires_was": int(row["claim_expires"]),
                            "claim_expires_now": new_expires,
                            "last_heartbeat_at": (
                                int(row["last_heartbeat_at"])
                                if row["last_heartbeat_at"] is not None
                                else None
                            ),
                        },
                        run_id=run_id,
                    )
            except OlympusContextError as exc:
                with write_txn(conn):
                    _append_event(
                        conn,
                        row["id"],
                        "authority_contained",
                        {"reason": exc.reason, "action": "extend_stale_claim"},
                        run_id=(int(row["current_run_id"]) if row["current_run_id"] else None),
                    )
                continue
            continue

        if governed:
            if not olympus_current or row["current_run_id"] is None:
                continue
            try:
                state = _stage_execute_governed_recovery(
                    conn,
                    task_id=str(row["id"]),
                    run_id=int(row["current_run_id"]),
                    reason=f"stale claim expired at {int(row['claim_expires'])}",
                    outcome="reclaimed",
                    event_kind="reclaimed",
                    olympus_auth=olympus_auth,
                    signal_fn=signal_fn,
                )
            except OlympusContextError:
                state = None
            if state is not None:
                reclaimed += 1
            continue

        try:
            with write_txn(conn):
                _authorize_task_mutation(
                    conn,
                    row["id"],
                    action="recover_stale_claim",
                    capability=OLYMPUS_CAPABILITY_RECOVER,
                    auth=olympus_auth,
                )
                current = conn.execute(
                    "SELECT status, claim_lock, worker_pid, current_run_id, "
                    "claim_expires, record_revision FROM tasks WHERE id = ?",
                    (row["id"],),
                ).fetchone()
                if current is None or any((
                    current["status"] != "running",
                    current["claim_lock"] != row["claim_lock"],
                    current["worker_pid"] != row["worker_pid"],
                    current["current_run_id"] != row["current_run_id"],
                    current["claim_expires"] != row["claim_expires"],
                    current["claim_expires"] is None,
                    current["claim_expires"] is not None
                    and int(current["claim_expires"]) >= now,
                )):
                    continue
                termination = _terminate_reclaimed_worker(
                    current["worker_pid"],
                    current["claim_lock"],
                    signal_fn=signal_fn,
                )
                cur = conn.execute(
                    "UPDATE tasks SET status = 'ready', claim_lock = NULL, "
                    "claim_expires = NULL, worker_pid = NULL "
                    "WHERE id = ? AND status = 'running' AND claim_lock IS ? "
                    "AND worker_pid IS ? AND current_run_id IS ? "
                    "AND record_revision = ? "
                    "AND claim_expires IS NOT NULL AND claim_expires < ?",
                    (
                        row["id"], row["claim_lock"], row["worker_pid"],
                        row["current_run_id"], int(current["record_revision"]), now,
                    ),
                )
                if cur.rowcount != 1:
                    continue
                run_id = _end_run(
                conn, row["id"],
                outcome="reclaimed", status="reclaimed",
                error=f"stale_lock={row['claim_lock']}",
                metadata=termination,
            )
                payload = {
                    "stale_lock": row["claim_lock"],
                    "worker_pid": (
                        int(row["worker_pid"])
                        if row["worker_pid"] is not None else None
                    ),
                    "claim_expires": int(row["claim_expires"]),
                    "last_heartbeat_at": (
                        int(row["last_heartbeat_at"])
                        if row["last_heartbeat_at"] is not None else None
                    ),
                    "now": now,
                    "host_local": host_local,
                    "heartbeat_stale": bool(heartbeat_stale),
                }
                payload.update(termination)
                _append_event(
                conn, row["id"], "reclaimed",
                payload,
                run_id=run_id,
            )
                reclaimed += 1
        except OlympusContextError as exc:
            with write_txn(conn):
                _append_event(
                    conn,
                    row["id"],
                    "authority_contained",
                    {"reason": exc.reason, "action": "recover_stale_claim"},
                    run_id=(int(row["current_run_id"]) if row["current_run_id"] else None),
                )
    return reclaimed


def reclaim_task(
    conn: sqlite3.Connection,
    task_id: str,
    *,
    reason: Optional[str] = None,
    signal_fn=None,
    olympus_auth: Optional[OlympusMutationAuth] = None,
) -> bool:
    """Operator-driven reclaim: release the claim and reset to ``ready``.

    Unlike :func:`release_stale_claims` which only acts on tasks whose
    ``claim_expires`` has passed, this function reclaims immediately
    regardless of TTL. Intended for the dashboard/CLI recovery flow
    when an operator wants to abort a running worker without waiting
    for the TTL to expire (e.g. after seeing a hallucination warning).

    Returns True if a reclaim happened, False if the task isn't in a
    reclaimable state (not running, or doesn't exist).
    """
    governed = conn.execute(
        "SELECT status, current_run_id, olympus_context FROM tasks WHERE id = ?",
        (task_id,),
    ).fetchone()
    if governed is not None and governed["olympus_context"] is not None:
        if governed["status"] != "running" or governed["current_run_id"] is None:
            return False
        try:
            state = _stage_execute_governed_recovery(
                conn,
                task_id=task_id,
                run_id=int(governed["current_run_id"]),
                reason=(
                    f"manual_reclaim: {reason}" if reason else "manual reclaim"
                ),
                outcome="reclaimed",
                event_kind="reclaimed",
                olympus_auth=olympus_auth,
                signal_fn=signal_fn,
            )
        except OlympusContextError:
            return False
        return state is not None
    with olympus_mutation_scope(olympus_auth), write_txn(conn):
        _authorize_task_mutation(
            conn,
            task_id,
            action="reclaim",
            capability=OLYMPUS_CAPABILITY_RECOVER,
            auth=olympus_auth,
        )
        row = conn.execute(
            "SELECT status, claim_lock, worker_pid, current_run_id, record_revision "
            "FROM tasks WHERE id = ?",
            (task_id,),
        ).fetchone()
        if not row:
            return False
        if row["status"] != "running" and row["claim_lock"] is None:
            return False
        prev_lock = row["claim_lock"]
        prev_pid = row["worker_pid"]
        cur = conn.execute(
            "UPDATE tasks SET status = 'ready', claim_lock = NULL, "
            "claim_expires = NULL, worker_pid = NULL, "
            "consecutive_failures = 0, last_failure_error = NULL "
            "WHERE id = ? AND status IN ('running', 'ready', 'blocked') "
            "AND claim_lock IS ? AND worker_pid IS ? AND current_run_id IS ? "
            "AND record_revision = ?",
            (
                task_id, prev_lock, prev_pid, row["current_run_id"],
                row["record_revision"],
            ),
        )
        if cur.rowcount != 1:
            return False
        run_id = _end_run(
            conn, task_id,
            outcome="reclaimed", status="reclaimed",
            error=(
                f"manual_reclaim: {reason}" if reason
                else f"manual_reclaim lock={prev_lock}"
            ),
            metadata={"termination_after_commit": True, "prev_pid": prev_pid},
        )
        payload = {
            "manual": True,
            "reason": reason,
            "prev_lock": prev_lock,
            "prev_pid": prev_pid,
            "termination_after_commit": True,
        }
        _append_event(
            conn, task_id, "reclaimed",
            payload,
            run_id=run_id,
        )
    # The state transition and termination intent are durable before the
    # irreversible process signal. A commit failure therefore sends nothing.
    _terminate_reclaimed_worker(
        prev_pid, prev_lock, signal_fn=signal_fn,
    )
    return True


def reassign_task(
    conn: sqlite3.Connection,
    task_id: str,
    profile: Optional[str],
    *,
    reclaim_first: bool = False,
    reason: Optional[str] = None,
    olympus_auth: Optional[OlympusMutationAuth] = None,
) -> bool:
    """Reassign a task, optionally reclaiming a stuck running worker first.

    This is the recovery path for "this profile's model is broken, try
    a different one". If ``reclaim_first`` is True, any active claim is
    released (via :func:`reclaim_task`) before the reassign happens;
    otherwise the function refuses to reassign a currently-running task
    and returns False (caller can retry with ``reclaim_first=True``).

    Returns True if the reassign landed. ``profile`` may be ``None`` to
    unassign entirely.
    """
    canonical_profile = _canonical_assignee(profile)
    row = conn.execute(
        "SELECT assignee, olympus_context FROM tasks WHERE id = ?", (task_id,),
    ).fetchone()
    if row is not None and row["olympus_context"] is not None:
        context = normalize_olympus_context(row["olympus_context"])
        lease = context["lease"]
        if not (
            canonical_profile
            == row["assignee"]
            == context["agent_id"]
            == lease["agent_id"]
            == lease["holder"]
        ):
            raise OlympusContextError(
                "olympus_reassignment_requires_rebind",
                "governed reassignment cannot reclaim before canonical rebind",
            )
    if reclaim_first:
        # Safe to call even if nothing to reclaim.
        reclaim_task(
            conn,
            task_id,
            reason=reason or "reassign",
            olympus_auth=olympus_auth,
        )
    # assign_task handles its own txn + the still-running guard.
    try:
        return assign_task(
            conn, task_id, canonical_profile, olympus_auth=olympus_auth,
        )
    except RuntimeError:
        # Task is still running and reclaim_first was False; caller
        # needs to decide whether to retry with reclaim.
        return False


def _verify_created_cards(
    conn: sqlite3.Connection,
    completing_task_id: str,
    claimed_ids: Iterable[str],
) -> tuple[list[str], list[str]]:
    """Partition ``claimed_ids`` into (verified, phantom).

    A card is "verified" iff a row exists in ``tasks`` AND at least one
    of the following holds:

    * ``created_by`` matches the completing task's ``assignee`` profile
      (the common case: worker A spawns a card via ``kanban_create``,
      which stamps ``created_by=A``).
    * ``created_by`` matches the completing task's id (edge case where
      a worker passed its own task id as the ``created_by`` value).
    * The card is linked as a ``task_links.child`` of the completing
      task — i.e. the worker explicitly called ``kanban_create`` with
      ``parents=[<current_task>]``. This accepts cards created through
      the dashboard/CLI by a different principal but then attached to
      the completing task by the worker.

    ``phantom`` returns ids that either don't exist at all, or exist
    but don't satisfy any of the three trust conditions. The caller
    decides what to do with each bucket; this helper never mutates.
    """
    claimed = [str(x).strip() for x in (claimed_ids or []) if str(x).strip()]
    if not claimed:
        return [], []
    # Dedupe while preserving order.
    seen: set[str] = set()
    ordered: list[str] = []
    for cid in claimed:
        if cid not in seen:
            seen.add(cid)
            ordered.append(cid)

    row = conn.execute(
        "SELECT assignee FROM tasks WHERE id = ?", (completing_task_id,),
    ).fetchone()
    if row is None:
        # Completing task not found — nothing resolves.
        return [], ordered
    completing_assignee = row["assignee"]

    # Batch-fetch existence + created_by in one query.
    placeholders = ",".join(["?"] * len(ordered))
    rows = conn.execute(
        f"SELECT id, created_by FROM tasks WHERE id IN ({placeholders})",
        tuple(ordered),
    ).fetchall()
    found = {r["id"]: r["created_by"] for r in rows}

    # Pull the set of cards linked as children of the completing task.
    # Cheap: one query, indexed on parent_id.
    linked_children: set[str] = set(child_ids(conn, completing_task_id))

    verified: list[str] = []
    phantom: list[str] = []
    for cid in ordered:
        created_by = found.get(cid)
        if created_by is None:
            phantom.append(cid)
            continue
        # Accept if any of the three trust conditions holds.
        if completing_assignee and created_by == completing_assignee:
            verified.append(cid)
        elif created_by == completing_task_id:
            verified.append(cid)
        elif cid in linked_children:
            verified.append(cid)
        else:
            phantom.append(cid)
    return verified, phantom


# Task-id pattern used both by ``kanban_create`` (``t_<12 hex>``) and
# ``_new_task_id`` below. Kept permissive on length for forward compat:
# accept 8+ hex chars after the ``t_`` prefix.
_TASK_ID_PROSE_RE = re.compile(r"\bt_[a-f0-9]{8,}\b")


def _scan_prose_for_phantom_ids(
    conn: sqlite3.Connection,
    text: str,
) -> list[str]:
    """Regex-scan free-form text for ``t_<hex>`` references; return the
    ones that don't exist in ``tasks``.

    Used as a non-blocking advisory check on completion summaries. An
    empty return means "no suspicious references found" — either the
    text had no IDs at all, or every ID it mentioned resolves to a real
    task. Duplicates are deduped.
    """
    if not text:
        return []
    matches = _TASK_ID_PROSE_RE.findall(text)
    if not matches:
        return []
    # Dedupe preserving order.
    seen: set[str] = set()
    unique: list[str] = []
    for m in matches:
        if m not in seen:
            seen.add(m)
            unique.append(m)
    placeholders = ",".join(["?"] * len(unique))
    rows = conn.execute(
        f"SELECT id FROM tasks WHERE id IN ({placeholders})",
        tuple(unique),
    ).fetchall()
    existing = {r["id"] for r in rows}
    return [m for m in unique if m not in existing]


class HallucinatedCardsError(ValueError):
    """Raised by ``complete_task`` when ``created_cards`` contains ids
    that don't exist or weren't created by the completing worker.

    The phantom list is attached as ``.phantom`` for callers that want
    structured access. Kept as ``ValueError`` subclass so existing
    tool-error handlers treat it as a recoverable user error.
    """

    def __init__(self, phantom: list[str], completing_task_id: str):
        self.phantom = list(phantom)
        self.completing_task_id = completing_task_id
        super().__init__(
            f"completion blocked: claimed created_cards that do not exist "
            f"or were not created by this worker: {', '.join(phantom)}"
        )


def complete_task(
    conn: sqlite3.Connection,
    task_id: str,
    *,
    result: Optional[str] = None,
    summary: Optional[str] = None,
    metadata: Optional[dict] = None,
    created_cards: Optional[Iterable[str]] = None,
    expected_run_id: Optional[int] = None,
    olympus_auth: Optional[OlympusMutationAuth] = None,
) -> bool:
    """Transition ``running|ready -> done`` and record ``result``.

    Ordinary Kanban tasks may be merely ``ready`` so the manual CLI completion
    path remains compatible. Olympus-governed tasks must be running under a
    current authority/lease and an attributable active run; direct completion
    can never bypass the claim/start gate.

    ``summary`` and ``metadata`` are stored on the closing run (if any)
    and surfaced to downstream children via :func:`build_worker_context`.
    When ``summary`` is omitted we fall back to ``result`` so single-run
    callers do not have to pass both. ``metadata`` is a free-form dict
    (e.g. ``{"changed_files": [...], "tests_run": [...]}``) — workers
    are encouraged to use it for structured handoff facts.

    ``created_cards`` is an optional list of task ids the completing
    worker claims to have created. Each id is verified against
    ``tasks.created_by``. If any id is phantom (does not exist or was
    not created by this worker's assignee profile), completion is blocked
    with a ``HallucinatedCardsError`` and a
    ``completion_blocked_hallucination`` event is emitted so the rejected
    attempt is auditable. When all ids verify, they are recorded on the
    ``completed`` event payload.

    After a successful completion, ``summary`` and ``result`` are scanned
    for prose references like ``t_deadbeefcafe`` that do not resolve.
    Any suspected phantom references are recorded as a
    ``suspected_hallucinated_references`` event. This pass is advisory
    and never blocks.
    """
    now = int(time.time())

    # Gate: verify created_cards BEFORE the main write txn. A rejected
    # completion still needs an auditable event, so we emit it in a
    # tiny dedicated txn, then raise. The caller is responsible for
    # surfacing HallucinatedCardsError to the worker; this function
    # never mutates task state on a phantom-card rejection.
    if created_cards:
        verified_cards, phantom_cards = _verify_created_cards(
            conn, task_id, created_cards
        )
        if phantom_cards:
            with write_txn(conn):
                _append_event(
                    conn, task_id, "completion_blocked_hallucination",
                    {
                        "phantom_cards": phantom_cards,
                        "verified_cards": verified_cards,
                        "summary_preview": (
                            (summary or result or "").strip().splitlines()[0][:200]
                            if (summary or result)
                            else None
                        ),
                    },
                )
            raise HallucinatedCardsError(phantom_cards, task_id)
    else:
        verified_cards = []

    with write_txn(conn):
        task_row = conn.execute(
            "SELECT status, assignee, claim_expires, current_run_id, "
            "olympus_context, record_revision "
            "FROM tasks WHERE id = ?",
            (task_id,),
        ).fetchone()
        if task_row is None:
            return False
        olympus: Optional[dict[str, Any]] = None
        if task_row["olympus_context"] is not None:
            try:
                olympus = _require_current_olympus_context(
                    task_row["olympus_context"],
                    assignee=task_row["assignee"],
                    now=now,
                )
                _authorize_task_mutation(
                    conn,
                    task_id,
                    action="complete",
                    capability=OLYMPUS_CAPABILITY_COMPLETE,
                    auth=olympus_auth,
                )
                if task_row["status"] != "running" or task_row["current_run_id"] is None:
                    raise OlympusContextError(
                        "olympus_completion_without_active_run",
                        "governed completion requires an active claimed run",
                    )
                if (
                    task_row["claim_expires"] is None
                    or int(task_row["claim_expires"]) <= now
                ):
                    raise OlympusContextError(
                        "olympus_claim_expired",
                        "governed completion requires an unexpired claim",
                    )
                run_row = conn.execute(
                    "SELECT olympus_context, subject_revision, ended_at "
                    "FROM task_runs WHERE id = ?",
                    (int(task_row["current_run_id"]),),
                ).fetchone()
                if run_row is None or run_row["ended_at"] is not None:
                    raise OlympusContextError(
                        "olympus_run_context_mismatch",
                        "active run does not carry the task authority snapshot",
                    )
                run_olympus = _require_matching_olympus_run_context(
                    run_row["olympus_context"],
                    task_context=olympus,
                    assignee=task_row["assignee"],
                    now=now,
                    run_subject_revision=run_row["subject_revision"],
                    task_record_revision=int(task_row["record_revision"]),
                )
                if run_olympus is None:
                    raise OlympusContextError(
                        "olympus_run_context_mismatch",
                        "governed task has no governed run context",
                    )
            except OlympusContextError as exc:
                _append_event(
                    conn,
                    task_id,
                    "completion_rejected",
                    {"reason": exc.reason, "governance": "olympus"},
                    run_id=(
                        int(task_row["current_run_id"])
                        if task_row["current_run_id"] is not None else None
                    ),
                )
                return False
        if expected_run_id is None:
            cur = conn.execute(
                """
                UPDATE tasks
                   SET status       = 'done',
                       result       = ?,
                       completed_at = ?,
                       claim_lock   = NULL,
                       claim_expires= NULL,
                       worker_pid   = NULL
                 WHERE id = ?
                   AND status IN ('running', 'ready', 'blocked')
                """,
                (result, now, task_id),
            )
        else:
            cur = conn.execute(
                """
                UPDATE tasks
                   SET status       = 'done',
                       result       = ?,
                       completed_at = ?,
                       claim_lock   = NULL,
                       claim_expires= NULL,
                       worker_pid   = NULL
                 WHERE id = ?
                   AND status IN ('running', 'ready', 'blocked')
                   AND current_run_id = ?
                """,
                (result, now, task_id, int(expected_run_id)),
            )
        if cur.rowcount != 1:
            return False
        run_id = _end_run(
            conn, task_id,
            outcome="completed", status="done",
            summary=summary if summary is not None else result,
            metadata=metadata,
        )
        # If complete_task was called on a never-claimed task (ready or
        # blocked → done with no run in flight), synthesize a
        # zero-duration run so the handoff fields are persisted in
        # attempt history instead of silently lost.
        if run_id is None and (summary or metadata or result):
            run_id = _synthesize_ended_run(
                conn, task_id,
                outcome="completed",
                summary=summary if summary is not None else result,
                metadata=metadata,
            )
        # Carry the handoff summary in the event payload so gateway
        # notifiers and dashboard WS consumers can render it without a
        # second SQL round-trip. First line only, 400 char cap — the
        # full summary stays on the run row.
        ev_summary = (summary if summary is not None else result) or ""
        ev_summary = ev_summary.strip().splitlines()[0][:400] if ev_summary else ""
        completed_payload: dict = {
            "result_len": len(result) if result else 0,
            "summary": ev_summary or None,
        }
        if olympus is not None:
            completed_payload["olympus"] = _olympus_trace(olympus)
        if verified_cards:
            completed_payload["verified_cards"] = verified_cards
        # Carry artifact paths in the event payload so the gateway
        # notifier can upload them as native attachments alongside the
        # completion message. Workers pass these via
        # ``kanban_complete(artifacts=[...])`` which stashes the list in
        # ``metadata["artifacts"]`` — we promote it onto the event so
        # consumers don't have to fetch the run row to find it.
        if isinstance(metadata, dict):
            md_artifacts = metadata.get("artifacts")
            if isinstance(md_artifacts, (list, tuple)):
                cleaned_artifacts = [
                    str(p).strip() for p in md_artifacts if isinstance(p, str) and str(p).strip()
                ]
                if cleaned_artifacts:
                    completed_payload["artifacts"] = cleaned_artifacts
        _append_event(
            conn, task_id, "completed",
            completed_payload,
            run_id=run_id,
        )
        # Keep advisory audit and counter reset in the same authorized
        # completion transaction. No governed write is attempted after its
        # exact permit has committed and been cleared.
        scan_text = " ".join(filter(None, [summary, result]))
        if scan_text:
            phantom_refs = _scan_prose_for_phantom_ids(conn, scan_text)
            phantom_refs = [p for p in phantom_refs if p not in set(verified_cards)]
            if phantom_refs:
                _append_event(
                    conn, task_id, "suspected_hallucinated_references",
                    {
                        "phantom_refs": phantom_refs,
                        "source": "completion_summary",
                    },
                    run_id=run_id,
                )
        conn.execute(
            "UPDATE tasks SET consecutive_failures = 0, "
            "last_failure_error = NULL WHERE id = ?",
            (task_id,),
        )
    # Recompute ready status for dependents (separate txn so children see done).
    recompute_ready(conn, olympus_auth=olympus_auth)
    # Clean up the scratch workspace and any stale tmux session for the worker.
    _cleanup_workspace(conn, task_id)
    return True


# ---------------------------------------------------------------------------
# Workspace / tmux cleanup
# ---------------------------------------------------------------------------

def _is_managed_scratch_path(p: Path) -> bool:
    """Return True iff *p* is a strict descendant of a kanban-managed scratch root.

    A managed root is exclusively a ``workspaces/`` directory — never the
    broader kanban home, a board root, or sibling subtrees like ``logs/`` or
    ``boards/<slug>/`` itself. Allowed roots:

    * ``HERMES_KANBAN_WORKSPACES_ROOT`` when set (worker-side override
      injected by the dispatcher).
    * ``<kanban_home>/kanban/workspaces`` — legacy default-board scratch root.
    * ``<kanban_home>/kanban/boards/<slug>/workspaces`` for each board slug
      that currently exists on disk.

    The check requires strict descendancy: a path equal to one of these
    roots is NOT managed (deleting the workspaces root would wipe every
    task's scratch dir at once), and a path that resolves to ``<kanban_home>
    /kanban`` itself, ``<kanban_home>/kanban/logs``, or
    ``<kanban_home>/kanban/boards/<slug>`` is rejected because those
    subtrees hold Hermes' own DB, metadata, and logs, not task workspaces.

    Used by :func:`_cleanup_workspace` to refuse to ``shutil.rmtree`` paths
    outside Hermes-managed storage. A board ``default_workdir`` pointing at a
    real source tree can otherwise pair with ``workspace_kind='scratch'`` and
    cause task completion to delete user data (#28818).
    """
    try:
        p_abs = p.resolve(strict=False)
    except OSError:
        return False
    roots: list[Path] = []
    override = os.environ.get("HERMES_KANBAN_WORKSPACES_ROOT", "").strip()
    if override:
        try:
            roots.append(Path(override).expanduser().resolve(strict=False))
        except OSError:
            pass
    try:
        home = kanban_home()
    except OSError:
        home = None
    if home is not None:
        try:
            roots.append((home / "kanban" / "workspaces").resolve(strict=False))
        except OSError:
            pass
        try:
            boards_parent = (home / "kanban" / "boards").resolve(strict=False)
        except OSError:
            boards_parent = None
        if boards_parent is not None:
            try:
                entries = list(boards_parent.iterdir())
            except OSError:
                entries = []
            for entry in entries:
                try:
                    if not entry.is_dir():
                        continue
                except OSError:
                    continue
                try:
                    roots.append((entry / "workspaces").resolve(strict=False))
                except OSError:
                    continue
    for root in roots:
        if p_abs == root:
            continue
        try:
            if p_abs.is_relative_to(root):
                return True
        except ValueError:
            continue
    return False


def _cleanup_workspace(conn: sqlite3.Connection, task_id: str) -> None:
    """Remove a task's scratch workspace dir and kill its stale tmux session.

    Called from :func:`complete_task` after the DB transaction commits.
    Best-effort — any error is swallowed so cleanup never blocks task completion.
    Only ``scratch`` workspaces are removed; ``worktree`` and ``dir`` workspaces
    are intentionally preserved.
    """
    try:
        row = conn.execute(
            "SELECT workspace_kind, workspace_path FROM tasks WHERE id = ?",
            (task_id,),
        ).fetchone()
        if not row:
            return
        kind: Optional[str] = row["workspace_kind"]
        path: Optional[str] = row["workspace_path"]
        if kind != "scratch" or not path:
            # This task's own workspace isn't a removable scratch dir, but its
            # completion may still unblock a deferred parent scratch cleanup
            # (e.g. a 'dir' child whose scratch parent was waiting on it). #33774
            _try_cleanup_parent_workspaces(conn, task_id)
            return
        # Check if this task has children that still need the workspace.
        # If any child is not yet done/archived, defer cleanup so the
        # child can read handoff artifacts from the scratch dir (#33774).
        _active_children = conn.execute(
            "SELECT 1 FROM task_links l "
            "JOIN tasks t ON t.id = l.child_id "
            "WHERE l.parent_id = ? AND t.status NOT IN ('done', 'archived', 'failed', 'cancelled') "
            "LIMIT 1",
            (task_id,),
        ).fetchone()
        if _active_children:
            _log.debug(
                "Deferring scratch workspace cleanup for task %s: "
                "active children still need workspace at %s",
                task_id, path,
            )
            return
        import shutil
        wp = Path(path)
        if wp.is_dir():
            # Containment guard (#28818): a board's ``default_workdir`` can
            # pair ``workspace_kind='scratch'`` with a user-supplied path
            # pointing at a real source tree. Without this check, task
            # completion would unconditionally ``shutil.rmtree`` that path
            # and silently delete the user's source data.
            if _is_managed_scratch_path(wp):
                shutil.rmtree(wp, ignore_errors=True)
                _log.debug("Removed scratch workspace: %s", wp)
            else:
                _log.warning(
                    "Refusing to remove out-of-scratch workspace for task %s: %s "
                    "(workspace_kind='scratch' but path is outside any "
                    "kanban-managed workspaces root)",
                    task_id, wp,
                )
        # Also kill the tmux session for the worker that owned this task,
        # if the tmux session is now dead (worker process exited).
        _cleanup_worker_tmux(conn, task_id)
        # After cleaning up this task's workspace, check if any parent
        # tasks now have all children done — their deferred cleanup can
        # proceed (#33774).
        _try_cleanup_parent_workspaces(conn, task_id)
    except Exception:
        pass  # best-effort — never block completion


def _try_cleanup_parent_workspaces(conn: sqlite3.Connection, task_id: str) -> None:
    """Clean up parent scratch workspaces now that *task_id* completed.

    When a parent task's cleanup was deferred because it had active children,
    this function is called after each child completes.  If all children of a
    parent are now done/archived/failed/cancelled, the parent's scratch
    workspace is removed (#33774).
    """
    try:
        parents = conn.execute(
            "SELECT parent_id FROM task_links WHERE child_id = ?",
            (task_id,),
        ).fetchall()
        for (parent_id,) in parents:
            row = conn.execute(
                "SELECT workspace_kind, workspace_path FROM tasks WHERE id = ?",
                (parent_id,),
            ).fetchone()
            if not row or row["workspace_kind"] != "scratch" or not row["workspace_path"]:
                continue
            # Check if ALL children of this parent are terminal
            active = conn.execute(
                "SELECT 1 FROM task_links l "
                "JOIN tasks t ON t.id = l.child_id "
                "WHERE l.parent_id = ? AND t.status NOT IN ('done', 'archived', 'failed', 'cancelled') "
                "LIMIT 1",
                (parent_id,),
            ).fetchone()
            if active:
                continue  # still has active children
            # All children done — safe to clean up parent workspace
            import shutil
            wp = Path(row["workspace_path"])
            if wp.is_dir() and _is_managed_scratch_path(wp):
                shutil.rmtree(wp, ignore_errors=True)
                _log.debug("Deferred cleanup: removed parent %s scratch workspace: %s", parent_id, wp)
    except Exception:
        pass  # best-effort


def _cleanup_worker_tmux(conn: sqlite3.Connection, task_id: str) -> None:
    """Kill the tmux session associated with a task's assignee, if dead."""
    try:
        row = conn.execute(
            "SELECT assignee FROM tasks WHERE id = ?", (task_id,)
        ).fetchone()
        if not row or not row["assignee"]:
            return
        assignee: str = row["assignee"]
        # Workers named swarm1-12 use tmux sessions named swarm-swarm1 etc.
        session = f"swarm-{assignee}"
        # Check if session exists and pane is dead before killing
        out = subprocess.run(
            ["tmux", "list-panes", "-t", session, "-F", "#{pane_dead}"],
            capture_output=True, text=True, timeout=5,
        )
        if out.stdout.strip() == "1":
            subprocess.run(
                ["tmux", "kill-session", "-t", session],
                capture_output=True, timeout=5,
            )
            _log.debug("Killed stale tmux session: %s", session)
    except Exception:
        pass  # best-effort — never block completion


# ---------------------------------------------------------------------------
# First-use tip for scratch workspaces
# ---------------------------------------------------------------------------
#
# Scratch workspaces are intentionally ephemeral — ``_cleanup_workspace``
# removes them as soon as ``complete_task`` runs.  New users often don't
# realize that and lose worker output (community report, May 2026).  The
# behavior is right; the lack of warning is the bug.
#
# On the FIRST scratch workspace materialization across the whole install
# we:
#   1. Log a warning line on the dispatcher logger.
#   2. Append a ``tip_scratch_workspace`` event on the task so it's visible
#      via ``hermes kanban show <id>`` and the dashboard.
#   3. Touch a sentinel file under ``kanban_home() / '.scratch_tip_shown'``
#      so we don't repeat the tip — once you know, you know.
#
# Scope is per-install, not per-board: a user creating a second board
# already learned the lesson on board #1.

_SCRATCH_TIP_SENTINEL_NAME = ".scratch_tip_shown"

_SCRATCH_TIP_MESSAGE = (
    "scratch workspaces are ephemeral — they're deleted when the task "
    "completes. Use --workspace worktree: (git worktree) or "
    "--workspace dir:/abs/path (existing dir) to preserve worker output."
)


def _scratch_tip_sentinel_path() -> Path:
    """Path to the per-install scratch-workspace-tip sentinel file."""
    return kanban_home() / _SCRATCH_TIP_SENTINEL_NAME


def _scratch_tip_shown() -> bool:
    """True iff the scratch-workspace tip has already been emitted on this
    install. Best-effort — any error means we re-emit, which is the safer
    failure mode for a help message."""
    try:
        return _scratch_tip_sentinel_path().exists()
    except OSError:
        return False


def _mark_scratch_tip_shown() -> None:
    """Touch the sentinel so future scratch workspaces stay silent.

    Best-effort: a failure here just means the tip might appear once more,
    which is preferable to crashing dispatch over a help message.
    """
    try:
        path = _scratch_tip_sentinel_path()
        path.parent.mkdir(parents=True, exist_ok=True)
        path.touch(exist_ok=True)
    except OSError:
        pass


def _maybe_emit_scratch_tip(
    conn: sqlite3.Connection,
    task_id: str,
    workspace_kind: Optional[str],
) -> None:
    """Emit the first-use scratch-workspace tip exactly once per install.

    Called from the dispatcher right after a scratch workspace is
    materialized. No-op for ``worktree`` / ``dir`` workspaces (they're
    preserved by design) and no-op after the sentinel exists.
    """
    if (workspace_kind or "scratch") != "scratch":
        return
    if _scratch_tip_shown():
        return
    try:
        _log.warning("kanban: %s (task %s)", _SCRATCH_TIP_MESSAGE, task_id)
        with write_txn(conn):
            _append_event(
                conn, task_id, "tip_scratch_workspace",
                {"message": _SCRATCH_TIP_MESSAGE},
            )
    except Exception:
        # Best-effort — never block the spawn loop over a help message.
        pass
    finally:
        _mark_scratch_tip_shown()


@_guarded_task_mutation(action="edit_result", capability=OLYMPUS_CAPABILITY_EDIT)
def edit_completed_task_result(
    conn: sqlite3.Connection,
    task_id: str,
    *,
    result: str,
    summary: Optional[str] = None,
    metadata: Optional[dict] = None,
) -> bool:
    """Backfill the user-visible result for an already completed task."""
    handoff_summary = summary if summary is not None else result
    with write_txn(conn):
        row = conn.execute(
            "SELECT status FROM tasks WHERE id = ?", (task_id,),
        ).fetchone()
        if not row or row["status"] != "done":
            return False
        conn.execute(
            "UPDATE tasks SET result = ? WHERE id = ?",
            (result, task_id),
        )
        run = conn.execute(
            """
            SELECT id FROM task_runs
             WHERE task_id = ?
               AND outcome = 'completed'
             ORDER BY COALESCE(ended_at, started_at, 0) DESC, id DESC
             LIMIT 1
            """,
            (task_id,),
        ).fetchone()
        run_id = int(run["id"]) if run else None
        if run_id is None:
            run_id = _synthesize_ended_run(
                conn, task_id,
                outcome="completed",
                summary=handoff_summary,
                metadata=metadata,
            )
        else:
            conn.execute(
                "UPDATE task_runs SET summary = ? WHERE id = ?",
                (handoff_summary, run_id),
            )
            if metadata is not None:
                conn.execute(
                    "UPDATE task_runs SET metadata = ? WHERE id = ?",
                    (json.dumps(metadata, ensure_ascii=False), run_id),
                )
        ev_summary = (
            handoff_summary.strip().splitlines()[0][:400]
            if handoff_summary else ""
        )
        _append_event(
            conn, task_id, "edited",
            {
                "fields": (
                    ["result", "summary"]
                    + (["metadata"] if metadata is not None else [])
                ),
                "result_len": len(result) if result else 0,
                "summary": ev_summary or None,
            },
            run_id=run_id,
        )
    return True


@_guarded_task_mutation(action="block", capability=OLYMPUS_CAPABILITY_STATUS)
def block_task(
    conn: sqlite3.Connection,
    task_id: str,
    *,
    reason: Optional[str] = None,
    expected_run_id: Optional[int] = None,
) -> bool:
    """Transition ``running -> blocked``."""
    with write_txn(conn):
        if expected_run_id is None:
            cur = conn.execute(
                """
                UPDATE tasks
                   SET status       = 'blocked',
                       claim_lock   = NULL,
                       claim_expires= NULL,
                       worker_pid   = NULL
                 WHERE id = ?
                   AND status IN ('running', 'ready')
                """,
                (task_id,),
            )
        else:
            cur = conn.execute(
                """
                UPDATE tasks
                   SET status       = 'blocked',
                       claim_lock   = NULL,
                       claim_expires= NULL,
                       worker_pid   = NULL
                 WHERE id = ?
                   AND status IN ('running', 'ready')
                   AND current_run_id = ?
                """,
                (task_id, int(expected_run_id)),
            )
        if cur.rowcount != 1:
            return False
        run_id = _end_run(
            conn, task_id,
            outcome="blocked", status="blocked",
            summary=reason,
        )
        # Synthesize a run when blocking a never-claimed task so the
        # reason is preserved in attempt history.
        if run_id is None and reason:
            run_id = _synthesize_ended_run(
                conn, task_id,
                outcome="blocked",
                summary=reason,
            )
        _append_event(conn, task_id, "blocked", {"reason": reason}, run_id=run_id)
        return True



@_guarded_task_mutation(action="promote", capability=OLYMPUS_CAPABILITY_STATUS)
def promote_task(
    conn: sqlite3.Connection,
    task_id: str,
    *,
    actor: str,
    reason: Optional[str] = None,
    force: bool = False,
    dry_run: bool = False,
) -> tuple[bool, Optional[str]]:
    """Manually promote a `todo` or `blocked` task to `ready`.

    Mirrors the automatic promotion done by ``recompute_ready`` but
    drives it from a deliberate operator action with an audit-trail
    entry. Refuses to promote if any parent dep is not in a terminal
    state (`done`/`archived`) unless ``force=True``. Does NOT change
    assignee or claim state. Returns ``(True, None)`` on success and
    ``(False, reason)`` if refused. ``dry_run=True`` validates the
    promotion would succeed without mutating state.
    """
    row = conn.execute(
        "SELECT status FROM tasks WHERE id = ?", (task_id,)
    ).fetchone()
    if row is None:
        return False, f"task {task_id} not found"

    cur_status = row["status"]
    if cur_status not in ("todo", "blocked"):
        return False, (
            f"task {task_id} is {cur_status!r}; promote only applies to "
            f"'todo' or 'blocked'"
        )

    if not force:
        parents = conn.execute(
            "SELECT t.id, t.status FROM tasks t "
            "JOIN task_links l ON l.parent_id = t.id "
            "WHERE l.child_id = ?",
            (task_id,),
        ).fetchall()
        unsatisfied = [
            p["id"] for p in parents
            if p["status"] not in ("done", "archived")
        ]
        if unsatisfied:
            return False, (
                f"unsatisfied parent dependencies: "
                f"{', '.join(unsatisfied)} (use --force to override)"
            )

    if dry_run:
        return True, None

    with write_txn(conn):
        upd = conn.execute(
            "UPDATE tasks SET status = 'ready' "
            "WHERE id = ? AND status IN ('todo', 'blocked')",
            (task_id,),
        )
        if upd.rowcount != 1:
            return False, f"task {task_id} status changed during promotion"
        _append_event(
            conn,
            task_id,
            "promoted_manual",
            {"actor": actor, "reason": reason, "forced": force},
        )

    return True, None


@_guarded_task_mutation(action="unblock", capability=OLYMPUS_CAPABILITY_STATUS)
def unblock_task(conn: sqlite3.Connection, task_id: str) -> bool:
    """Transition ``blocked``/``scheduled`` -> ready or todo.

    Defensively closes any stale ``current_run_id`` pointer before flipping
    status. In the common path (``block_task`` closed the run already) this
    is a no-op. If a future or external write left the pointer dangling,
    the leaked run is closed as ``reclaimed`` inside the same txn so the
    runs invariant (``current_run_id IS NULL`` ⇔ run row in terminal
    state) holds for the rest of this function's lifetime.
    """
    now = int(time.time())
    with write_txn(conn):
        stale = conn.execute(
            "SELECT current_run_id FROM tasks WHERE id = ? AND status IN ('blocked', 'scheduled')",
            (task_id,),
        ).fetchone()
        if stale and stale["current_run_id"]:
            conn.execute(
                """
                UPDATE task_runs
                   SET status = 'reclaimed', outcome = 'reclaimed',
                       summary = COALESCE(summary, 'invariant recovery on unblock'),
                       ended_at = ?,
                       claim_lock = NULL, claim_expires = NULL, worker_pid = NULL
                 WHERE id = ? AND ended_at IS NULL
                """,
                (now, int(stale["current_run_id"])),
            )
        # Re-gate on parent completion before flipping 'blocked' back to
        # 'ready'. Unconditionally setting status='ready' here bypasses the
        # parent-completion invariant (the dispatcher trusts that column);
        # if parents are still in progress the task must wait in 'todo'
        # until recompute_ready picks it up. RCA: Bug 2 at
        # kanban/boards/cookai/workspaces/t_a6acd07d/root-cause.md.
        undone_parents = conn.execute(
            "SELECT 1 FROM task_links l "
            "JOIN tasks p ON p.id = l.parent_id "
            "WHERE l.child_id = ? AND p.status != 'done' LIMIT 1",
            (task_id,),
        ).fetchone()
        new_status = "todo" if undone_parents else "ready"
        cur = conn.execute(
            "UPDATE tasks SET status = ?, current_run_id = NULL, "
            "consecutive_failures = 0, last_failure_error = NULL "
            "WHERE id = ? AND status IN ('blocked', 'scheduled')",
            (new_status, task_id),
        )
        if cur.rowcount != 1:
            return False
        _append_event(
            conn, task_id, "unblocked",
            {"status": new_status} if new_status != "ready" else None,
        )
        return True


@_guarded_task_mutation(action="specify_triage", capability=OLYMPUS_CAPABILITY_TRIAGE)
def specify_triage_task(
    conn: sqlite3.Connection,
    task_id: str,
    *,
    title: Optional[str] = None,
    body: Optional[str] = None,
    assignee: Optional[str] = None,
    author: Optional[str] = None,
) -> bool:
    """Flesh out a triage task and promote it to ``todo``.

    Atomically updates ``title`` / ``body`` / ``assignee`` (when provided)
    and transitions ``status: triage -> todo`` in a single write txn. Returns
    False when the task is missing or not in the ``triage`` column — callers
    should surface that as "nothing to specify" rather than an error.

    ``todo`` (not ``ready``) is the correct landing column: ``recompute_ready``
    promotes parent-free / parent-done todos to ``ready`` on the next
    dispatcher tick, which keeps the normal parent-gating behaviour intact
    for specified tasks that happen to have open parents.

    ``author`` is recorded on an audit comment only when at least one of
    ``title`` / ``body`` / ``assignee`` actually changed — avoids noisy
    comment spam for status-only promotions.
    """
    if title is not None and not title.strip():
        raise ValueError("title cannot be blank")
    assignee = _canonical_assignee(assignee)
    with write_txn(conn):
        existing = conn.execute(
            "SELECT title, body, assignee, olympus_context FROM tasks "
            "WHERE id = ? AND status = 'triage'",
            (task_id,),
        ).fetchone()
        if existing is None:
            return False
        if existing["olympus_context"] is not None and assignee is not None:
            context = normalize_olympus_context(existing["olympus_context"])
            lease = context["lease"]
            if not (
                assignee
                == existing["assignee"]
                == context["agent_id"]
                == lease["agent_id"]
                == lease["holder"]
            ):
                raise OlympusContextError(
                    "olympus_reassignment_requires_rebind",
                    "governed triage cannot change assignee without canonical rebind",
                )
        sets: list[str] = ["status = 'todo'"]
        params: list[Any] = []
        changed_fields: list[str] = []
        if title is not None and title.strip() != (existing["title"] or ""):
            sets.append("title = ?")
            params.append(title.strip())
            changed_fields.append("title")
        if body is not None and (body or "") != (existing["body"] or ""):
            sets.append("body = ?")
            params.append(body)
            changed_fields.append("body")
        if assignee is not None and assignee != (existing["assignee"] or None):
            sets.append("assignee = ?")
            params.append(assignee)
            changed_fields.append("assignee")
        params.append(task_id)
        cur = conn.execute(
            f"UPDATE tasks SET {', '.join(sets)} "
            f"WHERE id = ? AND status = 'triage'",
            tuple(params),
        )
        if cur.rowcount != 1:
            return False
        if (
            changed_fields and author and author.strip()
            and existing["olympus_context"] is None
        ):
            # Inline INSERT (rather than ``add_comment``) because we're
            # already inside this function's write_txn — nested BEGIN
            # IMMEDIATE would raise OperationalError. We also skip the
            # 'commented' event that ``add_comment`` emits, since the
            # 'specified' event below already records the change.
            conn.execute(
                "INSERT INTO task_comments (task_id, author, body, created_at) "
                "VALUES (?, ?, ?, ?)",
                (
                    task_id,
                    author.strip(),
                    "Specified — updated "
                    + ", ".join(changed_fields)
                    + " and promoted to todo.",
                    int(time.time()),
                ),
            )
        _append_event(
            conn,
            task_id,
            "specified",
            {"changed_fields": changed_fields} if changed_fields else None,
        )
    # Outside the write_txn above, so we don't nest BEGIN IMMEDIATE — the
    # ready-promotion pass opens its own IMMEDIATE txn. This runs the same
    # logic the dispatcher would on its next tick, so a specified task
    # with no open parents flips straight to 'ready' here instead of
    # idling in 'todo' until the next sweep.
    recompute_ready(conn)
    return True


@_guarded_task_mutation(action="decompose_triage", capability=OLYMPUS_CAPABILITY_TRIAGE)
def decompose_triage_task(
    conn: sqlite3.Connection,
    task_id: str,
    *,
    root_assignee: Optional[str],
    children: list[dict],
    author: Optional[str] = None,
    auto_promote: bool = True,
) -> Optional[list[str]]:
    """Fan a triage task out into child tasks and promote the root to ``todo``.

    The root task stays alive and becomes the parent of every child —
    when all children reach ``done``, the root promotes to ``ready`` and
    its assignee (typically the orchestrator profile) wakes back up to
    judge completion or spawn more work.

    ``children`` is a list of dicts, each shaped like::

        {
            "title": "...",
            "body": "...",                     # optional
            "assignee": "profile-name",        # optional, None -> default fallback
            "parents": [0, 2],                 # indices into this same children list
        }

    Returns the list of created child task ids (in input order) on
    success. Returns ``None`` when:
      - The root task does not exist
      - The root task is not in ``triage``
      - A cycle would result (caller built a bad graph)

    Validation of titles/assignees happens inside the same write_txn as
    the inserts so a malformed entry aborts the whole decomposition
    cleanly (no orphan children).
    """
    if not children:
        return None
    if root_assignee is not None:
        root_assignee = _canonical_assignee(root_assignee)

    # Pre-validate the children list shape outside the txn. Cheap checks
    # that don't need DB access. Bad input aborts before we touch the DB.
    for idx, child in enumerate(children):
        if not isinstance(child, dict):
            raise ValueError(f"child[{idx}] is not a dict")
        title = child.get("title")
        if not isinstance(title, str) or not title.strip():
            raise ValueError(f"child[{idx}].title is required")
        parents_idx = child.get("parents") or []
        if not isinstance(parents_idx, list):
            raise ValueError(f"child[{idx}].parents must be a list")
        for p in parents_idx:
            if not isinstance(p, int) or p < 0 or p >= len(children):
                raise ValueError(
                    f"child[{idx}].parents[{p}] is not a valid index into children"
                )
            if p == idx:
                raise ValueError(f"child[{idx}] cannot list itself as a parent")

    # Detect cycles in the sibling parent graph (Kahn's topological sort).
    # link_tasks() calls _would_cycle() for every new edge; here we check
    # the entire sibling graph before touching the DB.  A cycle silently
    # deadlocks every involved child in 'todo' because recompute_ready()
    # can never promote them.
    _in_deg = [0] * len(children)
    _adj: list[list[int]] = [[] for _ in range(len(children))]
    for _i, _c in enumerate(children):
        for _p in (_c.get("parents") or []):
            _adj[_p].append(_i)
            _in_deg[_i] += 1
    _queue = [_i for _i in range(len(children)) if _in_deg[_i] == 0]
    _seen = 0
    while _queue:
        _node = _queue.pop()
        _seen += 1
        for _nb in _adj[_node]:
            _in_deg[_nb] -= 1
            if _in_deg[_nb] == 0:
                _queue.append(_nb)
    if _seen != len(children):
        raise ValueError("cyclic dependency detected in decomposed children list")

    # We do the full decomposition in a SINGLE write_txn so it's
    # atomic: either every child is created AND the root flips to
    # ``todo``, or nothing changes. We deliberately do NOT call any
    # kb helper that opens its own write_txn (create_task, link_tasks,
    # add_comment) from inside this block — see architecture.md
    # write_txn pitfalls. Instead we inline the INSERTs and
    # _append_event calls.
    now = int(time.time())
    child_ids: list[str] = []
    with write_txn(conn):
        root_row = conn.execute(
            "SELECT id, status, assignee, tenant, workspace_kind, "
            "workspace_path, olympus_context "
            "FROM tasks WHERE id = ?",
            (task_id,),
        ).fetchone()
        if root_row is None:
            return None
        if root_row["status"] != "triage":
            return None
        root_olympus = _require_current_olympus_context(
            root_row["olympus_context"],
            assignee=root_row["assignee"],
            now=now,
        )
        if root_olympus is not None:
            raise OlympusContextError(
                "olympus_verified_context_required",
                "governed decomposition requires a dedicated canonical-verification path",
            )
        if (
            root_olympus is not None
            and root_assignee is not None
            and root_assignee != root_olympus["agent_id"]
        ):
            raise OlympusContextError(
                "olympus_agent_mismatch",
                "root reassignment requires a matching refreshed Olympus context",
            )
        tenant = root_row["tenant"]
        # Children inherit the root's workspace by default so a fan-out
        # of a code-gen task lands in the parent's project dir/worktree
        # rather than throwaway scratch tmp dirs. A child dict can still
        # override with its own 'workspace_kind' / 'workspace_path'.
        root_ws_kind = root_row["workspace_kind"] or "scratch"
        root_ws_path = root_row["workspace_path"]

        # Create children. Status is 'todo' regardless of parents — we
        # link them under the root AFTER creation so the dispatcher
        # sees a coherent state, and recompute_ready() at the end
        # promotes parent-free children to 'ready'.
        for idx, child in enumerate(children):
            new_id = _new_task_id()
            title = child["title"].strip()
            body = child.get("body")
            assignee = _canonical_assignee(child.get("assignee"))
            child_olympus: Optional[dict[str, Any]] = None
            if root_olympus is not None:
                if assignee is None:
                    raise OlympusContextError(
                        "olympus_agent_missing",
                        "a governed decomposed task requires an assignee",
                    )
                explicit_child_context = child.get("olympus_context")
                if explicit_child_context is None:
                    child_olympus = derive_olympus_child_context(
                        root_olympus,
                        agent_id=assignee,
                        workstream_id=child.get("workstream_id"),
                    )
                else:
                    child_olympus = normalize_olympus_context(
                        explicit_child_context
                    )
                    for key in (
                        "goal_id", "program_id", "milestone_id", "mission_id"
                    ):
                        if child_olympus[key] != root_olympus[key]:
                            raise OlympusContextError(
                                "olympus_parent_context_conflict",
                                "decomposed child context crosses the root mission",
                            )
            elif child.get("olympus_context") is not None:
                child_olympus = normalize_olympus_context(
                    child["olympus_context"]
                )
            # Per-child override wins; otherwise inherit the root's
            # workspace. A child that sets workspace_kind without a path
            # falls back to the root path only when kinds match (so a
            # child can't accidentally point a 'dir' at the root's
            # worktree path or vice versa).
            child_ws_kind = child.get("workspace_kind") or root_ws_kind
            if child.get("workspace_path"):
                child_ws_path = child.get("workspace_path")
            elif child_ws_kind == root_ws_kind:
                child_ws_path = root_ws_path
            else:
                child_ws_path = None
            conn.execute(
                "INSERT INTO tasks "
                "(id, title, body, assignee, status, workspace_kind, "
                " workspace_path, tenant, created_at, created_by, "
                " olympus_context) "
                "VALUES (?, ?, ?, ?, 'todo', ?, ?, ?, ?, ?, ?)",
                (
                    new_id,
                    title,
                    body if isinstance(body, str) else None,
                    assignee,
                    child_ws_kind,
                    child_ws_path,
                    tenant,
                    now,
                    (author or "decomposer"),
                    (
                        _serialize_olympus_context(child_olympus)
                        if child_olympus is not None else None
                    ),
                ),
            )
            _append_event(
                conn, new_id, "created",
                {
                    "by": author or "decomposer",
                    "from_decompose_of": task_id,
                    "olympus": (
                        _olympus_trace(child_olympus)
                        if child_olympus is not None else None
                    ),
                },
            )
            child_ids.append(new_id)

        # Link children to their sibling parents (within the decomposed graph).
        for idx, child in enumerate(children):
            for p_idx in child.get("parents") or []:
                parent_id = child_ids[p_idx]
                child_id = child_ids[idx]
                conn.execute(
                    "INSERT OR IGNORE INTO task_links (parent_id, child_id) "
                    "VALUES (?, ?)",
                    (parent_id, child_id),
                )
                _append_event(
                    conn, child_id, "linked",
                    {"parent": parent_id, "child": child_id},
                )

        # Link the ROOT task as a child of every leaf child — i.e. the
        # root waits for the whole graph. Simpler than computing leaves:
        # link root under every child. Cycle-free because the root is
        # only ever a child here, never a parent of children.
        for cid in child_ids:
            conn.execute(
                "INSERT OR IGNORE INTO task_links (parent_id, child_id) "
                "VALUES (?, ?)",
                (cid, task_id),
            )

        # Flip the root: triage -> todo, set assignee to the orchestrator.
        sets = ["status = 'todo'"]
        params: list[Any] = []
        if root_assignee is not None:
            sets.append("assignee = ?")
            params.append(root_assignee)
        params.append(task_id)
        conn.execute(
            f"UPDATE tasks SET {', '.join(sets)} WHERE id = ?",
            tuple(params),
        )

        # Audit comment + event on the root so the timeline shows the fan-out.
        if author and author.strip():
            conn.execute(
                "INSERT INTO task_comments (task_id, author, body, created_at) "
                "VALUES (?, ?, ?, ?)",
                (
                    task_id,
                    author.strip(),
                    "Decomposed into "
                    + ", ".join(child_ids)
                    + ". Root will wake when all children complete.",
                    now,
                ),
            )
        _append_event(
            conn, task_id, "decomposed",
            {
                "child_ids": child_ids,
                "root_assignee": root_assignee,
            },
        )

    # Outside the write_txn: promote parent-free children to 'ready'
    # so the dispatcher picks them up on its next tick. Same pattern
    # specify_triage_task uses.  When auto_promote is False children
    # stay in 'todo' until the user manually promotes them — useful
    # for manual-review-first workflows.
    if auto_promote:
        recompute_ready(conn)
    return child_ids


@_guarded_task_mutation(action="archive", capability=OLYMPUS_CAPABILITY_ARCHIVE)
def archive_task(
    conn: sqlite3.Connection,
    task_id: str,
    *,
    expected_record_revision: Optional[int] = None,
) -> bool:
    with write_txn(conn):
        if expected_record_revision is None:
            cur = conn.execute(
                "UPDATE tasks SET status = 'archived', "
                "    claim_lock = NULL, claim_expires = NULL, worker_pid = NULL "
                "WHERE id = ? AND status != 'archived'",
                (task_id,),
            )
        else:
            if isinstance(expected_record_revision, bool) \
                    or not isinstance(expected_record_revision, int) \
                    or expected_record_revision < 1:
                raise ValueError("expected_record_revision must be a positive integer")
            cur = conn.execute(
                "UPDATE tasks SET status = 'archived', "
                "    claim_lock = NULL, claim_expires = NULL, worker_pid = NULL "
                "WHERE id = ? AND status != 'archived' "
                "AND record_revision = ?",
                (task_id, expected_record_revision),
            )
        if cur.rowcount != 1:
            return False
        # If archive happened while a run was still in flight (e.g. user
        # archived a running task from the dashboard), close that run with
        # outcome='reclaimed' so attempt history isn't orphaned.
        run_id = _end_run(
            conn, task_id,
            outcome="reclaimed", status="reclaimed",
            summary="task archived with run still active",
        )
        _append_event(conn, task_id, "archived", None, run_id=run_id)
    # ``archived`` parents no longer block children, same as ``done``.
    # Promote newly-unblocked dependents immediately instead of waiting
    # for a later dispatcher tick.
    recompute_ready(conn)
    return True


def _authorize_delete_link_neighbors(
    conn: sqlite3.Connection,
    task_id: str,
) -> list[tuple[str, bool, Optional[dict[str, Any]]]]:
    """Authorize link removal against every governed neighbor aggregate."""
    rows = conn.execute(
        "SELECT DISTINCT CASE WHEN parent_id = ? THEN child_id ELSE parent_id END AS id "
        "FROM task_links WHERE parent_id = ? OR child_id = ?",
        (task_id, task_id, task_id),
    ).fetchall()
    permits: list[tuple[str, bool, Optional[dict[str, Any]]]] = []
    for row in rows:
        neighbor_id = str(row["id"])
        authorization, owns = _authorize_task_mutation(
            conn,
            neighbor_id,
            action="unlink_deleted_task",
            capability=OLYMPUS_CAPABILITY_LINK,
        )
        permits.append((neighbor_id, owns, authorization))
    return permits


@_guarded_task_mutation(action="delete_archived", capability=OLYMPUS_CAPABILITY_DELETE)
def delete_archived_task(conn: sqlite3.Connection, task_id: str) -> bool:
    """Permanently remove an already-archived task and its related rows.

    Safety guard: only archived tasks can be deleted. Active / blocked / done
    tasks must be explicitly archived first so accidental data loss requires a
    second deliberate action.
    """
    with write_txn(conn):
        row = conn.execute(
            "SELECT status FROM tasks WHERE id = ?",
            (task_id,),
        ).fetchone()
        if not row or row["status"] != "archived":
            return False
        permits = _authorize_delete_link_neighbors(conn, task_id)
        try:
            conn.execute(
                "DELETE FROM task_links WHERE parent_id = ? OR child_id = ?",
                (task_id, task_id),
            )
            for neighbor_id, _, authorization in permits:
                if authorization is not None:
                    conn.execute(
                        "UPDATE tasks SET record_revision = record_revision WHERE id = ?",
                        (neighbor_id,),
                    )
            conn.execute("DELETE FROM task_comments WHERE task_id = ?", (task_id,))
            conn.execute("DELETE FROM task_events WHERE task_id = ?", (task_id,))
            conn.execute("DELETE FROM kanban_effect_journal WHERE task_id = ?", (task_id,))
            conn.execute("DELETE FROM task_runs WHERE task_id = ?", (task_id,))
            conn.execute("DELETE FROM task_attachments WHERE task_id = ?", (task_id,))
            conn.execute("DELETE FROM kanban_notify_subs WHERE task_id = ?", (task_id,))
            cur = conn.execute("DELETE FROM tasks WHERE id = ?", (task_id,))
        finally:
            for neighbor_id, owns, _ in reversed(permits):
                _release_task_mutation_permit(conn, neighbor_id, owns)
    return cur.rowcount == 1


@_guarded_task_mutation(
    action="edit_task",
    capability=OLYMPUS_CAPABILITY_EDIT,
    touch_aggregate=True,
)
def edit_task_fields(
    conn: sqlite3.Connection,
    task_id: str,
    *,
    title: Optional[str] = None,
    body: Optional[str] = None,
    priority: Optional[int] = None,
) -> bool:
    """Edit dashboard-visible fields through the governed write boundary."""
    if title is None and body is None and priority is None:
        return False
    if title is not None and not title.strip():
        raise ValueError("title cannot be empty")
    with write_txn(conn):
        existing = conn.execute(
            "SELECT title, body, priority FROM tasks WHERE id = ?",
            (task_id,),
        ).fetchone()
        if existing is None:
            return False
        sets: list[str] = []
        values: list[Any] = []
        changed_fields: list[str] = []
        if title is not None and title.strip() != existing["title"]:
            sets.append("title = ?")
            values.append(title.strip())
            changed_fields.append("title")
        if body is not None and body != existing["body"]:
            sets.append("body = ?")
            values.append(body)
            changed_fields.append("body")
        if priority is not None and int(priority) != int(existing["priority"] or 0):
            sets.append("priority = ?")
            values.append(int(priority))
            changed_fields.append("priority")
        if not sets:
            return False
        values.append(task_id)
        cur = conn.execute(
            f"UPDATE tasks SET {', '.join(sets)} WHERE id = ?",
            values,
        )
        if cur.rowcount != 1:
            return False
        if "priority" in changed_fields:
            _append_event(
                conn, task_id, "reprioritized", {"priority": int(priority)},
            )
        if "title" in changed_fields or "body" in changed_fields:
            _append_event(
                conn,
                task_id,
                "edited",
                {
                    "fields": [
                        name for name in ("title", "body")
                        if name in changed_fields
                    ]
                },
            )
    return True


def set_task_status(
    conn: sqlite3.Connection,
    task_id: str,
    new_status: str,
    *,
    olympus_auth: Optional[OlympusMutationAuth] = None,
) -> bool:
    """Set a non-running status with atomic governed child demotion."""
    if new_status not in VALID_STATUSES or new_status == "running":
        raise ValueError("direct status must be a valid non-running status")
    bound_auth = olympus_auth or _OLYMPUS_MUTATION_AUTH.get()
    with olympus_mutation_scope(bound_auth), write_txn(conn):
        permits: list[tuple[str, bool, Optional[dict[str, Any]]]] = []
        try:
            authorization, owns = _authorize_task_mutation(
                conn,
                task_id,
                action="set_direct_status",
                capability=OLYMPUS_CAPABILITY_STATUS,
                auth=bound_auth,
            )
            permits.append((task_id, owns, authorization))
            prev = conn.execute(
                "SELECT status, current_run_id FROM tasks WHERE id = ?",
                (task_id,),
            ).fetchone()
            if prev is None:
                return False
            if prev["status"] == new_status:
                return False
            if new_status == "ready" and conn.execute(
                "SELECT 1 FROM task_links l JOIN tasks p ON p.id = l.parent_id "
                "WHERE l.child_id = ? AND p.status != 'done' LIMIT 1",
                (task_id,),
            ).fetchone() is not None:
                return False
            reopening = (
                prev["status"] in {"done", "archived"}
                and new_status not in {"done", "archived"}
            )
            children = (
                conn.execute(
                    "SELECT t.id FROM task_links l JOIN tasks t ON t.id = l.child_id "
                    "WHERE l.parent_id = ? AND t.status = 'ready' ORDER BY t.id",
                    (task_id,),
                ).fetchall()
                if reopening else []
            )
            for child in children:
                child_id = str(child["id"])
                child_auth, child_owns = _authorize_task_mutation(
                    conn,
                    child_id,
                    action="demote_parent_reopened",
                    capability=OLYMPUS_CAPABILITY_STATUS,
                    auth=bound_auth,
                )
                permits.append((child_id, child_owns, child_auth))
            cur = conn.execute(
                "UPDATE tasks SET status = ?, claim_lock = NULL, "
                "claim_expires = NULL, worker_pid = NULL WHERE id = ?",
                (new_status, task_id),
            )
            if cur.rowcount != 1:
                return False
            run_id = None
            if prev["status"] == "running" and prev["current_run_id"]:
                run_id = _end_run(
                    conn,
                    task_id,
                    outcome="reclaimed",
                    status="reclaimed",
                    summary=f"status changed to {new_status} (direct)",
                )
            _append_event(
                conn, task_id, "status", {"status": new_status}, run_id=run_id,
            )
            for child in children:
                child_id = str(child["id"])
                demoted = conn.execute(
                    "UPDATE tasks SET status = 'todo' "
                    "WHERE id = ? AND status = 'ready'",
                    (child_id,),
                )
                if demoted.rowcount == 1:
                    _append_event(
                        conn,
                        child_id,
                        "status",
                        {
                            "status": "todo",
                            "reason": "parent_reopened",
                            "parent": task_id,
                        },
                    )
        finally:
            for permit_task, permit_owns, _ in reversed(permits):
                _release_task_mutation_permit(conn, permit_task, permit_owns)
    if new_status in {"done", "ready"}:
        recompute_ready(conn, olympus_auth=bound_auth)
    return True


@_guarded_task_mutation(action="delete", capability=OLYMPUS_CAPABILITY_DELETE)
def delete_task(conn: sqlite3.Connection, task_id: str) -> bool:
    """Hard-delete a task and cascade to all related rows.

    Because the schema does not use ``ON DELETE CASCADE`` foreign keys,
    we explicitly delete from child tables first, then the task row.
    This keeps the operation atomic (single ``write_txn``).

    Returns ``True`` if the task existed and was deleted, ``False``
    if the task was not found.
    """
    with write_txn(conn):
        if conn.execute(
            "SELECT 1 FROM tasks WHERE id = ?", (task_id,),
        ).fetchone() is None:
            return False
        permits = _authorize_delete_link_neighbors(conn, task_id)
        try:
            conn.execute(
                "DELETE FROM task_links WHERE parent_id = ? OR child_id = ?",
                (task_id, task_id),
            )
            for neighbor_id, _, authorization in permits:
                if authorization is not None:
                    conn.execute(
                        "UPDATE tasks SET record_revision = record_revision WHERE id = ?",
                        (neighbor_id,),
                    )
            conn.execute("DELETE FROM task_comments WHERE task_id = ?", (task_id,))
            conn.execute("DELETE FROM task_events WHERE task_id = ?", (task_id,))
            conn.execute("DELETE FROM kanban_effect_journal WHERE task_id = ?", (task_id,))
            conn.execute("DELETE FROM task_runs WHERE task_id = ?", (task_id,))
            conn.execute("DELETE FROM task_attachments WHERE task_id = ?", (task_id,))
            conn.execute("DELETE FROM kanban_notify_subs WHERE task_id = ?", (task_id,))
            cur = conn.execute("DELETE FROM tasks WHERE id = ?", (task_id,))
            if cur.rowcount != 1:
                return False
        finally:
            for neighbor_id, owns, _ in reversed(permits):
                _release_task_mutation_permit(conn, neighbor_id, owns)
    recompute_ready(conn)
    return True


# ---------------------------------------------------------------------------
# Workspace resolution
# ---------------------------------------------------------------------------

def resolve_workspace(task: Task, *, board: Optional[str] = None) -> Path:
    """Resolve (and create if needed) the workspace for a task.

    - ``scratch``: a fresh dir under ``<board-root>/workspaces/<id>/``,
      where ``<board-root>`` is the active board's root. The path is the
      same for the dispatcher and every profile worker, so handoff is
      path-stable.
    - ``dir:<path>``: the path stored in ``workspace_path``.  Created
      if missing.  MUST be absolute — relative paths are rejected to
      prevent confused-deputy traversal where ``../../../tmp/attacker``
      resolves against the dispatcher's CWD instead of a meaningful
      root.  Users who want a kanban-root-relative workspace should
      compute the absolute path themselves.
    - ``worktree``: a git worktree at ``workspace_path``.  Not created
      automatically in v1 -- the kanban-worker skill documents
      ``git worktree add`` as a worker-side step.  Returns the intended path.

    Persist the resolved path back to the task row via ``set_workspace_path``
    so subsequent runs reuse the same directory.
    """
    kind = task.workspace_kind or "scratch"
    if kind == "scratch":
        if task.workspace_path:
            # Legacy scratch tasks that were set to an explicit path get the
            # same absolute-path guard as dir: — consistent with the
            # threat model.
            p = Path(task.workspace_path).expanduser()
            if not p.is_absolute():
                raise ValueError(
                    f"task {task.id} has non-absolute workspace_path "
                    f"{task.workspace_path!r}; workspace paths must be absolute"
                )
        else:
            p = workspaces_root(board=board) / task.id
        p.mkdir(parents=True, exist_ok=True)
        return p
    if kind == "dir":
        if not task.workspace_path:
            raise ValueError(
                f"task {task.id} has workspace_kind=dir but no workspace_path"
            )
        p = Path(task.workspace_path).expanduser()
        if not p.is_absolute():
            raise ValueError(
                f"task {task.id} has non-absolute workspace_path "
                f"{task.workspace_path!r}; use an absolute path "
                f"(relative paths are ambiguous against the dispatcher's CWD)"
            )
        p.mkdir(parents=True, exist_ok=True)
        return p
    if kind == "worktree":
        if not task.workspace_path:
            # Default: .worktrees/<id>/ under CWD.  Worker skill creates it.
            return Path.cwd() / ".worktrees" / task.id
        p = Path(task.workspace_path).expanduser()
        if not p.is_absolute():
            raise ValueError(
                f"task {task.id} has non-absolute worktree path "
                f"{task.workspace_path!r}; use an absolute path"
            )
        return p
    raise ValueError(f"unknown workspace_kind: {kind}")


@_guarded_task_mutation(action="set_workspace", capability=OLYMPUS_CAPABILITY_WORKSPACE)
def set_workspace_path(
    conn: sqlite3.Connection, task_id: str, path: Path | str
) -> None:
    with write_txn(conn):
        conn.execute(
            "UPDATE tasks SET workspace_path = ? WHERE id = ?",
            (str(path), task_id),
        )


# ---------------------------------------------------------------------------
@_guarded_task_mutation(action="schedule", capability=OLYMPUS_CAPABILITY_STATUS)
def schedule_task(
    conn: sqlite3.Connection,
    task_id: str,
    *,
    reason: Optional[str] = None,
    expected_run_id: Optional[int] = None,
) -> bool:
    """Park a task in ``scheduled`` so it is waiting on time, not human input.

    ``scheduled`` tasks are intentionally not dispatchable; an external cron,
    human action, or automation can later call ``unblock_task`` to re-gate them
    to ``ready`` (or ``todo`` if parents are still incomplete).
    """
    with write_txn(conn):
        params: list[Any] = [task_id]
        sql = """
            UPDATE tasks
               SET status       = 'scheduled',
                   claim_lock   = NULL,
                   claim_expires= NULL,
                   worker_pid   = NULL
             WHERE id = ?
               AND status IN ('todo', 'ready', 'running', 'blocked')
        """
        if expected_run_id is not None:
            sql += " AND current_run_id = ?"
            params.append(int(expected_run_id))
        cur = conn.execute(sql, params)
        if cur.rowcount != 1:
            return False
        run_id = _end_run(
            conn, task_id,
            outcome="scheduled", status="scheduled",
            summary=reason,
        )
        if run_id is None and reason:
            run_id = _synthesize_ended_run(
                conn, task_id,
                outcome="scheduled",
                summary=reason,
            )
        _append_event(conn, task_id, "scheduled", {"reason": reason}, run_id=run_id)
        return True


# Dispatcher (one-shot pass)
# ---------------------------------------------------------------------------

# After this many consecutive non-success attempts on a task/profile, the
# dispatcher stops retrying and parks the task in ``blocked`` with a reason so
# a human can investigate. Prevents retry storms when a worker repeatedly times
# out, crashes, or cannot spawn.
DEFAULT_FAILURE_LIMIT = 2
# Legacy alias — callers / tests still reference the old name.
DEFAULT_SPAWN_FAILURE_LIMIT = DEFAULT_FAILURE_LIMIT

# Max bytes to keep in a single worker log file. The dispatcher truncates
# and rotates on spawn if the file is larger than this at spawn time.
DEFAULT_LOG_ROTATE_BYTES = 2 * 1024 * 1024   # 2 MiB
DEFAULT_LOG_BACKUP_COUNT = 1

# Keep a little wall-clock budget for the worker to observe a terminal timeout
# and call kanban_block/kanban_complete before max_runtime_seconds kills it.
KANBAN_TERMINAL_TIMEOUT_GRACE_SECONDS = 30

# ---------------------------------------------------------------------------
# Respawn guard constants
# ---------------------------------------------------------------------------

# Patterns in last_failure_error that indicate a quota / auth blocker.
# These errors won't resolve by retrying immediately — auto-block instead.
_RESPAWN_BLOCKER_RE = re.compile(
    r"\b(quota|rate[\s_\-]?limit|429|403|auth\w*|"
    r"unauthorized|forbidden|billing|subscription|"
    r"access[\s_]denied|permission[\s_]denied|"
    r"invalid[\s_]api[\s_]key)\b",
    re.IGNORECASE,
)

# Within this window a completed run counts as "recent proof"; don't re-spawn.
_RESPAWN_GUARD_SUCCESS_WINDOW = 3600  # 1 hour

# Cooldown after a rate-limited (quota-wall) requeue before the dispatcher
# re-spawns the worker. Without this, a task released by the rate-limit path
# would be re-spawned on the very next tick and immediately bounce off the
# same quota wall, burning a worker slot every tick for hours. The cooldown
# spaces retries out so the board keeps cheaply probing whether quota is back
# without thrashing. Overridable via ``HERMES_KANBAN_RATE_LIMIT_COOLDOWN_SECONDS``
# for operators who want a tighter/looser probe cadence.
DEFAULT_RATE_LIMIT_COOLDOWN_SECONDS = 300  # 5 minutes

# Within this window a GitHub PR URL in a comment blocks re-spawn.
_RESPAWN_GUARD_PR_WINDOW = 86400  # 24 hours

# Pattern matching a GitHub PR URL in task comments.
_RESPAWN_GUARD_PR_URL_RE = re.compile(
    r"https?://github\.com/[^/\s]+/[^/\s]+/pull/\d+",
    re.IGNORECASE,
)


@dataclass
class DispatchResult:
    """Outcome of a single ``dispatch`` pass."""

    reclaimed: int = 0
    promoted: int = 0
    spawned: list[tuple[str, str, str]] = field(default_factory=list)
    """List of ``(task_id, assignee, workspace_path)`` triples."""
    skipped_unassigned: list[str] = field(default_factory=list)
    """Ready task ids skipped because they have no assignee at all.
    Operator-actionable — usually a misfiled task waiting for routing."""
    auto_assigned_default: list[str] = field(default_factory=list)
    """Task ids that were unassigned in the DB and had
    ``kanban.default_assignee`` applied this tick before spawning (#27145).
    Surfaces the auto-assignment to telemetry / CLI / dashboard so the
    operator can see when the dispatcher is acting on the fallback rule
    rather than on explicit per-task assignments."""
    skipped_nonspawnable: list[str] = field(default_factory=list)
    """Ready task ids skipped because their assignee names a control-plane
    lane (a Claude Code terminal like ``orion-cc``) rather than a Hermes
    profile. Expected steady-state on multi-lane setups; NOT an
    operator-actionable failure. Tracked separately so health telemetry
    can distinguish "real stuck" (nothing spawned but spawnable work
    available) from "correctly idle" (nothing spawnable in the queue)."""
    skipped_per_profile_capped: list[tuple[str, str, int]] = field(default_factory=list)
    """Tasks deferred this tick because their assignee is already at
    ``kanban.max_in_progress_per_profile`` (#21582). Each entry is
    ``(task_id, assignee, current_running_count)``. NOT an
    operator-actionable failure — the task will be picked up on a
    subsequent tick when the assignee has capacity. Separate bucket so
    telemetry / dashboards can show "this profile is busy" vs
    "task is genuinely stuck"."""
    crashed: list[str] = field(default_factory=list)
    """Task ids reclaimed because their worker PID disappeared."""
    auto_blocked: list[str] = field(default_factory=list)
    """Task ids auto-blocked by the spawn-failure circuit breaker."""
    timed_out: list[str] = field(default_factory=list)
    """Task ids whose workers exceeded ``max_runtime_seconds``."""
    stale: list[str] = field(default_factory=list)
    """Task ids reclaimed because no progress (heartbeat) was seen
    within ``dispatch_stale_timeout_seconds``."""
    respawn_guarded: list[tuple[str, str]] = field(default_factory=list)
    """Tasks skipped by the respawn guard, as ``(task_id, reason)`` pairs.

    Reasons: ``"blocker_auth"`` (quota/auth error — also auto-blocked),
    ``"recent_success"`` (completed run within guard window),
    ``"active_pr"`` (GitHub PR URL in a recent comment)."""
    rate_limited: list[str] = field(default_factory=list)
    """Task ids whose workers bailed on a provider rate-limit / quota wall
    (EX_TEMPFAIL sentinel exit) and were released back to ``ready`` WITHOUT
    counting a failure. These never trip the circuit breaker — a long quota
    window just makes the task bounce cheaply until the window clears."""


# Bounded registry of recently-reaped worker child exits, populated by the
# reap loop at the top of ``dispatch_once`` and consulted by
# ``detect_crashed_workers`` to classify a dead-pid task.
#
# Entry: ``pid -> (raw_wait_status, reaped_at_epoch)``. We keep raw status
# so both ``os.WIFEXITED`` / ``os.WEXITSTATUS`` and ``os.WIFSIGNALED`` can
# be consulted. Entries are trimmed by age (and total size cap as a
# belt-and-braces against unbounded growth on exotic platforms).
_RECENT_WORKER_EXIT_TTL_SECONDS = 600
_RECENT_WORKER_EXITS_MAX = 4096
_recent_worker_exits: "dict[int, tuple[int, float]]" = {}


def _record_worker_exit(pid: int, raw_status: int) -> None:
    """Record a reaped child's exit status for later classification.

    Called from the reap loop in ``dispatch_once``. Safe to call many
    times; duplicate pids overwrite (pids can cycle, latest wins).
    """
    if not pid or pid <= 0:
        return
    now = time.time()
    _recent_worker_exits[int(pid)] = (int(raw_status), now)
    # Age-based trim: drop entries older than the TTL.
    if len(_recent_worker_exits) > _RECENT_WORKER_EXITS_MAX // 2:
        cutoff = now - _RECENT_WORKER_EXIT_TTL_SECONDS
        for _pid in [p for p, (_s, t) in _recent_worker_exits.items() if t < cutoff]:
            _recent_worker_exits.pop(_pid, None)
    # Size cap as a final guard.
    if len(_recent_worker_exits) > _RECENT_WORKER_EXITS_MAX:
        # Drop oldest half.
        ordered = sorted(_recent_worker_exits.items(), key=lambda kv: kv[1][1])
        for _pid, _ in ordered[: len(ordered) // 2]:
            _recent_worker_exits.pop(_pid, None)


def _classify_worker_exit(pid: int) -> "tuple[str, Optional[int]]":
    """Classify a recently-reaped worker by pid.

    Returns ``(kind, code)`` where ``kind`` is one of:

    * ``"clean_exit"`` — ``WIFEXITED`` with ``WEXITSTATUS == 0``. When the
      task is still ``running`` in the DB, this is a protocol violation
      (worker exited without calling ``kanban_complete`` / ``kanban_block``)
      and should be auto-blocked immediately — retrying will just loop.
    * ``"rate_limited"`` — ``WIFEXITED`` with status
      ``KANBAN_RATE_LIMIT_EXIT_CODE``. The worker bailed because the
      provider rate-limited / exhausted quota, NOT because the task failed.
      ``detect_crashed_workers`` releases the task back to ``ready`` without
      counting a failure, so a long quota window can't trip the breaker.
    * ``"nonzero_exit"`` — ``WIFEXITED`` with non-zero status. Real error.
    * ``"signaled"`` — ``WIFSIGNALED`` (OOM killer, SIGKILL, etc). Real crash.
    * ``"unknown"`` — pid was not in the reap registry (either reaped by
      something else, or died between reap tick and liveness check). Fall
      back to existing crashed-counter behavior.

    ``code`` is the exit status (for ``clean_exit`` / ``rate_limited`` /
    ``nonzero_exit``) or the signal number (for ``signaled``), or ``None``
    for ``unknown``.
    """
    entry = _recent_worker_exits.get(int(pid))
    if entry is None:
        return ("unknown", None)
    raw, _ = entry
    try:
        if os.WIFEXITED(raw):
            code = os.WEXITSTATUS(raw)
            if code == 0:
                return ("clean_exit", 0)
            if code == KANBAN_RATE_LIMIT_EXIT_CODE:
                return ("rate_limited", code)
            return ("nonzero_exit", code)
        if os.WIFSIGNALED(raw):
            return ("signaled", os.WTERMSIG(raw))
    except Exception:
        pass
    return ("unknown", None)


def reap_worker_zombies() -> "list[int]":
    """Reap all zombie children of this process without blocking.

    Returns the list of reaped PIDs. Safe to call when there are no
    children (returns []). No-op on Windows.
    """
    reaped: "list[int]" = []
    if os.name != "nt":
        try:
            while True:
                try:
                    pid, status = os.waitpid(-1, os.WNOHANG)
                except ChildProcessError:
                    break
                if pid == 0:
                    break
                _record_worker_exit(pid, status)
                reaped.append(pid)
        except Exception:
            pass
    return reaped


def _pid_alive(pid: Optional[int]) -> bool:
    """Return True if ``pid`` is still running on this host.

    Cross-platform: uses ``OpenProcess`` + ``WaitForSingleObject`` on
    Windows (via ``gateway.status._pid_exists``) and ``os.kill(pid, 0)``
    on POSIX. Returns False for falsy PIDs or on any OS error.

    **DO NOT** use ``os.kill(pid, 0)`` directly on Windows — Python's
    Windows ``os.kill`` treats ``sig=0`` as ``CTRL_C_EVENT`` (bpo-14484)
    and will broadcast it to the target's console group, potentially
    killing unrelated processes.

    **Zombie handling:** the existence check succeeds against zombie
    processes (post-exit, pre-reap) because the process table entry
    still exists. A worker that exits without being reaped by its
    parent would stay "alive" to the dispatcher forever. Dispatcher
    workers are started via ``start_new_session=True`` + intentional
    Popen handle abandonment, so init reaps them quickly — but during
    the window between exit and reap, we'd otherwise see stale "alive"
    signals. On Linux we peek at ``/proc/<pid>/status`` and treat
    ``State: Z`` as dead. On macOS we ask ``ps`` for the BSD ``stat``
    field and treat values containing ``Z`` as dead.
    """
    if not pid or pid <= 0:
        return False
    from gateway.status import _pid_exists
    if not _pid_exists(int(pid)):
        return False
    # Still here → process exists. Check for zombie on platforms
    # where we have a cheap, deterministic process-state probe.
    if sys.platform == "linux":
        try:
            with open(f"/proc/{int(pid)}/status", "r", encoding="utf-8") as f:
                for line in f:
                    if line.startswith("State:"):
                        # "State:\tZ (zombie)" → dead
                        if "Z" in line.split(":", 1)[1]:
                            return False
                        break
        except (FileNotFoundError, PermissionError, OSError):
            # proc entry gone → already reaped; treat as dead.
            # PermissionError shouldn't happen for our own children but
            # be defensive.
            pass
    elif sys.platform == "darwin":
        try:
            proc = subprocess.run(
                ["ps", "-o", "stat=", "-p", str(int(pid))],
                stdout=subprocess.PIPE,
                stderr=subprocess.DEVNULL,
                text=True,
                timeout=1,
                check=False,
            )
            if proc.returncode != 0:
                return False
            if "Z" in (proc.stdout or "").strip():
                return False
        except (OSError, subprocess.SubprocessError, TimeoutError):
            # If the secondary probe fails, keep the kill(0) answer.
            pass
    return True


def _terminate_reclaimed_worker(
    pid: Optional[int],
    claim_lock: Optional[str],
    *,
    signal_fn=None,
) -> dict[str, Any]:
    """Best-effort host-local worker termination for reclaim paths."""
    import signal

    info: dict[str, Any] = {
        "prev_pid": int(pid) if pid else None,
        "host_local": False,
        "termination_attempted": False,
        "terminated": False,
        "sigkill": False,
    }
    if not pid or pid <= 0 or not claim_lock:
        return info

    host_prefix = f"{_claimer_id().split(':', 1)[0]}:"
    if not str(claim_lock).startswith(host_prefix):
        return info
    info["host_local"] = True

    kill = signal_fn if signal_fn is not None else (
        os.kill if hasattr(os, "kill") else None
    )
    if kill is None:
        return info

    info["termination_attempted"] = True
    try:
        kill(int(pid), signal.SIGTERM)
    except (ProcessLookupError, OSError):
        return info

    for _ in range(10):
        if not _pid_alive(pid):
            info["terminated"] = True
            return info
        time.sleep(0.5)

    if _pid_alive(pid):
        try:
            # signal.SIGKILL doesn't exist on Windows; fall back to SIGTERM
            # (which maps to TerminateProcess via the stdlib shim).
            _sigkill = getattr(signal, "SIGKILL", signal.SIGTERM)
            kill(int(pid), _sigkill)
            info["sigkill"] = True
        except (ProcessLookupError, OSError):
            return info

    info["terminated"] = not _pid_alive(pid)
    return info


@_guarded_task_mutation(action="heartbeat_worker", capability=OLYMPUS_CAPABILITY_HEARTBEAT)
def heartbeat_worker(
    conn: sqlite3.Connection,
    task_id: str,
    *,
    note: Optional[str] = None,
    expected_run_id: Optional[int] = None,
) -> bool:
    """Record a ``heartbeat`` event + touch ``last_heartbeat_at``.

    Called by long-running workers as a liveness signal orthogonal to
    the PID check. A worker that forks a long-lived child (train loop,
    video encode, web crawl) can have its Python still alive while the
    actual work process is stuck; periodic heartbeats catch that.

    Returns True on success, False if the task is not in a state that
    should be heartbeating (not running, or claim expired).
    """
    now = int(time.time())
    with write_txn(conn):
        if expected_run_id is None:
            cur = conn.execute(
                "UPDATE tasks SET last_heartbeat_at = ? "
                "WHERE id = ? AND status = 'running'",
                (now, task_id),
            )
        else:
            cur = conn.execute(
                "UPDATE tasks SET last_heartbeat_at = ? "
                "WHERE id = ? AND status = 'running' AND current_run_id = ?",
                (now, task_id, int(expected_run_id)),
            )
        if cur.rowcount != 1:
            return False
        run_id = (
            int(expected_run_id)
            if expected_run_id is not None
            else _current_run_id(conn, task_id)
        )
        if run_id is not None:
            conn.execute(
                "UPDATE task_runs SET last_heartbeat_at = ? WHERE id = ?",
                (now, run_id),
            )
        _append_event(
            conn, task_id, "heartbeat",
            {"note": note} if note else None,
            run_id=run_id,
        )
    return True


def enforce_max_runtime(
    conn: sqlite3.Connection,
    *,
    signal_fn=None,
    olympus_auth: Optional[OlympusMutationAuth] = None,
) -> list[str]:
    """Terminate workers whose per-task ``max_runtime_seconds`` has elapsed.

    Sends SIGTERM, waits a short grace window, then SIGKILL. Emits a
    ``timed_out`` event and drops the task back to ``ready`` so the next
    dispatcher tick re-spawns it — unless the spawn-failure circuit
    breaker has already given up, in which case the task stays blocked
    where ``_record_spawn_failure`` parked it.

    Runs host-local: only tasks claimed by this host are candidates
    (same reasoning as ``detect_crashed_workers``). ``signal_fn`` is a
    test hook; defaults to ``os.kill`` on POSIX.
    """
    import signal
    timed_out: list[str] = []
    now = int(time.time())
    host_prefix = f"{_claimer_id().split(':', 1)[0]}:"

    rows = conn.execute(
        "SELECT t.id, t.worker_pid, "
        "       COALESCE(r.started_at, t.started_at) AS active_started_at, "
        "       t.max_runtime_seconds, t.claim_lock, t.current_run_id, "
        "       t.record_revision, t.olympus_context "
        "FROM tasks t "
        "LEFT JOIN task_runs r ON r.id = t.current_run_id "
        "WHERE t.status = 'running' AND t.max_runtime_seconds IS NOT NULL "
        "  AND COALESCE(r.started_at, t.started_at) IS NOT NULL "
        "  AND t.worker_pid IS NOT NULL"
    ).fetchall()
    for row in rows:
        lock = row["claim_lock"] or ""
        if not lock.startswith(host_prefix):
            continue
        # Runtime is per attempt, not lifetime-of-task. ``tasks.started_at``
        # intentionally records the first time a task ever started, so retries
        # must be measured from the active task_runs row when present.
        elapsed = now - int(row["active_started_at"])
        if elapsed < int(row["max_runtime_seconds"]):
            continue

        pid = int(row["worker_pid"])
        tid = row["id"]
        if row["olympus_context"] is not None:
            if row["current_run_id"] is None:
                continue
            try:
                state = _stage_execute_governed_recovery(
                    conn,
                    task_id=str(tid),
                    run_id=int(row["current_run_id"]),
                    reason=(
                        f"elapsed {int(elapsed)}s > limit "
                        f"{int(row['max_runtime_seconds'])}s"
                    ),
                    outcome="timed_out",
                    event_kind="timed_out",
                    olympus_auth=olympus_auth,
                    signal_fn=signal_fn,
                )
            except OlympusContextError:
                state = None
            if state is not None:
                timed_out.append(str(tid))
            continue
        try:
            with write_txn(conn):
                _authorize_task_mutation(
                    conn,
                    tid,
                    action="enforce_max_runtime",
                    capability=OLYMPUS_CAPABILITY_RECOVER,
                    auth=olympus_auth,
                )
                current = conn.execute(
                    "SELECT status, claim_lock, worker_pid, current_run_id, "
                    "record_revision FROM tasks WHERE id = ?",
                    (tid,),
                ).fetchone()
                if current is None or any((
                    current["status"] != "running",
                    current["claim_lock"] != row["claim_lock"],
                    current["worker_pid"] != row["worker_pid"],
                    current["current_run_id"] != row["current_run_id"],
                    int(current["record_revision"]) != int(row["record_revision"]),
                )):
                    continue
                # Signal while the exact authorized row snapshot is protected
                # by BEGIN IMMEDIATE. A replacement claim cannot acquire the
                # row until this transaction commits.
                killed = False
                kill = signal_fn if signal_fn is not None else (
                    os.kill if hasattr(os, "kill") else None
                )
                if kill is not None:
                    try:
                        kill(pid, signal.SIGTERM)
                    except (ProcessLookupError, OSError):
                        pass
                    for _ in range(10):
                        if not _pid_alive(pid):
                            break
                        time.sleep(0.5)
                    if _pid_alive(pid):
                        try:
                            _sigkill = getattr(signal, "SIGKILL", signal.SIGTERM)
                            kill(pid, _sigkill)
                            killed = True
                        except (ProcessLookupError, OSError):
                            pass
                cur = conn.execute(
                    "UPDATE tasks SET status = 'ready', claim_lock = NULL, "
                    "claim_expires = NULL, worker_pid = NULL, "
                    "last_heartbeat_at = NULL "
                    "WHERE id = ? AND status = 'running' "
                    "AND claim_lock IS ? AND worker_pid IS ? "
                    "AND current_run_id IS ? AND record_revision = ?",
                    (
                        tid, row["claim_lock"], row["worker_pid"],
                        row["current_run_id"], row["record_revision"],
                    ),
                )
                if cur.rowcount == 1:
                    payload = {
                        "pid": pid,
                        "elapsed_seconds": int(elapsed),
                        "limit_seconds": int(row["max_runtime_seconds"]),
                        "sigkill": killed,
                    }
                    run_id = _end_run(
                    conn, tid,
                    outcome="timed_out", status="timed_out",
                    error=f"elapsed {int(elapsed)}s > limit {int(row['max_runtime_seconds'])}s",
                    metadata=payload,
                )
                    _append_event(
                    conn, tid, "timed_out", payload, run_id=run_id,
                )
                    timed_out.append(tid)
        except OlympusContextError as exc:
            with write_txn(conn):
                _append_event(
                    conn,
                    tid,
                    "authority_contained",
                    {"reason": exc.reason, "pid": pid, "recovery": "max_runtime"},
                    run_id=_current_run_id(conn, tid),
                )
            continue
        # Increment the unified failure counter. Outside the write_txn
        # above because ``_record_task_failure`` opens its own. If the
        # breaker trips, this flips the task ``ready → blocked`` and
        # emits a ``gave_up`` event on top of the ``timed_out`` we
        # already emitted.
        if cur.rowcount == 1:
            _record_task_failure(
                conn, tid,
                error=f"elapsed {int(elapsed)}s > limit {int(row['max_runtime_seconds'])}s",
                outcome="timed_out",
                release_claim=False,
                end_run=False,
                event_payload_extra={"pid": pid, "sigkill": killed},
                olympus_auth=olympus_auth,
            )
    return timed_out


# Heartbeat staleness heartbeat gap — if a running task hasn't sent a
# heartbeat in this many seconds it's considered inactive regardless of
# the ``dispatch_stale_timeout_seconds`` threshold.  Hardcoded at 1 hour
# to match the original spec (">4h started + no commits in 1h").
_STALE_HEARTBEAT_GAP_SECONDS = 3600


def detect_stale_running(
    conn: sqlite3.Connection,
    *,
    stale_timeout_seconds: int = 0,
    signal_fn=None,
    olympus_auth: Optional[OlympusMutationAuth] = None,
) -> list[str]:
    """Reclaim ``running`` tasks that show no progress (heartbeat) within the
    staleness window.

    A task is considered stale when BOTH of these hold:

    1. It has been running for longer than ``stale_timeout_seconds``
       (measured from the active run's ``started_at``, falling back to
       ``tasks.started_at`` on older runs).
    2. Its ``last_heartbeat_at`` is older than
       ``_STALE_HEARTBEAT_GAP_SECONDS`` (or NULL — never sent a heartbeat).

    On reclaim the task is reset to ``ready``, the run is closed with
    ``outcome='stale'``, and the host-local worker (if still running) is
    terminated.

    Only considers ``status='running'`` tasks. Blocked tasks are never
    candidates.  Returns the list of reclaimed task IDs.

    ``stale_timeout_seconds=0`` disables the check entirely (returns ``[]``
    immediately).  ``signal_fn`` is a test hook; defaults to ``os.kill``
    on POSIX.
    """
    if stale_timeout_seconds <= 0:
        return []


    now = int(time.time())
    host_prefix = f"{_claimer_id().split(':', 1)[0]}:"
    reclaimed: list[str] = []

    rows = conn.execute(
        "SELECT t.id, t.worker_pid, t.last_heartbeat_at, t.claim_lock, "
        "       t.current_run_id, t.record_revision, t.olympus_context, "
        "       COALESCE(r.started_at, t.started_at) AS active_started_at "
        "FROM tasks t "
        "LEFT JOIN task_runs r ON r.id = t.current_run_id "
        "WHERE t.status = 'running'"
    ).fetchall()

    for row in rows:
        # Skip if no started_at (shouldn't happen for running, but be safe).
        if row["active_started_at"] is None:
            continue

        elapsed = now - int(row["active_started_at"])
        if elapsed < stale_timeout_seconds:
            continue  # not old enough to check

        last_hb = row["last_heartbeat_at"]
        hb_age = (now - int(last_hb)) if last_hb is not None else None
        if hb_age is not None and hb_age < _STALE_HEARTBEAT_GAP_SECONDS:
            continue  # recent heartbeat → still alive

        pid = row["worker_pid"]
        tid = row["id"]
        lock = row["claim_lock"] or ""

        if row["olympus_context"] is not None:
            if row["current_run_id"] is None:
                continue
            try:
                state = _stage_execute_governed_recovery(
                    conn,
                    task_id=str(tid),
                    run_id=int(row["current_run_id"]),
                    reason=(
                        f"no heartbeat for {int(hb_age)}s"
                        if hb_age is not None else "no heartbeat ever"
                    ) + f" after {int(elapsed)}s running",
                    outcome="stale",
                    event_kind="stale",
                    olympus_auth=olympus_auth,
                    signal_fn=signal_fn,
                )
            except OlympusContextError:
                state = None
            if state is not None:
                reclaimed.append(str(tid))
            continue

        try:
            with write_txn(conn):
                _authorize_task_mutation(
                    conn,
                    tid,
                    action="recover_stale_running",
                    capability=OLYMPUS_CAPABILITY_RECOVER,
                    auth=olympus_auth,
                )
                current = conn.execute(
                    "SELECT status, claim_lock, worker_pid, current_run_id, "
                    "record_revision FROM tasks WHERE id = ?",
                    (tid,),
                ).fetchone()
                if current is None or any((
                    current["status"] != "running",
                    current["claim_lock"] != row["claim_lock"],
                    current["worker_pid"] != row["worker_pid"],
                    current["current_run_id"] != row["current_run_id"],
                    int(current["record_revision"]) != int(row["record_revision"]),
                )):
                    continue
                termination = _terminate_reclaimed_worker(
                    current["worker_pid"],
                    current["claim_lock"],
                    signal_fn=signal_fn,
                )
                cur = conn.execute(
                    "UPDATE tasks SET status = 'ready', claim_lock = NULL, "
                    "claim_expires = NULL, worker_pid = NULL, "
                    "last_heartbeat_at = NULL "
                    "WHERE id = ? AND status = 'running' "
                    "AND claim_lock IS ? AND worker_pid IS ? "
                    "AND current_run_id IS ? AND record_revision = ?",
                    (
                        tid, row["claim_lock"], row["worker_pid"],
                        row["current_run_id"], row["record_revision"],
                    ),
                )
                if cur.rowcount != 1:
                    continue

                payload = {
                    "elapsed_seconds": int(elapsed),
                    "last_heartbeat_at": (
                        int(last_hb) if last_hb is not None else None
                    ),
                    "heartbeat_age_seconds": (
                        int(hb_age) if hb_age is not None else None
                    ),
                    "timeout_seconds": stale_timeout_seconds,
                    "pid": int(pid) if pid else None,
                }
                payload.update(termination)

                run_id = _end_run(
                conn, tid,
                outcome="stale", status="stale",
                error=(
                    f"no heartbeat for {int(hb_age)}s "
                    if hb_age is not None
                    else "no heartbeat ever"
                ) + f" after {int(elapsed)}s running",
                metadata=payload,
            )
                _append_event(
                conn, tid, "stale", payload, run_id=run_id,
            )
                reclaimed.append(tid)
        except OlympusContextError as exc:
            with write_txn(conn):
                _append_event(
                    conn,
                    tid,
                    "authority_contained",
                    {"reason": exc.reason, "recovery": "stale_running"},
                    run_id=_current_run_id(conn, tid),
                )
            continue

        # Intentionally NOT calling _record_task_failure here. Stale reclaim
        # is dispatcher-side detection of an absent heartbeat; the task is
        # going straight back to ``ready`` for re-dispatch. Counting it as
        # a worker failure would let two legitimately-long-running tasks
        # (>4h without explicit heartbeat) trip the circuit breaker and
        # auto-block, even though no worker actually failed. The 'stale'
        # event already lives in task_events for auditability; that's the
        # right surface for "this happened" without conflating with the
        # spawn_failed / timed_out / crashed counters.

    return reclaimed


def _error_fingerprint(error_text: str) -> str:
    """Normalize an error message for grouping identical failures.

    Strips host-specific details (PIDs, timestamps) so that errors
    with the same root cause produce the same fingerprint.
    """
    fp = re.sub(r'\bpid \d+\b', 'pid N', error_text[:80])
    fp = re.sub(r'\b\d{10,}\b', '<TS>', fp)
    return fp.lower().strip()


def detect_crashed_workers(
    conn: sqlite3.Connection,
    *,
    olympus_auth: Optional[OlympusMutationAuth] = None,
) -> list[str]:
    """Reclaim ``running`` tasks whose worker PID is no longer alive.

    Appends a ``crashed`` event and drops the task back to ``ready``.
    Different from ``release_stale_claims``: this checks liveness
    immediately rather than waiting for the claim TTL.

    Only considers tasks claimed by *this host* — PIDs from other hosts
    are meaningless here. The host-local check is enough because
    ``_default_spawn`` always runs the worker on the same host as the
    dispatcher (the whole design is single-host).

    When the reap registry shows the worker exited cleanly (rc=0) but
    the task was still ``running`` in the DB, treat it as a protocol
    violation (worker answered conversationally without calling
    ``kanban_complete`` / ``kanban_block``) and trip the circuit breaker
    on the first occurrence — retrying a worker whose CLI keeps
    returning 0 without a terminal transition just loops forever.

    When the reap registry shows the worker exited with the rate-limit
    sentinel (``KANBAN_RATE_LIMIT_EXIT_CODE``), the worker bailed on a
    provider quota wall, NOT a task failure. Such tasks are released back
    to ``ready`` WITHOUT counting a failure (so a long quota window can't
    trip the breaker) and stamped with a quota-blocker error so
    ``check_respawn_guard`` defers their respawn until the window clears.
    The ids are returned via the ``_last_rate_limited`` function attribute
    (the public return stays the crashed-only ``list[str]``).
    """
    crashed: list[str] = []
    rate_limited: list[str] = []
    host_prefix = f"{_claimer_id().split(':', 1)[0]}:"

    # Governed workers are never recovered by PID liveness plus an in-place
    # task update. First compare the live process to the exact registered
    # host/boot/PID/birth token, then stage a durable termination/containment
    # effect. Effect execution and settlement happen after the staging
    # transaction and each performs its own canonical verification.
    governed_rows = conn.execute(
        "SELECT t.id, t.worker_pid, t.claim_lock, t.current_run_id, "
        "COALESCE(r.started_at,t.started_at) AS active_started_at, "
        "r.process_state, r.worker_host_id, r.worker_boot_id, "
        "r.worker_start_token "
        "FROM tasks t LEFT JOIN task_runs r ON r.id=t.current_run_id "
        "WHERE t.status='running' AND t.worker_pid IS NOT NULL "
        "AND t.olympus_context IS NOT NULL"
    ).fetchall()
    for row in governed_rows:
        lock = str(row["claim_lock"] or "")
        if not lock.startswith(host_prefix) or row["current_run_id"] is None:
            continue
        started_at = row["active_started_at"]
        if started_at is not None \
                and time.time() - int(started_at) < _resolve_crash_grace_seconds():
            continue
        stored = ProcessIdentity(
            host_id=str(row["worker_host_id"] or ""),
            boot_id=str(row["worker_boot_id"] or ""),
            pid=int(row["worker_pid"] or 0),
            start_token=str(row["worker_start_token"] or ""),
        )
        if (
            row["process_state"] != "registered"
            or not all((stored.host_id, stored.boot_id, stored.start_token))
            or stored.pid <= 0
        ):
            continue
        live = read_process_identity(stored.pid)
        if live == stored:
            continue
        kind, code = _classify_worker_exit(stored.pid)
        reason = (
            f"registered process identity changed for pid {stored.pid}"
            if live is not None
            else (
                f"registered worker exited ({kind}:{code})"
                if code is not None else "registered worker is no longer live"
            )
        )
        try:
            state = _stage_execute_governed_recovery(
                conn,
                task_id=str(row["id"]),
                run_id=int(row["current_run_id"]),
                reason=reason,
                outcome="crashed",
                event_kind="crashed",
                olympus_auth=olympus_auth,
            )
        except OlympusContextError:
            state = None
        if state is not None:
            crashed.append(str(row["id"]))
    # Per-crash details collected inside the main txn, used after it
    # closes to run ``_record_task_failure`` (which needs its own
    # write_txn so can't nest). ``protocol_violation`` flags the
    # clean-exit-but-still-running case so we can trip the breaker
    # immediately instead of incrementing by 1.
    crash_details: list[tuple[str, int, str, bool, str]] = []
    # (task_id, pid, claimer, protocol_violation, error_text)
    with write_txn(conn):
        rows = conn.execute(
            "SELECT id, worker_pid, claim_lock, started_at FROM tasks "
            "WHERE status = 'running' AND worker_pid IS NOT NULL "
            "AND olympus_context IS NULL"
        ).fetchall()
        for row in rows:
            # Only check liveness for claims owned by this host.
            lock = row["claim_lock"] or ""
            if not lock.startswith(host_prefix):
                continue
            # Skip liveness check inside the launch-window grace period
            # so a freshly-spawned worker isn't reclaimed before its PID
            # is visible on /proc.
            started_at = row["started_at"] if "started_at" in row.keys() else None
            if started_at is not None:
                grace = _resolve_crash_grace_seconds()
                if time.time() - started_at < grace:
                    continue
            if _pid_alive(row["worker_pid"]):
                continue

            pid = int(row["worker_pid"])
            kind, code = _classify_worker_exit(pid)
            rate_limited_exit = False
            if kind == "clean_exit":
                # Worker subprocess returned 0 but its task is still
                # ``running`` in the DB — it exited without calling
                # ``kanban_complete`` / ``kanban_block``. Retrying won't
                # help.
                protocol_violation = True
                error_text = (
                    "worker exited cleanly (rc=0) without calling "
                    "kanban_complete or kanban_block — protocol violation"
                )
                event_kind = "protocol_violation"
                event_payload = {
                    "pid": pid,
                    "claimer": row["claim_lock"],
                    "exit_code": code,
                }
            elif kind == "rate_limited":
                # Worker bailed because the provider rate-limited / exhausted
                # quota (EX_TEMPFAIL sentinel). This is NOT a task failure —
                # the task is fine, the account just hit a wall. Release it
                # back to ``ready`` so the respawn guard defers it until the
                # quota window clears, and crucially do NOT count a failure
                # (skip ``_record_task_failure``) so a long quota window can't
                # trip the circuit breaker and permanently block the card.
                protocol_violation = False
                rate_limited_exit = True
                error_text = (
                    f"pid {pid} exited rate-limited (quota wall) — "
                    f"requeued without counting a failure"
                )
                event_kind = "rate_limited"
                event_payload = {
                    "pid": pid,
                    "claimer": row["claim_lock"],
                    "exit_code": code,
                }
            else:
                protocol_violation = False
                if kind == "nonzero_exit":
                    error_text = f"pid {pid} exited with code {code}"
                elif kind == "signaled":
                    error_text = f"pid {pid} killed by signal {code}"
                else:
                    error_text = f"pid {pid} not alive"
                event_kind = "crashed"
                event_payload = {"pid": pid, "claimer": row["claim_lock"]}
                if code is not None and kind != "unknown":
                    event_payload["exit_kind"] = kind
                    event_payload["exit_code"] = code

            try:
                _authorize_task_mutation(
                    conn,
                    row["id"],
                    action="recover_crashed_worker",
                    capability=OLYMPUS_CAPABILITY_RECOVER,
                    auth=olympus_auth,
                )
            except OlympusContextError as exc:
                _append_event(
                    conn,
                    row["id"],
                    "authority_contained",
                    {"reason": exc.reason, "pid": pid, "recovery": "crashed"},
                    run_id=_current_run_id(conn, row["id"]),
                )
                continue

            cur = conn.execute(
                "UPDATE tasks SET status = 'ready', claim_lock = NULL, "
                "claim_expires = NULL, worker_pid = NULL "
                "WHERE id = ? AND status = 'running'",
                (row["id"],),
            )
            if cur.rowcount == 1:
                # Rate-limited requeues are a clean release, not a crash —
                # record the run outcome as ``rate_limited`` so the board
                # history doesn't show a phantom crash for a quota wall.
                _run_outcome = "rate_limited" if rate_limited_exit else "crashed"
                run_id = _end_run(
                    conn, row["id"],
                    outcome=_run_outcome, status=_run_outcome,
                    error=error_text,
                    metadata=dict(event_payload),
                )
                _append_event(
                    conn, row["id"], event_kind,
                    event_payload,
                    run_id=run_id,
                )
                if rate_limited_exit:
                    # Stamp the failure-error column so ``check_respawn_guard``
                    # recognizes this as a quota blocker and defers the
                    # respawn until the window clears — WITHOUT touching
                    # ``consecutive_failures`` (that's the whole point: no
                    # breaker trip on a throttle).
                    conn.execute(
                        "UPDATE tasks SET last_failure_error = ? WHERE id = ?",
                        (error_text[:500], row["id"]),
                    )
                    rate_limited.append(row["id"])
                else:
                    crashed.append(row["id"])
                    crash_details.append(
                        (row["id"], pid, row["claim_lock"],
                         protocol_violation, error_text)
                    )
    # Outside the main txn: increment the unified failure counter for
    # each crashed task. If the breaker trips, the task transitions
    # ready → blocked with a ``gave_up`` event on top of the ``crashed``
    # event we already emitted.
    #
    # Protocol-violation crashes force an immediate trip (failure_limit=1)
    # because clean-exit-without-transition is deterministic: the next
    # respawn will do exactly the same thing. Better to surface to a
    # human with a clear reason than to loop ``DEFAULT_FAILURE_LIMIT``
    # times first.
    auto_blocked: list[str] = []
    if crash_details:
        # Fingerprint errors to detect systemic failures.
        _fp_counts: dict[str, int] = {}
        for _, _, _, _, err_text in crash_details:
            fp = _error_fingerprint(err_text)
            _fp_counts[fp] = _fp_counts.get(fp, 0) + 1
        for tid, pid, claimer, protocol_violation, error_text in crash_details:
            fp = _error_fingerprint(error_text)
            is_systemic = (
                not protocol_violation
                and _fp_counts.get(fp, 0) >= 3
            )
            tripped = _record_task_failure(
                conn, tid,
                error=error_text,
                outcome="crashed",
                failure_limit=1 if (protocol_violation or is_systemic) else None,
                release_claim=False,
                end_run=False,
                event_payload_extra={"pid": pid, "claimer": claimer},
                olympus_auth=olympus_auth,
            )
            if tripped:
                auto_blocked.append(tid)
    # Stash auto-blocked ids on the function for the dispatch loop to pick up.
    # Keeps the public return type (``list[str]``) stable for direct callers
    # and tests that destructure the result; ``dispatch_once`` reads this
    # side-channel attribute to populate ``DispatchResult.auto_blocked``.
    detect_crashed_workers._last_auto_blocked = auto_blocked  # type: ignore[attr-defined]
    # Same side-channel for rate-limited requeues — these did NOT count a
    # failure and are NOT crashes, so they stay out of the ``crashed`` return.
    detect_crashed_workers._last_rate_limited = rate_limited  # type: ignore[attr-defined]
    return crashed


@_guarded_task_mutation(
    action="record_failure",
    capability=OLYMPUS_CAPABILITY_RECOVER,
)
def _record_task_failure(
    conn: sqlite3.Connection,
    task_id: str,
    error: str,
    *,
    outcome: str,
    failure_limit: int = None,
    release_claim: bool = False,
    end_run: bool = False,
    event_payload_extra: Optional[dict] = None,
) -> bool:
    """Record a non-success outcome (spawn_failed / crashed / timed_out)
    and maybe trip the circuit breaker.

    Unified replacement for the old spawn-only ``_record_spawn_failure``.
    Every path that ends a task with a non-success outcome funnels
    through here so the ``consecutive_failures`` counter and the
    auto-block threshold stay consistent.

    Returns True when the task was auto-blocked (counter reached
    ``failure_limit``), False when it was just updated in place.

    Modes:

    * ``release_claim=True, end_run=True`` — spawn-failure path.
      Caller has a running task with an open run; this transitions
      it back to ``ready`` (or ``blocked`` when the breaker trips),
      releases the claim, and closes the run with ``outcome=<outcome>``.

    * ``release_claim=False, end_run=False`` — timeout/crash path.
      Caller has ALREADY flipped the task to ``ready`` and closed the
      run with the appropriate outcome. This just increments the
      counter; if the breaker trips, the task is re-transitioned
      ``ready → blocked`` and a ``gave_up`` event is emitted.

    ``event_payload_extra`` merges into the ``gave_up`` event payload
    when the breaker trips, so callers can include outcome-specific
    context (e.g. pid on crash, elapsed on timeout).

    Resolution order for the effective threshold:
      1. per-task ``max_retries`` if set (nothing else overrides)
      2. caller-supplied ``failure_limit`` (gateway passes the config
         value from ``kanban.failure_limit``; tests pass fixed values)
      3. ``DEFAULT_FAILURE_LIMIT``
    """
    if failure_limit is None:
        failure_limit = DEFAULT_FAILURE_LIMIT
    blocked = False
    with write_txn(conn):
        row = conn.execute(
            "SELECT consecutive_failures, status, max_retries "
            "FROM tasks WHERE id = ?", (task_id,),
        ).fetchone()
        if row is None:
            return False
        failures = int(row["consecutive_failures"]) + 1
        cur_status = row["status"]

        # Per-task override wins over both caller-supplied and default
        # thresholds. None (the common case) falls through.
        task_override = (
            row["max_retries"] if "max_retries" in row.keys() else None
        )
        if task_override is not None:
            effective_limit = int(task_override)
            limit_source = "task"
        else:
            effective_limit = int(failure_limit)
            limit_source = "dispatcher"

        if failures >= effective_limit:
            # Trip the breaker.
            if release_claim:
                # Spawn path: still running, also clear claim state.
                conn.execute(
                    "UPDATE tasks SET status = 'blocked', claim_lock = NULL, "
                    "claim_expires = NULL, worker_pid = NULL, "
                    "consecutive_failures = ?, last_failure_error = ? "
                    "WHERE id = ? AND status IN ('running', 'ready')",
                    (failures, error[:500], task_id),
                )
            else:
                # Timeout/crash path: task is already at ``ready``
                # with claim cleared; just flip to blocked + update
                # counter fields.
                conn.execute(
                    "UPDATE tasks SET status = 'blocked', "
                    "consecutive_failures = ?, last_failure_error = ? "
                    "WHERE id = ? AND status IN ('ready', 'running')",
                    (failures, error[:500], task_id),
                )
            run_id = None
            if end_run:
                # Only the spawn path has an open run to close.
                run_id = _end_run(
                    conn, task_id,
                    outcome="gave_up", status="gave_up",
                    error=error[:500],
                    metadata={
                        "failures": failures,
                        "trigger_outcome": outcome,
                        "effective_limit": effective_limit,
                        "limit_source": limit_source,
                    },
                )
            payload = {
                "failures": failures,
                "effective_limit": effective_limit,
                "limit_source": limit_source,
                "error": error[:500],
                "trigger_outcome": outcome,
            }
            if event_payload_extra:
                payload.update(event_payload_extra)
            _append_event(
                conn, task_id, "gave_up", payload, run_id=run_id,
            )
            blocked = True
        else:
            # Below threshold.
            if release_claim:
                # Spawn path: transition running → ready + clear claim.
                conn.execute(
                    "UPDATE tasks SET status = 'ready', claim_lock = NULL, "
                    "claim_expires = NULL, worker_pid = NULL, "
                    "consecutive_failures = ?, last_failure_error = ? "
                    "WHERE id = ? AND status = 'running'",
                    (failures, error[:500], task_id),
                )
            else:
                # Timeout/crash path: task is already at ``ready`` via
                # its own UPDATE. Just bookkeep the counter + last error.
                conn.execute(
                    "UPDATE tasks SET consecutive_failures = ?, "
                    "last_failure_error = ? WHERE id = ?",
                    (failures, error[:500], task_id),
                )
            if end_run:
                # Spawn path: close the open run with outcome.
                run_id = _end_run(
                    conn, task_id,
                    outcome=outcome, status=outcome,
                    error=error[:500],
                    metadata={"failures": failures},
                )
                _append_event(
                    conn, task_id, outcome,
                    {"error": error[:500], "failures": failures},
                    run_id=run_id,
                )
            # Timeout/crash path's caller already emitted its own event.
    return blocked


# Backward-compat alias. Old name is referenced from tests and possibly
# third-party callers. New code should call ``_record_task_failure``.
def _record_spawn_failure(
    conn: sqlite3.Connection,
    task_id: str,
    error: str,
    *,
    failure_limit: int = None,
    olympus_auth: Optional[OlympusMutationAuth] = None,
) -> bool:
    return _record_task_failure(
        conn, task_id, error,
        outcome="spawn_failed",
        failure_limit=failure_limit,
        release_claim=True,
        end_run=True,
        olympus_auth=olympus_auth,
    )


@_guarded_task_mutation(action="set_worker_pid", capability=OLYMPUS_CAPABILITY_CLAIM)
def _set_worker_pid(conn: sqlite3.Connection, task_id: str, pid: int) -> None:
    """Record the spawned child's pid + emit a ``spawned`` event.

    The event's payload carries the pid so a human reading ``hermes kanban
    tail`` can correlate log lines with OS-level traces without opening
    the drawer.
    """
    with write_txn(conn):
        conn.execute(
            "UPDATE tasks SET worker_pid = ? WHERE id = ?",
            (int(pid), task_id),
        )
        run_id = _current_run_id(conn, task_id)
        if run_id is not None:
            conn.execute(
                "UPDATE task_runs SET worker_pid = ? WHERE id = ?",
                (int(pid), run_id),
            )
        _append_event(conn, task_id, "spawned", {"pid": int(pid)}, run_id=run_id)


def _clear_failure_counter(conn: sqlite3.Connection, task_id: str) -> None:
    """Reset the unified consecutive-failures counter.

    Called from ``complete_task`` on successful completion — a fresh
    success means the task + profile combination is working and any
    past failures are history. NOT called on spawn success anymore:
    a successful spawn proves the worker could start but says nothing
    about whether the run will succeed, so we need to let timeouts and
    crashes accumulate across spawn boundaries.
    """
    with write_txn(conn):
        conn.execute(
            "UPDATE tasks SET consecutive_failures = 0, "
            "last_failure_error = NULL WHERE id = ?",
            (task_id,),
        )


# Legacy alias for test-code and anything else that still imports it.
_clear_spawn_failures = _clear_failure_counter


def check_respawn_guard(conn: sqlite3.Connection, task_id: str) -> Optional[str]:
    """Return a guard reason if ``task_id`` should NOT be re-spawned, else None.

    Called per ready task in ``dispatch_once`` before any claim attempt.
    Returning a reason defers the spawn this tick; the task stays in
    ``ready`` and gets another chance on the next dispatcher tick.

    Checks in priority order:

    ``"rate_limit_cooldown"``
        The task's most recent run ended with the ``rate_limited`` outcome
        (a worker bailed on a provider quota wall via the EX_TEMPFAIL
        sentinel) within ``_resolve_rate_limit_cooldown_seconds()``. The
        quota almost certainly hasn't reset yet, so defer the respawn until
        the cooldown elapses — then allow a cheap probe. This is checked
        BEFORE ``blocker_auth`` because the rate-limit requeue stamps a
        quota-flavored ``last_failure_error`` that would otherwise match the
        auth-blocker regex and park the task forever (the rate-limit path
        never increments ``consecutive_failures``, so the breaker can't free
        it). Once the cooldown elapses the task falls through and respawns.

    ``"blocker_auth"``
        The task's last failure error matches a quota / authentication
        pattern. Retrying immediately is unlikely to help (rate limits
        reset on a timer; auth needs human action), so we defer to the
        next tick. The existing ``consecutive_failures`` counter still
        trips the auto-block circuit breaker after ``failure_limit``
        consecutive failures, so a persistent auth error eventually
        blocks via the normal path — but a transient 429 gets a few
        ticks of recovery first.

    ``"recent_success"``
        A completed run exists within ``_RESPAWN_GUARD_SUCCESS_WINDOW``
        seconds.  Useful work already succeeded for this task; wait for
        human review rather than immediately re-spawning.

    ``"active_pr"``
        A GitHub PR URL appears in a recent task comment (within
        ``_RESPAWN_GUARD_PR_WINDOW`` seconds).  A prior worker already
        opened a PR; re-spawning risks a duplicate PR on the same task.

    Stale / dead claim locks are NOT a guard reason — they are handled
    by ``release_stale_claims`` and ``detect_crashed_workers`` which
    reset the task to ``ready`` only after verifying the lock is
    genuinely dead (no live PID on this host).
    """
    row = conn.execute(
        "SELECT last_failure_error FROM tasks WHERE id = ?",
        (task_id,),
    ).fetchone()
    if row is None:
        return None

    now = int(time.time())

    # 1. Rate-limit cooldown. The most recent run ended ``rate_limited``
    #    (quota wall) — defer while inside the cooldown window, then allow a
    #    cheap probe. Must run BEFORE the blocker_auth regex check, because a
    #    rate-limit requeue stamps a quota-flavored last_failure_error that
    #    the regex would otherwise match → defer forever (no failure counter
    #    increment on this path means the breaker can never free it).
    #
    #    We look at the LATEST run only (ORDER BY ended_at DESC LIMIT 1): if a
    #    newer crash/completion superseded the rate-limit run, this guard
    #    no longer applies and the normal paths take over.
    rl_cooldown = _resolve_rate_limit_cooldown_seconds()
    latest_run = conn.execute(
        "SELECT outcome, ended_at FROM task_runs "
        "WHERE task_id = ? AND ended_at IS NOT NULL "
        "ORDER BY ended_at DESC LIMIT 1",
        (task_id,),
    ).fetchone()
    if (
        latest_run is not None
        and latest_run["outcome"] == "rate_limited"
    ):
        if rl_cooldown <= 0:
            # Cooldown disabled — respawn immediately, and skip the
            # blocker_auth regex so the stamped rate-limit text doesn't
            # re-trap the task.
            return None
        ended_at = latest_run["ended_at"]
        if ended_at is not None and (now - int(ended_at)) < rl_cooldown:
            return "rate_limit_cooldown"
        # Cooldown elapsed — allow the respawn. Return early so the
        # blocker_auth check below doesn't catch the rate-limit text we
        # stamped on the task; this path intentionally retries forever
        # (cheaply, spaced by the cooldown) until quota returns or a real
        # crash/completion supersedes it.
        return None

    # 2. Quota / auth blocker: retrying immediately will not help.
    err = row["last_failure_error"]
    if err and _RESPAWN_BLOCKER_RE.search(err):
        return "blocker_auth"

    # 3. Completed run within guard window — proof of recent success.
    cutoff = now - _RESPAWN_GUARD_SUCCESS_WINDOW
    if conn.execute(
        "SELECT id FROM task_runs "
        "WHERE task_id = ? AND outcome = 'completed' AND ended_at >= ?",
        (task_id, cutoff),
    ).fetchone():
        return "recent_success"

    # 4. GitHub PR URL in a recent comment — prior worker already opened a PR.
    pr_cutoff = now - _RESPAWN_GUARD_PR_WINDOW
    for c in conn.execute(
        "SELECT body FROM task_comments WHERE task_id = ? AND created_at >= ?",
        (task_id, pr_cutoff),
    ).fetchall():
        if c["body"] and _RESPAWN_GUARD_PR_URL_RE.search(c["body"]):
            return "active_pr"

    return None


def has_spawnable_ready(conn: sqlite3.Connection) -> bool:
    """Return True iff there is at least one ready+assigned+unclaimed task
    whose assignee maps to a real Hermes profile.

    Used by the gateway- and CLI-embedded dispatchers' health telemetry to
    decide whether ``0 spawned`` is a "stuck" condition (real spawnable
    work waiting) or a "correctly idle" condition (only control-plane
    lanes like ``orion-cc`` / ``orion-research`` waiting on terminals
    that pull tasks via ``claim_task`` directly).

    Falls back to "any ready+assigned" if ``profile_exists`` is not
    importable (e.g. partial install) — preserves the old behavior so
    the warning still fires in degraded environments.
    """
    rows = conn.execute(
        "SELECT DISTINCT assignee FROM tasks "
        "WHERE status = 'ready' AND assignee IS NOT NULL "
        "    AND claim_lock IS NULL"
    ).fetchall()
    if not rows:
        return False
    try:
        from hermes_cli.profiles import profile_exists  # local import: avoids cycle
    except Exception:
        # Can't introspect — assume spawnable, preserve legacy behavior.
        return True
    for row in rows:
        if profile_exists(row["assignee"]):
            return True
    return False


def has_spawnable_review(conn: sqlite3.Connection) -> bool:
    """Return True iff there is at least one review+assigned+unclaimed task
    whose assignee maps to a real Hermes profile.

    Mirror of :func:`has_spawnable_ready` for the review column —
    used by the health telemetry to decide whether the dispatcher
    should have spawned a review agent.
    """
    rows = conn.execute(
        "SELECT DISTINCT assignee FROM tasks "
        "WHERE status = 'review' AND assignee IS NOT NULL "
        "    AND claim_lock IS NULL"
    ).fetchall()
    if not rows:
        return False
    try:
        from hermes_cli.profiles import profile_exists  # local import: avoids cycle
    except Exception:
        return True
    for row in rows:
        if profile_exists(row["assignee"]):
            return True
    return False


@_guarded_task_mutation(
    action="release_unspawned_claim",
    capability=OLYMPUS_CAPABILITY_RECOVER,
)
def _release_unspawned_claim(
    conn: sqlite3.Connection,
    task_id: str,
    *,
    claim_lock: Optional[str],
) -> bool:
    """Release a claim that failed its final pre-spawn authority check."""
    with write_txn(conn):
        cur = conn.execute(
            "UPDATE tasks SET status = 'ready', claim_lock = NULL, "
            "claim_expires = NULL, worker_pid = NULL "
            "WHERE id = ? AND status = 'running' AND claim_lock IS ? "
            "AND worker_pid IS NULL",
            (task_id, claim_lock),
        )
        if cur.rowcount != 1:
            return False
        run_id = _end_run(
            conn,
            task_id,
            outcome="reclaimed",
            status="reclaimed",
            error="authority validation failed before worker spawn",
        )
        _append_event(
            conn,
            task_id,
            "spawn_rejected",
            {"reason": "authority_changed_before_spawn", "governance": "olympus"},
            run_id=run_id,
        )
        return True


def dispatch_once(
    conn: sqlite3.Connection,
    *,
    spawn_fn=None,
    ttl_seconds: Optional[int] = None,
    dry_run: bool = False,
    max_spawn: Optional[int] = None,
    max_in_progress: Optional[int] = None,
    failure_limit: int = DEFAULT_SPAWN_FAILURE_LIMIT,
    stale_timeout_seconds: int = 0,
    board: Optional[str] = None,
    default_assignee: Optional[str] = None,
    max_in_progress_per_profile: Optional[int] = None,
    olympus_auth: Optional[OlympusMutationAuth] = None,
    dispatcher_instance_id: Optional[str] = None,
) -> DispatchResult:
    """Run one dispatcher tick.

    Steps:
      1. Reclaim stale running tasks (TTL expired).
      2. Reclaim stale running tasks (no recent heartbeat).
      3. Reclaim crashed running tasks (host-local PID no longer alive).
      3. Promote todo -> ready where all parents are done.
      4. For each ready task with an assignee, atomically claim and call
         ``spawn_fn(task, workspace_path, board) -> Optional[int]``. The
         return value (if any) is recorded as ``worker_pid`` so subsequent
         ticks can detect crashes before the TTL expires.

    Spawn failures are counted per-task. After ``failure_limit`` consecutive
    failures the task is auto-blocked with the last error as its reason —
    prevents the dispatcher from thrashing forever on an unfixable task.

    ``max_spawn`` is a **live concurrency cap**, not a per-tick spawn budget:
    it counts tasks already in ``status='running'`` plus this tick's spawns
    against the limit. So ``max_spawn=4`` means "at most 4 workers running
    at any time across the whole board" — matching the gateway's stated
    intent ("limit concurrent kanban tasks"). With a per-tick interpretation
    a 60-second tick interval could grow concurrency by N every minute on a
    busy board and accumulate without bound.

    ``spawn_fn`` defaults to ``_default_spawn``. Tests pass a stub.
    ``board`` pins workspace/log/db resolution for this tick to a specific
    board. When omitted, the current-board resolution chain is used.
    """
    # Reap zombie children from previously spawned workers. See
    # reap_worker_zombies() for the full rationale.
    reap_worker_zombies()

    board_id = _connection_board_identity(conn)
    dispatcher = (dispatcher_instance_id or "").strip()
    if not dispatcher and olympus_auth is not None:
        source_prefix = f"kanban-dispatcher:{board_id}:"
        if olympus_auth.principal_source.startswith(source_prefix):
            dispatcher = olympus_auth.principal_source[len(source_prefix):]
    if not dispatcher:
        # Ordinary Kanban has no authority dependency, but still receives a
        # unique process-registration owner. Governed verification will reject
        # a service principal that is not derived from its exact board/id pair.
        dispatcher = f"local-{os.getpid()}-{id(conn)}"

    def _invoke_spawn(spawn, task: Task, workspace: str, run: Run):
        """Call old or lifecycle-aware spawn hooks without caller assertions."""
        import inspect

        kwargs: dict[str, Any] = {}
        try:
            signature = inspect.signature(spawn)
            accepts_kwargs = any(
                parameter.kind is inspect.Parameter.VAR_KEYWORD
                for parameter in signature.parameters.values()
            )
            for name, value in (
                ("board", board),
                ("launch_token", run.launch_token),
                ("dispatcher_instance_id", dispatcher),
            ):
                if accepts_kwargs or name in signature.parameters:
                    kwargs[name] = value
        except (TypeError, ValueError):
            kwargs = {}
        return spawn(task, workspace, **kwargs)

    result = DispatchResult()
    result.reclaimed = release_stale_claims(conn, olympus_auth=olympus_auth)
    result.stale = detect_stale_running(
        conn, stale_timeout_seconds=stale_timeout_seconds,
        olympus_auth=olympus_auth,
    )
    result.crashed = detect_crashed_workers(conn, olympus_auth=olympus_auth)
    # detect_crashed_workers stashes protocol-violation auto-blocks on
    # itself so the public list-return stays stable. Pull them into the
    # DispatchResult here so telemetry / tests see the trip.
    _crash_auto_blocked = getattr(
        detect_crashed_workers, "_last_auto_blocked", []
    )
    if _crash_auto_blocked:
        result.auto_blocked.extend(_crash_auto_blocked)
    # Rate-limited requeues (quota wall, no failure counted) — surface for
    # telemetry / tests. These tasks went back to ``ready`` and the respawn
    # guard will defer them until the quota window clears.
    _crash_rate_limited = getattr(
        detect_crashed_workers, "_last_rate_limited", []
    )
    if _crash_rate_limited:
        result.rate_limited.extend(_crash_rate_limited)
    result.timed_out = enforce_max_runtime(conn, olympus_auth=olympus_auth)
    result.promoted = recompute_ready(
        conn, failure_limit=failure_limit, olympus_auth=olympus_auth,
    )

    # Count tasks already running so max_spawn enforces concurrency rather
    # than a per-tick spawn budget. See the docstring above for the full
    # rationale; the short version is that a 60-second tick interval with a
    # per-tick budget of N would grow concurrency by N every tick on a busy
    # board, since "running" tasks aren't reclaimed by completion alone —
    # they sit in status='running' until the worker calls
    # kanban_complete/kanban_block (or the dispatcher TTL-reclaims them).
    running_count = 0
    if max_spawn is not None:
        running_count = int(
            conn.execute(
                "SELECT COUNT(*) FROM tasks WHERE status = 'running'"
            ).fetchone()[0]
        )

    ready_rows = conn.execute(
        "SELECT id, assignee FROM tasks "
        "WHERE status = 'ready' AND claim_lock IS NULL "
        "ORDER BY priority DESC, created_at ASC"
    ).fetchall()
    # Honour kanban.max_in_progress: if the board already has enough running
    # tasks, skip spawning this tick so slow workers (local LLMs,
    # resource-constrained hosts) can finish what they have before more tasks
    # pile up and time out.
    if max_in_progress is not None and ready_rows:
        in_progress = conn.execute(
            "SELECT COUNT(*) FROM tasks WHERE status = 'running'"
        ).fetchone()[0]
        if in_progress >= max_in_progress:
            return result
        # Only spawn enough to reach the cap, respecting max_spawn too.
        remaining = max_in_progress - in_progress
        if max_spawn is None or max_spawn > remaining:
            max_spawn = remaining
    spawned = 0
    # Per-profile concurrency cap (#21582): when set, track how many
    # workers each assignee already has in flight, and refuse to spawn
    # when this would push that assignee past the cap. Prevents
    # fan-out workloads from melting a single profile's local model /
    # API quota / browser pool while leaving other profiles idle.
    # Tasks blocked this way go to skipped_per_profile_capped (not
    # skipped_unassigned — the operator-actionable signal is different:
    # "this profile is busy, try again later" not "this needs routing").
    _per_profile_cap = max_in_progress_per_profile if (
        isinstance(max_in_progress_per_profile, int)
        and max_in_progress_per_profile > 0
    ) else None
    _per_profile_running: dict[str, int] = {}
    if _per_profile_cap is not None:
        for prow in conn.execute(
            "SELECT assignee, COUNT(*) AS n FROM tasks "
            "WHERE status = 'running' AND assignee IS NOT NULL "
            "GROUP BY assignee"
        ):
            _per_profile_running[prow["assignee"]] = int(prow["n"])
    # Normalize default_assignee once: empty/whitespace string → None so the
    # rest of the loop can use ``if default_assignee:`` as a single check.
    # We also resolve profile_exists once here for the same reason.
    _default_assignee = (default_assignee or "").strip() or None
    _default_assignee_resolved = False
    if _default_assignee:
        try:
            from hermes_cli.profiles import profile_exists as _pe
            _default_assignee_resolved = bool(_pe(_default_assignee))
        except Exception:
            # Profiles module not importable (test stubs, exotic envs).
            # Trust the operator's config and try the assignment; the
            # downstream profile_exists check on the assigned row will
            # bucket it as nonspawnable if the profile genuinely isn't
            # there, with the existing diagnostic.
            _default_assignee_resolved = True
    for row in ready_rows:
        if max_spawn is not None and running_count + spawned >= max_spawn:
            break
        row_assignee = row["assignee"]
        if not row_assignee:
            # Honour kanban.default_assignee: when the dispatcher hits an
            # unassigned ready task and an operator-configured fallback
            # exists, persist the assignment and proceed. This removes the
            # dashboard footgun where a task created without an assignee
            # parks in 'ready' forever even though the operator's intent
            # ("default") was perfectly clear (#27145). Mutating the row
            # (not just the in-memory view) keeps diagnostics and the
            # board state consistent: the task is now legitimately owned
            # by ``kanban.default_assignee``, not "unassigned but secretly
            # routed".
            if _default_assignee and _default_assignee_resolved:
                # Dry-run: show what WOULD happen (auto-assign + spawn) without
                # mutating the DB. Real run: mutate the row + emit the
                # 'assigned' event so the board state matches what just happened.
                if not dry_run:
                    try:
                        with write_txn(conn):
                            assign_task(
                                conn,
                                row["id"],
                                _default_assignee,
                                olympus_auth=olympus_auth,
                            )
                    except Exception:
                        _log.debug(
                            "kanban dispatch: failed to apply default_assignee=%r "
                            "to task %s",
                            _default_assignee, row["id"], exc_info=True,
                        )
                        result.skipped_unassigned.append(row["id"])
                        continue
                row_assignee = _default_assignee
                result.auto_assigned_default.append(row["id"])
            else:
                result.skipped_unassigned.append(row["id"])
                continue
        # Skip ready tasks whose assignee is not a real Hermes profile.
        # `_default_spawn` invokes ``hermes -p <assignee>`` which fails
        # with "Profile 'X' does not exist" when the assignee names a
        # control-plane lane (e.g. an interactive Claude Code terminal
        # like ``orion-cc`` / ``orion-research``) rather than a Hermes
        # profile. Those task lanes are pulled by terminals via
        # ``claim_task`` directly and should NEVER auto-spawn — the
        # subprocess would crash on startup, get reaped as a zombie,
        # the task would loop back to ``ready`` on next tick, and we'd
        # burn CPU forever (#kanban-dispatcher-crash-loop 2026-05-05).
        try:
            from hermes_cli.profiles import profile_exists  # local import: avoids cycle
        except Exception:
            profile_exists = None  # type: ignore[assignment]
        if profile_exists is not None and not profile_exists(row_assignee):
            # Bucket separately from skipped_unassigned: the operator
            # cannot fix this by assigning a profile (the assignee IS the
            # intended owner — a terminal lane). Health telemetry uses
            # this distinction to suppress spurious "stuck" warnings on
            # multi-lane setups where the ready queue is steadily full
            # of human-pulled work.
            result.skipped_nonspawnable.append(row["id"])
            continue
        # Per-profile concurrency cap (#21582): even if there's global
        # headroom, refuse to spawn for an assignee that's already at
        # its in-flight cap. Prevents one profile's local model / API
        # quota / browser pool from being overwhelmed by a fan-out
        # while the global max_in_progress / max_spawn caps still allow
        # work on OTHER profiles.
        if _per_profile_cap is not None:
            current = _per_profile_running.get(row_assignee, 0)
            if current >= _per_profile_cap:
                result.skipped_per_profile_capped.append(
                    (row["id"], row_assignee, current)
                )
                continue
        # Respawn guard: refuse to re-spawn when useful work is already
        # in-flight/recent, or when the last failure is a deterministic
        # blocker (quota / auth). The guard defers the spawn this tick so
        # the task gets a chance to clear (rate limits often reset in
        # seconds-to-minutes); the existing consecutive_failures counter
        # still trips the auto-block circuit breaker after failure_limit
        # consecutive failures, so a persistent auth error eventually
        # blocks via the normal path rather than on first occurrence.
        guard_reason = check_respawn_guard(conn, row["id"])
        if guard_reason is not None:
            result.respawn_guarded.append((row["id"], guard_reason))
            # Emit an event so operators can see why the task was
            # skipped when reading `hermes kanban tail` — without
            # this the task appears stuck in ready with no diagnosis.
            if not dry_run:
                with write_txn(conn):
                    _append_event(
                        conn, row["id"], "respawn_guarded",
                        {"reason": guard_reason},
                    )
            continue
        if dry_run:
            result.spawned.append((row["id"], row_assignee, ""))
            # Increment per-profile counter even in dry_run so the cap
            # check sees the would-be spawn on subsequent iterations.
            # Without this, dry_run reports every task as spawnable and
            # under-reports the capped subset (#21582).
            if _per_profile_cap is not None and row_assignee:
                _per_profile_running[row_assignee] = (
                    _per_profile_running.get(row_assignee, 0) + 1
                )
            continue
        reserved = reserve_worker_run(
            conn, row["id"], ttl_seconds=ttl_seconds,
            olympus_auth=olympus_auth,
        )
        if reserved is None:
            continue
        claimed = get_task(conn, row["id"])
        if claimed is None or not reserved.launch_token:
            continue
        try:
            workspace = resolve_workspace(claimed, board=board)
        except Exception as exc:
            if claimed.olympus_context is not None:
                try:
                    if fail_worker_launch(
                        conn,
                        task_id=claimed.id,
                        run_id=reserved.id,
                        launch_token=reserved.launch_token,
                        error=f"workspace: {exc}",
                        olympus_auth=olympus_auth,
                    ):
                        result.auto_blocked.append(claimed.id)
                except OlympusContextError:
                    pass
                continue
            auto = _record_spawn_failure(
                conn, claimed.id, f"workspace: {exc}",
                failure_limit=failure_limit,
                olympus_auth=olympus_auth,
            )
            if auto:
                result.auto_blocked.append(claimed.id)
            continue
        # Persist the resolved workspace path so the worker can cd there.
        set_workspace_path(
            conn, claimed.id, str(workspace), olympus_auth=olympus_auth,
        )
        _maybe_emit_scratch_tip(conn, claimed.id, claimed.workspace_kind)
        _spawn = spawn_fn if spawn_fn is not None else _default_spawn
        try:
            if claimed.olympus_context is not None:
                workspace_snapshot = {
                    "board_id": board_id,
                    "workspace_kind": claimed.workspace_kind,
                    "workspace_path": str(workspace),
                }
                if not mark_worker_workspace_ready(
                    conn,
                    task_id=claimed.id,
                    run_id=reserved.id,
                    launch_token=reserved.launch_token,
                    workspace_snapshot=workspace_snapshot,
                    olympus_auth=olympus_auth,
                ) or not mark_worker_starting(
                    conn,
                    task_id=claimed.id,
                    run_id=reserved.id,
                    launch_token=reserved.launch_token,
                    olympus_auth=olympus_auth,
                ):
                    raise OlympusContextError(
                        "worker_launch_state_conflict",
                        "governed worker launch reservation changed before spawn",
                    )
            spawned_process = _invoke_spawn(
                _spawn, claimed, str(workspace), reserved
            )
            if claimed.olympus_context is not None:
                process_identity = (
                    spawned_process
                    if isinstance(spawned_process, ProcessIdentity)
                    else read_process_identity(int(spawned_process or 0))
                )
                if process_identity is None or not register_worker_process(
                    conn,
                    task_id=claimed.id,
                    run_id=reserved.id,
                    launch_token=reserved.launch_token,
                    process_identity=process_identity,
                    dispatcher_instance_id=dispatcher,
                    olympus_auth=olympus_auth,
                ):
                    raise OlympusContextError(
                        "worker_process_identity_unverified",
                        "spawned governed worker could not be registered exactly",
                    )
            elif spawned_process:
                _set_worker_pid(
                    conn, claimed.id, int(spawned_process),
                )
            # NOTE: we intentionally do NOT reset consecutive_failures
            # here. A successful spawn proves the worker can start but
            # doesn't prove the run will succeed. Under unified
            # failure counting, resetting on spawn would let a task
            # that keeps timing out after spawn loop forever. The
            # counter is cleared only on successful completion (see
            # complete_task).
            result.spawned.append((claimed.id, claimed.assignee or "", str(workspace)))
            spawned += 1
            # Track the new in-flight count for this profile so later
            # iterations in this same tick respect the per-profile cap
            # (#21582). Subsequent ticks re-query from the DB.
            if _per_profile_cap is not None and claimed.assignee:
                _per_profile_running[claimed.assignee] = (
                    _per_profile_running.get(claimed.assignee, 0) + 1
                )
        except Exception as exc:
            if claimed.olympus_context is not None:
                try:
                    failed_closed = fail_worker_launch(
                        conn,
                        task_id=claimed.id,
                        run_id=reserved.id,
                        launch_token=reserved.launch_token,
                        error=str(exc),
                        olympus_auth=olympus_auth,
                    )
                except OlympusContextError:
                    failed_closed = False
                if failed_closed:
                    result.auto_blocked.append(claimed.id)
                continue
            auto = _record_spawn_failure(
                conn, claimed.id, str(exc),
                failure_limit=failure_limit,
                olympus_auth=olympus_auth,
            )
            if auto:
                result.auto_blocked.append(claimed.id)

    # ---- review column dispatch ----
    # Review tasks are tasks that a worker moved to 'review' after
    # creating a PR.  The dispatcher spawns a review agent (loading
    # sdlc-review skill) that verifies the PR and either merges (→ done)
    # or rejects (→ back to running for the worker to fix).
    #
    # Same concurrency model as ready dispatch: review spawns count
    # against max_spawn alongside ready tasks, so the total number of
    # running workers stays bounded.
    review_rows = conn.execute(
        "SELECT id, assignee FROM tasks "
        "WHERE status = 'review' AND claim_lock IS NULL "
        "ORDER BY priority DESC, created_at ASC"
    ).fetchall()
    for row in review_rows:
        if max_spawn is not None and running_count + spawned >= max_spawn:
            break
        if not row["assignee"]:
            result.skipped_unassigned.append(row["id"])
            continue
        try:
            from hermes_cli.profiles import profile_exists
        except Exception:
            profile_exists = None  # type: ignore[assignment]
        if profile_exists is not None and not profile_exists(row["assignee"]):
            result.skipped_nonspawnable.append(row["id"])
            continue
        if dry_run:
            result.spawned.append((row["id"], row["assignee"], ""))
            continue
        reserved = reserve_worker_run(
            conn, row["id"], review=True, ttl_seconds=ttl_seconds,
            olympus_auth=olympus_auth,
        )
        if reserved is None:
            continue
        claimed = get_task(conn, row["id"])
        if claimed is None or not reserved.launch_token:
            continue
        try:
            workspace = resolve_workspace(claimed, board=board)
        except Exception as exc:
            if claimed.olympus_context is not None:
                try:
                    if fail_worker_launch(
                        conn,
                        task_id=claimed.id,
                        run_id=reserved.id,
                        launch_token=reserved.launch_token,
                        error=f"workspace: {exc}",
                        olympus_auth=olympus_auth,
                    ):
                        result.auto_blocked.append(claimed.id)
                except OlympusContextError:
                    pass
                continue
            auto = _record_spawn_failure(
                conn, claimed.id, f"workspace: {exc}",
                failure_limit=failure_limit,
                olympus_auth=olympus_auth,
            )
            if auto:
                result.auto_blocked.append(claimed.id)
            continue
        # Persist the resolved workspace path so the worker can cd there.
        set_workspace_path(
            conn, claimed.id, str(workspace), olympus_auth=olympus_auth,
        )
        _maybe_emit_scratch_tip(conn, claimed.id, claimed.workspace_kind)
        if not heartbeat_claim(
            conn,
            claimed.id,
            ttl_seconds=ttl_seconds,
            claimer=claimed.claim_lock,
            olympus_auth=olympus_auth,
        ):
            _release_unspawned_claim(
                conn, claimed.id, claim_lock=claimed.claim_lock,
                olympus_auth=olympus_auth,
            )
            continue
        # Force-load sdlc-review skill for review agents.  The
        # _default_spawn function already auto-loads kanban-worker, and
        # appends task.skills via --skills.  Setting task.skills here
        # means the review agent gets both kanban-worker (lifecycle)
        # and sdlc-review (review logic: AC verification, merge, etc.).
        claimed.skills = ["sdlc-review"]
        _spawn = spawn_fn if spawn_fn is not None else _default_spawn
        try:
            if claimed.olympus_context is not None:
                if not mark_worker_workspace_ready(
                    conn,
                    task_id=claimed.id,
                    run_id=reserved.id,
                    launch_token=reserved.launch_token,
                    workspace_snapshot={
                        "board_id": board_id,
                        "workspace_kind": claimed.workspace_kind,
                        "workspace_path": str(workspace),
                    },
                    olympus_auth=olympus_auth,
                ) or not mark_worker_starting(
                    conn,
                    task_id=claimed.id,
                    run_id=reserved.id,
                    launch_token=reserved.launch_token,
                    olympus_auth=olympus_auth,
                ):
                    raise OlympusContextError(
                        "worker_launch_state_conflict",
                        "governed review launch changed before spawn",
                    )
            spawned_process = _invoke_spawn(
                _spawn, claimed, str(workspace), reserved
            )
            if claimed.olympus_context is not None:
                process_identity = (
                    spawned_process
                    if isinstance(spawned_process, ProcessIdentity)
                    else read_process_identity(int(spawned_process or 0))
                )
                if process_identity is None or not register_worker_process(
                    conn,
                    task_id=claimed.id,
                    run_id=reserved.id,
                    launch_token=reserved.launch_token,
                    process_identity=process_identity,
                    dispatcher_instance_id=dispatcher,
                    olympus_auth=olympus_auth,
                ):
                    raise OlympusContextError(
                        "worker_process_identity_unverified",
                        "spawned governed review worker was not registered",
                    )
            elif spawned_process:
                _set_worker_pid(
                    conn, claimed.id, int(spawned_process),
                )
            result.spawned.append((claimed.id, claimed.assignee or "", str(workspace)))
            spawned += 1
        except Exception as exc:
            if claimed.olympus_context is not None:
                try:
                    failed_closed = fail_worker_launch(
                        conn,
                        task_id=claimed.id,
                        run_id=reserved.id,
                        launch_token=reserved.launch_token,
                        error=str(exc),
                        olympus_auth=olympus_auth,
                    )
                except OlympusContextError:
                    failed_closed = False
                if failed_closed:
                    result.auto_blocked.append(claimed.id)
                continue
            auto = _record_spawn_failure(
                conn, claimed.id, str(exc),
                failure_limit=failure_limit,
                olympus_auth=olympus_auth,
            )
            if auto:
                result.auto_blocked.append(claimed.id)
    return result


def _positive_int(value: Any, default: int, *, minimum: int = 1) -> int:
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return default
    return parsed if parsed >= minimum else default


def worker_log_rotation_config(kanban_cfg: Optional[dict] = None) -> tuple[int, int]:
    """Return ``(rotate_bytes, backup_count)`` for worker log rotation.

    Defaults preserve the historical behavior: rotate at 2 MiB and keep one
    backup generation (``.log.1``). Operators with long-running workers can
    raise either value from ``config.yaml`` without changing dispatcher code.
    """
    if kanban_cfg is None:
        try:
            from hermes_cli.config import load_config

            kanban_cfg = (load_config().get("kanban") or {})
        except Exception:
            kanban_cfg = {}
    max_bytes = _positive_int(
        (kanban_cfg or {}).get("worker_log_rotate_bytes"),
        DEFAULT_LOG_ROTATE_BYTES,
        minimum=1,
    )
    backup_count = _positive_int(
        (kanban_cfg or {}).get("worker_log_backup_count"),
        DEFAULT_LOG_BACKUP_COUNT,
        minimum=0,
    )
    return max_bytes, backup_count


def _rotated_log_path(log_path: Path, generation: int) -> Path:
    return log_path.with_suffix(log_path.suffix + f".{generation}")


def _rotate_worker_log(
    log_path: Path,
    max_bytes: int,
    backup_count: int = DEFAULT_LOG_BACKUP_COUNT,
) -> None:
    """Rotate ``<log>`` when it exceeds ``max_bytes``.

    ``backup_count=1`` preserves the legacy single-generation behavior:
    ``<log>`` moves to ``<log>.1`` and any previous ``.1`` is replaced.
    Higher values shift older generations up to ``backup_count``.
    """
    try:
        if not log_path.exists():
            return
        if log_path.stat().st_size <= max_bytes:
            return
        backup_count = _positive_int(
            backup_count,
            DEFAULT_LOG_BACKUP_COUNT,
            minimum=0,
        )
        if backup_count == 0:
            log_path.unlink()
            return
        oldest = _rotated_log_path(log_path, backup_count)
        try:
            if oldest.exists():
                oldest.unlink()
        except OSError:
            pass
        for generation in range(backup_count - 1, 0, -1):
            src = _rotated_log_path(log_path, generation)
            if not src.exists():
                continue
            try:
                src.rename(_rotated_log_path(log_path, generation + 1))
            except OSError:
                pass
        log_path.rename(_rotated_log_path(log_path, 1))
    except OSError:
        pass


def _module_hermes_argv() -> list[str]:
    """Return the interpreter-bound Hermes CLI invocation."""
    # ``hermes_cli.main`` is the console-script target declared in
    # pyproject.toml, NOT a top-level ``hermes`` package — there is no
    # ``hermes`` package to import.
    return [sys.executable, "-m", "hermes_cli.main"]


def _absolute_hermes_path(path: str) -> str:
    """Return an absolute filesystem path for a resolved Hermes shim."""
    expanded = os.path.expanduser(path)
    return expanded if os.path.isabs(expanded) else os.path.abspath(expanded)


def _looks_like_path(value: str) -> bool:
    """Return true when a command override is an explicit path, not a name."""
    expanded = os.path.expanduser(value)
    return (
        expanded.startswith("~")
        or os.path.isabs(expanded)
        or bool(os.path.dirname(expanded))
        or "\\" in expanded
        or bool(re.match(r"^[A-Za-z]:", expanded))
    )


def _is_windows_batch_shim(path: str) -> bool:
    """Return true for Windows shell/batch shims that should not be argv[0]."""
    return path.lower().endswith((".cmd", ".bat"))


def _path_search_names(command: str) -> list[str]:
    """Return executable names to try for an unqualified command."""
    if not _IS_WINDOWS or os.path.splitext(command)[1]:
        return [command]
    raw = os.environ.get("PATHEXT") or ".COM;.EXE;.BAT;.CMD"
    exts = [ext for ext in raw.split(";") if ext]
    return [command + ext for ext in exts]


def _safe_which_no_cwd(command: str) -> Optional[str]:
    """Resolve a bare command from PATH without implicit current-dir search.

    ``shutil.which`` follows platform search behavior. On Windows that can
    include the current directory before PATH for bare names, which is not a
    safe dispatcher primitive. This resolver only considers explicit PATH
    entries and skips empty / ``.`` entries.
    """
    path_env = os.environ.get("PATH", "")
    for raw_dir in path_env.split(os.pathsep):
        if not raw_dir or raw_dir == ".":
            continue
        directory = os.path.expanduser(raw_dir)
        for name in _path_search_names(command):
            candidate = os.path.join(directory, name)
            if not os.path.isfile(candidate):
                continue
            if _IS_WINDOWS or os.access(candidate, os.X_OK):
                return candidate
    return None


def _hermes_path_argv(path: str) -> list[str]:
    """Return argv for a resolved Hermes executable path.

    Windows batch shims (`.cmd` / `.bat`) are not safe as argv[0] for
    worker launches because the argument vector includes task-derived
    values. Prefer the interpreter-bound module form whenever the resolved
    executable is only a shell shim.
    """
    if _IS_WINDOWS and _is_windows_batch_shim(path):
        return _module_hermes_argv()
    return [_absolute_hermes_path(path)]


def _resolve_hermes_argv() -> list[str]:
    """Resolve the ``hermes`` invocation as argv parts for ``Popen``.

    Tries in order:

    1. ``$HERMES_BIN`` — explicit operator override. Path-like values are
       normalized to absolute paths; bare command names keep normal PATH
       semantics and never prefer a same-directory file before ``PATH``.
    2. ``shutil.which("hermes")`` — the console-script shim, normalized to
       an absolute path. On Windows, ``which`` can return a relative
       ``.\\hermes.CMD`` when the current directory is on ``PATH``; directly
       launching batch shims is also unsafe with task-derived argv. The
       dispatcher therefore falls back to the interpreter-bound module form
       for implicit ``.cmd`` / ``.bat`` shims.
    3. ``sys.executable -m hermes_cli.main`` — fallback for setups where
       Hermes is launched from a venv and the ``hermes`` shim is not on
       the dispatcher's ``$PATH`` (cron, systemd ``User=`` services,
       launchd jobs, detached processes, etc.). Goes through the running
       interpreter so the result is independent of ``$PATH``.

    Mirrors ``gateway.run._resolve_hermes_bin`` for the same reason. Kept
    local (not imported from gateway) because ``hermes_cli`` sits below
    ``gateway`` in the dependency order.
    """
    import shutil

    env_bin = os.environ.get("HERMES_BIN", "").strip()
    if env_bin:
        if _looks_like_path(env_bin):
            return _hermes_path_argv(env_bin)
        resolved_env_bin = _safe_which_no_cwd(env_bin)
        if resolved_env_bin:
            return _hermes_path_argv(resolved_env_bin)
        return _module_hermes_argv()

    hermes_bin = _safe_which_no_cwd("hermes") if _IS_WINDOWS else shutil.which("hermes")
    if hermes_bin:
        return _hermes_path_argv(hermes_bin)
    return _module_hermes_argv()


def _kanban_worker_skill_available(hermes_home: Optional[str]) -> bool:
    """True if the bundled ``kanban-worker`` skill resolves for the home the
    spawned worker will run under.

    The dispatcher injects ``--skills kanban-worker`` into every worker. When
    the worker activates a profile (``hermes -p <name>``), its ``SKILLS_DIR``
    becomes ``<profile_home>/skills`` — which on many profiles does NOT contain
    the bundled skill (it ships in the *default* root home, not every
    profile-scoped skills dir). Preloading a missing skill is fatal at CLI
    startup (``ValueError: Unknown skill(s): kanban-worker``), aborting the
    worker before the agent loop runs. Gate the flag on actual resolvability;
    the kanban lifecycle contract is still injected via ``KANBAN_GUIDANCE``, so
    omitting the flag only drops the supplementary pattern library.
    """
    from pathlib import Path as _Path

    # An unset HERMES_HOME means the worker falls back to the default root
    # home (``~/.hermes``), which ships the bundled skill.
    base = _Path(hermes_home) if hermes_home else (_Path.home() / ".hermes")
    skills_root = base / "skills"
    if not skills_root.is_dir():
        return False
    # Canonical bundled location first (cheap), then a bounded scan for
    # profiles that have it nested elsewhere.
    if (skills_root / "devops" / "kanban-worker" / "SKILL.md").is_file():
        return True
    try:
        for skill_md in skills_root.rglob("kanban-worker/SKILL.md"):
            if skill_md.is_file():
                return True
    except OSError:
        pass
    return False


def _worker_terminal_timeout_env(
    max_runtime_seconds: Optional[int],
    current_timeout: Optional[str],
) -> Optional[str]:
    """Return a worker-scoped TERMINAL_TIMEOUT override, if needed.

    Kanban's ``max_runtime_seconds`` bounds the whole worker attempt. The
    terminal tool has its own default timeout via ``TERMINAL_TIMEOUT``; when
    the worker runtime is longer, raise only the child process default so a
    long command is not killed by the generic terminal default first.
    """
    if max_runtime_seconds is None:
        return None
    try:
        runtime = int(max_runtime_seconds)
    except (TypeError, ValueError):
        return None
    if runtime <= 0:
        return None

    desired = max(1, runtime - KANBAN_TERMINAL_TIMEOUT_GRACE_SECONDS)
    try:
        existing = int(str(current_timeout).strip()) if current_timeout else 0
    except (TypeError, ValueError):
        existing = 0
    if existing >= desired:
        return None
    return str(desired)


def _resolve_worker_cli_toolsets(hermes_home: Optional[str]) -> Optional[list[str]]:
    """Return the assigned profile's effective CLI toolsets for a worker.

    Dispatcher-spawned workers are launched from a long-lived gateway process,
    then the child re-enters the CLI with ``-p <assignee>``. Resolve the
    assignee profile's CLI tool surface at dispatch time and pass it as an
    explicit ``--toolsets`` pin so worker startup cannot fall back to a stale
    root/active-profile config or a profile whose top-level ``toolsets`` entry
    is only the kanban orchestrator surface. ``model_tools`` still appends the
    task-scoped kanban lifecycle tools when ``HERMES_KANBAN_TASK`` is set.
    """
    if not hermes_home:
        return None
    try:
        from hermes_constants import reset_hermes_home_override, set_hermes_home_override
        from hermes_cli.config import load_config
        from hermes_cli.tools_config import _get_platform_tools

        token = set_hermes_home_override(hermes_home)
        try:
            cfg = load_config()
            toolsets = sorted(_get_platform_tools(cfg, "cli"))
        finally:
            reset_hermes_home_override(token)
        return toolsets or None
    except Exception as exc:
        _log.debug(
            "kanban worker: could not resolve CLI toolsets for HERMES_HOME=%r (%s)",
            hermes_home,
            exc,
        )
        return None


def _default_spawn(
    task: Task,
    workspace: str,
    *,
    board: Optional[str] = None,
    launch_token: Optional[str] = None,
    dispatcher_instance_id: Optional[str] = None,
) -> Optional[int]:
    """Fire-and-forget ``hermes -p <profile> chat -q ...`` subprocess.

    Returns the spawned child's PID so the dispatcher can detect crashes
    before the claim TTL expires. The child's completion is still observed
    via the ``complete`` / ``block`` transitions the worker writes itself;
    the PID check is a safety net for crashes, OOM kills, and Ctrl+C.

    ``board`` pins the child's kanban context to that board: the child's
    ``HERMES_KANBAN_DB`` / ``HERMES_KANBAN_BOARD`` / workspaces_root env
    vars all resolve to the same board the dispatcher claimed the task
    from. Workers cannot accidentally see other boards.
    """
    import subprocess
    if not task.assignee:
        raise ValueError(f"task {task.id} has no assignee")

    from hermes_cli.profiles import normalize_profile_name

    profile_arg = normalize_profile_name(task.assignee)

    prompt = f"work kanban task {task.id}"
    env = dict(os.environ)

    # Inject HERMES_HOME so the worker reads the profile-scoped config.yaml
    # (fallback_providers, toolsets, agent settings, etc.) instead of the root
    # config.  Without this, `env = dict(os.environ)` copies only the parent's
    # env, and when the child process starts `hermes -p <name>` the
    # _apply_profile_override() runs *before* hermes_constants is imported.
    # If HERMES_HOME is absent from the child's env, get_hermes_home() falls
    # back to Path.home() / ".hermes" (the DEFAULT profile root), ignoring the
    # profile-specific config entirely.  Fixes profile-scoped fallback_providers
    # being invisible to kanban workers.
    from hermes_cli.profiles import resolve_profile_env
    try:
        env["HERMES_HOME"] = resolve_profile_env(profile_arg)
    except FileNotFoundError:
        # Profile dir doesn't exist — defer resolution to the CLI's
        # _apply_profile_override() via HERMES_PROFILE (set below).
        # This only happens in test fixtures where the isolated
        # HERMES_HOME never had profiles created.
        pass
    if task.tenant:
        env["HERMES_TENANT"] = task.tenant
    env["HERMES_KANBAN_TASK"] = task.id
    env["HERMES_KANBAN_WORKSPACE"] = workspace
    if task.branch_name:
        env["HERMES_KANBAN_BRANCH"] = task.branch_name
    if task.current_run_id is not None:
        env["HERMES_KANBAN_RUN_ID"] = str(task.current_run_id)
    if task.claim_lock:
        env["HERMES_KANBAN_CLAIM_LOCK"] = task.claim_lock
    if launch_token:
        env["HERMES_KANBAN_LAUNCH_TOKEN"] = launch_token
    if dispatcher_instance_id:
        env["HERMES_KANBAN_DISPATCHER_INSTANCE"] = dispatcher_instance_id
    # Goal-loop mode: the worker reads these and wraps its run in the
    # Ralph-style /goal judge loop (see cli.py quiet-mode path). Only set
    # when enabled so non-goal tasks keep a clean env.
    if task.goal_mode:
        env["HERMES_KANBAN_GOAL_MODE"] = "1"
        if task.goal_max_turns is not None:
            env["HERMES_KANBAN_GOAL_MAX_TURNS"] = str(int(task.goal_max_turns))
    terminal_timeout = _worker_terminal_timeout_env(
        task.max_runtime_seconds,
        env.get("TERMINAL_TIMEOUT"),
    )
    if terminal_timeout is not None:
        env["TERMINAL_TIMEOUT"] = terminal_timeout
    foreground_timeout = _worker_terminal_timeout_env(
        task.max_runtime_seconds,
        env.get("TERMINAL_MAX_FOREGROUND_TIMEOUT"),
    )
    if foreground_timeout is not None:
        env["TERMINAL_MAX_FOREGROUND_TIMEOUT"] = foreground_timeout
    # Pin the shared board + workspaces root the dispatcher resolved, so
    # that even when the worker activates a profile (`hermes -p <name>`
    # rewrites HERMES_HOME), its kanban paths still match the
    # dispatcher's. Belt-and-braces with the `get_default_hermes_root()`
    # resolution in `kanban_home()` — symmetric resolution is the norm,
    # but unusual symlink / Docker layouts are caught here too.
    env["HERMES_KANBAN_DB"] = str(kanban_db_path(board=board))
    env["HERMES_KANBAN_WORKSPACES_ROOT"] = str(workspaces_root(board=board))
    # Board slug — the final defense-in-depth pin. If the worker ever
    # resolves kanban paths without the DB / workspaces env vars, the
    # board slug still forces it to the right directory.
    resolved_board = _normalize_board_slug(board) or get_current_board()
    env["HERMES_KANBAN_BOARD"] = resolved_board
    # HERMES_PROFILE is the author the kanban_comment tool defaults to.
    # `hermes -p <assignee>` activates the profile, but the env var is
    # what the tool reads — set it explicitly here so comments are
    # attributed correctly regardless of how the child loads config.
    env["HERMES_PROFILE"] = profile_arg

    cmd = [
        *_resolve_hermes_argv(),
        "-p", profile_arg,
        # Worker subprocesses switch to a profile-scoped HERMES_HOME above,
        # so they see that profile's shell-hook allowlist instead of the
        # dispatcher's root allowlist. Pass --accept-hooks explicitly so
        # profile-local worker sessions still register configured hooks.
        "--accept-hooks",
    ]
    # Auto-load the kanban-worker skill so every dispatched worker
    # has the pattern library (good summary/metadata shapes, retry
    # diagnostics, block-reason examples) in its context, even if
    # the profile hasn't wired it into skills config. The MANDATORY
    # lifecycle is already in the system prompt via KANBAN_GUIDANCE;
    # this skill is the deeper reference. Users can point a profile
    # at a different/additional skill via config if they want —
    # --skills is additive to the profile's default skill set.
    #
    # Only add the flag when the skill actually resolves for the home
    # the worker runs under: the bundled skill is absent from many
    # profile-scoped skills dirs, and preloading a missing skill is
    # fatal at CLI startup. Omitting it is safe — the lifecycle
    # contract still ships via KANBAN_GUIDANCE.
    if _kanban_worker_skill_available(env.get("HERMES_HOME")):
        cmd.extend(["--skills", "kanban-worker"])
    # Per-task force-loaded skills. Each name goes in its own
    # `--skills X` pair rather than a single comma-joined arg: the CLI
    # accepts both forms (action='append' + comma-split), but
    # per-name pairs are easier to read in `ps` output and avoid any
    # quoting ambiguity if a skill name ever contains unusual chars.
    # Dedupe against the built-in so we don't double-load kanban-worker
    # if a task author asks for it explicitly.
    if task.skills:
        for sk in task.skills:
            if sk and sk != "kanban-worker":
                cmd.extend(["--skills", sk])
    if task.model_override:
        cmd.extend(["-m", task.model_override])
    worker_toolsets = _resolve_worker_cli_toolsets(env.get("HERMES_HOME"))
    if worker_toolsets:
        cmd.extend(["--toolsets", ",".join(worker_toolsets)])
    cmd.extend([
        "chat",
        "-q", prompt,
    ])
    # Redirect output to a per-task log under <board-root>/logs/.
    # Anchored at the board root (not the shared kanban root), so
    # `hermes kanban log` on a specific board reads its own file and
    # logs don't collide across boards that happen to share task ids.
    log_dir = worker_logs_dir(board=board)
    log_dir.mkdir(parents=True, exist_ok=True)
    log_path = log_dir / f"{task.id}.log"
    rotate_bytes, backup_count = worker_log_rotation_config()
    _rotate_worker_log(log_path, rotate_bytes, backup_count)

    # Use 'a' so a re-run on unblock appends rather than overwrites.
    log_f = open(log_path, "ab")
    try:
        proc = subprocess.Popen(  # noqa: S603 -- argv is a fixed list built above
            cmd,
            cwd=workspace if os.path.isdir(workspace) else None,
            stdin=subprocess.DEVNULL,
            stdout=log_f,
            stderr=subprocess.STDOUT,
            env=env,
            start_new_session=True,
            creationflags=subprocess.CREATE_NO_WINDOW if _IS_WINDOWS else 0,
        )
    except FileNotFoundError:
        log_f.close()
        raise RuntimeError(
            "`hermes` executable not found on PATH. "
            "Install Hermes Agent or activate its venv before running the kanban dispatcher."
        )
    # NOTE: we intentionally do NOT close log_f here — we want Popen's
    # child process to keep writing after this function returns.  The
    # handle is kept alive by the child's inheritance.  The parent's
    # reference goes out of scope and is GC'd, but the OS-level FD stays
    # open in the child until the child exits.
    return proc.pid


# ---------------------------------------------------------------------------
# Long-lived dispatcher daemon
# ---------------------------------------------------------------------------

def run_daemon(
    *,
    interval: float = 60.0,
    max_spawn: Optional[int] = None,
    failure_limit: int = DEFAULT_SPAWN_FAILURE_LIMIT,
    stop_event=None,
    on_tick=None,
    olympus_auth: Optional[OlympusMutationAuth] = None,
) -> None:
    """Run the dispatcher in a loop until interrupted.

    Calls :func:`dispatch_once` every ``interval`` seconds. Exits cleanly
    on SIGINT / SIGTERM so ``hermes kanban daemon`` is systemd-friendly.
    ``stop_event`` (a :class:`threading.Event`) and ``on_tick`` (a
    callable receiving the :class:`DispatchResult`) are test hooks.
    """
    import signal
    import threading

    if stop_event is None:
        stop_event = threading.Event()

    def _handle(_signum, _frame):
        stop_event.set()

    # Install handlers only when running on the main thread — tests call
    # this inline from worker threads and signal() would raise there.
    if threading.current_thread() is threading.main_thread():
        for sig_name in ("SIGINT", "SIGTERM"):
            sig = getattr(signal, sig_name, None)
            if sig is not None:
                try:
                    signal.signal(sig, _handle)
                except (ValueError, OSError):
                    pass

    while not stop_event.is_set():
        try:
            with contextlib.closing(connect()) as conn:
                res = dispatch_once(
                    conn,
                    max_spawn=max_spawn,
                    failure_limit=failure_limit,
                    olympus_auth=olympus_auth,
                )
            if on_tick is not None:
                try:
                    on_tick(res)
                except Exception:
                    pass
        except Exception:
            # Don't let any single tick kill the daemon.
            import traceback
            traceback.print_exc()
        stop_event.wait(timeout=interval)


# ---------------------------------------------------------------------------
# Worker context builder (what a spawned worker sees)
# ---------------------------------------------------------------------------

def build_worker_context(conn: sqlite3.Connection, task_id: str) -> str:
    """Return the full text a worker should read to understand its task.

    Order:
      1. Task title (mandatory).
      2. Task body (optional opening post, capped at 8 KB).
      3. Prior attempts on THIS task (most recent ``_CTX_MAX_PRIOR_ATTEMPTS``
         shown; older attempts collapsed into a one-line summary).
         Each attempt's ``summary`` / ``error`` / ``metadata`` capped at
         ``_CTX_MAX_FIELD_BYTES`` each.
      4. Structured handoff results of every done parent task. Prefers
         ``run.summary`` / ``run.metadata`` when the parent was executed
         via a run; falls back to ``task.result`` for older data. Same
         per-field cap.
      5. Cross-task role history for the assignee (most recent 5
         completed runs on other tasks).
      6. Comment thread (most recent ``_CTX_MAX_COMMENTS`` shown, older
         collapsed).

    All caps exist so worker prompts stay bounded even on pathological
    boards (retry-heavy tasks, comment storms). The per-field char cap
    prevents a single 1 MB summary from dominating context.
    """
    task = get_task(conn, task_id)
    if not task:
        raise ValueError(f"unknown task {task_id}")

    def _cap(s: Optional[str], limit: int = _CTX_MAX_FIELD_BYTES) -> str:
        """Truncate a string to `limit` chars with a visible ellipsis."""
        if not s:
            return ""
        s = s.strip()
        if len(s) <= limit:
            return s
        return s[:limit] + f"… [truncated, {len(s) - limit} chars omitted]"

    lines: list[str] = []
    lines.append(f"# Kanban task {task.id}: {task.title}")
    lines.append("")
    lines.append(f"Assignee: {task.assignee or '(unassigned)'}")
    lines.append(f"Status:   {task.status}")
    if task.tenant:
        lines.append(f"Tenant:   {task.tenant}")
    lines.append(f"Workspace: {task.workspace_kind} @ {task.workspace_path or '(unresolved)'}")
    if task.max_runtime_seconds is not None:
        terminal_timeout = _worker_terminal_timeout_env(
            task.max_runtime_seconds,
            os.environ.get("TERMINAL_TIMEOUT"),
        )
        effective_terminal_timeout = terminal_timeout or os.environ.get("TERMINAL_TIMEOUT")
        lines.append(f"Max runtime: {task.max_runtime_seconds}s")
        if effective_terminal_timeout:
            lines.append(f"Terminal timeout: {effective_terminal_timeout}s")
    if task.branch_name:
        lines.append(f"Branch:   {task.branch_name}")
    lines.append("")

    if task.olympus_context is not None:
        olympus = normalize_olympus_context(task.olympus_context)
        authority = olympus["authority"]
        lease = olympus["lease"]
        lines.append("## Olympus authority")
        lines.append(
            "This task is governed by the explicit scope below. Do not infer "
            "permission from task existence, assignment, or successful validation."
        )
        lines.append(f"Goal:       {olympus['goal_id']}")
        lines.append(f"Program:    {olympus['program_id']}")
        lines.append(f"Milestone:  {olympus['milestone_id']}")
        lines.append(f"Mission:    {olympus['mission_id']}")
        lines.append(f"Workstream: {olympus['workstream_id']}")
        lines.append(
            f"Authority:  {authority['authority_id']} ({authority['status']}, "
            f"revision {authority['revision']}, source {authority['source']}, "
            f"expires {authority['expires_at']})"
        )
        lines.append(
            f"Lease:      {lease['lease_id']} ({lease['status']}, holder "
            f"{lease['holder']}, agent {lease['agent_id']}, revision "
            f"{lease['revision']}, source {lease['source']}, expires "
            f"{lease['expires_at']})"
        )
        lines.append(f"Risk:       {olympus['risk']}")
        lines.append(f"Agent:      {olympus['agent_id']}")
        lines.append(f"Review:     {olympus['review_status']}")
        if olympus["evidence_refs"]:
            lines.append("Evidence references:")
            lines.extend(f"- {ref}" for ref in olympus["evidence_refs"])
        lines.append("")

    if task.body and task.body.strip():
        lines.append("## Body")
        lines.append(_cap(task.body, _CTX_MAX_BODY_BYTES))
        lines.append("")

    # Attachments — files uploaded to this task (PDFs, source docs,
    # images). Surface the absolute on-disk path so the worker, which has
    # full file-tool access, can read them directly (read_file, terminal
    # `pdftotext`, etc.). On the local terminal backend the path resolves
    # as-is; remote backends need the kanban attachments dir mounted.
    attachments = list_attachments(conn, task_id)
    if attachments:
        lines.append("## Attachments")
        lines.append(
            "Files attached to this task. Read them with the file/terminal "
            "tools at the absolute paths below:"
        )
        for att in attachments:
            size_kb = max(1, (att.size + 1023) // 1024) if att.size else 0
            size_str = f", {size_kb} KB" if size_kb else ""
            ctype = f", {att.content_type}" if att.content_type else ""
            lines.append(f"- `{att.filename}`{ctype}{size_str} → `{att.stored_path}`")
        lines.append("")

    # Prior attempts — show closed runs so a retrying worker sees the
    # history. Skip the currently-active run (that's this worker).
    # Cap at _CTX_MAX_PRIOR_ATTEMPTS most-recent closed runs; older
    # attempts get collapsed into a one-line marker so the worker knows
    # more exist without bloating the prompt.
    all_prior = [r for r in list_runs(conn, task_id) if r.ended_at is not None]
    # list_runs returns ascending by started_at; "most recent" = last N
    if len(all_prior) > _CTX_MAX_PRIOR_ATTEMPTS:
        omitted = len(all_prior) - _CTX_MAX_PRIOR_ATTEMPTS
        shown = all_prior[-_CTX_MAX_PRIOR_ATTEMPTS:]
        first_shown_idx = omitted + 1
    else:
        omitted = 0
        shown = all_prior
        first_shown_idx = 1
    if shown:
        lines.append("## Prior attempts on this task")
        if omitted:
            lines.append(
                f"_({omitted} earlier attempt{'s' if omitted != 1 else ''} "
                f"omitted; showing most recent {len(shown)})_"
            )
        for offset, run in enumerate(shown):
            idx = first_shown_idx + offset
            ts = time.strftime("%Y-%m-%d %H:%M", time.localtime(run.started_at))
            profile = run.profile or "(unknown)"
            outcome = run.outcome or run.status
            lines.append(f"### Attempt {idx} — {outcome} ({profile}, {ts})")
            if run.summary and run.summary.strip():
                lines.append(_cap(run.summary))
            if run.error and run.error.strip():
                lines.append(f"_error_: {_cap(run.error)}")
            if run.metadata:
                try:
                    meta_str = json.dumps(run.metadata, ensure_ascii=False, sort_keys=True)
                    lines.append(f"_metadata_: `{_cap(meta_str)}`")
                except Exception:
                    pass
            lines.append("")

    # Parents: prefer the most-recent 'completed' run's summary + metadata,
    # fall back to ``task.result`` when no run rows exist (legacy DBs,
    # or tasks completed before the runs table landed).
    parent_rows = conn.execute(
        "SELECT parent_id FROM task_links WHERE child_id = ? ORDER BY parent_id",
        (task_id,),
    ).fetchall()
    parent_ids = [r["parent_id"] for r in parent_rows]

    if parent_ids:
        wrote_header = False
        for pid in parent_ids:
            pt = get_task(conn, pid)
            if not pt or pt.status != "done":
                continue
            runs = [r for r in list_runs(conn, pid) if r.outcome == "completed"]
            runs.sort(key=lambda r: r.started_at, reverse=True)
            run = runs[0] if runs else None

            if not wrote_header:
                lines.append("## Parent task results")
                wrote_header = True
            lines.append(f"### {pid}")

            body_lines: list[str] = []
            if run is not None and run.summary and run.summary.strip():
                body_lines.append(_cap(run.summary))
            elif pt.result:
                body_lines.append(_cap(pt.result))
            else:
                body_lines.append("(no result recorded)")

            if run is not None and run.metadata:
                try:
                    meta_str = json.dumps(run.metadata, ensure_ascii=False, sort_keys=True)
                    body_lines.append(f"_metadata_: `{_cap(meta_str)}`")
                except Exception:
                    pass
            lines.extend(body_lines)
            lines.append("")

    # Cross-task role history: what else has THIS assignee completed
    # recently? Gives the worker implicit continuity — "I'm the reviewer
    # and my last three reviews focused on security" — without forcing
    # the user to wire anything into SOUL.md / MEMORY.md. Bounded to the
    # most recent 5 completed runs, excluding this task so the retry
    # section above isn't duplicated. Safe on assignee=None (skipped).
    if task.assignee:
        role_rows = conn.execute(
            "SELECT t.id, t.title, r.summary, r.ended_at "
            "FROM task_runs r JOIN tasks t ON r.task_id = t.id "
            "WHERE r.profile = ? AND r.task_id != ? "
            "  AND r.outcome = 'completed' "
            "ORDER BY r.ended_at DESC LIMIT 5",
            (task.assignee, task_id),
        ).fetchall()
        if role_rows:
            lines.append(f"## Recent work by @{task.assignee}")
            for row in role_rows:
                ts = time.strftime(
                    "%Y-%m-%d %H:%M", time.localtime(int(row["ended_at"]))
                )
                s = (row["summary"] or "").strip().splitlines()
                first = s[0][:200] if s else "(no summary)"
                lines.append(f"- {row['id']} — {row['title']} ({ts}): {first}")
            lines.append("")

    # Comments: cap at the most-recent _CTX_MAX_COMMENTS so
    # comment-storm tasks don't blow out the worker's prompt. Older
    # comments summarised in a one-line marker like prior attempts.
    all_comments = list_comments(conn, task_id)
    if len(all_comments) > _CTX_MAX_COMMENTS:
        omitted_c = len(all_comments) - _CTX_MAX_COMMENTS
        shown_c = all_comments[-_CTX_MAX_COMMENTS:]
    else:
        omitted_c = 0
        shown_c = all_comments
    if shown_c:
        lines.append("## Comment thread")
        if omitted_c:
            lines.append(
                f"_({omitted_c} earlier comment{'s' if omitted_c != 1 else ''} "
                f"omitted; showing most recent {len(shown_c)})_"
            )
        for c in shown_c:
            ts = time.strftime("%Y-%m-%d %H:%M", time.localtime(c.created_at))
            # Render author with explicit "comment from worker" framing so
            # operator-controlled HERMES_PROFILE values like "hermes-system"
            # or "operator" can't be misread by the next worker as a system
            # directive above the (attacker-influenceable) comment body.
            # Defense-in-depth — the LLM-controlled author-forgery surface
            # was already closed in #22435. See #22452.
            safe_author = (c.author or "").replace("`", "")
            lines.append(f"comment from worker `{safe_author}` at {ts}:")
            lines.append(_cap(c.body, _CTX_MAX_COMMENT_BYTES))
            lines.append("")

    return "\n".join(lines).rstrip() + "\n"


# ---------------------------------------------------------------------------
# Stats + SLA helpers
# ---------------------------------------------------------------------------

def board_stats(conn: sqlite3.Connection) -> dict:
    """Per-status + per-assignee counts, plus the oldest ``ready`` age in
    seconds (the clearest staleness signal for a router or HUD).
    """
    by_status: dict[str, int] = {}
    for row in conn.execute(
        "SELECT status, COUNT(*) AS n FROM tasks "
        "WHERE status != 'archived' GROUP BY status"
    ):
        by_status[row["status"]] = int(row["n"])

    by_assignee: dict[str, dict[str, int]] = {}
    for row in conn.execute(
        "SELECT assignee, status, COUNT(*) AS n FROM tasks "
        "WHERE status != 'archived' AND assignee IS NOT NULL "
        "GROUP BY assignee, status"
    ):
        by_assignee.setdefault(row["assignee"], {})[row["status"]] = int(row["n"])

    oldest_row = conn.execute(
        "SELECT MIN(created_at) AS ts FROM tasks WHERE status = 'ready'"
    ).fetchone()
    now = int(time.time())
    oldest_ready_age = (
        (now - int(oldest_row["ts"]))
        if oldest_row and oldest_row["ts"] is not None else None
    )

    return {
        "by_status": by_status,
        "by_assignee": by_assignee,
        "oldest_ready_age_seconds": oldest_ready_age,
        "now": now,
    }


def _to_epoch(val) -> Optional[int]:
    """Normalise a timestamp to unix epoch seconds.

    Accepts ints (pass-through), numeric strings, and ISO-8601 strings.
    Returns ``None`` for ``None`` / empty values.
    """
    if val is None:
        return None
    if isinstance(val, int):
        return val
    if isinstance(val, float):
        return int(val)
    s = str(val).strip()
    if not s:
        return None
    try:
        return int(s)
    except ValueError:
        pass
    # ISO-8601 fallback (e.g. '2026-05-10T15:00:00Z')
    try:
        from datetime import datetime
        dt = datetime.fromisoformat(s.replace("Z", "+00:00"))
        return int(dt.timestamp())
    except (ValueError, OSError):
        return None


def task_age(task: Task) -> dict:
    """Return age metrics for a single task. All values are seconds or None."""
    now = int(time.time())
    _c = _to_epoch(task.created_at)
    _s = _to_epoch(task.started_at)
    _co = _to_epoch(task.completed_at)
    age_since_created = now - _c if _c is not None else None
    age_since_started = now - _s if _s is not None else None
    time_to_complete = (
        _co - (_s or _c) if _co is not None else None
    )
    return {
        "created_age_seconds": age_since_created,
        "started_age_seconds": age_since_started,
        "time_to_complete_seconds": time_to_complete,
    }


# ---------------------------------------------------------------------------
# Notification subscriptions (used by the gateway kanban-notifier)
# ---------------------------------------------------------------------------

@_guarded_task_mutation(
    action="add_notification_subscription",
    capability=OLYMPUS_CAPABILITY_NOTIFY,
    touch_aggregate=True,
    success=bool,
)
def add_notify_sub(
    conn: sqlite3.Connection,
    *,
    task_id: str,
    platform: str,
    chat_id: str,
    thread_id: Optional[str] = None,
    user_id: Optional[str] = None,
    notifier_profile: Optional[str] = None,
) -> bool:
    """Register a gateway source that wants terminal-state notifications
    for ``task_id``.

    An exact tuple is idempotent. Reusing the unique destination key with a
    different user or notifier profile is an explicit identity conflict; it is
    never silently ignored or backfilled.
    """
    now = int(time.time())
    with write_txn(conn):
        canonical_thread = thread_id or ""
        existing = conn.execute(
            "SELECT user_id, notifier_profile FROM kanban_notify_subs "
            "WHERE task_id = ? AND platform = ? AND chat_id = ? AND thread_id = ?",
            (task_id, platform, chat_id, canonical_thread),
        ).fetchone()
        if existing is not None:
            if (
                existing["user_id"] == user_id
                and existing["notifier_profile"] == notifier_profile
            ):
                return False
            raise OlympusContextError(
                "notification_subscription_identity_conflict",
                "notification destination is already bound to another user or profile",
            )
        inserted = conn.execute(
            """
            INSERT INTO kanban_notify_subs
                (task_id, platform, chat_id, thread_id, user_id, notifier_profile, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                task_id, platform, chat_id, canonical_thread,
                user_id, notifier_profile, now,
            ),
        )
        return bool(inserted.rowcount)


def list_notify_subs(
    conn: sqlite3.Connection, task_id: Optional[str] = None,
) -> list[dict]:
    if task_id is not None:
        rows = conn.execute(
            "SELECT * FROM kanban_notify_subs WHERE task_id = ?", (task_id,),
        ).fetchall()
    else:
        rows = conn.execute("SELECT * FROM kanban_notify_subs").fetchall()
    return [dict(r) for r in rows]


@_guarded_task_mutation(
    action="remove_notification_subscription",
    capability=OLYMPUS_CAPABILITY_NOTIFY,
    touch_aggregate=True,
)
def remove_notify_sub(
    conn: sqlite3.Connection,
    *,
    task_id: str,
    platform: str,
    chat_id: str,
    thread_id: Optional[str] = None,
) -> bool:
    with write_txn(conn):
        cur = conn.execute(
            "DELETE FROM kanban_notify_subs WHERE task_id = ? "
            "AND platform = ? AND chat_id = ? AND thread_id = ?",
            (task_id, platform, chat_id, thread_id or ""),
        )
    return cur.rowcount > 0


def reserve_notification_effect(
    conn: sqlite3.Connection,
    *,
    task_id: str,
    effect_kind: str,
    operation_id: str,
    event_id: int,
    destination_key: str,
    part: str,
    payload: Mapping[str, Any],
    source_identity: Optional[Mapping[str, Any]] = None,
    olympus_auth: Optional[OlympusMutationAuth] = None,
) -> int:
    """Reserve a deterministic notification effect without moving its cursor."""
    if effect_kind not in {"notify_text", "notify_artifact"}:
        raise ValueError("invalid notification effect kind")
    encoded, digest = _canonical_effect_payload(payload)
    now = int(time.time())
    with write_txn(conn):
        task_row = conn.execute(
            "SELECT olympus_context IS NOT NULL AS governed, record_revision "
            "FROM tasks WHERE id = ?",
            (task_id,),
        ).fetchone()
        if task_row is None:
            raise KeyError(task_id)
        governed = bool(task_row["governed"])
        if governed:
            if olympus_auth is None:
                raise OlympusContextError(
                    "olympus_authority_verification_unavailable",
                    "notification reservation requires canonical notifier authority",
                )
            expected_source = _canonical_notifier_effect_source(olympus_auth)
            if source_identity is not None and dict(source_identity) != expected_source:
                raise OlympusContextError(
                    "olympus_effect_source_identity_conflict",
                    "effect source does not match the canonical notifier identity",
                )
            source_mapping = expected_source
        else:
            if source_identity is None:
                raise ValueError("source_identity is required for ordinary effects")
            source_mapping = dict(source_identity)
        source, _ = _canonical_effect_payload(source_mapping)
        subject_revision = int(task_row["record_revision"])
        mutation_binding = {
            "schema_version": NOTIFICATION_EFFECT_RESERVATION_SCHEMA,
            "action": "reserve_notification_effect",
            "task_id": task_id,
            "task_record_revision": subject_revision,
            "effect_kind": effect_kind,
            "operation_id": operation_id,
            "event_id": int(event_id),
            "destination_key": destination_key,
            "part": part,
            "source_identity": source,
            "payload": encoded,
            "payload_sha256": digest,
            "target_post_revision": subject_revision,
        }
        with _task_mutation_permit(
            conn,
            task_id,
            action="reserve_notification_effect",
            capability=OLYMPUS_CAPABILITY_NOTIFY,
            auth=olympus_auth,
            mutation_binding=mutation_binding,
        ):
            permit = _issued_permit_row(conn, task_id)
            if permit is None and task_row is not None and bool(task_row["governed"]):
                raise OlympusContextError(
                    "olympus_authority_verification_unavailable",
                    "notification reservation requires an active exact permit",
                )
            auth_root_id = permit["auth_root_id"] if permit is not None else None
            auth_root_revision = (
                permit["auth_root_revision"] if permit is not None else None
            )
            permitted_revision = (
                permit["subject_revision"]
                if permit is not None
                else subject_revision
            )
            prior = conn.execute(
                "SELECT effect_kind FROM kanban_effect_journal "
                "WHERE operation_id = ? LIMIT 1",
                (operation_id,),
            ).fetchone()
            if prior is not None and prior["effect_kind"] != effect_kind:
                raise OlympusContextError(
                    "notification_effect_identity_conflict",
                    "notification operation id belongs to another effect kind",
                )
            row = conn.execute(
                "INSERT INTO kanban_effect_journal (effect_kind, operation_id, "
                "task_id, event_id, destination_key, part, auth_root_id, "
                "auth_root_revision, target_pre_revision, target_post_revision, "
                "source_identity, payload, payload_sha256, state, created_at, updated_at) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'pending', ?, ?) "
                "ON CONFLICT(effect_kind, operation_id) DO NOTHING RETURNING id",
                (
                    effect_kind, operation_id, task_id, int(event_id),
                    destination_key, part, auth_root_id,
                    auth_root_revision, permitted_revision,
                    permitted_revision, source, encoded, digest, now, now,
                ),
            ).fetchone()
            if row is None:
                row = conn.execute(
                    "SELECT id, task_id, event_id, destination_key, part, "
                    "source_identity, payload, payload_sha256, "
                    "target_pre_revision, target_post_revision "
                    "FROM kanban_effect_journal "
                    "WHERE effect_kind = ? AND operation_id = ?",
                    (effect_kind, operation_id),
                ).fetchone()
                if (
                    row is None
                    or row["task_id"] != task_id
                    or row["event_id"] != int(event_id)
                    or row["destination_key"] != destination_key
                    or row["part"] != part
                    or row["source_identity"] != source
                    or row["payload"] != encoded
                    or row["payload_sha256"] != digest
                    or row["target_pre_revision"] != permitted_revision
                    or row["target_post_revision"] != permitted_revision
                ):
                    raise OlympusContextError(
                        "notification_effect_identity_conflict",
                        "notification operation id was reused with different content",
                    )
    return int(row["id"])


def claim_notification_effect(
    conn: sqlite3.Connection,
    effect_id: int,
    *,
    olympus_auth: Optional[OlympusMutationAuth] = None,
) -> Optional[dict[str, Any]]:
    """CAS one pending notification effect to applying after fresh auth."""
    with write_txn(conn):
        row = conn.execute(
            "SELECT * FROM kanban_effect_journal WHERE id = ? "
            "AND effect_kind IN ('notify_text','notify_artifact')",
            (int(effect_id),),
        ).fetchone()
        if row is None or row["state"] != "pending":
            return None
        updated_at = int(time.time())
        mutation_binding = {
            "schema_version": NOTIFICATION_EFFECT_TRANSITION_SCHEMA,
            "action": "claim_notification_effect",
            "task_id": str(row["task_id"]),
            "task_record_revision": int(
                conn.execute(
                    "SELECT record_revision FROM tasks WHERE id = ?",
                    (row["task_id"],),
                ).fetchone()["record_revision"]
            ),
            "effect_row_id": int(row["id"]),
            "effect_kind": str(row["effect_kind"]),
            "operation_id": str(row["operation_id"]),
            "event_id": int(row["event_id"]),
            "destination_key": str(row["destination_key"]),
            "old_state": "pending",
            "new_state": "applying",
            "error": row["error"],
            "updated_at": updated_at,
            "applied_at": row["applied_at"],
        }
        with _task_mutation_permit(
            conn,
            str(row["task_id"]),
            action="claim_notification_effect",
            capability=OLYMPUS_CAPABILITY_NOTIFY,
            auth=olympus_auth,
            mutation_binding=mutation_binding,
        ):
            updated = conn.execute(
                "UPDATE kanban_effect_journal SET state = 'applying', updated_at = ? "
                "WHERE id = ? AND state = 'pending' RETURNING *",
                (updated_at, int(effect_id)),
            ).fetchone()
            if updated is None:
                return None
    return dict(updated)


def finish_notification_effect(
    conn: sqlite3.Connection,
    effect_id: int,
    *,
    success: bool,
    may_have_sent: bool,
    error: Optional[str] = None,
    olympus_auth: Optional[OlympusMutationAuth] = None,
) -> str:
    """Settle a send result; ambiguity is durable and never auto-retried."""
    state = "applied" if success else ("unknown" if may_have_sent else "not_sent")
    with write_txn(conn):
        row = conn.execute(
            "SELECT * FROM kanban_effect_journal WHERE id = ? "
            "AND effect_kind IN ('notify_text','notify_artifact')",
            (int(effect_id),),
        ).fetchone()
        if row is None:
            raise KeyError(effect_id)
        if row["state"] != "applying":
            return str(row["state"])
        settled_error = str(error)[:2000] if error else None
        updated_at = int(time.time())
        mutation_binding = {
            "schema_version": NOTIFICATION_EFFECT_TRANSITION_SCHEMA,
            "action": "finish_notification_effect",
            "task_id": str(row["task_id"]),
            "task_record_revision": int(
                conn.execute(
                    "SELECT record_revision FROM tasks WHERE id = ?",
                    (row["task_id"],),
                ).fetchone()["record_revision"]
            ),
            "effect_row_id": int(row["id"]),
            "effect_kind": str(row["effect_kind"]),
            "operation_id": str(row["operation_id"]),
            "event_id": int(row["event_id"]),
            "destination_key": str(row["destination_key"]),
            "old_state": "applying",
            "new_state": state,
            "error": settled_error,
            "updated_at": updated_at,
            "applied_at": updated_at,
        }
        with _task_mutation_permit(
            conn,
            str(row["task_id"]),
            action="finish_notification_effect",
            capability=OLYMPUS_CAPABILITY_NOTIFY,
            auth=olympus_auth,
            mutation_binding=mutation_binding,
        ):
            conn.execute(
                "UPDATE kanban_effect_journal SET state = ?, error = ?, "
                "updated_at = ?, applied_at = ? WHERE id = ? AND state = 'applying'",
                (
                    state, settled_error, updated_at, updated_at, int(effect_id),
                ),
            )
    return state


def reconcile_effect_journal(
    conn: sqlite3.Connection,
    *,
    olympus_auth: Optional[OlympusMutationAuth] = None,
) -> int:
    """Resolve crash-left applying effects without ever replaying them."""
    rows = conn.execute(
        "SELECT * FROM kanban_effect_journal WHERE state = 'applying'",
    ).fetchall()
    changed = 0
    for row in rows:
        state = "unknown"
        if row["effect_kind"] == "terminate_worker":
            target = ProcessIdentity(
                host_id=str(row["worker_host_id"] or ""),
                boot_id=str(row["worker_boot_id"] or ""),
                pid=int(row["worker_pid"] or 0),
                start_token=str(row["worker_start_token"] or ""),
            )
            live = read_process_identity(target.pid)
            state = (
                "identity_unverified"
                if live is None and _pid_alive(target.pid)
                else "gone" if live is None else "unknown"
            )
            if live is not None and live != target:
                state = "identity_mismatch"
        try:
            with write_txn(conn):
                with _task_mutation_permit(
                    conn,
                    str(row["task_id"]),
                    action="reconcile_effect_journal",
                    capability=OLYMPUS_CAPABILITY_RECOVER,
                    auth=olympus_auth,
                ):
                    cur = conn.execute(
                        "UPDATE kanban_effect_journal SET state = ?, updated_at = ? "
                        "WHERE id = ? AND state = 'applying'",
                        (state, int(time.time()), int(row["id"])),
                    )
                    if cur.rowcount and row["effect_kind"] == "terminate_worker":
                        conn.execute(
                            "UPDATE task_runs SET process_state = ? WHERE id = ? "
                            "AND process_state = 'termination_pending'",
                            (
                                "terminal" if state == "gone"
                                else "identity_unverified",
                                int(row["run_id"]),
                            ),
                        )
                    changed += int(cur.rowcount or 0)
        except OlympusContextError:
            continue
    return changed


def reconcile_restart_state(
    conn: sqlite3.Connection,
    *,
    olympus_auth: Optional[OlympusMutationAuth] = None,
) -> dict[str, int]:
    """Reconcile durable side effects and worker identities before dispatch.

    Applying effects are settled first so a termination's run fence is no
    longer ambiguous when unfinished worker runs are inspected. Pending
    effects remain pending for their normal exact-once executor; they are never
    replayed merely because the process restarted.
    """
    return {
        "effects": reconcile_effect_journal(conn, olympus_auth=olympus_auth),
        "worker_runs": reconcile_worker_runs(conn, olympus_auth=olympus_auth),
    }


def unseen_events_for_sub(
    conn: sqlite3.Connection,
    *,
    task_id: str,
    platform: str,
    chat_id: str,
    thread_id: Optional[str] = None,
    kinds: Optional[Iterable[str]] = None,
) -> tuple[int, list[Event]]:
    """Return ``(new_cursor, events)`` for a given subscription.

    Only events with ``id > last_event_id`` are returned. The subscription's
    cursor is NOT advanced here; call :func:`advance_notify_cursor` after
    the gateway has successfully delivered the notifications.
    """
    row = conn.execute(
        "SELECT last_event_id FROM kanban_notify_subs "
        "WHERE task_id = ? AND platform = ? AND chat_id = ? AND thread_id = ?",
        (task_id, platform, chat_id, thread_id or ""),
    ).fetchone()
    if row is None:
        return 0, []
    cursor = int(row["last_event_id"])
    kind_list = list(kinds) if kinds else None
    q = (
        "SELECT * FROM task_events WHERE task_id = ? AND id > ? "
        + ("AND kind IN (" + ",".join("?" * len(kind_list)) + ") " if kind_list else "")
        + "ORDER BY id ASC"
    )
    params: list[Any] = [task_id, cursor]
    if kind_list:
        params.extend(kind_list)
    rows = conn.execute(q, params).fetchall()
    out: list[Event] = []
    max_id = cursor
    for r in rows:
        try:
            payload = json.loads(r["payload"]) if r["payload"] else None
        except Exception:
            payload = None
        out.append(Event(
            id=r["id"], task_id=r["task_id"], kind=r["kind"],
            payload=payload, created_at=r["created_at"],
            run_id=(int(r["run_id"]) if "run_id" in r.keys() and r["run_id"] is not None else None),
        ))
        max_id = max(max_id, int(r["id"]))
    return max_id, out


@_guarded_task_mutation(
    action="claim_notification_delivery",
    capability=OLYMPUS_CAPABILITY_NOTIFY,
    touch_aggregate=True,
    success=lambda result: bool(result and result[2]),
)
def claim_unseen_events_for_sub(
    conn: sqlite3.Connection,
    *,
    task_id: str,
    platform: str,
    chat_id: str,
    thread_id: Optional[str] = None,
    kinds: Optional[Iterable[str]] = None,
) -> tuple[int, int, list[Event]]:
    """Atomically claim unseen notification events for one subscription.

    Returns ``(old_cursor, new_cursor, events)``. When events are returned,
    ``kanban_notify_subs.last_event_id`` has already been advanced to
    ``new_cursor`` inside a ``BEGIN IMMEDIATE`` transaction. That makes the
    notifier's read/claim step single-owner across multiple gateway watcher
    processes pointed at the same board DB: concurrent watchers serialize on
    SQLite's writer lock, and only the first process sees and claims a given
    event range.

    Callers should send the claimed events, then either leave the cursor at
    ``new_cursor`` on success or call :func:`rewind_notify_cursor` if delivery
    failed before any terminal unsubscribe removed the row.
    """
    with write_txn(conn):
        row = conn.execute(
            "SELECT last_event_id FROM kanban_notify_subs "
            "WHERE task_id = ? AND platform = ? AND chat_id = ? AND thread_id = ?",
            (task_id, platform, chat_id, thread_id or ""),
        ).fetchone()
        if row is None:
            return 0, 0, []
        old_cursor = int(row["last_event_id"])
        new_cursor, events = unseen_events_for_sub(
            conn,
            task_id=task_id,
            platform=platform,
            chat_id=chat_id,
            thread_id=thread_id,
            kinds=kinds,
        )
        if not events:
            return old_cursor, old_cursor, []
        conn.execute(
            "UPDATE kanban_notify_subs SET last_event_id = ? "
            "WHERE task_id = ? AND platform = ? AND chat_id = ? AND thread_id = ? "
            "AND last_event_id = ?",
            (int(new_cursor), task_id, platform, chat_id, thread_id or "", int(old_cursor)),
        )
        return old_cursor, new_cursor, events


@_guarded_task_mutation(
    action="advance_notification_cursor",
    capability=OLYMPUS_CAPABILITY_NOTIFY,
    touch_aggregate=True,
    success=lambda _result: True,
)
def advance_notify_cursor(
    conn: sqlite3.Connection,
    *,
    task_id: str,
    platform: str,
    chat_id: str,
    thread_id: Optional[str] = None,
    new_cursor: int,
) -> None:
    with write_txn(conn):
        conn.execute(
            "UPDATE kanban_notify_subs SET last_event_id = ? "
            "WHERE task_id = ? AND platform = ? AND chat_id = ? AND thread_id = ?",
            (int(new_cursor), task_id, platform, chat_id, thread_id or ""),
        )


@_guarded_task_mutation(
    action="rewind_notification_cursor",
    capability=OLYMPUS_CAPABILITY_NOTIFY,
    touch_aggregate=True,
)
def rewind_notify_cursor(
    conn: sqlite3.Connection,
    *,
    task_id: str,
    platform: str,
    chat_id: str,
    thread_id: Optional[str] = None,
    claimed_cursor: int,
    old_cursor: int,
) -> bool:
    """Undo a notification claim when delivery fails.

    The CAS guard only rewinds if no later notifier advanced the row after our
    claim. This keeps retry behavior for transient send failures without
    clobbering newer progress.
    """
    with write_txn(conn):
        cur = conn.execute(
            "UPDATE kanban_notify_subs SET last_event_id = ? "
            "WHERE task_id = ? AND platform = ? AND chat_id = ? AND thread_id = ? "
            "AND last_event_id = ?",
            (
                int(old_cursor), task_id, platform, chat_id, thread_id or "",
                int(claimed_cursor),
            ),
        )
    return cur.rowcount > 0


# ---------------------------------------------------------------------------
# Retention + garbage collection
# ---------------------------------------------------------------------------

def gc_events(
    conn: sqlite3.Connection, *, older_than_seconds: int = 30 * 24 * 3600,
) -> int:
    """Delete task_events rows older than ``older_than_seconds`` for tasks
    in a terminal state (``done`` or ``archived``). Returns the number of
    rows deleted. Running / ready / blocked tasks keep their full event
    history."""
    cutoff = int(time.time()) - int(older_than_seconds)
    with write_txn(conn):
        cur = conn.execute(
            "DELETE FROM task_events WHERE created_at < ? AND task_id IN "
            "(SELECT id FROM tasks WHERE status IN ('done', 'archived') "
            "AND olympus_context IS NULL)",
            (cutoff,),
        )
    return int(cur.rowcount or 0)


def gc_worker_logs(
    *, older_than_seconds: int = 30 * 24 * 3600,
    board: Optional[str] = None,
) -> int:
    """Delete worker log files older than ``older_than_seconds``. Returns
    the number of files removed. Kept separate from ``gc_events`` because
    log files live on disk, not in SQLite. Scoped to ``board`` (defaults
    to the active board) — per-board isolation means deleting logs from
    board A cannot touch board B's logs."""
    # Resolve the existing DB without connect()/init side effects. Missing or
    # unreadable governance state preserves every log.
    db_file = kanban_db_path(board=board)
    if not db_file.exists():
        return 0
    try:
        ro = sqlite3.connect(f"{db_file.resolve().as_uri()}?mode=ro", uri=True)
        try:
            has_tasks = ro.execute(
                "SELECT 1 FROM sqlite_master "
                "WHERE type = 'table' AND name = 'tasks'"
            ).fetchone() is not None
            columns = (
                {row[1] for row in ro.execute("PRAGMA table_info(tasks)")}
                if has_tasks else set()
            )
            governed_task_ids = (
                {
                    str(row[0])
                    for row in ro.execute(
                        "SELECT id FROM tasks WHERE olympus_context IS NOT NULL"
                    ).fetchall()
                }
                if "olympus_context" in columns else set()
            )
        finally:
            ro.close()
    except sqlite3.Error as exc:
        raise OlympusContextError(
            "olympus_gc_governance_unreadable",
            "cannot prove worker logs are outside governed retention",
        ) from exc
    log_dir = worker_logs_dir(board=board)
    if not log_dir.exists():
        return 0
    cutoff = time.time() - older_than_seconds
    removed = 0
    for p in log_dir.iterdir():
        try:
            if (
                p.is_file()
                and not any(
                    p.name == f"{task_id}.log"
                    or p.name.startswith(f"{task_id}.log.")
                    for task_id in governed_task_ids
                )
                and p.stat().st_mtime < cutoff
            ):
                p.unlink()
                removed += 1
        except OSError:
            continue
    return removed


# ---------------------------------------------------------------------------
# Worker log accessor
# ---------------------------------------------------------------------------

def worker_log_path(task_id: str, *, board: Optional[str] = None) -> Path:
    """Return the path to a worker's log file. The file may not exist
    (task never spawned, or log already GC'd).

    When ``board`` is None, resolves via the active board (env var →
    current-board file → default). The dispatcher always passes the
    board explicitly to avoid any resolution ambiguity when multiple
    boards exist."""
    return worker_logs_dir(board=board) / f"{task_id}.log"


def read_worker_log(
    task_id: str, *, tail_bytes: Optional[int] = None,
    board: Optional[str] = None,
) -> Optional[str]:
    """Read the worker log for ``task_id``. Returns None if the file
    doesn't exist. If ``tail_bytes`` is set, only the last N bytes are
    returned (useful for the dashboard drawer which shouldn't page megabytes)."""
    path = worker_log_path(task_id, board=board)
    if not path.exists():
        return None
    try:
        if tail_bytes is None:
            return path.read_text(encoding="utf-8", errors="replace")
        size = path.stat().st_size
        with open(path, "rb") as f:
            if size > tail_bytes:
                f.seek(size - tail_bytes)
                # Skip a partial line if we tailed mid-line. But if the
                # window has no newline at all (one giant log line),
                # readline() would eat everything — in that case don't
                # skip and return the raw tail.
                probe = f.tell()
                partial = f.readline()
                if not partial.endswith(b"\n") and f.tell() >= size:
                    f.seek(probe)
            data = f.read()
        return data.decode("utf-8", errors="replace")
    except OSError:
        return None


# ---------------------------------------------------------------------------
# Assignee enumeration (known profiles + per-profile board stats)
# ---------------------------------------------------------------------------

def list_profiles_on_disk() -> list[str]:
    """Return the set of assignee/profile names discovered on disk.

    Includes:
    - named profiles under ``<default-root>/profiles/<name>/config.yaml``
    - the implicit ``default`` profile when the default Hermes root exists

    Reads profile paths directly so this module has no import dependency on
    ``hermes_cli.profiles`` (which pulls in a large chunk of the CLI startup
    path).
    """
    try:
        from hermes_constants import get_default_hermes_root
        default_root = get_default_hermes_root()
        profiles_dir = default_root / "profiles"
    except Exception:
        return []

    names: set[str] = set()
    if default_root.exists():
        names.add("default")

    if profiles_dir.is_dir():
        try:
            for entry in sorted(profiles_dir.iterdir()):
                if not entry.is_dir():
                    continue
                if (entry / "config.yaml").is_file():
                    names.add(entry.name)
        except OSError:
            pass

    return sorted(names)


def known_assignees(conn: sqlite3.Connection) -> list[dict]:
    """Return every assignee name known to the board or on disk.

    Each entry is ``{"name": str, "on_disk": bool, "counts": {status: n}}``.
    A name is included when it's a configured profile on disk OR when
    any non-archived task has it as the assignee. Used by:

    - ``hermes kanban assignees`` for the terminal.
    - The dashboard assignee dropdown (so a fresh profile appears in
      the picker even before it's been given any task).
    - Router-profile heuristics ("who's overloaded?") without scanning
      the whole board.
    """
    on_disk = set(list_profiles_on_disk())

    # Count tasks per (assignee, status), excluding archived.
    counts: dict[str, dict[str, int]] = {}
    for row in conn.execute(
        "SELECT assignee, status, COUNT(*) AS n FROM tasks "
        "WHERE status != 'archived' AND assignee IS NOT NULL "
        "GROUP BY assignee, status"
    ):
        counts.setdefault(row["assignee"], {})[row["status"]] = int(row["n"])

    names = sorted(on_disk | set(counts.keys()))
    return [
        {
            "name": name,
            "on_disk": name in on_disk,
            "counts": counts.get(name, {}),
        }
        for name in names
    ]


# ---------------------------------------------------------------------------
# Runs (attempt history on a task)
# ---------------------------------------------------------------------------

def list_runs(
    conn: sqlite3.Connection,
    task_id: str,
    *,
    include_active: bool = True,
    state_type: Optional[str] = None,
    state_name: Optional[str] = None,
) -> list[Run]:
    """Return all runs for ``task_id`` in start order.

    ``include_active=True`` (default) includes the currently-running
    attempt if any. Set False to return only closed runs (useful for
    "how many prior attempts have there been?" checks).

    When ``state_type`` and ``state_name`` are set, restrict to rows
    where that column equals ``state_name`` (``state_type`` is
    ``status`` or ``outcome``). Both must be passed together.
    """
    if (state_type is None) ^ (state_name is None):
        raise ValueError("state_type and state_name must both be set or both omitted")
    if state_type is not None:
        if state_type not in ("status", "outcome"):
            raise ValueError("state_type must be 'status' or 'outcome'")
    q = "SELECT * FROM task_runs WHERE task_id = ?"
    params: list[Any] = [task_id]
    if not include_active:
        q += " AND ended_at IS NOT NULL"
    if state_type is not None:
        q += f" AND {state_type} = ?"
        params.append(state_name)
    q += " ORDER BY started_at ASC, id ASC"
    rows = conn.execute(q, params).fetchall()
    return [Run.from_row(r) for r in rows]


def get_run(conn: sqlite3.Connection, run_id: int) -> Optional[Run]:
    row = conn.execute(
        "SELECT * FROM task_runs WHERE id = ?", (int(run_id),),
    ).fetchone()
    return Run.from_row(row) if row else None


def latest_run(conn: sqlite3.Connection, task_id: str) -> Optional[Run]:
    """Return the most recent run regardless of outcome (active or closed)."""
    row = conn.execute(
        "SELECT * FROM task_runs WHERE task_id = ? "
        "ORDER BY started_at DESC, id DESC LIMIT 1",
        (task_id,),
    ).fetchone()
    return Run.from_row(row) if row else None


def latest_summary(conn: sqlite3.Connection, task_id: str) -> Optional[str]:
    """Return the latest non-null ``task_runs.summary`` for ``task_id``.

    The kanban-worker skill writes its handoff to ``task_runs.summary``
    via ``complete_task(summary=...)``; ``tasks.result`` is left empty
    unless the caller passes ``result=`` explicitly. Dashboards and CLI
    "show" views need this value to surface what a worker actually did
    — without it, ``tasks.result`` is NULL and the task looks like a
    no-op even when the run completed.

    Picks the most recent run by ``ended_at`` (falling back to ``id``
    for ties or unfinished rows). Returns None if no run has a summary.
    """
    row = conn.execute(
        "SELECT summary FROM task_runs "
        "WHERE task_id = ? AND summary IS NOT NULL AND summary != '' "
        "ORDER BY COALESCE(ended_at, started_at) DESC, id DESC LIMIT 1",
        (task_id,),
    ).fetchone()
    return row["summary"] if row else None


def latest_summaries(
    conn: sqlite3.Connection, task_ids: Iterable[str]
) -> dict[str, str]:
    """Batch-fetch latest non-null summaries for a list of task ids.

    Used by the dashboard board endpoint to attach ``latest_summary`` to
    every card in a single SQL query, avoiding the N+1 pattern of
    calling :func:`latest_summary` per task. Returns a dict mapping
    ``task_id`` → summary string, omitting tasks with no summary.

    Approach: a window function picks the newest non-null-summary row
    per ``task_id``; works against SQLite ≥ 3.25 (default on every
    supported platform).
    """
    ids = list(task_ids)
    if not ids:
        return {}
    placeholders = ",".join("?" for _ in ids)
    rows = conn.execute(
        f"""
        SELECT task_id, summary FROM (
            SELECT task_id, summary,
                   ROW_NUMBER() OVER (
                       PARTITION BY task_id
                       ORDER BY COALESCE(ended_at, started_at) DESC, id DESC
                   ) AS rn
              FROM task_runs
             WHERE task_id IN ({placeholders})
               AND summary IS NOT NULL AND summary != ''
        ) WHERE rn = 1
        """,
        ids,
    ).fetchall()
    return {r["task_id"]: r["summary"] for r in rows}
