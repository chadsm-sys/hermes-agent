#!/usr/bin/env python3
"""Read-only Mission Control state guard.

Prints the canonical local Hermes Desktop / Mission Control state without
mutating sessions, configs, plugins, or backends.

Usage:
  python state_guard.py
  python state_guard.py --json
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sqlite3
import subprocess
import sys
import urllib.error
import urllib.request
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

import yaml

ROOT = Path(__file__).resolve().parent
NODES_PATH = ROOT / "nodes.yaml"
PLUGIN_MANIFEST_PATH = ROOT / "dashboard" / "manifest.json"
PLUGIN_NAME = "mission-control"
MINI_TUNNEL_SPEC = "127.0.0.1:49171:127.0.0.1:49170 mini"


@dataclass
class StateGuardReport:
    hermes_version: str | None
    hermes_home: str
    active_profile: str
    backend_url: str | None
    backend_pid: int | None
    backend_status: dict[str, Any] | None
    plugin_installed: bool
    plugin_enabled: bool
    plugin_visible: bool
    plugin_manifest_ok: bool
    session_count: int | None
    session_store_exists: bool
    session_store_entries: int | None
    state_db_exists: bool
    state_snapshot_count: int | None
    node_modes: list[dict[str, Any]]
    tunnel_status: dict[str, Any]
    fleet_card_health: str
    drift: list[str]
    recommendations: list[str]


def _run(command: list[str]) -> str:
    try:
        proc = subprocess.run(command, capture_output=True, text=True, check=False)
    except FileNotFoundError:
        return ""
    return (proc.stdout or "").strip()


def _hermes_home() -> Path:
    return Path(os.environ.get("HERMES_HOME", str(Path.home() / ".hermes"))).expanduser()


def _active_profile(home: Path) -> str:
    if os.environ.get("HERMES_PROFILE"):
        return os.environ["HERMES_PROFILE"]
    legacy = home / "active_profile"
    if legacy.exists():
        value = legacy.read_text(encoding="utf-8").strip()
        if value:
            return value
    desktop_active = Path.home() / "Library" / "Application Support" / "Hermes" / "active-profile.json"
    if desktop_active.exists():
        try:
            payload = json.loads(desktop_active.read_text(encoding="utf-8"))
            value = str(payload.get("profile") or payload.get("activeProfile") or "").strip()
            if value:
                return value
        except Exception:
            pass
    return "default (implicit; no profile pin found)"


def _hermes_version() -> str | None:
    out = _run(["hermes", "--version"])
    match = re.search(r"(\d+\.\d+\.\d+)", out)
    return match.group(1) if match else (out or None)


def _desktop_backend() -> tuple[str | None, int | None]:
    ps_out = _run(["ps", "-Ao", "pid=,ppid=,command="])
    hermes_pid = None
    child_rows: list[tuple[int, int, str]] = []
    for line in ps_out.splitlines():
        parts = line.strip().split(None, 2)
        if len(parts) != 3:
            continue
        pid_s, ppid_s, command = parts
        try:
            pid = int(pid_s)
            ppid = int(ppid_s)
        except ValueError:
            continue
        if "Hermes.app/Contents/MacOS/Hermes" in command:
            hermes_pid = pid
        child_rows.append((pid, ppid, command))
    if hermes_pid is None:
        return None, None
    for pid, ppid, _command in child_rows:
        if ppid != hermes_pid:
            continue
        lsof_out = _run(["lsof", "-nP", "-a", "-p", str(pid), "-iTCP", "-sTCP:LISTEN"])
        match = re.search(r"TCP\s+127\.0\.0\.1:(\d+)\s+\(LISTEN\)", lsof_out)
        if match:
            port = int(match.group(1))
            return f"http://127.0.0.1:{port}", pid
    return None, None


def _json_get(url: str, timeout: float = 3.0) -> dict[str, Any] | None:
    try:
        req = urllib.request.Request(url, headers={"Accept": "application/json", "Connection": "close"})
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read().decode("utf-8", "replace"))
    except (urllib.error.URLError, TimeoutError, OSError, ValueError, json.JSONDecodeError):
        return None


def _plugin_enabled(home: Path) -> tuple[bool, bool, bool]:
    installed = (home / "plugins" / PLUGIN_NAME).exists()
    enabled = False
    config_path = home / "config.yaml"
    if config_path.exists():
        try:
            cfg = yaml.safe_load(config_path.read_text(encoding="utf-8")) or {}
            enabled_names = ((cfg.get("plugins") or {}).get("enabled") or [])
            enabled = PLUGIN_NAME in enabled_names
        except Exception:
            enabled = False
    visible = installed and enabled
    return installed, enabled, visible


def _plugin_manifest_ok() -> bool:
    try:
        data = json.loads(PLUGIN_MANIFEST_PATH.read_text(encoding="utf-8"))
    except Exception:
        return False
    return (
        data.get("name") == PLUGIN_NAME
        and data.get("tab", {}).get("path") == "mission-control"
        and data.get("api") == "plugin_api.py"
        and data.get("entry") == "dist/plugin.js"
    )


def _session_metrics(home: Path) -> tuple[int | None, bool, int | None, bool, int | None]:
    state_db = home / "state.db"
    sessions_dir = home / "sessions"
    snapshots_dir = home / "state-snapshots"
    session_count = None
    if state_db.exists():
        try:
            con = sqlite3.connect(state_db)
            try:
                session_count = int(con.execute("select count(*) from sessions").fetchone()[0])
            finally:
                con.close()
        except Exception:
            session_count = None
    session_entries = None
    if sessions_dir.exists() and sessions_dir.is_dir():
        session_entries = len(list(sessions_dir.iterdir()))
    snapshot_count = None
    if snapshots_dir.exists() and snapshots_dir.is_dir():
        snapshot_count = len(list(snapshots_dir.iterdir()))
    return session_count, sessions_dir.exists(), session_entries, state_db.exists(), snapshot_count


def _node_modes() -> list[dict[str, Any]]:
    try:
        raw = yaml.safe_load(NODES_PATH.read_text(encoding="utf-8")) or {}
    except Exception:
        return []
    nodes = raw.get("nodes") if isinstance(raw, dict) else []
    out = []
    for node in nodes or []:
        out.append(
            {
                "id": node.get("id"),
                "enabled": bool(node.get("enabled")),
                "read_only": bool(node.get("read_only")),
                "mode": "live-read-only" if node.get("enabled") else "configured-disabled",
                "url": node.get("url"),
                "token_configured": bool(node.get("token_env") and os.environ.get(str(node.get("token_env")))),
            }
        )
    return out


def _tunnel_status() -> dict[str, Any]:
    ps_out = _run(["ps", "-Ao", "pid=,command="])
    pid = None
    command = None
    for line in ps_out.splitlines():
        if MINI_TUNNEL_SPEC in line:
            parts = line.strip().split(None, 1)
            if len(parts) == 2:
                pid = int(parts[0])
                command = parts[1]
                break
    status_payload = _json_get("http://127.0.0.1:49171/api/status", timeout=2.0)
    reachable = status_payload is not None
    return {
        "process_running": pid is not None,
        "pid": pid,
        "reachable": reachable,
        "target": "http://127.0.0.1:49171",
        "status_version": status_payload.get("version") if status_payload else None,
        "gateway_running": status_payload.get("gateway_running") if status_payload else None,
        "command": command,
    }


def _fleet_card_health(visible: bool, node_modes: list[dict[str, Any]], tunnel: dict[str, Any]) -> str:
    if not visible:
        return "plugin-not-visible-in-desktop"
    node_ids = {node.get("id") for node in node_modes}
    if "mac-mini" in node_ids and not tunnel.get("reachable"):
        return "degraded-mac-mini-tunnel-unreachable"
    return "ready"


def collect_report() -> StateGuardReport:
    home = _hermes_home()
    version = _hermes_version()
    active_profile = _active_profile(home)
    backend_url, backend_pid = _desktop_backend()
    backend_status = _json_get(f"{backend_url}/api/status") if backend_url else None
    plugin_installed, plugin_enabled, plugin_visible = _plugin_enabled(home)
    session_count, session_store_exists, session_store_entries, state_db_exists, snapshot_count = _session_metrics(home)
    node_modes = _node_modes()
    tunnel_status = _tunnel_status()
    plugin_manifest_ok = _plugin_manifest_ok()

    drift: list[str] = []
    recommendations: list[str] = []

    if version and not version.startswith("0.18."):
        drift.append(f"Hermes version {version} is not v0.18.x")
    if backend_status:
        current = backend_status.get("config_version")
        latest = backend_status.get("latest_config_version")
        if isinstance(current, int) and isinstance(latest, int) and current < latest:
            drift.append(f"Desktop backend config_version is {current} while latest_config_version is {latest}")
    if active_profile.startswith("default (implicit"):
        drift.append("Desktop profile is implicit default; no explicit profile pin is recorded")
    if not plugin_installed:
        drift.append("Mission Control plugin is not installed under ~/.hermes/plugins/mission-control")
    if plugin_installed and not plugin_enabled:
        drift.append("Mission Control plugin is installed but not enabled in ~/.hermes/config.yaml")
    if not plugin_manifest_ok:
        drift.append("Mission Control plugin manifest invariants failed")
    if not tunnel_status.get("process_running"):
        drift.append("Mac mini SSH tunnel process is not running")
    elif not tunnel_status.get("reachable"):
        drift.append("Mac mini SSH tunnel process exists but /api/status is not reachable")

    recommendations.append("Canonical desktop state: Hermes Desktop v0.18.x on HERMES_HOME ~/.hermes using the default profile, with the local desktop backend bound on loopback only.")
    recommendations.append("Canonical Mission Control state: keep nodes.yaml loopback-only and read_only for all enabled nodes; mac-mini remains reachable only through the existing SSH tunnel on 127.0.0.1:49171 -> 127.0.0.1:49170.")
    if not plugin_visible:
        recommendations.append("To make Mission Control visible in Desktop without touching session stores, install the plugin repo at ~/.hermes/plugins/mission-control and add mission-control to plugins.enabled in ~/.hermes/config.yaml, then relaunch Desktop when change control allows.")
    if backend_status and backend_status.get("config_version") != backend_status.get("latest_config_version"):
        recommendations.append("Before future Mission Control work, treat the local Desktop backend as drifted until its config schema mismatch (config_version vs latest_config_version) is intentionally reconciled in a controlled maintenance step.")

    return StateGuardReport(
        hermes_version=version,
        hermes_home=str(home),
        active_profile=active_profile,
        backend_url=backend_url,
        backend_pid=backend_pid,
        backend_status=backend_status,
        plugin_installed=plugin_installed,
        plugin_enabled=plugin_enabled,
        plugin_visible=plugin_visible,
        plugin_manifest_ok=plugin_manifest_ok,
        session_count=session_count,
        session_store_exists=session_store_exists,
        session_store_entries=session_store_entries,
        state_db_exists=state_db_exists,
        state_snapshot_count=snapshot_count,
        node_modes=node_modes,
        tunnel_status=tunnel_status,
        fleet_card_health=_fleet_card_health(plugin_visible, node_modes, tunnel_status),
        drift=drift,
        recommendations=recommendations,
    )


def _print_text(report: StateGuardReport) -> None:
    print("Mission Control State Guard")
    print(f"Hermes version: {report.hermes_version or 'unknown'}")
    print(f"HERMES_HOME: {report.hermes_home}")
    print(f"Active profile: {report.active_profile}")
    print(f"Backend URL: {report.backend_url or 'unknown'}")
    print(f"Plugin enabled state: installed={report.plugin_installed} enabled={report.plugin_enabled} visible={report.plugin_visible}")
    print(f"Session count: {report.session_count if report.session_count is not None else 'unknown'}")
    print("Mission Control node modes:")
    for node in report.node_modes:
        print(
            f"  - {node['id']}: mode={node['mode']} enabled={node['enabled']} "
            f"read_only={node['read_only']} url={node['url']} token_configured={node['token_configured']}"
        )
    tunnel = report.tunnel_status
    print(
        "Tunnel status: "
        f"running={tunnel['process_running']} reachable={tunnel['reachable']} "
        f"pid={tunnel['pid']} target={tunnel['target']}"
    )
    print(f"Fleet card health: {report.fleet_card_health}")
    print(f"Session stores: state_db_exists={report.state_db_exists} sessions_dir={report.session_store_exists} snapshots={report.state_snapshot_count}")
    if report.backend_status:
        print(
            "Backend status: "
            f"config_version={report.backend_status.get('config_version')} "
            f"latest_config_version={report.backend_status.get('latest_config_version')} "
            f"gateway_running={report.backend_status.get('gateway_running')}"
        )
    print("Drift:")
    if report.drift:
        for item in report.drift:
            print(f"  - {item}")
    else:
        print("  - none")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Read-only Mission Control state guard")
    parser.add_argument("--json", action="store_true", help="Emit machine-readable JSON")
    args = parser.parse_args(argv)
    report = collect_report()
    if args.json:
        print(json.dumps(asdict(report), indent=2, sort_keys=True))
    else:
        _print_text(report)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
