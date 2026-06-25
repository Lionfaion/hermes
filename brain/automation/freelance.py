"""Freelance Autopilot: monitorea oportunidades y genera propuestas."""

import logging
from datetime import datetime

logger = logging.getLogger(__name__)


def search_freelance_jobs(skills: str, platforms: str = "freelance", max_results: int = 10) -> list[dict]:
    from web.search import web_search

    queries = [
        f"freelance {skills} trabajo remoto",
        f"busco freelancer {skills} proyecto",
        f"hiring {skills} remote contractor",
    ]

    jobs = []
    seen = set()
    for q in queries:
        try:
            results = web_search(q, max_results=max_results)
            for r in results:
                url = r.get("href", r.get("url", ""))
                if url not in seen:
                    seen.add(url)
                    jobs.append({
                        "title": r.get("title", ""),
                        "url": url,
                        "description": r.get("body", r.get("snippet", "")),
                        "skills": skills,
                        "found_at": datetime.now().isoformat(),
                    })
        except Exception as e:
            logger.warning("Error buscando trabajos freelance: %s", e)

    return jobs[:max_results]


def generate_proposal(job: dict, my_skills: str, experience: str = "", rate: str = "") -> str:
    from inference_client import chat

    prompt = (
        f"Generá una propuesta de freelance para este trabajo:\n\n"
        f"**Trabajo:** {job.get('title', '')}\n"
        f"**Descripción:** {job.get('description', '')}\n\n"
        f"**Mis habilidades:** {my_skills}\n"
        f"**Mi experiencia:** {experience or 'No especificada'}\n"
        f"**Mi tarifa:** {rate or 'A discutir'}\n\n"
        "La propuesta debe:\n"
        "- Ser directa y personalizada al proyecto\n"
        "- Mostrar que entendí lo que necesitan\n"
        "- Incluir cómo resolvería el problema\n"
        "- Mencionar experiencia relevante\n"
        "- Tener un CTA para agendar llamada\n"
        "- Máx 200 palabras\n"
    )

    messages = [
        {"role": "system", "content": "Sos un freelancer exitoso que escribe propuestas ganadoras. Respondé en español."},
        {"role": "user", "content": prompt},
    ]
    return chat(messages)


def analyze_job_fit(job: dict, my_skills: str) -> str:
    from inference_client import chat

    prompt = (
        f"Analizá si este trabajo freelance es un buen fit:\n\n"
        f"**Trabajo:** {job.get('title', '')}\n"
        f"**Descripción:** {job.get('description', '')}\n"
        f"**Mis skills:** {my_skills}\n\n"
        "Respondé con:\n"
        "- **Match (1-10):** qué tan bien calzan mis skills\n"
        "- **Pros:** por qué aplicar\n"
        "- **Contras:** posibles problemas\n"
        "- **Tarifa sugerida:** rango estimado\n"
        "- **Recomendación:** aplicar sí/no y por qué\n"
    )

    messages = [
        {"role": "system", "content": "Sos un consultor de carrera freelance. Sé directo y honesto."},
        {"role": "user", "content": prompt},
    ]
    return chat(messages)
