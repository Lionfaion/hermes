"""Generación de voz con Edge-TTS (gratis, voces de Microsoft)."""

import asyncio
import logging
from pathlib import Path
from dataclasses import dataclass

logger = logging.getLogger(__name__)

VOICES = {
    "es-ar-female": "es-AR-ElenaNeural",
    "es-ar-male": "es-AR-TomasNeural",
    "es-es-female": "es-ES-ElviraNeural",
    "es-es-male": "es-ES-AlvaroNeural",
    "es-mx-female": "es-MX-DaliaNeural",
    "es-mx-male": "es-MX-JorgeNeural",
    "en-us-female": "en-US-JennyNeural",
    "en-us-male": "en-US-GuyNeural",
    "pt-br-female": "pt-BR-FranciscaNeural",
    "pt-br-male": "pt-BR-AntonioNeural",
}

DEFAULT_VOICE = "es-ar-male"


@dataclass
class TTSResult:
    success: bool
    audio_path: str = ""
    subtitle_path: str = ""
    duration: float = 0.0
    error: str = ""


async def _generate_tts(text: str, output_path: str, voice: str, rate: str) -> TTSResult:
    try:
        import edge_tts
    except ImportError:
        return TTSResult(success=False, error="edge-tts no instalado. Ejecutá: pip install edge-tts")

    try:
        voice_id = VOICES.get(voice, voice)
        communicate = edge_tts.Communicate(text, voice_id, rate=rate)

        srt_path = str(Path(output_path).with_suffix(".srt"))

        submaker = edge_tts.SubMaker()
        with open(output_path, "wb") as f:
            async for chunk in communicate.stream():
                if chunk["type"] == "audio":
                    f.write(chunk["data"])
                elif chunk["type"] == "WordBoundary":
                    submaker.feed(chunk)

        srt_content = submaker.generate_subs()
        if srt_content:
            with open(srt_path, "w", encoding="utf-8") as f:
                f.write(srt_content)

        from mutagen.mp3 import MP3
        try:
            audio = MP3(output_path)
            duration = audio.info.length
        except Exception:
            duration = 0.0

        return TTSResult(
            success=True,
            audio_path=output_path,
            subtitle_path=srt_path if Path(srt_path).exists() else "",
            duration=duration,
        )
    except Exception as e:
        logger.error("TTS falló: %s", e)
        return TTSResult(success=False, error=str(e))


def generate_speech(
    text: str,
    output_path: str,
    voice: str = DEFAULT_VOICE,
    rate: str = "+0%",
) -> TTSResult:
    """Genera audio con voz sintetizada y subtítulos sincronizados."""
    return asyncio.run(_generate_tts(text, output_path, voice, rate))


def list_voices() -> dict[str, str]:
    """Retorna las voces disponibles."""
    return dict(VOICES)
