"""Executive Conversation Mode tests (Part 3)."""

from __future__ import annotations

import pytest

from chief_of_staff.conversation import (
    ExecutiveConversation,
    ExecutiveIntent,
    classify_intent,
)
from chief_of_staff.evening_report import StaticEveningReportSource, parse_evening_report
from chief_of_staff.morning_brief import StaticMorningBriefSource, parse_morning_brief


class TestIntentClassification:
    @pytest.mark.parametrize(
        ("utterance", "intent"),
        [
            ("Good morning.", ExecutiveIntent.MORNING_GREETING),
            ("good   MORNING", ExecutiveIntent.MORNING_GREETING),
            ("What should I focus on?", ExecutiveIntent.FOCUS),
            ("Where should my focus be today", ExecutiveIntent.FOCUS),
            ("What's my bottleneck?", ExecutiveIntent.BOTTLENECK),
            ("biggest bottlenecks right now", ExecutiveIntent.BOTTLENECK),
            ("What changed overnight?", ExecutiveIntent.OVERNIGHT_CHANGES),
            ("anything happen overnight", ExecutiveIntent.OVERNIGHT_CHANGES),
            ("Anything I should ignore?", ExecutiveIntent.IGNORE_LIST),
            ("What should I learn?", ExecutiveIntent.LEARNING),
            ("what is worth learning", ExecutiveIntent.LEARNING),
        ],
    )
    def test_recognized_phrases(self, utterance, intent):
        assert classify_intent(utterance) is intent

    @pytest.mark.parametrize(
        "utterance",
        [
            "run the gateway restart script",
            "git status",
            "hello",
            "",
            "log my shift",  # retired command — must NOT be captured
        ],
    )
    def test_unrecognized_phrases_fall_through(self, utterance):
        """Behavior preservation: everything else goes to the normal pipeline."""
        assert classify_intent(utterance) is None

    def test_classification_is_deterministic(self):
        assert len({classify_intent("Good morning.") for _ in range(20)}) == 1


@pytest.fixture
def conversation(morning_brief_payload, evening_report_payload):
    return ExecutiveConversation(
        morning_source=StaticMorningBriefSource(parse_morning_brief(morning_brief_payload)),
        evening_source=StaticEveningReportSource(parse_evening_report(evening_report_payload)),
    )


@pytest.fixture
def empty_conversation():
    return ExecutiveConversation(
        morning_source=StaticMorningBriefSource(),
        evening_source=StaticEveningReportSource(),
    )


class TestComposers:
    def test_good_morning_covers_the_whole_day(self, conversation):
        response = conversation.respond("Good morning.")
        assert response is not None
        assert response.intent is ExecutiveIntent.MORNING_GREETING
        assert not response.degraded
        joined = " ".join((response.headline, *response.details))
        assert "35 minutes" in joined  # estimated operator time
        assert "Hermes gateway restarts are manual" in joined  # bottleneck
        assert "Gusto payroll authorization" in joined  # recommendation

    def test_focus_names_one_thing_with_cost_and_return(self, conversation):
        response = conversation.respond("What should I focus on?")
        assert "Gusto payroll authorization" in response.headline
        joined = " ".join(response.details)
        assert "10 minutes" in joined
        assert "$57,000" in joined

    def test_bottleneck_includes_the_unblocking_move(self, conversation):
        response = conversation.respond("What's my bottleneck?")
        assert "gateway restarts" in response.headline
        assert any("Unblocking move" in line for line in response.details)

    def test_overnight_reads_the_evening_report(self, conversation):
        response = conversation.respond("What changed overnight?")
        joined = " ".join(response.details)
        assert "Retry logic now survives provider timeouts" in joined
        assert "Expert witness inquiry" in joined  # top opportunity by ROI

    def test_ignore_list_covers_hermes_owned_work(self, conversation):
        response = conversation.respond("Anything I should ignore?")
        joined = " ".join(response.details)
        assert "Rebuild flaky gateway test" in joined  # hermes-owned plan item
        assert "Triage overnight backlog" in joined  # autonomous responsibility
        assert "Draft invoice follow-ups" not in joined  # NOT autonomous → not ignorable

    def test_learning_ranks_by_compounding_value(self, conversation):
        response = conversation.respond("What should I learn?")
        assert "Backlog triage classifier" in response.headline  # 600 min > 240 min
        assert len(response.details) == 2

    def test_command_utterances_return_none(self, conversation):
        assert conversation.respond("restart the gateway") is None


class TestDegradedMode:
    @pytest.mark.parametrize(
        "utterance",
        [
            "Good morning.",
            "What should I focus on?",
            "What's my bottleneck?",
            "What changed overnight?",
            "Anything I should ignore?",
            "What should I learn?",
        ],
    )
    def test_no_data_yields_honest_degraded_answer(self, empty_conversation, utterance):
        response = empty_conversation.respond(utterance)
        assert response is not None
        assert response.degraded
        assert "Mission Control" in response.headline
        assert response.details == ()
