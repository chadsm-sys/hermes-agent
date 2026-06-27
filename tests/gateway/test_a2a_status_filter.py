"""Regression tests for A2A lifecycle/status filtering."""

from gateway.run import _prepare_gateway_status_message


def test_a2a_lifecycle_status_is_not_delivered_as_reply():
    """A2A send() resolves the JSON-RPC reply Future, so status must be suppressed."""
    assert (
        _prepare_gateway_status_message(
            "a2a",
            "lifecycle",
            "⚠ Codex gpt-5.5 caps context at 272K; auto-compaction was raised.",
        )
        is None
    )


def test_a2a_nonempty_status_is_suppressed_even_if_not_noisy():
    assert _prepare_gateway_status_message("a2a", "status", "working…") is None


def test_local_status_send_unaffected_raw_text_passes_through():
    assert _prepare_gateway_status_message("local", "status", "working…") == "working…"


def test_webhook_status_send_unaffected_raw_text_passes_through():
    assert _prepare_gateway_status_message("webhook", "status", "working…") == "working…"
