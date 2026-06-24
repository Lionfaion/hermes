"""Herramienta de Google Calendar para crear, listar y gestionar eventos."""

import logging
from datetime import datetime, timedelta

from tools.base import BaseTool

logger = logging.getLogger(__name__)


class CalendarTool(BaseTool):
    name = "calendar"
    description = (
        "Gestiona Google Calendar: crear eventos, ver agenda del día, "
        "buscar disponibilidad. Requiere configurar las credenciales de Google Calendar."
    )
    parameters = {
        "type": "object",
        "properties": {
            "action": {
                "type": "string",
                "description": "Acción: create, today, week, delete",
                "enum": ["create", "today", "week", "delete"],
            },
            "title": {
                "type": "string",
                "description": "Título del evento (para create)",
            },
            "date": {
                "type": "string",
                "description": "Fecha (YYYY-MM-DD). Default: hoy",
            },
            "time": {
                "type": "string",
                "description": "Hora (HH:MM). Para create.",
            },
            "duration_minutes": {
                "type": "integer",
                "description": "Duración en minutos (default: 60)",
            },
            "description": {
                "type": "string",
                "description": "Descripción del evento",
            },
            "event_id": {
                "type": "string",
                "description": "ID del evento (para delete)",
            },
        },
        "required": ["action"],
    }

    def execute(
        self,
        action: str,
        title: str = "",
        date: str = "",
        time: str = "",
        duration_minutes: int = 60,
        description: str = "",
        event_id: str = "",
    ) -> str:
        try:
            from integrations.google_calendar import (
                create_event,
                get_events_today,
                get_events_week,
                delete_event,
            )
        except ImportError:
            return (
                "Google Calendar no configurado. Necesitás:\n"
                "1. Crear proyecto en console.cloud.google.com\n"
                "2. Activar Google Calendar API\n"
                "3. Crear credenciales OAuth y descargar credentials.json\n"
                "4. Ponerlo en brain/data/google_credentials.json"
            )

        if action == "today":
            return get_events_today()
        elif action == "week":
            return get_events_week()
        elif action == "create":
            if not title:
                return "Necesito un título para el evento."
            return create_event(title, date, time, duration_minutes, description)
        elif action == "delete":
            if not event_id:
                return "Necesito el event_id para borrar."
            return delete_event(event_id)
        return f"Acción '{action}' no reconocida."
