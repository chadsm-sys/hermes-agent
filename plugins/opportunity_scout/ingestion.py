"""Offline ingestion for the Opportunity Scout engine.

Three entry points, none of which ever touch the network:

- ``ingest_record``   — normalize a raw dict into an ``Opportunity``.
- ``ingest_json_file``— one JSON object, or a list of objects, from disk.
- ``ingest_inbox``    — every ``*.json`` file in a directory; processed
  files are moved to ``<dir>/processed/``. Malformed files are left in
  place and reported — never deleted.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from .models import IngestionError, Opportunity

ALLOWED_FIELDS = frozenset(
    {
        "title",
        "summary",
        "tags",
        "source_type",
        "source_detail",
        "expected_revenue_usd",
        "upfront_cost_usd",
        "ongoing_cost_usd_annual",
        "chad_hours_upfront",
        "chad_hours_weekly",
        "ai_hours_upfront",
        "ai_hours_weekly",
        "confidence",
    }
)

PROCESSED_DIR_NAME = "processed"


@dataclass
class InboxResult:
    ingested: list[Opportunity] = field(default_factory=list)
    errors: dict[str, str] = field(default_factory=dict)  # filename -> error


def ingest_record(record: dict[str, Any]) -> Opportunity:
    """Normalize and validate a raw dict into an Opportunity."""
    if not isinstance(record, dict):
        raise IngestionError(f"Opportunity record must be a dict, got {type(record).__name__}")
    unknown = set(record) - ALLOWED_FIELDS
    if unknown:
        raise IngestionError(f"Unknown opportunity fields: {sorted(unknown)}")
    if not str(record.get("title", "")).strip():
        raise IngestionError("Opportunity record requires a non-empty 'title'.")
    tags = record.get("tags", [])
    if isinstance(tags, str):
        tags = [part for part in tags.split(",") if part.strip()]
    if not isinstance(tags, list):
        raise IngestionError("'tags' must be a list or comma-separated string.")
    kwargs = {key: value for key, value in record.items() if key != "tags"}
    return Opportunity(tags=[str(tag) for tag in tags], **kwargs)


def ingest_json_file(path: str | Path) -> list[Opportunity]:
    """Ingest one JSON object or a list of objects from a file on disk."""
    file_path = Path(path)
    try:
        raw = json.loads(file_path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise IngestionError(f"No such file: {file_path}") from exc
    except (json.JSONDecodeError, UnicodeDecodeError) as exc:
        raise IngestionError(f"Invalid JSON in {file_path}: {exc}") from exc
    records = raw if isinstance(raw, list) else [raw]
    return [ingest_record(record) for record in records]


def ingest_inbox(directory: str | Path) -> InboxResult:
    """Ingest every ``*.json`` file in a directory.

    Successfully ingested files move to ``<directory>/processed/``.
    Files that fail to parse are left in place and reported in
    ``InboxResult.errors``.
    """
    inbox = Path(directory)
    if not inbox.is_dir():
        raise IngestionError(f"Inbox directory does not exist: {inbox}")
    processed_dir = inbox / PROCESSED_DIR_NAME
    result = InboxResult()
    for file_path in sorted(inbox.glob("*.json")):
        try:
            opportunities = ingest_json_file(file_path)
        except IngestionError as exc:
            result.errors[file_path.name] = str(exc)
            continue
        result.ingested.extend(opportunities)
        processed_dir.mkdir(parents=True, exist_ok=True)
        destination = processed_dir / file_path.name
        counter = 1
        while destination.exists():
            destination = processed_dir / f"{file_path.stem}-{counter}{file_path.suffix}"
            counter += 1
        file_path.rename(destination)
    return result
