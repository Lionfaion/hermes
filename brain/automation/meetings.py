"""Meeting Assistant: transcribe, resume y organiza reuniones."""

import json
import logging
from datetime import datetime
from pathlib import Path

from config import DATA_DIR

logger = logging.getLogger(__name__)

MEETINGS_DIR = DATA_DIR / "meetings"


def transcribe_meeting(audio_path: str) -> dict:
    from media.transcriber import transcribe

    MEETINGS_DIR.mkdir(parents=True, exist_ok=True)
    transcript = transcribe(audio_path)

    if not transcript or transcript.startswith("["):
        return {"error": "No se pudo transcribir el audio."}

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    meeting_file = MEETINGS_DIR / f"meeting_{timestamp}.json"

    meeting_data = {
        "audio": audio_path,
        "transcript": transcript,
        "date": datetime.now().isoformat(),
        "summary": "",
        "action_items": [],
    }

    meeting_file.write_text(json.dumps(meeting_data, indent=2, ensure_ascii=False), encoding="utf-8")
    return {"transcript": transcript, "file": str(meeting_file)}


def summarize_meeting(transcript: str, participants: str = "") -> str:
    from inference_client import chat

    prompt = (
        f"Resumí esta reunión:\n\n"
        f"**Participantes:** {participants or 'No especificados'}\n\n"
        f"**Transcripción:**\n{transcript[:8000]}\n\n"
        "Generá:\n"
        "1. **Resumen ejecutivo** (3-5 oraciones)\n"
        "2. **Temas tratados** (bullet points)\n"
        "3. **Decisiones tomadas**\n"
        "4. **Action items** (quién, qué, cuándo)\n"
        "5. **Próximos pasos**\n"
        "6. **Puntos pendientes** (temas que quedaron sin resolver)\n"
    )

    messages = [
        {"role": "system", "content": "Sos un asistente ejecutivo. Hacés resúmenes claros y accionables. Respondé en español."},
        {"role": "user", "content": prompt},
    ]
    return chat(messages)


def save_to_vault(summary: str, meeting_date: str = "") -> str:
    from config import VAULT_PATH
    vault = Path(VAULT_PATH)
    meetings_folder = vault / "Reuniones"
    meetings_folder.mkdir(parents=True, exist_ok=True)

    date_str = meeting_date or datetime.now().strftime("%Y-%m-%d")
    note_path = meetings_folder / f"Reunión {date_str}.md"

    counter = 1
    while note_path.exists():
        counter += 1
        note_path = meetings_folder / f"Reunión {date_str} ({counter}).md"

    content = f"# Reunión {date_str}\n\n{summary}\n\n---\n*Generado por Hermes*\n"
    note_path.write_text(content, encoding="utf-8")

    return f"Guardado en vault: {note_path.relative_to(vault)}"


def create_followup_events(action_items: str) -> str:
    from inference_client import chat

    prompt = (
        f"De estos action items, identificá cuáles necesitan un evento en calendario:\n\n"
        f"{action_items}\n\n"
        "Para cada uno que necesite calendario, generá:\n"
        "- Título del evento\n"
        "- Fecha sugerida\n"
        "- Duración estimada\n"
        "- Descripción\n"
        "Formato JSON array."
    )

    messages = [
        {"role": "system", "content": "Sos un asistente ejecutivo. Respondé en español."},
        {"role": "user", "content": prompt},
    ]
    return chat(messages)
