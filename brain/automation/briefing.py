"""Resumen diario automático para enviar por Telegram."""

import logging
from datetime import datetime

logger = logging.getLogger(__name__)


def generate_daily_briefing() -> str:
    from inference_client import chat

    sections = []

    # Schedule stats
    try:
        from automation.scheduler import get_schedule_stats
        stats = get_schedule_stats()
        sections.append(
            f"**Contenido generado:** {stats['generated_today']} hoy, "
            f"{stats['total_generated']} total"
        )
    except Exception:
        pass

    # Analytics
    try:
        from automation.analytics import get_performance_report
        report = get_performance_report()
        if "No hay datos" not in report:
            sections.append(report)
    except Exception:
        pass

    # Nichos activos
    try:
        from automation.niche_manager import list_niches
        niches = list_niches()
        if niches:
            niche_list = ", ".join(n.get("name", k) for k, n in niches.items())
            sections.append(f"**Nichos activos:** {niche_list}")
    except Exception:
        pass

    # Tendencias
    try:
        from automation.trends import detect_trends
        trends = detect_trends(max_results=3)
        if trends:
            trend_lines = [f"- {t['title']}" for t in trends[:3]]
            sections.append("**Tendencias del momento:**\n" + "\n".join(trend_lines))
    except Exception:
        pass

    date_str = datetime.now().strftime("%A %d de %B, %Y")
    header = f"**Buenos días. Resumen del {date_str}:**\n"

    if sections:
        return header + "\n\n".join(sections)

    return header + "Todo tranquilo por ahora. ¿Querés que genere contenido nuevo?"
