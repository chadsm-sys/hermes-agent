"""RED tests for Council Gate V1 config defaults."""

from __future__ import annotations


def test_council_default_config_is_disabled_and_safe():
    from hermes_cli.config import DEFAULT_CONFIG

    council = DEFAULT_CONFIG["council"]

    assert council["enabled"] is False
    assert council["mode"] == "mock"
    assert council["live_model_enabled"] is False
    assert council["triggers"] == ["plan", "scope", "delivery"]
    assert council["artifact_dir"] == "council"


def test_load_config_includes_council_defaults(tmp_path, monkeypatch):
    from hermes_cli.config import load_config

    monkeypatch.setenv("HERMES_HOME", str(tmp_path))

    config = load_config()

    assert config["council"]["enabled"] is False
    assert config["council"]["live_model_enabled"] is False
