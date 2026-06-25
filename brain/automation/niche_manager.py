"""Gestión de nichos y canales para contenido automatizado."""

import json
import logging
from pathlib import Path
from datetime import datetime

from config import DATA_DIR

logger = logging.getLogger(__name__)

NICHES_FILE = DATA_DIR / "niches.json"


def _load_niches() -> dict:
    if NICHES_FILE.exists():
        return json.loads(NICHES_FILE.read_text(encoding="utf-8"))
    return {}


def _save_niches(niches: dict) -> None:
    NICHES_FILE.parent.mkdir(parents=True, exist_ok=True)
    NICHES_FILE.write_text(json.dumps(niches, indent=2, ensure_ascii=False), encoding="utf-8")


def add_niche(
    niche_id: str,
    name: str,
    description: str,
    platforms: list[str],
    language: str = "es",
    tts_voice: str = "",
    posting_frequency: int = 1,
    hashtags: list[str] | None = None,
    style: str = "educativo",
) -> dict:
    niches = _load_niches()
    niches[niche_id] = {
        "name": name,
        "description": description,
        "platforms": platforms,
        "language": language,
        "tts_voice": tts_voice,
        "posting_frequency": posting_frequency,
        "hashtags": hashtags or [],
        "style": style,
        "created": datetime.now().isoformat(),
        "videos_generated": 0,
        "active": True,
    }
    _save_niches(niches)
    return niches[niche_id]


def remove_niche(niche_id: str) -> bool:
    niches = _load_niches()
    if niche_id in niches:
        niches[niche_id]["active"] = False
        _save_niches(niches)
        return True
    return False


def get_niche(niche_id: str) -> dict | None:
    return _load_niches().get(niche_id)


def list_niches(active_only: bool = True) -> dict:
    niches = _load_niches()
    if active_only:
        return {k: v for k, v in niches.items() if v.get("active", True)}
    return niches


def increment_video_count(niche_id: str) -> None:
    niches = _load_niches()
    if niche_id in niches:
        niches[niche_id]["videos_generated"] = niches[niche_id].get("videos_generated", 0) + 1
        _save_niches(niches)


def get_pending_niches() -> list[dict]:
    """Retorna nichos que necesitan contenido nuevo hoy."""
    niches = list_niches(active_only=True)
    pending = []
    for niche_id, niche in niches.items():
        pending.append({"id": niche_id, **niche})
    return pending
