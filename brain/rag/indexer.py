"""
Indexador de la bóveda de notas (Obsidian vault) en ChromaDB.
Usa sentence-transformers con all-MiniLM-L6-v2 (liviano, rápido en CPU).
"""
import hashlib
import logging
import re
import time
from pathlib import Path

logger = logging.getLogger(__name__)


def _clean_markdown(text: str) -> str:
    text = re.sub(r"^---.*?---\n", "", text, flags=re.DOTALL)  # frontmatter
    text = re.sub(r"\[\[([^\]]+)\]\]", r"\1", text)            # wiki links
    text = re.sub(r"\[([^\]]+)\]\([^\)]+\)", r"\1", text)      # markdown links
    text = re.sub(r"#{1,6}\s", "", text)                        # headings
    text = re.sub(r"[*_`]{1,3}", "", text)                      # bold/italic/code
    text = re.sub(r"#\w+", "", text)                            # tags
    text = re.sub(r"\n{3,}", "\n\n", text)                      # blank lines
    return text.strip()


def _chunk_text(text: str, chunk_size: int = 400, overlap: int = 80) -> list:
    words = text.split()
    chunks = []
    for i in range(0, len(words), chunk_size - overlap):
        chunk = " ".join(words[i : i + chunk_size])
        if len(chunk.strip()) > 50:
            chunks.append(chunk)
    return chunks


class VaultIndexer:
    def __init__(self, vault_path: str, db_path: str):
        self.vault = Path(vault_path)
        self.db_path = db_path
        self._model = None
        self._client = None
        self._collection = None

    def _ensure_initialized(self):
        if self._model is not None:
            return
        logger.info("Cargando modelo de embeddings (primera vez descarga ~90MB)...")
        from sentence_transformers import SentenceTransformer
        import chromadb
        self._model = SentenceTransformer("all-MiniLM-L6-v2")
        self._client = chromadb.PersistentClient(path=self.db_path)
        self._collection = self._client.get_or_create_collection(
            name="vault",
            metadata={"hnsw:space": "cosine"}
        )
        logger.info("Modelo listo.")

    @property
    def model(self):
        self._ensure_initialized()
        return self._model

    @property
    def collection(self):
        self._ensure_initialized()
        return self._collection

    def index_file(self, file_path: Path) -> int:
        self._ensure_initialized()
        try:
            content = file_path.read_text(encoding="utf-8", errors="ignore")
            clean = _clean_markdown(content)
            chunks = _chunk_text(clean)
            if not chunks:
                return 0

            file_id = hashlib.md5(str(file_path).encode()).hexdigest()

            try:
                self._collection.delete(where={"file_id": file_id})
            except Exception:
                pass

            embeddings = self._model.encode(chunks, show_progress_bar=False).tolist()
            ids = [f"{file_id}_{i}" for i in range(len(chunks))]
            metadatas = [
                {"file": str(file_path), "file_id": file_id, "title": file_path.stem}
                for _ in chunks
            ]

            self._collection.add(
                embeddings=embeddings,
                documents=chunks,
                ids=ids,
                metadatas=metadatas,
            )
            return len(chunks)
        except Exception as e:
            logger.warning("Error indexando %s: %s", file_path.name, e)
            return 0

    def index_vault(self) -> int:
        self._ensure_initialized()
        md_files = list(self.vault.rglob("*.md"))
        if not md_files:
            logger.info("No se encontraron notas en %s", self.vault)
            return 0

        total = 0
        for i, f in enumerate(md_files):
            total += self.index_file(f)
            if i % 5 == 0:
                time.sleep(0.05)  # No saturar CPU en Lenovo
        logger.info("Indexadas %d notas, %d fragmentos totales.", len(md_files), total)
        return total

    def count(self) -> int:
        try:
            return self.collection.count()
        except Exception:
            return 0
