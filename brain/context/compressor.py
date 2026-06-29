"""Context compression: LLM-based summarization of old conversation turns.

Inspired by NousResearch/hermes-agent context management.
When token budget fills up, summarizes old turns and prunes verbose tool outputs.
"""

import logging
from dataclasses import dataclass

from inference_client import chat
from config import OLLAMA_MODEL

logger = logging.getLogger(__name__)

DEFAULT_MAX_MESSAGES = 40
TOOL_OUTPUT_MAX_CHARS = 500
SUMMARY_KEEP_RECENT = 6


@dataclass
class CompressedContext:
    messages: list[dict]
    summary: str = ""
    original_count: int = 0
    compressed_count: int = 0
    pruned_tool_outputs: int = 0


def compress_context(
    messages: list[dict],
    max_messages: int = DEFAULT_MAX_MESSAGES,
    model: str = "",
) -> CompressedContext:
    """Compress conversation context when it exceeds the budget.

    Strategy:
    1. Prune verbose tool outputs to structured summaries
    2. If still over budget, LLM-summarize oldest turns into a single message
    3. Keep recent turns intact for continuity
    """
    model = model or OLLAMA_MODEL
    original_count = len(messages)

    if not messages or len(messages) <= max_messages:
        return CompressedContext(
            messages=messages,
            original_count=original_count,
            compressed_count=len(messages),
        )

    system_msgs = [m for m in messages if m.get("role") == "system"]
    non_system = [m for m in messages if m.get("role") != "system"]

    # Step 1: Prune verbose tool outputs
    pruned_count = 0
    pruned = []
    for msg in non_system:
        if msg.get("role") == "tool" and len(msg.get("content", "")) > TOOL_OUTPUT_MAX_CHARS:
            pruned.append({
                "role": "tool",
                "content": _prune_tool_output(msg["content"]),
            })
            pruned_count += 1
        else:
            pruned.append(msg)

    if len(system_msgs) + len(pruned) <= max_messages:
        return CompressedContext(
            messages=system_msgs + pruned,
            original_count=original_count,
            compressed_count=len(system_msgs) + len(pruned),
            pruned_tool_outputs=pruned_count,
        )

    # Step 2: Summarize old turns
    keep_count = min(SUMMARY_KEEP_RECENT, len(pruned))
    old_turns = pruned[:-keep_count] if keep_count > 0 else pruned
    recent_turns = pruned[-keep_count:] if keep_count > 0 else []

    summary = _summarize_turns(old_turns, model)

    summary_msg = {
        "role": "user",
        "content": f"[Resumen de conversación anterior ({len(old_turns)} mensajes)]\n{summary}",
    }

    compressed = system_msgs + [summary_msg] + recent_turns

    return CompressedContext(
        messages=compressed,
        summary=summary,
        original_count=original_count,
        compressed_count=len(compressed),
        pruned_tool_outputs=pruned_count,
    )


def _prune_tool_output(content: str) -> str:
    """Replace verbose tool output with a structured summary."""
    lines = content.strip().split("\n")
    total_lines = len(lines)

    if total_lines <= 5:
        return content

    # Check for common patterns
    if content.startswith("{") or content.startswith("["):
        return f"[JSON output: {len(content)} chars, {total_lines} lines]\n{content[:200]}..."

    if "error" in content.lower() or "fail" in content.lower():
        error_lines = [l for l in lines if "error" in l.lower() or "fail" in l.lower()]
        return f"[Output with errors: {total_lines} lines]\n" + "\n".join(error_lines[:5])

    # Generic truncation with first and last lines
    first = "\n".join(lines[:3])
    last = "\n".join(lines[-2:])
    return f"[Output: {total_lines} lines, {len(content)} chars]\n{first}\n...\n{last}"


def _summarize_turns(turns: list[dict], model: str) -> str:
    """LLM-summarize a list of conversation turns."""
    conversation = []
    for t in turns:
        role = t.get("role", "unknown")
        content = t.get("content", "")[:300]
        conversation.append(f"[{role}]: {content}")

    turns_text = "\n".join(conversation)
    if len(turns_text) > 3000:
        turns_text = turns_text[:3000] + "\n..."

    msg = (
        f"Resumí esta conversación en un párrafo conciso. "
        f"Mantené: decisiones tomadas, resultados de herramientas, datos clave, y contexto necesario.\n\n"
        f"{turns_text}"
    )

    try:
        return chat(
            [{"role": "system", "content": "Resumís conversaciones de forma concisa preservando información clave."},
             {"role": "user", "content": msg}],
            model,
        ).strip()
    except Exception as e:
        logger.warning("Context summarization failed: %s", e)
        return f"[Conversación previa de {len(turns)} mensajes - resumen no disponible]"


def estimate_tokens(messages: list[dict]) -> int:
    """Rough token estimate (4 chars ≈ 1 token)."""
    total_chars = sum(len(m.get("content", "")) for m in messages)
    return total_chars // 4
