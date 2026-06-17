"""Artifact helpers for Council Gate V1."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict

from .models import CouncilReviewRequest, CouncilReviewResult


def write_council_artifact(*, base_dir: str | Path, request: CouncilReviewRequest, result: CouncilReviewResult) -> Dict[str, Path]:
    """Write compact legacy-compatible Council markdown and JSON artifacts."""

    base = Path(base_dir)
    base.mkdir(parents=True, exist_ok=True)
    stem = request.review_id or "council-review"
    markdown = base / f"{stem}.md"
    json_path = base / f"{stem}.json"
    markdown.write_text(
        "# Council Gate Review\n\n"
        f"- Review ID: `{request.review_id}`\n"
        f"- Gate: `{request.gate_type}`\n"
        f"- Decision: `{result.decision}`\n"
        f"- Reviewer: `{result.reviewer}`\n\n"
        "## Summary\n"
        f"{result.summary}\n",
        encoding="utf-8",
    )
    json_path.write_text(
        json.dumps({"request": request.to_dict(), "result": result.to_dict()}, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    result.artifact_path = str(json_path)
    return {"markdown": markdown, "json": json_path}
