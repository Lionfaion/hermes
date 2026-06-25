"""Herramientas de Spec Driven Development para Hermes."""

from tools.base import BaseTool


class CreateSpecTool(BaseTool):
    name = "create_spec"
    description = (
        "Crea una especificación (spec) estructurada para una tarea o proyecto. "
        "Podés pasar los campos manualmente o una descripción libre y el LLM la estructura. "
        "Las specs se usan como 'brief' para tareas, cron jobs, generación de contenido, etc. "
        "Garantizan consistencia y calidad en ejecuciones repetidas."
    )
    parameters = {
        "type": "object",
        "properties": {
            "name": {
                "type": "string",
                "description": "Nombre corto de la spec",
            },
            "objective": {
                "type": "string",
                "description": "Objetivo claro y medible",
            },
            "description": {
                "type": "string",
                "description": "Descripción libre (alternativa: el LLM genera la spec estructurada)",
            },
            "context": {
                "type": "string",
                "description": "Contexto relevante para la tarea",
            },
            "steps": {
                "type": "array",
                "description": "Pasos a seguir (lista de strings o objetos con description y agent)",
                "items": {"type": "string"},
            },
            "acceptance_criteria": {
                "type": "array",
                "description": "Criterios que determinan si la tarea se completó bien",
                "items": {"type": "string"},
            },
            "constraints": {
                "type": "array",
                "description": "Restricciones o limitaciones",
                "items": {"type": "string"},
            },
            "audience": {
                "type": "string",
                "description": "Audiencia objetivo del resultado",
            },
            "tone": {
                "type": "string",
                "description": "Tono del contenido (profesional, casual, técnico, etc.)",
            },
            "format_spec": {
                "type": "string",
                "description": "Formato esperado del resultado (artículo, video, código, etc.)",
            },
            "tags": {
                "type": "array",
                "description": "Tags para categorizar la spec",
                "items": {"type": "string"},
            },
        },
        "required": [],
    }

    def execute(
        self,
        name: str = "",
        objective: str = "",
        description: str = "",
        context: str = "",
        steps: list = None,
        acceptance_criteria: list = None,
        constraints: list = None,
        audience: str = "",
        tone: str = "",
        format_spec: str = "",
        tags: list = None,
    ) -> str:
        from specs.manager import SpecManager

        manager = SpecManager()

        if description and not objective:
            generated = manager.generate_spec_from_description(description)
            spec_id = manager.create_spec(
                name=generated.get("name", description[:50]),
                objective=generated.get("objective", description),
                context=generated.get("context", context),
                steps=generated.get("steps", []),
                acceptance_criteria=generated.get("acceptance_criteria", []),
                constraints=generated.get("constraints", []),
                audience=generated.get("audience", audience),
                tone=generated.get("tone", tone),
                format_spec=generated.get("format_spec", format_spec),
                tags=generated.get("tags", tags or []),
            )
            spec = manager.get_spec(spec_id)
            return (
                f"Spec generada automáticamente!\n"
                f"ID: {spec_id}\n\n"
                f"{manager.build_prompt_injection(spec)}"
            )

        if not name or not objective:
            return "Necesito al menos 'name' y 'objective', o una 'description' libre."

        spec_id = manager.create_spec(
            name=name,
            objective=objective,
            context=context,
            steps=[{"description": s} if isinstance(s, str) else s for s in (steps or [])],
            acceptance_criteria=acceptance_criteria,
            constraints=constraints,
            audience=audience,
            tone=tone,
            format_spec=format_spec,
            tags=tags,
        )
        return f"Spec '{name}' creada con ID: {spec_id}"


