"""Transcripción de audio usando faster-whisper."""

import logging
from pathlib import Path

from config import WHISPER_MODEL_SIZE, WHISPER_DEVICE

logger = logging.getLogger(__name__)

_model = None


def _get_model():
    global _model
    if _model is None:
        try:
            from faster_whisper import WhisperModel
            compute = "int8" if WHISPER_DEVICE == "cpu" else "float16"
            _model = WhisperModel(WHISPER_MODEL_SIZE, device=WHISPER_DEVICE, compute_type=compute)
            logger.info("Whisper cargado: modelo=%s, device=%s", WHISPER_MODEL_SIZE, WHISPER_DEVICE)
        except ImportError:
            logger.error("faster-whisper no instalado. Ejecutá: pip install faster-whisper")
            return None
    return _model


def transcribe(audio_path: str) -> str:
    """Transcribe un archivo de audio y retorna el texto."""
    if not Path(audio_path).exists():
        return ""

    model = _get_model()
    if model is None:
        return "[faster-whisper no disponible]"

    try:
        segments, info = model.transcribe(audio_path, language=None)
        logger.info("Idioma detectado: %s (prob: %.2f)", info.language, info.language_probability)

        lines = []
        for segment in segments:
            lines.append(segment.text.strip())

        transcript = " ".join(lines)
        if len(transcript) > 50000:
            transcript = transcript[:50000] + " [... truncado]"
        return transcript
    except Exception as e:
        logger.error("Error transcribiendo: %s", e)
        return f"[Error de transcripción: {e}]"
