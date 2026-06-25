"""Lead Generation automático: busca prospectos y genera outreach personalizado."""

import json
import logging
from datetime import datetime
from pathlib import Path

from config import DATA_DIR

logger = logging.getLogger(__name__)

LEADS_FILE = DATA_DIR / "leads.json"


def _load_leads() -> list:
    if LEADS_FILE.exists():
        try:
            return json.loads(LEADS_FILE.read_text(encoding="utf-8"))
        except Exception:
            return []
    return []


def _save_leads(leads: list) -> None:
    LEADS_FILE.parent.mkdir(parents=True, exist_ok=True)
    LEADS_FILE.write_text(json.dumps(leads[-1000:], indent=2, ensure_ascii=False), encoding="utf-8")


def search_leads(industry: str, location: str = "", count: int = 10) -> list[dict]:
    from web.search import web_search

    queries = [
        f"{industry} empresas {location}".strip(),
        f"{industry} founders contacto {location}".strip(),
        f"{industry} directorio empresas {location}".strip(),
    ]

    leads = []
    seen = set()
    for q in queries:
        try:
            results = web_search(q, max_results=count)
            for r in results:
                url = r.get("href", r.get("url", ""))
                if url not in seen:
                    seen.add(url)
                    leads.append({
                        "source": url,
                        "title": r.get("title", ""),
                        "snippet": r.get("body", r.get("snippet", "")),
                        "industry": industry,
                        "location": location,
                        "found_at": datetime.now().isoformat(),
                        "status": "new",
                    })
        except Exception as e:
            logger.warning("Error buscando leads: %s", e)

    return leads[:count]


def generate_outreach(lead: dict, product_service: str, tone: str = "profesional") -> str:
    from inference_client import chat

    prompt = (
        f"Generá un email de outreach personalizado para este prospecto:\n\n"
        f"**Empresa/Contacto:** {lead.get('title', 'Desconocido')}\n"
        f"**Info:** {lead.get('snippet', '')}\n"
        f"**Industria:** {lead.get('industry', '')}\n\n"
        f"**Lo que ofrezco:** {product_service}\n"
        f"**Tono:** {tone}\n\n"
        "El email debe:\n"
        "- Ser corto (máx 150 palabras)\n"
        "- Personalizado al negocio del prospecto\n"
        "- Tener un asunto que genere curiosidad\n"
        "- Incluir un CTA claro\n"
        "- No sonar como spam\n"
        "Formato: ASUNTO: ...\n\nCUERPO: ..."
    )

    messages = [
        {"role": "system", "content": "Sos un experto en cold outreach B2B. Respondé en español."},
        {"role": "user", "content": prompt},
    ]
    return chat(messages)


def save_lead(lead: dict) -> None:
    leads = _load_leads()
    leads.append(lead)
    _save_leads(leads)


def get_leads(status: str = "", industry: str = "") -> list[dict]:
    leads = _load_leads()
    if status:
        leads = [l for l in leads if l.get("status") == status]
    if industry:
        leads = [l for l in leads if l.get("industry") == industry]
    return leads


def update_lead_status(index: int, status: str) -> bool:
    leads = _load_leads()
    if 0 <= index < len(leads):
        leads[index]["status"] = status
        leads[index]["updated_at"] = datetime.now().isoformat()
        _save_leads(leads)
        return True
    return False
