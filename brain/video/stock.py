"""Búsqueda y descarga de stock footage gratuito (Pexels)."""

import logging
import os
from dataclasses import dataclass
from pathlib import Path

import httpx

logger = logging.getLogger(__name__)

PEXELS_API_KEY = os.getenv("PEXELS_API_KEY", "")
PEXELS_BASE = "https://api.pexels.com"
PIXABAY_API_KEY = os.getenv("PIXABAY_API_KEY", "")
PIXABAY_BASE = "https://pixabay.com/api"


@dataclass
class StockClip:
    url: str
    width: int
    height: int
    duration: float
    source: str
    local_path: str = ""


def search_pexels_videos(query: str, per_page: int = 5, orientation: str = "portrait") -> list[StockClip]:
    """Busca videos en Pexels (requiere API key gratuita)."""
    if not PEXELS_API_KEY:
        logger.warning("PEXELS_API_KEY no configurada")
        return []

    try:
        resp = httpx.get(
            f"{PEXELS_BASE}/videos/search",
            params={"query": query, "per_page": per_page, "orientation": orientation},
            headers={"Authorization": PEXELS_API_KEY},
            timeout=15.0,
        )
        resp.raise_for_status()
        data = resp.json()

        clips = []
        for video in data.get("videos", []):
            files = video.get("video_files", [])
            # Preferir 1080p — evitar 4K que es muy lento de procesar
            best = None
            for f in files:
                h = f.get("height", 0)
                if 720 <= h <= 1080:
                    if best is None or h > best.get("height", 0):
                        best = f
            if not best:
                # Fallback: cualquier archivo <= 1080p
                candidates = [f for f in files if f.get("height", 0) <= 1080]
                best = candidates[0] if candidates else (files[0] if files else None)

            if best:
                clips.append(StockClip(
                    url=best["link"],
                    width=best.get("width", 0),
                    height=best.get("height", 0),
                    duration=video.get("duration", 0),
                    source="pexels",
                ))
        return clips
    except Exception as e:
        logger.error("Pexels search falló: %s", e)
        return []


def search_pixabay_videos(query: str, per_page: int = 5) -> list[StockClip]:
    """Busca videos en Pixabay (requiere API key gratuita)."""
    if not PIXABAY_API_KEY:
        logger.warning("PIXABAY_API_KEY no configurada")
        return []

    try:
        resp = httpx.get(
            f"{PIXABAY_BASE}/videos/",
            params={"key": PIXABAY_API_KEY, "q": query, "per_page": per_page},
            timeout=15.0,
        )
        resp.raise_for_status()
        data = resp.json()

        clips = []
        for hit in data.get("hits", []):
            videos = hit.get("videos", {})
            medium = videos.get("medium", {}) or videos.get("small", {})
            if medium:
                clips.append(StockClip(
                    url=medium.get("url", ""),
                    width=medium.get("width", 0),
                    height=medium.get("height", 0),
                    duration=hit.get("duration", 0),
                    source="pixabay",
                ))
        return clips
    except Exception as e:
        logger.error("Pixabay search falló: %s", e)
        return []


def download_clip(clip: StockClip, output_dir: str) -> str:
    """Descarga un clip de stock y retorna la ruta local."""
    output_dir_path = Path(output_dir)
    output_dir_path.mkdir(parents=True, exist_ok=True)

    filename = f"{clip.source}_{hash(clip.url) % 100000}.mp4"
    local_path = str(output_dir_path / filename)

    try:
        with httpx.Client(timeout=60.0, follow_redirects=True) as client:
            resp = client.get(clip.url)
            resp.raise_for_status()
            with open(local_path, "wb") as f:
                f.write(resp.content)
        clip.local_path = local_path
        return local_path
    except Exception as e:
        logger.error("Error descargando clip: %s", e)
        return ""
