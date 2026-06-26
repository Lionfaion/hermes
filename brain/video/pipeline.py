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
    use_broll_replicate: bool = False
    use_heygen_avatar: bool = False
    stock_query_override: str = ""
    tts_backend: str = ""
    clone_original_voice: bool = False
    require_approval: bool = True
    google_ai_scenes: int = 4
    broll_scenes: int = 3
    heygen_avatar_id: str = ""
    heygen_voice_id: str = ""
    burn_captions: bool = False
    caption_style: str = "karaoke"
    run_qc: bool = True


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
    job_id: str = ""
    qc_report: str = ""


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

    from video.job_manager import create_job, update_stage, complete_step, fail_job
    job = create_job(new_topic, config={"source_url": source_url, "format": config.format})
    result.job_id = job.job_id

    # === PASO 1: Descargar y analizar video original ===
    logger.info("Paso 1: Descargando video original...")
    update_stage(job, "download")
    from media.downloader import download_media
    dl = download_media(source_url)
    if not dl.success:
        result.error = f"Error descargando video: {dl.error}"
        fail_job(job, result.error)
        return result
    result.steps_completed.append("download")
    complete_step(job, "download")

    # === PASO 2: Transcribir audio ===
    transcript = ""
    if dl.audio_path:
        logger.info("Paso 2: Transcribiendo audio...")
        update_stage(job, "transcribe")
        from media.transcriber import transcribe
        transcript = transcribe(dl.audio_path)
        result.steps_completed.append("transcribe")
        complete_step(job, "transcribe")

    # === PASO 3: Analizar frames ===
    visual_descriptions = []
    if dl.video_path:
        logger.info("Paso 3: Analizando frames...")
        try:
            from media.vision import analyze_frames
            visual_descriptions = analyze_frames(dl.video_path, num_frames=4)
            result.steps_completed.append("vision")
            complete_step(job, "vision")
        except Exception as e:
            logger.warning("Análisis visual falló (continuando sin él): %s", e)

    # === PASO 4: Análisis de estructura viral ===
    logger.info("Paso 4: Analizando estructura viral...")
    update_stage(job, "analyze")
    from video.analyzer import analyze_viral_video, generate_new_script
    analysis = analyze_viral_video(transcript, visual_descriptions)
    result.analysis = analysis
    result.steps_completed.append("analyze")
    complete_step(job, "analyze")

    # === PASO 5: Generar nuevo guión (con web research + validación) ===
    logger.info("Paso 5: Investigando tema y generando guión...")
    update_stage(job, "script")
    new_script = generate_new_script(analysis, new_topic)
    result.script = new_script
    result.steps_completed.append("script")
    complete_step(job, "script")

    # === PASO 5.5: Si requiere aprobación, retornar para review ===
    if config.require_approval:
        result.awaiting_approval = True
        result.success = True
        update_stage(job, "awaiting_approval", status="paused")
        return result

    # === CONTINUAR con producción ===
    return _produce_video(result, config, output_dir, dl, job=job)


def produce_approved_video(
    script: str,
    topic: str,
    config: PipelineConfig = None,
    job_id: str = "",
) -> PipelineResult:
    """Produce el video final a partir de un guión ya aprobado."""
    if config is None:
        config = PipelineConfig()

    result = PipelineResult(success=False, script=script)
    result.steps_completed.append("script_approved")

    output_dir = Path(MEDIA_DOWNLOAD_DIR) / "pipeline"
    output_dir.mkdir(parents=True, exist_ok=True)

    from video.job_manager import load_job, create_job, complete_step
    job = None
    if job_id:
        job = load_job(job_id)
    if not job:
        job = create_job(topic, config={"format": config.format})
    result.job_id = job.job_id
    complete_step(job, "script_approved")

    return _produce_video(result, config, output_dir, dl_result=None, topic=topic, job=job)


