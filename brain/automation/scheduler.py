"""Scheduler automático: genera y publica contenido según los nichos configurados."""

import logging
import json
from datetime import datetime
from pathlib import Path

from config import DATA_DIR

logger = logging.getLogger(__name__)

SCHEDULE_LOG = DATA_DIR / "schedule_log.json"


def _load_log() -> list:
    if SCHEDULE_LOG.exists():
        try:
            return json.loads(SCHEDULE_LOG.read_text(encoding="utf-8"))
        except Exception:
            return []
    return []


def _save_log(log: list) -> None:
    SCHEDULE_LOG.parent.mkdir(parents=True, exist_ok=True)
    # Keep last 500 entries
    SCHEDULE_LOG.write_text(json.dumps(log[-500:], indent=2, ensure_ascii=False), encoding="utf-8")


def generate_and_publish(niche_id: str, topic: str = "") -> dict:
    from automation.niche_manager import get_niche, increment_video_count
    from automation.templates import build_generation_prompt, get_niche_config
    from inference_client import chat

    niche = get_niche(niche_id)
    if not niche:
        return {"error": f"Nicho '{niche_id}' no encontrado"}

    niche_name = niche.get("description", niche_id)
    niche_cfg = get_niche_config(niche_id) or {}

    gen_prompt = build_generation_prompt(niche_id, topic=topic)

    messages = [
        {"role": "system", "content": "Sos un guionista de videos virales. Generá guiones listos para producir. Respondé en español."},
        {"role": "user", "content": gen_prompt},
    ]
    script = chat(messages)

    result = {
        "niche_id": niche_id,
        "niche_name": niche_name,
        "topic": topic,
        "script": script,
        "platforms": niche.get("platforms", []),
        "hashtags": niche.get("hashtags", []) + niche_cfg.get("hashtags", []),
        "generated_at": datetime.now().isoformat(),
        "status": "script_generated",
        "next_steps": (
            "Para producir el video completo, usá la herramienta generate_video "
            "con este guión, y luego publish_video para publicarlo."
        ),
    }

    increment_video_count(niche_id)

    log = _load_log()
    log.append({
        "niche_id": niche_id,
        "topic": topic,
        "timestamp": result["generated_at"],
        "status": "generated",
    })
    _save_log(log)

    return result


def run_batch(max_videos: int = 5) -> list[dict]:
    from automation.niche_manager import get_pending_niches

    pending = get_pending_niches()
    results = []

    for niche_info in pending[:max_videos]:
        niche_id = niche_info["id"]
        try:
            result = generate_and_publish(niche_id)
            results.append(result)
        except Exception as e:
            logger.error("Error generando para nicho '%s': %s", niche_id, e)
            results.append({"niche_id": niche_id, "error": str(e)})

    return results


def get_schedule_stats() -> dict:
    log = _load_log()
    today = datetime.now().strftime("%Y-%m-%d")

    total = len(log)
    today_count = sum(1 for e in log if e.get("timestamp", "").startswith(today))

    niche_counts = {}
    for entry in log:
        nid = entry.get("niche_id", "unknown")
        niche_counts[nid] = niche_counts.get(nid, 0) + 1

    return {
        "total_generated": total,
        "generated_today": today_count,
        "by_niche": niche_counts,
    }
