"""Plantillas de guiones probadas por nicho para videos virales."""

SCRIPT_TEMPLATES = {
    "hook_story_cta": {
        "name": "Hook → Story → CTA",
        "description": "Estructura viral clásica: gancho impactante, desarrollo, llamada a acción",
        "template": (
            "HOOK (primeros 3 segundos - lo más impactante):\n"
            "{hook}\n\n"
            "DESARROLLO (30-50 segundos):\n"
            "{body}\n\n"
            "CTA (últimos 5 segundos):\n"
            "{cta}"
        ),
        "best_for": ["shorts", "reels", "tiktok"],
    },
    "listicle": {
        "name": "Listicle (Top X)",
        "description": "Lista de X cosas con intro y cierre",
        "template": (
            "INTRO: {hook}\n\n"
            "LISTA:\n"
            "{items}\n\n"
            "CIERRE: {cta}"
        ),
        "best_for": ["youtube", "shorts", "tiktok"],
    },
    "storytelling": {
        "name": "Storytelling",
        "description": "Historia con tensión narrativa",
        "template": (
            "SETUP: {setup}\n\n"
            "CONFLICTO: {conflict}\n\n"
            "RESOLUCIÓN: {resolution}\n\n"
            "LECCIÓN: {lesson}"
        ),
        "best_for": ["youtube", "reels"],
    },
    "educational": {
        "name": "Educativo (Problema → Solución)",
        "description": "Identifica un problema y da la solución",
        "template": (
            "PROBLEMA: {problem}\n\n"
            "POR QUÉ IMPORTA: {why}\n\n"
            "SOLUCIÓN: {solution}\n\n"
            "RESUMEN: {summary}"
        ),
        "best_for": ["youtube", "shorts", "tiktok", "reels"],
    },
    "curiosity": {
        "name": "Datos Curiosos / Misterio",
        "description": "Datos impactantes que generan curiosidad",
        "template": (
            "DATO IMPACTANTE: {shocking_fact}\n\n"
            "CONTEXTO: {context}\n\n"
            "EXPLICACIÓN: {explanation}\n\n"
            "DATO EXTRA: {bonus}"
        ),
        "best_for": ["shorts", "tiktok", "reels"],
    },
    "before_after": {
        "name": "Antes vs Después",
        "description": "Transformación o comparación dramática",
        "template": (
            "ANTES: {before}\n\n"
            "EL CAMBIO: {transition}\n\n"
            "DESPUÉS: {after}\n\n"
            "CÓMO HACERLO: {how}"
        ),
        "best_for": ["reels", "tiktok", "youtube"],
    },
}

