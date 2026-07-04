from __future__ import annotations

import json
from pathlib import Path

import state_guard


def test_plugin_manifest_invariants_hold():
    assert state_guard._plugin_manifest_ok() is True


def test_node_modes_respect_registry_invariants():
    nodes = state_guard._node_modes()
    assert nodes, "nodes.yaml should load"
    by_id = {node["id"]: node for node in nodes}
    assert by_id["mbp"]["mode"] == "live-read-only"
    assert by_id["mac-mini"]["mode"] == "live-read-only"
    assert by_id["mac-mini"]["read_only"] is True
    assert by_id["dgx-spark"]["mode"] == "configured-disabled"
    for node in nodes:
        if node["enabled"]:
            assert str(node["url"]).startswith("http://127.0.0.1")


def test_active_profile_falls_back_to_implicit_default(tmp_path: Path, monkeypatch):
    monkeypatch.delenv("HERMES_PROFILE", raising=False)
    monkeypatch.setattr(state_guard.Path, "home", staticmethod(lambda: tmp_path))
    hermes_home = tmp_path / ".hermes"
    hermes_home.mkdir()
    assert state_guard._active_profile(hermes_home) == "default (implicit; no profile pin found)"


def test_plugin_enabled_requires_install_and_config(tmp_path: Path):
    home = tmp_path / ".hermes"
    (home / "plugins" / "mission-control").mkdir(parents=True)
    (home / "config.yaml").write_text("plugins:\n  enabled:\n    - mission-control\n", encoding="utf-8")
    installed, enabled, visible = state_guard._plugin_enabled(home)
    assert (installed, enabled, visible) == (True, True, True)


def test_fleet_card_health_degrades_when_plugin_hidden():
    tunnel = {"reachable": True}
    assert state_guard._fleet_card_health(False, [], tunnel) == "plugin-not-visible-in-desktop"


def test_json_output_shape_is_serializable():
    report = state_guard.collect_report()
    payload = json.loads(json.dumps(state_guard.asdict(report)))
    assert "hermes_version" in payload
    assert "node_modes" in payload
    assert "tunnel_status" in payload
