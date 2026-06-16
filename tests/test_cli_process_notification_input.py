"""Regression coverage for CLI background notification event preservation."""

from cli import _make_process_notification_input, _unpack_process_notification_input


def test_process_notification_queue_payload_preserves_raw_async_event():
    raw_event = {
        "type": "async_delegation_complete",
        "delegation_id": "delig_test123",
        "status": "completed",
        "goal": "verify raw event preservation",
        "context": "must survive CLI queue handoff",
        "result": {"summary": "done", "children": ["leaf"]},
    }
    formatted_text = (
        "**ASYNC DELEGATION COMPLETE**\n"
        "delegation_id=delig_test123\n"
        "summary=done"
    )

    payload = _make_process_notification_input(raw_event, formatted_text)
    unpacked_text, unpacked_event = _unpack_process_notification_input(payload)

    assert unpacked_text == formatted_text
    assert unpacked_event == raw_event
    assert unpacked_event is not raw_event


def test_unpack_plain_input_is_unchanged_without_raw_event():
    message = "normal user input"

    unpacked_text, unpacked_event = _unpack_process_notification_input(message)

    assert unpacked_text == message
    assert unpacked_event is None
