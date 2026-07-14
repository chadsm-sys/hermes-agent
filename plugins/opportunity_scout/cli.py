"""CLI for the Opportunity Scout engine.

Usage: ``python -m plugins.opportunity_scout.cli <command> [...]``

Fully offline. The only writes are to the store file (and moving processed
inbox files within the inbox directory).
"""

from __future__ import annotations

import argparse
import json
import sys
from typing import Any

from .engine import OpportunityScoutEngine
from .models import Opportunity, OpportunityScoutError, SourceType, Stage
from .store import StoreError


def _print(payload: Any, as_json: bool) -> None:
    if as_json:
        print(json.dumps(payload, indent=2, sort_keys=True, default=str))
        return
    if isinstance(payload, str):
        print(payload)
    else:
        print(json.dumps(payload, indent=2, sort_keys=True, default=str))


def _summary_line(opportunity: Opportunity) -> str:
    composite = (
        f"{opportunity.score.composite:6.2f}" if opportunity.score else "  --  "
    )
    return (
        f"{opportunity.opportunity_id[:8]}  {composite}  "
        f"{opportunity.stage.value:<10}  conf={opportunity.confidence:.2f}  "
        f"{opportunity.title}"
    )


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="opportunity-scout",
        description="Local-first opportunity capture, scoring, and validation.",
    )
    parser.add_argument("--store", help="Path to the store file.", default=None)
    parser.add_argument("--json", action="store_true", help="JSON output.")
    sub = parser.add_subparsers(dest="command", required=True)

    add = sub.add_parser("add", help="Capture a new opportunity.")
    add.add_argument("title")
    add.add_argument("--summary", default="")
    add.add_argument("--tags", default="", help="Comma-separated tags.")
    add.add_argument(
        "--source-type",
        default=SourceType.IDEA.value,
        choices=[item.value for item in SourceType],
    )
    add.add_argument("--source-detail", default="")
    add.add_argument("--revenue", type=float, default=0.0, help="Expected annual revenue USD.")
    add.add_argument("--upfront-cost", type=float, default=0.0)
    add.add_argument("--ongoing-cost", type=float, default=0.0, help="Annual ongoing cost USD.")
    add.add_argument("--chad-hours-upfront", type=float, default=0.0)
    add.add_argument("--chad-hours-weekly", type=float, default=0.0)
    add.add_argument("--ai-hours-upfront", type=float, default=0.0)
    add.add_argument("--ai-hours-weekly", type=float, default=0.0)
    add.add_argument(
        "--on-duplicate", default="flag", choices=["flag", "reject", "allow"]
    )

    inbox = sub.add_parser("inbox", help="Ingest all *.json files from a directory.")
    inbox.add_argument("directory")
    inbox.add_argument(
        "--on-duplicate", default="flag", choices=["flag", "reject", "allow"]
    )

    list_cmd = sub.add_parser("list", help="List opportunities.")
    list_cmd.add_argument(
        "--stage", default=None, choices=[item.value for item in Stage]
    )

    show = sub.add_parser("show", help="Show one opportunity in full.")
    show.add_argument("opportunity_id")

    score = sub.add_parser("score", help="Score an opportunity.")
    score.add_argument("opportunity_id")

    validate = sub.add_parser("validate", help="Market validation workflow.")
    validate_sub = validate.add_subparsers(dest="validate_command", required=True)
    begin = validate_sub.add_parser("begin")
    begin.add_argument("opportunity_id")
    evidence = validate_sub.add_parser("evidence")
    evidence.add_argument("opportunity_id")
    evidence.add_argument("stage_id")
    evidence.add_argument("--summary", required=True)
    evidence.add_argument("--source", required=True)
    evidence.add_argument(
        "--strength", default="moderate", choices=["weak", "moderate", "strong"]
    )
    resolve = validate_sub.add_parser("resolve")
    resolve.add_argument("opportunity_id")
    resolve.add_argument("stage_id")
    resolve.add_argument("outcome", choices=["pass", "fail", "skip"])
    resolve.add_argument("--note", default="")

    advance = sub.add_parser("advance", help="Move an opportunity to a new stage.")
    advance.add_argument("opportunity_id")
    advance.add_argument("target", choices=[item.value for item in Stage])
    advance.add_argument("--reason", required=True)

    sub.add_parser("report", help="Portfolio report.")

    return parser


