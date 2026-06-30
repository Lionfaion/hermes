"""
PumpScannerWorker: detecta pumps cripto vía CoinGecko, abre paper trades
automáticamente con TP/SL dinámico y loguea en Obsidian vault para autolearning.
"""

import json
import logging
import threading
import urllib.error
import urllib.request
from datetime import datetime
from pathlib import Path

from config import (
    IOL_DASHBOARD_URL, IOL_AGENT_API_KEY,
    PUMP_SCAN_INTERVAL, PUMP_CONFIDENCE_THRESHOLD,
    PUMP_MIN_VOLUME_USD, PUMP_POSITION_SIZE_USD,
    TELEGRAM_TOKEN, TELEGRAM_ALLOWED_USERS,
    VAULT_PATH, BASE_DIR,
)

logger = logging.getLogger(__name__)

COINGECKO_URL = (
    "https://api.coingecko.com/api/v3/coins/markets"
    "?vs_currency=usd&order=volume_desc&per_page=100&page=1"
    "&sparkline=false&price_change_percentage=1h%2C24h"
)
STATS_PATH = BASE_DIR / "data" / "pump_scanner_stats.json"
MAX_OPEN_POSITIONS = 10


# ── TP/SL Formula ──────────────────────────────────────────────────────────

def _calc_tp_sl(confidence: int, signal: str) -> tuple[float, float]:
    """Returns (tp_pct, sl_pct) based on confidence score and signal type.

    confidence 60 → TP 20% / SL 12%
    confidence 100 → TP 35% / SL 8%
    pump_detected adds 3% to TP.
    """
    normalized = max(0.0, (confidence - 60) / 40)
    tp_pct = 20 + normalized * 15
    sl_pct = 12 - normalized * 4
    if signal == "pump_detected":
        tp_pct += 3
    return round(tp_pct, 2), round(sl_pct, 2)


# ── CoinGecko ──────────────────────────────────────────────────────────────

def _fetch_coingecko() -> list[dict]:
    req = urllib.request.Request(COINGECKO_URL, headers={"Accept": "application/json"})
    with urllib.request.urlopen(req, timeout=15) as resp:
        return json.loads(resp.read())


def _score_coin(coin: dict) -> dict | None:
    change1h = coin.get("price_change_percentage_1h_in_currency") or 0.0
    change24h = coin.get("price_change_percentage_24h_in_currency") or 0.0
    volume = coin.get("total_volume") or 0
    mcap = coin.get("market_cap") or 1

    if volume < PUMP_MIN_VOLUME_USD:
        return None
    if change1h <= 0:
        return None

    spike = volume / mcap
    score_1h = min(change1h, 15) / 15 * 50
    score_vol = min(spike * 300, 30)
    score_momentum = 20 if (change1h > 3 and change24h > 5) else 0
    confidence = min(int(score_1h + score_vol + score_momentum), 100)

    signal = (
        "pump_detected" if change1h > 5 and spike > 0.08 else
        "momentum" if change1h > 2 and spike > 0.04 else
        "normal"
    )

    return {
        "symbol": f"{coin['symbol'].upper()}/USDT",
        "name": coin["name"],
        "price_usd": coin.get("current_price", 0),
        "change_1h_pct": round(change1h, 2),
        "change_24h_pct": round(change24h, 2),
        "volume_usd": volume,
        "volume_spike_ratio": round(spike, 4),
        "confidence": confidence,
        "signal": signal,
    }


# ── Dashboard API helpers ───────────────────────────────────────────────────

