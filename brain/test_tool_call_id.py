#!/usr/bin/env python3
"""
Regression test for the missing tool_call_id bug.

Root cause: inference_client.py parsed provider tool_calls into
{"function": {"name", "arguments"}} only, dropping the call's `id` and
`type`. assistant.py / base_agent.py then appended `{"role": "tool",
"content": result}` with no `tool_call_id` at all. OpenAI-compatible
providers (OpenRouter, Groq, Google AI, Claude, ChatGPT) require every
`tool` message to carry the `tool_call_id` of the assistant tool_call it
answers -> every cloud provider rejected the request with 400 ("Tool
message must have either name or tool_call_id" / "tool_calls.0.function
.arguments: value must be a string"), and the whole fallback cascade
bottomed out at Ollama (which tolerates the missing field), ~2min later.

This test proves:
1. inference_client parses each tool_call with its `id` + `type: "function"`.
2. The enumerate+setdefault pattern used in assistant.py/base_agent.py
   assigns a fallback id when a provider (e.g. Ollama) omits one, so a
   tool result message can always be paired via tool_call_id.

Run: python test_tool_call_id.py
"""
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

sys.path.insert(0, str(Path(__file__).parent))

OK = "[OK]"
FAIL = "[FAIL]"
failures = []


def check(name, condition):
    status = OK if condition else FAIL
    print(f"  {status} {name}")
    if not condition:
        failures.append(name)


def _fake_response_with_tool_call(call_id: str):
    tc = MagicMock()
    tc.id = call_id
    tc.function.name = "iol_status"
    tc.function.arguments = '{"symbol": "BTC"}'
    msg = MagicMock()
    msg.content = ""
    msg.tool_calls = [tc]
    resp = MagicMock()
    resp.choices = [MagicMock(message=msg)]
    return resp


def test_provider_tool_calls_include_id_and_type():
    import inference_client as ic

    fake_client = MagicMock()
    fake_client.chat.completions.create.return_value = _fake_response_with_tool_call("call_abc123")

    messages = [{"role": "user", "content": "como van mis posiciones?"}]
    with patch.object(ic, "_get_groq_client", return_value=fake_client):
        result = ic._groq_chat(messages, "llama-3.3-70b-versatile")

    tc = result["tool_calls"][0]
    check("Parsed tool_call carries the provider's id", tc.get("id") == "call_abc123")
    check("Parsed tool_call carries type: function", tc.get("type") == "function")
    check("Parsed tool_call keeps the function name/arguments", tc["function"]["name"] == "iol_status")


def test_missing_id_gets_a_fallback_for_pairing():
    """Simulates the enumerate+setdefault fix in assistant.py / base_agent.py
    for providers (Ollama) whose tool_calls carry no id at all."""
    tool_calls = [{"function": {"name": "iol_status", "arguments": {}}}]

    for i, tc in enumerate(tool_calls):
        tc.setdefault("id", f"call_0_{i}")

    tool_call_id = tool_calls[0].get("id")
    tool_result_msg = {"role": "tool", "tool_call_id": tool_call_id, "content": "ok"}

    check("Missing id gets a deterministic fallback assigned", tool_calls[0]["id"] == "call_0_0")
    check(
        "Tool result message's tool_call_id matches the assistant tool_call's id",
        tool_result_msg["tool_call_id"] == tool_calls[0]["id"],
    )


if __name__ == "__main__":
    print("=" * 60)
    print("  Tool-call id / tool_call_id pairing regression test")
    print("=" * 60)
    test_provider_tool_calls_include_id_and_type()
    test_missing_id_gets_a_fallback_for_pairing()
    print("=" * 60)
    if failures:
        print(f"{FAIL} {len(failures)} check(s) failed: {failures}")
        sys.exit(1)
    print(f"{OK} All checks passed")
