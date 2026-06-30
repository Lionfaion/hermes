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
    # Trading
    "Análisis técnico vs análisis fundamental: qué predice mejor el corto plazo",
    "Gestión de riesgo en trading algorítmico: reglas que los profesionales usan",
    "Indicadores técnicos realmente útiles vs los que generan ruido",
    "Backtesting: errores comunes que invalidan los resultados",
    "Estrategias de scalping vs swing trading: ventajas y desventajas reales",
    # Diseño & Creatividad
    "Principios de diseño minimalista aplicados a interfaces de usuario",
    "Cómo la psicología del color afecta las decisiones en diseño de interiores",
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


def seleccionar_tema() -> str:
    """Pick topic from vault keywords or default list."""
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
    return random.choice(TEMAS)


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


def run():
    logger.info("=== Debate sintético nocturno ===")

    if not is_online():
        logger.error("GPU node offline. Cancelando debate.")
        return

    tema = seleccionar_tema()
    transcript = run_debate(tema)
    resultado = juzgar(tema, transcript)
    guardar(resultado, transcript)

    conclusion = resultado.get("conclusion", "Sin conclusión")
    conceptos = resultado.get("conceptos_clave_aprendidos", [])
    conceptos_txt = "\n".join(f"• {c}" for c in conceptos) if conceptos else "• (ninguno)"

    logger.info("Conclusión: %s", conclusion)
    logger.info("=== Debate completado ===")

    _notify_telegram(
        f"*Debate nocturno completado* 🧠\n\n"
        f"*Tema:* {tema}\n\n"
        f"*Conceptos aprendidos:*\n{conceptos_txt}\n\n"
        f"*Veredicto:* {conclusion}"
    )


if __name__ == "__main__":
    run()
