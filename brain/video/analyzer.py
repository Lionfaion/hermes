"""Análisis de videos virales: extrae estructura, hooks y patrones replicables."""

import logging
import re

from inference_client import (
    chat, is_online as _ollama_online,
    is_groq_available, chat_groq,
    GOOGLE_AI_API_KEY,
)

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
- DURACIÓN OBJETIVO: {target_words} palabras aproximadamente (para un video de ~{target_secs:.0f} segundos)
- Mínimo 150 palabras siempre, aunque el video original sea más corto

INFORMACIÓN DE CONTEXTO SOBRE EL TEMA:
{web_context}

ANÁLISIS DEL VIDEO ORIGINAL:
{analysis}

TEMA PARA EL NUEVO VIDEO: {topic}

RECORDATORIO FINAL: solo texto narrado, sin corchetes, sin markdown, sin etiquetas. NO incluyas explicaciones ni aclaraciones. Solo el texto que se va a narrar en el video.
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


def _video_chat(messages: list, model: str) -> str:
    """Llama al LLM disponible: Ollama → Google AI → Groq (último recurso).

    El pipeline de video genera prompts largos. Preferimos Gemini sobre Groq
    para no agotar el TPM de Groq que se necesita para las tool dispatch calls.
    """
    if _ollama_online():
        return chat(messages, model)
    if is_groq_available():
        # Último recurso: Groq con truncado para evitar 413/429
        trimmed = []
        for m in messages:
            if m.get("role") == "user" and len(m.get("content", "")) > 6000:
                m = dict(m)
                m["content"] = m["content"][:6000] + "\n[...truncado]"
            trimmed.append(m)
        return chat_groq(trimmed)
    raise RuntimeError("Sin proveedor de IA disponible para el pipeline de video")


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


def infer_topic(analysis: str, transcript: str = "") -> str:
    """Infiere el tema del video desde el análisis o la transcripción cuando no se especificó."""
    _instruction_re = re.compile(
        r'palabras?\s+clave|stock\s+footage|buscar|listá?|listar|similares?|imágenes?',
        re.IGNORECASE,
    )

    # Extraer keywords del análisis estructurado, filtrando líneas de instrucción
    kw_match = re.search(r'##\s*KEYWORDS[^\n]*\n(.*?)(?=\n##|\Z)', analysis, re.DOTALL | re.IGNORECASE)
    if kw_match:
        section = kw_match.group(1).strip()
        actual_keywords = []
        for line in section.splitlines():
            line = line.strip()
            if not line or _instruction_re.search(line):
                continue
            clean = re.sub(r'^[\d\.\-\*\s]+|\*+', '', line).strip()
            if clean:
                actual_keywords.append(clean)
        if actual_keywords:
            return " ".join(actual_keywords[:3])[:200]

    # Extraer tema del hook
    hook_match = re.search(r'##\s*HOOK[^\n]*\n(.*?)(?=\n##|\Z)', analysis, re.DOTALL | re.IGNORECASE)
    if hook_match:
        hook = hook_match.group(1).strip()
        if hook and not _instruction_re.search(hook.splitlines()[0] if hook.splitlines() else hook):
            return hook[:200]

    # Fallback: primeras palabras del transcript
    if transcript:
        words = transcript.strip().split()[:20]
        return " ".join(words)

    return "contenido similar al video original"


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

    return _video_chat(messages, model)


def generate_new_script(
    analysis: str,
    topic: str,
    model: str = None,
    max_retries: int = 2,
    original_duration_secs: float = 0.0,
) -> str:
    """Genera un guión nuevo basado en el análisis de un video viral.

    Busca información web sobre el tema, valida que el resultado sea un guión real,
    y reintenta si el LLM genera un rechazo.
    """
    from config import OLLAMA_MODEL
    model = model or OLLAMA_MODEL

    web_context = research_topic(topic)
    if not web_context:
        web_context = "(No se encontró información adicional, generá el guión con tu conocimiento)"

    # Estimar palabras objetivo: ~2.5 palabras/segundo para narración en español
    # Mínimo 150 palabras (~60s) para que el video tenga sustancia
    target_words = max(150, int(original_duration_secs * 2.5)) if original_duration_secs > 0 else 150
    target_secs = max(60.0, original_duration_secs)

    for attempt in range(max_retries + 1):
        prompt = REWRITE_PROMPT.format(
            analysis=analysis,
            topic=topic,
            web_context=web_context,
            target_words=target_words,
            target_secs=target_secs,
        )

        system_msg = (
            "Sos un guionista experto en contenido viral para redes sociales. "
            "Escribís guiones que enganchan desde el primer segundo. "
            "NUNCA rechaces escribir un guión. SIEMPRE generá contenido creativo "
            "basándote en la información disponible. Si no tenés datos exactos, "
            "usá tu creatividad para inventar un guión atractivo sobre el tema. "
            "Escribís SOLO texto narrado, sin corchetes, sin markdown, sin etiquetas."
        )

        messages = [
            {"role": "system", "content": system_msg},
            {"role": "user", "content": prompt},
        ]

        script = _video_chat(messages, model)

        if is_script_valid(script):
            return sanitize_script(script)

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
    return sanitize_script(script)
