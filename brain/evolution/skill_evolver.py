"""Skill self-evolution: prompts and agent profiles improve from experience.

Inspired by NousResearch/hermes-agent-self-evolution.
Uses execution traces to understand WHY things fail and proposes targeted improvements.
"""

import json
import logging
import sqlite3
import time
from dataclasses import dataclass, field
from pathlib import Path

from inference_client import chat
from config import OLLAMA_MODEL, DB_PATH

logger = logging.getLogger(__name__)


@dataclass
class EvolutionResult:
    improved: bool
    original: str
    evolved: str
    score_before: float = 0.0
    score_after: float = 0.0
    generation: int = 0
    changes_summary: str = ""


def _init_db():
    conn = sqlite3.connect(str(DB_PATH))
    conn.execute("""
        CREATE TABLE IF NOT EXISTS evolution_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            target_type TEXT NOT NULL,
            target_name TEXT NOT NULL,
            generation INTEGER DEFAULT 0,
            original TEXT,
            evolved TEXT,
            score_before REAL,
            score_after REAL,
            changes TEXT,
            created_at REAL
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS execution_traces (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            agent_name TEXT,
            tool_name TEXT,
            input_summary TEXT,
            output_summary TEXT,
            success INTEGER,
            error TEXT,
            duration_ms REAL,
            created_at REAL
        )
    """)
    conn.commit()
    return conn


def log_execution_trace(
    agent_name: str = "",
    tool_name: str = "",
    input_summary: str = "",
    output_summary: str = "",
    success: bool = True,
    error: str = "",
    duration_ms: float = 0.0,
):
    """Log a tool execution for future evolution analysis."""
    try:
        conn = _init_db()
        conn.execute(
            "INSERT INTO execution_traces (agent_name, tool_name, input_summary, output_summary, success, error, duration_ms, created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (agent_name, tool_name, input_summary[:500], output_summary[:500], int(success), error[:200], duration_ms, time.time()),
        )
        conn.commit()
        conn.close()
    except Exception as e:
        logger.debug("Error logging trace: %s", e)


def evolve_prompt(
    prompt_name: str,
    current_prompt: str,
    context: str = "",
    iterations: int = 3,
    model: str = "",
) -> EvolutionResult:
    """Evolve a system prompt using execution traces and LLM evaluation."""
    model = model or OLLAMA_MODEL

    # Get recent traces for context
    traces = _get_recent_traces(prompt_name, limit=20)
    trace_context = _format_traces(traces) if traces else "No hay trazas de ejecución recientes."

    # Score original
    score_before = _evaluate_prompt(current_prompt, prompt_name, context, model)

    best_prompt = current_prompt
    best_score = score_before
    generation = 0

    for i in range(iterations):
        # Generate mutation
        mutate_msg = (
            f"Sos un optimizador de prompts de IA. Analizá este system prompt y mejoralo.\n\n"
            f"PROMPT ACTUAL ({prompt_name}):\n{best_prompt}\n\n"
            f"TRAZAS DE EJECUCIÓN RECIENTES:\n{trace_context}\n\n"
            f"CONTEXTO ADICIONAL:\n{context or 'Ninguno'}\n\n"
            f"Analizá los patrones de éxito/fallo en las trazas y proponé una versión mejorada "
            f"del prompt. Mantené la esencia pero optimizá para mejores resultados.\n\n"
            f"Respondé SOLO con el nuevo prompt, sin explicaciones."
        )

        candidate = chat(
            [{"role": "system", "content": "Sos un experto en prompt engineering. Optimizás prompts para máximo rendimiento."},
             {"role": "user", "content": mutate_msg}],
            model,
        ).strip()

        if not candidate or len(candidate) < 20:
            continue

        score = _evaluate_prompt(candidate, prompt_name, context, model)

        if score > best_score:
            best_prompt = candidate
            best_score = score
            generation = i + 1

    improved = best_score > score_before and best_prompt != current_prompt

    result = EvolutionResult(
        improved=improved,
        original=current_prompt,
        evolved=best_prompt if improved else current_prompt,
        score_before=score_before,
        score_after=best_score,
        generation=generation,
    )

    if improved:
        result.changes_summary = _summarize_changes(current_prompt, best_prompt, model)
        _save_evolution(prompt_name, result)

    return result


def _evaluate_prompt(prompt: str, name: str, context: str, model: str) -> float:
    """Score a prompt on clarity, specificity, and effectiveness."""
    eval_msg = (
        f"Evaluá este system prompt del 1 al 10 en estos criterios:\n"
        f"- Claridad de instrucciones (1-10)\n"
        f"- Especificidad de la tarea (1-10)\n"
        f"- Probabilidad de generar buenos resultados (1-10)\n\n"
        f"PROMPT ({name}):\n{prompt}\n\n"
        f"Respondé SOLO con un número del 1 al 10 (promedio de los 3 criterios)."
    )

    response = chat(
        [{"role": "system", "content": "Sos un evaluador de prompts. Respondé solo con un número."},
         {"role": "user", "content": eval_msg}],
        model,
    ).strip()

    try:
        for word in response.split():
            word = word.strip(".,;:!?")
            if word.replace(".", "").isdigit():
                score = float(word)
                if 1 <= score <= 10:
                    return score
    except Exception:
        pass
    return 5.0


def _summarize_changes(original: str, evolved: str, model: str) -> str:
    msg = (
        f"Resumí en 1-2 oraciones qué cambió entre estos dos prompts:\n\n"
        f"ORIGINAL:\n{original[:300]}\n\nEVOLUCIONADO:\n{evolved[:300]}"
    )
    return chat(
        [{"role": "user", "content": msg}],
        model,
    ).strip()


def _get_recent_traces(name: str, limit: int = 20) -> list[dict]:
    try:
        conn = _init_db()
        cursor = conn.execute(
            "SELECT agent_name, tool_name, input_summary, output_summary, success, error, duration_ms "
            "FROM execution_traces ORDER BY created_at DESC LIMIT ?",
            (limit,),
        )
        rows = cursor.fetchall()
        conn.close()
        return [
            {"agent": r[0], "tool": r[1], "input": r[2], "output": r[3],
             "success": bool(r[4]), "error": r[5], "ms": r[6]}
            for r in rows
        ]
    except Exception:
        return []


def _format_traces(traces: list[dict]) -> str:
    lines = []
    for t in traces[:10]:
        status = "OK" if t["success"] else f"FAIL: {t['error']}"
        lines.append(f"- [{status}] {t['tool']} ({t['ms']:.0f}ms): {t['input'][:80]}")
    return "\n".join(lines) if lines else "Sin trazas"


def _save_evolution(name: str, result: EvolutionResult):
    try:
        conn = _init_db()
        conn.execute(
            "INSERT INTO evolution_log (target_type, target_name, generation, original, evolved, score_before, score_after, changes, created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            ("prompt", name, result.generation, result.original[:2000], result.evolved[:2000],
             result.score_before, result.score_after, result.changes_summary, time.time()),
        )
        conn.commit()
        conn.close()
    except Exception as e:
        logger.debug("Error saving evolution: %s", e)
