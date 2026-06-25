"""Pipeline completo: de video viral a video nuevo listo para subir."""

import logging
from pathlib import Path
from dataclasses import dataclass, field

from config import MEDIA_DOWNLOAD_DIR

logger = logging.getLogger(__name__)


@dataclass
class PipelineConfig:
    voice: str = "es-ar-male"
    voice_rate: str = "+5%"
    format: str = "vertical"
    music_volume: float = 0.1
    background_music: str = ""
    use_stock_footage: bool = True
    use_google_ai_images: bool = False
    use_google_ai_video: bool = False
    stock_query_override: str = ""
    tts_backend: str = ""
    clone_original_voice: bool = False
    require_approval: bool = True
    google_ai_scenes: int = 4


@dataclass
class PipelineResult:
    success: bool
    video_path: str = ""
    script: str = ""
    analysis: str = ""
    duration: float = 0.0
    error: str = ""
    steps_completed: list[str] = field(default_factory=list)
    awaiting_approval: bool = False


def replicate_viral(
    source_url: str,
    new_topic: str,
    config: PipelineConfig = None,
) -> PipelineResult:
    """Pipeline completo: analiza viral → investiga → reescribe → (aprueba) → genera video."""
    if config is None:
        config = PipelineConfig()

    result = PipelineResult(success=False)
    output_dir = Path(MEDIA_DOWNLOAD_DIR) / "pipeline"
    output_dir.mkdir(parents=True, exist_ok=True)

    # === PASO 1: Descargar y analizar video original ===
    logger.info("Paso 1: Descargando video original...")
    from media.downloader import download_media
    dl = download_media(source_url)
    if not dl.success:
        result.error = f"Error descargando video: {dl.error}"
        return result
    result.steps_completed.append("download")

    # === PASO 2: Transcribir audio ===
    transcript = ""
    if dl.audio_path:
        logger.info("Paso 2: Transcribiendo audio...")
        from media.transcriber import transcribe
        transcript = transcribe(dl.audio_path)
        result.steps_completed.append("transcribe")

    # === PASO 3: Analizar frames ===
    visual_descriptions = []
    if dl.video_path:
        logger.info("Paso 3: Analizando frames...")
        try:
            from media.vision import analyze_frames
            visual_descriptions = analyze_frames(dl.video_path, num_frames=4)
            result.steps_completed.append("vision")
        except Exception as e:
            logger.warning("Análisis visual falló (continuando sin él): %s", e)

    # === PASO 4: Análisis de estructura viral ===
    logger.info("Paso 4: Analizando estructura viral...")
    from video.analyzer import analyze_viral_video, generate_new_script
    analysis = analyze_viral_video(transcript, visual_descriptions)
    result.analysis = analysis
    result.steps_completed.append("analyze")

    # === PASO 5: Generar nuevo guión (con web research + validación) ===
    logger.info("Paso 5: Investigando tema y generando guión...")
    new_script = generate_new_script(analysis, new_topic)
    result.script = new_script
    result.steps_completed.append("script")

    # === PASO 5.5: Si requiere aprobación, retornar para review ===
    if config.require_approval:
        result.awaiting_approval = True
        result.success = True
        return result

    # === CONTINUAR con producción ===
    return _produce_video(result, config, output_dir, dl)


def produce_approved_video(
    script: str,
    topic: str,
    config: PipelineConfig = None,
) -> PipelineResult:
    """Produce el video final a partir de un guión ya aprobado."""
    if config is None:
        config = PipelineConfig()

    result = PipelineResult(success=False, script=script)
    result.steps_completed.append("script_approved")

    output_dir = Path(MEDIA_DOWNLOAD_DIR) / "pipeline"
    output_dir.mkdir(parents=True, exist_ok=True)

    return _produce_video(result, config, output_dir, dl_result=None, topic=topic)


def _produce_video(
    result: PipelineResult,
    config: PipelineConfig,
    output_dir: Path,
    dl_result=None,
    topic: str = "",
) -> PipelineResult:
    """Pasos de producción: TTS → visuals → ensamblaje."""
    script = result.script

    # === TTS ===
    logger.info("Generando voz...")
    from video.tts import generate_speech
    audio_output = str(output_dir / "narration.mp3")

    voice_ref = ""
    if config.clone_original_voice and dl_result and dl_result.audio_path:
        voice_ref = dl_result.audio_path
        logger.info("Clonando voz del video original con Voxtral")

    tts = generate_speech(
        script, audio_output,
        voice=config.voice,
        rate=config.voice_rate,
        backend=config.tts_backend,
        voice_reference_path=voice_ref,
    )
    if not tts.success:
        result.error = f"Error generando voz: {tts.error}"
        return result
    result.steps_completed.append("tts")

    # === VISUALS: Google AI o Stock Footage ===
    background_clips = []

    if config.use_google_ai_images:
        logger.info("Generando imágenes con Google AI...")
        try:
            from video.google_ai import generate_scene_images
            aspect = "9:16" if config.format == "vertical" else "16:9" if config.format == "horizontal" else "1:1"
            image_paths = generate_scene_images(script, num_scenes=config.google_ai_scenes, aspect_ratio=aspect)
            background_clips = image_paths
            if image_paths:
                result.steps_completed.append("google_ai_images")
        except Exception as e:
            logger.warning("Google AI images falló: %s", e)

    if config.use_google_ai_video:
        logger.info("Generando video con Google Veo...")
        try:
            from video.google_ai import generate_video
            aspect = "9:16" if config.format == "vertical" else "16:9" if config.format == "horizontal" else "1:1"
            video_result = generate_video(
                f"Cinematic video about: {topic or script[:200]}",
                aspect_ratio=aspect,
            )
            if video_result.success:
                background_clips = [video_result.video_path]
                result.steps_completed.append("google_ai_video")
        except Exception as e:
            logger.warning("Google Veo falló: %s", e)

    if config.use_stock_footage and not background_clips:
        logger.info("Buscando stock footage...")
        try:
            from video.stock import search_pexels_videos, search_pixabay_videos, download_clip
            query = config.stock_query_override or topic or "abstract background"
            clips = search_pexels_videos(query, per_page=3, orientation="portrait")
            if not clips:
                clips = search_pixabay_videos(query, per_page=3)

            clip_dir = str(output_dir / "clips")
            for clip in clips[:3]:
                local = download_clip(clip, clip_dir)
                if local:
                    background_clips.append(local)
            result.steps_completed.append("stock_footage")
        except Exception as e:
            logger.warning("Stock footage falló (usando fondo negro): %s", e)

    # === ENSAMBLAJE ===
    logger.info("Ensamblando video final...")
    from video.assembler import assemble_video, VideoProject

    safe_title = "".join(c for c in (topic or "video")[:30] if c.isalnum() or c in " -_")
    project = VideoProject(
        title=safe_title,
        audio_path=tts.audio_path,
        subtitle_path=tts.subtitle_path,
        background_clips=background_clips,
        background_music=config.background_music,
        music_volume=config.music_volume,
        format=config.format,
        output_path=str(output_dir / f"{safe_title}_final.mp4"),
    )

    assembly = assemble_video(project)
    if not assembly.success:
        result.error = f"Error ensamblando video: {assembly.error}"
        return result

    result.steps_completed.append("assemble")
    result.success = True
    result.video_path = assembly.output_path
    result.duration = assembly.duration
    result.awaiting_approval = False
    logger.info("Video generado exitosamente: %s", result.video_path)
    return result
