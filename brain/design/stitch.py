"""Cliente Python para Google Stitch — generación de UI/HTML con IA."""

import base64
import logging
import os
from dataclasses import dataclass, field
from pathlib import Path

import httpx

logger = logging.getLogger(__name__)

STITCH_API_KEY = os.getenv("STITCH_API_KEY", "")
STITCH_BASE_URL = "https://stitch.googleapis.com"
STITCH_TIMEOUT = 60


@dataclass
class StitchScreen:
    html: str = ""
    css: str = ""
    image_url: str = ""
    screen_name: str = ""


@dataclass
class StitchResult:
    success: bool
    screens: list[StitchScreen] = field(default_factory=list)
    project_url: str = ""
    error: str = ""


def _get_headers() -> dict:
    if not STITCH_API_KEY:
        raise ValueError(
            "STITCH_API_KEY no configurada. "
            "Obtenela en stitch.withgoogle.com → Settings → API Key"
        )
    return {
        "X-Goog-Api-Key": STITCH_API_KEY,
        "Content-Type": "application/json",
    }


def generate_ui(
    prompt: str,
    num_screens: int = 1,
    style: str = "",
    reference_image_path: str = "",
) -> StitchResult:
    """Genera UI/HTML desde un prompt de texto.

    Args:
        prompt: Descripción de lo que querés generar.
        num_screens: Cantidad de pantallas (1-5).
        style: Estilo visual (ej: "modern minimalist", "dark theme", "glassmorphism").
        reference_image_path: Imagen de referencia opcional (screenshot, wireframe).
    """
    try:
        headers = _get_headers()
    except ValueError as e:
        return StitchResult(success=False, error=str(e))

    payload = {
        "prompt": prompt,
        "numScreens": min(max(num_screens, 1), 5),
        "outputFormat": "html",
    }

    if style:
        payload["prompt"] = f"{prompt}. Style: {style}"

    if reference_image_path and Path(reference_image_path).exists():
        with open(reference_image_path, "rb") as f:
            img_b64 = base64.b64encode(f.read()).decode("utf-8")
        ext = Path(reference_image_path).suffix.lstrip(".").lower()
        mime = {"png": "image/png", "jpg": "image/jpeg", "jpeg": "image/jpeg",
                "webp": "image/webp"}.get(ext, "image/png")
        payload["referenceImage"] = {
            "type": "base64",
            "mediaType": mime,
            "data": img_b64,
        }

    try:
        with httpx.Client(timeout=STITCH_TIMEOUT) as client:
            resp = client.post(
                f"{STITCH_BASE_URL}/mcp/v1/generate",
                headers=headers,
                json=payload,
            )
            resp.raise_for_status()
            data = resp.json()

        screens = []
        for screen_data in data.get("screens", [data]):
            screens.append(StitchScreen(
                html=screen_data.get("html", ""),
                css=screen_data.get("css", ""),
                image_url=screen_data.get("imageUrl", ""),
                screen_name=screen_data.get("name", ""),
            ))

        return StitchResult(
            success=True,
            screens=screens,
            project_url=data.get("projectUrl", ""),
        )
    except httpx.HTTPStatusError as e:
        logger.error("Stitch API error %d: %s", e.response.status_code, e.response.text)
        return StitchResult(success=False, error=f"HTTP {e.response.status_code}: {e.response.text[:200]}")
    except Exception as e:
        logger.error("Stitch falló: %s", e)
        return StitchResult(success=False, error=str(e))


def iterate_design(
    project_url: str,
    feedback: str,
    screen_index: int = 0,
) -> StitchResult:
    """Itera sobre un diseño existente con feedback."""
    try:
        headers = _get_headers()
    except ValueError as e:
        return StitchResult(success=False, error=str(e))

    try:
        with httpx.Client(timeout=STITCH_TIMEOUT) as client:
            resp = client.post(
                f"{STITCH_BASE_URL}/mcp/v1/iterate",
                headers=headers,
                json={
                    "projectUrl": project_url,
                    "feedback": feedback,
                    "screenIndex": screen_index,
                },
            )
            resp.raise_for_status()
            data = resp.json()

        screens = []
        for screen_data in data.get("screens", [data]):
            screens.append(StitchScreen(
                html=screen_data.get("html", ""),
                css=screen_data.get("css", ""),
                image_url=screen_data.get("imageUrl", ""),
                screen_name=screen_data.get("name", ""),
            ))

        return StitchResult(
            success=True,
            screens=screens,
            project_url=data.get("projectUrl", project_url),
        )
    except Exception as e:
        logger.error("Stitch iterate falló: %s", e)
        return StitchResult(success=False, error=str(e))