NICHE_CONFIGS = {
    "finanzas": {
        "topics": [
            "ahorro e inversión", "errores financieros comunes", "ingresos pasivos",
            "criptomonedas", "impuestos", "presupuesto personal", "deudas",
            "independencia financiera", "negocios online", "mentalidad de dinero",
        ],
        "hooks": [
            "El 90% de la gente pierde dinero por esto...",
            "Si ganas menos de $X al mes, necesitas saber esto",
            "Este truco me ahorró $X en un año",
            "Los ricos hacen esto y nadie te lo dice",
            "Nunca hagas esto con tu dinero",
        ],
        "style": "directo, con datos, urgencia",
        "best_templates": ["hook_story_cta", "listicle", "educational"],
        "hashtags": ["finanzas", "dinero", "inversiones", "ahorro", "libertadfinanciera"],
    },
    "tecnologia": {
        "topics": [
            "inteligencia artificial", "gadgets", "apps útiles", "programación",
            "ciberseguridad", "futuro de la tecnología", "automatización",
            "herramientas de productividad", "novedades tech", "tutoriales",
        ],
        "hooks": [
            "Esta IA puede hacer lo que tardabas horas en minutos",
            "La app que nadie conoce pero todos necesitan",
            "En 5 años esto va a cambiar todo",
            "Probé la nueva IA de X y esto pasó",
            "3 herramientas gratis que valen oro",
        ],
        "style": "entusiasta, demos visuales, asombro",
        "best_templates": ["hook_story_cta", "listicle", "before_after"],
        "hashtags": ["tech", "ia", "tecnologia", "apps", "futuro"],
    },
    "curiosidades": {
        "topics": [
            "datos históricos impactantes", "ciencia fascinante", "records mundiales",
            "misterios sin resolver", "datos psicológicos", "naturaleza extrema",
            "coincidencias increíbles", "inventos accidentales", "culturas del mundo",
        ],
        "hooks": [
            "Esto no te lo enseñaron en la escuela...",
            "El 99% de la gente no sabe esto",
            "Lo que pasó en este lugar te va a volar la cabeza",
            "Este dato va a cambiar cómo ves el mundo",
            "La historia más loca que vas a escuchar hoy",
        ],
        "style": "narrativo, suspenso, revelaciones",
        "best_templates": ["curiosity", "storytelling", "listicle"],
        "hashtags": ["curiosidades", "datoscuriosos", "sabiasque", "increible", "viral"],
    },
    "motivacion": {
        "topics": [
            "mentalidad de éxito", "hábitos de personas exitosas", "superar obstáculos",
            "disciplina", "emprendimiento", "productividad", "metas",
            "historias de éxito", "mindset", "rutinas matutinas",
        ],
        "hooks": [
            "Empecé desde cero y esto fue lo que aprendí",
            "Si estás pensando en rendirte, escuchá esto",
            "El hábito que me cambió la vida en 30 días",
            "Los exitosos hacen esto cada mañana",
            "Tu mayor enemigo sos vos mismo, y acá te explico por qué",
        ],
        "style": "emocional, directo, inspirador",
        "best_templates": ["hook_story_cta", "storytelling", "before_after"],
        "hashtags": ["motivacion", "exito", "mentalidad", "emprendedor", "habitos"],
    },
    "salud": {
        "topics": [
            "nutrición", "ejercicio en casa", "hábitos saludables", "dormir mejor",
            "salud mental", "alimentos que dañan", "remedios naturales",
            "bienestar", "ayuno intermitente", "suplementos",
        ],
        "hooks": [
            "Dejá de comer esto ya, tu cuerpo te lo agradece",
            "Este hábito destruye tu salud y lo hacés todos los días",
            "3 alimentos que parecen sanos pero no lo son",
            "Dormí mejor con este truco simple",
            "Lo que los médicos no te dicen sobre X",
        ],
        "style": "alarmante pero informativo, con evidencia",
        "best_templates": ["educational", "listicle", "hook_story_cta"],
        "hashtags": ["salud", "bienestar", "nutricion", "vidasana", "fitness"],
    },
}


def get_template(template_id: str) -> dict | None:
    return SCRIPT_TEMPLATES.get(template_id)


def get_niche_config(niche: str) -> dict | None:
    return NICHE_CONFIGS.get(niche)


def list_templates() -> list[str]:
    return list(SCRIPT_TEMPLATES.keys())


def list_available_niches() -> list[str]:
    return list(NICHE_CONFIGS.keys())


def build_generation_prompt(niche: str, template_id: str = "", topic: str = "") -> str:
    niche_cfg = NICHE_CONFIGS.get(niche, {})
    if not niche_cfg:
        return f"Generá un guión de video corto sobre: {topic or niche}"

    if not template_id:
        template_id = niche_cfg.get("best_templates", ["hook_story_cta"])[0]

    template = SCRIPT_TEMPLATES.get(template_id, SCRIPT_TEMPLATES["hook_story_cta"])
    topic_str = topic or "un tema de " + niche

    return (
        f"Generá un guión de video corto (30-60 segundos) para el nicho de **{niche}**.\n\n"
        f"**Tema:** {topic_str}\n"
        f"**Estilo:** {niche_cfg.get('style', 'directo')}\n"
        f"**Estructura:** {template['name']}\n"
        f"**Formato:**\n{template['template']}\n\n"
        f"**Ejemplos de hooks que funcionan:**\n"
        + "\n".join(f"- {h}" for h in niche_cfg.get("hooks", [])[:3])
        + "\n\n"
        "**Instrucciones:**\n"
        "- El hook DEBE captar atención en 3 segundos\n"
        "- Lenguaje simple y directo\n"
        "- Incluí datos o ejemplos concretos\n"
        "- El CTA debe generar interacción (comentar, compartir, seguir)\n"
        "- Optimizado para retención (que no se vayan del video)\n"
    )
