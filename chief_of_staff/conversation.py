"""Executive Conversation Mode — Part 3 of the Chief of Staff design.

Hermes stops acting like a command runner. Chad speaks to it the way he'd
speak to a chief of staff, and it answers from the Morning Plan and Evening
Report — deterministically, with no fabrication:

- "Good morning."
- "What should I focus on?"
- "What's my bottleneck?"
- "What changed overnight?"
- "Anything I should ignore?"
- "What should I learn?"

Two layers:

1. :func:`classify_intent` — deterministic phrase → intent mapping. Returns
   ``None`` for anything it doesn't recognize, so the existing Hermes
   pipeline handles everything else *unchanged* (behavior preservation).
2. :class:`ExecutiveConversation` — composes a structured
   :class:`ExecutiveResponse` for each intent from injected sources. When a
   brief or report isn't available yet, it says so plainly instead of
   inventing one.
"""

from __future__ import annotations

import enum
import re
from dataclasses import dataclass

from chief_of_staff.evening_report import EveningReportSource
from chief_of_staff.morning_brief import MorningBriefSource


class ExecutiveIntent(enum.Enum):
    MORNING_GREETING = "morning_greeting"
    FOCUS = "focus"
    BOTTLENECK = "bottleneck"
    OVERNIGHT_CHANGES = "overnight_changes"
    IGNORE_LIST = "ignore_list"
    LEARNING = "learning"


#: Ordered (pattern, intent) table. First match wins; order is part of the
#: contract, so more specific phrases must sit above more general ones.
_INTENT_PATTERNS: tuple[tuple[re.Pattern[str], ExecutiveIntent], ...] = (
    (re.compile(r"\bgood\s+morning\b"), ExecutiveIntent.MORNING_GREETING),
    (re.compile(r"\bmorning\b\W*$"), ExecutiveIntent.MORNING_GREETING),
    (re.compile(r"\bfocus\b"), ExecutiveIntent.FOCUS),
    (re.compile(r"\bbottleneck"), ExecutiveIntent.BOTTLENECK),
    (re.compile(r"\bovernight\b"), ExecutiveIntent.OVERNIGHT_CHANGES),
    (re.compile(r"\bwhat(?:'s| is| has)? changed\b"), ExecutiveIntent.OVERNIGHT_CHANGES),
    (re.compile(r"\bignore\b"), ExecutiveIntent.IGNORE_LIST),
    (re.compile(r"\blearn(?:ing)?\b"), ExecutiveIntent.LEARNING),
)


def classify_intent(text: str) -> ExecutiveIntent | None:
    """Map an utterance to an executive intent, or ``None`` if unrecognized.

    Deterministic and conservative: an unrecognized utterance falls through
    to the existing Hermes pipeline rather than being guessed at.
    """
    normalized = " ".join(text.lower().split())
    for pattern, intent in _INTENT_PATTERNS:
        if pattern.search(normalized):
            return intent
    return None


@dataclass(frozen=True, slots=True)
class ExecutiveResponse:
    """Structured answer — rendering (chat, TUI, brief) is the caller's job."""

    intent: ExecutiveIntent
    headline: str
    #: Supporting lines, most important first. May be empty.
    details: tuple[str, ...] = ()
    #: True when the response is degraded because a source had no data yet.
    degraded: bool = False


_NO_BRIEF = "No Morning Plan is available yet — Mission Control hasn't published one."
_NO_REPORT = "No Evening Report is available yet — Mission Control hasn't published one."


