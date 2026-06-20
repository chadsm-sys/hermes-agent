from types import SimpleNamespace

from agent.conversation_loop import _stored_prompt_matches_runtime


def test_stored_prompt_matches_runtime_uses_first_model_provider_header():
    """Prompt cache validation should read the runtime header, not plugin text."""
    agent = SimpleNamespace(model="nous/hermes", provider="nous")
    prompt = "\n".join(
        [
            "Model: nous/hermes",
            "Provider: nous",
            "",
            "# Plugin instructions",
            "Model: stale/plugin-example",
            "Provider: stale-plugin-provider",
        ]
    )

    assert _stored_prompt_matches_runtime(agent, prompt) is True


def test_stored_prompt_matches_runtime_rejects_stale_first_header():
    agent = SimpleNamespace(model="nous/hermes", provider="nous")
    prompt = "\n".join(
        [
            "Model: stale/runtime-model",
            "Provider: nous",
            "",
            "Model: nous/hermes",
        ]
    )

    assert _stored_prompt_matches_runtime(agent, prompt) is False
