"""Durable local persistence for the Opportunity Scout engine.

JSON-backed, atomic, thread-safe — mirrors the proven ``teams_pipeline``
store pattern. No network, no external dependencies.
"""

from __future__ import annotations

import json
import os
import threading
import time
from pathlib import Path
from tempfile import NamedTemporaryFile

from hermes_constants import get_hermes_home

from .models import SCHEMA_VERSION, Opportunity, OpportunityScoutError

DEFAULT_STORE_FILENAME = "opportunity_scout_store.json"
STORE_PATH_ENV_VAR = "OPPORTUNITY_SCOUT_STORE_PATH"


class StoreError(OpportunityScoutError):
    pass


def resolve_store_path(path: str | Path | None = None) -> Path:
    if path is not None:
        explicit = str(path).strip()
        if explicit:
            return Path(explicit)

    env_path = os.getenv(STORE_PATH_ENV_VAR, "").strip()
    if env_path:
        return Path(env_path)

    return get_hermes_home() / DEFAULT_STORE_FILENAME


class OpportunityStore:
    """JSON-backed durable store for opportunities."""

    def __init__(self, path: str | Path | None = None):
        self._path = resolve_store_path(path)
        self._lock = threading.RLock()
        self._opportunities: dict[str, Opportunity] = {}
        self._load()

    @property
    def path(self) -> Path:
        return self._path

    # -- loading / saving -------------------------------------------------

    def _load(self) -> None:
        if not self._path.exists():
            return
        try:
            raw = json.loads(self._path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, UnicodeDecodeError, OSError):
            self._quarantine_corrupt_file()
            return
        if not isinstance(raw, dict):
            self._quarantine_corrupt_file()
            return
        version = raw.get("version")
        if version != SCHEMA_VERSION:
            raise StoreError(
                f"Unsupported opportunity store schema version {version!r} "
                f"(expected {SCHEMA_VERSION}) at {self._path}. Refusing to "
                "load to avoid silent data loss."
            )
        opportunities = raw.get("opportunities", {})
        loaded: dict[str, Opportunity] = {}
        for opportunity_id, data in opportunities.items():
            opportunity = Opportunity.from_dict(data)
            loaded[str(opportunity_id)] = opportunity
        self._opportunities = loaded

    def _quarantine_corrupt_file(self) -> None:
        backup = self._path.with_name(
            f"{self._path.name}.corrupt-{int(time.time())}"
        )
        try:
            os.replace(self._path, backup)
        except OSError:
            pass

    def _save(self) -> None:
        payload = {
            "version": SCHEMA_VERSION,
            "opportunities": {
                opportunity_id: opportunity.to_dict()
                for opportunity_id, opportunity in self._opportunities.items()
            },
        }
        self._path.parent.mkdir(parents=True, exist_ok=True)
        with NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            dir=str(self._path.parent),
            prefix=f".{self._path.name}.",
            suffix=".tmp",
            delete=False,
        ) as handle:
            json.dump(payload, handle, indent=2, sort_keys=True)
            handle.flush()
            os.fsync(handle.fileno())
            temp_name = handle.name
        os.replace(temp_name, self._path)

    # -- CRUD --------------------------------------------------------------

    def upsert(self, opportunity: Opportunity) -> None:
        with self._lock:
            self._opportunities[opportunity.opportunity_id] = opportunity
            self._save()

    def get(self, opportunity_id: str) -> Opportunity:
        with self._lock:
            try:
                return self._opportunities[opportunity_id]
            except KeyError as exc:
                raise StoreError(f"Unknown opportunity: {opportunity_id!r}") from exc

    def exists(self, opportunity_id: str) -> bool:
        with self._lock:
            return opportunity_id in self._opportunities

    def delete(self, opportunity_id: str) -> None:
        with self._lock:
            if opportunity_id not in self._opportunities:
                raise StoreError(f"Unknown opportunity: {opportunity_id!r}")
            del self._opportunities[opportunity_id]
            self._save()

    def all(self) -> list[Opportunity]:
        with self._lock:
            return list(self._opportunities.values())

    def __len__(self) -> int:
        with self._lock:
            return len(self._opportunities)
