"""
PumpScannerWorker: detecta pumps cripto vía CoinGecko, abre paper trades
automáticamente y loguea en Obsidian vault para autolearning.
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


# ── Paper trade ────────────────────────────────────────────────────────────

def _open_paper_trade(coin: dict) -> dict | None:
    if not IOL_DASHBOARD_URL or not IOL_AGENT_API_KEY:
        logger.warning("IOL_DASHBOARD_URL o IOL_AGENT_API_KEY no configurados")
        return None

    qty = round(PUMP_POSITION_SIZE_USD / max(coin["price_usd"], 0.0001), 6)
    body = {
        "symbol": coin["symbol"],
        "side": "long",
        "entry_price": coin["price_usd"],
        "quantity": qty,
        "reason": (
            f"PumpScanner: {coin['signal']} | "
            f"1h={coin['change_1h_pct']}% | "
            f"vol_spike={coin['volume_spike_ratio']} | "
            f"confidence={coin['confidence']}%"
        ),
    }
    data = json.dumps(body).encode()
    req = urllib.request.Request(
        f"{IOL_DASHBOARD_URL.rstrip('/')}/api/agent/paper-trade",
        data=data,
        method="POST",
        headers={"x-api-key": IOL_AGENT_API_KEY, "Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            return json.loads(resp.read())
    except urllib.error.HTTPError as e:
        logger.error("Error abriendo paper trade: HTTP %s — %s", e.code, e.read().decode())
        return None
    except Exception as e:
        logger.error("Error abriendo paper trade: %s", e)
        return None


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

def _log_to_vault(coin: dict, trade_id: str) -> None:
    vault_dir = Path(VAULT_PATH) / "Hermes" / "trades"
    vault_dir.mkdir(parents=True, exist_ok=True)

    date_str = datetime.now().strftime("%Y-%m-%d")
    symbol_safe = coin["symbol"].replace("/", "-")
    filename = f"{date_str}-{symbol_safe}-LONG.md"
    filepath = vault_dir / filename

    # Si ya existe (mismo símbolo, mismo día) no sobrescribir
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
        f"## Condiciones de entrada\n"
        f"- Precio: ${coin['price_usd']}\n"
        f"- Cambio 1h: {coin['change_1h_pct']}%\n"
        f"- Cambio 24h: {coin['change_24h_pct']}%\n"
        f"- Volume spike ratio: {coin['volume_spike_ratio']} (>0.08 = pump)\n\n"
        f"## Resultado\n"
        f"*(Completar al cerrar: win/loss, precio de salida, lección)*\n"
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

        try:
            coins_raw = _fetch_coingecko()
        except Exception as e:
            logger.warning("CoinGecko fetch falló: %s", e)
            _save_stats(stats)
            return

        picks = [c for coin in coins_raw if (c := _score_coin(coin)) is not None]
        pumps = [
            p for p in picks
            if p["confidence"] >= PUMP_CONFIDENCE_THRESHOLD
            and p["symbol"] not in self._seen
        ]

        stats["pumps_detected"] += len(pumps)

        for coin in pumps[:3]:  # máx 3 por scan para no saturar
            logger.info(
                "🚀 Pump: %s confidence=%d%% signal=%s",
                coin["symbol"], coin["confidence"], coin["signal"]
            )

            result = _open_paper_trade(coin)
            if not result:
                continue

            trade = result.get("position", {})
            trade_id = trade.get("id", "unknown")
            self._seen.add(coin["symbol"])
            stats["trades_opened"] += 1

            sig = coin["signal"]
            stats["by_signal"].setdefault(sig, {"trades": 0, "wins": 0})
            stats["by_signal"][sig]["trades"] += 1

            _log_to_vault(coin, trade_id)

            msg = (
                f"🚀 <b>Pump detectado: {coin['symbol']}</b>\n"
                f"Señal: {coin['signal']} | Confianza: {coin['confidence']}%\n"
                f"1h: {coin['change_1h_pct']}% | 24h: {coin['change_24h_pct']}%\n"
                f"Volume spike: {coin['volume_spike_ratio']:.3f}\n"
                f"📋 Paper trade: LONG x{trade.get('quantity', '?')} @ ${coin['price_usd']}\n"
                f"ID: <code>{trade_id[:8]}</code>"
            )
            _send_telegram(msg)

        _save_stats(stats)
        logger.info(
            "Scan completo: %d coins analizadas, %d picks, %d pumps nuevos",
            len(coins_raw), len(picks), len(pumps),
        )
