"""Video quality control: ffprobe validation, black frame detection, spec checks."""

import json
import logging
import os
import subprocess
from dataclasses import dataclass, field
from pathlib import Path

logger = logging.getLogger(__name__)

SOCIAL_SPECS = {
    "tiktok": {"max_duration": 600, "aspect": "9:16", "codec": "h264", "pix_fmt": "yuv420p"},
    "reels": {"max_duration": 90, "aspect": "9:16", "codec": "h264", "pix_fmt": "yuv420p"},
    "shorts": {"max_duration": 60, "aspect": "9:16", "codec": "h264", "pix_fmt": "yuv420p"},
    "youtube": {"max_duration": 43200, "aspect": "16:9", "codec": "h264", "pix_fmt": "yuv420p"},
}


@dataclass
class QCResult:
    success: bool
    path: str = ""
    duration: float = 0.0
    width: int = 0
    height: int = 0
    video_codec: str = ""
    audio_codec: str = ""
    pix_fmt: str = ""
    size_mb: float = 0.0
    has_audio: bool = False
    warnings: list[str] = field(default_factory=list)
    black_frames: int = 0
    platform_ready: dict = field(default_factory=dict)


def probe_video(video_path: str) -> QCResult:
    """Runs ffprobe to extract video metadata and detect issues."""
    path = Path(video_path)
    if not path.exists():
        return QCResult(success=False, path=video_path, warnings=["Archivo no encontrado"])

    try:
        cmd = [
            "ffprobe", "-v", "error",
            "-show_streams", "-show_format",
            "-of", "json",
            str(path),
        ]
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
        if proc.returncode != 0:
            return QCResult(success=False, path=video_path,
                            warnings=[f"ffprobe falló: {proc.stderr[:200]}"])

        data = json.loads(proc.stdout)
        streams = data.get("streams", [])
        fmt = data.get("format", {})

        video_streams = [s for s in streams if s.get("codec_type") == "video"]
        audio_streams = [s for s in streams if s.get("codec_type") == "audio"]

        warnings = []

        if not video_streams:
            warnings.append("No se encontró stream de video")

        v0 = video_streams[0] if video_streams else {}
        codec = v0.get("codec_name", "")
        pix_fmt = v0.get("pix_fmt", "")
        width = int(v0.get("width", 0))
        height = int(v0.get("height", 0))
        duration = float(fmt.get("duration", 0))
        size_mb = os.path.getsize(path) / (1024 * 1024)

        if pix_fmt and pix_fmt != "yuv420p":
            warnings.append(f"Pixel format {pix_fmt} — yuv420p es más compatible para redes sociales")

        if codec and codec not in ("h264", "hevc"):
            warnings.append(f"Codec {codec} — h264 es más compatible")

        if duration <= 0:
            warnings.append("Duración es 0 o no detectada")

        if not audio_streams:
            warnings.append("Sin audio — los videos para redes necesitan audio")

        audio_codec = audio_streams[0].get("codec_name", "") if audio_streams else ""

        black_count = _detect_black_frames(video_path)
        if black_count > 0:
            warnings.append(f"Detectados {black_count} segmentos de frames negros")

        platform_ready = {}
        for platform, spec in SOCIAL_SPECS.items():
            issues = []
            if duration > spec["max_duration"]:
                issues.append(f"Duración {duration:.0f}s excede máximo {spec['max_duration']}s")
            if codec != spec["codec"]:
                issues.append(f"Codec {codec} != {spec['codec']}")
            if pix_fmt != spec["pix_fmt"]:
                issues.append(f"Pixel format {pix_fmt} != {spec['pix_fmt']}")
            platform_ready[platform] = {"ready": len(issues) == 0, "issues": issues}

        return QCResult(
            success=True,
            path=video_path,
            duration=duration,
            width=width,
            height=height,
            video_codec=codec,
            audio_codec=audio_codec,
            pix_fmt=pix_fmt,
            size_mb=size_mb,
            has_audio=bool(audio_streams),
            warnings=warnings,
            black_frames=black_count,
            platform_ready=platform_ready,
        )

    except Exception as e:
        logger.error("QC probe falló: %s", e)
        return QCResult(success=False, path=video_path, warnings=[str(e)])


def _detect_black_frames(video_path: str) -> int:
    try:
        proc = subprocess.run(
            ["ffmpeg", "-i", video_path,
             "-vf", "blackdetect=d=0.5:pix_th=0.10",
             "-an", "-f", "null", "-"],
            capture_output=True, text=True, timeout=120,
        )
        lines = [l for l in (proc.stderr or "").splitlines() if "black_start:" in l]
        return len(lines)
    except Exception:
        return 0


def format_qc_report(result: QCResult) -> str:
    """Formats QC result as a readable report."""
    if not result.success:
        return f"QC falló: {', '.join(result.warnings)}"

    lines = [
        f"**QC Video: {Path(result.path).name}**",
        f"- Resolución: {result.width}x{result.height}",
        f"- Duración: {result.duration:.1f}s",
        f"- Tamaño: {result.size_mb:.1f} MB",
        f"- Video codec: {result.video_codec}",
        f"- Audio codec: {result.audio_codec or 'sin audio'}",
        f"- Pixel format: {result.pix_fmt}",
    ]

    if result.warnings:
        lines.append("\n**Advertencias:**")
        for w in result.warnings:
            lines.append(f"  - {w}")

    lines.append("\n**Compatibilidad:**")
    for platform, info in result.platform_ready.items():
        status = "OK" if info["ready"] else "AJUSTAR"
        lines.append(f"  - {platform}: {status}")
        for issue in info.get("issues", []):
            lines.append(f"    - {issue}")

    return "\n".join(lines)
