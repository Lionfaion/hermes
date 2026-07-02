"""
PumpScannerWorker: pide candidatos ya puntuados por el motor real del dashboard
(/api/agent/crypto-picks), abre paper trades con sizing/riesgo calculados por el
dashboard (Kelly + risk engine) y loguea en Obsidian vault para autolearning.

No envía notificaciones de Telegram por cada apertura/cierre — el estado del
trading se consulta a demanda vía las tools iol_status / iol_learning / iol_paper_trade.
"""

import json
import logging
import re
import threading
import urllib.error
import urllib.request
from datetime import datetime
from pathlib import Path

from config import (
    IOL_DASHBOARD_URL, IOL_AGENT_API_KEY,
    PUMP_SCAN_INTERVAL, PUMP_CONFIDENCE_THRESHOLD,
    VAULT_PATH,
)

logger = logging.getLogger(__name__)

MAX_OPEN_POSITIONS = 10
VAULT_TRADES_DIR = Path(VAULT_PATH) / "Hermes" / "trades"


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
        with urllib.request.urlopen(req, timeout=25) as resp:
            return json.loads(resp.read())
    except urllib.error.HTTPError as e:
        return {"error": f"HTTP {e.code}: {e.read().decode()}"}
    except Exception as e:
        return {"error": str(e)}


def _fetch_picks() -> list[dict]:
    """Candidatos ya puntuados por el scorer real del dashboard (PumpCandidate[])."""
    result = _dashboard_request("GET", "/api/agent/crypto-picks")
    if "error" in result or not result.get("scanner_active"):
        if "error" in result:
            logger.warning("crypto-picks falló: %s", result["error"])
        return []
    return result.get("candidates", [])


def _check_positions() -> dict:
    return _dashboard_request("GET", "/api/agent/check-positions")


def _get_open_count() -> int:
    result = _dashboard_request("GET", "/api/agent/paper-trade?status=open")
    return result.get("count", 0)


def _open_paper_trade(candidate: dict) -> dict | None:
    body = {
        "symbol": candidate["simbolo"],
        "nombre": candidate["nombre"],
        "coingeckoId": candidate.get("id"),
        "cluster": candidate["cluster"],
        "entryPrice": candidate["price"],
        "signalScore": candidate["totalScore"],
        "change24h": candidate["change24h"],
    }
    result = _dashboard_request("POST", "/api/agent/paper-trade", body)
    if "error" in result:
        logger.warning("Trade rechazado para %s: %s", candidate["simbolo"], result["error"])
        return None
    return result


# ── Vault logging ──────────────────────────────────────────────────────────

def _log_to_vault(candidate: dict, trade: dict, sizing: dict) -> None:
    VAULT_TRADES_DIR.mkdir(parents=True, exist_ok=True)

    date_str = datetime.now().strftime("%Y-%m-%d")
    symbol_safe = candidate["simbolo"].replace("/", "-")
    filename = f"{date_str}-{symbol_safe}-LONG.md"
    filepath = VAULT_TRADES_DIR / filename

    if filepath.exists():
        return

    content = (
        f"---\n"
        f"date: {datetime.now().isoformat()}\n"
        f"symbol: {candidate['simbolo']}\n"
        f"cluster: {candidate['cluster']}\n"
        f"side: long\n"
        f"entry_price: {candidate['price']}\n"
        f"signal_score: {candidate['totalScore']}\n"
        f"position_size_usd: {trade.get('positionSizeUSD')}\n"
        f"leverage: {trade.get('leverage')}\n"
        f"tp_pct: {sizing.get('takeProfitPct')}%\n"
        f"sl_pct: {sizing.get('stopLossPct')}%\n"
        f"change_1h: {candidate.get('change1h')}%\n"
        f"change_24h: {candidate.get('change24h')}%\n"
        f"vol_mcap_ratio: {candidate.get('volMcapRatio')}\n"
        f"trade_id: {trade.get('id')}\n"
        f"status: open\n"
        f"outcome: \n"
        f"pnl_pct: \n"
        f"---\n\n"
        f"# Paper Trade: {candidate['simbolo']} LONG ({candidate['cluster']})\n\n"
        f"**Score:** {candidate['totalScore']} | **Cluster:** {candidate['cluster']}\n\n"
        f"## Sizing (Kelly + risk engine)\n"
        f"- Tamaño: ${trade.get('positionSizeUSD')} | Leverage: {trade.get('leverage')}x\n"
        f"- Take Profit: +{sizing.get('takeProfitPct')}%\n"
        f"- Stop Loss: -{sizing.get('stopLossPct')}%\n\n"
        f"## Condiciones de entrada\n"
        f"- Cambio 1h: {candidate.get('change1h')}%\n"
        f"- Cambio 24h: {candidate.get('change24h')}%\n"
        f"- Vol/Mcap ratio: {candidate.get('volMcapRatio')}\n\n"
        f"## Resultado\n"
        f"*(Se completa automáticamente al cerrar la posición)*\n"
    )
    filepath.write_text(content, encoding="utf-8")
    logger.info("Trade logueado en vault: %s", filepath)


