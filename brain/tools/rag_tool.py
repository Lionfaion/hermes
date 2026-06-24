"""Herramienta de búsqueda en notas personales (Obsidian vault via RAG)."""

from tools.base import BaseTool


class SearchNotesTool(BaseTool):
    name = "search_notes"
    description = (
        "Busca en las notas personales del usuario (Obsidian vault). "
        "Úsala cuando el usuario pregunte sobre algo que podría estar en sus notas, "
        "documentos personales o base de conocimiento."
    )
    parameters = {
        "type": "object",
        "properties": {
            "query": {
                "type": "string",
                "description": "Texto de búsqueda semántica en las notas",
            },
        },
        "required": ["query"],
    }

    def __init__(self):
        self._searcher = None

    def _get_searcher(self):
        if self._searcher is None:
            from config import VAULT_PATH, CHROMA_PATH
            from rag.indexer import VaultIndexer
            from rag.searcher import VaultSearcher
            indexer = VaultIndexer(VAULT_PATH, CHROMA_PATH)
            self._searcher = VaultSearcher(indexer)
        return self._searcher

    def execute(self, query: str) -> str:
        try:
            searcher = self._get_searcher()
            ctx = searcher.build_context(query)
            return ctx if ctx else "No se encontraron notas relevantes."
        except Exception as e:
            return f"Error buscando en notas: {e}"
