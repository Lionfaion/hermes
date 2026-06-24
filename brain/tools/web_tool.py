"""Herramientas web: búsqueda en internet y análisis de páginas."""

from tools.base import BaseTool


class WebSearchTool(BaseTool):
    name = "web_search"
    description = (
        "Busca información en internet usando DuckDuckGo. "
        "Úsala cuando el usuario pregunte algo que requiera información actualizada "
        "o que no sepas con certeza."
    )
    parameters = {
        "type": "object",
        "properties": {
            "query": {
                "type": "string",
                "description": "Texto de búsqueda",
            },
            "max_results": {
                "type": "integer",
                "description": "Cantidad máxima de resultados (default 5)",
            },
        },
        "required": ["query"],
    }

    def execute(self, query: str, max_results: int = 5) -> str:
        from web.search import web_search, format_search_results
        results = web_search(query, max_results=max_results)
        if not results:
            return "No se encontraron resultados para esa búsqueda."
        return format_search_results(results)


class WebFetchTool(BaseTool):
    name = "web_fetch"
    description = (
        "Descarga y extrae el contenido de texto de una página web. "
        "Úsala cuando el usuario te pase una URL para analizar."
    )
    parameters = {
        "type": "object",
        "properties": {
            "url": {
                "type": "string",
                "description": "URL de la página a descargar",
            },
            "use_browser": {
                "type": "boolean",
                "description": "Usar navegador headless para páginas con JavaScript (default false)",
            },
        },
        "required": ["url"],
    }

    def execute(self, url: str, use_browser: bool = False) -> str:
        if use_browser:
            from web.browser import browse_page
            result = browse_page(url)
        else:
            from web.scraper import fetch_page
            result = fetch_page(url)

        if result.success:
            return f"Título: {result.title}\n---\n{result.text}"
        return f"Error al cargar {url}: {result.error}"
