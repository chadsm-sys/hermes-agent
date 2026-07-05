"""Human leverage metrics — Part 6 of the Chief of Staff design.

The Chief of Staff layer is only worth running if it measurably buys Chad
time and makes recommendations he actually takes. This module defines the
architecture for tracking exactly that:

- Hours Chad saved
- Operator time required
- AI autonomous time
- Recommendations accepted
- Recommendations rejected

The ledger is a pure in-memory accumulator with a dict round-trip, so any
storage backend (JSON file, SQLite, Mission Control itself) can persist it
by implementing :class:`LeverageStore`. No storage is wired here — interface
only, consistent with the rest of the package.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol, runtime_checkable


@dataclass(frozen=True, slots=True)
class LeverageSnapshot:
    """Point-in-time view of the leverage ledger."""

    #: Operator minutes eliminated by AI work (the headline number).
    minutes_saved: int
    #: Minutes of Chad's hands-on time actually spent.
    operator_minutes: int
    #: Minutes the AI layer ran without Chad in the loop.
    ai_autonomous_minutes: int
    recommendations_accepted: int
    recommendations_rejected: int

    @property
    def hours_saved(self) -> float:
        return self.minutes_saved / 60.0

    @property
    def operator_hours(self) -> float:
        return self.operator_minutes / 60.0

    @property
    def ai_autonomous_hours(self) -> float:
        return self.ai_autonomous_minutes / 60.0

    @property
    def recommendations_total(self) -> int:
        return self.recommendations_accepted + self.recommendations_rejected

    @property
    def acceptance_rate(self) -> float | None:
        """Accepted / total, or ``None`` before any recommendation was decided.

        ``None`` (not ``0.0``) so an unused recommender is distinguishable
        from a distrusted one.
        """
        total = self.recommendations_total
        if total == 0:
            return None
        return self.recommendations_accepted / total

    @property
    def leverage_ratio(self) -> float | None:
        """AI autonomous minutes per operator minute, or ``None`` with no operator time."""
        if self.operator_minutes == 0:
            return None
        return self.ai_autonomous_minutes / self.operator_minutes

    def to_dict(self) -> dict[str, int]:
        return {
            "minutes_saved": self.minutes_saved,
            "operator_minutes": self.operator_minutes,
            "ai_autonomous_minutes": self.ai_autonomous_minutes,
            "recommendations_accepted": self.recommendations_accepted,
            "recommendations_rejected": self.recommendations_rejected,
        }


class LeverageLedger:
    """Accumulates leverage events. All inputs are minutes and counts."""

    def __init__(self) -> None:
        self._minutes_saved = 0
        self._operator_minutes = 0
        self._ai_autonomous_minutes = 0
        self._accepted = 0
        self._rejected = 0

    @staticmethod
    def _check_minutes(minutes: int) -> int:
        if isinstance(minutes, bool) or not isinstance(minutes, int):
            raise TypeError(f"minutes must be an integer, got {type(minutes).__name__}")
        if minutes < 0:
            raise ValueError(f"minutes must be >= 0, got {minutes}")
        return minutes

    def record_minutes_saved(self, minutes: int) -> None:
        """Operator minutes eliminated (e.g. a task Hermes did end-to-end)."""
        self._minutes_saved += self._check_minutes(minutes)

    def record_operator_minutes(self, minutes: int) -> None:
        """Minutes of Chad's hands-on time actually consumed."""
        self._operator_minutes += self._check_minutes(minutes)

    def record_ai_autonomous_minutes(self, minutes: int) -> None:
        """Minutes the AI layer worked without Chad in the loop."""
        self._ai_autonomous_minutes += self._check_minutes(minutes)

    def record_recommendation(self, accepted: bool) -> None:
        """Outcome of one executive recommendation Chad decided on."""
        if accepted:
            self._accepted += 1
        else:
            self._rejected += 1

    def snapshot(self) -> LeverageSnapshot:
        return LeverageSnapshot(
            minutes_saved=self._minutes_saved,
            operator_minutes=self._operator_minutes,
            ai_autonomous_minutes=self._ai_autonomous_minutes,
            recommendations_accepted=self._accepted,
            recommendations_rejected=self._rejected,
        )

    def to_dict(self) -> dict[str, int]:
        return self.snapshot().to_dict()

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> LeverageLedger:
        ledger = cls()
        ledger._minutes_saved = cls._check_minutes(payload.get("minutes_saved", 0))
        ledger._operator_minutes = cls._check_minutes(payload.get("operator_minutes", 0))
        ledger._ai_autonomous_minutes = cls._check_minutes(
            payload.get("ai_autonomous_minutes", 0)
        )
        ledger._accepted = cls._check_minutes(payload.get("recommendations_accepted", 0))
        ledger._rejected = cls._check_minutes(payload.get("recommendations_rejected", 0))
        return ledger


@runtime_checkable
class LeverageStore(Protocol):
    """Persistence boundary for the ledger — implemented later, elsewhere."""

    def load(self) -> LeverageLedger:
        """Return the persisted ledger, or a fresh one when none exists."""
        ...  # pragma: no cover - protocol definition

    def save(self, ledger: LeverageLedger) -> None:
        """Persist the ledger atomically."""
        ...  # pragma: no cover - protocol definition
