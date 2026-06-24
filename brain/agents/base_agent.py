"""Agente base: un LLM especializado con su propio system prompt y herramientas."""

import logging
from dataclasses import dataclass, field

from inference_client import chat_with_tools
from tools.registry import ToolRegistry

logger = logging.getLogger(__name__)

TOOL_MAX_ITERATIONS = 5


@dataclass
class AgentProfile:
    name: str
    system_prompt: str
    model: str
    tool_names: list[str] = field(default_factory=list)


class BaseAgent:
    def __init__(self, profile: AgentProfile, registry: ToolRegistry):
        self.profile = profile
        self.registry = registry

    def _get_allowed_schemas(self) -> list[dict]:
        """Retorna solo los schemas de las tools que este agente puede usar."""
        all_schemas = self.registry.get_schemas()
        if not self.profile.tool_names:
            return all_schemas
        return [
            s for s in all_schemas
            if s["function"]["name"] in self.profile.tool_names
        ]

    def run(self, task: str, context: str = "") -> str:
        """Ejecuta una tarea con el agente, incluyendo loop de tool calling."""
        messages = [{"role": "system", "content": self.profile.system_prompt}]

        if context:
            messages.append({"role": "system", "content": f"[Contexto]\n{context}"})

        messages.append({"role": "user", "content": task})

        schemas = self._get_allowed_schemas()

        for iteration in range(TOOL_MAX_ITERATIONS):
            response = chat_with_tools(messages, schemas, self.profile.model)

            tool_calls = response.get("tool_calls")
            if not tool_calls:
                return response.get("content", "")

            messages.append(response)

            for tc in tool_calls:
                func = tc.get("function", {})
                name = func.get("name", "")
                args = func.get("arguments", {})

                logger.info("[%s] Tool call: %s(%s)", self.profile.name, name, args)

                if name not in self.profile.tool_names and self.profile.tool_names:
                    result = f"[Agente {self.profile.name} no tiene acceso a '{name}']"
                else:
                    result = self.registry.execute(name, args)

                messages.append({"role": "tool", "content": result})

        return response.get("content", "[Límite de iteraciones alcanzado]")
