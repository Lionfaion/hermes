"""Descarga de videos/audio de internet usando yt-dlp."""

import logging
from dataclasses import dataclass, field
from pathlib import Path

from config import MEDIA_DOWNLOAD_DIR, MEDIA_MAX_DURATION

logger = logging.getLogger(__name__)


@dataclass
class DownloadResult:
    success: bool
    title: str = ""
    duration: int = 0
    video_path: str = ""
    audio_path: str = ""
    error: str = ""


def download_media(url: str) -> DownloadResult:
    """Descarga video/audio de una URL usando yt-dlp."""
    try:
        import yt_dlp
    except ImportError:
        return DownloadResult(
            success=False,
            error="yt-dlp no instalado. Ejecutá: pip install yt-dlp"
        )

    output_dir = Path(MEDIA_DOWNLOAD_DIR)
    output_dir.mkdir(parents=True, exist_ok=True)

    ydl_opts = {
        "outtmpl": str(output_dir / "%(id)s.%(ext)s"),
        "format": "best[ext=mp4]/best",
        "noplaylist": True,
        "quiet": True,
        "no_warnings": True,
    }

    try:
        # Primero chequear duración sin descargar
        with yt_dlp.YoutubeDL({**ydl_opts, "quiet": True}) as ydl_check:
            info = ydl_check.extract_info(url, download=False)
            if not info:
                return DownloadResult(success=False, error="No se pudo obtener info del video")
            duration = info.get("duration", 0) or 0
            if duration > MEDIA_MAX_DURATION:
                return DownloadResult(
                    success=False,
                    error=f"Video demasiado largo ({duration}s, máximo {MEDIA_MAX_DURATION}s)"
                )
            video_id = info.get("id", "unknown")
            title = info.get("title", "")

        # Nueva instancia limpia para descargar
        with yt_dlp.YoutubeDL(ydl_opts) as ydl_dl:
            ydl_dl.download([url])

        ext = "mp4"
        video_path = str(output_dir / f"{video_id}.{ext}")
        if not Path(video_path).exists():
            # Buscar el archivo descargado por id
            candidates = list(output_dir.glob(f"{video_id}.*"))
            if candidates:
                video_path = str(candidates[0])
            else:
                return DownloadResult(success=False, error="Archivo descargado no encontrado")

        audio_path = _extract_audio(video_path)

        return DownloadResult(
            success=True,
            title=title,
            duration=duration,
            video_path=video_path,
            audio_path=audio_path,
        )
    except Exception as e:
        logger.error("Error descargando %s: %s", url, e)
        return DownloadResult(success=False, error=str(e))


def _extract_audio(video_path: str) -> str:
    """Extrae audio del video a WAV usando ffmpeg."""
    import subprocess

    audio_path = str(Path(video_path).with_suffix(".wav"))
    try:
        subprocess.run(
            ["ffmpeg", "-i", video_path, "-vn", "-acodec", "pcm_s16le",
             "-ar", "16000", "-ac", "1", audio_path, "-y"],
            capture_output=True, timeout=120,
        )
        if Path(audio_path).exists():
            return audio_path
    except FileNotFoundError:
        logger.warning("ffmpeg no encontrado, no se puede extraer audio")
    except Exception as e:
        logger.warning("Error extrayendo audio: %s", e)
    return ""
