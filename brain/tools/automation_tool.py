"""Herramientas de automatización de contenido."""

from tools.base import BaseTool


class ManageNicheTool(BaseTool):
    name = "manage_niche"
    description = (
        "Gestiona nichos de contenido. Podés agregar, listar o eliminar nichos "
        "para generar videos automáticos. Nichos pre-configurados: finanzas, "
        "tecnologia, curiosidades, motivacion, salud."
    )
    parameters = {
        "type": "object",
        "properties": {
            "action": {
                "type": "string",
                "description": "Acción: add, list, remove",
                "enum": ["add", "list", "remove"],
            },
            "niche_id": {
                "type": "string",
                "description": "ID del nicho (ej: finanzas, tecnologia, mi-nicho-custom)",
            },
            "name": {
                "type": "string",
                "description": "Nombre descriptivo del nicho (solo para add)",
            },
            "description": {
                "type": "string",
                "description": "Descripción del nicho (solo para add)",
            },
            "platforms": {
                "type": "string",
                "description": "Plataformas separadas por coma (solo para add). Default: youtube,instagram,tiktok",
            },
        },
        "required": ["action"],
    }

    def execute(self, action: str, niche_id: str = "", name: str = "", description: str = "", platforms: str = "") -> str:
        from automation.niche_manager import add_niche, remove_niche, list_niches

        if action == "list":
            niches = list_niches()
            if not niches:
                return "No hay nichos configurados. Usá action='add' para agregar uno."
            lines = []
            for nid, n in niches.items():
                lines.append(f"- **{nid}** ({n['name']}): {n.get('videos_generated', 0)} videos, plataformas: {', '.join(n.get('platforms', []))}")
            return "**Nichos activos:**\n" + "\n".join(lines)

        if not niche_id:
            return "Necesito el niche_id para esta acción."

        if action == "add":
            plats = [p.strip() for p in (platforms or "youtube,instagram,tiktok").split(",")]
            result = add_niche(
                niche_id=niche_id,
                name=name or niche_id,
                description=description or niche_id,
                platforms=plats,
            )
            return f"Nicho '{niche_id}' creado: {result['name']} → {', '.join(result['platforms'])}"

        if action == "remove":
            if remove_niche(niche_id):
                return f"Nicho '{niche_id}' desactivado."
            return f"Nicho '{niche_id}' no encontrado."

        return f"Acción '{action}' no reconocida."


class GenerateContentTool(BaseTool):
    name = "generate_content"
    description = (
        "Genera un guión de video para un nicho específico. Usa plantillas optimizadas "
        "para viralidad (hook-story-CTA, listicle, storytelling, etc). "
        "Puede generar para un tema específico o elegir uno automáticamente."
    )
    parameters = {
        "type": "object",
        "properties": {
            "niche": {
                "type": "string",
                "description": "Nicho (finanzas, tecnologia, curiosidades, motivacion, salud, o custom)",
            },
            "topic": {
                "type": "string",
                "description": "Tema específico (opcional, si no se especifica elige uno)",
            },
            "template": {
                "type": "string",
                "description": "Plantilla: hook_story_cta, listicle, storytelling, educational, curiosity, before_after",
            },
        },
        "required": ["niche"],
    }

    def execute(self, niche: str, topic: str = "", template: str = "") -> str:
        from automation.scheduler import generate_and_publish
        result = generate_and_publish(niche_id=niche, topic=topic)
        if "error" in result:
            from automation.templates import build_generation_prompt
            from inference_client import chat
            prompt = build_generation_prompt(niche, template_id=template, topic=topic)
            messages = [
                {"role": "system", "content": "Sos un guionista de videos virales. Respondé en español."},
                {"role": "user", "content": prompt},
            ]
            return chat(messages)
        return result.get("script", str(result))


class DetectTrendsTool(BaseTool):
    name = "detect_trends"
    description = (
        "Detecta tendencias actuales en redes sociales y web para un nicho. "
        "Busca qué está trending para crear contenido oportuno."
    )
    parameters = {
        "type": "object",
        "properties": {
            "niche": {
                "type": "string",
                "description": "Nicho para buscar tendencias (ej: tecnologia, finanzas)",
            },
        },
        "required": ["niche"],
    }

    def execute(self, niche: str) -> str:
        from automation.trends import get_trending_topics_for_niche
        return get_trending_topics_for_niche(niche)


class ClipContentTool(BaseTool):
    name = "clip_content"
    description = (
        "Descarga un video largo (podcast, stream, etc) y encuentra los mejores "
        "momentos para crear clips cortos virales."
    )
    parameters = {
        "type": "object",
        "properties": {
            "url": {
                "type": "string",
                "description": "URL del video a clipear (YouTube, etc)",
            },
            "clip_duration": {
                "type": "integer",
                "description": "Duración de cada clip en segundos (default: 60)",
            },
        },
        "required": ["url"],
    }

    def execute(self, url: str, clip_duration: int = 60) -> str:
        from automation.clipper import download_and_clip
        import json
        result = download_and_clip(url, clip_duration=clip_duration)
        if "error" in result:
            return f"Error: {result['error']}"
        return json.dumps(result, indent=2, ensure_ascii=False)


class BatchGenerateTool(BaseTool):
    name = "batch_generate"
    description = (
        "Genera contenido en lote para todos los nichos activos. "
        "Ideal para producción masiva de videos."
    )
    parameters = {
        "type": "object",
        "properties": {
            "max_videos": {
                "type": "integer",
                "description": "Máximo de videos a generar (default: 5)",
            },
        },
        "required": [],
    }

    def execute(self, max_videos: int = 5) -> str:
        from automation.scheduler import run_batch
        results = run_batch(max_videos=max_videos)
        if not results:
            return "No hay nichos configurados. Primero agregá nichos con manage_niche."
        lines = []
        for r in results:
            if "error" in r:
                lines.append(f"❌ {r['niche_id']}: {r['error']}")
            else:
                lines.append(f"✅ {r['niche_id']}: guión generado")
        return "**Generación en lote:**\n" + "\n".join(lines)


class VideoAnalyticsTool(BaseTool):
    name = "video_analytics"
    description = (
        "Muestra el reporte de performance de los videos publicados. "
        "Métricas: views, likes, engagement, por plataforma y nicho."
    )
    parameters = {
        "type": "object",
        "properties": {
            "niche": {
                "type": "string",
                "description": "Filtrar por nicho (opcional, vacío = todos)",
            },
        },
        "required": [],
    }

    def execute(self, niche: str = "") -> str:
        from automation.analytics import get_performance_report
        return get_performance_report(niche=niche)


class DailyBriefingTool(BaseTool):
    name = "daily_briefing"
    description = (
        "Genera el resumen diario: contenido generado, performance, "
        "tendencias y estado de los nichos."
    )
    parameters = {
        "type": "object",
        "properties": {},
        "required": [],
    }

    def execute(self) -> str:
        from automation.briefing import generate_daily_briefing
        return generate_daily_briefing()
