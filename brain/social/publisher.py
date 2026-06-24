"""Orquestador de publicación multi-plataforma."""

import logging
from pathlib import Path

from social.youtube import upload_video as youtube_upload
from social.make_webhook import trigger_scenario, trigger_text_post

logger = logging.getLogger(__name__)

PLATFORM_SPECS = {
    "youtube": {"max_title": 100, "max_desc": 5000, "max_tags": 500, "formats": ["mp4", "mov", "avi"]},
    "instagram": {"max_caption": 2200, "aspect_ratios": ["9:16", "1:1", "4:5"], "max_duration": 90},
    "tiktok": {"max_caption": 2200, "aspect_ratios": ["9:16"], "max_duration": 180},
    "x": {"max_text": 280, "max_duration": 140},
    "facebook": {"max_caption": 63206, "formats": ["mp4", "mov"]},
}


def publish_video(
    video_path: str,
    title: str,
    description: str = "",
    hashtags: list[str] | None = None,
    platforms: list[str] | None = None,
    privacy: str = "private",
    schedule_time: str = "",
) -> dict:
    if platforms is None:
        platforms = ["youtube", "instagram", "tiktok"]

    path = Path(video_path)
    if not path.exists():
        return {"error": f"Video no encontrado: {video_path}"}

    results = {}
    tags_str = " ".join(f"#{t}" for t in (hashtags or []))
    caption = f"{title}\n\n{description}\n\n{tags_str}".strip()

    youtube_platforms = [p for p in platforms if p == "youtube"]
    make_platforms = [p for p in platforms if p != "youtube"]

    for _ in youtube_platforms:
        results["youtube"] = youtube_upload(
            video_path=video_path,
            title=title,
            description=f"{description}\n\n{tags_str}",
            tags=hashtags,
            privacy=privacy,
        )

    if make_platforms:
        make_result = trigger_scenario(
            video_path=video_path,
            title=title,
            description=caption,
            hashtags=hashtags,
            platforms=make_platforms,
            schedule_time=schedule_time,
        )
        for p in make_platforms:
            results[p] = make_result

    return {
        "video": video_path,
        "platforms": results,
        "summary": _build_summary(results),
    }


def publish_text(
    text: str,
    platforms: list[str] | None = None,
    image_path: str = "",
    schedule_time: str = "",
) -> dict:
    if platforms is None:
        platforms = ["instagram", "x", "facebook"]

    result = trigger_text_post(
        text=text,
        platforms=platforms,
        image_path=image_path,
        schedule_time=schedule_time,
    )
    return {
        "text": text[:100] + "..." if len(text) > 100 else text,
        "platforms": platforms,
        "result": result,
    }


def get_platform_specs(platform: str) -> dict:
    return PLATFORM_SPECS.get(platform, {})


def optimize_for_platform(title: str, description: str, hashtags: list[str], platform: str) -> dict:
    specs = PLATFORM_SPECS.get(platform, {})
    tags_str = " ".join(f"#{t}" for t in hashtags)

    if platform == "youtube":
        return {
            "title": title[:specs.get("max_title", 100)],
            "description": f"{description}\n\n{tags_str}"[:specs.get("max_desc", 5000)],
            "tags": hashtags,
        }
    elif platform == "x":
        max_len = specs.get("max_text", 280)
        text = f"{title} {tags_str}"
        return {"text": text[:max_len]}
    else:
        max_cap = specs.get("max_caption", 2200)
        caption = f"{title}\n\n{description}\n\n{tags_str}"
        return {"caption": caption[:max_cap]}


def _build_summary(results: dict) -> str:
    lines = []
    for platform, result in results.items():
        if isinstance(result, dict) and result.get("error"):
            lines.append(f"❌ {platform}: {result['error']}")
        elif isinstance(result, dict) and result.get("success"):
            url = result.get("url", "")
            extra = f" → {url}" if url else ""
            lines.append(f"✅ {platform}: publicado{extra}")
        else:
            lines.append(f"⏳ {platform}: enviado a Make.com")
    return "\n".join(lines)
