"""Personal CRM: gestión de contactos, follow-ups y contexto de relaciones."""

import json
import logging
from datetime import datetime, timedelta
from pathlib import Path

from config import DATA_DIR

logger = logging.getLogger(__name__)

CRM_FILE = DATA_DIR / "crm_contacts.json"


def _load_contacts() -> dict:
    if CRM_FILE.exists():
        try:
            return json.loads(CRM_FILE.read_text(encoding="utf-8"))
        except Exception:
            return {}
    return {}


def _save_contacts(contacts: dict) -> None:
    CRM_FILE.parent.mkdir(parents=True, exist_ok=True)
    CRM_FILE.write_text(json.dumps(contacts, indent=2, ensure_ascii=False), encoding="utf-8")


def add_contact(
    name: str,
    email: str = "",
    phone: str = "",
    company: str = "",
    role: str = "",
    notes: str = "",
    tags: list[str] | None = None,
) -> dict:
    contacts = _load_contacts()
    contact_id = name.lower().replace(" ", "_")

    contacts[contact_id] = {
        "name": name,
        "email": email,
        "phone": phone,
        "company": company,
        "role": role,
        "notes": notes,
        "tags": tags or [],
        "interactions": [],
        "created_at": datetime.now().isoformat(),
        "last_contact": datetime.now().isoformat(),
        "follow_up_days": 14,
    }
    _save_contacts(contacts)
    return contacts[contact_id]


def log_interaction(contact_name: str, interaction_type: str, summary: str) -> str:
    contacts = _load_contacts()
    contact_id = contact_name.lower().replace(" ", "_")

    if contact_id not in contacts:
        return f"Contacto '{contact_name}' no encontrado."

    contacts[contact_id]["interactions"].append({
        "type": interaction_type,
        "summary": summary,
        "date": datetime.now().isoformat(),
    })
    contacts[contact_id]["last_contact"] = datetime.now().isoformat()

    _save_contacts(contacts)
    return f"Interacción registrada con {contact_name}."


def get_contact(contact_name: str) -> str:
    contacts = _load_contacts()
    contact_id = contact_name.lower().replace(" ", "_")

    contact = contacts.get(contact_id)
    if not contact:
        return f"Contacto '{contact_name}' no encontrado."

    lines = [
        f"**{contact['name']}**",
        f"Empresa: {contact.get('company', '-')} | Rol: {contact.get('role', '-')}",
        f"Email: {contact.get('email', '-')} | Tel: {contact.get('phone', '-')}",
        f"Tags: {', '.join(contact.get('tags', []))}",
        f"Notas: {contact.get('notes', '-')}",
        f"Último contacto: {contact.get('last_contact', '-')}",
    ]

    interactions = contact.get("interactions", [])[-5:]
    if interactions:
        lines.append("\n**Últimas interacciones:**")
        for i in interactions:
            lines.append(f"- [{i['date'][:10]}] {i['type']}: {i['summary']}")

    return "\n".join(lines)


def get_pending_followups() -> str:
    contacts = _load_contacts()
    now = datetime.now()
    pending = []

    for cid, contact in contacts.items():
        last = contact.get("last_contact", "")
        follow_days = contact.get("follow_up_days", 14)

        if last:
            try:
                last_dt = datetime.fromisoformat(last)
                days_since = (now - last_dt).days
                if days_since >= follow_days:
                    pending.append({
                        "name": contact["name"],
                        "days_since": days_since,
                        "company": contact.get("company", ""),
                        "last_interaction": contact.get("interactions", [{}])[-1].get("summary", "N/A") if contact.get("interactions") else "N/A",
                    })
            except Exception:
                pass

    if not pending:
        return "No hay follow-ups pendientes. Todos los contactos están al día."

    pending.sort(key=lambda x: x["days_since"], reverse=True)

    lines = ["**Follow-ups pendientes:**\n"]
    for p in pending:
        lines.append(
            f"- **{p['name']}** ({p['company']}): {p['days_since']} días sin contacto\n"
            f"  Último: {p['last_interaction']}"
        )

    return "\n".join(lines)


def search_contacts(query: str) -> str:
    contacts = _load_contacts()
    q = query.lower()

    matches = []
    for cid, contact in contacts.items():
        searchable = f"{contact.get('name', '')} {contact.get('company', '')} {contact.get('role', '')} {' '.join(contact.get('tags', []))} {contact.get('notes', '')}".lower()
        if q in searchable:
            matches.append(contact)

    if not matches:
        return f"No se encontraron contactos con '{query}'."

    lines = [f"**Resultados para '{query}' ({len(matches)}):**\n"]
    for c in matches[:10]:
        lines.append(f"- **{c['name']}** — {c.get('company', '-')} ({c.get('role', '-')})")

    return "\n".join(lines)


def prepare_meeting_context(contact_name: str) -> str:
    from inference_client import chat

    contact_info = get_contact(contact_name)
    if "no encontrado" in contact_info.lower():
        return contact_info

    prompt = (
        f"Preparame un brief para una reunión con este contacto:\n\n"
        f"{contact_info}\n\n"
        "Incluí:\n"
        "- Resumen de la relación\n"
        "- Temas pendientes de conversaciones anteriores\n"
        "- Sugerencias de temas para hablar\n"
        "- Recordatorios importantes\n"
    )

    messages = [
        {"role": "system", "content": "Sos un asistente ejecutivo. Sé conciso y útil. Respondé en español."},
        {"role": "user", "content": prompt},
    ]
    return chat(messages)
