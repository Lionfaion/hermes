"""Market Monitor: alertas de trading, crypto y sentimiento de mercado."""

import json
import logging
from datetime import datetime
from pathlib import Path

from config import DATA_DIR

logger = logging.getLogger(__name__)

ALERTS_FILE = DATA_DIR / "market_alerts.json"
WATCHLIST_FILE = DATA_DIR / "market_watchlist.json"


def _load_watchlist() -> list:
    if WATCHLIST_FILE.exists():
        try:
            return json.loads(WATCHLIST_FILE.read_text(encoding="utf-8"))
        except Exception:
            return []
    return []


def _save_watchlist(wl: list) -> None:
    WATCHLIST_FILE.parent.mkdir(parents=True, exist_ok=True)
    WATCHLIST_FILE.write_text(json.dumps(wl, indent=2, ensure_ascii=False), encoding="utf-8")


def add_to_watchlist(asset: str, asset_type: str = "crypto") -> dict:
    wl = _load_watchlist()
    entry = {
        "asset": asset,
        "type": asset_type,
        "added_at": datetime.now().isoformat(),
        "active": True,
    }
    wl.append(entry)
    _save_watchlist(wl)
    return entry


def remove_from_watchlist(asset: str) -> bool:
    wl = _load_watchlist()
    wl = [w for w in wl if w["asset"].lower() != asset.lower()]
    _save_watchlist(wl)
    return True


def get_watchlist() -> list:
    return [w for w in _load_watchlist() if w.get("active", True)]


def check_market(asset: str) -> str:
    from web.search import web_search
    from inference_client import chat

    results = web_search(f"{asset} precio hoy noticias", max_results=5)
    news_text = "\n".join(
        f"- {r.get('title', '')}: {r.get('body', r.get('snippet', ''))[:150]}"
        for r in results
    )

    prompt = (
        f"Analizá el estado actual de **{asset}**:\n\n"
        f"**Noticias recientes:**\n{news_text}\n\n"
        "Respondé con:\n"
        "- **Precio actual aproximado** (basado en noticias)\n"
        "- **Sentimiento del mercado:** alcista/bajista/neutro\n"
        "- **Noticias clave** que impactan el precio\n"
        "- **Señales:** qué vigilar en las próximas horas/días\n"
        "- **Recomendación:** (solo informativa, no consejo financiero)\n"
    )

    messages = [
        {"role": "system", "content": (
            "Sos un analista de mercados. Dá información objetiva basada en datos. "
            "Siempre aclarás que no es consejo financiero. Respondé en español."
        )},
        {"role": "user", "content": prompt},
    ]
    return chat(messages)


def scan_watchlist() -> str:
    wl = get_watchlist()
    if not wl:
        return "Watchlist vacía. Agregá assets con manage_watchlist action=add."

    lines = [f"**Market Scan — {datetime.now().strftime('%d/%m %H:%M')}**\n"]
    for item in wl:
        try:
            from web.search import web_search
            results = web_search(f"{item['asset']} precio", max_results=1)
            if results:
                lines.append(f"- **{item['asset']}** ({item['type']}): {results[0].get('title', 'Sin datos')}")
            else:
                lines.append(f"- **{item['asset']}**: Sin datos recientes")
        except Exception:
            lines.append(f"- **{item['asset']}**: Error obteniendo datos")

    return "\n".join(lines)
