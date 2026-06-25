"""Herramientas para gestión de tareas en segundo plano."""

from tools.base import BaseTool
from agents.profiles import AGENT_PROFILES


class CreateBackgroundTaskTool(BaseTool):
    name = "create_task"
    description = (
        "Crea una tarea que se ejecuta en segundo plano con un agente especializado. "
        "El usuario puede seguir chateando mientras la tarea se procesa. "
        "Úsala para tareas complejas que toman tiempo: investigaciones profundas, "
        "análisis extensos, generación de contenido en lote, etc."
    )
    parameters = {
        "type": "object",
        "properties": {
            "name": {
                "type": "string",
                "description": "Nombre corto de la tarea",
            },
            "agent": {
                "type": "string",
                "description": "Agente especializado para la tarea",
                "enum": list(AGENT_PROFILES.keys()),
            },
            "task": {
                "type": "string",
                "description": "Descripción detallada de lo que debe hacer el agente",
            },
            "context": {
                "type": "string",
                "description": "Contexto adicional para la tarea (opcional)",
            },
        },
        "required": ["name", "agent", "task"],
    }

    def __init__(self, registry=None):
        self._registry = registry

    def execute(self, name: str, agent: str, task: str, context: str = "") -> str:
        from background.task_manager import BackgroundTaskManager

        manager = BackgroundTaskManager()
        task_id = manager.create_task(
            name=name,
            description=task[:200],
            agent=agent,
            task_text=task,
            context=context,
            registry=self._registry,
        )
        active = manager.get_active_count()
        return (
            f"Tarea creada en segundo plano!\n"
            f"ID: {task_id}\n"
            f"Agente: {agent}\n"
            f"Tareas activas: {active}\n"
            f"Podés seguir chateando. Usá 'check_tasks' para ver el progreso."
        )


class CheckTasksTool(BaseTool):
    name = "check_tasks"
    description = (
        "Muestra el estado de las tareas en segundo plano. "
        "Si se pasa un task_id, muestra detalles y resultado de esa tarea específica. "
        "Sin task_id, lista todas las tareas recientes."
    )
    parameters = {
        "type": "object",
        "properties": {
            "task_id": {
                "type": "string",
                "description": "ID de la tarea (opcional, sin él lista todas)",
            },
            "status": {
                "type": "string",
                "description": "Filtrar por estado: running, completed, failed, pending",
                "enum": ["running", "completed", "failed", "pending", "cancelled"],
            },
        },
        "required": [],
    }

    def execute(self, task_id: str = "", status: str = "") -> str:
        from background.task_manager import BackgroundTaskManager

        manager = BackgroundTaskManager()

        if task_id:
            task = manager.get_task(task_id)
            if not task:
                return f"Tarea '{task_id}' no encontrada."

            status_icons = {
                "pending": "⏳", "running": "🔄",
                "completed": "✅", "failed": "❌", "cancelled": "🚫",
            }
            icon = status_icons.get(task.status, "❓")

            result = (
                f"{icon} **{task.name}** [{task.task_id}]\n"
                f"Agente: {task.agent}\n"
                f"Estado: {task.status}\n"
                f"Progreso: {task.progress or 'N/A'}\n"
                f"Creada: {task.created_at}\n"
            )
            if task.started_at:
                result += f"Iniciada: {task.started_at}\n"
            if task.completed_at:
                result += f"Completada: {task.completed_at}\n"
            if task.result:
                result += f"\nResultado:\n{task.result}"
            if task.error:
                result += f"\nError: {task.error}"
            return result

        tasks = manager.list_tasks(status=status, limit=10)
        if not tasks:
            return "No hay tareas registradas." if not status else f"No hay tareas con estado '{status}'."

        status_icons = {
            "pending": "⏳", "running": "🔄",
            "completed": "✅", "failed": "❌", "cancelled": "🚫",
        }

        lines = ["**Tareas en segundo plano:**\n"]
        for t in tasks:
            icon = status_icons.get(t.status, "❓")
            line = f"{icon} [{t.task_id}] **{t.name}** — {t.agent} — {t.status}"
            if t.progress and t.status == "running":
                line += f" ({t.progress})"
            lines.append(line)

        active = manager.get_active_count()
        lines.append(f"\nActivas: {active}")
        return "\n".join(lines)


class CancelTaskTool(BaseTool):
    name = "cancel_task"
    description = "Cancela una tarea en segundo plano por su ID."
    parameters = {
        "type": "object",
        "properties": {
            "task_id": {
                "type": "string",
                "description": "ID de la tarea a cancelar",
            },
        },
        "required": ["task_id"],
    }

    def execute(self, task_id: str) -> str:
        from background.task_manager import BackgroundTaskManager

        manager = BackgroundTaskManager()
        if manager.cancel_task(task_id):
            return f"Tarea {task_id} cancelada."
        return f"No se pudo cancelar la tarea {task_id}. Puede que ya haya terminado."
