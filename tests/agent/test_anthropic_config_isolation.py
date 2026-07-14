"""Hermetic credential-boundary tests for Anthropic account selection.

Every credential value is synthetic. The fixture redirects HOME and
HERMES_HOME before importing the adapter, stubs Keychain, pool, and OAuth
refresh access, and never reads operator credential state.
"""

import importlib
import json
import logging
import time
from types import SimpleNamespace

import pytest


FUTURE_MS = int(time.time() * 1000) + 3_600_000
PAST_MS = 1
_CREDENTIAL_ENV = (
    "ANTHROPIC_TOKEN",
    "CLAUDE_CODE_OAUTH_TOKEN",
    "CLAUDE_CONFIG_DIR",
    "ANTHROPIC_API_KEY",
)


def _oauth_record(token, *, refresh="synthetic-refresh", expires_at=FUTURE_MS):
    return {
        "claudeAiOauth": {
            "accessToken": token,
            "refreshToken": refresh,
            "expiresAt": expires_at,
        }
    }


def _write_record(config_dir, token, *, refresh="synthetic-refresh", expires_at=FUTURE_MS):
    config_dir.mkdir(parents=True, exist_ok=True)
    path = config_dir / ".credentials.json"
    path.write_text(
        json.dumps(
            _oauth_record(token, refresh=refresh, expires_at=expires_at)
        ),
        encoding="utf-8",
    )
    return path


@pytest.fixture
def isolated_anthropic(tmp_path, monkeypatch):
    """Install synthetic roots and deny all external credential access."""
    home = tmp_path / "home"
    hermes_home = tmp_path / "hermes"
    cache = tmp_path / "cache"
    home.mkdir()
    hermes_home.mkdir()
    cache.mkdir()

    monkeypatch.setenv("HOME", str(home))
    monkeypatch.setenv("HERMES_HOME", str(hermes_home))
    monkeypatch.setenv("XDG_CACHE_HOME", str(cache))
    for name in _CREDENTIAL_ENV:
        monkeypatch.delenv(name, raising=False)

    adapter = importlib.import_module("agent.anthropic_adapter")
    pool_module = importlib.import_module("agent.credential_pool")
    real_keychain_reader = adapter._read_claude_code_credentials_from_keychain

    keychain_calls = []
    pool_calls = []
    refresh_calls = []

    def _empty_keychain():
        keychain_calls.append("read")
        return None

    empty_pool = SimpleNamespace(
        _available_entries=lambda **kwargs: pool_calls.append(kwargs) or []
    )

    def _load_empty_pool(provider):
        pool_calls.append({"provider": provider})
        return empty_pool

    def _deny_refresh(*args, **kwargs):
        refresh_calls.append((args, kwargs))
        raise AssertionError("network refresh is forbidden in the isolated harness")

    monkeypatch.setattr(
        adapter, "_read_claude_code_credentials_from_keychain", _empty_keychain
    )
    monkeypatch.setattr(pool_module, "load_pool", _load_empty_pool)
    monkeypatch.setattr(adapter, "refresh_anthropic_oauth_pure", _deny_refresh)

    return SimpleNamespace(
        adapter=adapter,
        home=home,
        hermes_home=hermes_home,
        cache=cache,
        keychain_calls=keychain_calls,
        pool_calls=pool_calls,
        refresh_calls=refresh_calls,
        pool_module=pool_module,
        real_keychain_reader=real_keychain_reader,
    )


def test_anthropic_token_precedes_conflicting_explicit_and_selected_sources(
    isolated_anthropic, monkeypatch
):
    harness = isolated_anthropic
    selected = harness.home / "selected"
    _write_record(selected, "synthetic-selected")
    monkeypatch.setenv("CLAUDE_CONFIG_DIR", str(selected))
    monkeypatch.setenv("ANTHROPIC_TOKEN", "synthetic-anthropic-env")
    monkeypatch.setenv("CLAUDE_CODE_OAUTH_TOKEN", "synthetic-claude-env")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "synthetic-api-key")

    assert harness.adapter.resolve_anthropic_token() == "synthetic-anthropic-env"
    assert harness.keychain_calls == []
    assert harness.pool_calls == []


def test_claude_oauth_token_precedes_selected_and_lower_sources(
    isolated_anthropic, monkeypatch
):
    harness = isolated_anthropic
    selected = harness.home / "selected"
    _write_record(selected, "synthetic-selected")
    monkeypatch.setenv("CLAUDE_CONFIG_DIR", str(selected))
    monkeypatch.setenv("CLAUDE_CODE_OAUTH_TOKEN", "synthetic-claude-env")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "synthetic-api-key")

    assert harness.adapter.resolve_anthropic_token() == "synthetic-claude-env"
    assert harness.keychain_calls == []
    assert harness.pool_calls == []


