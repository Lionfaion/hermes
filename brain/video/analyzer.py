"""Análisis de videos virales: extrae estructura, hooks y patrones replicables."""

import logging
import re

from inference_client import chat

logger = logging.getLogger(__name__)


def sanitize_script(text: str) -> str:
    """Elimina artefactos de formato que el TTS leería literalmente."""
    # Encabezados markdown: ## Intro → vacío
    text = re.sub(r'^#{1,6}\s+.*$', '', text, flags=re.MULTILINE)
    # Negrita/cursiva: **texto** → texto
    text = re.sub(r'\*{1,3}([^*\n]+)\*{1,3}', r'\1', text)
    # Etiquetas entre corchetes: [Intro], [Espacio], [Sección 1] → vacío
    text = re.sub(r'\[[^\]]{1,30}\]', '', text)
    # Indicaciones entre paréntesis cortas: (pausa), (música), (efecto) → vacío
    text = re.sub(r'\([^)]{1,25}\)', '', text)
    # Líneas que son solo guiones/puntos separadores
    text = re.sub(r'^[-–—=*_]{2,}\s*$', '', text, flags=re.MULTILINE)
    # Colapsar múltiples líneas vacías en una sola
    text = re.sub(r'\n{3,}', '\n\n', text)
    # Limpiar espacios sobrantes al inicio de cada línea
    lines = [line.strip() for line in text.splitlines()]
    text = '\n'.join(line for line in lines if line)
    return text.strip()

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

REGLAS ABSOLUTAS — VIOLACIONES ARRUINAN EL AUDIO:
1. Respondé ÚNICAMENTE con el texto que se va a narrar en voz alta, palabra por palabra
2. PROHIBIDO usar corchetes: NO [Intro], NO [Espacio], NO [Hook], NO [Sección], NO [CTA], NO [Outro]
3. PROHIBIDO usar Markdown: NO #, NO ##, NO **, NO *, NO __
4. PROHIBIDO escribir indicaciones técnicas, nombres de sección o cualquier texto que no sea narración pura
5. Las pausas van con "..." únicamente, nada más
6. El guión debe poder leerse de corrido sin que suene raro

REGLAS DE CONTENIDO:
- Mantené el mismo formato y estructura que funciona
- El hook debe ser igual de potente en los primeros 3 segundos
- Cambiá el tema/contenido pero mantené el estilo y ritmo
- Duración similar al original

ANÁLISIS DEL VIDEO ORIGINAL:
{analysis}

TEMA PARA EL NUEVO VIDEO: {topic}

RECORDATORIO FINAL: solo texto narrado, sin corchetes, sin markdown, sin etiquetas.
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
            "Escribís guiones que enganchan desde el primer segundo. "
            "Escribís SOLO el texto narrado, sin corchetes, sin markdown, sin etiquetas."
        )},
        {"role": "user", "content": prompt},
    ]

    raw = chat(messages, model)
    return sanitize_script(raw)
