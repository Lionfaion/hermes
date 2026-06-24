"""Monitor de Reputación: busca menciones y analiza sentimiento."""

import json
import logging
from datetime import datetime
from pathlib import Path

from config import DATA_DIR

logger = logging.getLogger(__name__)

REPUTATION_FILE = DATA_DIR / "reputation_log.json"


def monitor_brand(brand_name: str, additional_terms: str = "") -> str:
    from web.search import web_search
    from inference_client import chat

    queries = [
        f'"{brand_name}" opiniones reseñas',
        f'"{brand_name}" reviews',
        f'"{brand_name}" redes sociales mencionado',
    ]
    if additional_terms:
        queries.append(f'"{brand_name}" {additional_terms}')

    all_results = []
    for q in queries:
        try:
            results = web_search(q, max_results=5)
            for r in results:
                all_results.append({
                    "title": r.get("title", ""),
                    "url": r.get("href", r.get("url", "")),
                    "snippet": r.get("body", r.get("snippet", "")),
                })
        except Exception:
            pass

    if not all_results:
        return f"No se encontraron menciones de '{brand_name}'."

    mentions_text = "\n".join(
        f"- {r['title']}: {r['snippet'][:150]}" for r in all_results[:15]
    )

    prompt = (
        f"Analizá las menciones de la marca/persona '{brand_name}':\n\n"
        f"{mentions_text}\n\n"
        "Respondé con:\n"
        "- **Sentimiento general:** positivo/neutro/negativo\n"
        "- **Menciones positivas:** resumen\n"
        "- **Menciones negativas:** resumen y nivel de urgencia\n"
        "- **Temas recurrentes:** qué se dice más\n"
        "- **Acciones sugeridas:** qué hacer al respecto\n"
        "- **Alertas:** algo que requiera atención inmediata\n"
    )

    messages = [
        {"role": "system", "content": "Sos un especialista en gestión de reputación online. Respondé en español."},
        {"role": "user", "content": prompt},
    ]

    analysis = chat(messages)

    _log_scan(brand_name, len(all_results), analysis[:200])

    return analysis


def generate_response(negative_review: str, brand_context: str = "") -> str:
    from inference_client import chat

    prompt = (
        f"Generá una respuesta profesional a esta reseña negativa:\n\n"
        f"**Reseña:** {negative_review}\n"
        f"**Contexto de la marca:** {brand_context or 'No especificado'}\n\n"
        "La respuesta debe:\n"
        "- Ser empática y profesional\n"
        "- Reconocer el problema sin excusarse\n"
        "- Ofrecer una solución concreta\n"
        "- Invitar a resolver por privado\n"
        "- Máx 100 palabras\n"
    )

    messages = [
        {"role": "system", "content": "Sos un community manager experto en manejo de crisis. Respondé en español."},
        {"role": "user", "content": prompt},
    ]
    return chat(messages)


def _log_scan(brand: str, mentions_count: int, summary: str) -> None:
    try:
        log = []
        if REPUTATION_FILE.exists():
            log = json.loads(REPUTATION_FILE.read_text(encoding="utf-8"))
        log.append({
            "brand": brand,
            "mentions": mentions_count,
            "summary": summary,
            "timestamp": datetime.now().isoformat(),
        })
        REPUTATION_FILE.parent.mkdir(parents=True, exist_ok=True)
        REPUTATION_FILE.write_text(json.dumps(log[-200:], indent=2, ensure_ascii=False), encoding="utf-8")
    except Exception:
        pass
