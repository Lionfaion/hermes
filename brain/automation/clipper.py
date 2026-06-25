"""Clipper: extrae los mejores momentos de contenido largo."""

import logging
import subprocess
import json
from pathlib import Path

from config import DATA_DIR, MEDIA_DOWNLOAD_DIR

logger = logging.getLogger(__name__)

CLIPS_DIR = Path(MEDIA_DOWNLOAD_DIR) / "clips"


def extract_clips_from_video(
    video_path: str,
    timestamps: list[dict],
    output_dir: str = "",
) -> list[str]:
    out = Path(output_dir) if output_dir else CLIPS_DIR
    out.mkdir(parents=True, exist_ok=True)

    clips = []
    source = Path(video_path)

    for i, ts in enumerate(timestamps):
        start = ts.get("start", "00:00:00")
        duration = ts.get("duration", "00:00:60")
        label = ts.get("label", f"clip_{i}")

        output_file = out / f"{source.stem}_{label}.mp4"

        cmd = [
            "ffmpeg", "-y",
            "-ss", str(start),
            "-i", str(source),
            "-t", str(duration),
            "-c:v", "libx264",
            "-c:a", "aac",
            "-preset", "fast",
            "-movflags", "+faststart",
            str(output_file),
        ]

        try:
            subprocess.run(cmd, capture_output=True, timeout=120, check=True)
            clips.append(str(output_file))
            logger.info("Clip extraído: %s", output_file.name)
        except Exception as e:
            logger.error("Error extrayendo clip %s: %s", label, e)

    return clips


def identify_best_moments(transcript: str, duration_seconds: int = 60) -> str:
    from inference_client import chat

    prompt = (
        "Analizá esta transcripción de un video/podcast largo e identificá los "
        f"mejores momentos para crear clips cortos de {duration_seconds} segundos.\n\n"
        f"**Transcripción:**\n{transcript[:8000]}\n\n"
        "Para cada momento identificá:\n"
        "1. **Timestamp aproximado** (basado en la posición en el texto)\n"
        "2. **Título para el clip**\n"
        "3. **Por qué es viral**: qué lo hace interesante/compartible\n"
        "4. **Hook sugerido**: cómo empezar el clip para captar atención\n\n"
        "Identificá entre 3 y 5 momentos. Priorizá: frases impactantes, "
        "datos sorprendentes, momentos emocionales, opiniones controversiales."
    )

    messages = [
        {"role": "system", "content": "Sos un editor de contenido viral experto. Respondé en español con formato JSON."},
        {"role": "user", "content": prompt},
    ]
    return chat(messages)


def download_and_clip(
    url: str,
    clip_duration: int = 60,
    max_clips: int = 5,
) -> dict:
    from media.transcriber import transcribe

    download_dir = Path(MEDIA_DOWNLOAD_DIR)
    download_dir.mkdir(parents=True, exist_ok=True)

    try:
        result = subprocess.run(
            ["yt-dlp", "-f", "best[height<=720]", "--no-playlist",
             "-o", str(download_dir / "%(title)s.%(ext)s"),
             "--print", "after_move:filepath", url],
            capture_output=True, text=True, timeout=300,
        )
        video_path = result.stdout.strip().split("\n")[-1]

        if not Path(video_path).exists():
            return {"error": "No se pudo descargar el video"}

        transcript = transcribe(video_path)
        if not transcript:
            return {"error": "No se pudo transcribir el audio"}

        moments = identify_best_moments(transcript, clip_duration)

        return {
            "video_path": video_path,
            "transcript_preview": transcript[:500],
            "best_moments": moments,
            "instructions": (
                "Usá extract_clips_from_video() con los timestamps identificados "
                "para extraer los clips. Luego publicalos con publish_video."
            ),
        }
    except Exception as e:
        logger.error("Error en download_and_clip: %s", e)
        return {"error": str(e)}
