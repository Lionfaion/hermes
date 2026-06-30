"""Auto-mejora: Hermes analiza sus conversaciones y propone mejoras de comportamiento."""
import logging
import sqlite3
from datetime import datetime
from pathlib import Path

logger = logging.getLogger(__name__)

_META_COACH_PROMPT = """Sos un coach especializado en mejorar asistentes de IA conversacionales.
Analizá las siguientes conversaciones reales de Hermes (asistente personal en español argentino).

Tu tarea:
1. Identificá qué cosas pide el usuario frecuentemente
2. Detectá respuestas de Hermes que podrían ser mejores (incompletas, genéricas, lentas de entender)
3. Sugerí comportamientos concretos que Hermes debería adoptar

Devolvé SOLO el análisis en este formato:

## Lo que el usuario valora
- [punto breve]

## Comportamientos a mejorar
- [punto breve]

## Nuevas reglas de comportamiento
- [instrucción concreta para el system prompt]

Sé conciso. Máximo 300 palabras. No agregues intro ni cierre."""


def _get_recent_conversations(limit: int = 80) -> str:
    """Lee las últimas N interacciones de todos los usuarios."""
    from config import DB_PATH
    try:
        with sqlite3.connect(DB_PATH) as conn:
            cursor = conn.execute(
                """
                SELECT role, content, created_at
                FROM messages
                WHERE role IN ('user', 'assistant')
                ORDER BY created_at DESC
                LIMIT ?
                """,
                (limit,),
            )
            rows = cursor.fetchall()
    except Exception as e:
        logger.error("Error leyendo conversaciones: %s", e)
        return ""

    if not rows:
        return ""

    rows = list(reversed(rows))
    lines = []
    for role, content, created_at in rows:
        prefix = "Usuario" if role == "user" else "Hermes"
        short = content[:400] + "..." if len(content) > 400 else content
        lines.append(f"[{created_at}] {prefix}: {short}")

    return "\n".join(lines)


def run_self_improvement() -> str:
    """
    Analiza las conversaciones recientes usando Gemini y guarda las mejoras en el vault.
    Retorna el texto de las mejoras generadas.
    """
    from config import GOOGLE_AI_API_KEY, VAULT_PATH

    if not GOOGLE_AI_API_KEY:
        return "GOOGLE_AI_API_KEY no configurada. Necesito acceso a Gemini para auto-mejora."

    conversations = _get_recent_conversations(limit=80)
    if not conversations:
        return "No hay conversaciones suficientes para analizar todavía."

    from inference_client import chat
    messages = [
        {"role": "system", "content": _META_COACH_PROMPT},
        {
            "role": "user",
            "content": f"Conversaciones recientes:\n\n{conversations}",
        },
    ]

    logger.info("Ejecutando auto-mejora...")
    try:
        result = chat(messages)
    except Exception as e:
        logger.error("Auto-mejora falló: %s", e)
        return f"Error en auto-mejora: {e}"

    _save_to_vault(result)
    return result


def _save_to_vault(content: str) -> None:
    """Guarda las mejoras en el vault de Obsidian."""
    from config import VAULT_PATH
    try:
        vault = Path(VAULT_PATH)
        note = vault / "Hermes" / "Mejoras.md"
        note.parent.mkdir(parents=True, exist_ok=True)
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M")
        note.write_text(
            f"# Auto-mejoras de Hermes\n\n_Última actualización: {timestamp}_\n\n{content}",
            encoding="utf-8",
        )
        logger.info("Mejoras guardadas en vault: %s", note)
    except Exception as e:
        logger.error("Error guardando mejoras en vault: %s", e)


def load_improvements() -> str:
    """Lee las mejoras guardadas del vault para inyectar en el system prompt."""
    from config import VAULT_PATH
    try:
        note = Path(VAULT_PATH) / "Hermes" / "Mejoras.md"
        if not note.exists():
            return ""
        content = note.read_text(encoding="utf-8", errors="ignore").strip()
        # Extraer solo las secciones de reglas (saltar header y timestamp)
        lines = content.split("\n")
        rule_lines = [l for l in lines if l.startswith("## ") or l.startswith("- ")]
        return "\n".join(rule_lines) if rule_lines else ""
    except Exception as e:
        logger.debug("Error cargando mejoras: %s", e)
        return ""
