"""memorygraph — governed knowledge graph memory provider for Hermes.

Transforms memory from searchable notes into a governed knowledge graph:
typed entities (people, projects, goals, skills, businesses, ...), typed
time-aware relationships, attribute claims with evidence links, confidence
tracking, contradiction + duplicate detection, knowledge aging, and
candidate → established → core promotion.

Local-only: stdlib sqlite3, no network, no credentials. The database is
profile-scoped at ``$HERMES_HOME/memory_graph.db`` by default.

Activate with ``memory.provider: memorygraph`` in config.yaml. The built-in
``memory`` tool (MEMORY.md / USER.md) is unchanged and keeps working; writes
to it are mirrored into the graph via the ``on_memory_write`` hook.

Optional config file ``$HERMES_HOME/memorygraph.json``:
  {
    "db_path": "...",             # default: $HERMES_HOME/memory_graph.db
    "half_life_days": 90,         # knowledge aging half-life
    "duplicate_similarity": 0.88, # near-duplicate threshold [0, 1]
    "prefetch_enabled": true,     # inject graph recall before each turn
    "sweep_on_session_end": true  # run aging+promotion at session end
  }

See DESIGN.md in this directory for the governance model and the
design-only roadmap (semantic dedupe, automatic turn extraction, federation).
"""

from __future__ import annotations

import json
import logging
import os
import threading
from typing import Any, Dict, List, Optional

from agent.memory_provider import MemoryProvider

from .governance import GovernanceEngine, GovernancePolicy
from .store import ENTITY_TYPES, GraphStore

logger = logging.getLogger(__name__)

_CONFIG_FILENAME = "memorygraph.json"
_DB_FILENAME = "memory_graph.db"

GRAPH_MEMORY_SCHEMA: Dict[str, Any] = {
    "name": "graph_memory",
    "description": (
        "Governed knowledge graph memory. Use alongside the built-in memory "
        "tool — memory for always-on notes, graph_memory for structured, "
        "evidence-linked knowledge about people, projects, goals, skills and "
        "businesses.\n\n"
        "ACTIONS:\n"
        "• remember — Store a claim about an entity (creates the entity if "
        "needed). Duplicates reinforce; conflicting exclusive values are "
        "superseded time-aware or flagged as contradictions.\n"
        "• link — Create a typed relationship between two entities.\n"
        "• unlink — Close a relationship's validity window (it happened, "
        "but is no longer current).\n"
        "• about — Everything known about an entity: claims by tier, open "
        "relationships, evidence counts.\n"
        "• query — Keyword search across entities and claims.\n"
        "• timeline — Chronological claim history for an entity, including "
        "superseded values (time-aware knowledge).\n"
        "• contradictions — List contradicted claim groups needing review.\n"
        "• resolve — Resolve a contradiction by choosing the winning claim.\n"
        "• duplicates — Audit for near-duplicate active claims.\n"
        "• feedback — Rate a claim after use (helpful/unhelpful) to tune "
        "confidence.\n"
        "• forget — Retract a claim (kept in history, never surfaced).\n"
        "• sweep — Run governance now: aging (confidence decay + demotion) "
        "then promotion (candidate → established → core).\n"
        "• stats — Graph size, tier distribution, governance counters.\n\n"
        "Before answering questions about known people or projects, use "
        "'about' or 'query' first."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "action": {
                "type": "string",
                "enum": [
                    "remember", "link", "unlink", "about", "query", "timeline",
                    "contradictions", "resolve", "duplicates", "feedback",
                    "forget", "sweep", "stats",
                ],
            },
            "entity": {"type": "string", "description": "Entity name (remember/about/timeline)."},
            "entity_type": {
                "type": "string",
                "enum": ENTITY_TYPES,
                "description": "Entity type hint (default: concept).",
            },
            "attribute": {
                "type": "string",
                "description": "Claim attribute, e.g. 'employer', 'status', 'deadline' (remember/timeline).",
            },
            "value": {"type": "string", "description": "Claim value (remember)."},
            "exclusive": {
                "type": "boolean",
                "description": "True if the attribute holds one current value (e.g. employer, status).",
            },
            "confidence": {"type": "number", "description": "Initial confidence 0-1 (default 0.6)."},
            "source": {"type": "string", "description": "Evidence reference: URL, file, quote origin."},
            "quote": {"type": "string", "description": "Supporting quote for the evidence link."},
            "src": {"type": "string", "description": "Source entity name (link)."},
            "dst": {"type": "string", "description": "Target entity name (link)."},
            "rel_type": {
                "type": "string",
                "description": "Relationship type, e.g. 'works_at', 'owns', 'part_of' (link).",
            },
            "relationship_id": {"type": "integer", "description": "Relationship id (unlink)."},
            "claim_id": {"type": "integer", "description": "Claim id (feedback/forget/resolve)."},
            "helpful": {"type": "boolean", "description": "Feedback direction (feedback)."},
            "query": {"type": "string", "description": "Search text (query)."},
            "limit": {"type": "integer", "description": "Max results (default 10)."},
        },
        "required": ["action"],
    },
}


