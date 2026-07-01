#!/usr/bin/env python3
"""
Sistema de debate sintético nocturno.
Hermes vs El Crítico → 5 rondas → El Juez extrae conocimiento.
Guarda resultados en el vault como notas .md y en /memoria/conocimiento_sintetico/
"""
import json
import logging
import os
import random
import re
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

try:
    from dotenv import load_dotenv
    load_dotenv(Path(__file__).parent.parent / ".env")
except ImportError:
    pass

from inference_client import chat, is_online
from config import OLLAMA_MODEL, VAULT_PATH

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("hermes.debate")

# ── Temas de interés (se complementan con palabras clave del vault) ───────────
TEMAS = [
    # Programación & Software
    "Mejores prácticas para construir agentes de IA autónomos con Python",
    "Cuándo usar microservicios vs monolito en proyectos personales",
    "Técnicas de optimización de código Python para hardware limitado",
    "Patrones de diseño más útiles para scripts de automatización",
    # IA & ML
    "RAG vs Fine-tuning: cuándo usar cada enfoque y por qué",
    "Cómo evaluar la calidad de modelos LLM locales sin benchmarks externos",
    "Prompt engineering avanzado: técnicas que realmente marcan diferencia",
    "Arquitecturas de memoria para agentes de IA con contexto largo",
    # Diseño & Creatividad
    "Principios de diseño minimalista aplicados a interfaces de usuario",
    "Cómo la psicología del color afecta las decisiones en diseño de interiores",
]

# ── Temas de cripto / pump trading / evaluación de proyectos (peso alto) ──────
TEMAS_CRIPTO = [
    "Cómo distinguir un pump real (con fundamento) de un pump-and-dump diseñado para atrapar compradores tardíos",
    "Qué métricas on-chain (holders, liquidez, distribución de supply) predicen mejor la sostenibilidad de un rally",
    "Tokenomics: red flags en la distribución de supply y vesting que anticipan un dump",
    "Cómo evaluar el equipo y la narrativa de un proyecto cripto antes de invertir, más allá del precio",
    "Funding rate y open interest: qué dicen sobre si un pump tiene combustible para seguir o está sobre-apalancado",
    "Gestión de riesgo específica para pump trading: sizing, stop-loss y cuándo tomar ganancias parciales",
    "Rotación de narrativas en cripto (AI coins, memecoins, RWA, gaming): cómo detectar el sector caliente antes de que sea obvio",
    "Errores comunes al perseguir un pump que ya corrió mucho (FOMO entry) y cómo evitarlos",
    "Cómo la correlación con BTC afecta la probabilidad de éxito de un altcoin pump",
    "Qué aprender de un trade perdedor en pump trading: separar mala suerte de mal proceso",
    "Análisis técnico vs fundamental aplicado específicamente a microcaps cripto de baja liquidez",
    "Cómo se manipulan los volúmenes en exchanges de bajo volumen y cómo detectarlo",
]

# ── System prompts de cada rol ─────────────────────────────────────────────────
PROMPT_HERMES = """Eres Hermes, un experto analítico con profundo conocimiento técnico.
Cuando debatas, defiende tu postura con argumentos sólidos, datos concretos y ejemplos prácticos.
Sé directo, conciso y claro. Máximo 120 palabras por respuesta."""

PROMPT_CRITICO = """Eres El Crítico, un experto hipercrítico y escéptico con estándares altísimos.
Tu rol es encontrar fallas lógicas, limitaciones prácticas, excepciones importantes y alternativas superiores.
No ataques a la persona. Ataca los argumentos con precisión. Señala contraejemplos reales.
Máximo 120 palabras por respuesta."""

PROMPT_JUEZ = """Eres un Juez neutral con experiencia en el área debatida.
Analiza el debate completo. Sé objetivo y honesto — si ambos tienen razón en partes, dilo.

Devuelve ÚNICAMENTE un JSON válido, sin texto adicional:
{
  "tema": "...",
  "conceptos_clave_aprendidos": ["concepto 1", "concepto 2", "concepto 3"],
  "errores_desmentidos": ["mito o error corregido 1", "..."],
  "mejores_practicas_validadas": ["práctica validada 1", "..."],
  "conclusion": "Una frase que resume el veredicto final del debate"
}

Cada lista: máximo 4 ítems. Cada ítem: máximo 15 palabras."""


