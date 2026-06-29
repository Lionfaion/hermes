"""Multi-agent Kanban video pipeline: Director → Cinematographer → Renderers → Editor.

Inspired by NousResearch/kanban-video-pipeline. Four specialized agents
collaborate through a task board to produce videos autonomously.
"""

import json
import logging
import time
from dataclasses import dataclass, field
from pathlib import Path

from inference_client import chat
from config import OLLAMA_MODEL, MEDIA_DOWNLOAD_DIR

logger = logging.getLogger(__name__)


@dataclass
class KanbanTask:
    id: str
    title: str
    agent: str
    status: str = "todo"  # todo, in_progress, done, failed
    input_data: dict = field(default_factory=dict)
    output_data: dict = field(default_factory=dict)
    dependencies: list[str] = field(default_factory=list)


@dataclass
class KanbanBoard:
    project_name: str
    tasks: list[KanbanTask] = field(default_factory=list)
    artifacts: list[str] = field(default_factory=list)
    final_video: str = ""


def produce_kanban_video(
    brief: str,
    format: str = "vertical",
    model: str = "",
) -> KanbanBoard:
    """Full autonomous pipeline: brief → decompose → render → assemble."""
    model = model or OLLAMA_MODEL
    board = KanbanBoard(project_name=brief[:50])
    output_dir = Path(MEDIA_DOWNLOAD_DIR) / "kanban" / f"project_{int(time.time())}"
    output_dir.mkdir(parents=True, exist_ok=True)

    # === STAGE 1: DIRECTOR — decompose brief into tasks ===
    logger.info("[Director] Descomponiendo brief...")
    shot_list = _director_decompose(brief, format, model)
    board.tasks.append(KanbanTask(
        id="director_plan", title="Plan de producción",
        agent="director", status="done",
        output_data={"shot_list": shot_list},
    ))

    # === STAGE 2: CINEMATOGRAPHER — create visual specs ===
    logger.info("[Cinematographer] Creando specs visuales...")
    visual_specs = _cinematographer_spec(brief, shot_list, format, model)
    board.tasks.append(KanbanTask(
        id="visual_specs", title="Specs visuales",
        agent="cinematographer", status="done",
        output_data={"specs": visual_specs},
    ))

    # === STAGE 3: RENDERERS — generate assets ===
    logger.info("[Renderers] Generando assets...")
    scene_clips = []
    for i, spec in enumerate(visual_specs):
        task_id = f"render_{i}"
        board.tasks.append(KanbanTask(
            id=task_id, title=f"Render escena {i+1}",
            agent="renderer", status="in_progress",
            input_data={"spec": spec},
            dependencies=["visual_specs"],
        ))

        clip_path = _render_scene(spec, i, output_dir, format)
        if clip_path:
            scene_clips.append(clip_path)
            board.tasks[-1].status = "done"
            board.tasks[-1].output_data = {"clip": clip_path}
            board.artifacts.append(clip_path)
        else:
            board.tasks[-1].status = "failed"

    # === STAGE 4: TTS — generate narration ===
    logger.info("[TTS] Generando narración...")
    narration = _extract_narration(shot_list)
    if narration:
        from video.tts import generate_speech
        audio_path = str(output_dir / "narration.mp3")
        tts_result = generate_speech(narration, audio_path)
        if tts_result.success:
            board.artifacts.append(tts_result.audio_path)
            board.tasks.append(KanbanTask(
                id="tts", title="Narración TTS",
                agent="renderer", status="done",
                output_data={"audio": tts_result.audio_path, "srt": tts_result.subtitle_path},
            ))

    # === STAGE 5: EDITOR — assemble final cut ===
    logger.info("[Editor] Ensamblando video final...")
    if scene_clips:
        from video.assembler import assemble_video, VideoProject
        project = VideoProject(
            title=board.project_name,
            audio_path=tts_result.audio_path if narration and tts_result.success else "",
            subtitle_path=tts_result.subtitle_path if narration and tts_result.success else "",
            background_clips=scene_clips,
            format=format,
            output_path=str(output_dir / "final.mp4"),
        )
        result = assemble_video(project)
        if result.success:
            board.final_video = result.output_path
            board.tasks.append(KanbanTask(
                id="editor_final", title="Ensamblaje final",
                agent="editor", status="done",
                output_data={"video": result.output_path, "duration": result.duration},
            ))
            logger.info("[Editor] Video finalizado: %s", result.output_path)

    return board