def _update_vault_outcome(symbol: str, reason: str, pnl_pct: float) -> None:
    """Marca la nota de vault de este símbolo como cerrada con su resultado real,
    para que el debate sintético nocturno (Task 12) pueda analizarlo después."""
    if not VAULT_TRADES_DIR.exists():
        return
    candidates = sorted(
        VAULT_TRADES_DIR.glob(f"*-{symbol.replace('/', '-')}-LONG.md"),
        key=lambda p: p.stat().st_mtime,
        reverse=True,
    )
    for filepath in candidates:
        try:
            content = filepath.read_text(encoding="utf-8")
        except Exception:
            continue
        if "status: open" not in content:
            continue
        updated = content.replace("status: open", "status: closed", 1)
        updated = re.sub(r"^outcome:\s*$", f"outcome: {reason}", updated, count=1, flags=re.MULTILINE)
        updated = re.sub(r"^pnl_pct:\s*$", f"pnl_pct: {pnl_pct}", updated, count=1, flags=re.MULTILINE)
        filepath.write_text(updated, encoding="utf-8")
        logger.info("Vault actualizado (%s): %s", reason, filepath.name)
        return


# ── Worker ─────────────────────────────────────────────────────────────────

class PumpScannerWorker:
    def __init__(self):
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None
        self._seen: set[str] = set()  # símbolos ya operados en esta sesión

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
        # 1. Auto-close any TP/SL hits before scanning for new entries — sin Telegram,
        #    solo actualiza el vault para que iol_status/iol_learning lo reflejen al consultar.
        try:
            checked = _check_positions()
            for c in checked.get("closed", []):
                _update_vault_outcome(c["symbol"], c["reason"], c["pnl_pct"])
                logger.info(
                    "Auto-close: %s — %s | P&L $%s (%s%%)",
                    c["symbol"], c["reason"], c["pnl_usd"], c["pnl_pct"],
                )
        except Exception as e:
            logger.warning("check-positions falló: %s", e)

        # 2. Check available slots
        open_count = _get_open_count()
        available_slots = max(0, MAX_OPEN_POSITIONS - open_count)
        if available_slots == 0:
            logger.info("Max positions reached (%d). Skipping new entries.", MAX_OPEN_POSITIONS)
            return

        # 3. Fetch real-scored candidates from the dashboard
        candidates = _fetch_picks()
        if not candidates:
            logger.info("Sin candidatos del scanner esta vez.")
            return

        pumps = [
            c for c in candidates
            if c["totalScore"] >= PUMP_CONFIDENCE_THRESHOLD
            and c["simbolo"] not in self._seen
        ]
        pumps.sort(key=lambda c: c["totalScore"], reverse=True)

        # 4. Open new positions up to available slots — dashboard sizes/risk-checks each one.
        #    Sin Telegram: queda logueado y disponible vía iol_status / iol_paper_trade.
        opened = 0
        for candidate in pumps[:available_slots]:
            logger.info(
                "🚀 Candidato: %s score=%d cluster=%s",
                candidate["simbolo"], candidate["totalScore"], candidate["cluster"]
            )

            result = _open_paper_trade(candidate)
            if not result:
                continue

            trade = result.get("trade", {})
            sizing = result.get("sizing", {})

            self._seen.add(candidate["simbolo"])
            _log_to_vault(candidate, trade, sizing)
            opened += 1

            for w in result.get("riskWarnings", []):
                logger.info("Risk warning %s: %s", candidate["simbolo"], w)

        logger.info(
            "Scan completo: %d candidatos, %d superan umbral, %d abiertos",
            len(candidates), len(pumps), opened,
        )
