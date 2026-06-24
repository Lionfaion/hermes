"""Orquestador de agentes: el LLM principal delega tareas a agentes especializados."""

import logging

from tools.base import BaseTool
from tools.registry import ToolRegistry
from agents.base_agent import BaseAgent
from agents.profiles import AGENT_PROFILES

logger = logging.getLogger(__name__)


class DelegateToAgentTool(BaseTool):
    name = "delegate_to_agent"
    description = (
        "Delega una tarea a un agente especializado. Agentes disponibles:\n"
        "- researcher: Investiga temas buscando en internet y notas personales\n"
        "- coder: Programación, código, comandos del sistema\n"
        "- analyst: Análisis de datos y documentos\n"
        "- media_specialist: Análisis de videos, audios e imágenes\n"
        "- designer: Diseño web, landing pages, UI/UX con Google Stitch\n"
        "- strategist: Planificación estratégica, análisis de negocio (FODA, Pareto, Blue Ocean, Eisenhower, Customer Journey)\n"
        "- social_media: Publicación en redes sociales, calendarios de contenido, omnipresencia digital\n"
        "Úsala cuando la tarea requiera trabajo profundo de un especialista."
    )
    parameters = {
        "type": "object",
        "properties": {
            "agent": {
                "type": "string",
                "description": "Nombre del agente (researcher, coder, analyst, media_specialist)",
                "enum": list(AGENT_PROFILES.keys()),
            },
            "task": {
                "type": "string",
                "description": "Descripción detallada de la tarea para el agente",
            },
            "context": {
                "type": "string",
                "description": "Contexto adicional relevante para la tarea (opcional)",
            },
        },
        "required": ["agent", "task"],
    }

    def __init__(self, registry: ToolRegistry):
        self._registry = registry
        self._agents: dict[str, BaseAgent] = {}

    def _get_agent(self, name: str) -> BaseAgent | None:
        if name not in AGENT_PROFILES:
            return None
        if name not in self._agents:
            self._agents[name] = BaseAgent(AGENT_PROFILES[name], self._registry)
        return self._agents[name]

    def execute(self, agent: str, task: str, context: str = "") -> str:
        agent_instance = self._get_agent(agent)
        if not agent_instance:
            available = ", ".join(AGENT_PROFILES.keys())
            return f"Agente '{agent}' no encontrado. Disponibles: {available}"

        logger.info("Delegando a agente '%s': %s", agent, task[:100])
        try:
            return agent_instance.run(task, context)
        except Exception as e:
            logger.error("Agente '%s' falló: %s", agent, e)
            return f"[Error del agente {agent}: {e}]"
