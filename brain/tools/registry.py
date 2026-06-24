"""Registro central de herramientas. Recolecta schemas y despacha ejecuciones."""

import logging
from tools.base import BaseTool

logger = logging.getLogger(__name__)


class ToolRegistry:
    def __init__(self):
        self._tools: dict[str, BaseTool] = {}

    def register(self, tool: BaseTool):
        self._tools[tool.name] = tool
        logger.info("Tool registrada: %s", tool.name)

    def get(self, name: str) -> BaseTool | None:
        return self._tools.get(name)

    def get_schemas(self) -> list[dict]:
        return [t.to_ollama_schema() for t in self._tools.values()]

    def execute(self, name: str, arguments: dict) -> str:
        tool = self._tools.get(name)
        if not tool:
            return f"[Error: herramienta '{name}' no encontrada]"
        try:
            logger.info("Ejecutando tool '%s' con args: %s", name, arguments)
            return tool.execute(**arguments)
        except Exception as e:
            logger.error("Tool '%s' falló: %s", name, e)
            return f"[Error ejecutando {name}: {e}]"

    def list_tools(self) -> list[str]:
        return list(self._tools.keys())
