"""Autoreason: self-refinement that knows when to stop.

Inspired by NousResearch/autoreason. Generates 3 competing versions
of a response and uses blind judging to pick the best one.
"""

import logging
from dataclasses import dataclass, field

from inference_client import chat
from config import OLLAMA_MODEL

logger = logging.getLogger(__name__)


@dataclass
class ReasonResult:
    best_response: str
    method: str = ""
    scores: dict = field(default_factory=dict)
    improved: bool = False


def autoreason(
    prompt: str,
    system_prompt: str = "",
    model: str = "",
    num_judges: int = 3,
) -> ReasonResult:
    """Generate 3 competing versions and pick the best via blind judging.

    A (incumbent) = direct response
    B (adversarial) = revision of A by a fresh critic
    AB (synthesis) = merge of best parts of A and B
    """
    model = model or OLLAMA_MODEL

    sys_msg = system_prompt or "Sos un asistente experto. Respondé de forma clara, precisa y completa."

    # Version A: direct response (incumbent)
    response_a = chat(
        [{"role": "system", "content": sys_msg},
         {"role": "user", "content": prompt}],
        model,
    )

    # Version B: adversarial revision
    critic_prompt = (
        f"Analizá esta respuesta y generá una versión MEJORADA. "
        f"Corregí errores, agregá información faltante, mejorá la claridad.\n\n"
        f"PREGUNTA ORIGINAL:\n{prompt}\n\n"
        f"RESPUESTA A MEJORAR:\n{response_a}\n\n"
        f"Generá SOLO la respuesta mejorada, sin explicar qué cambiaste."
    )
    response_b = chat(
        [{"role": "system", "content": "Sos un editor experto. Mejorás textos sin perder la esencia."},
         {"role": "user", "content": critic_prompt}],
        model,
    )

    # Version AB: synthesis
    synthesis_prompt = (
        f"Tenés dos respuestas a la misma pregunta. Combiná lo mejor de ambas "
        f"en una respuesta definitiva superior.\n\n"
        f"PREGUNTA:\n{prompt}\n\n"
        f"RESPUESTA A:\n{response_a}\n\n"
        f"RESPUESTA B:\n{response_b}\n\n"
        f"Generá SOLO la respuesta final combinada."
    )
    response_ab = chat(
        [{"role": "system", "content": "Sos un sintetizador experto. Combinás ideas en la mejor versión posible."},
         {"role": "user", "content": synthesis_prompt}],
        model,
    )

    # Blind judging with Borda count
    candidates = {"A": response_a, "B": response_b, "AB": response_ab}
    borda_scores = {"A": 0, "B": 0, "AB": 0}

    for judge_id in range(num_judges):
        judge_prompt = (
            f"Sos un juez imparcial. Rankeá estas 3 respuestas de MEJOR a PEOR.\n\n"
            f"PREGUNTA:\n{prompt}\n\n"
            f"RESPUESTA 1:\n{response_a}\n\n"
            f"RESPUESTA 2:\n{response_b}\n\n"
            f"RESPUESTA 3:\n{response_ab}\n\n"
            f"Criterios: precisión, completitud, claridad, utilidad.\n"
            f"Respondé SOLO con el ranking, formato: mejor,segundo,peor\n"
            f"Ejemplo: 2,1,3"
        )
        ranking = chat(
            [{"role": "system", "content": f"Sos el juez #{judge_id + 1}. Evaluás de forma independiente y objetiva."},
             {"role": "user", "content": judge_prompt}],
            model,
        ).strip()

        # Parse ranking
        order = _parse_ranking(ranking)
        if order:
            labels = ["A", "B", "AB"]
            for rank, idx in enumerate(order):
                if 0 <= idx < 3:
                    borda_scores[labels[idx]] += (2 - rank)  # 2 for 1st, 1 for 2nd, 0 for 3rd

    # Select winner
    winner = max(borda_scores, key=borda_scores.get)

    return ReasonResult(
        best_response=candidates[winner],
        method=f"autoreason_{winner}",
        scores=borda_scores,
        improved=winner != "A",
    )


def _parse_ranking(text: str) -> list[int]:
    """Parse ranking like '2,1,3' into [1,0,2] (0-indexed)."""
    try:
        nums = []
        for c in text.replace(" ", ""):
            if c.isdigit():
                nums.append(int(c) - 1)
        if len(nums) >= 3 and all(0 <= n < 3 for n in nums[:3]):
            return nums[:3]
    except Exception:
        pass
    return []


def refine_text(
    text: str,
    context: str = "",
    text_type: str = "respuesta",
    model: str = "",
) -> str:
    """Shortcut: refine any text using autoreason."""
    prompt = f"Mejorá esta {text_type}:\n\n{text}"
    if context:
        prompt = f"Contexto: {context}\n\n{prompt}"

    result = autoreason(prompt, model=model)
    return result.best_response
