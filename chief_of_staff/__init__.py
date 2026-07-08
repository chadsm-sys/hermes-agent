"""Chief of Staff layer — Hermes as Executive Assistant.

Mission Control is the Executive Brain; Hermes is the Executive Assistant.
This package is the interface-only design layer for that relationship:

- ``morning_brief``   — consumer contract for the Mission Control Morning Plan API.
- ``evening_report``  — consumer contract for the Mission Control Evening Report API.
- ``conversation``    — executive conversation mode (intents + deterministic composers).
- ``escalation``      — CONTINUE / PAUSE / NEEDS_CHAD work classification.
- ``ranking``         — deterministic recommendation ranking.
- ``metrics``         — human-leverage metrics (hours saved, operator time, acceptance).

Nothing in this package performs I/O against a live Mission Control install,
mutates Hermes runtime state, or is imported by any existing Hermes code path.
It is safe to ship inert: existing Hermes behavior is preserved byte-for-byte.

See ``docs/HERMES_EXECUTIVE_ARCHITECTURE.md`` for the full design.
"""

from chief_of_staff.contracts import (
    ContractError,
    Recommendation,
    SafetyRisk,
)
from chief_of_staff.conversation import (
    ExecutiveConversation,
    ExecutiveIntent,
    ExecutiveResponse,
    classify_intent,
)
from chief_of_staff.escalation import (
    EscalationDecision,
    EscalationResult,
    WorkSignals,
    classify_work,
)
from chief_of_staff.evening_report import (
    EveningReport,
    EveningReportError,
    EveningReportSource,
    StaticEveningReportSource,
    parse_evening_report,
)
from chief_of_staff.metrics import (
    LeverageLedger,
    LeverageSnapshot,
)
from chief_of_staff.morning_brief import (
    MorningBrief,
    MorningBriefError,
    MorningBriefSource,
    StaticMorningBriefSource,
    parse_morning_brief,
)
from chief_of_staff.ranking import (
    rank_recommendations,
    ranking_key,
    top_recommendation,
)

__all__ = [
    "ContractError",
    "EscalationDecision",
    "EscalationResult",
    "EveningReport",
    "EveningReportError",
    "EveningReportSource",
    "ExecutiveConversation",
    "ExecutiveIntent",
    "ExecutiveResponse",
    "LeverageLedger",
    "LeverageSnapshot",
    "MorningBrief",
    "MorningBriefError",
    "MorningBriefSource",
    "Recommendation",
    "SafetyRisk",
    "StaticEveningReportSource",
    "StaticMorningBriefSource",
    "WorkSignals",
    "classify_intent",
    "classify_work",
    "parse_evening_report",
    "parse_morning_brief",
    "rank_recommendations",
    "ranking_key",
    "top_recommendation",
]
