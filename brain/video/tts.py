"""Generación de voz multi-backend: Edge-TTS (gratis) y Voxtral (clonación de voz)."""

import asyncio
import base64
import logging
import os
from pathlib import Path
from dataclasses import dataclass

logger = logging.getLogger(__name__)

# ── Voces Edge-TTS (100% gratis) ──

EDGE_VOICES = {
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

# ── Voces Voxtral presets ──

VOXTRAL_VOICES = {
    "casual-male": "casual_male",
    "casual-female": "casual_female",
    "neutral-male": "neutral_male",
    "neutral-female": "neutral_female",
    "alloy": "alloy",
    "jane-confident": "jane_confident",
}

DEFAULT_VOICE = "es-ar-male"
DEFAULT_BACKEND = os.getenv("TTS_BACKEND", "edge")  # "edge" o "voxtral"
MISTRAL_API_KEY = os.getenv("MISTRAL_API_KEY", "")


@dataclass
class TTSResult:
    success: bool
    audio_path: str = ""
    subtitle_path: str = ""
    duration: float = 0.0
    backend: str = ""
    error: str = ""


def _get_audio_duration(file_path: str) -> float:
    """Obtiene la duración de un archivo de audio."""
    try:
        from mutagen.mp3 import MP3
        return MP3(file_path).info.length
    except Exception:
        pass
    try:
        from mutagen import File as MutagenFile
        audio = MutagenFile(file_path)
        if audio and audio.info:
            return audio.info.length
    except Exception:
        pass
    try:
        import subprocess
        result = subprocess.run(
            ["ffprobe", "-v", "error", "-show_entries", "format=duration",
             "-of", "default=noprint_wrappers=1:nokey=1", file_path],
            capture_output=True, text=True, timeout=10,
        )
        return float(result.stdout.strip())
    except Exception:
        return 0.0


# ══════════════════════════════════════════
#  EDGE-TTS (gratis, Microsoft)
# ══════════════════════════════════════════

async def _generate_edge_tts(text: str, output_path: str, voice: str, rate: str) -> TTSResult:
    try:
        import edge_tts
    except ImportError:
        return TTSResult(success=False, error="edge-tts no instalado. Ejecutá: pip install edge-tts")

    try:
        voice_id = EDGE_VOICES.get(voice, voice)
        communicate = edge_tts.Communicate(text, voice_id, rate=rate)

        srt_path = str(Path(output_path).with_suffix(".srt"))

        submaker = edge_tts.SubMaker()
        with open(output_path, "wb") as f:
            async for chunk in communicate.stream():
                if chunk["type"] == "audio":
                    f.write(chunk["data"])
                elif chunk["type"] == "WordBoundary":
                    submaker.feed(chunk)

        srt_content = submaker.get_srt() if hasattr(submaker, "get_srt") else submaker.generate_subs()
        if srt_content:
            with open(srt_path, "w", encoding="utf-8") as f:
                f.write(srt_content)

        duration = _get_audio_duration(output_path)

        return TTSResult(
            success=True,
            audio_path=output_path,
            subtitle_path=srt_path if Path(srt_path).exists() else "",
            duration=duration,
            backend="edge",
        )
    except Exception as e:
        logger.error("Edge-TTS falló: %s", e)
        return TTSResult(success=False, error=str(e))


# ══════════════════════════════════════════
#  VOXTRAL TTS (Mistral AI - clonación de voz)
# ══════════════════════════════════════════

def _generate_voxtral(
    text: str,
    output_path: str,
    voice: str = "casual_male",
    voice_reference_path: str = "",
    response_format: str = "mp3",
) -> TTSResult:
    """Genera audio con Voxtral TTS de Mistral (API)."""
    if not MISTRAL_API_KEY:
        return TTSResult(
            success=False,
            error="MISTRAL_API_KEY no configurada. Obtenela en console.mistral.ai"
        )

    try:
        from mistralai import Mistral
    except ImportError:
        return TTSResult(
            success=False,
            error="mistralai no instalado. Ejecutá: pip install mistralai"
        )

    try:
        client = Mistral(api_key=MISTRAL_API_KEY)

        kwargs = {
            "model": "voxtral-mini-tts-2603",
            "input": text,
            "response_format": response_format,
        }

        if voice_reference_path and Path(voice_reference_path).exists():
            # Clonación de voz: enviar audio de referencia
            with open(voice_reference_path, "rb") as f:
                audio_data = f.read()
            audio_b64 = base64.b64encode(audio_data).decode("utf-8")

            ext = Path(voice_reference_path).suffix.lstrip(".").lower()
            mime_map = {"mp3": "audio/mpeg", "wav": "audio/wav", "flac": "audio/flac",
                        "ogg": "audio/ogg", "m4a": "audio/mp4", "aac": "audio/aac"}
            mime = mime_map.get(ext, "audio/wav")

            kwargs["voice"] = {
                "type": "voice_preset",
                "id": VOXTRAL_VOICES.get(voice, voice),
                "reference_audio": {
                    "type": "base64",
                    "media_type": mime,
                    "data": audio_b64,
                },
            }
            logger.info("Voxtral: usando clonación de voz desde %s", voice_reference_path)
        else:
            # Usar preset de voz
            voice_id = VOXTRAL_VOICES.get(voice, voice)
            kwargs["voice"] = voice_id

        response = client.audio.speech.complete(**kwargs)

        # Decodificar y guardar audio
        audio_bytes = base64.b64decode(response.data)
        Path(output_path).parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, "wb") as f:
            f.write(audio_bytes)

        duration = _get_audio_duration(output_path)

        return TTSResult(
            success=True,
            audio_path=output_path,
            duration=duration,
            backend="voxtral",
        )
    except Exception as e:
        logger.error("Voxtral TTS falló: %s", e)
        return TTSResult(success=False, error=str(e))


