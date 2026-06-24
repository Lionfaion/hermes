"""Scraping simple de páginas web usando httpx + BeautifulSoup."""

import logging
from dataclasses import dataclass

import httpx
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)

_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "es-ES,es;q=0.9,en;q=0.8",
}

MAX_CONTENT_LENGTH = 50_000


@dataclass
class PageResult:
    url: str
    title: str
    text: str
    status_code: int
    success: bool
    error: str = ""


def _extract_text(html: str) -> tuple[str, str]:
    """Extrae título y texto limpio del HTML."""
    soup = BeautifulSoup(html, "html.parser")

    for tag in soup(["script", "style", "nav", "footer", "header", "aside", "noscript"]):
        tag.decompose()

    title = soup.title.string.strip() if soup.title and soup.title.string else ""

    # Priorizar contenido principal
    main = soup.find("main") or soup.find("article") or soup.find("body")
    if main is None:
        main = soup

    lines = []
    for element in main.stripped_strings:
        line = element.strip()
        if line:
            lines.append(line)

    text = "\n".join(lines)
    if len(text) > MAX_CONTENT_LENGTH:
        text = text[:MAX_CONTENT_LENGTH] + "\n[... contenido truncado]"

    return title, text


def fetch_page(url: str, timeout: float = 15.0) -> PageResult:
    """Descarga y extrae el texto de una URL."""
    try:
        with httpx.Client(timeout=timeout, follow_redirects=True, headers=_HEADERS) as client:
            resp = client.get(url)
            resp.raise_for_status()

        title, text = _extract_text(resp.text)
        return PageResult(
            url=str(resp.url),
            title=title,
            text=text,
            status_code=resp.status_code,
            success=True,
        )
    except httpx.TimeoutException:
        logger.warning("Timeout al cargar %s", url)
        return PageResult(url=url, title="", text="", status_code=0, success=False,
                          error=f"Timeout después de {timeout}s")
    except httpx.HTTPStatusError as e:
        logger.warning("HTTP %d en %s", e.response.status_code, url)
        return PageResult(url=url, title="", text="", status_code=e.response.status_code,
                          success=False, error=f"HTTP {e.response.status_code}")
    except Exception as e:
        logger.error("Error al descargar %s: %s", url, e)
        return PageResult(url=url, title="", text="", status_code=0, success=False,
                          error=str(e))
