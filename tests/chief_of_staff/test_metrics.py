"""Human leverage metrics tests (Part 6)."""

from __future__ import annotations

import pytest

from chief_of_staff.metrics import LeverageLedger, LeverageStore


class TestLedgerAccumulation:
    def test_tracks_all_five_metrics(self):
        ledger = LeverageLedger()
        ledger.record_minutes_saved(90)
        ledger.record_minutes_saved(30)
        ledger.record_operator_minutes(45)
        ledger.record_ai_autonomous_minutes(300)
        ledger.record_recommendation(accepted=True)
        ledger.record_recommendation(accepted=True)
        ledger.record_recommendation(accepted=False)

        snap = ledger.snapshot()
        assert snap.minutes_saved == 120
        assert snap.hours_saved == 2.0  # "Hours Chad saved"
        assert snap.operator_minutes == 45  # "Operator time required"
        assert snap.ai_autonomous_minutes == 300  # "AI autonomous time"
        assert snap.recommendations_accepted == 2
        assert snap.recommendations_rejected == 1

    def test_fresh_ledger_is_all_zero(self):
        snap = LeverageLedger().snapshot()
        assert snap.to_dict() == {
            "minutes_saved": 0,
            "operator_minutes": 0,
            "ai_autonomous_minutes": 0,
            "recommendations_accepted": 0,
            "recommendations_rejected": 0,
        }

    def test_negative_minutes_rejected(self):
        ledger = LeverageLedger()
        with pytest.raises(ValueError, match=">= 0"):
            ledger.record_operator_minutes(-5)

    def test_boolean_minutes_rejected(self):
        ledger = LeverageLedger()
        with pytest.raises(TypeError, match="integer"):
            ledger.record_ai_autonomous_minutes(True)  # bool is not a duration


class TestDerivedRates:
    def test_acceptance_rate(self):
        ledger = LeverageLedger()
        ledger.record_recommendation(accepted=True)
        ledger.record_recommendation(accepted=True)
        ledger.record_recommendation(accepted=True)
        ledger.record_recommendation(accepted=False)
        assert ledger.snapshot().acceptance_rate == 0.75

    def test_unused_recommender_is_none_not_zero(self):
        assert LeverageLedger().snapshot().acceptance_rate is None

    def test_leverage_ratio(self):
        ledger = LeverageLedger()
        ledger.record_ai_autonomous_minutes(270)
        ledger.record_operator_minutes(90)
        assert ledger.snapshot().leverage_ratio == 3.0

    def test_leverage_ratio_undefined_without_operator_time(self):
        ledger = LeverageLedger()
        ledger.record_ai_autonomous_minutes(500)
        assert ledger.snapshot().leverage_ratio is None


class TestPersistenceBoundary:
    def test_dict_round_trip(self):
        ledger = LeverageLedger()
        ledger.record_minutes_saved(75)
        ledger.record_operator_minutes(20)
        ledger.record_ai_autonomous_minutes(400)
        ledger.record_recommendation(accepted=True)
        ledger.record_recommendation(accepted=False)

        restored = LeverageLedger.from_dict(ledger.to_dict())
        assert restored.to_dict() == ledger.to_dict()

    def test_from_dict_tolerates_missing_keys(self):
        restored = LeverageLedger.from_dict({"minutes_saved": 10})
        snap = restored.snapshot()
        assert snap.minutes_saved == 10
        assert snap.operator_minutes == 0

    def test_from_dict_rejects_corrupt_values(self):
        with pytest.raises(ValueError, match=">= 0"):
            LeverageLedger.from_dict({"operator_minutes": -1})

    def test_any_load_save_object_satisfies_the_protocol(self):
        class InMemoryStore:
            def __init__(self) -> None:
                self._payload: dict[str, int] = {}

            def load(self) -> LeverageLedger:
                return LeverageLedger.from_dict(self._payload)

            def save(self, ledger: LeverageLedger) -> None:
                self._payload = ledger.to_dict()

        store = InMemoryStore()
        assert isinstance(store, LeverageStore)

        ledger = LeverageLedger()
        ledger.record_minutes_saved(60)
        store.save(ledger)
        assert store.load().snapshot().hours_saved == 1.0
