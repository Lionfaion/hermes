"""Herramienta del Director: orquesta múltiples agentes para tareas complejas."""

from tools.base import BaseTool


class DirectorTool(BaseTool):
    name = "delegate_to_director"
    description = (
        "Delega una tarea compleja al Director, que la descompone en subtareas "
        "y coordina múltiples agentes especializados para resolverla. "
        "Úsala para tareas que requieren investigación + análisis + código, "
        "o cualquier trabajo que necesite más de un agente."
    )
    parameters = {
        "type": "object",
        "properties": {
            "task": {
                "type": "string",
                "description": "Descripción completa de la tarea compleja",
            },
            "context": {
                "type": "string",
                "description": "Contexto adicional relevante (opcional)",
            },
            "background": {
                "type": "boolean",
                "description": "Si es true, ejecuta en segundo plano (default false)",
            },
        },
        "required": ["task"],
    }

    def __init__(self, registry=None):
        self._registry = registry

    def execute(self, task: str, context: str = "", background: bool = False) -> str:
        if background:
            from background.task_manager import BackgroundTaskManager
            manager = BackgroundTaskManager()
            task_id = manager.create_task(
                name=f"Director: {task[:50]}",
                description=task[:200],
                agent="director",
                task_text=task,
                context=context,
                registry=self._registry,
            )
            return (
                f"Tarea compleja delegada al Director en segundo plano.\n"
                f"ID: {task_id}\n"
                f"Usá 'check_tasks' para ver el progreso."
            )

        from agents.director import DirectorAgent
        director = DirectorAgent(self._registry)
        return director.run(task, context)
