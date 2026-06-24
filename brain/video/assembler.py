"""Ensamblador de video: combina audio, clips, subtítulos y música."""

import logging
import os
import subprocess
import tempfile
from dataclasses import dataclass, field
from pathlib import Path

_TMP = tempfile.gettempdir()

logger = logging.getLogger(__name__)


FORMATS = {
    "vertical": {"width": 1080, "height": 1920},    # TikTok, Reels, Shorts
    "horizontal": {"width": 1920, "height": 1080},   # YouTube
    "square": {"width": 1080, "height": 1080},       # Instagram feed
}


@dataclass
class VideoProject:
    title: str
    audio_path: str
    subtitle_path: str = ""
    background_clips: list[str] = field(default_factory=list)
    background_music: str = ""
    music_volume: float = 0.1
    format: str = "vertical"
    output_path: str = ""


@dataclass
class AssembleResult:
    success: bool
    output_path: str = ""
    duration: float = 0.0
    error: str = ""


def assemble_video(project: VideoProject) -> AssembleResult:
    """Ensambla el video final usando ffmpeg directamente."""
    fmt = FORMATS.get(project.format, FORMATS["vertical"])
    w, h = fmt["width"], fmt["height"]

    if not project.output_path:
        project.output_path = str(Path(project.audio_path).parent / f"{project.title[:50]}_final.mp4")

    try:
        audio_duration = _get_duration(project.audio_path)
        if audio_duration <= 0:
            return AssembleResult(success=False, error="No se pudo determinar la duración del audio")

        if project.background_clips:
            bg_video = _concat_and_loop_clips(project.background_clips, audio_duration, w, h)
        else:
            bg_video = _generate_black_background(audio_duration, w, h)

        _assemble_final(
            video_path=bg_video,
            audio_path=project.audio_path,
            subtitle_path=project.subtitle_path,
            music_path=project.background_music,
            music_volume=project.music_volume,
            output_path=project.output_path,
            width=w, height=h,
        )

        if Path(project.output_path).exists():
            return AssembleResult(
                success=True,
                output_path=project.output_path,
                duration=audio_duration,
            )
        return AssembleResult(success=False, error="El archivo de salida no se generó")

    except FileNotFoundError:
        return AssembleResult(success=False, error="ffmpeg no encontrado. Instalá con: sudo apt install ffmpeg")
    except Exception as e:
        logger.error("Error ensamblando video: %s", e)
        return AssembleResult(success=False, error=str(e))


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


def _generate_black_background(duration: float, w: int, h: int) -> str:
    output = str(Path(_TMP) / f"hermes_bg_{w}x{h}.mp4")
    subprocess.run(
        ["ffmpeg", "-y", "-f", "lavfi", "-i",
         f"color=c=black:s={w}x{h}:d={duration}:r=30",
         "-c:v", "libx264", "-preset", "ultrafast", output],
        capture_output=True, timeout=120,
    )
    return output


def _concat_and_loop_clips(clips: list[str], target_duration: float, w: int, h: int) -> str:
    """Concatena clips, los escala al formato y los loopea hasta cubrir la duración."""
    concat_list = str(Path(_TMP) / "hermes_concat.txt")
    scaled_clips = []

    for i, clip_path in enumerate(clips):
        scaled = str(Path(_TMP) / f"hermes_scaled_{i}.mp4")
        subprocess.run(
            ["ffmpeg", "-y", "-i", clip_path, "-vf",
             f"scale={w}:{h}:force_original_aspect_ratio=increase,crop={w}:{h}",
             "-c:v", "libx264", "-preset", "ultrafast", "-an", scaled],
            capture_output=True, timeout=120,
        )
        if Path(scaled).exists():
            scaled_clips.append(scaled)

    if not scaled_clips:
        return _generate_black_background(target_duration, w, h)

    # Crear archivo de concatenación, repitiendo clips hasta cubrir duración
    total = 0.0
    with open(concat_list, "w") as f:
        while total < target_duration:
            for clip in scaled_clips:
                f.write(f"file '{clip}'\n")
                total += _get_duration(clip)
                if total >= target_duration:
                    break

    output = str(Path(_TMP) / "hermes_bg_concat.mp4")
    subprocess.run(
        ["ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", concat_list,
         "-t", str(target_duration), "-c:v", "libx264", "-preset", "ultrafast", output],
        capture_output=True, timeout=300,
    )
    return output


def _assemble_final(
    video_path: str, audio_path: str, subtitle_path: str,
    music_path: str, music_volume: float,
    output_path: str, width: int, height: int,
):
    """Ensambla el video final con audio, subtítulos y música opcional."""
    cmd = ["ffmpeg", "-y", "-i", video_path, "-i", audio_path]

    filter_parts = []

    if music_path and Path(music_path).exists():
        cmd.extend(["-i", music_path])
        filter_parts.append(f"[2:a]volume={music_volume}[bg];[1:a][bg]amix=inputs=2:duration=first[aout]")
        audio_map = "[aout]"
    else:
        audio_map = "1:a"

    if subtitle_path and Path(subtitle_path).exists():
        # Subtítulos con estilo para viral videos
        style = (
            "FontName=Arial Black,FontSize=14,PrimaryColour=&H00FFFFFF,"
            "OutlineColour=&H00000000,BackColour=&H80000000,"
            "Bold=1,Outline=2,Shadow=1,MarginV=80,Alignment=2"
        )
        sub_filter = f"subtitles='{subtitle_path}':force_style='{style}'"
        filter_parts.insert(0, f"[0:v]{sub_filter}[vout]")
        video_map = "[vout]"
    else:
        video_map = "0:v"

    if filter_parts:
        cmd.extend(["-filter_complex", ";".join(filter_parts)])

    cmd.extend([
        "-map", video_map, "-map", audio_map,
        "-c:v", "libx264", "-preset", "medium", "-crf", "23",
        "-c:a", "aac", "-b:a", "192k",
        "-movflags", "+faststart",
        "-shortest",
        output_path,
    ])

    subprocess.run(cmd, capture_output=True, timeout=600)
