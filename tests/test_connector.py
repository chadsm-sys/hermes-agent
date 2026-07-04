"""Safety + behavior tests for the Mission Control read-only connector.

Covers every M2 Phase-3 requirement:
  disabled nodes never contacted · missing token degrades · expired/401
  degrades · timeout degrades · malformed JSON degrades · offline degrades ·
  retry cap respected · circuit breaker opens · GET-only under all
  circumstances · unexpected fields redacted.

Run: ~/.hermes/hermes-agent/venv/bin/python tests/test_connector.py
"""

from __future__ import annotations

import io
import json
import sys
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "dashboard"))

import connector  # noqa: E402


class RequestLog:
    """Monkeypatched transport that records every request the connector makes."""

    def __init__(self, responses=None, exc=None):
        self.requests: list[urllib.request.Request] = []
        self.responses = list(responses or [])
        self.exc = exc
        self.sleeps: list[float] = []

    def urlopen(self, req, timeout=None):
        self.requests.append(req)
        if self.exc is not None:
            raise self.exc
        body = self.responses.pop(0) if self.responses else "{}"

        class _Resp:
            status = 200
            def __init__(self, data): self._data = data
            def read(self): return self._data.encode()
            def __enter__(self): return self
            def __exit__(self, *a): return False

        return _Resp(body)


def patched(log: RequestLog):
    """Context: swap transport + neutralize backoff sleeps."""
    class _Ctx:
        def __enter__(self):
            self._urlopen = urllib.request.urlopen
            self._sleep = connector.time.sleep
            urllib.request.urlopen = log.urlopen
            connector.time.sleep = lambda s: log.sleeps.append(s)
            connector.reset_for_tests()
            return log
        def __exit__(self, *a):
            urllib.request.urlopen = self._urlopen
            connector.time.sleep = self._sleep
            connector.reset_for_tests()
            return False
    return _Ctx()


NODE = {"id": "test-node", "label": "T", "role": "lab", "enabled": True,
        "read_only": True, "url": "http://192.0.2.1:9", "token_env": "MC_TEST_TOKEN"}

GOOD_STATUS = json.dumps({"version": "0.18.0", "gateway_running": True,
                          "gateway_state": "running",
                          "secret_field": "SHOULD-NEVER-APPEAR",
                          "gateway_platforms": {"telegram": "connected"}})
GOOD_STATS = json.dumps({"hostname": "mini", "cpu_percent": 12.5,
                         "uptime_seconds": 86400.0,
                         "memory": {"percent": 41.0, "total": 1, "used": 1,
                                    "available": 1, "secret": "NO"},
                         "disk": {"percent": 63.0},
                         "env_dump": {"API_KEY": "SHOULD-NEVER-APPEAR"}})


def test_disabled_node_never_contacted():
    with patched(RequestLog()) as log:
        card = connector.poll_node({**NODE, "enabled": False})
        assert log.requests == [], "disabled node was contacted!"
        assert card["source"] == "configured-disabled"
        assert card["alive"] is None


def test_happy_path_and_redaction():
    with patched(RequestLog(responses=[GOOD_STATUS, GOOD_STATS])) as log:
        card = connector.poll_node(dict(NODE))
        assert card["alive"] is True and card["version"] == "0.18.0"
        assert card["gateway_state"] == "running"
        assert card["cpu_percent"] == 12.5 and card["memory_percent"] == 41.0
        assert card["disk_percent"] == 63.0 and card["uptime_seconds"] == 86400.0
        assert card["source"] == "live-read-only"
        # Redaction: unexpected fields must not appear anywhere in the card.
        assert "SHOULD-NEVER-APPEAR" not in json.dumps(card)
        assert "secret_field" not in json.dumps(card) and "env_dump" not in json.dumps(card)
        assert len(log.requests) == 2


def test_get_only_under_all_circumstances():
    with patched(RequestLog(responses=[GOOD_STATUS, GOOD_STATS])) as log:
        connector.poll_node(dict(NODE))
        for req in log.requests:
            assert req.get_method() == "GET", f"non-GET issued: {req.get_method()}"
            assert req.data is None, "request carried a body!"


