"""Video captioning: Whisper transcription + burned-in captions via FFmpeg."""

import logging
import os
import subprocess
import tempfile
from dataclasses import dataclass, field
from pathlib import Path

logger = logging.getLogger(__name__)


@dataclass
class CaptionSegment:
    start: float
    end: float
    text: str


@dataclass
class CaptionResult:
    success: bool
    output_path: str = ""
    segments: list[CaptionSegment] = field(default_factory=list)
    subtitle_path: str = ""
    error: str = ""


def transcribe_to_segments(audio_path: str) -> list[CaptionSegment]:
    """Transcribe audio to word-level segments using Whisper."""
    try:
        import whisper
    except ImportError:
        logger.error("openai-whisper no instalado: pip install openai-whisper")
        return []

    from config import WHISPER_MODEL_SIZE, WHISPER_DEVICE

    try:
        model = whisper.load_model(WHISPER_MODEL_SIZE, device=WHISPER_DEVICE)
        result = model.transcribe(audio_path, word_timestamps=True)

        segments = []
        for seg in result.get("segments", []):
            segments.append(CaptionSegment(
                start=seg["start"],
                end=seg["end"],
                text=seg["text"].strip(),
            ))
        return segments

    except Exception as e:
        logger.error("Whisper transcription falló: %s", e)
        return []


def segments_to_ass(segments: list[CaptionSegment], output_path: str, style: str = "karaoke") -> str:
    """Convert caption segments to ASS subtitle format with styling."""
    if style == "karaoke":
        font_name = "Arial Black"
        font_size = 48
        primary_color = "&H00FFFFFF"
        outline_color = "&H00000000"
        bold = -1
        outline = 3
        shadow = 1
        margin_v = 80
        alignment = 2
    else:
        font_name = "Arial"
        font_size = 36
        primary_color = "&H00FFFFFF"
        outline_color = "&H00000000"
        bold = 0
        outline = 2
        shadow = 1
        margin_v = 60
        alignment = 2

    header = f"""[Script Info]
Title: Hermes Captions
ScriptType: v4.00+
PlayResX: 1080
PlayResY: 1920
WrapStyle: 0

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Default,{font_name},{font_size},{primary_color},&H000000FF,{outline_color},&H80000000,{bold},0,0,0,100,100,0,0,1,{outline},{shadow},{alignment},40,40,{margin_v},1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""

    def _format_time(seconds: float) -> str:
        h = int(seconds // 3600)
        m = int((seconds % 3600) // 60)
        s = int(seconds % 60)
        cs = int((seconds % 1) * 100)
        return f"{h}:{m:02d}:{s:02d}.{cs:02d}"

    lines = [header]
    for seg in segments:
        start = _format_time(seg.start)
        end = _format_time(seg.end)
        text = seg.text.replace("\n", "\\N")
        lines.append(f"Dialogue: 0,{start},{end},Default,,0,0,0,,{text}")

    content = "\n".join(lines)
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(content)

    return output_path


def burn_captions(
    video_path: str,
    subtitle_path: str,
    output_path: str = "",
) -> CaptionResult:
    """Burn subtitle file (ASS/SRT) into video using FFmpeg."""
    if not Path(video_path).exists():
        return CaptionResult(success=False, error=f"Video no encontrado: {video_path}")
    if not Path(subtitle_path).exists():
        return CaptionResult(success=False, error=f"Subtítulos no encontrados: {subtitle_path}")

    if not output_path:
        stem = Path(video_path).stem
        output_path = str(Path(video_path).parent / f"{stem}_captioned.mp4")

    ext = Path(subtitle_path).suffix.lower()
    if ext == ".ass":
        sub_filter = f"ass='{subtitle_path}'"
    else:
        style = (
            "FontName=Arial Black,FontSize=14,PrimaryColour=&H00FFFFFF,"
            "OutlineColour=&H00000000,Bold=1,Outline=2,Shadow=1,MarginV=80,Alignment=2"
        )
        sub_filter = f"subtitles='{subtitle_path}':force_style='{style}'"

    cmd = [
        "ffmpeg", "-y",
        "-i", video_path,
        "-vf", sub_filter,
        "-c:v", "libx264", "-preset", "medium", "-crf", "23",
        "-c:a", "copy",
        "-movflags", "+faststart",
        output_path,
    ]

    try:
        subprocess.run(cmd, capture_output=True, timeout=600, check=True)
        if Path(output_path).exists():
            return CaptionResult(success=True, output_path=output_path, subtitle_path=subtitle_path)
        return CaptionResult(success=False, error="Archivo de salida no generado")
    except subprocess.CalledProcessError as e:
        return CaptionResult(success=False, error=f"FFmpeg falló: {e.stderr[:500] if e.stderr else str(e)}")
    except Exception as e:
        return CaptionResult(success=False, error=str(e))


def add_captions_to_video(
    video_path: str,
    output_path: str = "",
    style: str = "karaoke",
) -> CaptionResult:
    """Full pipeline: extract audio → Whisper transcribe → ASS → burn captions."""
    if not Path(video_path).exists():
        return CaptionResult(success=False, error=f"Video no encontrado: {video_path}")

    try:
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
            audio_tmp = tmp.name

        subprocess.run(
            ["ffmpeg", "-y", "-i", video_path, "-vn", "-acodec", "pcm_s16le",
             "-ar", "16000", "-ac", "1", audio_tmp],
            capture_output=True, timeout=120, check=True,
        )

        segments = transcribe_to_segments(audio_tmp)
        if not segments:
            return CaptionResult(success=False, error="No se detectaron segmentos de audio")

        ass_path = str(Path(video_path).with_suffix(".ass"))
        segments_to_ass(segments, ass_path, style=style)

        result = burn_captions(video_path, ass_path, output_path)
        result.segments = segments
        result.subtitle_path = ass_path
        return result

    except Exception as e:
        logger.error("Caption pipeline falló: %s", e)
        return CaptionResult(success=False, error=str(e))
    finally:
        try:
            os.unlink(audio_tmp)
        except Exception:
            pass
