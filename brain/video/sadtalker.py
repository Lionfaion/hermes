"""Free avatar video generation using SadTalker (open source, runs locally).

Requires: pip install sadtalker
Or clone: git clone https://github.com/OpenTalker/SadTalker
Needs ~6GB GPU VRAM.
"""

import logging
import os
import subprocess
import time
from dataclasses import dataclass
from pathlib import Path

logger = logging.getLogger(__name__)

SADTALKER_PATH = os.getenv("SADTALKER_PATH", str(Path.home() / "SadTalker"))
DEFAULT_AVATAR_IMAGE = os.getenv("HERMES_AVATAR_IMAGE", "")


@dataclass
class AvatarResult:
    success: bool
    video_path: str = ""
    duration: float = 0.0
    error: str = ""


def is_available() -> bool:
    """Verifica si SadTalker está instalado."""
    inference_script = Path(SADTALKER_PATH) / "inference.py"
    return inference_script.exists()


def generate_avatar_video(
    audio_path: str,
    image_path: str = "",
    output_dir: str = "",
    enhancer: str = "gfpgan",
    still_mode: bool = False,
    preprocess: str = "crop",
) -> AvatarResult:
    """Genera un video con cara animada usando SadTalker.

    Args:
        audio_path: Ruta al audio de narración
        image_path: Ruta a imagen de cara (usa default si no se especifica)
        output_dir: Directorio de salida
        enhancer: 'gfpgan' para mejorar calidad facial, '' para desactivar
        still_mode: True para que solo mueva la boca (sin movimiento de cabeza)
        preprocess: 'crop' (recorta cara), 'resize' (escala), 'full' (frame completo)
    """
    if not is_available():
        return AvatarResult(
            success=False,
            error=(
                f"SadTalker no encontrado en {SADTALKER_PATH}. "
                "Instalalo con:\n"
                "  git clone https://github.com/OpenTalker/SadTalker.git ~/SadTalker\n"
                "  cd ~/SadTalker && pip install -r requirements.txt\n"
                "  bash scripts/download_models.sh"
            ),
        )

    image_path = image_path or DEFAULT_AVATAR_IMAGE
    if not image_path or not Path(image_path).exists():
        return AvatarResult(
            success=False,
            error=(
                "Se necesita una imagen de cara. Configurá HERMES_AVATAR_IMAGE "
                "en .env o pasá image_path. La imagen debe tener una cara visible."
            ),
        )

    if not Path(audio_path).exists():
        return AvatarResult(success=False, error=f"Audio no encontrado: {audio_path}")

    if not output_dir:
        from config import MEDIA_DOWNLOAD_DIR
        output_dir = str(Path(MEDIA_DOWNLOAD_DIR) / "avatar")
    Path(output_dir).mkdir(parents=True, exist_ok=True)

    cmd = [
        "python", str(Path(SADTALKER_PATH) / "inference.py"),
        "--driven_audio", str(audio_path),
        "--source_image", str(image_path),
        "--result_dir", output_dir,
        "--preprocess", preprocess,
    ]

    if enhancer:
        cmd.extend(["--enhancer", enhancer])
    if still_mode:
        cmd.append("--still")

    try:
        logger.info("Generando avatar con SadTalker...")
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=600,
            cwd=SADTALKER_PATH,
        )

        if result.returncode != 0:
            error_msg = result.stderr[-500:] if result.stderr else "Error desconocido"
            return AvatarResult(success=False, error=f"SadTalker falló: {error_msg}")

        output_files = sorted(
            Path(output_dir).glob("*.mp4"),
            key=lambda p: p.stat().st_mtime,
            reverse=True,
        )

        if not output_files:
            return AvatarResult(
                success=False,
                error="SadTalker no generó archivo de video",
            )

        video_path = str(output_files[0])
        duration = _get_duration(video_path)

        return AvatarResult(
            success=True,
            video_path=video_path,
            duration=duration,
        )

    except subprocess.TimeoutExpired:
        return AvatarResult(success=False, error="SadTalker timeout (>10 min)")
    except Exception as e:
        logger.error("SadTalker falló: %s", e)
        return AvatarResult(success=False, error=str(e))


def _get_duration(file_path: str) -> float:
    try:
        result = subprocess.run(
            ["ffprobe", "-v", "error", "-show_entries", "format=duration",
             "-of", "default=noprint_wrappers=1:nokey=1", file_path],
            capture_output=True, text=True, timeout=10,
        )
        return float(result.stdout.strip())
    except Exception:
        return 0.0
