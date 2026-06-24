"""Herramienta de memoria persistente para recordar preferencias del usuario."""

import json
import logging
from pathlib import Path

from tools.base import BaseTool
from config import DATA_DIR

logger = logging.getLogger(__name__)

_PREFS_FILE = DATA_DIR / "user_preferences.json"


def _load_prefs() -> dict:
    if _PREFS_FILE.exists():
        try:
            return json.loads(_PREFS_FILE.read_text(encoding="utf-8"))
        except Exception:
            return {}
    return {}


def _save_prefs(prefs: dict):
    _PREFS_FILE.parent.mkdir(parents=True, exist_ok=True)
    _PREFS_FILE.write_text(json.dumps(prefs, ensure_ascii=False, indent=2), encoding="utf-8")


class RememberTool(BaseTool):
    name = "remember"
    description = (
        "Guarda una preferencia o dato del usuario para recordar a largo plazo. "
        "Úsala cuando el usuario te diga algo que quiere que recuerdes entre sesiones."
    )
    parameters = {
        "type": "object",
        "properties": {
            "key": {
                "type": "string",
                "description": "Nombre/categoría de lo que hay que recordar (ej: 'idioma_preferido')",
            },
            "value": {
                "type": "string",
                "description": "El valor a recordar",
            },
        },
        "required": ["key", "value"],
    }

    def execute(self, key: str, value: str) -> str:
        prefs = _load_prefs()
        prefs[key] = value
        _save_prefs(prefs)
        return f"Guardado: {key} = {value}"


class RecallTool(BaseTool):
    name = "recall"
    description = (
        "Recupera una preferencia o dato guardado del usuario. "
        "Úsala para consultar información previamente almacenada."
    )
    parameters = {
        "type": "object",
        "properties": {
            "key": {
                "type": "string",
                "description": "Nombre de lo que hay que buscar. Usa '*' para ver todo.",
            },
        },
        "required": ["key"],
    }

    def execute(self, key: str) -> str:
        prefs = _load_prefs()
        if key == "*":
            if not prefs:
                return "No hay preferencias guardadas."
            lines = [f"- {k}: {v}" for k, v in prefs.items()]
            return "Preferencias guardadas:\n" + "\n".join(lines)
        value = prefs.get(key)
        if value is None:
            return f"No se encontró '{key}' en las preferencias."
        return f"{key} = {value}"
