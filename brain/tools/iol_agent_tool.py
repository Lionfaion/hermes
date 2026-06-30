"""Herramienta para que Hermes interactúe con el dashboard IOL / paper trading."""

import json
import urllib.request
import urllib.error
from tools.base import BaseTool
from config import IOL_DASHBOARD_URL, IOL_AGENT_API_KEY


def _request(method: str, path: str, body: dict | None = None) -> dict:
    url = f"{IOL_DASHBOARD_URL.rstrip('/')}{path}"
    data = json.dumps(body).encode() if body else None
    req = urllib.request.Request(
        url,
        data=data,
        method=method,
        headers={
            "x-api-key": IOL_AGENT_API_KEY,
            "Content-Type": "application/json",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            return json.loads(resp.read())
    except urllib.error.HTTPError as e:
        body_text = e.read().decode()
        return {"error": f"HTTP {e.code}: {body_text}"}
    except Exception as e:
        return {"error": str(e)}


class IOLAgentStatusTool(BaseTool):
    name = "iol_status"
    description = (
        "Obtiene el digest del sistema: régimen de mercado, portfolio de paper trading "
        "(P&L, win rate, posiciones abiertas), oportunidades de carry y próximos unlocks."
    )
    parameters = {"type": "object", "properties": {}, "required": []}

    def execute(self, **_) -> str:
        result = _request("GET", "/api/agent/status")
        if "error" in result:
            return f"[IOL Status Error] {result['error']}"
        pp = result.get("paper_portfolio", {})
        regime = result.get("market_regime", {})
        lines = [
            f"📊 Régimen: crypto={regime.get('crypto')} | arg={regime.get('arg_equities')}",
            f"💼 Paper portfolio: {pp.get('open_count', 0)} abiertas | "
            f"win rate {pp.get('win_rate', 0)}% | P&L ${pp.get('total_pnl_usd', 0)}",
        ]
        if pp.get("open_positions"):
            lines.append("Posiciones abiertas:")
            for p in pp["open_positions"]:
                lines.append(
                    f"  • {p['symbol']} {p['side'].upper()} "
                    f"x{p['quantity']} @ ${p['entry_price']} (entrada: {p['entry_time'][:10]})"
                )
        return "\n".join(lines)


class IOLCryptoPicksTool(BaseTool):
    name = "iol_crypto_picks"
    description = (
        "Escanea el mercado crypto en busca de señales de pump/momentum. "
        "Devuelve picks rankeados con confianza, cambio de precio y volumen."
    )
    parameters = {"type": "object", "properties": {}, "required": []}

    def execute(self, **_) -> str:
        result = _request("GET", "/api/agent/crypto-picks")
        if "error" in result:
            return f"[Crypto Picks Error] {result['error']}"
        picks = result.get("picks", [])
        if not picks or not result.get("scanner_active"):
            return (
                f"⚠️ {result.get('note', 'Scanner inactivo')}\n"
                "Para activarlo conectá un feed de precios (CoinGecko/Binance) al endpoint."
            )
        lines = [f"🚀 Crypto picks ({result.get('timestamp', '')[:10]}):"]
        for p in picks:
            lines.append(
                f"  • {p['symbol']} — señal: {p['signal']} "
                f"| confianza: {p['confidence']}% "
                f"| 1h: {p.get('change_1h_pct')}% | 24h: {p.get('change_24h_pct')}%"
            )
        return "\n".join(lines)


class IOLOpportunitiesTool(BaseTool):
    name = "iol_opportunities"
    description = (
        "Scan completo de acciones, CEDEARs y bonos argentinos rankeados por score. "
        "Útil para encontrar las mejores oportunidades del mercado local."
    )
    parameters = {"type": "object", "properties": {}, "required": []}

    def execute(self, **_) -> str:
        result = _request("GET", "/api/agent/opportunities")
        if "error" in result:
            return f"[Opportunities Error] {result['error']}"
        opps = result.get("opportunities", [])
        lines = [f"🏆 Oportunidades rankeadas ({result.get('scan_time', '')[:10]}):"]
        for o in opps:
            lines.append(
                f"  • [{o['score']}] {o['symbol']} ({o['type']}) — "
                f"{o['signal']} | {o.get('note', '')}"
            )
        return "\n".join(lines)


class IOLPaperTradeTool(BaseTool):
    name = "iol_paper_trade"
    description = (
        "Gestiona posiciones de paper trading cripto (simuladas, sin dinero real). "
        "Acciones disponibles:\n"
        "  - list: lista posiciones (status='open'|'closed'|'all')\n"
        "  - open: abre posición (symbol, side='long'|'short', entry_price, quantity, reason)\n"
        "  - close: cierra posición (id, exit_price)"
    )
    parameters = {
        "type": "object",
        "properties": {
            "action": {
                "type": "string",
                "enum": ["list", "open", "close"],
                "description": "Acción a realizar",
            },
            "status": {
                "type": "string",
                "enum": ["open", "closed", "all"],
                "description": "Filtro para 'list'. Por defecto 'open'.",
            },
            "symbol": {"type": "string", "description": "Par cripto. Ej: BTC/USDT"},
            "side": {"type": "string", "enum": ["long", "short"]},
            "entry_price": {"type": "number", "description": "Precio de entrada en USD"},
            "quantity": {"type": "number", "description": "Cantidad en activo base (ej. 0.01 BTC)"},
            "reason": {"type": "string", "description": "Razón / señal que disparó el trade"},
            "id": {"type": "string", "description": "ID de la posición (para cerrar)"},
            "exit_price": {"type": "number", "description": "Precio de salida en USD"},
        },
        "required": ["action"],
    }

    def execute(self, action: str, **kwargs) -> str:
        if action == "list":
            status = kwargs.get("status", "open")
            path = f"/api/agent/paper-trade?status={status}" if status != "all" else "/api/agent/paper-trade"
            result = _request("GET", path)
            if "error" in result:
                return f"[Paper Trade Error] {result['error']}"
            positions = result.get("positions", [])
            if not positions:
                return f"No hay posiciones ({status})."
            lines = [f"📋 Posiciones {status} ({len(positions)}):"]
            for p in positions:
                pnl = f" | P&L ${p['pnl_usd']}" if p.get("pnl_usd") is not None else ""
                lines.append(
                    f"  • [{p['id'][:8]}] {p['symbol']} {p['side'].upper()} "
                    f"x{p['quantity']} @ ${p['entry_price']}{pnl} — {p['status']}"
                )
            return "\n".join(lines)

        elif action == "open":
            for field in ("symbol", "side", "entry_price", "quantity"):
                if field not in kwargs:
                    return f"[Error] Falta el campo requerido: {field}"
            body = {
                "symbol": kwargs["symbol"],
                "side": kwargs["side"],
                "entry_price": kwargs["entry_price"],
                "quantity": kwargs["quantity"],
                "reason": kwargs.get("reason"),
            }
            result = _request("POST", "/api/agent/paper-trade", body)
            if "error" in result:
                return f"[Paper Trade Error] {result['error']}"
            p = result["position"]
            return (
                f"✅ Posición abierta: {p['symbol']} {p['side'].upper()} "
                f"x{p['quantity']} @ ${p['entry_price']} (id: {p['id'][:8]})"
            )

        elif action == "close":
            for field in ("id", "exit_price"):
                if field not in kwargs:
                    return f"[Error] Falta el campo requerido: {field}"
            body = {"id": kwargs["id"], "exit_price": kwargs["exit_price"]}
            result = _request("PATCH", "/api/agent/paper-trade", body)
            if "error" in result:
                return f"[Paper Trade Error] {result['error']}"
            p = result["position"]
            emoji = "🟢" if (p.get("pnl_usd") or 0) >= 0 else "🔴"
            return (
                f"{emoji} Posición cerrada: {p['symbol']} {p['side'].upper()} "
                f"@ ${p['exit_price']} | P&L: ${p['pnl_usd']} ({p['pnl_pct']}%)"
            )

        return f"[Error] Acción desconocida: {action}"
