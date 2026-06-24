"""Análisis visual de frames de video usando modelo de visión (LLaVA via Ollama)."""

import base64
import logging
import subprocess
import tempfile
from pathlib import Path

from config import VISION_MODEL, VISION_FRAMES
from inference_client import chat_with_images

logger = logging.getLogger(__name__)


def _extract_frames(video_path: str, num_frames: int) -> list[str]:
    """Extrae N frames equiespaciados del video y los retorna como paths."""
    frames = []
    with tempfile.TemporaryDirectory() as tmpdir:
        try:
            result = subprocess.run(
                ["ffprobe", "-v", "error", "-show_entries", "format=duration",
                 "-of", "default=noprint_wrappers=1:nokey=1", video_path],
                capture_output=True, text=True, timeout=10,
            )
            duration = float(result.stdout.strip())
        except Exception:
            duration = 60.0

        interval = duration / (num_frames + 1)

        for i in range(1, num_frames + 1):
            timestamp = interval * i
            frame_path = str(Path(tmpdir) / f"frame_{i}.jpg")
            try:
                subprocess.run(
                    ["ffmpeg", "-ss", str(timestamp), "-i", video_path,
                     "-vframes", "1", "-q:v", "2", frame_path, "-y"],
                    capture_output=True, timeout=30,
                )
                if Path(frame_path).exists():
                    frames.append(frame_path)
            except Exception as e:
                logger.warning("Error extrayendo frame %d: %s", i, e)

        frames_b64 = []
        for fp in frames:
            with open(fp, "rb") as f:
                frames_b64.append(base64.b64encode(f.read()).decode("utf-8"))

    return frames_b64


def analyze_frames(video_path: str, num_frames: int = None) -> list[str]:
    """Analiza frames del video usando un modelo de visión y retorna descripciones."""
    if num_frames is None:
        num_frames = VISION_FRAMES

    frames_b64 = _extract_frames(video_path, num_frames)
    if not frames_b64:
        return ["No se pudieron extraer frames del video."]

    descriptions = []
    for i, frame_b64 in enumerate(frames_b64, 1):
        try:
            desc = chat_with_images(
                messages=[{
                    "role": "user",
                    "content": "Describe detalladamente qué se ve en esta imagen. "
                               "Sé específico sobre personas, objetos, texto y acciones.",
                }],
                images=[frame_b64],
                model=VISION_MODEL,
            )
            descriptions.append(desc)
        except Exception as e:
            logger.warning("Error analizando frame %d: %s", i, e)
            descriptions.append(f"[Error analizando frame: {e}]")

    return descriptions
