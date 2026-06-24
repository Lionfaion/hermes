"""Herramientas de planificación estratégica para el LLM."""

from tools.base import BaseTool
from strategy.planner import (
    build_analysis_prompt,
    detect_frameworks,
    get_framework_guide,
    load_frameworks,
    FRAMEWORK_NAMES,
)
from inference_client import chat


class StrategicAnalysisTool(BaseTool):
    name = "strategic_analysis"
    description = (
        "Realiza un análisis estratégico aplicando frameworks (Pareto 80/20, FODA/SWOT, "
        "Blue Ocean, Eisenhower, Customer Journey) a una situación de negocio. "
        "Detecta automáticamente qué frameworks aplicar o podés especificarlos."
    )
    parameters = {
        "type": "object",
        "properties": {
            "question": {
                "type": "string",
                "description": "La situación o pregunta a analizar estratégicamente",
            },
            "context": {
                "type": "string",
                "description": "Contexto adicional (datos, industria, recursos disponibles)",
            },
            "frameworks": {
                "type": "string",
                "description": "Frameworks a usar separados por coma (pareto, foda, blue_ocean, eisenhower, customer_journey). Si no se especifica, se detectan automáticamente.",
            },
        },
        "required": ["question"],
    }

    def execute(self, question: str, context: str = "", frameworks: str = "") -> str:
        fw_list = [f.strip() for f in frameworks.split(",") if f.strip()] if frameworks else None
        if fw_list:
            invalid = [f for f in fw_list if f not in FRAMEWORK_NAMES]
            if invalid:
                available = ", ".join(FRAMEWORK_NAMES.keys())
                return f"Frameworks no válidos: {', '.join(invalid)}. Disponibles: {available}"

        prompt = build_analysis_prompt(question, context, fw_list)
        messages = [
            {"role": "system", "content": "Sos un consultor estratégico experto. Respondé en español."},
            {"role": "user", "content": prompt},
        ]
        return chat(messages)


class FrameworkGuideTool(BaseTool):
    name = "framework_guide"
    description = (
        "Recomienda qué framework estratégico usar según el tipo de decisión. "
        "Tipos: priorización, mercado, conversión, oportunidad, producto, tiempo."
    )
    parameters = {
        "type": "object",
        "properties": {
            "decision_type": {
                "type": "string",
                "description": "Tipo de decisión (priorización, mercado, conversión, oportunidad, producto, tiempo)",
            },
        },
        "required": ["decision_type"],
    }

    def execute(self, decision_type: str) -> str:
        guide = get_framework_guide(decision_type)
        detected = detect_frameworks(decision_type)
        fw_names = [FRAMEWORK_NAMES[f] for f in detected if f in FRAMEWORK_NAMES]
        return (
            f"**Recomendación para '{decision_type}':**\n{guide}\n\n"
            f"**Frameworks sugeridos:** {', '.join(fw_names)}\n\n"
            "Usá la herramienta `strategic_analysis` para aplicar estos frameworks a tu caso concreto."
        )
