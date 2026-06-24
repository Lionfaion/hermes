"""Navegador headless con Playwright para páginas dinámicas con JavaScript."""

import logging
from dataclasses import dataclass

logger = logging.getLogger(__name__)

MAX_CONTENT_LENGTH = 50_000


@dataclass
class BrowseResult:
    url: str
    title: str
    text: str
    success: bool
    error: str = ""


def _is_playwright_available() -> bool:
    try:
        from playwright.sync_api import sync_playwright  # noqa: F401
        return True
    except ImportError:
        return False


def browse_page(url: str, timeout: int = 30000, wait_for: str = "networkidle") -> BrowseResult:
    """Navega una página con JavaScript renderizado usando Playwright.

    Args:
        url: URL a navegar.
        timeout: Timeout en milisegundos.
        wait_for: Estrategia de espera ('load', 'domcontentloaded', 'networkidle').
    """
    if not _is_playwright_available():
        return BrowseResult(
            url=url, title="", text="", success=False,
            error="Playwright no instalado. Ejecutá: pip install playwright && playwright install chromium"
        )

    try:
        from playwright.sync_api import sync_playwright

        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page(
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                           "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
            )
            page.goto(url, timeout=timeout, wait_until=wait_for)

            title = page.title()

            text = page.evaluate("""() => {
                const selectors = ['script', 'style', 'nav', 'footer', 'header', 'aside', 'noscript'];
                selectors.forEach(s => {
                    document.querySelectorAll(s).forEach(el => el.remove());
                });
                const main = document.querySelector('main')
                           || document.querySelector('article')
                           || document.body;
                return main ? main.innerText : document.body.innerText;
            }""")

            browser.close()

        if len(text) > MAX_CONTENT_LENGTH:
            text = text[:MAX_CONTENT_LENGTH] + "\n[... contenido truncado]"

        return BrowseResult(url=url, title=title, text=text, success=True)

    except Exception as e:
        logger.error("Playwright error en %s: %s", url, e)
        return BrowseResult(url=url, title="", text="", success=False, error=str(e))