def _dashboard_request(method: str, path: str, body: dict | None = None) -> dict:
    if not IOL_DASHBOARD_URL or not IOL_AGENT_API_KEY:
        return {"error": "IOL_DASHBOARD_URL o IOL_AGENT_API_KEY no configurados"}
    url = f"{IOL_DASHBOARD_URL.rstrip('/')}{path}"
    data = json.dumps(body).encode() if body else None
    req = urllib.request.Request(
        url,
        data=data,
        method=method,
        headers={"x-api-key": IOL_AGENT_API_KEY, "Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(req, timeout=20) as resp:
            return json.loads(resp.read())
    except urllib.error.HTTPError as e:
        return {"error": f"HTTP {e.code}: {e.read().decode()}"}
    except Exception as e:
        return {"error": str(e)}


def _check_positions() -> dict:
    """Call dashboard check-positions to auto-close TP/SL hits."""
    return _dashboard_request("GET", "/api/agent/check-positions")


def _get_open_count() -> int:
    """Return number of currently open paper positions."""
    result = _dashboard_request("GET", "/api/agent/paper-trade?status=open")
    return result.get("count", 0)


def _open_paper_trade(coin: dict) -> dict | None:
    tp_pct, sl_pct = _calc_tp_sl(coin["confidence"], coin["signal"])
    body = {
        "symbol": coin["symbol"],
        "side": "long",
        "entry_price": coin["price_usd"],
        "quantity": round(PUMP_POSITION_SIZE_USD / max(coin["price_usd"], 0.0001), 6),
        "signal": coin["signal"],
        "confidence": coin["confidence"],
        "tp_pct": tp_pct,
        "sl_pct": sl_pct,
        "entry_context": {
            "btc_24h_pct": coin.get("btc_24h_pct", 0),
            "volume_spike": coin["volume_spike_ratio"],
            "total_open_at_entry": coin.get("open_count_at_entry", 0),
        },
        "reason": (
            f"PumpScanner: {coin['signal']} | "
            f"1h={coin['change_1h_pct']}% | "
            f"vol_spike={coin['volume_spike_ratio']} | "
            f"confidence={coin['confidence']}% | "
            f"TP={tp_pct}% SL={sl_pct}%"
        ),
    }
    result = _dashboard_request("POST", "/api/agent/paper-trade", body)
    if "error" in result:
        logger.error("Error abriendo paper trade: %s", result["error"])
        return None
    return result


# ── Telegram ───────────────────────────────────────────────────────────────

def _send_telegram(message: str) -> None:
    if not TELEGRAM_TOKEN or not TELEGRAM_ALLOWED_USERS:
        return
    chat_id = TELEGRAM_ALLOWED_USERS[0]
    payload = json.dumps({"chat_id": chat_id, "text": message, "parse_mode": "HTML"}).encode()
    req = urllib.request.Request(
        f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage",
        data=payload,
        headers={"Content-Type": "application/json"},
    )
    try:
        urllib.request.urlopen(req, timeout=10)
    except Exception as e:
        logger.warning("Telegram send failed: %s", e)


# ── Vault logging ──────────────────────────────────────────────────────────

def _log_to_vault(coin: dict, trade_id: str, tp_pct: float, sl_pct: float) -> None:
    vault_dir = Path(VAULT_PATH) / "Hermes" / "trades"
    vault_dir.mkdir(parents=True, exist_ok=True)

    date_str = datetime.now().strftime("%Y-%m-%d")
    symbol_safe = coin["symbol"].replace("/", "-")
    filename = f"{date_str}-{symbol_safe}-LONG.md"
    filepath = vault_dir / filename

    if filepath.exists():
        return

    content = (
        f"---\n"
        f"date: {datetime.now().isoformat()}\n"
        f"symbol: {coin['symbol']}\n"
        f"side: long\n"
        f"entry_price: {coin['price_usd']}\n"
        f"signal: {coin['signal']}\n"
        f"confidence: {coin['confidence']}%\n"
        f"tp_pct: {tp_pct}%\n"
        f"sl_pct: {sl_pct}%\n"
        f"change_1h: {coin['change_1h_pct']}%\n"
        f"change_24h: {coin['change_24h_pct']}%\n"
        f"volume_spike_ratio: {coin['volume_spike_ratio']}\n"
        f"trade_id: {trade_id}\n"
        f"status: open\n"
        f"outcome: \n"
        f"pnl_pct: \n"
        f"---\n\n"
        f"# Paper Trade: {coin['symbol']} LONG\n\n"
        f"**Señal:** {coin['signal']} | Confianza: {coin['confidence']}%\n\n"
        f"## Niveles\n"
        f"- Entrada: ${coin['price_usd']}\n"
        f"- Take Profit: +{tp_pct}%\n"
        f"- Stop Loss: -{sl_pct}%\n\n"
        f"## Condiciones de entrada\n"
        f"- Cambio 1h: {coin['change_1h_pct']}%\n"
        f"- Cambio 24h: {coin['change_24h_pct']}%\n"
        f"- Volume spike ratio: {coin['volume_spike_ratio']}\n\n"
        f"## Resultado\n"
        f"*(Completar al cerrar: tp_hit/sl_hit, precio de salida, lección)*\n"
    )
    filepath.write_text(content, encoding="utf-8")
    logger.info("Trade logueado en vault: %s", filepath)


# ── Stats ──────────────────────────────────────────────────────────────────

def _load_stats() -> dict:
    if STATS_PATH.exists():
        try:
            return json.loads(STATS_PATH.read_text())
        except Exception:
            pass
    return {
        "total_scans": 0,
        "pumps_detected": 0,
        "trades_opened": 0,
        "by_signal": {},
        "last_scan": None,
    }


def _save_stats(stats: dict) -> None:
    STATS_PATH.parent.mkdir(parents=True, exist_ok=True)
    STATS_PATH.write_text(json.dumps(stats, indent=2))


# ── Worker ─────────────────────────────────────────────────────────────────

class PumpScannerWorker:
    def __init__(self):
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None
        self._seen: set[str] = set()  # symbols ya operados en esta sesión

    def start(self) -> None:
        if self._thread and self._thread.is_alive():
            return
        self._stop.clear()
        self._thread = threading.Thread(
            target=self._loop, daemon=True, name="pump-scanner"
        )
        self._thread.start()
        logger.info("PumpScannerWorker iniciado (intervalo %ds)", PUMP_SCAN_INTERVAL)

    def stop(self) -> None:
        self._stop.set()
        if self._thread:
            self._thread.join(timeout=10)

    def _loop(self) -> None:
        while not self._stop.is_set():
            try:
                self._scan()
            except Exception as e:
                logger.error("PumpScanner error en scan: %s", e)
            self._stop.wait(PUMP_SCAN_INTERVAL)

    def _scan(self) -> None:
        stats = _load_stats()
        stats["total_scans"] += 1
        stats["last_scan"] = datetime.now().isoformat()

        # 1. Auto-close any TP/SL hits before scanning for new entries
        try:
            checked = _check_positions()
            if checked.get("closed"):
                for c in checked["closed"]:
                    emoji = "✅" if c["reason"] == "tp_hit" else "🔴"
                    msg = (
                        f"{emoji} <b>Auto-close: {c['symbol']}</b>\n"
                        f"Motivo: {c['reason']} | P&amp;L: ${c['pnl_usd']} ({c['pnl_pct']}%)\n"
                        f"Duración: {c['held_hours']}hs"
                    )
                    _send_telegram(msg)
        except Exception as e:
            logger.warning("check-positions falló: %s", e)

        # 2. Check available slots
        open_count = _get_open_count()
        available_slots = max(0, MAX_OPEN_POSITIONS - open_count)
        if available_slots == 0:
            logger.info("Max positions reached (%d). Skipping new entries.", MAX_OPEN_POSITIONS)
            _save_stats(stats)
            return

        # 3. Fetch and score coins
        try:
            coins_raw = _fetch_coingecko()
        except Exception as e:
            logger.warning("CoinGecko fetch falló: %s", e)
            _save_stats(stats)
            return

        # Extract BTC 24h change for entry_context
        btc_coin = next((c for c in coins_raw if c.get("symbol", "").lower() == "btc"), {})
        btc_24h_pct = round(btc_coin.get("price_change_percentage_24h_in_currency") or 0.0, 2)

        picks = [c for coin in coins_raw if (c := _score_coin(coin)) is not None]
        pumps = [
            p for p in picks
            if p["confidence"] >= PUMP_CONFIDENCE_THRESHOLD
            and p["signal"] in ("pump_detected", "momentum")
            and p["symbol"] not in self._seen
        ]
        pumps.sort(key=lambda x: x["confidence"], reverse=True)

        stats["pumps_detected"] += len(pumps)

        # 4. Open new positions up to available slots
        opened_this_cycle: list[tuple[dict, dict]] = []
        for coin in pumps[:available_slots]:
            coin["open_count_at_entry"] = open_count
            coin["btc_24h_pct"] = btc_24h_pct

            logger.info(
                "🚀 Pump: %s confidence=%d%% signal=%s",
                coin["symbol"], coin["confidence"], coin["signal"]
            )

            result = _open_paper_trade(coin)
            if not result:
                continue

            trade = result.get("position", {})
            trade_id = trade.get("id", "unknown")
            tp_pct, sl_pct = _calc_tp_sl(coin["confidence"], coin["signal"])

            self._seen.add(coin["symbol"])
            stats["trades_opened"] += 1
            open_count += 1

            sig = coin["signal"]
            stats["by_signal"].setdefault(sig, {"trades": 0, "wins": 0})
            stats["by_signal"][sig]["trades"] += 1

            _log_to_vault(coin, trade_id, tp_pct, sl_pct)
            opened_this_cycle.append((coin, trade))

        # 5. Send single Telegram summary if new positions opened
        if opened_this_cycle:
            lines = [f"🤖 <b>Hermes Trading — {datetime.now().strftime('%H:%M')}hs</b>"]
            lines.append(f"📈 Nuevas posiciones: {len(opened_this_cycle)}")
            for coin, _ in opened_this_cycle:
                tp_pct, sl_pct = _calc_tp_sl(coin["confidence"], coin["signal"])
                lines.append(
                    f"  • {coin['symbol']} LONG ${PUMP_POSITION_SIZE_USD} "
                    f"(conf {coin['confidence']}%) → TP +{tp_pct}% / SL -{sl_pct}%"
                )
            total_open = _get_open_count()
            lines.append(f"Portfolio: {total_open} abiertas de {MAX_OPEN_POSITIONS} máx")
            _send_telegram("\n".join(lines))

        _save_stats(stats)
        logger.info(
            "Scan completo: %d coins, %d picks, %d pumps nuevos",
            len(coins_raw), len(picks), len(pumps),
        )
