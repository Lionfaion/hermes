"""Herramienta de email: leer y enviar emails via IMAP/SMTP."""

import logging

from tools.base import BaseTool

logger = logging.getLogger(__name__)


class EmailTool(BaseTool):
    name = "email"
    description = (
        "Gestiona emails: leer inbox, buscar emails, enviar respuestas. "
        "Requiere configurar IMAP/SMTP en .env."
    )
    parameters = {
        "type": "object",
        "properties": {
            "action": {
                "type": "string",
                "description": "Acción: inbox, search, send, read",
                "enum": ["inbox", "search", "send", "read"],
            },
            "query": {
                "type": "string",
                "description": "Búsqueda para action=search (remitente, asunto, etc)",
            },
            "to": {
                "type": "string",
                "description": "Destinatario para action=send",
            },
            "subject": {
                "type": "string",
                "description": "Asunto para action=send",
            },
            "body": {
                "type": "string",
                "description": "Cuerpo del email para action=send",
            },
            "count": {
                "type": "integer",
                "description": "Cantidad de emails a mostrar (default: 5)",
            },
            "email_id": {
                "type": "string",
                "description": "ID del email para action=read",
            },
        },
        "required": ["action"],
    }

    def execute(
        self,
        action: str,
        query: str = "",
        to: str = "",
        subject: str = "",
        body: str = "",
        count: int = 5,
        email_id: str = "",
    ) -> str:
        try:
            from integrations.email_client import (
                get_inbox,
                search_emails,
                send_email,
                read_email,
            )
        except ImportError:
            return (
                "Email no configurado. Agregá estas variables al .env:\n"
                "EMAIL_ADDRESS=tu@email.com\n"
                "EMAIL_PASSWORD=contraseña-de-app\n"
                "IMAP_SERVER=imap.gmail.com\n"
                "SMTP_SERVER=smtp.gmail.com\n"
                "SMTP_PORT=587"
            )

        if action == "inbox":
            return get_inbox(count)
        elif action == "search":
            if not query:
                return "Necesito una búsqueda (query)."
            return search_emails(query, count)
        elif action == "send":
            if not to or not subject or not body:
                return "Necesito: to, subject y body para enviar."
            return send_email(to, subject, body)
        elif action == "read":
            if not email_id:
                return "Necesito el email_id."
            return read_email(email_id)
        return f"Acción '{action}' no reconocida."
