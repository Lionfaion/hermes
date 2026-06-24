"""Herramientas de diseño web: Google Stitch + generación HTML con LLM."""

from tools.base import BaseTool


class DesignPageTool(BaseTool):
    name = "design_page"
    description = (
        "Diseña una página web, landing page o UI usando Google Stitch (IA de Google). "
        "Genera HTML/CSS de producción, responsive y moderno. "
        "Si Stitch no está disponible, usa el LLM local como fallback. "
        "Úsala cuando el usuario quiera crear una página web, landing, formulario, dashboard, etc."
    )
    parameters = {
        "type": "object",
        "properties": {
            "prompt": {
                "type": "string",
                "description": "Descripción detallada de la página que querés generar",
            },
            "name": {
                "type": "string",
                "description": "Nombre del proyecto/archivo (ej: 'mi-landing')",
            },
            "style": {
                "type": "string",
                "description": "Estilo visual (ej: 'modern minimalist', 'dark theme', 'glassmorphism', 'corporate')",
            },
            "num_screens": {
                "type": "integer",
                "description": "Cantidad de pantallas a generar (1-5, default 1)",
            },
            "page_type": {
                "type": "string",
                "description": "Tipo de página: landing, portfolio, blog, ecommerce, dashboard, form",
                "enum": ["landing", "portfolio", "blog", "ecommerce", "dashboard", "form"],
            },
        },
        "required": ["prompt", "name"],
    }

    def execute(
        self,
        prompt: str,
        name: str,
        style: str = "",
        num_screens: int = 1,
        page_type: str = "landing",
    ) -> str:
        # Intentar con Google Stitch primero
        from design.stitch import generate_ui, STITCH_API_KEY

        if STITCH_API_KEY:
            result = generate_ui(prompt, num_screens=num_screens, style=style)

            if result.success and result.screens:
                if len(result.screens) > 1:
                    from design.builder import save_multipage
                    saved = save_multipage(result.screens, name)
                    paths = [r.file_path for r in saved if r.success]
                    return (
                        f"Diseño generado con Google Stitch ({len(paths)} pantallas)!\n"
                        f"Archivos: {', '.join(paths)}\n"
                        f"Proyecto Stitch: {result.project_url}"
                    )
                else:
                    from design.builder import save_design
                    screen = result.screens[0]
                    saved = save_design(screen.html, screen.css, name)
                    if saved.success:
                        return (
                            f"Diseño generado con Google Stitch!\n"
                            f"Archivo: {saved.file_path}\n"
                            f"Proyecto Stitch: {result.project_url}"
                        )

        # Fallback: generar con LLM local
        from design.builder import generate_html_with_llm, save_design

        html = generate_html_with_llm(prompt, page_type=page_type)
        saved = save_design(html, "", name)

        if saved.success:
            return (
                f"Diseño generado con LLM local (Stitch no disponible).\n"
                f"Archivo: {saved.file_path}"
            )
        return f"Error guardando diseño: {saved.error}"


class IterateDesignTool(BaseTool):
    name = "iterate_design"
    description = (
        "Modifica un diseño existente de Google Stitch con feedback. "
        "Úsala cuando el usuario quiera ajustar un diseño que ya se generó "
        "(cambiar colores, agregar secciones, etc.)."
    )
    parameters = {
        "type": "object",
        "properties": {
            "project_url": {
                "type": "string",
                "description": "URL del proyecto Stitch a modificar",
            },
            "feedback": {
                "type": "string",
                "description": "Qué cambios querés hacer al diseño",
            },
            "name": {
                "type": "string",
                "description": "Nombre para guardar la versión actualizada",
            },
        },
        "required": ["project_url", "feedback", "name"],
    }

    def execute(self, project_url: str, feedback: str, name: str) -> str:
        from design.stitch import iterate_design
        from design.builder import save_design

        result = iterate_design(project_url, feedback)

        if not result.success:
            return f"Error iterando diseño: {result.error}"

        if not result.screens:
            return "Stitch no devolvió pantallas actualizadas."

        screen = result.screens[0]
        saved = save_design(screen.html, screen.css, f"{name}_v2")

        if saved.success:
            return (
                f"Diseño actualizado!\n"
                f"Archivo: {saved.file_path}\n"
                f"Proyecto: {result.project_url}"
            )
        return f"Error guardando: {saved.error}"


class GenerateHTMLTool(BaseTool):
    name = "generate_html"
    description = (
        "Genera código HTML/CSS directamente con el LLM local (sin Google Stitch). "
        "Úsala cuando necesites generar HTML rápido, componentes sueltos, "
        "emails HTML, o cuando Stitch no esté disponible."
    )
    parameters = {
        "type": "object",
        "properties": {
            "prompt": {
                "type": "string",
                "description": "Descripción de lo que querés generar",
            },
            "name": {
                "type": "string",
                "description": "Nombre del archivo",
            },
            "page_type": {
                "type": "string",
                "description": "Tipo: landing, portfolio, blog, ecommerce, dashboard, form",
            },
        },
        "required": ["prompt", "name"],
    }

    def execute(self, prompt: str, name: str, page_type: str = "landing") -> str:
        from design.builder import generate_html_with_llm, save_design

        html = generate_html_with_llm(prompt, page_type=page_type)
        saved = save_design(html, "", name)

        if saved.success:
            return f"HTML generado!\nArchivo: {saved.file_path}"
        return f"Error: {saved.error}"
