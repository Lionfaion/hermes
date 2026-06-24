"""Herramienta de análisis de videos y audio (Instagram, YouTube, TikTok, etc.)."""

from tools.base import BaseTool


class AnalyzeMediaTool(BaseTool):
    name = "analyze_media"
    description = (
        "Descarga y analiza un video o audio de internet (Instagram, YouTube, TikTok, etc.). "
        "Puede transcribir el audio y/o analizar los frames del video. "
        "Úsala cuando el usuario te pase un link de video o te pida analizar contenido multimedia."
    )
    parameters = {
        "type": "object",
        "properties": {
            "url": {
                "type": "string",
                "description": "URL del video/audio a analizar",
            },
            "transcribe": {
                "type": "boolean",
                "description": "Transcribir el audio del video (default true)",
            },
            "analyze_frames": {
                "type": "boolean",
                "description": "Analizar frames del video con visión AI (default true)",
            },
        },
        "required": ["url"],
    }

    def execute(self, url: str, transcribe: bool = True, analyze_frames: bool = True) -> str:
        parts = []

        from media.downloader import download_media
        dl = download_media(url)
        if not dl.success:
            return f"Error descargando media: {dl.error}"

        parts.append(f"Título: {dl.title}")
        parts.append(f"Duración: {dl.duration}s")

        if transcribe and dl.audio_path:
            from media.transcriber import transcribe as do_transcribe
            transcript = do_transcribe(dl.audio_path)
            if transcript:
                parts.append(f"\n[Transcripción]\n{transcript}")
            else:
                parts.append("\n[No se pudo transcribir el audio]")

        if analyze_frames and dl.video_path:
            from media.vision import analyze_frames as do_analyze
            descriptions = do_analyze(dl.video_path)
            if descriptions:
                parts.append("\n[Análisis visual]")
                for i, desc in enumerate(descriptions, 1):
                    parts.append(f"Frame {i}: {desc}")

        return "\n".join(parts)