# ══════════════════════════════════════════
#  COQUI TTS (gratis, open source, clonación de voz local)
# ══════════════════════════════════════════

def _generate_coqui(
    text: str,
    output_path: str,
    voice_reference_path: str = "",
    language: str = "es",
) -> TTSResult:
    """Genera audio con Coqui TTS XTTS v2 (local, gratis, soporta clonación)."""
    try:
        from TTS.api import TTS
    except ImportError:
        return TTSResult(
            success=False,
            error="Coqui TTS no instalado. Ejecutá: pip install TTS"
        )

    try:
        model_name = "tts_models/multilingual/multi-dataset/xtts_v2"
        tts = TTS(model_name)

        Path(output_path).parent.mkdir(parents=True, exist_ok=True)

        if voice_reference_path and Path(voice_reference_path).exists():
            tts.tts_to_file(
                text=text,
                speaker_wav=voice_reference_path,
                language=language,
                file_path=output_path,
            )
            logger.info("Coqui TTS: voz clonada desde %s", voice_reference_path)
        else:
            tts.tts_to_file(
                text=text,
                language=language,
                file_path=output_path,
            )

        duration = _get_audio_duration(output_path)

        return TTSResult(
            success=True,
            audio_path=output_path,
            duration=duration,
            backend="coqui",
        )
    except Exception as e:
        logger.error("Coqui TTS falló: %s", e)
        return TTSResult(success=False, error=str(e))


# ══════════════════════════════════════════
#  API PÚBLICA (selecciona backend automáticamente)
# ══════════════════════════════════════════

def generate_speech(
    text: str,
    output_path: str,
    voice: str = DEFAULT_VOICE,
    rate: str = "+0%",
    backend: str = "",
    voice_reference_path: str = "",
) -> TTSResult:
    """Genera audio con voz sintetizada.

    Args:
        text: Texto a convertir en voz.
        output_path: Ruta donde guardar el audio.
        voice: Nombre de la voz (ver EDGE_VOICES y VOXTRAL_VOICES).
        rate: Velocidad de habla (solo Edge-TTS, ej: "+10%", "-5%").
        backend: "edge" (gratis), "voxtral" (premium+clonación), o "" (auto).
        voice_reference_path: Ruta a audio de referencia para clonar voz (solo Voxtral).
    """
    # Auto-selección de backend
    if not backend:
        if voice_reference_path:
            if MISTRAL_API_KEY:
                backend = "voxtral"
            else:
                backend = "coqui"
        elif voice in VOXTRAL_VOICES:
            backend = "voxtral"
        else:
            backend = DEFAULT_BACKEND

    if backend == "coqui":
        result = _generate_coqui(
            text, output_path,
            voice_reference_path=voice_reference_path,
        )
        if not result.success and voice in EDGE_VOICES:
            logger.warning("Coqui TTS falló, fallback a Edge-TTS: %s", result.error)
            return asyncio.run(_generate_edge_tts(text, output_path, voice, rate))
        return result

    if backend == "voxtral":
        result = _generate_voxtral(
            text, output_path,
            voice=voice,
            voice_reference_path=voice_reference_path,
        )
        # Fallback a Coqui si Voxtral falla, luego a Edge-TTS
        if not result.success:
            if voice_reference_path:
                logger.warning("Voxtral falló, intentando Coqui TTS: %s", result.error)
                coqui_result = _generate_coqui(text, output_path, voice_reference_path=voice_reference_path)
                if coqui_result.success:
                    return coqui_result
            if voice in EDGE_VOICES:
                logger.warning("Fallback a Edge-TTS")
                return asyncio.run(_generate_edge_tts(text, output_path, voice, rate))
        return result

    return asyncio.run(_generate_edge_tts(text, output_path, voice, rate))


def clone_voice(
    text: str,
    output_path: str,
    reference_audio: str,
) -> TTSResult:
    """Clona una voz a partir de un audio de referencia (2-25 segundos).

    Usa Coqui TTS XTTS v2 (gratis, local) o Voxtral (si MISTRAL_API_KEY está configurada).
    """
    if MISTRAL_API_KEY:
        result = _generate_voxtral(
            text, output_path,
            voice="casual_male",
            voice_reference_path=reference_audio,
        )
        if result.success:
            return result
        logger.warning("Voxtral falló para clonación, intentando Coqui: %s", result.error)

    return _generate_coqui(
        text, output_path,
        voice_reference_path=reference_audio,
    )


def list_voices() -> dict:
    """Retorna todas las voces disponibles organizadas por backend."""
    return {
        "edge_tts (gratis)": dict(EDGE_VOICES),
        "voxtral (premium + clonación)": dict(VOXTRAL_VOICES),
    }
