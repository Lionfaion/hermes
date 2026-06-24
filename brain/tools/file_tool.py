"""Herramienta de análisis de archivos (PDF, texto, imágenes)."""

import logging
from pathlib import Path

from tools.base import BaseTool
from config import DATA_DIR

logger = logging.getLogger(__name__)

SAFE_DIRS = [str(DATA_DIR), str(Path.home())]
MAX_FILE_SIZE = 10 * 1024 * 1024  # 10MB


class AnalyzeFileTool(BaseTool):
    name = "analyze_file"
    description = (
        "Lee y analiza un archivo local (PDF, texto, CSV, etc.). "
        "Úsala cuando el usuario te pida leer o resumir un documento."
    )
    parameters = {
        "type": "object",
        "properties": {
            "file_path": {
                "type": "string",
                "description": "Ruta al archivo a analizar",
            },
        },
        "required": ["file_path"],
    }

    def execute(self, file_path: str) -> str:
        path = Path(file_path).resolve()

        if not path.exists():
            return f"Archivo no encontrado: {file_path}"

        if path.stat().st_size > MAX_FILE_SIZE:
            return f"Archivo demasiado grande (máx {MAX_FILE_SIZE // 1024 // 1024}MB)"

        suffix = path.suffix.lower()

        if suffix == ".pdf":
            return self._read_pdf(path)
        elif suffix in (".txt", ".md", ".csv", ".json", ".yaml", ".yml", ".log"):
            return self._read_text(path)
        else:
            return f"Formato no soportado: {suffix}"

    def _read_pdf(self, path: Path) -> str:
        try:
            from PyPDF2 import PdfReader
            reader = PdfReader(str(path))
            text = ""
            for page in reader.pages[:50]:
                text += page.extract_text() or ""
            if not text.strip():
                return "El PDF no contiene texto extraíble."
            if len(text) > 50000:
                text = text[:50000] + "\n[... contenido truncado]"
            return f"[Contenido de {path.name}]\n{text}"
        except ImportError:
            return "PyPDF2 no instalado. Ejecutá: pip install PyPDF2"
        except Exception as e:
            return f"Error leyendo PDF: {e}"

    def _read_text(self, path: Path) -> str:
        try:
            text = path.read_text(encoding="utf-8")
            if len(text) > 50000:
                text = text[:50000] + "\n[... contenido truncado]"
            return f"[Contenido de {path.name}]\n{text}"
        except Exception as e:
            return f"Error leyendo archivo: {e}"
