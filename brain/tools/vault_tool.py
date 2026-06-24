"""Herramientas de acceso directo al vault de Obsidian (leer, escribir, listar notas)."""

import logging
from datetime import datetime
from pathlib import Path

from config import VAULT_PATH
from tools.base import BaseTool

logger = logging.getLogger(__name__)

_vault = Path(VAULT_PATH)


def _safe_path(note_path: str) -> Path | None:
    """Resuelve un path relativo dentro del vault, evitando path traversal."""
    if not note_path.endswith(".md"):
        note_path += ".md"
    resolved = (_vault / note_path).resolve()
    if not str(resolved).startswith(str(_vault.resolve())):
        return None
    return resolved


class VaultReadTool(BaseTool):
    name = "vault_read"
    description = (
        "Lee una nota específica del vault de Obsidian. "
        "Pasá el nombre o path relativo de la nota (ej: 'proyectos/mi-idea' o 'Daily/2025-01-15')."
    )
    parameters = {
        "type": "object",
        "properties": {
            "note_path": {
                "type": "string",
                "description": "Path relativo de la nota dentro del vault (sin .md o con .md)",
            },
        },
        "required": ["note_path"],
    }

    def execute(self, note_path: str) -> str:
        path = _safe_path(note_path)
        if path is None:
            return "Error: path inválido (fuera del vault)."
        if not path.exists():
            return f"Nota no encontrada: {note_path}"
        try:
            content = path.read_text(encoding="utf-8", errors="ignore")
            return f"**{path.stem}**\n\n{content}"
        except Exception as e:
            return f"Error leyendo nota: {e}"


class VaultWriteTool(BaseTool):
    name = "vault_write"
    description = (
        "Crea o actualiza una nota en el vault de Obsidian. "
        "Podés crear notas nuevas o agregar contenido a notas existentes."
    )
    parameters = {
        "type": "object",
        "properties": {
            "note_path": {
                "type": "string",
                "description": "Path relativo de la nota (ej: 'proyectos/nueva-idea')",
            },
            "content": {
                "type": "string",
                "description": "Contenido en Markdown para escribir en la nota",
            },
            "mode": {
                "type": "string",
                "description": "'create' para crear/sobreescribir, 'append' para agregar al final",
                "enum": ["create", "append"],
            },
        },
        "required": ["note_path", "content"],
    }

    def execute(self, note_path: str, content: str, mode: str = "create") -> str:
        path = _safe_path(note_path)
        if path is None:
            return "Error: path inválido (fuera del vault)."

        try:
            path.parent.mkdir(parents=True, exist_ok=True)

            if mode == "append" and path.exists():
                existing = path.read_text(encoding="utf-8", errors="ignore")
                timestamp = datetime.now().strftime("%Y-%m-%d %H:%M")
                content = f"{existing}\n\n---\n*Agregado por Hermes ({timestamp})*\n\n{content}"

            path.write_text(content, encoding="utf-8")
            action = "actualizada" if mode == "append" else "creada"
            logger.info("Nota %s: %s", action, note_path)
            return f"Nota {action}: {note_path}"
        except Exception as e:
            return f"Error escribiendo nota: {e}"


class VaultListTool(BaseTool):
    name = "vault_list"
    description = (
        "Lista las notas y carpetas del vault de Obsidian. "
        "Podés especificar una carpeta para ver su contenido, o dejar vacío para la raíz."
    )
    parameters = {
        "type": "object",
        "properties": {
            "folder": {
                "type": "string",
                "description": "Carpeta relativa dentro del vault (vacío = raíz)",
            },
            "recursive": {
                "type": "boolean",
                "description": "Si buscar recursivamente en subcarpetas (default: false)",
            },
        },
        "required": [],
    }

    def execute(self, folder: str = "", recursive: bool = False) -> str:
        target = _vault / folder if folder else _vault
        resolved = target.resolve()
        if not str(resolved).startswith(str(_vault.resolve())):
            return "Error: path inválido (fuera del vault)."
        if not resolved.is_dir():
            return f"Carpeta no encontrada: {folder}"

        try:
            glob_fn = resolved.rglob if recursive else resolved.glob
            items = sorted(glob_fn("*"))

            folders = []
            notes = []
            for item in items:
                rel = item.relative_to(_vault)
                if item.is_dir() and not item.name.startswith("."):
                    folders.append(f"📁 {rel}/")
                elif item.suffix == ".md":
                    notes.append(f"📄 {rel}")

            if not folders and not notes:
                return f"Carpeta vacía: {folder or 'raíz'}"

            result = f"**Vault: {folder or '/'}**\n\n"
            if folders:
                result += "**Carpetas:**\n" + "\n".join(folders[:50]) + "\n\n"
            if notes:
                result += "**Notas:**\n" + "\n".join(notes[:100])
            if len(notes) > 100:
                result += f"\n... y {len(notes) - 100} notas más"

            return result
        except Exception as e:
            return f"Error listando vault: {e}"
