"""Read-only node connector for Mission Control.

SAFETY CONTRACT:
  * GET-only by construction — there is no code path that sets a request
    method, body, or data. ``urllib`` with ``data=None`` and no ``method=``
    always issues GET.
  * Only two whitelisted paths may be fetched: /api/status, /api/system/stats.
  * Strict per-request timeout, bounded retries with exponential backoff,
    and a per-node circuit breaker (opens after N consecutive failures,
    cools down before any re-contact).
  * Every response is schema-whitelisted: only known, non-sensitive fields
    are extracted. Unexpected fields — whatever they contain — are dropped
    (redaction by construction).
  * A node whose ``enabled`` flag is false is never contacted; callers must
    gate on it, and ``poll_node`` re-checks defensively.
  * Missing/expired token, timeout, DNS failure, non-2xx, and malformed JSON
    all degrade to ``None`` fields on the card — never an exception, never
    a retry storm, never a write.
"""

from __future__ import annotations

import json
import os
import time
import urllib.error
import urllib.request
from typing import Any, Optional

ALLOWED_PATHS = ("/api/status", "/api/system/stats")

DEFAULT_TIMEOUT_S = 4.0
MAX_ATTEMPTS = 2               # 1 try + 1 retry, per path, per poll
BACKOFF_BASE_S = 0.5           # 0.5s, then 1.0s, ... (capped by MAX_ATTEMPTS)
BREAKER_THRESHOLD = 3          # consecutive failed polls to open the breaker
BREAKER_COOLDOWN_S = 300.0     # no re-contact for 5 minutes once open
CACHE_TTL_S = 15.0             # don't re-poll a node more often than this

# Schema whitelists — extraction IS redaction: any field not listed here
# (tokens, paths, platform internals, anything unexpected) never leaves
# the connector.
STATUS_FIELDS = {
    "version": str,
    "gateway_running": bool,
    "gateway_state": (str, type(None)),
}
STATS_FIELDS = {
    "hostname": str,
    "os": str,
    "platform": str,
    "arch": str,
    "hermes_version": str,
    "cpu_percent": (int, float),
    "load_avg": list,
    "uptime_seconds": (int, float),
    "boot_time": (int, float),
}
STATS_NESTED = {  # nested dicts: keep only numeric summary keys
    "memory": {"total", "used", "available", "percent"},
    "disk": {"total", "used", "free", "percent"},
}


class _Breaker:
    """Per-node circuit breaker + poll cache."""

    def __init__(self) -> None:
        self.failures = 0
        self.open_until = 0.0
        self.cached: Optional[dict[str, Any]] = None
        self.cached_at = 0.0

    def is_open(self, now: float) -> bool:
        return now < self.open_until

    def record(self, ok: bool, now: float) -> None:
        if ok:
            self.failures = 0
            self.open_until = 0.0
        else:
            self.failures += 1
            if self.failures >= BREAKER_THRESHOLD:
                self.open_until = now + BREAKER_COOLDOWN_S


_breakers: dict[str, _Breaker] = {}


def _breaker(node_id: str) -> _Breaker:
    return _breakers.setdefault(node_id, _Breaker())


def reset_for_tests() -> None:
    _breakers.clear()


def _extract(payload: Any, fields: dict, nested: Optional[dict] = None) -> dict[str, Any]:
    """Whitelist-extract known fields; everything else is dropped (redacted)."""
    if not isinstance(payload, dict):
        return {}
    out: dict[str, Any] = {}
    for key, types in fields.items():
        value = payload.get(key)
        if value is not None and isinstance(value, types):
            out[key] = value
    for key, subkeys in (nested or {}).items():
        sub = payload.get(key)
        if isinstance(sub, dict):
            out[key] = {k: v for k, v in sub.items()
                        if k in subkeys and isinstance(v, (int, float))}
    return out


def _get_json(base_url: str, path: str, token: Optional[str],
              timeout: float = DEFAULT_TIMEOUT_S) -> Optional[Any]:
    """One GET with bounded retry/backoff. Returns parsed JSON or None.

    GET-only: ``urllib.request.Request`` with ``data=None`` and no ``method``
    argument can only ever issue a GET request.
    """
    if path not in ALLOWED_PATHS:  # defense in depth — never fetch anything else
        return None
    url = base_url.rstrip("/") + path
    headers = {"Accept": "application/json"}
    if token:
        headers["X-Hermes-Session-Token"] = token
    for attempt in range(MAX_ATTEMPTS):
        try:
            req = urllib.request.Request(url, headers=headers)  # GET by construction
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                if resp.status != 200:
                    return None  # 401/403/5xx → degrade, don't retry auth failures
                return json.loads(resp.read().decode("utf-8", "replace"))
        except urllib.error.HTTPError:
            return None  # auth/HTTP errors are deterministic — no retry
        except (urllib.error.URLError, TimeoutError, OSError, json.JSONDecodeError,
                ValueError):
            if attempt + 1 < MAX_ATTEMPTS:
                time.sleep(BACKOFF_BASE_S * (2 ** attempt))
    return None


def poll_node(node: dict[str, Any], now: Optional[float] = None) -> dict[str, Any]:
    """Poll one node read-only and return live card fields.

    Degrades field-by-field: status and stats are independent; a node with a
    public /api/status but a token-gated /api/system/stats still shows
    liveness with null metrics.
    """
    now = time.time() if now is None else now
    node_id = str(node.get("id", "?"))
    card: dict[str, Any] = {
        "alive": None, "gateway_state": None, "version": None,
        "cpu_percent": None, "memory_percent": None, "disk_percent": None,
        "uptime_seconds": None, "heartbeat_at": None, "last_poll_at": None,
        "source": "live-read-only", "breaker_open": False,
    }

    if not node.get("enabled"):  # defensive re-check: disabled ⇒ zero contact
        card["source"] = "configured-disabled"
        return card

    br = _breaker(node_id)
    if br.cached and now - br.cached_at < CACHE_TTL_S:
        return dict(br.cached)
    if br.is_open(now):
        card["breaker_open"] = True
        card["alive"] = False
        return card

    token = os.environ.get(node["token_env"]) if node.get("token_env") else None
    base_url = str(node.get("url", ""))

    status_raw = _get_json(base_url, "/api/status", token)
    status = _extract(status_raw, STATUS_FIELDS)
    ok = status_raw is not None

    if ok:
        card["alive"] = True
        card["version"] = status.get("version")
        card["gateway_state"] = (status.get("gateway_state")
                                 or ("running" if status.get("gateway_running") else "stopped"))
        card["heartbeat_at"] = now
        stats = _extract(_get_json(base_url, "/api/system/stats", token),
                         STATS_FIELDS, STATS_NESTED)
        card["cpu_percent"] = stats.get("cpu_percent")
        card["memory_percent"] = (stats.get("memory") or {}).get("percent")
        card["disk_percent"] = (stats.get("disk") or {}).get("percent")
        card["uptime_seconds"] = stats.get("uptime_seconds")
        card["last_poll_at"] = now
    else:
        card["alive"] = False

    br.record(ok, now)
    br.cached = dict(card)
    br.cached_at = now
    return card
