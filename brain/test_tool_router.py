#!/usr/bin/env python3
"""
Regression test for tool-schema filtering.

Root cause: the main Telegram bot loop (assistant.py::_tool_call_loop) sent
ALL 79+ registered tool schemas on every tool-calling turn (~13,000 tokens
fixed overhead), regardless of what the user asked. That alone nearly maxes
out Groq's 12,000 TPM limit before counting conversation history or the
message itself -- the real reason trading queries (which trigger tool
calling) kept blowing through the whole provider fallback cascade.

tools/router.py groups tools into categories and picks only the categories
relevant to the user's message (by keyword) plus a small always-on core set,
falling back to the full list when nothing matches (never worse than the
old behavior).

Run: python test_tool_router.py
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

OK = "[OK]"
FAIL = "[FAIL]"
failures = []


def check(name, condition):
    status = OK if condition else FAIL
    print(f"  {status} {name}")
    if not condition:
        failures.append(name)


def _schema(name):
    return {"function": {"name": name, "description": "", "parameters": {}}}


ALL_TOOL_NAMES = [
    "web_search", "web_fetch", "search_notes", "vault_read", "vault_write", "vault_list",
    "remember", "recall", "graph_connections", "graph_search",
    "iol_status", "iol_crypto_picks", "iol_opportunities", "iol_paper_trade", "iol_learning",
    "replicate_viral", "generate_video", "clone_voice", "produce_video",
    "publish_video", "publish_text", "content_calendar",
    "design_page", "iterate_design", "generate_html",
    "lead_gen", "freelance", "seo_factory", "ecommerce", "crm",
    "calendar", "email", "set_reminder", "analyze_file",
    "github", "code_diagnostics", "find_definition", "find_references", "run_command",
    "create_task", "check_tasks", "create_cron_job",
    "autoreason", "parallel_solve", "write_novel",
    "delegate_to_agent", "delegate_to_director",
]
ALL_SCHEMAS = [_schema(n) for n in ALL_TOOL_NAMES]


def test_trading_query_scopes_to_trading_plus_core():
    from tools.router import select_relevant_schemas

    selected = select_relevant_schemas("como va el trading?", ALL_SCHEMAS)
    names = {s["function"]["name"] for s in selected}

    check("Includes trading tools", {"iol_status", "iol_crypto_picks", "iol_learning"} <= names)
    check("Excludes unrelated video tools", "generate_video" not in names and "clone_voice" not in names)
    check("Excludes unrelated business tools", "seo_factory" not in names and "crm" not in names)
    check(
        "Drastically smaller than full schema set",
        len(selected) < len(ALL_SCHEMAS) * 0.5,
    )


def test_video_query_scopes_to_video_plus_core():
    from tools.router import select_relevant_schemas

    selected = select_relevant_schemas("quiero armar un video viral de tiktok", ALL_SCHEMAS)
    names = {s["function"]["name"] for s in selected}

    check("Includes video tools", {"replicate_viral", "generate_video"} <= names)
    check("Excludes trading tools", "iol_status" not in names and "iol_paper_trade" not in names)


def test_core_tools_always_present():
    from tools.router import select_relevant_schemas

    selected = select_relevant_schemas("como va el trading?", ALL_SCHEMAS)
    names = {s["function"]["name"] for s in selected}
    check(
        "Core tools (web_search, memory, delegation) always included",
        {"web_search", "remember", "recall", "delegate_to_agent"} <= names,
    )


def test_unmatched_query_falls_back_to_everything():
    from tools.router import select_relevant_schemas

    selected = select_relevant_schemas("asdkjahsdkjahsd 12345 ???", ALL_SCHEMAS)
    check(
        "No keyword match -> safe fallback to the full schema set (never worse than before)",
        len(selected) == len(ALL_SCHEMAS),
    )


def test_empty_message_falls_back_to_everything():
    from tools.router import select_relevant_schemas

    selected = select_relevant_schemas("", ALL_SCHEMAS)
    check("Empty message -> full schema set", len(selected) == len(ALL_SCHEMAS))


def test_accents_and_case_do_not_break_matching():
    from tools.router import select_relevant_schemas

    selected = select_relevant_schemas("¿CÓMO ESTÁN MIS POSICIONES ABIERTAS?", ALL_SCHEMAS)
    names = {s["function"]["name"] for s in selected}
    check("Matches despite accents/uppercase", "iol_status" in names)


if __name__ == "__main__":
    print("=" * 60)
    print("  Tool schema router regression test")
    print("=" * 60)
    test_trading_query_scopes_to_trading_plus_core()
    test_video_query_scopes_to_video_plus_core()
    test_core_tools_always_present()
    test_unmatched_query_falls_back_to_everything()
    test_empty_message_falls_back_to_everything()
    test_accents_and_case_do_not_break_matching()
    print("=" * 60)
    if failures:
        print(f"{FAIL} {len(failures)} check(s) failed: {failures}")
        sys.exit(1)
    print(f"{OK} All checks passed")
