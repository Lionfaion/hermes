"""Detector de tendencias en redes sociales y web."""

import logging
from datetime import datetime

logger = logging.getLogger(__name__)


def detect_trends(niche: str = "", region: str = "es-ar", max_results: int = 10) -> list[dict]:
    from web.search import web_search

    queries = []
    if niche:
        queries.append(f"{niche} tendencias {datetime.now().year}")
        queries.append(f"{niche} viral hoy")
        queries.append(f"trending {niche} {datetime.now().strftime('%B %Y')}")
    else:
        queries.append(f"tendencias virales hoy {datetime.now().strftime('%d/%m/%Y')}")
        queries.append("trending topics redes sociales hoy")

    all_results = []
    seen_urls = set()

    for query in queries:
        try:
            results = web_search(query, region=region, max_results=max_results)
            for r in results:
                url = r.get("href", r.get("url", ""))
                if url not in seen_urls:
                    seen_urls.add(url)
                    all_results.append({
                        "title": r.get("title", ""),
                        "url": url,
                        "snippet": r.get("body", r.get("snippet", "")),
                        "query": query,
                    })
        except Exception as e:
            logger.warning("Error buscando tendencias '%s': %s", query, e)

    return all_results[:max_results]


def analyze_trend_for_content(trend: str, niche: str = "") -> str:
    from inference_client import chat

    prompt = (
        f"Analizá esta tendencia para crear contenido viral:\n\n"
        f"**Tendencia:** {trend}\n"
    )
    if niche:
        prompt += f"**Nicho:** {niche}\n"

    prompt += (
        "\nRespondé con:\n"
        "1. **Ángulo para video**: Cómo enfocar un video corto sobre esto\n"
        "2. **Hook sugerido**: Frase de apertura que capte atención\n"
        "3. **Formato recomendado**: Shorts/Reel/TikTok, duración ideal\n"
        "4. **Urgencia**: ¿Cuánto tiempo queda antes de que deje de ser tendencia?\n"
        "5. **Potencial viral**: Alto/Medio/Bajo y por qué\n"
    )

    messages = [
        {"role": "system", "content": "Sos un experto en contenido viral y tendencias. Respondé en español, sé directo."},
        {"role": "user", "content": prompt},
    ]
    return chat(messages)


def get_trending_topics_for_niche(niche: str) -> str:
    from inference_client import chat

    trends = detect_trends(niche=niche, max_results=5)

    if not trends:
        return f"No se encontraron tendencias actuales para '{niche}'."

    trends_text = "\n".join(
        f"- {t['title']}: {t['snippet'][:150]}" for t in trends
    )

    prompt = (
        f"Basándote en estas tendencias actuales del nicho '{niche}':\n\n"
        f"{trends_text}\n\n"
        "Generá 5 ideas de videos cortos (30-60s) que aprovechen estas tendencias.\n"
        "Para cada idea incluí: título, hook, y por qué funcionaría ahora."
    )

    messages = [
        {"role": "system", "content": "Sos un estratega de contenido viral. Respondé en español."},
        {"role": "user", "content": prompt},
    ]
    return chat(messages)
