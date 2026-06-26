"""Tools for reasoning, self-evolution, and advanced AI capabilities."""

import json
from tools.base import BaseTool


class AutoReasonTool(BaseTool):
    @property
    def name(self) -> str:
        return "autoreason"

    @property
    def description(self) -> str:
        return "Genera múltiples respuestas competidoras y selecciona la mejor via juicio ciego (Borda count). Útil para respuestas de alta calidad."

    @property
    def parameters(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "prompt": {"type": "string", "description": "La pregunta o tarea a resolver con máxima calidad"},
                "system_prompt": {"type": "string", "description": "System prompt personalizado (opcional)"},
            },
            "required": ["prompt"],
        }

    def execute(self, **kwargs) -> str:
        from reasoning.autoreason import autoreason
        result = autoreason(
            prompt=kwargs["prompt"],
            system_prompt=kwargs.get("system_prompt", ""),
        )
        return (
            f"**Método ganador:** {result.method}\n"
            f"**Mejorado:** {'Sí' if result.improved else 'No'}\n"
            f"**Scores:** {result.scores}\n\n"
            f"{result.best_response}"
        )


class ParallelSolveTool(BaseTool):
    @property
    def name(self) -> str:
        return "parallel_solve"

    @property
    def description(self) -> str:
        return "Resuelve un problema usando múltiples estrategias en paralelo y selecciona/combina la mejor solución."

    @property
    def parameters(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "problem": {"type": "string", "description": "El problema a resolver"},
                "strategies": {
                    "type": "string",
                    "description": "Estrategias separadas por coma: direct, step_by_step, first_principles, analogical, adversarial, constraint",
                },
            },
            "required": ["problem"],
        }

    def execute(self, **kwargs) -> str:
        from reasoning.parallel_solver import parallel_solve
        strategies = None
        if kwargs.get("strategies"):
            strategies = [s.strip() for s in kwargs["strategies"].split(",")]
        result = parallel_solve(problem=kwargs["problem"], strategies=strategies)

        parts = [f"**Mejor estrategia:** {result.best.strategy} (score: {result.best.score:.1f})"]
        parts.append(f"**Tiempo total:** {result.total_time_ms:.0f}ms")
        for r in result.all_results:
            parts.append(f"- {r.strategy}: {r.score:.1f} ({r.time_ms:.0f}ms)")
        if result.merged:
            parts.append(f"\n**Solución combinada:**\n{result.merged}")
        else:
            parts.append(f"\n**Mejor respuesta:**\n{result.best.response}")
        return "\n".join(parts)


class ReasoningPracticeTool(BaseTool):
    @property
    def name(self) -> str:
        return "reasoning_practice"

    @property
    def description(self) -> str:
        return "Ejecuta una sesión de práctica de razonamiento con ejercicios generados y evaluados automáticamente."

    @property
    def parameters(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "num_tasks": {"type": "integer", "description": "Cantidad de ejercicios (default: 3)"},
                "category": {"type": "string", "description": "Categoría: logical_deduction, mathematical_reasoning, causal_reasoning, analogical_reasoning, etc."},
            },
            "required": [],
        }

    def execute(self, **kwargs) -> str:
        from reasoning.tasks import practice_session, TASK_CATEGORIES
        categories = None
        if kwargs.get("category"):
            categories = [kwargs["category"]]

        results = practice_session(
            num_tasks=kwargs.get("num_tasks", 3),
            categories=categories,
        )

        parts = [f"**Sesión de práctica: {len(results)} ejercicios**\n"]
        total_score = 0
        for r in results:
            status = "PASS" if r.passed else "FAIL"
            parts.append(f"### [{status}] {r.task.category} (score: {r.score:.1f})")
            parts.append(f"**Ejercicio:** {r.task.prompt[:200]}")
            parts.append(f"**Feedback:** {r.feedback[:200]}\n")
            total_score += r.score

        avg = total_score / len(results) if results else 0
        parts.append(f"**Promedio: {avg:.1f}/10**")
        return "\n".join(parts)


class EvolvePromptTool(BaseTool):
    @property
    def name(self) -> str:
        return "evolve_prompt"

    @property
    def description(self) -> str:
        return "Evoluciona y mejora un system prompt usando trazas de ejecución y evaluación LLM."

    @property
    def parameters(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "prompt_name": {"type": "string", "description": "Nombre del prompt a evolucionar"},
                "current_prompt": {"type": "string", "description": "El prompt actual a mejorar"},
                "context": {"type": "string", "description": "Contexto adicional sobre el uso del prompt"},
            },
            "required": ["prompt_name", "current_prompt"],
        }

    def execute(self, **kwargs) -> str:
        from evolution.skill_evolver import evolve_prompt
        result = evolve_prompt(
            prompt_name=kwargs["prompt_name"],
            current_prompt=kwargs["current_prompt"],
            context=kwargs.get("context", ""),
        )

        if result.improved:
            return (
                f"**Prompt mejorado** (gen {result.generation})\n"
                f"Score: {result.score_before:.1f} → {result.score_after:.1f}\n"
                f"Cambios: {result.changes_summary}\n\n"
                f"**Nuevo prompt:**\n{result.evolved}"
            )
        return f"El prompt actual ya es óptimo (score: {result.score_before:.1f}). Sin mejoras encontradas."


