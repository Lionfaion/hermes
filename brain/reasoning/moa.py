"""Mixture-of-Agents (MoA): fan-out to multiple model personas for high-stakes decisions.

Inspired by NousResearch/hermes-agent MoA pattern.
Sends the same query to multiple "reference" perspectives in parallel,
aggregates their advice, then synthesizes a superior final response.
"""

import logging
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field

from inference_client import chat
from config import OLLAMA_MODEL

logger = logging.getLogger(__name__)

REFERENCE_PERSONAS = {
    "pragmatist": "Sos un pragmatista. Priorizás soluciones prácticas, implementables y con ROI claro. Evitás over-engineering.",
    "critic": "Sos un crítico constructivo. Buscás debilidades, riesgos y edge cases. Cuestionás supuestos.",
    "innovator": "Sos un innovador. Proponés soluciones creativas y no convencionales. Pensás fuera de la caja.",
    "analyst": "Sos un analista riguroso. Te basás en datos, evidencia y lógica formal. Cuantificás todo lo posible.",
    "user_advocate": "Sos un defensor del usuario. Priorizás UX, accesibilidad y simplicidad. Todo debe ser intuitivo.",
}


@dataclass
class MoAResult:
    final_response: str
    perspectives: dict[str, str] = field(default_factory=dict)
    synthesis_method: str = "aggregate"
    num_perspectives: int = 0


def mixture_of_agents(
    query: str,
    system_prompt: str = "",
    perspectives: list[str] = None,
    model: str = "",
    max_workers: int = 3,
) -> MoAResult:
    """Fan-out query to multiple perspectives, then synthesize.

    Args:
        query: The question or task
        system_prompt: Base system prompt (combined with each persona)
        perspectives: Which personas to use (default: pragmatist, critic, analyst)
        model: LLM model to use
        max_workers: Parallel workers
    """
    model = model or OLLAMA_MODEL
    perspectives = perspectives or ["pragmatist", "critic", "analyst"]

    # Stage 1: Fan-out to reference models
    responses = {}
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = {}
        for persona_name in perspectives:
            if persona_name not in REFERENCE_PERSONAS:
                continue
            persona_prompt = REFERENCE_PERSONAS[persona_name]
            combined_system = f"{system_prompt}\n\n{persona_prompt}" if system_prompt else persona_prompt

            future = executor.submit(
                chat,
                [{"role": "system", "content": combined_system},
                 {"role": "user", "content": query}],
                model,
            )
            futures[future] = persona_name

        for future in as_completed(futures):
            persona_name = futures[future]
            try:
                responses[persona_name] = future.result()
            except Exception as e:
                logger.warning("MoA perspective '%s' failed: %s", persona_name, e)
                responses[persona_name] = f"[Error: {e}]"

    if not responses:
        direct = chat(
            [{"role": "system", "content": system_prompt or "Respondé de forma clara y útil."},
             {"role": "user", "content": query}],
            model,
        )
        return MoAResult(final_response=direct, num_perspectives=0)

    # Stage 2: Synthesize
    perspectives_text = "\n\n".join(
        f"### Perspectiva {name.upper()}:\n{response[:800]}"
        for name, response in responses.items()
    )

    synthesis_prompt = (
        f"Tenés múltiples perspectivas de expertos sobre la misma consulta. "
        f"Sintetizá la MEJOR respuesta posible combinando los puntos fuertes de cada una.\n\n"
        f"CONSULTA ORIGINAL:\n{query}\n\n"
        f"PERSPECTIVAS:\n{perspectives_text}\n\n"
        f"Generá una respuesta final que:\n"
        f"1. Integre los mejores insights de cada perspectiva\n"
        f"2. Resuelva contradicciones entre ellas\n"
        f"3. Sea accionable y completa\n\n"
        f"Respondé SOLO con la respuesta final sintetizada."
    )

    final = chat(
        [{"role": "system", "content": "Sos un sintetizador experto. Combinás múltiples perspectivas en una respuesta superior."},
         {"role": "user", "content": synthesis_prompt}],
        model,
    )

    return MoAResult(
        final_response=final,
        perspectives=responses,
        synthesis_method="aggregate",
        num_perspectives=len(responses),
    )


def get_available_perspectives() -> dict[str, str]:
    """List available MoA perspectives."""
    return {k: v[:80] for k, v in REFERENCE_PERSONAS.items()}