class ListSpecsTool(BaseTool):
    name = "list_specs"
    description = "Lista todas las especificaciones (specs) disponibles, opcionalmente filtradas por tag o estado."
    parameters = {
        "type": "object",
        "properties": {
            "tag": {
                "type": "string",
                "description": "Filtrar por tag",
            },
            "status": {
                "type": "string",
                "description": "Filtrar por estado: draft, active, archived",
                "enum": ["draft", "active", "archived"],
            },
        },
        "required": [],
    }

    def execute(self, tag: str = "", status: str = "") -> str:
        from specs.manager import SpecManager

        manager = SpecManager()
        specs = manager.list_specs(tag=tag, status=status)

        if not specs:
            return "No hay specs registradas." + (f" (filtro: tag={tag}, status={status})" if tag or status else "")

        lines = ["**Especificaciones disponibles:**\n"]
        status_icons = {"draft": "📝", "active": "✅", "archived": "📦"}

        for s in specs:
            icon = status_icons.get(s.status, "📄")
            tags_str = f" [{', '.join(s.tags)}]" if s.tags else ""
            lines.append(f"{icon} [{s.spec_id}] **{s.name}**{tags_str}")
            lines.append(f"   {s.objective[:100]}")

        return "\n".join(lines)


class GetSpecTool(BaseTool):
    name = "get_spec"
    description = "Muestra los detalles completos de una spec por ID o nombre."
    parameters = {
        "type": "object",
        "properties": {
            "spec_id": {
                "type": "string",
                "description": "ID de la spec",
            },
            "name": {
                "type": "string",
                "description": "Nombre (búsqueda parcial) de la spec",
            },
        },
        "required": [],
    }

    def execute(self, spec_id: str = "", name: str = "") -> str:
        from specs.manager import SpecManager

        manager = SpecManager()

        if spec_id:
            spec = manager.get_spec(spec_id)
        elif name:
            spec = manager.find_spec(name)
        else:
            return "Necesito spec_id o name."

        if not spec:
            return f"Spec no encontrada."

        return manager.build_prompt_injection(spec)


class ExecuteSpecTool(BaseTool):
    name = "execute_spec"
    description = (
        "Ejecuta una spec usando el Director agent. La spec se convierte en un plan "
        "de ejecución con agentes asignados. Puede ejecutarse en primer plano o en background."
    )
    parameters = {
        "type": "object",
        "properties": {
            "spec_id": {
                "type": "string",
                "description": "ID de la spec a ejecutar",
            },
            "name": {
                "type": "string",
                "description": "Nombre de la spec (búsqueda parcial)",
            },
            "background": {
                "type": "boolean",
                "description": "Ejecutar en segundo plano (default false)",
            },
            "extra_context": {
                "type": "string",
                "description": "Contexto adicional para esta ejecución específica",
            },
        },
        "required": [],
    }

    def __init__(self, registry=None):
        self._registry = registry

    def execute(
        self,
        spec_id: str = "",
        name: str = "",
        background: bool = False,
        extra_context: str = "",
    ) -> str:
        from specs.manager import SpecManager

        manager = SpecManager()

        if spec_id:
            spec = manager.get_spec(spec_id)
        elif name:
            spec = manager.find_spec(name)
        else:
            return "Necesito spec_id o name."

        if not spec:
            return "Spec no encontrada."

        spec_prompt = manager.build_prompt_injection(spec)
        task_text = f"Ejecutá esta especificación:\n\n{spec_prompt}"
        context = extra_context

        manager.update_spec(spec.spec_id, status="active")

        if background:
            from background.task_manager import BackgroundTaskManager
            task_manager = BackgroundTaskManager()
            task_id = task_manager.create_task(
                name=f"Spec: {spec.name}",
                description=spec.objective[:200],
                agent="director",
                task_text=task_text,
                context=context,
                registry=self._registry,
            )
            return (
                f"Spec '{spec.name}' ejecutándose en background.\n"
                f"Task ID: {task_id}\n"
                f"Usá 'check_tasks' para ver el progreso."
            )

        from agents.director import DirectorAgent
        director = DirectorAgent(self._registry)
        result = director.run(task_text, context)

        manager.update_spec(spec.spec_id, status="active")
        return result


class DeleteSpecTool(BaseTool):
    name = "delete_spec"
    description = "Elimina una spec por su ID."
    parameters = {
        "type": "object",
        "properties": {
            "spec_id": {
                "type": "string",
                "description": "ID de la spec a eliminar",
            },
        },
        "required": ["spec_id"],
    }

    def execute(self, spec_id: str) -> str:
        from specs.manager import SpecManager
        manager = SpecManager()
        if manager.delete_spec(spec_id):
            return f"Spec {spec_id} eliminada."
        return f"Spec {spec_id} no encontrada."