class NeuralSteerTool(BaseTool):
    @property
    def name(self) -> str:
        return "neural_steer"

    @property
    def description(self) -> str:
        return "Genera una respuesta con steering neural: ajusta creatividad, precisión, tono, etc."

    @property
    def parameters(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "prompt": {"type": "string", "description": "El prompt a procesar"},
                "steering": {
                    "type": "string",
                    "description": "Vectores de steering separados por coma: creative, precise, concise, verbose, formal, casual, analytical, empathetic",
                },
            },
            "required": ["prompt", "steering"],
        }

    def execute(self, **kwargs) -> str:
        from models.neural_steer import create_steered_chat
        vectors = [s.strip() for s in kwargs["steering"].split(",")]
        response = create_steered_chat(
            messages=[{"role": "user", "content": kwargs["prompt"]}],
            steering=vectors,
        )
        return f"**[Steering: {', '.join(vectors)}]**\n\n{response}"


class AbliterateTool(BaseTool):
    @property
    def name(self) -> str:
        return "abliterate_chat"

    @property
    def description(self) -> str:
        return "Chat con manejo automático de rechazos del modelo. Reenmarca la solicitud si el modelo se niega."

    @property
    def parameters(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "prompt": {"type": "string", "description": "El mensaje a enviar"},
                "system_prompt": {"type": "string", "description": "System prompt personalizado (opcional)"},
            },
            "required": ["prompt"],
        }

    def execute(self, **kwargs) -> str:
        from models.abliterate import abliterate_chat
        messages = []
        if kwargs.get("system_prompt"):
            messages.append({"role": "system", "content": kwargs["system_prompt"]})
        messages.append({"role": "user", "content": kwargs["prompt"]})

        result = abliterate_chat(messages)
        prefix = ""
        if result.was_refused:
            prefix = f"*[Reenmarcado con {result.method} después de {result.retry_count} intentos]*\n\n"
        return prefix + result.response


class KanbanVideoTool(BaseTool):
    @property
    def name(self) -> str:
        return "kanban_video"

    @property
    def description(self) -> str:
        return "Produce un video usando el pipeline multi-agente Kanban: Director → Cinematographer → Renderers → Editor."

    @property
    def parameters(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "brief": {"type": "string", "description": "Descripción del video a producir"},
                "format": {"type": "string", "enum": ["vertical", "horizontal", "square"], "description": "Formato del video"},
            },
            "required": ["brief"],
        }

    def execute(self, **kwargs) -> str:
        from video.kanban_pipeline import produce_kanban_video
        board = produce_kanban_video(
            brief=kwargs["brief"],
            format=kwargs.get("format", "vertical"),
        )

        parts = [f"**Proyecto:** {board.project_name}"]
        for task in board.tasks:
            parts.append(f"- [{task.status.upper()}] {task.agent}: {task.title}")
        if board.final_video:
            parts.append(f"\n**Video final:** {board.final_video}")
        if board.artifacts:
            parts.append(f"**Artefactos:** {len(board.artifacts)}")
        return "\n".join(parts)


class NovelWriterTool(BaseTool):
    @property
    def name(self) -> str:
        return "write_novel"

    @property
    def description(self) -> str:
        return "Genera una novela o contenido largo con múltiples capítulos coherentes."

    @property
    def parameters(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "premise": {"type": "string", "description": "Premisa de la novela"},
                "genre": {"type": "string", "description": "Género literario"},
                "num_chapters": {"type": "integer", "description": "Cantidad de capítulos (default: 5)"},
            },
            "required": ["premise"],
        }

    def execute(self, **kwargs) -> str:
        from content.novel_pipeline import generate_novel
        project = generate_novel(
            premise=kwargs["premise"],
            genre=kwargs.get("genre", "ficción"),
            num_chapters=kwargs.get("num_chapters", 5),
        )

        parts = [
            f"**{project.title}**",
            f"Género: {project.genre} | {project.total_words} palabras | {len(project.chapters)} capítulos",
        ]
        for ch in project.chapters:
            parts.append(f"- Cap {ch.number}: {ch.title} ({ch.word_count} palabras)")
        parts.append(f"\nArchivo: {project.output_path}")
        return "\n".join(parts)


class AgentStatsTool(BaseTool):
    @property
    def name(self) -> str:
        return "agent_stats"

    @property
    def description(self) -> str:
        return "Muestra estadísticas de rendimiento de un agente basadas en el historial RL."

    @property
    def parameters(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "agent": {"type": "string", "description": "Nombre del agente a consultar"},
            },
            "required": ["agent"],
        }

    def execute(self, **kwargs) -> str:
        from training.rl_env import get_agent_stats
        stats = get_agent_stats(kwargs["agent"])
        return (
            f"**Agente: {kwargs['agent']}**\n"
            f"Episodios: {stats['episodes']}\n"
            f"Reward promedio: {stats['avg_reward']}\n"
            f"Reward máximo: {stats['max_reward']}\n"
            f"Reward mínimo: {stats['min_reward']}"
        )
