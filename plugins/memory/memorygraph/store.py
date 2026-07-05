"""SQLite-backed governed knowledge graph store for the memorygraph provider.

Schema overview (schema_version 1):

  entities        — typed nodes (person, project, goal, skill, business, ...)
  entity_aliases  — alternate names resolving to a canonical entity
  relationships   — typed, time-aware, confidence-scored edges
  claims          — attribute/value knowledge about an entity with
                    confidence, tier (candidate/established/core), status
                    (active/superseded/retracted/contradicted) and temporal
                    validity (valid_from/valid_to)
  evidence        — provenance links for claims / relationships / entities
  governance_log  — append-only audit trail of every governed mutation
  meta            — schema version and sweep bookkeeping

All timestamps are UTC ISO-8601 strings. The store takes an optional
``now`` callable so tests can control the clock deterministically.

The store is deliberately stdlib-only (sqlite3) and profile-scoped: the
database lives under ``$HERMES_HOME`` by default so it never leaks across
Hermes profiles.
"""

from __future__ import annotations

import json
import re
import sqlite3
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

SCHEMA_VERSION = 1

ENTITY_TYPES = [
    "person",
    "project",
    "goal",
    "skill",
    "business",
    "organization",
    "place",
    "tool",
    "concept",
]

CLAIM_TIERS = ["candidate", "established", "core"]
CLAIM_STATUSES = ["active", "superseded", "retracted", "contradicted"]

_SCHEMA = """
CREATE TABLE IF NOT EXISTS entities (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    name        TEXT NOT NULL,
    name_key    TEXT NOT NULL,
    type        TEXT NOT NULL DEFAULT 'concept',
    summary     TEXT NOT NULL DEFAULT '',
    attrs       TEXT NOT NULL DEFAULT '{}',
    created_at  TEXT NOT NULL,
    updated_at  TEXT NOT NULL,
    UNIQUE (name_key, type)
);
CREATE INDEX IF NOT EXISTS idx_entities_name_key ON entities (name_key);

CREATE TABLE IF NOT EXISTS entity_aliases (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    entity_id  INTEGER NOT NULL REFERENCES entities (id) ON DELETE CASCADE,
    alias      TEXT NOT NULL,
    alias_key  TEXT NOT NULL,
    created_at TEXT NOT NULL,
    UNIQUE (entity_id, alias_key)
);
CREATE INDEX IF NOT EXISTS idx_aliases_key ON entity_aliases (alias_key);

CREATE TABLE IF NOT EXISTS relationships (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    src_id      INTEGER NOT NULL REFERENCES entities (id) ON DELETE CASCADE,
    dst_id      INTEGER NOT NULL REFERENCES entities (id) ON DELETE CASCADE,
    rel_type    TEXT NOT NULL,
    confidence  REAL NOT NULL DEFAULT 0.6,
    valid_from  TEXT NOT NULL,
    valid_to    TEXT,
    created_at  TEXT NOT NULL,
    updated_at  TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_rel_src ON relationships (src_id);
CREATE INDEX IF NOT EXISTS idx_rel_dst ON relationships (dst_id);

CREATE TABLE IF NOT EXISTS claims (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    entity_id           INTEGER NOT NULL REFERENCES entities (id) ON DELETE CASCADE,
    attribute           TEXT NOT NULL,
    value               TEXT NOT NULL,
    value_key           TEXT NOT NULL,
    confidence          REAL NOT NULL DEFAULT 0.6,
    tier                TEXT NOT NULL DEFAULT 'candidate',
    status              TEXT NOT NULL DEFAULT 'active',
    exclusive           INTEGER NOT NULL DEFAULT 0,
    reinforcement_count INTEGER NOT NULL DEFAULT 0,
    created_at          TEXT NOT NULL,
    updated_at          TEXT NOT NULL,
    last_reinforced_at  TEXT NOT NULL,
    valid_from          TEXT NOT NULL,
    valid_to            TEXT,
    superseded_by       INTEGER
);
CREATE INDEX IF NOT EXISTS idx_claims_entity ON claims (entity_id);
CREATE INDEX IF NOT EXISTS idx_claims_attr ON claims (entity_id, attribute);
CREATE INDEX IF NOT EXISTS idx_claims_status ON claims (status);

CREATE TABLE IF NOT EXISTS evidence (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    subject_kind TEXT NOT NULL,
    subject_id   INTEGER NOT NULL,
    kind         TEXT NOT NULL DEFAULT 'session',
    ref          TEXT NOT NULL DEFAULT '',
    quote        TEXT NOT NULL DEFAULT '',
    session_id   TEXT NOT NULL DEFAULT '',
    created_at   TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_evidence_subject ON evidence (subject_kind, subject_id);

CREATE TABLE IF NOT EXISTS governance_log (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    ts           TEXT NOT NULL,
    event        TEXT NOT NULL,
    subject_kind TEXT NOT NULL DEFAULT '',
    subject_id   INTEGER,
    details      TEXT NOT NULL DEFAULT ''
);

CREATE TABLE IF NOT EXISTS meta (
    key   TEXT PRIMARY KEY,
    value TEXT NOT NULL
);
"""

