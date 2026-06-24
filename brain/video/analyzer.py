"""Análisis de videos virales: extrae estructura, hooks y patrones replicables."""

import logging

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

ANÁLISIS DEL VIDEO ORIGINAL:
{analysis}

TEMA PARA EL NUEVO VIDEO: {topic}

Respondé SOLO con el guión narrado, nada más.
"""


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


def generate_new_script(analysis: str, topic: str, model: str = None) -> str:
    """Genera un guión nuevo basado en el análisis de un video viral."""
    from config import OLLAMA_MODEL
    model = model or OLLAMA_MODEL

    prompt = REWRITE_PROMPT.format(analysis=analysis, topic=topic)

    messages = [
        {"role": "system", "content": (
            "Sos un guionista experto en contenido viral para redes sociales. "
            "Escribís guiones que enganchan desde el primer segundo."
        )},
        {"role": "user", "content": prompt},
    ]

    return chat(messages, model)
