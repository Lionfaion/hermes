"""Director Agent: descompone tareas complejas y coordina múltiples agentes."""

import json
import logging

from inference_client import chat
from agents.base_agent import BaseAgent
from agents.profiles import AGENT_PROFILES
from tools.registry import ToolRegistry

logger = logging.getLogger(__name__)

DECOMPOSITION_PROMPT = """Sos un director de proyectos experto. Tu trabajo es descomponer tareas complejas en pasos ejecutables y asignar cada paso al agente más apropiado.

## Agentes disponibles:
{agents_list}

## Reglas:
1. Descomponé la tarea en pasos claros y específicos (máximo {max_steps} pasos)
2. Cada paso debe tener un agente asignado
3. Indicá dependencias entre pasos (qué pasos necesitan completarse antes)
4. Si la tarea es simple, usá solo 1-2 pasos
5. Los pasos independientes pueden ejecutarse en paralelo

## Formato de respuesta:
Respondé SOLO con JSON válido, sin texto adicional:
{{
    "plan_name": "nombre del plan",
    "steps": [
        {{"id": "s1", "agent": "researcher", "task": "descripción de la tarea", "depends_on": []}},
        {{"id": "s2", "agent": "analyst", "task": "otra tarea", "depends_on": ["s1"]}},
        {{"id": "s3", "agent": "coder", "task": "tarea paralela", "depends_on": ["s1"]}},
        {{"id": "s4", "agent": "researcher", "task": "tarea final", "depends_on": ["s2", "s3"]}}
    ]
}}

## Tarea a descomponer:
{task}
"""

SYNTHESIS_PROMPT = """Sos un director de proyectos. Recibiste los resultados de múltiples agentes que trabajaron en subtareas de un proyecto. Tu trabajo es sintetizar todo en una respuesta coherente y completa.

## Tarea original:
{task}

## Resultados de los agentes:
{results}

Sintetizá los resultados en una respuesta clara, organizada y útil. Si hay contradicciones entre agentes, señalalas. Si faltan elementos, mencionalo.
"""


class DirectorAgent:
    def __init__(self, registry: ToolRegistry, max_steps: int = 6):
        self.registry = registry
        self.max_steps = max_steps

    def _build_agents_list(self) -> str:
        lines = []
        for name, profile in AGENT_PROFILES.items():
            if name == "director":
                continue
            tools = ", ".join(profile.tool_names) if profile.tool_names else "ninguna"
            lines.append(f"- **{name}** ({profile.name}): {profile.system_prompt[:100]}... Tools: {tools}")
        return "\n".join(lines)

    def decompose(self, task: str, context: str = "") -> dict:
        """Usa el LLM para descomponer la tarea en un plan de pasos."""
        from config import OLLAMA_MODEL

        prompt = DECOMPOSITION_PROMPT.format(
            agents_list=self._build_agents_list(),
            max_steps=self.max_steps,
            task=task + (f"\n\nContexto: {context}" if context else ""),
        )

        messages = [
            {"role": "system", "content": "Respondé SOLO con JSON válido."},
            {"role": "user", "content": prompt},
        ]

        for attempt in range(3):
            response = chat(messages, OLLAMA_MODEL)

            try:
                # Extraer JSON del response (puede tener markdown)
                text = response.strip()
                if "```" in text:
                    text = text.split("```")[1]
                    if text.startswith("json"):
                        text = text[4:]
                    text = text.strip()

                plan = json.loads(text)

                if "steps" in plan and isinstance(plan["steps"], list):
                    # Validar agentes
                    valid_agents = set(AGENT_PROFILES.keys())
                    for step in plan["steps"]:
                        if step.get("agent") not in valid_agents:
                            step["agent"] = "researcher"
                    return plan

            except (json.JSONDecodeError, KeyError, IndexError):
                logger.warning("Director: JSON inválido (intento %d), reintentando...", attempt + 1)
                messages.append({"role": "assistant", "content": response})
                messages.append({"role": "user", "content": "El JSON no es válido. Respondé SOLO con JSON válido, sin texto adicional."})

        # Fallback: un solo paso con researcher
        return {
            "plan_name": "Plan simple",
            "steps": [{"id": "s1", "agent": "researcher", "task": task, "depends_on": []}],
        }

    def execute_plan(self, plan: dict, context: str = "") -> dict:
        """Ejecuta el plan respetando dependencias."""
        steps = plan.get("steps", [])
        results = {}
        completed = set()

        # Topological execution
        max_iterations = len(steps) * 2
        iteration = 0

        while len(completed) < len(steps) and iteration < max_iterations:
            iteration += 1
            ran_something = False

            for step in steps:
                step_id = step["id"]
                if step_id in completed:
                    continue

                deps = set(step.get("depends_on", []))
                if not deps.issubset(completed):
                    continue

                # Build context from completed dependencies
                dep_context = context
                for dep_id in deps:
                    if dep_id in results:
                        dep_context += f"\n\n[Resultado de paso {dep_id}]:\n{results[dep_id]}"

                agent_name = step["agent"]
                task_text = step["task"]

                logger.info("Director: ejecutando paso %s con agente %s", step_id, agent_name)

                if agent_name in AGENT_PROFILES:
                    agent = BaseAgent(AGENT_PROFILES[agent_name], self.registry)
                    try:
                        result = agent.run(task_text, dep_context)
                        results[step_id] = result
                    except Exception as e:
                        results[step_id] = f"[Error: {e}]"
                        logger.error("Director: paso %s falló: %s", step_id, e)
                else:
                    results[step_id] = f"[Agente '{agent_name}' no encontrado]"

                completed.add(step_id)
                ran_something = True

            if not ran_something and len(completed) < len(steps):
                remaining = [s["id"] for s in steps if s["id"] not in completed]
                logger.warning("Director: pasos con dependencias irresolvibles: %s", remaining)
                for step_id in remaining:
                    results[step_id] = "[Skipped: dependencias no resueltas]"
                    completed.add(step_id)

        return results

    def synthesize(self, task: str, results: dict) -> str:
        """Sintetiza los resultados de los agentes en una respuesta final."""
        from config import OLLAMA_MODEL

        results_text = ""
        for step_id, result in results.items():
            results_text += f"\n### Paso {step_id}:\n{result}\n"

        prompt = SYNTHESIS_PROMPT.format(task=task, results=results_text)

        messages = [
            {"role": "system", "content": "Sos un director de proyectos que sintetiza resultados de múltiples agentes."},
            {"role": "user", "content": prompt},
        ]

        return chat(messages, OLLAMA_MODEL)

    def run(self, task: str, context: str = "") -> str:
        """Flujo completo: descomponer → ejecutar → sintetizar."""
        logger.info("Director: descomponiendo tarea...")
        plan = self.decompose(task, context)

        plan_summary = f"Plan: {plan.get('plan_name', 'Sin nombre')}\n"
        for step in plan.get("steps", []):
            deps = f" (depende de: {', '.join(step.get('depends_on', []))})" if step.get("depends_on") else ""
            plan_summary += f"  {step['id']}: [{step['agent']}] {step['task'][:80]}{deps}\n"
        logger.info("Director plan:\n%s", plan_summary)

        logger.info("Director: ejecutando plan (%d pasos)...", len(plan.get("steps", [])))
        results = self.execute_plan(plan, context)

        if len(results) == 1:
            return list(results.values())[0]

        logger.info("Director: sintetizando resultados...")
        return self.synthesize(task, results)