def _produce_video(
    result: PipelineResult,
    config: PipelineConfig,
    output_dir: Path,
    dl_result=None,
    topic: str = "",
    job=None,
) -> PipelineResult:
    """Pasos de producción: TTS → visuals → ensamblaje → captions → QC."""
    from video.job_manager import update_stage, complete_step, add_artifact, fail_job, complete_job

    script = result.script

    # === HEYGEN AVATAR (si está habilitado, genera el video completo con avatar) ===
    if config.use_heygen_avatar:
        logger.info("Generando video con HeyGen avatar...")
        if job:
            update_stage(job, "heygen_avatar")
        try:
            from video.heygen import generate_avatar_video
            aspect = "9:16" if config.format == "vertical" else "16:9" if config.format == "horizontal" else "1:1"
            avatar_result = generate_avatar_video(
                script,
                avatar_id=config.heygen_avatar_id,
                voice_id=config.heygen_voice_id,
                aspect_ratio=aspect,
            )
            if avatar_result.success:
                result.video_path = avatar_result.video_path
                result.duration = avatar_result.duration
                result.steps_completed.append("heygen_avatar")
                if job:
                    complete_step(job, "heygen_avatar")
                    add_artifact(job, "video", avatar_result.video_path)

                if config.run_qc:
                    result.qc_report = _run_qc(result.video_path, job)

                result.success = True
                result.awaiting_approval = False
                if job:
                    complete_job(job)
                return result
            else:
                logger.warning("HeyGen falló, continuando con pipeline estándar: %s", avatar_result.error)
        except Exception as e:
            logger.warning("HeyGen falló: %s", e)

    # === TTS ===
    logger.info("Generando voz...")
    if job:
        update_stage(job, "tts")
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
        if job:
            fail_job(job, result.error)
        return result
    result.steps_completed.append("tts")
    if job:
        complete_step(job, "tts")
        add_artifact(job, "audio", tts.audio_path)

    # === VISUALS ===
    background_clips = []

    # B-Roll via Replicate/Seedance
    if config.use_broll_replicate:
        logger.info("Generando b-roll con Replicate Seedance...")
        if job:
            update_stage(job, "broll")
        try:
            from video.broll import generate_scene_broll
            aspect = "9:16" if config.format == "vertical" else "16:9" if config.format == "horizontal" else "1:1"
            broll_paths = generate_scene_broll(
                script, num_scenes=config.broll_scenes,
                aspect_ratio=aspect, use_replicate=True,
            )
            background_clips = broll_paths
            if broll_paths:
                result.steps_completed.append("broll_replicate")
                if job:
                    complete_step(job, "broll_replicate")
                    for p in broll_paths:
                        add_artifact(job, "broll", p)
        except Exception as e:
            logger.warning("B-roll Replicate falló: %s", e)

    # Google AI Images
    if config.use_google_ai_images and not background_clips:
        logger.info("Generando imágenes con Google AI...")
        try:
            from video.google_ai import generate_scene_images
            aspect = "9:16" if config.format == "vertical" else "16:9" if config.format == "horizontal" else "1:1"
            image_paths = generate_scene_images(script, num_scenes=config.google_ai_scenes, aspect_ratio=aspect)
            background_clips = image_paths
            if image_paths:
                result.steps_completed.append("google_ai_images")
                if job:
                    complete_step(job, "google_ai_images")
        except Exception as e:
            logger.warning("Google AI images falló: %s", e)

    # Google AI Video
    if config.use_google_ai_video and not background_clips:
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
                if job:
                    complete_step(job, "google_ai_video")
        except Exception as e:
            logger.warning("Google Veo falló: %s", e)

    # Stock footage (fallback)
    if config.use_stock_footage and not background_clips:
        logger.info("Buscando stock footage...")
        if job:
            update_stage(job, "stock_footage")
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
            if job:
                complete_step(job, "stock_footage")
        except Exception as e:
            logger.warning("Stock footage falló (usando fondo negro): %s", e)

    # B-roll local (último fallback si no hay nada)
    if not background_clips:
        logger.info("Generando b-roll local como fallback...")
        try:
            from video.broll import generate_broll_local
            broll = generate_broll_local(topic or "video")
            if broll.success:
                background_clips = [broll.video_path]
                result.steps_completed.append("broll_local")
                if job:
                    complete_step(job, "broll_local")
        except Exception as e:
            logger.warning("B-roll local falló: %s", e)

    # === ENSAMBLAJE ===
    logger.info("Ensamblando video final...")
    if job:
        update_stage(job, "assemble")
    from video.assembler import assemble_video, VideoProject

    safe_title = "".join(c for c in (topic or "video")[:30] if c.isalnum() or c in " -_")
    project = VideoProject(
        title=safe_title,
        audio_path=tts.audio_path,
        subtitle_path=tts.subtitle_path if not config.burn_captions else "",
        background_clips=background_clips,
        background_music=config.background_music,
        music_volume=config.music_volume,
        format=config.format,
        output_path=str(output_dir / f"{safe_title}_final.mp4"),
    )

    assembly = assemble_video(project)
    if not assembly.success:
        result.error = f"Error ensamblando video: {assembly.error}"
        if job:
            fail_job(job, result.error)
        return result

    result.steps_completed.append("assemble")
    result.video_path = assembly.output_path
    result.duration = assembly.duration
    if job:
        complete_step(job, "assemble")
        add_artifact(job, "video", assembly.output_path)

    # === BURN CAPTIONS (si se pide ASS karaoke en vez de SRT) ===
    if config.burn_captions and result.video_path:
        logger.info("Quemando subtítulos karaoke en el video...")
        if job:
            update_stage(job, "captions")
        try:
            from video.captioner import add_captions_to_video
            caption_result = add_captions_to_video(
                result.video_path,
                style=config.caption_style,
            )
            if caption_result.success:
                result.video_path = caption_result.output_path
                result.steps_completed.append("captions")
                if job:
                    complete_step(job, "captions")
                    add_artifact(job, "captioned_video", caption_result.output_path)
        except Exception as e:
            logger.warning("Caption burn falló: %s", e)

    # === QC ===
    if config.run_qc and result.video_path:
        result.qc_report = _run_qc(result.video_path, job)

    result.success = True
    result.awaiting_approval = False
    if job:
        complete_job(job)
    logger.info("Video generado exitosamente: %s", result.video_path)
    return result


def _run_qc(video_path: str, job=None) -> str:
    """Run QC on the final video."""
    try:
        from video.qc import probe_video, format_qc_report
        from video.job_manager import complete_step
        qc = probe_video(video_path)
        report = format_qc_report(qc)
        if job:
            complete_step(job, "qc")
        return report
    except Exception as e:
        logger.warning("QC falló: %s", e)
        return ""
