"""Búsqueda web usando DuckDuckGo (sin API key)."""

import logging
from dataclasses import dataclass

try:
    from ddgs import DDGS
except ImportError:
    from duckduckgo_search import DDGS

logger = logging.getLogger(__name__)


@dataclass
class SearchResult:
    title: str
    url: str
    snippet: str


def web_search(query: str, max_results: int = 5, region: str = "es-ar") -> list[SearchResult]:
    """Busca en internet y devuelve resultados."""
    try:
        with DDGS() as ddgs:
            raw = ddgs.text(query, region=region, max_results=max_results)

        results = []
        for r in raw:
            results.append(SearchResult(
                title=r.get("title", ""),
                url=r.get("href", ""),
                snippet=r.get("body", ""),
            ))
        return results
    except Exception as e:
        logger.error("Búsqueda web falló: %s", e)
        return []


def format_search_results(results: list[SearchResult]) -> str:
    """Formatea resultados de búsqueda para inyectarlos como contexto."""
    if not results:
        return ""

    lines = ["[Resultados de búsqueda web]"]
    for i, r in enumerate(results, 1):
        lines.append(f"{i}. **{r.title}**")
        lines.append(f"   URL: {r.url}")
        lines.append(f"   {r.snippet}")
        lines.append("")

    return "\n".join(lines)
