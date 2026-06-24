"""Herramienta unificada de navegación web para el asistente."""

import logging
import re

from web.scraper import fetch_page, PageResult
from web.search import web_search, format_search_results, SearchResult
from web.browser import browse_page, BrowseResult

logger = logging.getLogger(__name__)

_URL_PATTERN = re.compile(r'https?://[^\s<>"\']+')


def extract_urls(text: str) -> list[str]:
    """Extrae URLs de un texto."""
    return _URL_PATTERN.findall(text)


def detect_web_intent(user_input: str) -> dict:
    """Detecta si el usuario quiere buscar en la web o analizar una URL.

    Retorna:
        {"action": "none"} - No hay intención web
        {"action": "search", "query": "..."} - Búsqueda web
        {"action": "fetch", "urls": [...]} - Analizar URLs específicas
        {"action": "browse", "urls": [...]} - Navegar URLs dinámicas
    """
    text = user_input.lower()
    urls = extract_urls(user_input)

    if urls:
        browse_keywords = ["navega", "renderiz", "javascript", "dinamica", "dinámica",
                           "carga completa", "playwright", "browse"]
        if any(kw in text for kw in browse_keywords):
            return {"action": "browse", "urls": urls}
        return {"action": "fetch", "urls": urls}

    search_keywords = [
        "busca en internet", "busca en la web", "busca online",
        "buscá en internet", "buscá en la web", "buscá online",
        "buscar en internet", "buscar en la web", "buscar online",
        "qué dice internet", "que dice internet",
        "investiga sobre", "investigá sobre",
        "search for", "search the web", "web search",
        "googlea", "googleá", "google ",
    ]
    if any(kw in text for kw in search_keywords):
        for kw in search_keywords:
            if kw in text:
                query = text.split(kw, 1)[1].strip().strip('"').strip("'")
                if query:
                    return {"action": "search", "query": query}
        return {"action": "search", "query": user_input}

    return {"action": "none"}


def process_web_action(intent: dict, use_browser: bool = False) -> str:
    """Ejecuta la acción web y devuelve contexto formateado para el LLM."""
    action = intent.get("action", "none")

    if action == "none":
        return ""

    if action == "search":
        query = intent["query"]
        logger.info("Buscando en la web: %s", query)
        results = web_search(query)
        if not results:
            return "[Búsqueda web: no se encontraron resultados]"
        return format_search_results(results)

    if action == "fetch":
        return _process_urls(intent["urls"], use_browser=False)

    if action == "browse":
        return _process_urls(intent["urls"], use_browser=True)

    return ""


def _process_urls(urls: list[str], use_browser: bool) -> str:
    """Procesa una lista de URLs y devuelve el contenido formateado."""
    parts = []
    for url in urls[:3]:  # Limitar a 3 URLs por petición
        if use_browser:
            logger.info("Navegando (headless): %s", url)
            result = browse_page(url)
        else:
            logger.info("Descargando: %s", url)
            result = fetch_page(url)

        if isinstance(result, (PageResult, BrowseResult)) and result.success:
            parts.append(
                f"[Contenido de: {result.url}]\n"
                f"Título: {result.title}\n"
                f"---\n{result.text}\n---"
            )
        else:
            parts.append(f"[Error al cargar {url}: {result.error}]")

    return "\n\n".join(parts)
