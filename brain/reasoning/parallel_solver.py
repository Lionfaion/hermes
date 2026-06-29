"""Parallel Solver: solve problems with multiple competing approaches.

Inspired by NousResearch/nomos.
Runs N parallel solution attempts with different strategies,
then merges or selects the best result.
"""

import logging
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field

from inference_client import chat
from config import OLLAMA_MODEL

logger = logging.getLogger(__name__)

SOLVER_STRATEGIES = {
    "direct": "Resolvé el problema de forma directa y eficiente.",
    "step_by_step": "Resolvé paso a paso, mostrando cada etapa del razonamiento.",
    "first_principles": "Descomponé el problema en principios fundamentales y construí la solución desde cero.",
    "analogical": "Buscá analogías con problemas conocidos y adaptá soluciones existentes.",
    "adversarial": "Intentá encontrar por qué la solución obvia está mal, luego proponé una mejor.",
    "constraint": "Identificá todas las restricciones del problema y resolé satisfaciéndolas una por una.",
}


@dataclass
class SolverResult:
    strategy: str
    response: str
    score: float = 0.0
    time_ms: float = 0.0


@dataclass
class ParallelResult:
    best: SolverResult
    all_results: list[SolverResult] = field(default_factory=list)
    merged: str = ""
    total_time_ms: float = 0.0


def parallel_solve(
    problem: str,
    strategies: list[str] = None,
    model: str = "",
    max_workers: int = 3,
    merge: bool = True,
) -> ParallelResult:
    """Solve a problem using multiple strategies in parallel."""
    model = model or OLLAMA_MODEL
    strategies = strategies or ["direct", "step_by_step", "first_principles"]
    start = time.perf_counter()

    results = []

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = {}
        for strategy in strategies:
            if strategy not in SOLVER_STRATEGIES:
                continue
            future = executor.submit(_solve_with_strategy, problem, strategy, model)
            futures[future] = strategy

        for future in as_completed(futures):
            strategy = futures[future]
            try:
                result = future.result()
                results.append(result)
            except Exception as e:
                logger.warning("Strategy %s failed: %s", strategy, e)

    if not results:
        fallback = _solve_with_strategy(problem, "direct", model)
        results.append(fallback)

    # Score all results
    scored = _score_results(problem, results, model)
    scored.sort(key=lambda r: r.score, reverse=True)
    best = scored[0]

    total_ms = (time.perf_counter() - start) * 1000

    parallel = ParallelResult(
        best=best,
        all_results=scored,
        total_time_ms=total_ms,
    )

    if merge and len(scored) > 1:
        parallel.merged = _merge_solutions(problem, scored[:3], model)

    return parallel


def _solve_with_strategy(problem: str, strategy: str, model: str) -> SolverResult:
    """Solve using a specific strategy."""
    start = time.perf_counter()
    instruction = SOLVER_STRATEGIES.get(strategy, SOLVER_STRATEGIES["direct"])

    response = chat(
        [{"role": "system", "content": f"Sos un experto en resolución de problemas. {instruction}"},
         {"role": "user", "content": problem}],
        model,
    )

    elapsed = (time.perf_counter() - start) * 1000
    return SolverResult(strategy=strategy, response=response, time_ms=elapsed)


def _score_results(problem: str, results: list[SolverResult], model: str) -> list[SolverResult]:
    """Score each result for quality."""
    if len(results) == 1:
        results[0].score = 7.0
        return results

    solutions_text = "\n\n".join(
        f"--- SOLUCIÓN {i + 1} ({r.strategy}) ---\n{r.response[:500]}"
        for i, r in enumerate(results)
    )

    msg = (
        f"Evaluá estas {len(results)} soluciones al mismo problema.\n\n"
        f"PROBLEMA:\n{problem[:500]}\n\n"
        f"SOLUCIONES:\n{solutions_text}\n\n"
        f"Para cada solución, asigná un puntaje del 1 al 10.\n"
        f"Respondé con los puntajes separados por coma. Ejemplo: 7,8,6"
    )

    response = chat(
        [{"role": "system", "content": "Sos un evaluador objetivo. Respondé solo con números separados por coma."},
         {"role": "user", "content": msg}],
        model,
    ).strip()

    scores = _parse_scores(response, len(results))
    for i, result in enumerate(results):
        result.score = scores[i] if i < len(scores) else 5.0

    return results


def _merge_solutions(problem: str, top_results: list[SolverResult], model: str) -> str:
    """Merge the best solutions into one superior answer."""
    solutions = "\n\n".join(
        f"--- {r.strategy} (score: {r.score:.1f}) ---\n{r.response[:800]}"
        for r in top_results
    )

    msg = (
        f"Combiná lo mejor de estas soluciones en UNA respuesta definitiva.\n\n"
        f"PROBLEMA:\n{problem[:500]}\n\n"
        f"SOLUCIONES:\n{solutions}\n\n"
        f"Generá SOLO la respuesta final combinada."
    )

    return chat(
        [{"role": "system", "content": "Sos un sintetizador experto. Combinás las mejores ideas en una respuesta superior."},
         {"role": "user", "content": msg}],
        model,
    )


def _parse_scores(text: str, expected: int) -> list[float]:
    """Parse comma-separated scores from LLM response."""
    scores = []
    for part in text.replace(" ", "").split(","):
        part = part.strip(".,;:!?")
        try:
            s = float(part)
            if 1 <= s <= 10:
                scores.append(s)
        except ValueError:
            continue
    while len(scores) < expected:
        scores.append(5.0)
    return scores