def _tema_de_trade_reciente() -> str | None:
    """Si hay paper trades recientes de Hermes en el vault, debatir sobre uno real
    en vez de un tema genérico — autolearning sobre decisiones propias."""
    trades_dir = Path(VAULT_PATH) / "Hermes" / "trades"
    if not trades_dir.exists():
        return None
    files = sorted(trades_dir.glob("*.md"), key=lambda p: p.stat().st_mtime, reverse=True)[:15]
    if not files:
        return None
    f = random.choice(files)
    try:
        content = f.read_text(encoding="utf-8", errors="ignore")
        symbol_m  = re.search(r"^symbol:\s*(.+)$", content, re.MULTILINE)
        cluster_m = re.search(r"^cluster:\s*(.+)$", content, re.MULTILINE)
        score_m   = re.search(r"^signal_score:\s*(.+)$", content, re.MULTILINE)
        outcome_m = re.search(r"^outcome:\s*(.*)$", content, re.MULTILINE)
        symbol  = symbol_m.group(1).strip()  if symbol_m  else "un activo"
        cluster = cluster_m.group(1).strip() if cluster_m else "?"
        score   = score_m.group(1).strip()   if score_m   else "?"
        outcome = outcome_m.group(1).strip() if outcome_m else ""
        resultado_txt = f" (resultado: {outcome})" if outcome else " (todavía abierta o sin resolver)"
        return (
            f"Analizar la entrada en {symbol} (cluster {cluster}, score {score}){resultado_txt}: "
            f"¿la señal estaba bien fundamentada? ¿el sizing y los niveles de TP/SL fueron correctos? "
            f"¿qué cambiaría para la próxima vez?"
        )
    except Exception:
        return None


def seleccionar_tema(forzar_cripto: bool = False) -> str:
    """Prioriza pumps/cripto/proyectos: 35% un trade real reciente si existe,
    35% un tema curado de TEMAS_CRIPTO, 25% un tema general, 5% palabras del vault.
    Si forzar_cripto=True, ignora el sorteo y siempre elige cripto (trade real si hay,
    si no un tema curado de TEMAS_CRIPTO)."""
    if forzar_cripto:
        tema_real = _tema_de_trade_reciente()
        return tema_real if tema_real else random.choice(TEMAS_CRIPTO)

    roll = random.random()

    if roll < 0.35:
        tema_real = _tema_de_trade_reciente()
        if tema_real:
            return tema_real
        # sin trades aún — cae a tema curado de cripto
        return random.choice(TEMAS_CRIPTO)

    if roll < 0.70:
        return random.choice(TEMAS_CRIPTO)

    if roll < 0.95:
        return random.choice(TEMAS)

    vault = Path(VAULT_PATH)
    if vault.exists():
        md_files = list(vault.rglob("*.md"))
        if md_files:
            try:
                content = random.choice(md_files).read_text(encoding="utf-8", errors="ignore")
                words = re.findall(r"\b[A-Za-záéíóúüñÁÉÍÓÚÑ]{6,}\b", content)
                if len(words) >= 3:
                    sample = random.sample(words, min(3, len(words)))
                    return f"Profundizar en: {', '.join(sample)} — mejores prácticas y errores comunes"
            except Exception:
                pass
    return random.choice(TEMAS_CRIPTO)


def run_debate(tema: str, rondas: int = 5) -> list:
    import time
    logger.info("Iniciando debate — Tema: %s", tema)
    transcript = []

    h_hist = [{"role": "system", "content": PROMPT_HERMES}]
    c_hist = [{"role": "system", "content": PROMPT_CRITICO}]

    # Apertura de Hermes
    h_hist.append({"role": "user", "content": f"El tema es: '{tema}'. Presenta tu postura inicial con argumentos concretos."})
    h_resp = chat(h_hist, OLLAMA_MODEL)
    h_hist.append({"role": "assistant", "content": h_resp})
    transcript.append({"rol": "Hermes", "msg": h_resp})
    logger.info("Hermes abre: %s...", h_resp[:70])
    time.sleep(4)

    for ronda in range(rondas):
        # Crítico responde a Hermes
        c_hist.append({"role": "user", "content": h_resp})
        c_resp = chat(c_hist, OLLAMA_MODEL)
        c_hist.append({"role": "assistant", "content": c_resp})
        transcript.append({"rol": "Crítico", "msg": c_resp})
        logger.info("Ronda %d — Crítico: %s...", ronda + 1, c_resp[:60])
        time.sleep(4)

        if ronda == rondas - 1:
            break

        # Hermes contraargumenta
        h_hist.append({"role": "user", "content": c_resp})
        h_resp = chat(h_hist, OLLAMA_MODEL)
        h_hist.append({"role": "assistant", "content": h_resp})
        transcript.append({"rol": "Hermes", "msg": h_resp})
        logger.info("Ronda %d — Hermes: %s...", ronda + 1, h_resp[:60])

    return transcript


