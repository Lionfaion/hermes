"""
Rutina nocturna (3am Argentina): Hermes conversa con Gemini para aprender
cosas nuevas basadas en lo que el usuario preguntó, y corre auto-mejora.
"""
import logging
import sqlite3
import sys
import os
from datetime import datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

try:
    from dotenv import load_dotenv
    load_dotenv(Path(__file__).parent / ".env")
except ImportError:
    pass

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler(
            Path(__file__).parent.parent / "logs" / "nightly.log",
            encoding="utf-8",
        ),
    ],
)
logger = logging.getLogger("nightly")


# ── Helpers ─────────────────────────────────────────────────────────────────

def _chat(messages: list) -> str:
    from inference_client import chat_google
    return chat_google(messages)


def _get_recent_conversations(days: int = 7) -> str:
    """Lee conversaciones de los últimos N días."""
    from config import DB_PATH
    cutoff = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d")
    try:
        with sqlite3.connect(DB_PATH) as conn:
            cursor = conn.execute(
                """
                SELECT role, content, created_at
                FROM messages
                WHERE role IN ('user', 'assistant')
                  AND created_at >= ?
                ORDER BY created_at ASC
                LIMIT 120
                """,
                (cutoff,),
            )
            rows = cursor.fetchall()
    except Exception as e:
        logger.error("Error leyendo DB: %s", e)
        return ""

    if not rows:
        return ""

    lines = []
    for role, content, ts in rows:
        prefix = "Usuario" if role == "user" else "Hermes"
        short = content[:350] + "..." if len(content) > 350 else content
        lines.append(f"[{ts[:16]}] {prefix}: {short}")
    return "\n".join(lines)


def _notify_telegram(text: str) -> None:
    """Envía notificación al usuario vía Telegram."""
    import requests
    token = os.getenv("TELEGRAM_TOKEN", "")
    chat_id = os.getenv("TELEGRAM_CHAT_ID", "")
    if not token or not chat_id:
        logger.warning("TELEGRAM_TOKEN o TELEGRAM_CHAT_ID no configurados — sin notificación")
        return
    try:
        requests.post(
            f"https://api.telegram.org/bot{token}/sendMessage",
            json={"chat_id": chat_id, "text": text, "parse_mode": "Markdown"},
            timeout=10,
        )
    except Exception as e:
        logger.warning("No pude notificar por Telegram: %s", e)


def _save_to_vault(content: str, date_str: str) -> None:
    """Guarda el aprendizaje en el vault de Obsidian."""
    from config import VAULT_PATH
    try:
        note_dir = Path(VAULT_PATH) / "Hermes" / "Aprendizaje"
        note_dir.mkdir(parents=True, exist_ok=True)
        note = note_dir / f"{date_str}.md"
        note.write_text(content, encoding="utf-8")
        logger.info("Aprendizaje guardado: %s", note)
    except Exception as e:
        logger.error("Error guardando en vault: %s", e)


# ── Fases de la conversación nocturna ───────────────────────────────────────

def _identify_topics(conversations: str) -> list[str]:
    """Fase 1: Gemini identifica qué temas debería aprender Hermes."""
    logger.info("Fase 1: identificando temas a aprender...")

    system = (
        "Sos un mentor de IA. Hermes es un asistente personal en español argentino. "
        "Analizá las conversaciones recientes y respondé SOLO con una lista de 3 a 5 temas "
        "concretos que Hermes debería aprender para ser más útil a su usuario. "
        "Formato: un tema por línea, sin numeración, sin explicación, solo el tema breve."
    )

    if conversations:
        user_msg = (
            f"Conversaciones recientes de Hermes con su usuario (últimos 7 días):\n\n"
            f"{conversations}\n\n"
            "¿Qué 3-5 temas debería aprender Hermes para responder mejor mañana?"
        )
    else:
        user_msg = (
            "No hay conversaciones recientes. Sugerí 3 temas útiles para un asistente "
            "personal de un usuario argentino interesado en tecnología e inversiones."
        )

    response = _chat([
        {"role": "system", "content": system},
        {"role": "user", "content": user_msg},
    ])

    topics = [line.strip() for line in response.strip().split("\n") if line.strip()]
    topics = [t.lstrip("•-* ") for t in topics if len(t) > 3][:5]
    logger.info("Temas identificados: %s", topics)
    return topics


