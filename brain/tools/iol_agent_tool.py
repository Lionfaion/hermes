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
            f"📊 Régimen: {regime.get('label')} (longs {'permitidos' if regime.get('allow_long') else 'bloqueados'}, "
            f"size x{regime.get('size_multiplier')})",
            f"💼 Paper portfolio: {pp.get('open_count', 0)} abiertas | "
            f"win rate {pp.get('win_rate', 0)}% | P&L ${pp.get('total_pnl_usd', 0)}",
        ]
        if pp.get("open_positions"):
            lines.append("Posiciones abiertas:")
            for p in pp["open_positions"]:
                lines.append(
                    f"  • {p['symbol']} ({p['cluster']}) "
                    f"${p['position_size_usd']} @ ${p['entry_price']} (entrada: {p['entry_time'][:10]})"
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
        candidates = result.get("candidates", [])
        if not candidates or not result.get("scanner_active"):
            return "⚠️ Scanner inactivo o sin candidatos en este momento."
        lines = [f"🚀 Crypto picks ({result.get('updatedAt', '')[:10]}):"]
        for c in candidates[:10]:
            lines.append(
                f"  • {c['simbolo']} ({c['cluster']}) — score: {c['totalScore']} "
                f"| 1h: {c.get('change1h')}% | 24h: {c.get('change24h')}%"
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
            "symbol": {"type": "string", "description": "Ticker. Ej: SOL"},
            "nombre": {"type": "string", "description": "Nombre del activo. Ej: Solana"},
            "cluster": {"type": "string", "enum": ["long_pump", "classic"]},
            "entry_price": {"type": "number", "description": "Precio de entrada en USD"},
            "signal_score": {"type": "number", "description": "Score 0-100 del candidato"},
            "change_24h": {"type": "number", "description": "Cambio 24h en %, usado para sizing"},
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
            trades = result.get("trades", [])
            if not trades:
                return f"No hay posiciones ({status})."
            lines = [f"📋 Posiciones {status} ({len(trades)}):"]
            for t in trades:
                pnl = f" | P&L ${t['pnl']}" if t.get("pnl") is not None else ""
                lines.append(
                    f"  • [{t['id'][:8]}] {t['symbol']} ({t['cluster']}) "
                    f"${t['positionSizeUSD']} @ ${t['entryPrice']}{pnl} — {t['status']}"
                )
            return "\n".join(lines)

        elif action == "open":
            for field in ("symbol", "nombre", "cluster", "entry_price", "signal_score", "change_24h"):
                if field not in kwargs:
                    return f"[Error] Falta el campo requerido: {field}"
            body = {
                "symbol": kwargs["symbol"],
                "nombre": kwargs["nombre"],
                "cluster": kwargs["cluster"],
                "entryPrice": kwargs["entry_price"],
                "signalScore": kwargs["signal_score"],
                "change24h": kwargs["change_24h"],
            }
            result = _request("POST", "/api/agent/paper-trade", body)
            if "error" in result:
                return f"[Paper Trade Error] {result['error']}"
            t = result["trade"]
            return (
                f"✅ Posición abierta: {t['symbol']} LONG "
                f"${t['positionSizeUSD']} x{t['leverage']} @ ${t['entryPrice']} (id: {t['id'][:12]})"
            )

        elif action == "close":
            for field in ("id", "exit_price"):
                if field not in kwargs:
                    return f"[Error] Falta el campo requerido: {field}"
            body = {"id": kwargs["id"], "closePrice": kwargs["exit_price"]}
            result = _request("PATCH", "/api/agent/paper-trade", body)
            if "error" in result:
                return f"[Paper Trade Error] {result['error']}"
            t = result["trade"]
            emoji = "🟢" if (t.get("pnl") or 0) >= 0 else "🔴"
            return (
                f"{emoji} Posición cerrada: {t['symbol']} "
                f"@ ${t['closePrice']} | P&L: ${t['pnl']} ({t['pnlPct']}%)"
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
        result = _request("GET", "/api/agent/learning")
        if "error" in result:
            return f"[Learning Error] {result['error']}"

        scoring = result.get("scoring", {})
        trading = result.get("trading", {})

        lines = [
            "📊 <b>Hermes Trading — Aprendizaje</b>",
            f"Trades cerrados: {trading.get('closedCount', 0)} | "
            f"Win rate real: {trading.get('winRate', 0)}%",
            f"P&L total: ${trading.get('totalPnL', 0)} | "
            f"Profit factor: {trading.get('profitFactor', 0)}",
            f"Drawdown máx: {trading.get('maxDrawdownPct', 0)}%",
            "",
            f"Precisión del scoring (alertas que llegaron a +{scoring.get('hitThresholdPct', 15)}% "
            f"en {scoring.get('windowDays', 7)}d): {scoring.get('precisionPct', 'n/a')}%",
            f"Alertas evaluadas: {scoring.get('evaluatedCount', 0)} / {scoring.get('totalAlerts', 0)}",
        ]

        for prop in scoring.get("proposals", []):
            lines.append(f"\n💡 {prop['titulo']}: {prop['detalle']}")

        return "\n".join(lines)
