"""Herramientas de creación de video para el sistema de tool calling."""

from tools.base import BaseTool


class ReplicateViralTool(BaseTool):
    name = "replicate_viral"
    description = (
        "Analiza un video viral, extrae su estructura, genera un guión nuevo sobre otro tema, "
        "crea la voz con TTS, busca stock footage, y ensambla un video listo para subir. "
        "Úsala cuando el usuario quiera replicar un video viral o crear contenido basado en uno."
    )
    parameters = {
        "type": "object",
        "properties": {
            "source_url": {
                "type": "string",
                "description": "URL del video viral a analizar (Instagram, TikTok, YouTube, etc.)",
            },
            "new_topic": {
                "type": "string",
                "description": "Tema/contenido para el nuevo video",
            },
            "voice": {
                "type": "string",
                "description": "Voz a usar (es-ar-male, casual-male, alloy, etc.)",
            },
            "format": {
                "type": "string",
                "description": "Formato: vertical (TikTok/Reels), horizontal (YouTube), square (Instagram)",
                "enum": ["vertical", "horizontal", "square"],
            },
            "tts_backend": {
                "type": "string",
                "description": "Motor de voz: 'edge' (gratis) o 'voxtral' (premium + clonación)",
                "enum": ["edge", "voxtral"],
            },
            "clone_voice": {
                "type": "boolean",
                "description": "Si es true, clona la voz del video original (requiere Voxtral/Mistral API key)",
            },
        },
        "required": ["source_url", "new_topic"],
    }

    def execute(
        self,
        source_url: str,
        new_topic: str,
        voice: str = "es-ar-male",
        format: str = "vertical",
        tts_backend: str = "",
        clone_voice: bool = False,
    ) -> str:
        from video.pipeline import replicate_viral, PipelineConfig

        config = PipelineConfig(
            voice=voice,
            format=format,
            tts_backend=tts_backend if tts_backend else "",
            clone_original_voice=clone_voice,
        )
        result = replicate_viral(source_url, new_topic, config)

        if result.success:
            return (
                f"Video generado exitosamente!\n"
                f"Ruta: {result.video_path}\n"
                f"Duración: {result.duration:.1f}s\n"
                f"Pasos completados: {', '.join(result.steps_completed)}\n\n"
                f"Guión generado:\n{result.script}"
            )
        return f"Error en el pipeline: {result.error}\nPasos completados: {', '.join(result.steps_completed)}"


class GenerateVideoTool(BaseTool):
    name = "generate_video"
    description = (
        "Genera un video desde cero a partir de un guión. Crea la voz con TTS, "
        "busca stock footage, y ensambla el video final. "
        "Úsala cuando el usuario ya tenga un guión o quiera crear un video desde texto."
    )
    parameters = {
        "type": "object",
        "properties": {
            "script": {
                "type": "string",
                "description": "Guión/texto que se va a narrar en el video",
            },
            "title": {
                "type": "string",
                "description": "Título del video (para el nombre del archivo)",
            },
            "voice": {
                "type": "string",
                "description": "Voz a usar (es-ar-male, casual-male, alloy, etc.)",
            },
            "format": {
                "type": "string",
                "description": "Formato: vertical, horizontal, square",
                "enum": ["vertical", "horizontal", "square"],
            },
            "stock_query": {
                "type": "string",
                "description": "Búsqueda para stock footage de fondo (en inglés preferido)",
            },
            "tts_backend": {
                "type": "string",
                "description": "Motor de voz: 'edge' (gratis) o 'voxtral' (premium + clonación)",
                "enum": ["edge", "voxtral"],
            },
            "voice_reference_path": {
                "type": "string",
                "description": "Ruta a audio de referencia para clonar voz (solo Voxtral, 2-25 seg)",
            },
        },
        "required": ["script", "title"],
    }

    def execute(
        self,
        script: str,
        title: str,
        voice: str = "es-ar-male",
        format: str = "vertical",
        stock_query: str = "",
        tts_backend: str = "",
        voice_reference_path: str = "",
    ) -> str:
        from pathlib import Path
        from config import MEDIA_DOWNLOAD_DIR

        output_dir = Path(MEDIA_DOWNLOAD_DIR) / "pipeline"
        output_dir.mkdir(parents=True, exist_ok=True)

        from video.tts import generate_speech
        audio_path = str(output_dir / "narration.mp3")
        tts = generate_speech(
            script, audio_path,
            voice=voice,
            backend=tts_backend or "",
            voice_reference_path=voice_reference_path,
        )
        if not tts.success:
            return f"Error generando voz: {tts.error}"

        background_clips = []
        if stock_query:
            try:
                from video.stock import search_pexels_videos, download_clip
                clips = search_pexels_videos(stock_query, per_page=3)
                clip_dir = str(output_dir / "clips")
                for clip in clips[:3]:
                    local = download_clip(clip, clip_dir)
                    if local:
                        background_clips.append(local)
            except Exception:
                pass

        from video.assembler import assemble_video, VideoProject

        safe_title = "".join(c for c in title[:30] if c.isalnum() or c in " -_")
        project = VideoProject(
            title=safe_title,
            audio_path=tts.audio_path,
            subtitle_path=tts.subtitle_path,
            background_clips=background_clips,
            format=format,
            output_path=str(output_dir / f"{safe_title}_final.mp4"),
        )

        result = assemble_video(project)
        if result.success:
            return (
                f"Video generado: {result.output_path}\n"
                f"Duración: {result.duration:.1f}s\n"
                f"Backend voz: {tts.backend}"
            )
        return f"Error ensamblando: {result.error}"


