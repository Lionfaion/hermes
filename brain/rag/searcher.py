"""
Buscador semántico sobre el vault indexado en ChromaDB.
"""
import logging
from pathlib import Path

logger = logging.getLogger(__name__)


class VaultSearcher:
    def __init__(self, indexer):
        self.indexer = indexer

    def search(self, query: str, n_results: int = 4) -> list:
        try:
            if self.indexer.count() == 0:
                return []

            q_emb = self.indexer.model.encode([query], show_progress_bar=False).tolist()
            results = self.indexer.collection.query(
                query_embeddings=q_emb,
                n_results=min(n_results, self.indexer.count()),
            )

            chunks = []
            for doc, meta, dist in zip(
                results["documents"][0],
                results["metadatas"][0],
                results["distances"][0],
            ):
                relevance = 1 - dist  # cosine → similarity
                if relevance > 0.3:   # threshold mínimo
                    chunks.append({
                        "text": doc,
                        "title": meta.get("title", "nota"),
                        "relevance": round(relevance, 3),
                    })
            return chunks
        except Exception as e:
            logger.warning("RAG search error: %s", e)
            return []

    def build_context(self, query: str) -> str:
        chunks = self.search(query)
        if not chunks:
            return ""

        parts = ["[Contexto de tus notas personales — usa esta información si es relevante:]"]
        for c in chunks:
            parts.append(f'[Nota: "{c["title"]}" | Relevancia: {c["relevance"]}]\n{c["text"]}')

        return "\n\n".join(parts)