def _resolve_id(engine: OpportunityScoutEngine, prefix: str) -> str:
    """Allow ID prefixes for CLI ergonomics."""
    if engine.store.exists(prefix):
        return prefix
    matches = [
        opportunity.opportunity_id
        for opportunity in engine.store.all()
        if opportunity.opportunity_id.startswith(prefix)
    ]
    if len(matches) == 1:
        return matches[0]
    if not matches:
        raise StoreError(f"No opportunity matches id {prefix!r}.")
    raise StoreError(f"Ambiguous id prefix {prefix!r}: {matches}")


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    engine = OpportunityScoutEngine(store_path=args.store)
    try:
        return _dispatch(engine, args)
    except OpportunityScoutError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1


def _dispatch(engine: OpportunityScoutEngine, args: argparse.Namespace) -> int:
    if args.command == "add":
        result = engine.capture(
            {
                "title": args.title,
                "summary": args.summary,
                "tags": args.tags,
                "source_type": args.source_type,
                "source_detail": args.source_detail,
                "expected_revenue_usd": args.revenue,
                "upfront_cost_usd": args.upfront_cost,
                "ongoing_cost_usd_annual": args.ongoing_cost,
                "chad_hours_upfront": args.chad_hours_upfront,
                "chad_hours_weekly": args.chad_hours_weekly,
                "ai_hours_upfront": args.ai_hours_upfront,
                "ai_hours_weekly": args.ai_hours_weekly,
            },
            on_duplicate=args.on_duplicate,
        )
        if result.rejected_as_duplicate:
            _print(
                {
                    "rejected_as_duplicate": True,
                    "duplicates": [match.to_dict() for match in result.duplicates],
                },
                args.json,
            )
            return 2
        payload: dict[str, Any] = {"opportunity": result.opportunity.to_dict()}
        if result.duplicates:
            payload["duplicates"] = [match.to_dict() for match in result.duplicates]
        _print(payload if args.json else _summary_line(result.opportunity), args.json)
        if result.duplicates and not args.json:
            for match in result.duplicates:
                print(
                    f"  possible duplicate ({match.kind}, {match.similarity:.2f}): "
                    f"{match.opportunity_id[:8]} {match.title}"
                )
        return 0

    if args.command == "inbox":
        result = engine.capture_inbox(args.directory, on_duplicate=args.on_duplicate)
        payload = {
            "captured": len(result.captured),
            "errors": result.errors,
        }
        _print(payload, args.json)
        return 0 if not result.errors else 1

    if args.command == "list":
        opportunities = engine.store.all()
        if args.stage:
            opportunities = [
                item for item in opportunities if item.stage.value == args.stage
            ]
        opportunities.sort(
            key=lambda item: -(item.score.composite if item.score else -1)
        )
        if args.json:
            _print([item.to_dict() for item in opportunities], True)
        else:
            for item in opportunities:
                print(_summary_line(item))
        return 0

    if args.command == "show":
        opportunity = engine.store.get(_resolve_id(engine, args.opportunity_id))
        _print(opportunity.to_dict(), True)
        return 0

    if args.command == "score":
        opportunity = engine.score(_resolve_id(engine, args.opportunity_id))
        _print(
            opportunity.to_dict() if args.json else _summary_line(opportunity),
            args.json,
        )
        return 0

    if args.command == "validate":
        opportunity_id = _resolve_id(engine, args.opportunity_id)
        if args.validate_command == "begin":
            opportunity = engine.begin_validation(opportunity_id)
        elif args.validate_command == "evidence":
            opportunity = engine.add_evidence(
                opportunity_id,
                args.stage_id,
                summary=args.summary,
                source=args.source,
                strength=args.strength,
            )
        else:
            opportunity = engine.resolve_stage(
                opportunity_id, args.stage_id, args.outcome, note=args.note
            )
        _print(opportunity.validation.to_dict(), True)
        return 0

    if args.command == "advance":
        opportunity = engine.advance(
            _resolve_id(engine, args.opportunity_id), args.target, args.reason
        )
        _print(
            opportunity.to_dict() if args.json else _summary_line(opportunity),
            args.json,
        )
        return 0

    if args.command == "report":
        _print(engine.portfolio_report(), True)
        return 0

    raise AssertionError(f"Unhandled command: {args.command}")


if __name__ == "__main__":
    raise SystemExit(main())
