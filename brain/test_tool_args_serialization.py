#!/usr/bin/env python3
"""
Regression test for the tool-calling history corruption bug.

Root cause: inference_client.py parsed `tool_calls[].function.arguments`
into a dict before returning it. assistant.py / base_agent.py then stored
that dict straight into the conversation history. On any fallback
provider after OpenRouter (Groq, Google AI, Z.ai), the OpenAI-compatible
API rejects the whole request because `arguments` must be a JSON string,
not an object -> every cloud fallback broke, leaving only Ollama (which
tolerates dicts) able to answer, ~2-3min later.

This test proves messages are serialized correctly at the HTTP boundary
for OpenAI-compatible providers, while the caller's dict-based history
(needed for local tool execution) is left untouched.

Run: python test_tool_args_serialization.py
"""
import sys
import json
from pathlib import Path
from unittest.mock import MagicMock, patch

sys.path.insert(0, str(Path(__file__).parent))

OK = "[OK]"
FAIL = "[FAIL]"
failures = []


def _fake_openai_response():
    msg = MagicMock()
    msg.content = "ok"
    msg.tool_calls = None
    resp = MagicMock()
    resp.choices = [MagicMock(message=msg)]
    return resp


def check(name, condition):
    status = OK if condition else FAIL
    print(f"  {status} {name}")
    if not condition:
        failures.append(name)


def test_groq_serializes_dict_arguments():
    import inference_client as ic

    # History as assistant.py / base_agent.py actually store it: dict arguments
    poisoned_messages = [
        {"role": "user", "content": "como va el trading?"},
        {
            "role": "assistant",
            "content": "",
            "tool_calls": [
                {"function": {"name": "iol_status", "arguments": {"symbol": "BTC"}}}
            ],
        },
        {"role": "tool", "content": "status: ok"},
    ]
    original_snapshot = json.dumps(poisoned_messages, sort_keys=True)

    captured = {}

    def fake_create(**kwargs):
        captured["messages"] = kwargs["messages"]
        return _fake_openai_response()

    fake_client = MagicMock()
    fake_client.chat.completions.create.side_effect = fake_create

    with patch.object(ic, "_get_groq_client", return_value=fake_client):
        ic._groq_chat(poisoned_messages, "llama-3.3-70b-versatile")

    sent_args = captured["messages"][1]["tool_calls"][0]["function"]["arguments"]
    check(
        "Groq request serializes dict arguments to a JSON string",
        isinstance(sent_args, str) and json.loads(sent_args) == {"symbol": "BTC"},
    )
    check(
        "Original messages list (used for local tool execution) stays a dict, unmutated",
        json.dumps(poisoned_messages, sort_keys=True) == original_snapshot,
    )


def test_string_arguments_pass_through_unchanged():
    import inference_client as ic

    messages = [
        {"role": "user", "content": "hola"},
        {
            "role": "assistant",
            "content": "",
            "tool_calls": [
                {"function": {"name": "iol_status", "arguments": '{"symbol": "ETH"}'}}
            ],
        },
    ]

    captured = {}

    def fake_create(**kwargs):
        captured["messages"] = kwargs["messages"]
        return _fake_openai_response()

    fake_client = MagicMock()
    fake_client.chat.completions.create.side_effect = fake_create

    with patch.object(ic, "_get_openrouter_client", return_value=fake_client):
        ic._openrouter_chat(messages, "some/model")

    sent_args = captured["messages"][1]["tool_calls"][0]["function"]["arguments"]
    check("Already-string arguments pass through unchanged", sent_args == '{"symbol": "ETH"}')


if __name__ == "__main__":
    print("=" * 60)
    print("  Tool-call arguments serialization regression test")
    print("=" * 60)
    test_groq_serializes_dict_arguments()
    test_string_arguments_pass_through_unchanged()
    print("=" * 60)
    if failures:
        print(f"{FAIL} {len(failures)} check(s) failed: {failures}")
        sys.exit(1)
    print(f"{OK} All checks passed")
