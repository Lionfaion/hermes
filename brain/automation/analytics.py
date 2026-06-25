"""Analytics: tracking de rendimiento de videos publicados."""

import json
import logging
from datetime import datetime
from pathlib import Path

from config import DATA_DIR

logger = logging.getLogger(__name__)

ANALYTICS_FILE = DATA_DIR / "video_analytics.json"


def _load_analytics() -> list:
    if ANALYTICS_FILE.exists():
        try:
            return json.loads(ANALYTICS_FILE.read_text(encoding="utf-8"))
        except Exception:
            return []
    return []


def _save_analytics(data: list) -> None:
    ANALYTICS_FILE.parent.mkdir(parents=True, exist_ok=True)
    ANALYTICS_FILE.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")


def track_video(
    title: str,
    platform: str,
    url: str = "",
    niche: str = "",
    video_id: str = "",
) -> dict:
    analytics = _load_analytics()
    entry = {
        "title": title,
        "platform": platform,
        "url": url,
        "niche": niche,
        "video_id": video_id,
        "published_at": datetime.now().isoformat(),
        "metrics": {},
    }
    analytics.append(entry)
    _save_analytics(analytics)
    return entry


def update_metrics(
    video_id: str,
    platform: str,
    views: int = 0,
    likes: int = 0,
    comments: int = 0,
    shares: int = 0,
) -> dict | None:
    analytics = _load_analytics()
    for entry in analytics:
        if entry.get("video_id") == video_id and entry.get("platform") == platform:
            entry["metrics"] = {
                "views": views,
                "likes": likes,
                "comments": comments,
                "shares": shares,
                "updated_at": datetime.now().isoformat(),
                "engagement_rate": round((likes + comments + shares) / max(views, 1) * 100, 2),
            }
            _save_analytics(analytics)
            return entry
    return None


def fetch_youtube_stats(video_id: str) -> dict:
    from config import YOUTUBE_CLIENT_ID

    if not YOUTUBE_CLIENT_ID:
        return {"error": "YouTube API no configurada"}

    try:
        import httpx
        from social.youtube import _get_access_token

        token = _get_access_token()
        if not token:
            return {"error": "No se pudo obtener token de YouTube"}

        resp = httpx.get(
            "https://www.googleapis.com/youtube/v3/videos",
            params={
                "part": "statistics,snippet",
                "id": video_id,
            },
            headers={"Authorization": f"Bearer {token}"},
            timeout=30,
        )
        resp.raise_for_status()
        data = resp.json()

        if not data.get("items"):
            return {"error": "Video no encontrado"}

        stats = data["items"][0]["statistics"]
        return {
            "views": int(stats.get("viewCount", 0)),
            "likes": int(stats.get("likeCount", 0)),
            "comments": int(stats.get("commentCount", 0)),
        }
    except Exception as e:
        return {"error": str(e)}


def get_performance_report(niche: str = "") -> str:
    analytics = _load_analytics()

    if niche:
        analytics = [a for a in analytics if a.get("niche") == niche]

    if not analytics:
        return "No hay datos de analytics todavía."

    total = len(analytics)
    by_platform = {}
    total_views = 0
    total_engagement = 0

    for entry in analytics:
        p = entry.get("platform", "unknown")
        by_platform[p] = by_platform.get(p, 0) + 1
        metrics = entry.get("metrics", {})
        total_views += metrics.get("views", 0)
        total_engagement += metrics.get("engagement_rate", 0)

    avg_engagement = round(total_engagement / max(total, 1), 2)

    report = f"**Reporte de Performance{' - ' + niche if niche else ''}**\n\n"
    report += f"- Videos publicados: {total}\n"
    report += f"- Views totales: {total_views:,}\n"
    report += f"- Engagement promedio: {avg_engagement}%\n\n"
    report += "**Por plataforma:**\n"
    for p, count in sorted(by_platform.items()):
        report += f"- {p}: {count} videos\n"

    best = sorted(analytics, key=lambda x: x.get("metrics", {}).get("views", 0), reverse=True)[:3]
    if best and best[0].get("metrics", {}).get("views", 0) > 0:
        report += "\n**Top 3 videos:**\n"
        for v in best:
            m = v.get("metrics", {})
            report += f"- {v['title']} ({v['platform']}): {m.get('views', 0):,} views\n"

    return report
