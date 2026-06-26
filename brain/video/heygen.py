"""HeyGen avatar video generation client."""

import json
import logging
import os
import time
from dataclasses import dataclass
from pathlib import Path

import httpx

logger = logging.getLogger(__name__)

HEYGEN_API_KEY = os.getenv("HEYGEN_API_KEY", "")
HEYGEN_BASE_URL = "https://api.heygen.com/v2"
HEYGEN_AVATAR_ID = os.getenv("HEYGEN_AVATAR_ID", "")
HEYGEN_VOICE_ID = os.getenv("HEYGEN_VOICE_ID", "")


@dataclass
class AvatarResult:
    success: bool
    video_path: str = ""
    video_url: str = ""
    duration: float = 0.0
    error: str = ""


def _headers() -> dict:
    return {
        "x-api-key": HEYGEN_API_KEY,
        "Content-Type": "application/json",
    }


def list_avatars() -> list[dict]:
    if not HEYGEN_API_KEY:
        return []
    try:
        resp = httpx.get(
            f"{HEYGEN_BASE_URL}/avatars",
            headers=_headers(),
            timeout=30.0,
        )
        resp.raise_for_status()
        data = resp.json()
        return data.get("data", {}).get("avatars", [])
    except Exception as e:
        logger.error("Error listando avatars: %s", e)
        return []


def list_voices() -> list[dict]:
    if not HEYGEN_API_KEY:
        return []
    try:
        resp = httpx.get(
            f"{HEYGEN_BASE_URL}/voices",
            headers=_headers(),
            timeout=30.0,
        )
        resp.raise_for_status()
        data = resp.json()
        return data.get("data", {}).get("voices", [])
    except Exception as e:
        logger.error("Error listando voces: %s", e)
        return []


def generate_avatar_video(
    script: str,
    avatar_id: str = "",
    voice_id: str = "",
    aspect_ratio: str = "9:16",
    output_path: str = "",
    max_wait: int = 600,
) -> AvatarResult:
    """Genera un video con avatar HeyGen."""
    if not HEYGEN_API_KEY:
        return AvatarResult(
            success=False,
            error="HEYGEN_API_KEY no configurada. Obtenela en https://www.heygen.com/",
        )

    avatar_id = avatar_id or HEYGEN_AVATAR_ID
    voice_id = voice_id or HEYGEN_VOICE_ID

    if not avatar_id:
        return AvatarResult(success=False, error="No se especificó avatar_id")

    dimension = {"9:16": {"width": 1080, "height": 1920},
                 "16:9": {"width": 1920, "height": 1080},
                 "1:1": {"width": 1080, "height": 1080}}
    dim = dimension.get(aspect_ratio, dimension["9:16"])

    payload = {
        "video_inputs": [{
            "character": {
                "type": "avatar",
                "avatar_id": avatar_id,
                "avatar_style": "normal",
            },
            "voice": {
                "type": "text",
                "input_text": script,
                "voice_id": voice_id,
            },
        }],
        "dimension": dim,
    }

    try:
        resp = httpx.post(
            f"{HEYGEN_BASE_URL}/video/generate",
            headers=_headers(),
            json=payload,
            timeout=90.0,
        )
        resp.raise_for_status()
        data = resp.json()

        video_id = data.get("data", {}).get("video_id")
        if not video_id:
            return AvatarResult(success=False, error=f"No se obtuvo video_id: {data}")

        logger.info("HeyGen video creado: %s, esperando renderizado...", video_id)

        waited = 0
        poll_interval = 10
        while waited < max_wait:
            time.sleep(poll_interval)
            waited += poll_interval

            status_resp = httpx.get(
                f"{HEYGEN_BASE_URL}/video_status.get",
                params={"video_id": video_id},
                headers=_headers(),
                timeout=30.0,
            )
            status_data = status_resp.json()
            status = status_data.get("data", {}).get("status", "")

            if status == "completed":
                video_url = status_data["data"].get("video_url", "")
                duration = status_data["data"].get("duration", 0.0)

                if output_path:
                    dl_path = output_path
                else:
                    from config import MEDIA_DOWNLOAD_DIR
                    dl_dir = Path(MEDIA_DOWNLOAD_DIR) / "heygen"
                    dl_dir.mkdir(parents=True, exist_ok=True)
                    dl_path = str(dl_dir / f"avatar_{video_id}.mp4")

                dl_resp = httpx.get(video_url, timeout=120.0, follow_redirects=True)
                dl_resp.raise_for_status()
                with open(dl_path, "wb") as f:
                    f.write(dl_resp.content)

                return AvatarResult(
                    success=True,
                    video_path=dl_path,
                    video_url=video_url,
                    duration=duration,
                )

            if status == "failed":
                error = status_data["data"].get("error", "Renderizado falló")
                return AvatarResult(success=False, error=error)

            logger.info("HeyGen status: %s (%ds)", status, waited)

        return AvatarResult(success=False, error=f"Timeout después de {max_wait}s")

    except Exception as e:
        logger.error("HeyGen falló: %s", e)
        return AvatarResult(success=False, error=str(e))
