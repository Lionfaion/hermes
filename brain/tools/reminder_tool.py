"""Herramienta de recordatorios/notificaciones programadas."""

import threading
import logging
import json
from datetime import datetime, timedelta
from pathlib import Path

from tools.base import BaseTool
from config import DATA_DIR

logger = logging.getLogger(__name__)

_REMINDERS_FILE = DATA_DIR / "reminders.json"
_active_timers: dict[str, threading.Timer] = {}
_notification_callback = None


def set_notification_callback(callback):
    """Configura el callback que se llama cuando un recordatorio se activa.

    El callback recibe (message: str). Debe ser configurado por el bot de
    Telegram o la interfaz que quiera recibir notificaciones.
    """
    global _notification_callback
    _notification_callback = callback


def _fire_reminder(reminder_id: str, message: str):
    logger.info("Recordatorio activado: %s", message)
    if _notification_callback:
        try:
            _notification_callback(message)
        except Exception as e:
            logger.error("Error enviando notificación: %s", e)
    _active_timers.pop(reminder_id, None)


class SetReminderTool(BaseTool):
    name = "set_reminder"
    description = (
        "Programa un recordatorio que se activará después de cierto tiempo. "
        "Úsala cuando el usuario te pida que le recuerdes algo."
    )
    parameters = {
        "type": "object",
        "properties": {
            "message": {
                "type": "string",
                "description": "Mensaje del recordatorio",
            },
            "delay_minutes": {
                "type": "integer",
                "description": "Minutos hasta que se active el recordatorio",
            },
        },
        "required": ["message", "delay_minutes"],
    }

    def execute(self, message: str, delay_minutes: int) -> str:
        if delay_minutes < 1:
            return "El delay debe ser al menos 1 minuto."
        if delay_minutes > 1440 * 7:
            return "El máximo es 7 días (10080 minutos)."

        reminder_id = f"r_{datetime.now().strftime('%Y%m%d%H%M%S')}"
        fire_at = datetime.now() + timedelta(minutes=delay_minutes)

        timer = threading.Timer(delay_minutes * 60, _fire_reminder, args=[reminder_id, message])
        timer.daemon = True
        timer.start()
        _active_timers[reminder_id] = timer

        if fire_at.date() == datetime.now().date():
            time_str = fire_at.strftime("%H:%M")
        else:
            time_str = fire_at.strftime("%d/%m %H:%M")

        return f"Recordatorio programado para las {time_str}: '{message}'"
