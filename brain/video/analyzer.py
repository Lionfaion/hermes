"""Análisis de videos virales: extrae estructura, hooks y patrones replicables."""

import logging
import re

from inference_client import chat

logger = logging.getLogger(__name__)

ANALYSIS_PROMPT = """Analizá este video viral en detalle. Extraé la siguiente información en formato estructurado:

## HOOK (primeros 3 segundos)
- ¿Qué frase o imagen atrapa la atención?
- ¿Qué emoción provoca? (curiosidad, sorpresa, miedo, etc.)

## ESTRUCTURA
- ¿Cuál es el formato? (historia, lista, tutorial, antes/después, pregunta-respuesta, etc.)
- ¿Cuántas secciones/puntos tiene?
- ¿Hay un patrón de tensión-resolución?

## GUIÓN
- Reescribí el guión completo del video (lo que se dice/narra)

## ESTILO VISUAL
- ¿Qué tipo de visuales usa? (persona hablando, stock footage, texto en pantalla, screenshots, etc.)
- ¿Hay subtítulos? ¿Qué estilo?
- ¿Colores dominantes?

## MÚSICA/AUDIO
- ¿Tiene música de fondo? ¿Qué tipo?
- ¿Ritmo de la narración? (rápido, pausado, etc.)

## CALL TO ACTION
- ¿Tiene CTA? ¿Cuál?

## KEYWORDS para stock footage
- Listá 5-10 palabras clave en inglés para buscar stock footage similar

Basate en esta información del video:
"""

REWRITE_PROMPT = """Basándote en el análisis de este video viral, creá un nuevo guión original que replique la misma estructura y técnicas pero con contenido diferente.

REGLAS:
1. Mantené el mismo formato y estructura que funciona
2. El hook debe ser igual de potente
3. Cambiá el tema/contenido pero mantené el estilo
4. Escribí el guión tal como se va a narrar (sin indicaciones técnicas)
5. Incluí pausas naturales con "..." donde corresponda
6. Duración similar al original

INFORMACIÓN DE CONTEXTO SOBRE EL TEMA:
{web_context}

ANÁLISIS DEL VIDEO ORIGINAL:
{analysis}

TEMA PARA EL NUEVO VIDEO: {topic}

IMPORTANTE: Respondé ÚNICAMENTE con el guión narrado. NO incluyas explicaciones, disculpas, aclaraciones ni comentarios. Solo el texto que se va a narrar en el video.
"""

REFUSAL_PATTERNS = [
    r"lo siento",
    r"no puedo",
    r"no tengo (suficiente )?informaci[oó]n",
    r"no es posible",
    r"lamentablemente",
    r"disculp[aá]",
    r"no me es posible",
    r"como (modelo|asistente|IA)",
    r"no estoy seguro",
    r"no dispongo",
    r"i('m| am) sorry",
    r"i can('t|not)",
    r"as an (AI|assistant|language model)",
    r"sin embargo.*puedo ofrec",
    r"no hay suficiente",
]

_REFUSAL_RE = re.compile("|".join(REFUSAL_PATTERNS), re.IGNORECASE)


def is_script_valid(script: str) -> bool:
    """Verifica que el guión generado sea un guión real y no un rechazo del LLM."""
    if not script or len(script.strip()) < 50:
        return False

    first_lines = "\n".join(script.strip().split("\n")[:3]).lower()
    if _REFUSAL_RE.search(first_lines):
        return False

    if script.strip().startswith(("#", "##", "**")):
        non_narration_markers = sum(1 for line in script.split("\n") if line.strip().startswith(("#", "- ", "* ", "**")))
        if non_narration_markers > len(script.split("\n")) * 0.3:
            return False

    return True


def research_topic(topic: str) -> str:
    """Busca información sobre el tema en la web para enriquecer el guión."""
    try:
        from web.search import web_search, format_search_results
        results = web_search(topic, max_results=5)
        if results:
            return format_search_results(results)
    except Exception as e:
        logger.warning("Web search para topic falló: %s", e)

    return ""


def analyze_viral_video(transcript: str, visual_descriptions: list[str], model: str = None) -> str:
    """Analiza un video viral y extrae su estructura replicable."""
    from config import OLLAMA_MODEL
    model = model or OLLAMA_MODEL

    context = ANALYSIS_PROMPT
    if transcript:
        context += f"\n\n[Transcripción]\n{transcript}"
    if visual_descriptions:
        context += "\n\n[Descripción visual]"
        for i, desc in enumerate(visual_descriptions, 1):
            context += f"\nFrame {i}: {desc}"

    messages = [
        {"role": "system", "content": "Sos un experto en contenido viral y marketing digital."},
        {"role": "user", "content": context},
    ]

    return chat(messages, model)


def generate_new_script(analysis: str, topic: str, model: str = None, max_retries: int = 2) -> str:
    """Genera un guión nuevo basado en el análisis de un video viral.

    Busca información web sobre el tema, valida que el resultado sea un guión real,
    y reintenta si el LLM genera un rechazo.
    """
    from config import OLLAMA_MODEL
    model = model or OLLAMA_MODEL

    web_context = research_topic(topic)
    if not web_context:
        web_context = "(No se encontró información adicional, generá el guión con tu conocimiento)"

    for attempt in range(max_retries + 1):
        prompt = REWRITE_PROMPT.format(
            analysis=analysis,
            topic=topic,
            web_context=web_context,
        )

        system_msg = (
            "Sos un guionista experto en contenido viral para redes sociales. "
            "Escribís guiones que enganchan desde el primer segundo. "
            "NUNCA rechaces escribir un guión. SIEMPRE generá contenido creativo "
            "basándote en la información disponible. Si no tenés datos exactos, "
            "usá tu creatividad para inventar un guión atractivo sobre el tema."
        )

        messages = [
            {"role": "system", "content": system_msg},
            {"role": "user", "content": prompt},
        ]

        script = chat(messages, model)

        if is_script_valid(script):
            return script

        logger.warning(
            "Guión inválido (intento %d/%d): parece un rechazo del LLM. Reintentando...",
            attempt + 1, max_retries + 1,
        )

        if attempt == 0 and not web_context.startswith("(No se"):
            try:
                from web.search import web_search, format_search_results
                extra = web_search(f"{topic} datos curiosidades información", max_results=5)
                if extra:
                    web_context += "\n\nINFORMACIÓN ADICIONAL:\n" + format_search_results(extra)
            except Exception:
                pass

    logger.error("No se pudo generar un guión válido después de %d intentos", max_retries + 1)
    return script