def test_only_allowed_paths_fetched():
    with patched(RequestLog(responses=[GOOD_STATUS, GOOD_STATS])) as log:
        connector.poll_node(dict(NODE))
        paths = [req.full_url.split(NODE["url"], 1)[1] for req in log.requests]
        assert set(paths) <= set(connector.ALLOWED_PATHS), paths
    # And the fetch primitive refuses anything else outright.
    assert connector._get_json("http://x", "/api/hermes/update", None) is None


def test_missing_token_degrades_no_header():
    import os
    os.environ.pop("MC_TEST_TOKEN", None)
    with patched(RequestLog(responses=[GOOD_STATUS, GOOD_STATS])) as log:
        card = connector.poll_node(dict(NODE))
        assert card["alive"] is True  # public /api/status still works
        assert all(not r.headers.get("X-hermes-session-token") for r in log.requests)


def test_expired_token_401_degrades_without_retry():
    err = urllib.error.HTTPError("http://x", 401, "Unauthorized", {}, io.BytesIO(b""))
    with patched(RequestLog(exc=err)) as log:
        card = connector.poll_node(dict(NODE))
        assert card["alive"] is False and card["source"] == "live-read-only"
        assert len(log.requests) == 1, "HTTP auth errors must not be retried"


def test_timeout_degrades_with_bounded_retry():
    with patched(RequestLog(exc=TimeoutError("timed out"))) as log:
        card = connector.poll_node(dict(NODE))
        assert card["alive"] is False
        # status path only (stats never attempted when status fails):
        assert len(log.requests) == connector.MAX_ATTEMPTS, "retry cap violated"
        assert len(log.sleeps) == connector.MAX_ATTEMPTS - 1  # backoff between attempts


def test_offline_node_degrades():
    with patched(RequestLog(exc=urllib.error.URLError("conn refused"))) as log:
        card = connector.poll_node(dict(NODE))
        assert card["alive"] is False
        assert len(log.requests) <= connector.MAX_ATTEMPTS


def test_malformed_json_degrades():
    with patched(RequestLog(responses=["<html>not json</html>", "{}"])) as log:
        card = connector.poll_node(dict(NODE))
        assert card["alive"] is False or card["version"] is None


def test_circuit_breaker_opens_and_blocks_contact():
    with patched(RequestLog(exc=urllib.error.URLError("down"))) as log:
        now = 1000.0
        for i in range(connector.BREAKER_THRESHOLD):
            connector.poll_node(dict(NODE), now=now + i * (connector.CACHE_TTL_S + 1))
        count_at_open = len(log.requests)
        # Next poll inside cooldown: zero new requests.
        card = connector.poll_node(dict(NODE),
                                   now=now + connector.BREAKER_THRESHOLD * (connector.CACHE_TTL_S + 1))
        assert card["breaker_open"] is True
        assert len(log.requests) == count_at_open, "breaker-open node was contacted"


def test_cache_prevents_poll_storms():
    with patched(RequestLog(responses=[GOOD_STATUS, GOOD_STATS])) as log:
        connector.poll_node(dict(NODE), now=100.0)
        connector.poll_node(dict(NODE), now=101.0)  # within TTL → cached
        assert len(log.requests) == 2, "cached poll re-contacted the node"


def test_no_write_primitives_in_connector_source():
    """AST-level: no call in the connector passes a method/data argument, and
    no string literal names a write verb — prose in comments/docstrings is
    exempt because it isn't executable."""
    import ast
    tree = ast.parse((ROOT / "dashboard" / "connector.py").read_text())
    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            for kw in node.keywords:
                assert kw.arg not in {"method", "data"}, \
                    f"call passes {kw.arg}= at line {node.lineno}"
        if isinstance(node, ast.Constant) and isinstance(node.value, str):
            if not node.value.startswith(("\n", " ", "Read-only")):  # skip docstrings
                assert node.value.upper() not in {"POST", "PUT", "DELETE", "PATCH"}, \
                    f"write verb literal at line {node.lineno}"


if __name__ == "__main__":
    failures = 0
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            try:
                fn()
                print(f"PASS  {name}")
            except AssertionError as exc:
                failures += 1
                print(f"FAIL  {name}: {exc}")
            except Exception as exc:  # noqa: BLE001
                failures += 1
                print(f"ERROR {name}: {type(exc).__name__}: {exc}")
    print(f"\n{'ALL TESTS PASSED' if failures == 0 else f'{failures} FAILURES'}")
    sys.exit(1 if failures else 0)
