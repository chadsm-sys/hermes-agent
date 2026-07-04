"""Schema + safety-behavior tests for the Mission Control v0 broker plugin.

Run with the hermes-agent venv (has fastapi/httpx):
  ~/.hermes/hermes-agent/venv/bin/python -m pytest tests/ -q
or plain stdlib runner:
  ~/.hermes/hermes-agent/venv/bin/python tests/test_broker.py
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "dashboard"))

import plugin_api  # noqa: E402
from fastapi import FastAPI  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

PREFIX = "/api/plugins/mission-control"


def make_client() -> TestClient:
    app = FastAPI()
    # Mirror how web_server.py mounts plugin routers.
    app.include_router(plugin_api.router, prefix=PREFIX)
    plugin_api._reset_inbox_for_tests()
    return TestClient(app)


def test_health_reports_mock_mode():
    client = make_client()
    body = client.get(f"{PREFIX}/health").json()
    assert body["ok"] is True
    assert body["mode"] == "mock", "v0 must never report live mode"


def test_fleet_summary_schema_and_all_nodes_disabled():
    client = make_client()
    resp = client.get(f"{PREFIX}/fleet/summary")
    assert resp.status_code == 200
    body = resp.json()
    assert body["mode"] == "mock"
    assert isinstance(body["nodes"], list) and len(body["nodes"]) >= 3
    for node in body["nodes"]:
        for key in ("id", "label", "role", "enabled", "read_only"):
            assert key in node, f"fleet node missing {key}"
        # SAFETY INVARIANT: v0 ships with every node disabled + read-only.
        assert node["enabled"] is False
        assert node["read_only"] is True
    ids = {n["id"] for n in body["nodes"]}
    assert {"mbp", "mac-mini", "dgx-spark"} <= ids


def test_jobs_summary_counts_match_jobs():
    client = make_client()
    body = client.get(f"{PREFIX}/jobs/summary").json()
    assert isinstance(body["jobs"], list)
    # Behavior contract: counts must be derived from the jobs list.
    recomputed: dict[str, int] = {}
    for job in body["jobs"]:
        recomputed[job["state"]] = recomputed.get(job["state"], 0) + 1
    assert body["counts"] == recomputed


def test_approvals_summary_count_matches():
    client = make_client()
    body = client.get(f"{PREFIX}/approvals/summary").json()
    assert body["count"] == len(body["approvals"])
    for item in body["approvals"]:
        assert item["kind"] in {"approval", "sudo", "secret"}


def test_opportunities_inbox_sorted_by_confidence():
    client = make_client()
    body = client.get(f"{PREFIX}/opportunities/inbox").json()
    confs = [i["confidence"] for i in body["items"]]
    assert confs == sorted(confs, reverse=True)


def test_opportunities_tier_filter():
    client = make_client()
    body = client.get(f"{PREFIX}/opportunities/inbox", params={"tier": "quick"}).json()
    assert all(i["tier"] == "quick" for i in body["items"])


def test_opportunity_ingestion_happy_path():
    client = make_client()
    resp = client.post(
        f"{PREFIX}/opportunities",
        json={"title": "Test opp", "confidence": 0.9, "tier": "quick", "source": "income-scout"},
    )
    assert resp.status_code == 201
    item = resp.json()["item"]
    assert item["status"] == "new" and item["source"] == "income-scout"
    inbox = client.get(f"{PREFIX}/opportunities/inbox").json()
    assert any(i["id"] == item["id"] for i in inbox["items"])


def test_expert_witness_source_rejected():
    """Lane separation: expert-witness must never enter the opportunity inbox."""
    client = make_client()
    for variant in ("expert-witness", "expert_witness", "Expert-Witness"):
        resp = client.post(
            f"{PREFIX}/opportunities",
            json={"title": "EW leak attempt", "confidence": 0.99, "tier": "quick", "source": variant},
        )
        assert resp.status_code == 422, f"{variant!r} must be rejected"
        assert "Expert Witness" in resp.text or "expert-witness" in resp.text


def test_unknown_source_rejected():
    client = make_client()
    resp = client.post(
        f"{PREFIX}/opportunities",
        json={"title": "x", "confidence": 0.5, "tier": "long", "source": "mystery-scout"},
    )
    assert resp.status_code == 422


def test_confidence_bounds_enforced():
    client = make_client()
    for bad in (-0.1, 1.5):
        resp = client.post(
            f"{PREFIX}/opportunities",
            json={"title": "x", "confidence": bad, "tier": "quick", "source": "manual"},
        )
        assert resp.status_code == 422


def test_missing_fixture_degrades_not_500(monkeypatch=None):
    """Safe-failure: a missing fixture returns degraded empty data, never a 500.
    fleet/summary is registry-first since M2, so its degrade path additionally
    requires nodes.yaml to be unreadable."""
    client = make_client()
    original_fixtures = plugin_api._FIXTURES
    original_load_nodes = plugin_api._load_nodes
    plugin_api._FIXTURES = Path("/nonexistent-mission-control-fixtures")
    plugin_api._load_nodes = lambda: None
    try:
        for path in ("fleet/summary", "jobs/summary", "approvals/summary", "providers/summary"):
            resp = client.get(f"{PREFIX}/{path}")
            assert resp.status_code == 200, f"{path} should degrade, not error"
            assert resp.json().get("degraded") is True
    finally:
        plugin_api._FIXTURES = original_fixtures
        plugin_api._load_nodes = original_load_nodes


def test_fleet_disabled_nodes_render_without_contact():
    """Registry-driven fleet: all-disabled registry yields cards with
    source=configured-disabled and never flips the envelope to live mode."""
    client = make_client()
    body = client.get(f"{PREFIX}/fleet/summary").json()
    assert body["mode"] == "mock", "all-disabled fleet must not report live mode"
    for node in body["nodes"]:
        assert node["enabled"] is False and node["read_only"] is True
        assert node["source"] == "configured-disabled"


def test_no_mutation_routes_against_remote_nodes():
    """Contract: the only POST in the router is local opportunity ingestion."""
    posts = [
        r.path for r in plugin_api.router.routes
        if hasattr(r, "methods") and "POST" in (r.methods or set())
    ]
    assert posts == ["/opportunities"], f"unexpected mutation routes: {posts}"
    # And nothing exposes DELETE/PUT/PATCH at all.
    for r in plugin_api.router.routes:
        methods = getattr(r, "methods", None) or set()
        assert not ({"DELETE", "PUT", "PATCH"} & methods)


if __name__ == "__main__":
    # Minimal stdlib runner (no pytest dependency).
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
