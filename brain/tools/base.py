"""Base abstracta para todas las herramientas de Hermes."""

from abc import ABC, abstractmethod


class BaseTool(ABC):
    name: str = ""
    description: str = ""
    parameters: dict = {}

    @abstractmethod
    def execute(self, **kwargs) -> str:
        """Ejecuta la herramienta y retorna un string para el LLM."""

    def to_ollama_schema(self) -> dict:
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": self.parameters,
            },
        }
