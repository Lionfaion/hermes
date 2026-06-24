#!/usr/bin/env python3
"""
Meta-agente de reflexión nocturna.
Lee los chats del día → extrae lecciones → actualiza skills.yaml.
Ejecutar como tarea programada (ej: 3:00 AM).
"""
import json
import logging
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from learning.logger import InteractionLogger
from learning.skills_manager import SkillsManager
from inference_client import chat, is_online
from config import OLLAMA_MODEL

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("hermes.reflexion")

META_PROMPT = """Eres un analizador crítico especializado en mejorar asistentes de IA.
Analiza las siguientes conversaciones del día de forma objetiva y rigurosa.

Tu tarea:
1. Detecta ERRORES del asistente (información incorrecta, malentendidos, respuestas incompletas)
2. Identifica PREFERENCIAS del usuario (qué pidió explícita o implícitamente, su estilo, sus intereses)
3. Extrae REGLAS de mejora concretas para futuras conversaciones

Responde ÚNICAMENTE con un JSON válido, sin texto extra, con esta estructura:
{
  "lecciones": [
    {"categoria": "preferencias", "texto": "Al usuario le gusta X"},
    {"categoria": "reglas", "texto": "Siempre hacer Y cuando Z"},
    {"categoria": "errores_conocidos", "texto": "Nunca asumir X sin preguntar"}
  ]
}

Reglas estrictas:
- Máximo 5 lecciones por análisis
- Cada lección: UNA sola frase, máximo 20 palabras
- Si no hay nada relevante: {"lecciones": []}
- No inventes lecciones si no hay evidencia en los logs"""


def format_logs(logs: list) -> str:
    if not logs:
        return "Sin conversaciones registradas hoy."
    parts = []
    for e in logs[-60:]:  # últimos 60 mensajes
        role = "USUARIO" if e["role"] == "user" else "HERMES"
        corrected = " ⚠️CORREGIDO" if e.get("corrected") else ""
        parts.append(f"{role}{corrected}: {e['content'][:250]}")
    return "\n".join(parts)


def extract_json(text: str) -> dict:
    match = re.search(r"\{.*\}", text, re.DOTALL)
    if match:
        return json.loads(match.group())
    raise ValueError("No JSON found in response")


def run():
    logger.info("=== Reflexión nocturna iniciada ===")

    if not is_online():
        logger.warning("GPU node offline. Cancelando reflexión.")
        return

    ilog = InteractionLogger()
    skills = SkillsManager()

    logs = ilog.get_today()
    logger.info("Interacciones del día: %d", len(logs))

    if len(logs) < 4:
        logger.info("Pocas interacciones hoy. Reflexión omitida.")
        return

    messages = [
        {"role": "system", "content": META_PROMPT},
        {"role": "user", "content": f"Analiza estas conversaciones:\n\n{format_logs(logs)}"},
    ]

    try:
        response = chat(messages, OLLAMA_MODEL)
        result = extract_json(response)
        lessons = result.get("lecciones", [])

        if lessons:
            skills.add_lessons(lessons)
            logger.info("Aprendidas %d lecciones:", len(lessons))
            for l in lessons:
                logger.info("  [%s] %s", l.get("categoria", "?"), l.get("texto", ""))
        else:
            logger.info("No hay lecciones nuevas hoy.")

    except json.JSONDecodeError as e:
        logger.error("JSON inválido en respuesta: %s", e)
    except Exception as e:
        logger.error("Error en reflexión: %s", e)

    logger.info("=== Reflexión completada ===")


if __name__ == "__main__":
    run()
