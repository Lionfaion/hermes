"""Cliente de email IMAP/SMTP."""

import email
import imaplib
import logging
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.header import decode_header

from config import (
    EMAIL_ADDRESS, EMAIL_PASSWORD,
    IMAP_SERVER, SMTP_SERVER, SMTP_PORT,
)

logger = logging.getLogger(__name__)


def _decode_subject(subject_header: str) -> str:
    decoded = decode_header(subject_header)
    parts = []
    for data, charset in decoded:
        if isinstance(data, bytes):
            parts.append(data.decode(charset or "utf-8", errors="ignore"))
        else:
            parts.append(data)
    return " ".join(parts)


def _connect_imap():
    if not EMAIL_ADDRESS or not EMAIL_PASSWORD:
        raise RuntimeError("Email no configurado (EMAIL_ADDRESS/EMAIL_PASSWORD)")
    mail = imaplib.IMAP4_SSL(IMAP_SERVER)
    mail.login(EMAIL_ADDRESS, EMAIL_PASSWORD)
    return mail


def get_inbox(count: int = 5) -> str:
    mail = _connect_imap()
    mail.select("INBOX")

    _, data = mail.search(None, "ALL")
    ids = data[0].split()
    recent_ids = ids[-count:] if len(ids) >= count else ids

    lines = [f"**Inbox ({len(ids)} emails totales, mostrando {len(recent_ids)}):**\n"]

    for eid in reversed(recent_ids):
        _, msg_data = mail.fetch(eid, "(RFC822)")
        msg = email.message_from_bytes(msg_data[0][1])

        subject = _decode_subject(msg.get("Subject", "Sin asunto"))
        sender = msg.get("From", "Desconocido")
        date = msg.get("Date", "")

        lines.append(f"- **{subject}**\n  De: {sender}\n  Fecha: {date}\n  ID: {eid.decode()}")

    mail.logout()
    return "\n".join(lines)


def search_emails(query: str, count: int = 5) -> str:
    mail = _connect_imap()
    mail.select("INBOX")

    search_criteria = f'(OR (SUBJECT "{query}") (FROM "{query}"))'
    _, data = mail.search(None, search_criteria)
    ids = data[0].split()

    if not ids:
        mail.logout()
        return f"No se encontraron emails con '{query}'."

    recent = ids[-count:] if len(ids) >= count else ids
    lines = [f"**Resultados para '{query}' ({len(ids)} encontrados):**\n"]

    for eid in reversed(recent):
        _, msg_data = mail.fetch(eid, "(RFC822)")
        msg = email.message_from_bytes(msg_data[0][1])

        subject = _decode_subject(msg.get("Subject", "Sin asunto"))
        sender = msg.get("From", "Desconocido")
        lines.append(f"- **{subject}** — {sender} (ID: {eid.decode()})")

    mail.logout()
    return "\n".join(lines)


def read_email(email_id: str) -> str:
    mail = _connect_imap()
    mail.select("INBOX")

    _, msg_data = mail.fetch(email_id.encode(), "(RFC822)")
    if not msg_data or not msg_data[0]:
        mail.logout()
        return f"Email ID {email_id} no encontrado."

    msg = email.message_from_bytes(msg_data[0][1])
    subject = _decode_subject(msg.get("Subject", "Sin asunto"))
    sender = msg.get("From", "Desconocido")
    date = msg.get("Date", "")

    body = ""
    if msg.is_multipart():
        for part in msg.walk():
            if part.get_content_type() == "text/plain":
                body = part.get_payload(decode=True).decode("utf-8", errors="ignore")
                break
    else:
        body = msg.get_payload(decode=True).decode("utf-8", errors="ignore")

    mail.logout()

    body = body[:3000] + "..." if len(body) > 3000 else body
    return f"**{subject}**\nDe: {sender}\nFecha: {date}\n\n{body}"


def send_email(to: str, subject: str, body: str) -> str:
    if not EMAIL_ADDRESS or not EMAIL_PASSWORD:
        return "Email no configurado."

    msg = MIMEMultipart()
    msg["From"] = EMAIL_ADDRESS
    msg["To"] = to
    msg["Subject"] = subject
    msg.attach(MIMEText(body, "plain", "utf-8"))

    try:
        with smtplib.SMTP(SMTP_SERVER, SMTP_PORT) as server:
            server.starttls()
            server.login(EMAIL_ADDRESS, EMAIL_PASSWORD)
            server.send_message(msg)
        logger.info("Email enviado a %s: %s", to, subject)
        return f"Email enviado a {to}: **{subject}**"
    except Exception as e:
        return f"Error enviando email: {e}"