class ExecutiveConversation:
    """Deterministic composers for each executive intent.

    Sources are injected (:class:`MorningBriefSource` /
    :class:`EveningReportSource`), so this class runs identically against the
    future Mission Control adapter and against static fixtures today.
    """

    def __init__(
        self,
        morning_source: MorningBriefSource,
        evening_source: EveningReportSource,
    ) -> None:
        self._morning_source = morning_source
        self._evening_source = evening_source

    # -- public API ----------------------------------------------------------

    def respond(self, text: str) -> ExecutiveResponse | None:
        """Answer an utterance, or ``None`` so the normal pipeline handles it."""
        intent = classify_intent(text)
        if intent is None:
            return None
        composer = {
            ExecutiveIntent.MORNING_GREETING: self.morning_greeting,
            ExecutiveIntent.FOCUS: self.focus,
            ExecutiveIntent.BOTTLENECK: self.bottleneck,
            ExecutiveIntent.OVERNIGHT_CHANGES: self.overnight_changes,
            ExecutiveIntent.IGNORE_LIST: self.ignore_list,
            ExecutiveIntent.LEARNING: self.learning,
        }[intent]
        return composer()

    # -- composers -----------------------------------------------------------

    def morning_greeting(self) -> ExecutiveResponse:
        """"Good morning." → the whole day in one glance."""
        brief = self._morning_source.fetch_latest()
        if brief is None:
            return ExecutiveResponse(
                intent=ExecutiveIntent.MORNING_GREETING, headline=_NO_BRIEF, degraded=True
            )
        chad_items = brief.chad_items()
        details = [
            f"Your plan has {len(chad_items)} item(s) needing you — "
            f"about {brief.estimated_operator_minutes} minutes of your time.",
            f"Bottleneck: {brief.biggest_bottleneck.summary}",
            f"Recommendation: {brief.executive_recommendation.title}",
        ]
        details.extend(
            f"{index}. {item.title} (~{item.estimated_minutes} min)"
            for index, item in enumerate(chad_items, start=1)
        )
        hermes_count = len(brief.hermes_items()) + len(brief.ai_responsibilities)
        details.append(f"I'm carrying {hermes_count} item(s) autonomously.")
        return ExecutiveResponse(
            intent=ExecutiveIntent.MORNING_GREETING,
            headline=f"Good morning. Plan for {brief.generated_for} is loaded.",
            details=tuple(details),
        )

    def focus(self) -> ExecutiveResponse:
        """"What should I focus on?" → the single best use of Chad's time."""
        brief = self._morning_source.fetch_latest()
        if brief is None:
            return ExecutiveResponse(
                intent=ExecutiveIntent.FOCUS, headline=_NO_BRIEF, degraded=True
            )
        rec = brief.executive_recommendation
        return ExecutiveResponse(
            intent=ExecutiveIntent.FOCUS,
            headline=f"Focus on: {rec.title}",
            details=(
                rec.rationale,
                f"Costs you about {rec.chad_effort_minutes} minutes; "
                f"expected return ≈ ${rec.expected_roi_usd:,.0f}.",
            ),
        )

    def bottleneck(self) -> ExecutiveResponse:
        """"What's my bottleneck?" → the constraint and the one unblocking move."""
        brief = self._morning_source.fetch_latest()
        if brief is None:
            return ExecutiveResponse(
                intent=ExecutiveIntent.BOTTLENECK, headline=_NO_BRIEF, degraded=True
            )
        b = brief.biggest_bottleneck
        return ExecutiveResponse(
            intent=ExecutiveIntent.BOTTLENECK,
            headline=f"Bottleneck: {b.summary}",
            details=(f"Cost of leaving it: {b.impact}", f"Unblocking move: {b.unblocking_action}"),
        )

    def overnight_changes(self) -> ExecutiveResponse:
        """"What changed overnight?" → last Evening Report, improvements first."""
        report = self._evening_source.fetch_latest()
        if report is None:
            return ExecutiveResponse(
                intent=ExecutiveIntent.OVERNIGHT_CHANGES, headline=_NO_REPORT, degraded=True
            )
        details = [report.summary]
        details.extend(f"Improved: {imp.description}" for imp in report.ai_improvements)
        details.extend(
            f"Opportunity: {opp.title} (≈ ${opp.expected_roi_usd:,.0f}, {opp.effort} effort)"
            for opp in report.top_opportunities()
        )
        return ExecutiveResponse(
            intent=ExecutiveIntent.OVERNIGHT_CHANGES,
            headline=f"Overnight, {len(report.ai_improvements)} improvement(s) landed.",
            details=tuple(details),
        )

    def ignore_list(self) -> ExecutiveResponse:
        """"Anything I should ignore?" → what is explicitly NOT worth Chad's time.

        Anti-recommendations are as valuable as recommendations: everything
        Hermes already owns, plus low-ROI opportunities, is declared safe to
        ignore so the 90-minute window goes only to what needs Chad.
        """
        brief = self._morning_source.fetch_latest()
        if brief is None:
            return ExecutiveResponse(
                intent=ExecutiveIntent.IGNORE_LIST, headline=_NO_BRIEF, degraded=True
            )
        ignorable = [
            f"{item.title} — mine, I'll report back" for item in brief.hermes_items()
        ]
        ignorable.extend(
            f"{resp.description} — running autonomously"
            for resp in brief.ai_responsibilities
            if resp.autonomous
        )
        if not ignorable:
            return ExecutiveResponse(
                intent=ExecutiveIntent.IGNORE_LIST,
                headline="Nothing is safely ignorable today — every open item needs you.",
            )
        return ExecutiveResponse(
            intent=ExecutiveIntent.IGNORE_LIST,
            headline=f"Safe to ignore today: {len(ignorable)} item(s). They're covered.",
            details=tuple(ignorable),
        )

    def learning(self) -> ExecutiveResponse:
        """"What should I learn?" → compounding capabilities worth understanding."""
        report = self._evening_source.fetch_latest()
        if report is None:
            return ExecutiveResponse(
                intent=ExecutiveIntent.LEARNING, headline=_NO_REPORT, degraded=True
            )
        # Highest-compounding capabilities are the ones worth Chad's study time.
        entries = sorted(
            report.compound_engine,
            key=lambda e: (-e.minutes_saved_total, -e.reuse_count, e.id),
        )
        if not entries:
            return ExecutiveResponse(
                intent=ExecutiveIntent.LEARNING,
                headline="No compounding capabilities on record yet — nothing to study.",
            )
        details = tuple(
            f"{e.capability} — reused {e.reuse_count}×, "
            f"{e.minutes_saved_total} operator minutes saved so far"
            for e in entries
        )
        return ExecutiveResponse(
            intent=ExecutiveIntent.LEARNING,
            headline=f"Worth learning: {entries[0].capability}",
            details=details,
        )
