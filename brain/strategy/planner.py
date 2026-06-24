"""Motor de planificación estratégica: carga frameworks y los aplica a escenarios del usuario."""

import logging
from pathlib import Path

logger = logging.getLogger(__name__)

FRAMEWORKS_PATH = Path(__file__).parent / "frameworks.md"

FRAMEWORK_NAMES = {
    "pareto": "Principio de Pareto (80/20)",
    "foda": "Análisis FODA (SWOT)",
    "blue_ocean": "Blue Ocean Strategy",
    "eisenhower": "Matriz de Eisenhower",
    "customer_journey": "Customer Journey Mapping",
}

FRAMEWORK_TRIGGERS = {
    "pareto": ["priorizar", "80/20", "recursos", "inversión", "alto impacto", "qué eliminar"],
    "foda": ["fortalezas", "debilidades", "oportunidades", "amenazas", "swot", "foda", "lanzar", "evaluar"],
    "blue_ocean": ["diferenciar", "competencia", "océano azul", "innovar", "nuevo mercado", "blue ocean"],
    "eisenhower": ["urgente", "importante", "prioridad", "qué hacer primero", "tiempo", "delegar"],
    "customer_journey": ["conversión", "cliente", "experiencia", "journey", "funnel", "retención"],
}


def load_frameworks() -> str:
    try:
        return FRAMEWORKS_PATH.read_text(encoding="utf-8")
    except FileNotFoundError:
        logger.error("frameworks.md no encontrado en %s", FRAMEWORKS_PATH)
        return ""


def detect_frameworks(question: str) -> list[str]:
    q = question.lower()
    matches = []
    for fw, triggers in FRAMEWORK_TRIGGERS.items():
        if any(t in q for t in triggers):
            matches.append(fw)
    return matches or ["foda", "pareto"]


def build_analysis_prompt(question: str, context: str = "", frameworks: list[str] | None = None) -> str:
    if frameworks is None:
        frameworks = detect_frameworks(question)

    fw_names = [FRAMEWORK_NAMES.get(f, f) for f in frameworks]
    frameworks_doc = load_frameworks()

    prompt = (
        "Sos un estratega de negocios experto. Analizá la siguiente situación "
        f"usando los frameworks: {', '.join(fw_names)}.\n\n"
        "## Frameworks de referencia\n"
        f"{frameworks_doc}\n\n"
        f"## Pregunta/Situación\n{question}\n"
    )
    if context:
        prompt += f"\n## Contexto adicional\n{context}\n"

    prompt += (
        "\n## Instrucciones\n"
        "1. Aplicá cada framework seleccionado al caso concreto\n"
        "2. Dá conclusiones accionables y específicas\n"
        "3. Priorizá las recomendaciones por impacto\n"
        "4. Sé directo y práctico, no teórico\n"
    )
    return prompt


def get_framework_guide(decision_type: str) -> str:
    guides = {
        "priorización": "Pareto (80/20) + Eisenhower: identificá el 20% de mayor impacto y priorizá por urgencia/importancia.",
        "mercado": "FODA + Blue Ocean: evaluá posición actual y buscá espacios sin competencia.",
        "conversión": "Customer Journey: mapeá cada etapa y optimizá los puntos de fricción.",
        "oportunidad": "FODA + Pareto: evaluá fortalezas/amenazas y enfocá en alto impacto.",
        "producto": "Blue Ocean + Customer Journey: diferenciá y validá que mejora la experiencia.",
        "tiempo": "Eisenhower + Pareto: priorizá lo importante y eliminá lo trivial.",
    }
    dt = decision_type.lower()
    for key, guide in guides.items():
        if key in dt:
            return guide
    return "Usá FODA para contexto general, luego Pareto para identificar alto impacto, y Eisenhower para priorizar ejecución."