def _director_decompose(brief: str, format: str, model: str) -> list[dict]:
    """Director agent: decompose brief into shot list."""
    msg = (
        f"Sos un director de video. Descomponé este brief en una lista de escenas.\n\n"
        f"BRIEF: {brief}\n"
        f"FORMATO: {format}\n\n"
        f"Generá un JSON con la lista de escenas. Cada escena tiene:\n"
        f'- "scene": número de escena\n'
        f'- "description": qué se ve\n'
        f'- "narration": qué se dice (texto para TTS)\n'
        f'- "duration": duración en segundos\n'
        f'- "visual_type": "image", "animation", "text_card"\n\n'
        f"Respondé SOLO con el JSON array."
    )
    response = chat(
        [{"role": "system", "content": "Sos un director de cine. Respondés en JSON válido."},
         {"role": "user", "content": msg}],
        model,
    )
    return _parse_json_array(response)


def _cinematographer_spec(brief: str, shots: list[dict], format: str, model: str) -> list[dict]:
    """Cinematographer agent: create visual specs for each shot."""
    msg = (
        f"Sos un cinematógrafo. Para cada escena, creá un spec visual detallado.\n\n"
        f"BRIEF: {brief}\n"
        f"ESCENAS: {json.dumps(shots, ensure_ascii=False)}\n\n"
        f"Para cada escena generá:\n"
        f'- "scene": número\n'
        f'- "prompt": prompt en inglés para generar la imagen/video con IA\n'
        f'- "mood": mood visual (cinematic, warm, dark, etc.)\n'
        f'- "text_overlay": texto a mostrar en pantalla (o vacío)\n\n'
        f"Respondé SOLO con el JSON array."
    )
    response = chat(
        [{"role": "system", "content": "Sos un director de fotografía. Respondés en JSON válido."},
         {"role": "user", "content": msg}],
        model,
    )
    specs = _parse_json_array(response)
    if not specs:
        specs = [{"scene": i + 1, "prompt": s.get("description", "abstract scene"),
                  "mood": "cinematic", "text_overlay": ""}
                 for i, s in enumerate(shots)]
    return specs


def _render_scene(spec: dict, index: int, output_dir: Path, format: str) -> str:
    """Render a single scene using available providers."""
    prompt = spec.get("prompt", "cinematic scene")

    # Try Pollinations (free)
    try:
        from video.pollinations import generate_image
        w, h = (1080, 1920) if format == "vertical" else (1920, 1080) if format == "horizontal" else (1080, 1080)
        result = generate_image(prompt, output_path=str(output_dir / f"scene_{index}.jpg"), width=w, height=h)
        if result.success:
            return result.image_path
    except Exception as e:
        logger.warning("Pollinations render falló para escena %d: %s", index, e)

    # Fallback: local b-roll
    try:
        from video.broll import generate_broll_local
        result = generate_broll_local(prompt, output_path=str(output_dir / f"scene_{index}.mp4"))
        if result.success:
            return result.video_path
    except Exception as e:
        logger.warning("B-roll local falló para escena %d: %s", index, e)

    return ""


def _extract_narration(shots: list[dict]) -> str:
    """Extract narration text from shot list."""
    parts = []
    for shot in shots:
        narration = shot.get("narration", "")
        if narration:
            parts.append(narration)
    return " ".join(parts)


def _parse_json_array(text: str) -> list[dict]:
    """Extract JSON array from LLM response."""
    text = text.strip()
    start = text.find("[")
    end = text.rfind("]")
    if start >= 0 and end > start:
        try:
            return json.loads(text[start:end + 1])
        except json.JSONDecodeError:
            pass
    # Try line by line
    try:
        return json.loads(text)
    except Exception:
        pass
    return [{"scene": 1, "description": text[:200], "narration": text[:200],
             "duration": 5, "visual_type": "image"}]