class CloneVoiceTool(BaseTool):
    name = "clone_voice"
    description = (
        "Clona una voz a partir de un audio de referencia (2-25 segundos) usando Voxtral TTS de Mistral. "
        "Genera audio con esa voz clonada diciendo el texto que le pases. "
        "Requiere MISTRAL_API_KEY. Soporta clonación cross-lingual (referencia en un idioma, output en otro)."
    )
    parameters = {
        "type": "object",
        "properties": {
            "text": {
                "type": "string",
                "description": "Texto que la voz clonada debe decir",
            },
            "reference_audio_path": {
                "type": "string",
                "description": "Ruta al archivo de audio con la voz a clonar (2-25 segundos, un solo hablante)",
            },
            "output_path": {
                "type": "string",
                "description": "Ruta donde guardar el audio generado (opcional)",
            },
        },
        "required": ["text", "reference_audio_path"],
    }

    def execute(self, text: str, reference_audio_path: str, output_path: str = "") -> str:
        from pathlib import Path
        from config import MEDIA_DOWNLOAD_DIR

        if not output_path:
            out_dir = Path(MEDIA_DOWNLOAD_DIR) / "cloned_voices"
            out_dir.mkdir(parents=True, exist_ok=True)
            output_path = str(out_dir / "cloned_output.mp3")

        from video.tts import clone_voice
        result = clone_voice(text, output_path, reference_audio_path)

        if result.success:
            return (
                f"Voz clonada exitosamente!\n"
                f"Audio: {result.audio_path}\n"
                f"Duración: {result.duration:.1f}s"
            )
        return f"Error clonando voz: {result.error}"


class AnalyzeViralTool(BaseTool):
    name = "analyze_viral"
    description = (
        "Analiza un video viral para extraer su estructura, hooks, estilo y patrones. "
        "No genera video nuevo, solo analiza. Úsala cuando el usuario quiera entender "
        "por qué un video es viral o quiera ideas."
    )
    parameters = {
        "type": "object",
        "properties": {
            "url": {
                "type": "string",
                "description": "URL del video viral a analizar",
            },
        },
        "required": ["url"],
    }

    def execute(self, url: str) -> str:
        from media.downloader import download_media
        dl = download_media(url)
        if not dl.success:
            return f"Error descargando: {dl.error}"

        transcript = ""
        if dl.audio_path:
            from media.transcriber import transcribe
            transcript = transcribe(dl.audio_path)

        visual_descriptions = []
        if dl.video_path:
            try:
                from media.vision import analyze_frames
                visual_descriptions = analyze_frames(dl.video_path, num_frames=4)
            except Exception:
                pass

        from video.analyzer import analyze_viral_video
        return analyze_viral_video(transcript, visual_descriptions)