def test_explicit_token_survives_invalid_lower_priority_selection(
    isolated_anthropic, monkeypatch
):
    harness = isolated_anthropic
    monkeypatch.setenv("CLAUDE_CONFIG_DIR", "relative/account")
    monkeypatch.setenv("ANTHROPIC_TOKEN", "synthetic-anthropic-env")

    assert harness.adapter.resolve_anthropic_token() == "synthetic-anthropic-env"
    assert harness.keychain_calls == []
    assert harness.pool_calls == []


def test_selected_config_directory_is_canonical_and_exclusive(
    isolated_anthropic, monkeypatch
):
    harness = isolated_anthropic
    selected = harness.home / "accounts" / "selected"
    _write_record(selected, "synthetic-selected")
    _write_record(harness.home / ".claude", "synthetic-default")
    monkeypatch.setenv("CLAUDE_CONFIG_DIR", str(selected.parent / ".." / "accounts" / "selected"))
    monkeypatch.setenv("ANTHROPIC_API_KEY", "synthetic-api-key")

    assert harness.adapter._explicit_claude_config_dir() == selected.resolve()
    assert harness.adapter.resolve_anthropic_token() == "synthetic-selected"
    assert harness.keychain_calls == []
    assert harness.pool_calls == []


def test_tilde_selected_directory_expands_inside_isolated_home(
    isolated_anthropic, monkeypatch
):
    harness = isolated_anthropic
    selected = harness.home / "claude-account"
    _write_record(selected, "synthetic-selected")
    monkeypatch.setenv("CLAUDE_CONFIG_DIR", "~/claude-account")

    assert harness.adapter._explicit_claude_config_dir() == selected.resolve()
    assert harness.adapter.resolve_anthropic_token() == "synthetic-selected"


def test_default_file_fallback_without_selection(isolated_anthropic):
    harness = isolated_anthropic
    _write_record(harness.home / ".claude", "synthetic-default")

    assert harness.adapter.resolve_anthropic_token() == "synthetic-default"
    assert harness.keychain_calls == ["read"]
    assert harness.pool_calls == []


@pytest.mark.parametrize("empty_selection", ["", "   "])
def test_empty_or_whitespace_selection_preserves_default_fallback(
    empty_selection, isolated_anthropic, monkeypatch
):
    harness = isolated_anthropic
    _write_record(harness.home / ".claude", "synthetic-default")
    monkeypatch.setenv("CLAUDE_CONFIG_DIR", empty_selection)

    assert harness.adapter.resolve_anthropic_token() == "synthetic-default"


def test_keychain_fallback_without_selection(isolated_anthropic, monkeypatch):
    harness = isolated_anthropic
    monkeypatch.setattr(
        harness.adapter,
        "_read_claude_code_credentials_from_keychain",
        lambda: {
            "accessToken": "synthetic-keychain",
            "refreshToken": "synthetic-refresh",
            "expiresAt": FUTURE_MS,
            "source": "macos_keychain",
        },
    )

    assert harness.adapter.resolve_anthropic_token() == "synthetic-keychain"
    assert harness.pool_calls == []


def test_non_text_keychain_payload_fails_closed(isolated_anthropic, monkeypatch):
    harness = isolated_anthropic
    monkeypatch.setattr(harness.adapter.platform, "system", lambda: "Darwin")
    monkeypatch.setattr(
        harness.adapter.subprocess,
        "run",
        lambda *args, **kwargs: SimpleNamespace(
            returncode=0,
            stdout=SimpleNamespace(),
        ),
    )

    assert harness.real_keychain_reader() is None


def test_default_file_and_keychain_conflict_reconciles_by_freshness(
    isolated_anthropic, monkeypatch
):
    harness = isolated_anthropic
    _write_record(
        harness.home / ".claude",
        "synthetic-file-newer",
        expires_at=FUTURE_MS,
    )
    monkeypatch.setattr(
        harness.adapter,
        "_read_claude_code_credentials_from_keychain",
        lambda: {
            "accessToken": "synthetic-keychain-older",
            "refreshToken": "synthetic-refresh",
            "expiresAt": FUTURE_MS - 60_000,
            "source": "macos_keychain",
        },
    )

    assert harness.adapter.resolve_anthropic_token() == "synthetic-file-newer"


def test_credential_pool_fallback_is_read_only(isolated_anthropic, monkeypatch):
    harness = isolated_anthropic
    captured = []
    entry = SimpleNamespace(auth_type="oauth", access_token="synthetic-pool")
    pool = SimpleNamespace(
        _available_entries=lambda **kwargs: captured.append(kwargs) or [entry]
    )
    monkeypatch.setattr(harness.pool_module, "load_pool", lambda provider: pool)

    assert harness.adapter.resolve_anthropic_token() == "synthetic-pool"
    assert captured == [{"clear_expired": False, "refresh": False}]


