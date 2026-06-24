"""Integración con Make.com via webhooks para publicación multi-plataforma."""

import base64
import logging
import json
from pathlib import Path

import httpx

from config import MAKE_WEBHOOK_URL

logger = logging.getLogger(__name__)


def trigger_scenario(
    video_path: str,
    title: str,
    description: str = "",
    hashtags: list[str] | None = None,
    platforms: list[str] | None = None,
    schedule_time: str = "",
) -> dict:
    if not MAKE_WEBHOOK_URL:
        return {"error": "Make.com no configurado. Configurá MAKE_WEBHOOK_URL en .env"}

    path = Path(video_path)
    if not path.exists():
        return {"error": f"Video no encontrado: {video_path}"}

    file_size_mb = path.stat().st_size / (1024 * 1024)
    if file_size_mb > 25:
        return _trigger_with_path(video_path, title, description, hashtags, platforms, schedule_time)

    video_b64 = base64.b64encode(path.read_bytes()).decode("utf-8")

    payload = {
        "action": "publish_video",
        "title": title,
        "description": description,
        "hashtags": hashtags or [],
        "platforms": platforms or ["instagram", "tiktok", "facebook", "x"],
        "schedule_time": schedule_time,
        "video_filename": path.name,
        "video_base64": video_b64,
    }

    return _send_webhook(payload)


def _trigger_with_path(
    video_path: str,
    title: str,
    description: str,
    hashtags: list[str] | None,
    platforms: list[str] | None,
    schedule_time: str,
) -> dict:
    payload = {
        "action": "publish_video",
        "title": title,
        "description": description,
        "hashtags": hashtags or [],
        "platforms": platforms or ["instagram", "tiktok", "facebook", "x"],
        "schedule_time": schedule_time,
        "video_path": video_path,
    }
    return _send_webhook(payload)


def trigger_text_post(
    text: str,
    platforms: list[str] | None = None,
    image_path: str = "",
    schedule_time: str = "",
) -> dict:
    if not MAKE_WEBHOOK_URL:
        return {"error": "Make.com no configurado. Configurá MAKE_WEBHOOK_URL en .env"}

    payload = {
        "action": "publish_text",
        "text": text,
        "platforms": platforms or ["instagram", "tiktok", "facebook", "x"],
        "schedule_time": schedule_time,
    }

    if image_path:
        path = Path(image_path)
        if path.exists() and path.stat().st_size < 10 * 1024 * 1024:
            payload["image_base64"] = base64.b64encode(path.read_bytes()).decode("utf-8")
            payload["image_filename"] = path.name

    return _send_webhook(payload)


def _send_webhook(payload: dict) -> dict:
    try:
        resp = httpx.post(
            MAKE_WEBHOOK_URL,
            json=payload,
            timeout=60,
        )
        resp.raise_for_status()

        try:
            result = resp.json()
        except Exception:
            result = {"response": resp.text}

        logger.info("Make.com webhook triggered: %s", payload.get("action"))
        return {"success": True, "make_response": result}
    except httpx.TimeoutException:
        return {"success": True, "note": "Webhook enviado (timeout esperando respuesta, Make lo procesa async)"}
    except Exception as e:
        logger.error("Error en Make.com webhook: %s", e)
        return {"error": str(e)}
