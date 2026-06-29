"""Herramientas de creación de video para el sistema de tool calling."""

from tools.base import BaseTool


class ReplicateViralTool(BaseTool):
    name = "replicate_viral"
    description = (
        "Analiza un video viral, investiga el tema en internet, genera un guión nuevo, "
        "y te lo muestra para aprobación ANTES de producir el video. "
        "Si el usuario aprueba, usá 'produce_video' con el guión aprobado. "
        "Úsala cuando el usuario quiera replicar un video viral."
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
            "skip_approval": {
                "type": "boolean",
                "description": "Si es true, no pide aprobación y produce el video directamente",
            },
            "visual_mode": {
                "type": "string",
                "description": "Fuente de visuales: 'stock' (gratis), 'pollinations_images' (gratis IA), 'pollinations_video' (gratis IA), 'broll' (Replicate), 'google_images', 'google_video', 'heygen', 'sadtalker' (gratis avatar local)",
                "enum": ["stock", "pollinations_images", "pollinations_video", "broll", "google_images", "google_video", "heygen", "sadtalker"],
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
        skip_approval: bool = False,
        visual_mode: str = "stock",
    ) -> str:
        from video.pipeline import replicate_viral, PipelineConfig

        config = PipelineConfig(
            voice=voice,
            format=format,
            tts_backend=tts_backend if tts_backend else "",
            clone_original_voice=clone_voice,
            require_approval=not skip_approval,
            use_stock_footage=visual_mode == "stock",
            use_pollinations_images=visual_mode == "pollinations_images",
            use_pollinations_video=visual_mode == "pollinations_video",
            use_google_ai_images=visual_mode == "google_images",
            use_google_ai_video=visual_mode == "google_video",
            use_broll_replicate=visual_mode == "broll",
            use_heygen_avatar=visual_mode == "heygen",
            use_sadtalker_avatar=visual_mode == "sadtalker",
        )
        result = replicate_viral(source_url, new_topic, config)

        if result.awaiting_approval:
            return (
                f"**Guión generado para aprobación:**\n\n"
                f"{result.script}\n\n"
                f"---\n"
                f"Job ID: {result.job_id}\n"
                f"Pasos completados: {', '.join(result.steps_completed)}\n\n"
                f"¿Te gusta este guión? Si querés que lo produzca, decime 'dale, producilo' "
                f"o 'aprobado'. Si querés cambios, decime qué modificar."
            )

        if result.success:
            msg = (
                f"Video generado exitosamente!\n"
                f"Ruta: {result.video_path}\n"
                f"Duración: {result.duration:.1f}s\n"
                f"Job ID: {result.job_id}\n"
                f"Pasos: {', '.join(result.steps_completed)}"
            )
            if result.qc_report:
                msg += f"\n\n{result.qc_report}"
            return msg
        return f"Error en el pipeline: {result.error}\nPasos: {', '.join(result.steps_completed)}"


class ProduceVideoTool(BaseTool):
    name = "produce_video"
    description = (
        "Produce un video a partir de un guión ya aprobado por el usuario. "
        "Genera TTS, busca/genera visuales, y ensambla el video final. "
        "Úsala después de que el usuario apruebe un guión de 'replicate_viral'."
    )
    parameters = {
        "type": "object",
        "properties": {
            "script": {
                "type": "string",
                "description": "Guión aprobado para producir",
            },
            "topic": {
                "type": "string",
                "description": "Tema del video (para búsqueda de visuales y nombre de archivo)",
            },
            "voice": {
                "type": "string",
                "description": "Voz a usar",
            },
            "format": {
                "type": "string",
                "description": "Formato: vertical, horizontal, square",
                "enum": ["vertical", "horizontal", "square"],
            },
            "tts_backend": {
                "type": "string",
                "description": "Motor de voz: 'edge' o 'voxtral'",
                "enum": ["edge", "voxtral"],
            },
            "visual_mode": {
                "type": "string",
                "description": "Fuente de visuales: 'stock' (gratis), 'pollinations_images' (gratis IA), 'pollinations_video' (gratis IA), 'broll' (Replicate), 'google_images', 'google_video', 'heygen', 'sadtalker' (gratis avatar local)",
                "enum": ["stock", "pollinations_images", "pollinations_video", "broll", "google_images", "google_video", "heygen", "sadtalker"],
            },
            "stock_query": {
                "type": "string",
                "description": "Búsqueda para stock footage (en inglés)",
            },
            "burn_captions": {
                "type": "boolean",
                "description": "Si es true, quema subtítulos karaoke (ASS) en el video",
            },
            "job_id": {
                "type": "string",
                "description": "ID del job previo (para retomar pipeline)",
            },
        },
        "required": ["script", "topic"],
    }

    def execute(
        self,
        script: str,
        topic: str,
        voice: str = "es-ar-male",
        format: str = "vertical",
        tts_backend: str = "",
        visual_mode: str = "stock",
        stock_query: str = "",
        burn_captions: bool = False,
        job_id: str = "",
    ) -> str:
        from video.pipeline import produce_approved_video, PipelineConfig

        config = PipelineConfig(
            voice=voice,
            format=format,
            tts_backend=tts_backend if tts_backend else "",
            require_approval=False,
            use_stock_footage=visual_mode == "stock",
            use_pollinations_images=visual_mode == "pollinations_images",
            use_pollinations_video=visual_mode == "pollinations_video",
            use_google_ai_images=visual_mode == "google_images",
            use_google_ai_video=visual_mode == "google_video",
            use_broll_replicate=visual_mode == "broll",
            use_heygen_avatar=visual_mode == "heygen",
            use_sadtalker_avatar=visual_mode == "sadtalker",
            stock_query_override=stock_query,
            burn_captions=burn_captions,
        )
        result = produce_approved_video(script, topic, config, job_id=job_id)

        if result.success:
            msg = (
                f"Video producido exitosamente!\n"
                f"Ruta: {result.video_path}\n"
                f"Duración: {result.duration:.1f}s\n"
                f"Job ID: {result.job_id}\n"
                f"Pasos: {', '.join(result.steps_completed)}"
            )
            if result.qc_report:
                msg += f"\n\n{result.qc_report}"
            return msg
        return f"Error produciendo video: {result.error}\nPasos: {', '.join(result.steps_completed)}"


class GenerateVideoTool(BaseTool):
    name = "generate_video"
    description = (
        "Genera un video desde cero a partir de un guión. Crea la voz con TTS, "
        "busca stock footage o genera imágenes/b-roll con IA, y ensambla el video final. "
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
            "visual_mode": {
                "type": "string",
                "description": "Fuente de visuales: 'stock' (gratis), 'pollinations_images' (gratis IA), 'pollinations_video' (gratis IA), 'broll' (Replicate), 'google_images', 'google_video', 'heygen', 'sadtalker' (gratis avatar local)",
                "enum": ["stock", "pollinations_images", "pollinations_video", "broll", "google_images", "google_video", "heygen", "sadtalker"],
            },
            "burn_captions": {
                "type": "boolean",
                "description": "Si es true, quema subtítulos karaoke (ASS) en el video",
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
        visual_mode: str = "stock",
        burn_captions: bool = False,
    ) -> str:
        from video.pipeline import produce_approved_video, PipelineConfig

        config = PipelineConfig(
            voice=voice,
            format=format,
            tts_backend=tts_backend if tts_backend else "",
            require_approval=False,
            use_stock_footage=visual_mode == "stock",
            use_pollinations_images=visual_mode == "pollinations_images",
            use_pollinations_video=visual_mode == "pollinations_video",
            use_google_ai_images=visual_mode == "google_images",
            use_google_ai_video=visual_mode == "google_video",
            use_broll_replicate=visual_mode == "broll",
            use_heygen_avatar=visual_mode == "heygen",
            use_sadtalker_avatar=visual_mode == "sadtalker",
            stock_query_override=stock_query,
            clone_original_voice=bool(voice_reference_path),
            burn_captions=burn_captions,
        )
        result = produce_approved_video(script, title, config)

        if result.success:
            msg = (
                f"Video generado: {result.video_path}\n"
                f"Duración: {result.duration:.1f}s\n"
                f"Job ID: {result.job_id}\n"
                f"Pasos: {', '.join(result.steps_completed)}"
            )
            if result.qc_report:
                msg += f"\n\n{result.qc_report}"
            return msg
        return f"Error: {result.error}\nPasos: {', '.join(result.steps_completed)}"


class GenerateImageTool(BaseTool):
    name = "generate_image"
    description = (
        "Genera imágenes con Google AI (Imagen). Crea imágenes de alta calidad "
        "a partir de una descripción textual. Úsala cuando el usuario quiera "
        "generar imágenes, thumbnails, o visuales."
    )
    parameters = {
        "type": "object",
        "properties": {
            "prompt": {
                "type": "string",
                "description": "Descripción de la imagen a generar (en inglés es mejor)",
            },
            "aspect_ratio": {
                "type": "string",
                "description": "Relación de aspecto: 9:16 (vertical), 16:9 (horizontal), 1:1 (cuadrado)",
                "enum": ["9:16", "16:9", "1:1", "4:3", "3:4"],
            },
            "count": {
                "type": "integer",
                "description": "Cantidad de imágenes a generar (1-4)",
            },
        },
        "required": ["prompt"],
    }

    def execute(self, prompt: str, aspect_ratio: str = "9:16", count: int = 1) -> str:
        from video.google_ai import generate_image
        results = generate_image(prompt, aspect_ratio=aspect_ratio, number_of_images=min(count, 4))

        successful = [r for r in results if r.success]
        if successful:
            paths = "\n".join(f"- {r.image_path}" for r in successful)
            return f"Imágenes generadas ({len(successful)}):\n{paths}"
        return f"Error generando imágenes: {results[0].error if results else 'desconocido'}"


class GenerateBrollTool(BaseTool):
    name = "generate_broll"
    description = (
        "Genera clips de b-roll (video de fondo) con IA usando Replicate Seedance 2.0. "
        "Si Replicate no está disponible, usa generación local con animaciones procedurales. "
        "Úsala cuando necesites clips cortos de video para fondos, transiciones o complementar narración."
    )
    parameters = {
        "type": "object",
        "properties": {
            "prompt": {
                "type": "string",
                "description": "Descripción del clip a generar (en inglés es mejor)",
            },
            "duration": {
                "type": "integer",
                "description": "Duración del clip en segundos (default 5)",
            },
            "aspect_ratio": {
                "type": "string",
                "description": "Relación de aspecto",
                "enum": ["9:16", "16:9", "1:1"],
            },
        },
        "required": ["prompt"],
    }

    def execute(self, prompt: str, duration: int = 5, aspect_ratio: str = "9:16") -> str:
        from video.broll import generate_broll_replicate, generate_broll_local, REPLICATE_API_TOKEN

        if REPLICATE_API_TOKEN:
            result = generate_broll_replicate(prompt, duration=duration, aspect_ratio=aspect_ratio)
        else:
            result = generate_broll_local(prompt)

        if result.success:
            return (
                f"B-roll generado!\n"
                f"Ruta: {result.video_path}\n"
                f"Duración: {result.duration:.1f}s\n"
                f"Fuente: {result.source}"
            )
        return f"Error generando b-roll: {result.error}"


class HeyGenAvatarTool(BaseTool):
    name = "heygen_avatar"
    description = (
        "Genera un video con avatar sintético usando HeyGen. "
        "El avatar habla el texto que le pases con labios sincronizados. "
        "Requiere HEYGEN_API_KEY. Úsala para crear videos con presentador virtual."
    )
    parameters = {
        "type": "object",
        "properties": {
            "script": {
                "type": "string",
                "description": "Texto que el avatar va a decir",
            },
            "avatar_id": {
                "type": "string",
                "description": "ID del avatar HeyGen (vacío para usar el default)",
            },
            "voice_id": {
                "type": "string",
                "description": "ID de la voz HeyGen (vacío para usar el default)",
            },
            "aspect_ratio": {
                "type": "string",
                "description": "Relación de aspecto del video",
                "enum": ["9:16", "16:9", "1:1"],
            },
        },
        "required": ["script"],
    }

    def execute(
        self, script: str, avatar_id: str = "", voice_id: str = "", aspect_ratio: str = "9:16"
    ) -> str:
        from video.heygen import generate_avatar_video
        result = generate_avatar_video(script, avatar_id=avatar_id, voice_id=voice_id, aspect_ratio=aspect_ratio)

        if result.success:
            return (
                f"Video con avatar generado!\n"
                f"Ruta: {result.video_path}\n"
                f"Duración: {result.duration:.1f}s"
            )
        return f"Error con HeyGen: {result.error}"


class AddCaptionsTool(BaseTool):
    name = "add_captions"
    description = (
        "Agrega subtítulos quemados a un video existente. Transcribe el audio con Whisper, "
        "genera subtítulos ASS con estilo karaoke, y los quema en el video. "
        "Úsala para agregar captions a cualquier video."
    )
    parameters = {
        "type": "object",
        "properties": {
            "video_path": {
                "type": "string",
                "description": "Ruta al video al que agregar subtítulos",
            },
            "style": {
                "type": "string",
                "description": "Estilo de subtítulos: 'karaoke' (grande, bold) o 'standard' (normal)",
                "enum": ["karaoke", "standard"],
            },
        },
        "required": ["video_path"],
    }

    def execute(self, video_path: str, style: str = "karaoke") -> str:
        from video.captioner import add_captions_to_video
        result = add_captions_to_video(video_path, style=style)

        if result.success:
            return (
                f"Subtítulos agregados!\n"
                f"Video: {result.output_path}\n"
                f"Segmentos detectados: {len(result.segments)}"
            )
        return f"Error agregando subtítulos: {result.error}"


class VideoQCTool(BaseTool):
    name = "video_qc"
    description = (
        "Valida la calidad técnica de un video: resolución, codec, duración, frames negros, "
        "y compatibilidad con plataformas (TikTok, Reels, Shorts, YouTube). "
        "Úsala antes de publicar para asegurarte que el video cumple los requisitos."
    )
    parameters = {
        "type": "object",
        "properties": {
            "video_path": {
                "type": "string",
                "description": "Ruta al video a validar",
            },
        },
        "required": ["video_path"],
    }

    def execute(self, video_path: str) -> str:
        from video.qc import probe_video, format_qc_report
        result = probe_video(video_path)
        return format_qc_report(result)


class ListVideoJobsTool(BaseTool):
    name = "list_video_jobs"
    description = (
        "Lista los trabajos de video recientes con su estado y progreso. "
        "Úsala para ver qué videos se generaron, cuáles están en progreso o fallaron."
    )
    parameters = {
        "type": "object",
        "properties": {
            "limit": {
                "type": "integer",
                "description": "Cantidad máxima de jobs a mostrar",
            },
        },
    }

    def execute(self, limit: int = 10) -> str:
        from video.job_manager import list_jobs
        jobs = list_jobs(limit=limit)
        if not jobs:
            return "No hay video jobs registrados."

        lines = [f"**Video Jobs ({len(jobs)}):**\n"]
        for job in jobs:
            status_icon = {"completed": "OK", "failed": "FAIL", "paused": "PAUSA", "in_progress": "..."}.get(job.status, "?")
            lines.append(
                f"- [{status_icon}] {job.job_id}: {job.topic[:40]} "
                f"(stage: {job.stage}, pasos: {len(job.steps_completed)})"
            )
        return "\n".join(lines)


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
