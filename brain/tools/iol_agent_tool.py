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


class IOLLearningTool(BaseTool):
    name = "iol_learning"
    description = (
        "Consulta el historial de aprendizaje del trading autónomo. "
        "Muestra win rate, mejores señales, P&L total, duración promedio de trades ganadores. "
        "Útil cuando el usuario pregunta '¿cómo viene el trading?', '¿qué aprendiste?', "
        "'¿cuáles son las mejores señales?', '¿cuál es el rendimiento?'."
    )
    parameters = {
        "type": "object",
        "properties": {
            "outcome": {
                "type": "string",
                "enum": ["tp_hit", "sl_hit", "open", "all"],
                "description": "Filtrar por resultado. Por defecto 'all'.",
            },
            "limit": {
                "type": "integer",
                "description": "Número máximo de trades a mostrar. Por defecto 20.",
            },
        },
        "required": [],
    }

    def execute(self, outcome: str = "all", limit: int = 20, **_) -> str:
        path = "/api/agent/learning"
        params = []
        if outcome and outcome != "all":
            params.append(f"outcome={outcome}")
        if limit:
            params.append(f"limit={limit}")
        if params:
            path += "?" + "&".join(params)

        result = _request("GET", path)
        if "error" in result:
            return f"[Learning Error] {result['error']}"

        summary = result.get("summary", {})
        entries = result.get("entries", [])
        total = result.get("total", 0)

        lines = [
            f"📊 <b>Hermes Trading — Aprendizaje</b>",
            f"Trades totales: {total} | Win rate: {summary.get('win_rate', 0)}%",
            f"P&L total: ${summary.get('total_pnl_usd', 0)}",
            f"Promedio ganadores: +${summary.get('avg_pnl_winners_usd', 0)}",
            f"Promedio perdedores: ${summary.get('avg_pnl_losers_usd', 0)}",
            f"Mejor señal: {summary.get('best_signal', 'n/a')}",
            f"Duración promedio ganadores: {summary.get('avg_held_hours_winners', 0)}hs",
        ]

        if entries:
            lines.append(f"\nÚltimos {min(len(entries), 10)} trades:")
            for e in entries[:10]:
                outcome_emoji = (
                    "✅" if e["outcome"] == "tp_hit" else
                    "🔴" if e["outcome"] == "sl_hit" else
                    "🔵" if e["outcome"] == "open" else "⚪"
                )
                pnl_str = f" P&L ${e['pnl_usd']}" if e.get("pnl_usd") is not None else ""
                lines.append(
                    f"  {outcome_emoji} {e['symbol']} | conf {e['confidence']}% | "
                    f"{e['signal']}{pnl_str}"
                )

        return "\n".join(lines)
