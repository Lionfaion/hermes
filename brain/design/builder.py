"""Constructor de páginas web: genera, guarda y sirve archivos HTML."""

import logging
from pathlib import Path
from dataclasses import dataclass

from config import DATA_DIR

logger = logging.getLogger(__name__)

DESIGNS_DIR = DATA_DIR / "designs"


@dataclass
class BuildResult:
    success: bool
    file_path: str = ""
    url: str = ""
    error: str = ""


def save_design(html: str, css: str, name: str, output_dir: str = "") -> BuildResult:
    """Guarda un diseño como archivo HTML completo."""
    out = Path(output_dir) if output_dir else DESIGNS_DIR
    out.mkdir(parents=True, exist_ok=True)

    safe_name = "".join(c for c in name[:50] if c.isalnum() or c in " -_").strip()
    if not safe_name:
        safe_name = "design"

    file_path = out / f"{safe_name}.html"

    if css and "<style>" not in html:
        # Inyectar CSS en el HTML si no está incluido
        if "<head>" in html:
            html = html.replace("<head>", f"<head>\n<style>\n{css}\n</style>")
        else:
            html = f"<style>\n{css}\n</style>\n{html}"

    # Asegurar que sea HTML completo
    if "<!DOCTYPE" not in html.upper() and "<html" not in html.lower():
        html = f"""<!DOCTYPE html>
<html lang="es">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{safe_name}</title>
</head>
<body>
{html}
</body>
</html>"""

    try:
        file_path.write_text(html, encoding="utf-8")
        logger.info("Diseño guardado: %s", file_path)
        return BuildResult(success=True, file_path=str(file_path))
    except Exception as e:
        return BuildResult(success=False, error=str(e))


def save_multipage(screens: list, project_name: str) -> list[BuildResult]:
    """Guarda múltiples pantallas como archivos HTML separados."""
    results = []
    project_dir = DESIGNS_DIR / project_name
    project_dir.mkdir(parents=True, exist_ok=True)

    for i, screen in enumerate(screens):
        name = screen.screen_name or f"screen_{i + 1}"
        result = save_design(
            html=screen.html,
            css=screen.css,
            name=name,
            output_dir=str(project_dir),
        )
        results.append(result)

    # Crear index.html que linkea todas las páginas
    if len(results) > 1:
        links = []
        for i, r in enumerate(results):
            if r.success:
                fname = Path(r.file_path).name
                screen_name = screens[i].screen_name or f"Screen {i + 1}"
                links.append(f'<li><a href="{fname}">{screen_name}</a></li>')

        index_html = f"""<!DOCTYPE html>
<html lang="es">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{project_name}</title>
    <style>
        body {{ font-family: system-ui, sans-serif; max-width: 600px; margin: 2rem auto; padding: 0 1rem; }}
        h1 {{ color: #333; }}
        ul {{ list-style: none; padding: 0; }}
        li {{ margin: 0.5rem 0; }}
        a {{ color: #0066cc; text-decoration: none; padding: 0.5rem 1rem; border: 1px solid #ddd;
             border-radius: 8px; display: inline-block; }}
        a:hover {{ background: #f0f0f0; }}
    </style>
</head>
<body>
    <h1>{project_name}</h1>
    <ul>{"".join(links)}</ul>
</body>
</html>"""
        index_path = project_dir / "index.html"
        index_path.write_text(index_html, encoding="utf-8")

    return results


def generate_html_with_llm(prompt: str, page_type: str = "landing") -> str:
    """Genera HTML usando el LLM local cuando Stitch no está disponible."""
    from inference_client import chat

    system = (
        "Sos un experto en desarrollo web frontend. Generás HTML5 + CSS3 moderno, responsive, "
        "y visualmente atractivo. Usás Tailwind CSS via CDN cuando corresponda. "
        "Respondé SOLO con el código HTML completo, sin explicaciones."
    )

    type_hints = {
        "landing": "landing page con hero section, features, testimonials y CTA",
        "portfolio": "portfolio personal con proyectos, about me y contacto",
        "blog": "blog layout con sidebar, cards de posts y navegación",
        "ecommerce": "producto ecommerce con galería, precio, reviews y botón de compra",
        "dashboard": "dashboard con cards de métricas, gráficos placeholder y sidebar",
        "form": "formulario con validación visual, steps y confirmación",
    }

    hint = type_hints.get(page_type, page_type)
    full_prompt = f"Generá un {hint}. Requerimientos del usuario: {prompt}"

    messages = [
        {"role": "system", "content": system},
        {"role": "user", "content": full_prompt},
    ]

    return chat(messages)