def test_api_key_fallback_without_higher_source(isolated_anthropic, monkeypatch):
    harness = isolated_anthropic
    monkeypatch.setenv("ANTHROPIC_API_KEY", "synthetic-api-key")

    assert harness.adapter.resolve_anthropic_token() == "synthetic-api-key"


def test_missing_credentials_returns_none(isolated_anthropic):
    assert isolated_anthropic.adapter.resolve_anthropic_token() is None


@pytest.mark.parametrize("selected_value", ["relative/account", "./account"])
def test_relative_selected_path_fails_closed(
    selected_value, isolated_anthropic, monkeypatch
):
    harness = isolated_anthropic
    _write_record(harness.home / ".claude", "synthetic-default")
    monkeypatch.setenv("CLAUDE_CONFIG_DIR", selected_value)
    monkeypatch.setenv("ANTHROPIC_API_KEY", "synthetic-api-key")

    assert harness.adapter.resolve_anthropic_token() is None
    assert harness.keychain_calls == []
    assert harness.pool_calls == []


def test_nonexistent_selected_path_fails_closed(isolated_anthropic, monkeypatch):
    harness = isolated_anthropic
    monkeypatch.setenv("CLAUDE_CONFIG_DIR", str(harness.home / "missing"))
    monkeypatch.setenv("ANTHROPIC_API_KEY", "synthetic-api-key")

    assert harness.adapter.resolve_anthropic_token() is None
    assert harness.keychain_calls == []
    assert harness.pool_calls == []


def test_existing_selected_directory_without_record_fails_closed(
    isolated_anthropic, monkeypatch
):
    harness = isolated_anthropic
    selected = harness.home / "empty-selected"
    selected.mkdir()
    _write_record(harness.home / ".claude", "synthetic-default")
    monkeypatch.setenv("CLAUDE_CONFIG_DIR", str(selected))
    monkeypatch.setenv("ANTHROPIC_API_KEY", "synthetic-api-key")

    assert harness.adapter.resolve_anthropic_token() is None
    assert harness.keychain_calls == []
    assert harness.pool_calls == []


def test_broken_symlink_selected_path_fails_closed(isolated_anthropic, monkeypatch):
    harness = isolated_anthropic
    link = harness.home / "broken-link"
    link.symlink_to(harness.home / "missing-target", target_is_directory=True)
    monkeypatch.setenv("CLAUDE_CONFIG_DIR", str(link))
    monkeypatch.setenv("ANTHROPIC_API_KEY", "synthetic-api-key")

    assert harness.adapter.resolve_anthropic_token() is None
    assert harness.keychain_calls == []
    assert harness.pool_calls == []


def test_valid_directory_symlink_is_canonicalized_and_accepted(
    isolated_anthropic, monkeypatch
):
    harness = isolated_anthropic
    target = harness.home / "canonical-account"
    _write_record(target, "synthetic-selected")
    link = harness.home / "account-link"
    link.symlink_to(target, target_is_directory=True)
    monkeypatch.setenv("CLAUDE_CONFIG_DIR", str(link))

    assert harness.adapter._explicit_claude_config_dir() == target.resolve()
    assert harness.adapter.resolve_anthropic_token() == "synthetic-selected"


def test_selected_path_resolving_to_file_fails_closed(
    isolated_anthropic, monkeypatch
):
    harness = isolated_anthropic
    selected_file = harness.home / "not-a-directory"
    selected_file.write_text("synthetic", encoding="utf-8")
    monkeypatch.setenv("CLAUDE_CONFIG_DIR", str(selected_file))
    monkeypatch.setenv("ANTHROPIC_API_KEY", "synthetic-api-key")

    assert harness.adapter.resolve_anthropic_token() is None
    assert harness.keychain_calls == []
    assert harness.pool_calls == []


@pytest.mark.parametrize(
    "record",
    [
        "{not-json",
        json.dumps({"claudeAiOauth": {"refreshToken": "synthetic-refresh"}}),
    ],
)
def test_malformed_or_tokenless_selected_record_fails_closed(
    record, isolated_anthropic, monkeypatch
):
    harness = isolated_anthropic
    selected = harness.home / "selected"
    selected.mkdir()
    (selected / ".credentials.json").write_text(record, encoding="utf-8")
    monkeypatch.setenv("CLAUDE_CONFIG_DIR", str(selected))
    monkeypatch.setenv("ANTHROPIC_API_KEY", "synthetic-api-key")

    assert harness.adapter.resolve_anthropic_token() is None
    assert harness.keychain_calls == []
    assert harness.pool_calls == []