_KEY_RE = re.compile(r"[^a-z0-9]+")


def normalize_key(text: str) -> str:
    """Normalize a name/value into a stable comparison key."""
    return _KEY_RE.sub(" ", (text or "").lower()).strip()


def utcnow_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def parse_ts(ts: str) -> datetime:
    """Parse a stored ISO-8601 UTC timestamp back into a datetime."""
    return datetime.strptime(ts, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)


def _row_to_dict(row: sqlite3.Row) -> Dict[str, Any]:
    return {k: row[k] for k in row.keys()}


class GraphStore:
    """Thread-safe SQLite knowledge graph store."""

    def __init__(self, db_path: str, now: Optional[Callable[[], str]] = None):
        self.db_path = str(db_path)
        self._now = now or utcnow_iso
        self._lock = threading.RLock()
        Path(self.db_path).parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(self.db_path, check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._conn.execute("PRAGMA foreign_keys = ON")
        with self._lock, self._conn:
            self._conn.executescript(_SCHEMA)
            self._conn.execute(
                "INSERT OR IGNORE INTO meta (key, value) VALUES ('schema_version', ?)",
                (str(SCHEMA_VERSION),),
            )

    def close(self) -> None:
        with self._lock:
            self._conn.close()

    def now(self) -> str:
        return self._now()

    # -- meta / audit ------------------------------------------------------

    def get_meta(self, key: str, default: str = "") -> str:
        with self._lock:
            row = self._conn.execute("SELECT value FROM meta WHERE key = ?", (key,)).fetchone()
        return row["value"] if row else default

    def set_meta(self, key: str, value: str) -> None:
        with self._lock, self._conn:
            self._conn.execute(
                "INSERT INTO meta (key, value) VALUES (?, ?) "
                "ON CONFLICT (key) DO UPDATE SET value = excluded.value",
                (key, value),
            )

    def log_event(
        self,
        event: str,
        subject_kind: str = "",
        subject_id: Optional[int] = None,
        details: Optional[Dict[str, Any]] = None,
    ) -> None:
        with self._lock, self._conn:
            self._conn.execute(
                "INSERT INTO governance_log (ts, event, subject_kind, subject_id, details) "
                "VALUES (?, ?, ?, ?, ?)",
                (self.now(), event, subject_kind, subject_id,
                 json.dumps(details or {}, ensure_ascii=False)),
            )

    def recent_events(self, limit: int = 20) -> List[Dict[str, Any]]:
        with self._lock:
            rows = self._conn.execute(
                "SELECT * FROM governance_log ORDER BY id DESC LIMIT ?", (limit,)
            ).fetchall()
        return [_row_to_dict(r) for r in rows]

    # -- entities ----------------------------------------------------------

    def resolve_entity(self, name: str, entity_type: str = "") -> Optional[Dict[str, Any]]:
        """Resolve a name (or alias) to an entity dict, or None."""
        key = normalize_key(name)
        if not key:
            return None
        with self._lock:
            if entity_type:
                row = self._conn.execute(
                    "SELECT * FROM entities WHERE name_key = ? AND type = ?",
                    (key, entity_type),
                ).fetchone()
            else:
                row = self._conn.execute(
                    "SELECT * FROM entities WHERE name_key = ? ORDER BY id LIMIT 1", (key,)
                ).fetchone()
            if row:
                return _row_to_dict(row)
            alias = self._conn.execute(
                "SELECT e.* FROM entity_aliases a JOIN entities e ON e.id = a.entity_id "
                "WHERE a.alias_key = ? ORDER BY a.id LIMIT 1",
                (key,),
            ).fetchone()
        return _row_to_dict(alias) if alias else None

    def upsert_entity(
        self,
        name: str,
        entity_type: str = "concept",
        summary: str = "",
        attrs: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Create or update an entity; resolves aliases first."""
        if entity_type not in ENTITY_TYPES:
            entity_type = "concept"
        key = normalize_key(name)
        if not key:
            raise ValueError("entity name must be non-empty")
        ts = self.now()
        existing = self.resolve_entity(name, entity_type) or self.resolve_entity(name)
        with self._lock, self._conn:
            if existing:
                new_summary = summary or existing["summary"]
                merged = json.loads(existing["attrs"] or "{}")
                merged.update(attrs or {})
                self._conn.execute(
                    "UPDATE entities SET summary = ?, attrs = ?, updated_at = ? WHERE id = ?",
                    (new_summary, json.dumps(merged, ensure_ascii=False), ts, existing["id"]),
                )
                return self.get_entity(existing["id"])  # type: ignore[return-value]
            cur = self._conn.execute(
                "INSERT INTO entities (name, name_key, type, summary, attrs, created_at, updated_at) "
                "VALUES (?, ?, ?, ?, ?, ?, ?)",
                (name.strip(), key, entity_type, summary,
                 json.dumps(attrs or {}, ensure_ascii=False), ts, ts),
            )
            entity_id = cur.lastrowid
        self.log_event("entity_created", "entity", entity_id, {"name": name, "type": entity_type})
        return self.get_entity(entity_id)  # type: ignore[return-value]

    def get_entity(self, entity_id: int) -> Optional[Dict[str, Any]]:
        with self._lock:
            row = self._conn.execute(
                "SELECT * FROM entities WHERE id = ?", (entity_id,)
            ).fetchone()
        return _row_to_dict(row) if row else None

    def add_alias(self, entity_id: int, alias: str) -> bool:
        key = normalize_key(alias)
        if not key:
            return False
        with self._lock, self._conn:
            try:
                self._conn.execute(
                    "INSERT INTO entity_aliases (entity_id, alias, alias_key, created_at) "
                    "VALUES (?, ?, ?, ?)",
                    (entity_id, alias.strip(), key, self.now()),
                )
            except sqlite3.IntegrityError:
                return False
        self.log_event("alias_added", "entity", entity_id, {"alias": alias})
        return True

    def list_entities(self, entity_type: str = "", limit: int = 50) -> List[Dict[str, Any]]:
        with self._lock:
            if entity_type:
                rows = self._conn.execute(
                    "SELECT * FROM entities WHERE type = ? ORDER BY updated_at DESC LIMIT ?",
                    (entity_type, limit),
                ).fetchall()
            else:
                rows = self._conn.execute(
                    "SELECT * FROM entities ORDER BY updated_at DESC LIMIT ?", (limit,)
                ).fetchall()
        return [_row_to_dict(r) for r in rows]

    # -- relationships -----------------------------------------------------

    def add_relationship(
        self,
        src_id: int,
        dst_id: int,
        rel_type: str,
        confidence: float = 0.6,
        valid_from: str = "",
    ) -> Dict[str, Any]:
        """Add a typed edge. Re-adding an identical open edge reinforces it."""
        ts = self.now()
        rel_key = normalize_key(rel_type)
        with self._lock, self._conn:
            row = self._conn.execute(
                "SELECT * FROM relationships WHERE src_id = ? AND dst_id = ? "
                "AND rel_type = ? AND valid_to IS NULL",
                (src_id, dst_id, rel_key),
            ).fetchone()
            if row:
                new_conf = min(1.0, row["confidence"] + 0.1)
                self._conn.execute(
                    "UPDATE relationships SET confidence = ?, updated_at = ? WHERE id = ?",
                    (new_conf, ts, row["id"]),
                )
                rel_id = row["id"]
            else:
                cur = self._conn.execute(
                    "INSERT INTO relationships "
                    "(src_id, dst_id, rel_type, confidence, valid_from, valid_to, created_at, updated_at) "
                    "VALUES (?, ?, ?, ?, ?, NULL, ?, ?)",
                    (src_id, dst_id, rel_key, max(0.0, min(1.0, confidence)),
                     valid_from or ts, ts, ts),
                )
                rel_id = cur.lastrowid
                self.log_event("relationship_created", "relationship", rel_id,
                               {"src": src_id, "dst": dst_id, "type": rel_key})
            out = self._conn.execute(
                "SELECT * FROM relationships WHERE id = ?", (rel_id,)
            ).fetchone()
        return _row_to_dict(out)

    def end_relationship(self, rel_id: int, valid_to: str = "") -> bool:
        """Close a relationship's validity window (time-aware retirement)."""
        with self._lock, self._conn:
            cur = self._conn.execute(
                "UPDATE relationships SET valid_to = ?, updated_at = ? "
                "WHERE id = ? AND valid_to IS NULL",
                (valid_to or self.now(), self.now(), rel_id),
            )
        if cur.rowcount:
            self.log_event("relationship_ended", "relationship", rel_id, {})
        return bool(cur.rowcount)

    def relationships_for(
        self, entity_id: int, include_ended: bool = False
    ) -> List[Dict[str, Any]]:
        q = (
            "SELECT r.*, s.name AS src_name, d.name AS dst_name FROM relationships r "
            "JOIN entities s ON s.id = r.src_id JOIN entities d ON d.id = r.dst_id "
            "WHERE (r.src_id = ? OR r.dst_id = ?)"
        )
        if not include_ended:
            q += " AND r.valid_to IS NULL"
        q += " ORDER BY r.updated_at DESC"
        with self._lock:
            rows = self._conn.execute(q, (entity_id, entity_id)).fetchall()
        return [_row_to_dict(r) for r in rows]

    def neighbors(self, entity_id: int) -> List[Dict[str, Any]]:
        """Entities directly connected to entity_id via open edges."""
        with self._lock:
            rows = self._conn.execute(
                "SELECT DISTINCT e.* FROM relationships r "
                "JOIN entities e ON e.id = CASE WHEN r.src_id = ? THEN r.dst_id ELSE r.src_id END "
                "WHERE (r.src_id = ? OR r.dst_id = ?) AND r.valid_to IS NULL",
                (entity_id, entity_id, entity_id),
            ).fetchall()
        return [_row_to_dict(r) for r in rows]

    # -- claims --------------------------------------------------------------

    def insert_claim(
        self,
        entity_id: int,
        attribute: str,
        value: str,
        confidence: float = 0.6,
        exclusive: bool = False,
        valid_from: str = "",
    ) -> Dict[str, Any]:
        """Insert a raw claim row (governance handled by GovernanceEngine)."""
        ts = self.now()
        with self._lock, self._conn:
            cur = self._conn.execute(
                "INSERT INTO claims (entity_id, attribute, value, value_key, confidence, tier, "
                "status, exclusive, reinforcement_count, created_at, updated_at, "
                "last_reinforced_at, valid_from, valid_to, superseded_by) "
                "VALUES (?, ?, ?, ?, ?, 'candidate', 'active', ?, 0, ?, ?, ?, ?, NULL, NULL)",
                (entity_id, normalize_key(attribute) or "note", value.strip(),
                 normalize_key(value), max(0.0, min(1.0, confidence)),
                 1 if exclusive else 0, ts, ts, ts, valid_from or ts),
            )
            claim_id = cur.lastrowid
        self.log_event("claim_created", "claim", claim_id,
                       {"entity_id": entity_id, "attribute": attribute})
        return self.get_claim(claim_id)  # type: ignore[return-value]

    def get_claim(self, claim_id: int) -> Optional[Dict[str, Any]]:
        with self._lock:
            row = self._conn.execute("SELECT * FROM claims WHERE id = ?", (claim_id,)).fetchone()
        return _row_to_dict(row) if row else None

    def update_claim(self, claim_id: int, **fields: Any) -> None:
        allowed = {
            "value", "value_key", "confidence", "tier", "status", "exclusive",
            "reinforcement_count", "last_reinforced_at", "valid_from", "valid_to",
            "superseded_by",
        }
        cols = {k: v for k, v in fields.items() if k in allowed}
        if not cols:
            return
        cols["updated_at"] = self.now()
        sets = ", ".join(f"{k} = ?" for k in cols)
        with self._lock, self._conn:
            self._conn.execute(
                f"UPDATE claims SET {sets} WHERE id = ?",  # noqa: S608 — cols whitelisted
                (*cols.values(), claim_id),
            )

    def claims_for(
        self,
        entity_id: int,
        attribute: str = "",
        status: str = "active",
        include_history: bool = False,
    ) -> List[Dict[str, Any]]:
        q = "SELECT * FROM claims WHERE entity_id = ?"
        params: List[Any] = [entity_id]
        if attribute:
            q += " AND attribute = ?"
            params.append(normalize_key(attribute))
        if not include_history:
            q += " AND status = ?"
            params.append(status)
        q += " ORDER BY valid_from ASC, id ASC"
        with self._lock:
            rows = self._conn.execute(q, params).fetchall()
        return [_row_to_dict(r) for r in rows]

    def claims_by_status(self, status: str, limit: int = 100) -> List[Dict[str, Any]]:
        with self._lock:
            rows = self._conn.execute(
                "SELECT * FROM claims WHERE status = ? ORDER BY updated_at DESC LIMIT ?",
                (status, limit),
            ).fetchall()
        return [_row_to_dict(r) for r in rows]

    def all_active_claims(self) -> List[Dict[str, Any]]:
        with self._lock:
            rows = self._conn.execute(
                "SELECT * FROM claims WHERE status = 'active' ORDER BY id"
            ).fetchall()
        return [_row_to_dict(r) for r in rows]

    # -- evidence ------------------------------------------------------------

    def add_evidence(
        self,
        subject_kind: str,
        subject_id: int,
        kind: str = "session",
        ref: str = "",
        quote: str = "",
        session_id: str = "",
    ) -> int:
        with self._lock, self._conn:
            cur = self._conn.execute(
                "INSERT INTO evidence (subject_kind, subject_id, kind, ref, quote, session_id, created_at) "
                "VALUES (?, ?, ?, ?, ?, ?, ?)",
                (subject_kind, subject_id, kind, ref, quote[:500], session_id, self.now()),
            )
        return cur.lastrowid

    def evidence_for(self, subject_kind: str, subject_id: int) -> List[Dict[str, Any]]:
        with self._lock:
            rows = self._conn.execute(
                "SELECT * FROM evidence WHERE subject_kind = ? AND subject_id = ? ORDER BY id",
                (subject_kind, subject_id),
            ).fetchall()
        return [_row_to_dict(r) for r in rows]

    def evidence_count(self, subject_kind: str, subject_id: int) -> int:
        with self._lock:
            row = self._conn.execute(
                "SELECT COUNT(*) AS n FROM evidence WHERE subject_kind = ? AND subject_id = ?",
                (subject_kind, subject_id),
            ).fetchone()
        return int(row["n"])

    # -- search --------------------------------------------------------------

    def search(self, query: str, limit: int = 10) -> List[Dict[str, Any]]:
        """Keyword search across entities and active claims.

        Word-boundary match on significant tokens (length >= 3, falling back
        to all tokens for short queries). Any-token match, ranked by token
        coverage; claim hits are additionally weighted by confidence so
        trusted knowledge surfaces first. Works both for explicit keyword
        queries and for whole-message prefetch queries.
        """
        all_tokens = [t for t in normalize_key(query).split() if t]
        tokens = [t for t in all_tokens if len(t) >= 3] or all_tokens
        if not tokens:
            return []
        results: List[Dict[str, Any]] = []
        with self._lock:
            ent_rows = self._conn.execute("SELECT * FROM entities").fetchall()
            claim_rows = self._conn.execute(
                "SELECT c.*, e.name AS entity_name FROM claims c "
                "JOIN entities e ON e.id = c.entity_id WHERE c.status = 'active'"
            ).fetchall()
        for row in ent_rows:
            words = set(normalize_key(f"{row['name']} {row['type']} {row['summary']}").split())
            hits = sum(1 for t in tokens if t in words)
            if hits:
                d = _row_to_dict(row)
                d["_kind"] = "entity"
                d["_score"] = hits / len(tokens)
                results.append(d)
        for row in claim_rows:
            words = set(
                normalize_key(f"{row['entity_name']} {row['attribute']} {row['value']}").split()
            )
            hits = sum(1 for t in tokens if t in words)
            if hits:
                d = _row_to_dict(row)
                d["_kind"] = "claim"
                d["_score"] = (hits / len(tokens)) * (0.5 + 0.5 * float(row["confidence"]))
                results.append(d)
        results.sort(key=lambda d: d["_score"], reverse=True)
        return results[:limit]

    # -- stats -----------------------------------------------------------------

    def stats(self) -> Dict[str, Any]:
        with self._lock:
            n_ent = self._conn.execute("SELECT COUNT(*) AS n FROM entities").fetchone()["n"]
            n_rel = self._conn.execute(
                "SELECT COUNT(*) AS n FROM relationships WHERE valid_to IS NULL"
            ).fetchone()["n"]
            by_status = {
                r["status"]: r["n"]
                for r in self._conn.execute(
                    "SELECT status, COUNT(*) AS n FROM claims GROUP BY status"
                ).fetchall()
            }
            by_tier = {
                r["tier"]: r["n"]
                for r in self._conn.execute(
                    "SELECT tier, COUNT(*) AS n FROM claims WHERE status = 'active' GROUP BY tier"
                ).fetchall()
            }
            n_ev = self._conn.execute("SELECT COUNT(*) AS n FROM evidence").fetchone()["n"]
        return {
            "entities": n_ent,
            "open_relationships": n_rel,
            "claims_by_status": by_status,
            "active_claims_by_tier": by_tier,
            "evidence": n_ev,
            "schema_version": int(self.get_meta("schema_version", "1")),
        }