def _load_json_config(hermes_home: str) -> Dict[str, Any]:
    path = os.path.join(hermes_home, _CONFIG_FILENAME)
    try:
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
        return data if isinstance(data, dict) else {}
    except (OSError, ValueError):
        return {}


class MemoryGraphProvider(MemoryProvider):
    """Governed knowledge graph memory provider (local SQLite)."""

    def __init__(self):
        self._store: Optional[GraphStore] = None
        self._engine: Optional[GovernanceEngine] = None
        self._session_id: str = ""
        self._hermes_home: str = ""
        self._agent_context: str = "primary"
        self._prefetch_enabled: bool = True
        self._sweep_on_session_end: bool = True
        self._prefetch_cache: Dict[str, str] = {}
        self._lock = threading.Lock()

    # -- identity / availability ------------------------------------------------

    @property
    def name(self) -> str:
        return "memorygraph"

    def is_available(self) -> bool:
        # Local, stdlib-only: always available. No network, no credentials.
        return True

    # -- lifecycle ----------------------------------------------------------------

    def initialize(self, session_id: str, **kwargs) -> None:
        self._session_id = session_id
        self._hermes_home = str(
            kwargs.get("hermes_home") or os.path.expanduser("~/.hermes")
        )
        self._agent_context = str(kwargs.get("agent_context") or "primary")
        config = _load_json_config(self._hermes_home)

        db_path = str(config.get("db_path") or os.path.join(self._hermes_home, _DB_FILENAME))
        policy = GovernancePolicy()
        try:
            policy.half_life_days = float(config.get("half_life_days", policy.half_life_days))
            policy.duplicate_similarity = float(
                config.get("duplicate_similarity", policy.duplicate_similarity)
            )
        except (TypeError, ValueError):
            logger.warning("memorygraph: invalid numeric config value; using defaults")
        self._prefetch_enabled = bool(config.get("prefetch_enabled", True))
        self._sweep_on_session_end = bool(config.get("sweep_on_session_end", True))

        self._store = GraphStore(db_path)
        self._engine = GovernanceEngine(self._store, policy)
        logger.info("memorygraph initialized (db=%s, session=%s)", db_path, session_id)

    def shutdown(self) -> None:
        with self._lock:
            if self._store is not None:
                self._store.close()
                self._store = None
                self._engine = None

    def on_session_switch(self, new_session_id: str, **kwargs) -> None:
        self._session_id = new_session_id
        self._prefetch_cache.clear()

    def on_session_end(self, messages: List[Dict[str, Any]]) -> None:
        if self._engine is None or not self._sweep_on_session_end:
            return
        if self._agent_context != "primary":
            return
        try:
            result = self._engine.sweep()
            logger.debug("memorygraph session-end sweep: %s", result)
        except Exception:
            logger.exception("memorygraph: session-end governance sweep failed")

    # -- prompt / recall ------------------------------------------------------------

    def system_prompt_block(self) -> str:
        if self._store is None:
            return ""
        try:
            stats = self._store.stats()
        except Exception:
            return ""
        active = sum(stats["active_claims_by_tier"].values())
        contradicted = stats["claims_by_status"].get("contradicted", 0)
        lines = [
            "## Knowledge Graph Memory (memorygraph)",
            f"Graph: {stats['entities']} entities, {stats['open_relationships']} "
            f"relationships, {active} active claims.",
            "Use the graph_memory tool to recall ('about', 'query', 'timeline') "
            "before answering questions about known people, projects, goals, "
            "skills or businesses, and to store new durable knowledge "
            "('remember', 'link').",
        ]
        if contradicted:
            lines.append(
                f"⚠ {contradicted} contradicted claims await review — "
                "use graph_memory action='contradictions' then 'resolve'."
            )
        return "\n".join(lines)

    def prefetch(self, query: str, *, session_id: str = "") -> str:
        if self._store is None or not self._prefetch_enabled or not query:
            return ""
        try:
            hits = self._store.search(query, limit=5)
        except Exception:
            logger.exception("memorygraph: prefetch search failed")
            return ""
        if not hits:
            return ""
        lines = ["[memorygraph recall]"]
        for hit in hits:
            if hit["_kind"] == "entity":
                lines.append(f"- entity: {hit['name']} ({hit['type']}) — {hit['summary']}".rstrip(" —"))
            else:
                lines.append(
                    f"- {hit['entity_name']}.{hit['attribute']} = {hit['value']} "
                    f"(confidence {float(hit['confidence']):.2f}, {hit['tier']})"
                )
        return "\n".join(lines)

    # -- built-in memory mirroring ---------------------------------------------------

    def on_memory_write(
        self,
        action: str,
        target: str,
        content: str,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Mirror built-in MEMORY.md / USER.md writes into the graph.

        Mirrored entries land as claims on the 'Hermes Notes' or 'User'
        entity with evidence kind 'builtin_memory', so file memory and
        graph memory stay consistent without changing built-in behavior.
        """
        if self._engine is None or self._store is None:
            return
        if action not in ("add", "replace") or not (content or "").strip():
            return
        try:
            entity_name = "User" if target == "user" else "Hermes Notes"
            entity_type = "person" if target == "user" else "concept"
            entity = self._store.upsert_entity(entity_name, entity_type)
            session_id = str((metadata or {}).get("session_id") or self._session_id)
            self._engine.assert_claim(
                entity["id"], "note", content.strip(), confidence=0.6,
                evidence={
                    "kind": "builtin_memory",
                    "ref": f"{target}:{action}",
                    "quote": content.strip()[:200],
                    "session_id": session_id,
                },
            )
        except Exception:
            logger.exception("memorygraph: failed to mirror built-in memory write")

    # -- tools -----------------------------------------------------------------------

    def get_tool_schemas(self) -> List[Dict[str, Any]]:
        return [GRAPH_MEMORY_SCHEMA]

    def handle_tool_call(self, tool_name: str, args: Dict[str, Any], **kwargs) -> str:
        if tool_name != "graph_memory":
            return json.dumps({"error": f"unknown tool: {tool_name}"})
        if self._engine is None or self._store is None:
            return json.dumps({"error": "memorygraph is not initialized"})
        action = str(args.get("action") or "")
        handler = getattr(self, f"_action_{action}", None)
        if handler is None:
            return json.dumps({"error": f"unknown action: {action}"})
        try:
            result = handler(args)
        except ValueError as e:
            return json.dumps({"error": str(e)})
        except Exception:
            logger.exception("memorygraph: action %s failed", action)
            return json.dumps({"error": f"action {action} failed; see logs"})
        return json.dumps(result, ensure_ascii=False, default=str)

    # Individual actions. Each returns a JSON-serializable dict.

    def _require(self, args: Dict[str, Any], *names: str) -> List[Any]:
        values = []
        for n in names:
            v = args.get(n)
            if v is None or (isinstance(v, str) and not v.strip()):
                raise ValueError(f"'{n}' is required for this action")
            values.append(v)
        return values

    def _evidence_from_args(self, args: Dict[str, Any]) -> Dict[str, Any]:
        return {
            "kind": "tool",
            "ref": str(args.get("source") or ""),
            "quote": str(args.get("quote") or ""),
            "session_id": self._session_id,
        }

    def _action_remember(self, args: Dict[str, Any]) -> Dict[str, Any]:
        entity_name, attribute, value = self._require(args, "entity", "attribute", "value")
        entity = self._store.upsert_entity(
            str(entity_name), str(args.get("entity_type") or "concept")
        )
        result = self._engine.assert_claim(
            entity["id"],
            str(attribute),
            str(value),
            confidence=float(args.get("confidence") or 0.6),
            exclusive=bool(args.get("exclusive") or False),
            evidence=self._evidence_from_args(args),
        )
        return {
            "outcome": result["outcome"],
            "claim": result["claim"],
            "entity": {"id": entity["id"], "name": entity["name"], "type": entity["type"]},
            "conflicts": result.get("conflicts", []),
        }

    def _action_link(self, args: Dict[str, Any]) -> Dict[str, Any]:
        src_name, dst_name, rel_type = self._require(args, "src", "dst", "rel_type")
        src = self._store.upsert_entity(str(src_name), str(args.get("entity_type") or "concept"))
        dst = self._store.upsert_entity(str(dst_name))
        rel = self._store.add_relationship(
            src["id"], dst["id"], str(rel_type),
            confidence=float(args.get("confidence") or 0.6),
        )
        self._store.add_evidence("relationship", rel["id"], **self._evidence_from_args(args))
        return {"relationship": rel, "src": src["name"], "dst": dst["name"]}

    def _action_unlink(self, args: Dict[str, Any]) -> Dict[str, Any]:
        (rel_id,) = self._require(args, "relationship_id")
        ok = self._store.end_relationship(int(rel_id))
        return {"ended": ok, "relationship_id": int(rel_id)}

    def _action_about(self, args: Dict[str, Any]) -> Dict[str, Any]:
        (entity_name,) = self._require(args, "entity")
        entity = self._store.resolve_entity(str(entity_name))
        if not entity:
            return {"found": False, "entity": str(entity_name)}
        claims = self._store.claims_for(entity["id"])
        for claim in claims:
            claim["evidence_count"] = self._store.evidence_count("claim", claim["id"])
        return {
            "found": True,
            "entity": entity,
            "claims": sorted(claims, key=lambda c: (c["tier"] != "core",
                                                    c["tier"] != "established",
                                                    -float(c["confidence"]))),
            "relationships": self._store.relationships_for(entity["id"]),
        }

    def _action_query(self, args: Dict[str, Any]) -> Dict[str, Any]:
        (query,) = self._require(args, "query")
        limit = int(args.get("limit") or 10)
        return {"results": self._store.search(str(query), limit=limit)}

    def _action_timeline(self, args: Dict[str, Any]) -> Dict[str, Any]:
        (entity_name,) = self._require(args, "entity")
        entity = self._store.resolve_entity(str(entity_name))
        if not entity:
            return {"found": False, "entity": str(entity_name)}
        claims = self._store.claims_for(
            entity["id"], attribute=str(args.get("attribute") or ""), include_history=True
        )
        return {"found": True, "entity": entity["name"], "timeline": claims}

    def _action_contradictions(self, args: Dict[str, Any]) -> Dict[str, Any]:
        return {"groups": self._engine.find_contradictions()}

    def _action_resolve(self, args: Dict[str, Any]) -> Dict[str, Any]:
        (claim_id,) = self._require(args, "claim_id")
        return self._engine.resolve_contradiction(int(claim_id))

    def _action_duplicates(self, args: Dict[str, Any]) -> Dict[str, Any]:
        return {"groups": self._engine.find_duplicates()}

    def _action_feedback(self, args: Dict[str, Any]) -> Dict[str, Any]:
        (claim_id,) = self._require(args, "claim_id")
        if args.get("helpful") is None:
            raise ValueError("'helpful' is required for this action")
        claim = self._engine.feedback(int(claim_id), bool(args["helpful"]))
        if claim is None:
            raise ValueError(f"claim {claim_id} not found")
        return {"claim": claim}

    def _action_forget(self, args: Dict[str, Any]) -> Dict[str, Any]:
        (claim_id,) = self._require(args, "claim_id")
        ok = self._engine.retract(int(claim_id), reason="user request")
        return {"retracted": ok, "claim_id": int(claim_id)}

    def _action_sweep(self, args: Dict[str, Any]) -> Dict[str, Any]:
        return self._engine.sweep()

    def _action_stats(self, args: Dict[str, Any]) -> Dict[str, Any]:
        stats = self._store.stats()
        stats["recent_governance_events"] = [
            {"ts": e["ts"], "event": e["event"], "subject_id": e["subject_id"]}
            for e in self._store.recent_events(10)
        ]
        return stats

    # -- setup wizard -------------------------------------------------------------------

    def get_config_schema(self) -> List[Dict[str, Any]]:
        return [
            {
                "key": "half_life_days",
                "description": "Knowledge aging half-life in days (confidence decay).",
                "required": False,
                "default": "90",
            },
            {
                "key": "duplicate_similarity",
                "description": "Near-duplicate similarity threshold (0-1).",
                "required": False,
                "default": "0.88",
            },
        ]

    def save_config(self, values: Dict[str, Any], hermes_home: str) -> None:
        path = os.path.join(hermes_home, _CONFIG_FILENAME)
        config = _load_json_config(hermes_home)
        for key in ("half_life_days", "duplicate_similarity"):
            if key in values and values[key] not in (None, ""):
                try:
                    config[key] = float(values[key])
                except (TypeError, ValueError):
                    continue
        os.makedirs(hermes_home, exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(config, f, indent=2)
        logger.info("memorygraph: config saved to %s", path)


def register(ctx) -> None:
    """Plugin entry point — called by the memory provider loader."""
    ctx.register_memory_provider(MemoryGraphProvider())
