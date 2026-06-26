"""Open Reasoning Tasks: curated reasoning challenges for self-improvement.

Inspired by NousResearch/Open-Reasoning-Tasks.
Provides reasoning exercises that an agent can use to practice and improve.
"""

import json
import logging
import random
from dataclasses import dataclass, field

from inference_client import chat
from config import OLLAMA_MODEL

logger = logging.getLogger(__name__)

TASK_CATEGORIES = [
    "logical_deduction",
    "mathematical_reasoning",
    "causal_reasoning",
    "analogical_reasoning",
    "spatial_reasoning",
    "temporal_reasoning",
    "counterfactual_thinking",
    "constraint_satisfaction",
    "pattern_recognition",
    "ethical_reasoning",
]

TASK_TEMPLATES = {
    "logical_deduction": [
        "Si todos los A son B, y algunos B son C, ¿qué podemos concluir sobre A y C?",
        "Tres personas dicen: P1 dice que P2 miente, P2 dice que P3 miente, P3 dice que P1 dice la verdad. ¿Quién miente?",
    ],
    "mathematical_reasoning": [
        "Un tanque se llena con dos canillas. La primera lo llena en {a} horas, la segunda en {b} horas. ¿Cuánto tardan juntas?",
        "Si duplico un número y le resto {a}, obtengo {b}. ¿Cuál es el número?",
    ],
    "causal_reasoning": [
        "Un servidor empezó a fallar después de una actualización. ¿Cuáles son las 3 causas más probables y cómo las diagnosticarías?",
        "Las ventas cayeron un {a}% este mes. Listá 5 posibles causas y cómo validar cada una.",
    ],
    "analogical_reasoning": [
        "CPU es a computadora como _____ es a célula. Explicá la analogía.",
        "Git es a código como _____ es a documentos legales. Proponé y justificá.",
    ],
    "constraint_satisfaction": [
        "Asigná {a} tareas a {b} personas sin que nadie tenga más de {c} tareas y respetando que las tareas dependientes no se asignen a la misma persona.",
        "Organizá un torneo de {a} equipos en {b} rondas donde cada equipo juega exactamente una vez por ronda.",
    ],
    "pattern_recognition": [
        "Continuá la secuencia: {seq}. Explicá el patrón.",
        "Encontrá el intruso: {items}. Justificá tu respuesta.",
    ],
}


@dataclass
class ReasoningTask:
    category: str
    prompt: str
    difficulty: str = "medium"  # easy, medium, hard
    expected_skills: list[str] = field(default_factory=list)


@dataclass
class TaskResult:
    task: ReasoningTask
    response: str
    score: float = 0.0
    feedback: str = ""
    passed: bool = False


def generate_task(
    category: str = "",
    difficulty: str = "medium",
    model: str = "",
) -> ReasoningTask:
    """Generate a reasoning task, either from templates or via LLM."""
    model = model or OLLAMA_MODEL
    category = category or random.choice(TASK_CATEGORIES)

    if category in TASK_TEMPLATES:
        template = random.choice(TASK_TEMPLATES[category])
        prompt = _fill_template(template)
        return ReasoningTask(category=category, prompt=prompt, difficulty=difficulty)

    gen_msg = (
        f"Generá un ejercicio de razonamiento de tipo '{category}' "
        f"con dificultad '{difficulty}'. "
        f"El ejercicio debe tener una respuesta correcta verificable. "
        f"Respondé SOLO con el enunciado del ejercicio, sin la respuesta."
    )
    prompt = chat(
        [{"role": "system", "content": "Generás ejercicios de razonamiento claros y precisos."},
         {"role": "user", "content": gen_msg}],
        model,
    ).strip()

    return ReasoningTask(category=category, prompt=prompt, difficulty=difficulty)


def evaluate_response(
    task: ReasoningTask,
    response: str,
    model: str = "",
) -> TaskResult:
    """Evaluate a response to a reasoning task."""
    model = model or OLLAMA_MODEL

    eval_msg = (
        f"Evaluá esta respuesta a un ejercicio de razonamiento.\n\n"
        f"CATEGORÍA: {task.category}\n"
        f"EJERCICIO:\n{task.prompt}\n\n"
        f"RESPUESTA:\n{response}\n\n"
        f"Evaluá del 1 al 10 considerando:\n"
        f"- Corrección lógica\n"
        f"- Completitud del razonamiento\n"
        f"- Claridad de la explicación\n\n"
        f'Respondé en JSON: {{"score": N, "feedback": "...", "passed": true/false}}'
    )

    eval_response = chat(
        [{"role": "system", "content": "Sos un evaluador de razonamiento. Respondés en JSON."},
         {"role": "user", "content": eval_msg}],
        model,
    ).strip()

    score, feedback, passed = _parse_evaluation(eval_response)

    return TaskResult(
        task=task,
        response=response,
        score=score,
        feedback=feedback,
        passed=passed,
    )


def practice_session(
    num_tasks: int = 3,
    categories: list[str] = None,
    model: str = "",
) -> list[TaskResult]:
    """Run a practice session: generate tasks, solve them, evaluate."""
    model = model or OLLAMA_MODEL
    categories = categories or random.sample(TASK_CATEGORIES, min(num_tasks, len(TASK_CATEGORIES)))
    results = []

    for i in range(num_tasks):
        cat = categories[i % len(categories)]
        task = generate_task(category=cat, model=model)

        response = chat(
            [{"role": "system", "content": "Resolvé el ejercicio paso a paso, mostrando tu razonamiento."},
             {"role": "user", "content": task.prompt}],
            model,
        )

        result = evaluate_response(task, response, model=model)
        results.append(result)
        logger.info("Task %d/%d [%s]: score=%.1f passed=%s", i + 1, num_tasks, cat, result.score, result.passed)

    return results


def _fill_template(template: str) -> str:
    """Fill numeric placeholders in templates."""
    replacements = {
        "{a}": str(random.randint(2, 12)),
        "{b}": str(random.randint(2, 12)),
        "{c}": str(random.randint(2, 5)),
        "{seq}": ", ".join(str(x) for x in _random_sequence()),
        "{items}": ", ".join(_random_items()),
    }
    for k, v in replacements.items():
        template = template.replace(k, v)
    return template


def _random_sequence() -> list[int]:
    """Generate a sequence with a pattern."""
    patterns = [
        lambda i: 2 ** i,
        lambda i: i * 3 + 1,
        lambda i: i ** 2,
        lambda i: (i + 1) * (i + 2) // 2,
    ]
    fn = random.choice(patterns)
    return [fn(i) for i in range(5)] + ["..."]


def _random_items() -> list[str]:
    """Generate items with one outlier."""
    groups = [
        (["Python", "Java", "Rust", "Go"], "PostgreSQL"),
        (["TCP", "UDP", "HTTP", "FTP"], "RAM"),
        (["Git", "SVN", "Mercurial", "Perforce"], "Docker"),
    ]
    items, outlier = random.choice(groups)
    result = items + [outlier]
    random.shuffle(result)
    return result


def _parse_evaluation(text: str) -> tuple[float, str, bool]:
    """Parse evaluation JSON from LLM."""
    try:
        start = text.find("{")
        end = text.rfind("}")
        if start >= 0 and end > start:
            data = json.loads(text[start:end + 1])
            return (
                float(data.get("score", 5)),
                data.get("feedback", ""),
                bool(data.get("passed", False)),
            )
    except Exception:
        pass
    return 5.0, "", False
