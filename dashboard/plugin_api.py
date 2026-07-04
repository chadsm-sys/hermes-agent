"""Mission Control v0 broker — Hermes dashboard backend plugin.

Mounted by hermes_cli/web_server.py::_mount_plugin_api_routes() at
/api/plugins/mission-control/... once the plugin directory is installed in
~/.hermes/plugins/ AND the name is added to `plugins.enabled` in config.yaml.

SAFETY CONTRACT (v0):
  * mode is ALWAYS "mock" — no network calls, no remote polling, no tokens read.
  * every endpoint is read-only except POST /opportunities, which only writes
    to the plugin's own local inbox (in-memory in v0).
  * source="expert-witness" is REJECTED at ingestion: the Opportunity Scout
    lane and the Expert Witness lane must never mix (operator directive).
  * a node with enabled=false in nodes.yaml is never contacted, in any mode.

Live mode (v1) is intentionally NOT implemented here; it lands only after the
operator approves token provisioning and the M0 connectivity test passes.
"""

from __future__ import annotations

import json
import sys
import time
import uuid
from pathlib import Path
from typing import Any, Literal, Optional

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field, field_validator

router = APIRouter()

PLUGIN_VERSION = "0.2.0"
# Base mode for non-fleet endpoints (jobs/approvals/opportunities remain mock
# in M2). fleet/summary reports "live-read-only" when at least one enabled
# node was polled via the GET-only connector.
MODE = "mock"

_HERE = Path(__file__).resolve().parent
_FIXTURES = _HERE / "fixtures"

# Opportunity sources allowed into the inbox. "expert-witness" is deliberately
# absent AND explicitly blocked below with a clear error, so the rejection is
# self-documenting rather than a generic enum failure.
ALLOWED_OPPORTUNITY_SOURCES = {"income-scout", "infra-scout", "research-scout", "manual"}
BLOCKED_OPPORTUNITY_SOURCES = {"expert-witness", "expert_witness", "expertwitness"}

OpportunityTier = Literal["quick", "long"]
OpportunityStatus = Literal["new", "reviewed", "acted", "dismissed"]


def _now() -> float:
    return time.time()


def _load_fixture(name: str) -> Any:
    """Load a mock fixture; missing/corrupt fixtures degrade to empty data,
    never to a 500 — Mission Control must fail safe and visible, not crash."""
    path = _FIXTURES / f"{name}.json"
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return None
    except (json.JSONDecodeError, OSError):
        return None


def _envelope(payload: dict[str, Any]) -> dict[str, Any]:
    return {"generated_at": _now(), "mode": MODE, **payload}


# ── Health ───────────────────────────────────────────────────────────────────

@router.get("/health")
async def health() -> dict[str, Any]:
    return _envelope({"ok": True, "version": PLUGIN_VERSION})


# ── Fleet ────────────────────────────────────────────────────────────────────

def _load_nodes() -> Optional[list[dict[str, Any]]]:
    """Node registry from nodes.yaml (plugin root). None on any read failure."""
    try:
        import yaml
        raw = yaml.safe_load((_HERE.parent / "nodes.yaml").read_text(encoding="utf-8"))
        nodes = raw.get("nodes") if isinstance(raw, dict) else None
        return nodes if isinstance(nodes, list) else None
    except Exception:
        return None


def _connector():
    """Load the sibling connector module by path. plugin_api is imported via
    spec_from_file_location (no package, dashboard/ not on sys.path), so a
    plain ``import connector`` cannot resolve inside the dashboard server."""
    import importlib.util
    name = "hermes_mc_connector"
    mod = sys.modules.get(name)
    if mod is None:
        spec = importlib.util.spec_from_file_location(name, _HERE / "connector.py")
        mod = importlib.util.module_from_spec(spec)
        sys.modules[name] = mod
        spec.loader.exec_module(mod)
    return mod


@router.get("/fleet/summary")
async def fleet_summary() -> dict[str, Any]:
    """Fleet cards from nodes.yaml. Enabled nodes are polled read-only via the
    connector (GET-only, breaker-guarded); disabled nodes are NEVER contacted
    and render from config alone. Falls back to the mock fixture when the
    registry is unreadable."""
    nodes = _load_nodes()
    if nodes is None:
        fixture = _load_fixture("fleet")
        if fixture is None:
            return _envelope({"nodes": [], "degraded": True,
                              "reason": "nodes.yaml and fixture unreadable"})
        return _envelope({"nodes": fixture})

    connector = _connector()
    cards = []
    any_live = False
    for node in nodes:
        card = {k: node.get(k) for k in ("id", "label", "role", "url", "enabled", "read_only")}
        card.update(connector.poll_node(node))
        any_live = any_live or card["source"] == "live-read-only"
        cards.append(card)
    return {**_envelope({"nodes": cards}),
            "mode": "live-read-only" if any_live else MODE}