def test_unreadable_selected_record_fails_closed(isolated_anthropic, monkeypatch):
    harness = isolated_anthropic
    selected = harness.home / "selected"
    selected_path = _write_record(selected, "synthetic-selected")
    original_read_text = harness.adapter.Path.read_text

    def _raise_for_selected(path, *args, **kwargs):
        if path == selected_path:
            raise OSError("synthetic unreadable record")
        return original_read_text(path, *args, **kwargs)

    monkeypatch.setattr(harness.adapter.Path, "read_text", _raise_for_selected)
    monkeypatch.setenv("CLAUDE_CONFIG_DIR", str(selected))
    monkeypatch.setenv("ANTHROPIC_API_KEY", "synthetic-api-key")

    assert harness.adapter.resolve_anthropic_token() is None
    assert harness.keychain_calls == []
    assert harness.pool_calls == []


def test_selected_expired_record_refreshes_and_writes_only_selected_account(
    isolated_anthropic, monkeypatch
):
    harness = isolated_anthropic
    selected = harness.home / "selected"
    selected_path = _write_record(
        selected,
        "synthetic-expired",
        refresh="synthetic-refresh-old",
        expires_at=PAST_MS,
    )
    default_path = _write_record(harness.home / ".claude", "synthetic-default")
    default_before = default_path.read_bytes()
    monkeypatch.setenv("CLAUDE_CONFIG_DIR", str(selected))

    calls = []

    def _synthetic_refresh(refresh_token, *, use_json=False):
        calls.append((refresh_token, use_json))
        return {
            "access_token": "synthetic-refreshed",
            "refresh_token": "synthetic-refresh-new",
            "expires_at_ms": FUTURE_MS,
        }

    monkeypatch.setattr(
        harness.adapter, "refresh_anthropic_oauth_pure", _synthetic_refresh
    )

    assert harness.adapter.resolve_anthropic_token() == "synthetic-refreshed"
    assert calls == [("synthetic-refresh-old", False)]
    assert json.loads(selected_path.read_text(encoding="utf-8"))[
        "claudeAiOauth"
    ]["accessToken"] == "synthetic-refreshed"
    assert default_path.read_bytes() == default_before
    assert harness.keychain_calls == []
    assert harness.pool_calls == []


def test_selected_refresh_failure_does_not_fall_through(
    isolated_anthropic, monkeypatch
):
    harness = isolated_anthropic
    selected = harness.home / "selected"
    _write_record(
        selected,
        "synthetic-expired",
        refresh="synthetic-refresh-old",
        expires_at=PAST_MS,
    )
    monkeypatch.setenv("CLAUDE_CONFIG_DIR", str(selected))
    monkeypatch.setenv("ANTHROPIC_API_KEY", "synthetic-api-key")

    assert harness.adapter.resolve_anthropic_token() is None
    assert len(harness.refresh_calls) == 1
    assert harness.keychain_calls == []
    assert harness.pool_calls == []


def test_config_isolation_across_accounts(isolated_anthropic, monkeypatch):
    harness = isolated_anthropic
    account_a = harness.home / "accounts" / "a"
    account_b = harness.home / "accounts" / "b"
    _write_record(account_a, "synthetic-account-a")
    _write_record(account_b, "synthetic-account-b")

    monkeypatch.setenv("CLAUDE_CONFIG_DIR", str(account_a))
    assert harness.adapter.resolve_anthropic_token() == "synthetic-account-a"

    monkeypatch.setenv("CLAUDE_CONFIG_DIR", str(account_b))
    assert harness.adapter.resolve_anthropic_token() == "synthetic-account-b"

    monkeypatch.setenv("CLAUDE_CONFIG_DIR", str(account_a))
    assert harness.adapter.resolve_anthropic_token() == "synthetic-account-a"


def test_failure_diagnostics_do_not_expose_synthetic_secrets(
    isolated_anthropic, monkeypatch, caplog
):
    harness = isolated_anthropic
    selected = harness.home / "selected"
    synthetic_secrets = (
        "synthetic-access-secret",
        "synthetic-refresh-secret",
        "synthetic-api-secret",
    )
    _write_record(
        selected,
        synthetic_secrets[0],
        refresh=synthetic_secrets[1],
        expires_at=PAST_MS,
    )
    monkeypatch.setenv("CLAUDE_CONFIG_DIR", str(selected))
    monkeypatch.setenv("ANTHROPIC_API_KEY", synthetic_secrets[2])

    with caplog.at_level(logging.DEBUG, logger=harness.adapter.__name__):
        assert harness.adapter.resolve_anthropic_token() is None

    log_text = caplog.text
    for secret in synthetic_secrets:
        assert secret not in log_text
    assert "Authorization" not in log_text
