"""Herramientas de publicación en redes sociales."""

from tools.base import BaseTool


class PublishVideoTool(BaseTool):
    name = "publish_video"
    description = (
        "Publica un video en múltiples redes sociales (YouTube, Instagram, TikTok, X, Facebook). "
        "YouTube se sube directo via API, el resto via Make.com. "
        "Podés programar la publicación para una fecha/hora específica."
    )
    parameters = {
        "type": "object",
        "properties": {
            "video_path": {
                "type": "string",
                "description": "Ruta al archivo de video a publicar",
            },
            "title": {
                "type": "string",
                "description": "Título del video",
            },
            "description": {
                "type": "string",
                "description": "Descripción del video",
            },
            "hashtags": {
                "type": "string",
                "description": "Hashtags separados por coma (sin #)",
            },
            "platforms": {
                "type": "string",
                "description": "Plataformas separadas por coma (youtube, instagram, tiktok, x, facebook). Default: youtube,instagram,tiktok",
            },
            "privacy": {
                "type": "string",
                "description": "Privacidad en YouTube: public, unlisted, private (default: private)",
            },
            "schedule_time": {
                "type": "string",
                "description": "Fecha/hora para publicar (ISO 8601, ej: 2025-01-15T10:00:00). Vacío = ahora",
            },
        },
        "required": ["video_path", "title"],
    }

    def execute(
        self,
        video_path: str,
        title: str,
        description: str = "",
        hashtags: str = "",
        platforms: str = "",
        privacy: str = "private",
        schedule_time: str = "",
    ) -> str:
        from social.publisher import publish_video

        tags = [t.strip() for t in hashtags.split(",") if t.strip()] if hashtags else []
        plats = [p.strip() for p in platforms.split(",") if p.strip()] if platforms else None

        result = publish_video(
            video_path=video_path,
            title=title,
            description=description,
            hashtags=tags,
            platforms=plats,
            privacy=privacy,
            schedule_time=schedule_time,
        )

        if "error" in result:
            return f"Error: {result['error']}"
        return result.get("summary", str(result))


class PublishTextTool(BaseTool):
    name = "publish_text"
    description = (
        "Publica un post de texto (con imagen opcional) en redes sociales via Make.com. "
        "Ideal para posts, stories, tweets."
    )
    parameters = {
        "type": "object",
        "properties": {
            "text": {
                "type": "string",
                "description": "Texto del post",
            },
            "platforms": {
                "type": "string",
                "description": "Plataformas separadas por coma (instagram, x, facebook, tiktok). Default: instagram,x,facebook",
            },
            "image_path": {
                "type": "string",
                "description": "Ruta a imagen para adjuntar (opcional)",
            },
            "schedule_time": {
                "type": "string",
                "description": "Fecha/hora para publicar (ISO 8601). Vacío = ahora",
            },
        },
        "required": ["text"],
    }

    def execute(
        self,
        text: str,
        platforms: str = "",
        image_path: str = "",
        schedule_time: str = "",
    ) -> str:
        from social.publisher import publish_text

        plats = [p.strip() for p in platforms.split(",") if p.strip()] if platforms else None

        result = publish_text(
            text=text,
            platforms=plats,
            image_path=image_path,
            schedule_time=schedule_time,
        )

        r = result.get("result", {})
        if isinstance(r, dict) and r.get("error"):
            return f"Error: {r['error']}"
        return f"Post enviado a {', '.join(result.get('platforms', []))}"


class ContentCalendarTool(BaseTool):
    name = "content_calendar"
    description = (
        "Genera un calendario de contenido para redes sociales. "
        "Planifica qué publicar, cuándo y en qué plataforma para mantener omnipresencia."
    )
    parameters = {
        "type": "object",
        "properties": {
            "topic": {
                "type": "string",
                "description": "Tema o nicho del contenido",
            },
            "days": {
                "type": "integer",
                "description": "Cantidad de días a planificar (default: 7)",
            },
            "platforms": {
                "type": "string",
                "description": "Plataformas a incluir separadas por coma",
            },
            "style": {
                "type": "string",
                "description": "Estilo de contenido (educativo, entretenimiento, motivacional, mixto)",
            },
        },
        "required": ["topic"],
    }

    def execute(
        self,
        topic: str,
        days: int = 7,
        platforms: str = "youtube,instagram,tiktok,x",
        style: str = "mixto",
    ) -> str:
        from inference_client import chat

        plats = [p.strip() for p in platforms.split(",") if p.strip()]

        prompt = (
            f"Creá un calendario de contenido de {days} días para las plataformas: {', '.join(plats)}.\n\n"
            f"**Tema/Nicho:** {topic}\n"
            f"**Estilo:** {style}\n\n"
            "Para cada día incluí:\n"
            "- Plataforma(s)\n"
            "- Tipo de contenido (video corto, reel, post, story, thread)\n"
            "- Título/hook\n"
            "- Descripción breve del contenido\n"
            "- Mejor horario para publicar\n"
            "- Hashtags sugeridos\n\n"
            "Estrategia: reutilizar contenido adaptándolo a cada plataforma (ej: un video largo de YouTube "
            "se corta en clips para TikTok/Reels, el hook se usa como tweet, etc).\n"
            "Mantener consistencia pero adaptar formato a cada plataforma."
        )

        messages = [
            {"role": "system", "content": "Sos un social media manager experto. Respondé en español."},
            {"role": "user", "content": prompt},
        ]
        return chat(messages)
