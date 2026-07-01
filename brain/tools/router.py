"""Filtra los schemas de tools a enviar al LLM según el mensaje del usuario.

Mandar las ~80 tools registradas en cada turno de tool-calling cuesta
~13,000 tokens fijos, sin importar la consulta. Eso por sí solo casi agota
el límite de 12,000 TPM de Groq, y explica por qué la cascada de fallback
se rompía justo en las consultas de trading (que activan tool calling).
Acá agrupamos las tools por categoría y solo mandamos las relevantes al
mensaje actual + un set 'core' chico siempre presente. Si nada matchea,
cae de vuelta a mandar todo (nunca peor que el comportamiento anterior).
"""
import unicodedata

# Tools livianas y de propósito general que siempre conviene tener disponibles:
# búsqueda web/notas, memoria, y delegación (que a su vez tiene su propio
# set de tools filtrado por agente en base_agent.py).
CORE_TOOLS = {
    "web_search", "web_fetch", "search_notes",
    "remember", "recall",
    "delegate_to_agent", "delegate_to_director",
}

TOOL_CATEGORIES: dict[str, set[str]] = {
    "trading": {
        "iol_status", "iol_crypto_picks", "iol_opportunities",
        "iol_paper_trade", "iol_learning", "market_monitor",
    },
    "vault": {
        "vault_read", "vault_write", "vault_list",
        "graph_connections", "graph_search",
    },
    "video": {
        "replicate_viral", "generate_video", "analyze_viral", "clone_voice",
        "produce_video", "generate_image", "generate_broll", "heygen_avatar",
        "add_captions", "video_qc", "list_video_jobs", "kanban_video",
        "clip_content", "video_analytics", "analyze_media",
    },
    "social": {
        "publish_video", "publish_text", "content_calendar", "manage_niche",
        "generate_content", "detect_trends", "batch_generate", "daily_briefing",
    },
    "design": {
        "design_page", "iterate_design", "generate_html",
    },
    "business": {
        "lead_gen", "freelance", "seo_factory", "ecommerce", "course_factory",
        "meeting_assistant", "reputation_monitor", "legal_assistant", "crm",
    },
    "productivity": {
        "calendar", "email", "set_reminder", "analyze_file",
    },
    "code": {
        "github", "code_diagnostics", "find_definition", "find_references", "run_command",
    },
    "automation": {
        "create_task", "check_tasks", "cancel_task",
        "create_cron_job", "list_cron_jobs", "delete_cron_job",
        "create_spec", "list_specs", "get_spec", "execute_spec", "delete_spec",
    },
    "reasoning": {
        "autoreason", "parallel_solve", "reasoning_practice", "evolve_prompt",
        "neural_steer", "abliterate_chat", "agent_stats", "mixture_of_agents",
        "write_novel", "strategic_analysis", "framework_guide",
    },
}

CATEGORY_KEYWORDS: dict[str, list[str]] = {
    "trading": [
        "trading", "trade", "posicion", "posiciones", "cripto", "crypto",
        "pump", "altcoin", "mercado", "btc", "bitcoin", "invertir", "inversion",
        "ganancia", "perdida", "pnl", "win rate", "winrate", "iol", "precio",
        "senal", "senales", "operacion", "operaciones", "capital",
    ],
    "vault": [
        "nota", "notas", "obsidian", "vault", "apunte", "conexion", "conexiones", "grafo",
    ],
    "video": [
        "video", "viral", "tiktok", "reel", "reels", "imagen", "avatar", "voz",
        "subtitulo", "subtitulos", "clip", "render", "youtube short",
    ],
    "social": [
        "publicar", "publicacion", "instagram", "facebook", "calendario de contenido",
        "tendencia", "tendencias", "nicho", "contenido",
    ],
    "design": [
        "diseno", "landing", "pagina web", "html", " ui ", "interfaz", "maqueta",
    ],
    "business": [
        "lead", "freelance", "seo", "ecommerce", "tienda online", "curso online",
        "reunion", "reputacion", "legal", "contrato", "cliente", "crm",
    ],
    "productivity": [
        "calendario", "email", "correo", "recordatorio", "recordame", "archivo",
        "pdf", "reunion",
    ],
    "code": [
        "codigo", "code", "github", "repo", "pull request", "bug", "funcion",
        "terminal", "comando", "script",
    ],
    "automation": [
        "tarea en background", "tarea programada", "cron", "programada", "spec",
    ],
    "reasoning": [
        "razona", "analiza a fondo", "mejorar prompt", "escribir novela",
        "framework", "estrategia", "pareto", "swot", "foda",
    ],
}


def _normalize(text: str) -> str:
    """minúsculas + sin acentos, para matching robusto."""
    decomposed = unicodedata.normalize("NFD", text.lower())
    return "".join(c for c in decomposed if unicodedata.category(c) != "Mn")


def _matched_categories(message: str) -> set[str]:
    normalized = f" {_normalize(message)} "
    matched = set()
    for category, keywords in CATEGORY_KEYWORDS.items():
        for kw in keywords:
            if _normalize(kw) in normalized or f" {_normalize(kw)}" in normalized:
                matched.add(category)
                break
    return matched


def select_relevant_schemas(message: str, all_schemas: list[dict]) -> list[dict]:
    """Devuelve solo los schemas relevantes al mensaje + el set core.

    Si no matchea ninguna categoría, devuelve todos los schemas (fallback
    seguro: nunca es peor que el comportamiento previo sin filtrar).
    """
    if not message or not message.strip():
        return all_schemas

    matched_categories = _matched_categories(message)
    if not matched_categories:
        return all_schemas

    allowed_names = set(CORE_TOOLS)
    for category in matched_categories:
        allowed_names |= TOOL_CATEGORIES.get(category, set())

    selected = [s for s in all_schemas if s.get("function", {}).get("name") in allowed_names]
    return selected or all_schemas