def _learn_topic(topic: str, conversation_context: str) -> dict:
    """Fase 2: Conversación de 3 turnos sobre un tema específico."""
    logger.info("Aprendiendo: %s", topic)

    system = (
        "Sos un experto que enseña a Hermes, un asistente de IA en español argentino. "
        "Respondé de forma concisa, práctica y aplicable. Máximo 300 palabras por respuesta."
    )

    # Turno 1: qué es el tema
    msgs = [
        {"role": "system", "content": system},
        {"role": "user", "content": f"Explicame '{topic}' de forma clara y práctica para que pueda aplicarlo con mi usuario."},
    ]
    turn1 = _chat(msgs)

    # Turno 2: aplicación práctica para el contexto del usuario
    msgs += [
        {"role": "assistant", "content": turn1},
        {"role": "user", "content": f"¿Cómo puedo usar este conocimiento sobre '{topic}' con un usuario argentino que usa IA para productividad e inversiones?"},
    ]
    turn2 = _chat(msgs)

    # Turno 3: resumen comprimido para el system prompt
    msgs += [
        {"role": "assistant", "content": turn2},
        {"role": "user", "content": f"Dame una regla de comportamiento de 1 sola línea sobre '{topic}' que pueda inyectar en mi system prompt."},
    ]
    turn3 = _chat(msgs)

    return {
        "topic": topic,
        "explicacion": turn1,
        "aplicacion": turn2,
        "regla": turn3.strip(),
    }


def _run_self_improvement() -> str:
    """Fase 3: Auto-mejora basada en conversaciones recientes."""
    logger.info("Fase 3: auto-mejora...")
    try:
        from self_improvement import run_self_improvement
        return run_self_improvement()
    except Exception as e:
        logger.error("Auto-mejora falló: %s", e)
        return f"Error en auto-mejora: {e}"


# ── Entrada principal ────────────────────────────────────────────────────────

def run_nightly_learning() -> str:
    """Ejecuta la rutina nocturna completa. Retorna resumen."""
    from config import GOOGLE_AI_API_KEY
    if not GOOGLE_AI_API_KEY:
        msg = "GOOGLE_AI_API_KEY no configurada — rutina nocturna cancelada."
        logger.error(msg)
        return msg

    date_str = datetime.now().strftime("%Y-%m-%d")
    hour_str = datetime.now().strftime("%H:%M")
    logger.info("=== Rutina nocturna iniciada: %s %s ===", date_str, hour_str)

    # Fase 1: obtener contexto y temas
    conversations = _get_recent_conversations(days=7)
    topics = _identify_topics(conversations)

    if not topics:
        logger.warning("No se identificaron temas — rutina abortada.")
        return "Sin temas para aprender."

    # Fase 2: aprender cada tema en conversación multi-turno
    learned = []
    for topic in topics:
        try:
            result = _learn_topic(topic, conversations)
            learned.append(result)
        except Exception as e:
            logger.error("Error aprendiendo '%s': %s", topic, e)

    # Fase 3: auto-mejora de comportamiento
    improvement = _run_self_improvement()

    # Armar nota para el vault
    lines = [
        f"# Aprendizaje nocturno — {date_str}",
        "",
        f"_Sesión de las {hour_str} — {len(learned)} temas aprendidos_",
        "",
    ]

    rules = []
    for item in learned:
        lines += [
            f"## {item['topic']}",
            "",
            "### Explicación",
            item["explicacion"],
            "",
            "### Aplicación con el usuario",
            item["aplicacion"],
            "",
            f"**Regla:** {item['regla']}",
            "",
        ]
        rules.append(item["regla"])

    lines += [
        "---",
        "",
        "## Auto-mejora de comportamiento",
        "",
        improvement,
    ]

    note_content = "\n".join(lines)
    _save_to_vault(note_content, date_str)

    # Resumen compacto para Telegram
    topics_list = "\n".join(f"• {item['topic']}" for item in learned)
    summary = (
        f"*Rutina nocturna completada* ({date_str} {hour_str})\n\n"
        f"Aprendí {len(learned)} temas nuevos:\n{topics_list}\n\n"
        f"Auto-mejora de comportamiento actualizada en vault."
    )
    _notify_telegram(summary)
    logger.info("=== Rutina nocturna completada ===")
    return summary


if __name__ == "__main__":
    result = run_nightly_learning()
    print(result)