def juzgar(tema: str, transcript: list) -> dict:
    debate_txt = "\n\n".join(f"[{t['rol']}]: {t['msg']}" for t in transcript)
    messages = [
        {"role": "system", "content": PROMPT_JUEZ},
        {"role": "user", "content": f"Tema: {tema}\n\nDebate completo:\n{debate_txt}"},
    ]
    response = chat(messages, OLLAMA_MODEL)
    match = re.search(r"\{.*\}", response, re.DOTALL)
    if match:
        result = json.loads(match.group())
        result.setdefault("tema", tema)
        return result
    return {
        "tema": tema,
        "conceptos_clave_aprendidos": [],
        "errores_desmentidos": [],
        "mejores_practicas_validadas": [],
        "conclusion": "Sin veredicto (JSON no parseable)",
    }


def guardar(resultado: dict, transcript: list):
    fecha = datetime.now().strftime("%Y-%m-%d_%H-%M")

    # 1. JSON de conocimiento sintético
    mem_dir = Path(VAULT_PATH).parent / "memoria" / "conocimiento_sintetico"
    mem_dir.mkdir(parents=True, exist_ok=True)
    json_path = mem_dir / f"debate_{fecha}.json"
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump({"resultado": resultado, "transcript": transcript}, f, ensure_ascii=False, indent=2)

    # 2. Nota .md legible en el vault
    vault_dir = Path(VAULT_PATH) / "conocimiento" / "debates"
    vault_dir.mkdir(parents=True, exist_ok=True)
    md_path = vault_dir / f"debate_{fecha}.md"

    def li(items): return "\n".join(f"- {i}" for i in items) if items else "- (ninguno)"

    md = f"""# Debate: {resultado['tema']}
*Generado automáticamente — {datetime.now().strftime('%d/%m/%Y %H:%M')}*

## Conceptos Clave Aprendidos
{li(resultado.get('conceptos_clave_aprendidos', []))}

## Errores Desmentidos
{li(resultado.get('errores_desmentidos', []))}

## Mejores Prácticas Validadas
{li(resultado.get('mejores_practicas_validadas', []))}

## Conclusión del Juez
{resultado.get('conclusion', '')}
"""
    md_path.write_text(md, encoding="utf-8")
    logger.info("Guardado: %s", json_path)
    logger.info("Nota vault: %s", md_path)


def _notify_telegram(text: str) -> None:
    import requests
    token = os.getenv("TELEGRAM_TOKEN", "")
    chat_id = os.getenv("TELEGRAM_CHAT_ID", "")
    if not token or not chat_id:
        logger.warning("TELEGRAM_TOKEN o TELEGRAM_CHAT_ID no configurados — sin notificación")
        return
    try:
        requests.post(
            f"https://api.telegram.org/bot{token}/sendMessage",
            json={"chat_id": chat_id, "text": text, "parse_mode": "Markdown"},
            timeout=10,
        )
    except Exception as e:
        logger.warning("No pude notificar por Telegram: %s", e)


def _ejecutar_una_conversacion(numero: int, total: int, forzar_cripto: bool) -> None:
    tema = seleccionar_tema(forzar_cripto=forzar_cripto)
    logger.info("--- Conversación %d/%d — Tema: %s", numero, total, tema)

    transcript = run_debate(tema)
    resultado = juzgar(tema, transcript)
    guardar(resultado, transcript)

    conclusion = resultado.get("conclusion", "Sin conclusión")
    conceptos = resultado.get("conceptos_clave_aprendidos", [])
    conceptos_txt = "\n".join(f"• {c}" for c in conceptos) if conceptos else "• (ninguno)"

    logger.info("Conclusión %d/%d: %s", numero, total, conclusion)

    _notify_telegram(
        f"*Debate nocturno {numero}/{total} completado* 🧠\n\n"
        f"*Tema:* {tema}\n\n"
        f"*Conceptos aprendidos:*\n{conceptos_txt}\n\n"
        f"*Veredicto:* {conclusion}"
    )


def run(cantidad: int = 3):
    """Corre `cantidad` conversaciones sintéticas en una sola ejecución nocturna.
    La primera siempre es sobre pumps/cripto/trades reales (forzado); el resto usa
    la selección de tema normal (que ya favorece cripto, pero es libre)."""
    import time

    logger.info("=== Debates sintéticos nocturnos (%d) ===", cantidad)

    if not is_online():
        logger.error("GPU node offline. Cancelando debates.")
        return

    for i in range(1, cantidad + 1):
        forzar_cripto = (i == 1)
        try:
            _ejecutar_una_conversacion(i, cantidad, forzar_cripto)
        except Exception as e:
            logger.error("Conversación %d/%d falló: %s", i, cantidad, e)

        if i < cantidad:
            time.sleep(60)  # pausa entre conversaciones para no saturar el proveedor cloud

    logger.info("=== Debates sintéticos completados (%d) ===", cantidad)


if __name__ == "__main__":
    run()
