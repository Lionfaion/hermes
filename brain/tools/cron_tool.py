"""Herramientas para programar tareas recurrentes (Cron Jobs)."""

from tools.base import BaseTool
from agents.profiles import AGENT_PROFILES


class CreateCronJobTool(BaseTool):
    name = "create_cron_job"
    description = (
        "Programa una tarea recurrente que se ejecuta automáticamente. "
        "Podés usar lenguaje natural como 'cada lunes', 'diario a las 9', "
        "'cada 6 horas', o expresiones cron como '0 9 * * 1'. "
        "Úsala cuando el usuario quiera automatizar algo que se repite."
    )
    parameters = {
        "type": "object",
        "properties": {
            "name": {
                "type": "string",
                "description": "Nombre descriptivo del cron job",
            },
            "agent": {
                "type": "string",
                "description": "Agente que ejecutará la tarea",
                "enum": list(AGENT_PROFILES.keys()),
            },
            "task": {
                "type": "string",
                "description": "Descripción de la tarea a ejecutar en cada ciclo",
            },
            "schedule": {
                "type": "string",
                "description": "Frecuencia: 'cada lunes', 'diario a las 9', 'cada 6 horas', o cron '0 9 * * 1'",
            },
            "context": {
                "type": "string",
                "description": "Contexto adicional para la tarea (opcional)",
            },
        },
        "required": ["name", "agent", "task", "schedule"],
    }

    def execute(
        self,
        name: str,
        agent: str,
        task: str,
        schedule: str,
        context: str = "",
    ) -> str:
        from background.cron import CronScheduler, parse_schedule

        scheduler = CronScheduler()
        job_id = scheduler.add_job(name, agent, task, schedule, context)
        cron_expr = parse_schedule(schedule)

        if not scheduler._running:
            scheduler.start()

        return (
            f"Cron Job programado!\n"
            f"ID: {job_id}\n"
            f"Nombre: {name}\n"
            f"Agente: {agent}\n"
            f"Cron: {cron_expr}\n"
            f"La tarea se ejecutará automáticamente según la programación."
        )


class ListCronJobsTool(BaseTool):
    name = "list_cron_jobs"
    description = "Lista todas las tareas programadas (cron jobs) activas y su estado."
    parameters = {
        "type": "object",
        "properties": {},
        "required": [],
    }

    def execute(self) -> str:
        from background.cron import CronScheduler

        scheduler = CronScheduler()
        jobs = scheduler.list_jobs()

        if not jobs:
            return "No hay cron jobs programados."

        lines = ["**Tareas programadas (Cron Jobs):**\n"]
        for j in jobs:
            icon = "✅" if j.enabled else "⏸️"
            lines.append(
                f"{icon} [{j.job_id}] **{j.name}**\n"
                f"   Agente: {j.agent} | Cron: `{j.cron_expression}`\n"
                f"   Próxima: {j.next_run or 'N/A'} | Última: {j.last_run or 'nunca'}"
            )

        return "\n".join(lines)


class DeleteCronJobTool(BaseTool):
    name = "delete_cron_job"
    description = "Elimina un cron job programado por su ID."
    parameters = {
        "type": "object",
        "properties": {
            "job_id": {
                "type": "string",
                "description": "ID del cron job a eliminar",
            },
        },
        "required": ["job_id"],
    }

    def execute(self, job_id: str) -> str:
        from background.cron import CronScheduler

        scheduler = CronScheduler()
        if scheduler.delete_job(job_id):
            return f"Cron job {job_id} eliminado."
        return f"Cron job {job_id} no encontrado."