# ── Jobs ─────────────────────────────────────────────────────────────────────

@router.get("/jobs/summary")
async def jobs_summary() -> dict[str, Any]:
    jobs = _load_fixture("jobs")
    if jobs is None:
        return _envelope({"jobs": [], "counts": {}, "degraded": True,
                          "reason": "fixture missing/unreadable"})
    counts: dict[str, int] = {}
    for job in jobs:
        state = job.get("state", "unknown")
        counts[state] = counts.get(state, 0) + 1
    return _envelope({"jobs": jobs, "counts": counts})


# ── Approvals ────────────────────────────────────────────────────────────────

@router.get("/approvals/summary")
async def approvals_summary() -> dict[str, Any]:
    approvals = _load_fixture("approvals")
    if approvals is None:
        return _envelope({"approvals": [], "count": 0, "degraded": True,
                          "reason": "fixture missing/unreadable"})
    return _envelope({"approvals": approvals, "count": len(approvals)})


# ── Opportunities ────────────────────────────────────────────────────────────

class OpportunityIn(BaseModel):
    title: str = Field(min_length=1, max_length=500)
    confidence: float = Field(ge=0.0, le=1.0)
    tier: OpportunityTier
    source: str
    payload: Optional[dict[str, Any]] = None

    @field_validator("source")
    @classmethod
    def _lane_separation(cls, v: str) -> str:
        normalized = v.strip().lower()
        if normalized in BLOCKED_OPPORTUNITY_SOURCES:
            raise ValueError(
                "expert-witness items are not opportunities: the Expert Witness "
                "lane is intentionally separate from the Opportunity Scout inbox."
            )
        if normalized not in ALLOWED_OPPORTUNITY_SOURCES:
            raise ValueError(
                f"unknown source {v!r}; allowed: {sorted(ALLOWED_OPPORTUNITY_SOURCES)}"
            )
        return normalized


# v0 inbox: in-memory, seeded from fixture. v1 moves this to SQLite.
_inbox: list[dict[str, Any]] = []
_inbox_seeded = False


def _seed_inbox() -> None:
    global _inbox_seeded
    if _inbox_seeded:
        return
    seed = _load_fixture("opportunities")
    if isinstance(seed, list):
        _inbox.extend(seed)
    _inbox_seeded = True


def _reset_inbox_for_tests() -> None:
    """Test hook: clear and re-arm seeding."""
    global _inbox_seeded
    _inbox.clear()
    _inbox_seeded = False


@router.get("/opportunities/inbox")
async def opportunities_inbox(
    tier: Optional[OpportunityTier] = Query(default=None),
    status: Optional[OpportunityStatus] = Query(default=None),
) -> dict[str, Any]:
    _seed_inbox()
    items = list(_inbox)
    if tier is not None:
        items = [i for i in items if i.get("tier") == tier]
    if status is not None:
        items = [i for i in items if i.get("status") == status]
    items.sort(key=lambda i: (-float(i.get("confidence", 0)), i.get("created_at", 0)))
    return _envelope({"items": items, "count": len(items)})


@router.post("/opportunities", status_code=201)
async def ingest_opportunity(body: OpportunityIn) -> dict[str, Any]:
    _seed_inbox()
    item = {
        "id": str(uuid.uuid4()),
        "title": body.title,
        "confidence": body.confidence,
        "tier": body.tier,
        "source": body.source,
        "status": "new",
        "created_at": _now(),
        "payload": body.payload or {},
    }
    _inbox.append(item)
    return _envelope({"item": item})


# ── Providers (placeholder) ──────────────────────────────────────────────────

@router.get("/providers/summary")
async def providers_summary() -> dict[str, Any]:
    providers = _load_fixture("providers")
    if providers is None:
        return _envelope({"providers": [], "degraded": True,
                          "reason": "fixture missing/unreadable"})
    return _envelope({"providers": providers})
