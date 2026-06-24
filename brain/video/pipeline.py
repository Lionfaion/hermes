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
    stock_query_override: str = ""
    tts_backend: str = ""
    clone_original_voice: bool = False


@dataclass
class PipelineResult:
    success: bool
    video_path: str = ""
    script: str = ""
    analysis: str = ""
    duration: float = 0.0
    error: str = ""
    steps_completed: list[str] = field(default_factory=list)


def replicate_viral(
    source_url: str,
    new_topic: str,
    config: PipelineConfig = None,
) -> PipelineResult:
    """Pipeline completo: analiza viral → reescribe → genera video."""
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

    # === PASO 5: Generar nuevo guión ===
    logger.info("Paso 5: Generando nuevo guión...")
    new_script = generate_new_script(analysis, new_topic)
    result.script = new_script
    result.steps_completed.append("script")

    # === PASO 6: Generar voz ===
    logger.info("Paso 6: Generando voz...")
    from video.tts import generate_speech
    audio_output = str(output_dir / "narration.mp3")

    voice_ref = ""
    if config.clone_original_voice and dl.audio_path:
        voice_ref = dl.audio_path
        logger.info("Clonando voz del video original con Voxtral")

    tts = generate_speech(
        new_script, audio_output,
        voice=config.voice,
        rate=config.voice_rate,
        backend=config.tts_backend,
        voice_reference_path=voice_ref,
    )
    if not tts.success:
        result.error = f"Error generando voz: {tts.error}"
        return result
    result.steps_completed.append("tts")

    # === PASO 7: Buscar stock footage (opcional) ===
    background_clips = []
    if config.use_stock_footage:
        logger.info("Paso 7: Buscando stock footage...")
        try:
            from video.stock import search_pexels_videos, search_pixabay_videos, download_clip
            query = config.stock_query_override or new_topic
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

    # === PASO 8: Ensamblar video ===
    logger.info("Paso 8: Ensamblando video final...")
    from video.assembler import assemble_video, VideoProject

    safe_title = "".join(c for c in new_topic[:30] if c.isalnum() or c in " -_")
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
    logger.info("Video generado exitosamente: %s", result.video_path)
    return result
