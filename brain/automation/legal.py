"""Legal Assistant: análisis de contratos y generación de documentos legales."""

import logging

logger = logging.getLogger(__name__)


def analyze_contract(contract_text: str) -> str:
    from inference_client import chat

    prompt = (
        "Analizá este contrato/documento legal:\n\n"
        f"{contract_text[:8000]}\n\n"
        "Respondé con:\n"
        "1. **Resumen general** (qué tipo de contrato es, partes involucradas)\n"
        "2. **Puntos clave** (obligaciones principales de cada parte)\n"
        "3. **Cláusulas de riesgo** (penalidades, exclusividad, no competencia, etc)\n"
        "4. **Plazos importantes** (vigencia, renovación, preaviso)\n"
        "5. **Cláusulas faltantes** (qué debería tener y no tiene)\n"
        "6. **Recomendaciones** (qué negociar, qué modificar)\n"
        "7. **Nivel de riesgo general** (bajo/medio/alto)\n\n"
        "NOTA: Esto es un análisis informativo, NO constituye asesoría legal profesional."
    )

    messages = [
        {"role": "system", "content": (
            "Sos un asistente legal que analiza contratos de forma clara y accesible. "
            "Siempre aclarás que no reemplaza a un abogado. Respondé en español."
        )},
        {"role": "user", "content": prompt},
    ]
    return chat(messages)


def generate_contract(
    contract_type: str,
    parties: str,
    key_terms: str = "",
    duration: str = "",
) -> str:
    from inference_client import chat

    prompt = (
        f"Generá un borrador de contrato:\n\n"
        f"**Tipo:** {contract_type}\n"
        f"**Partes:** {parties}\n"
        f"**Términos clave:** {key_terms or 'Estándar'}\n"
        f"**Duración:** {duration or 'A definir'}\n\n"
        "Incluí:\n"
        "- Encabezado con datos de las partes\n"
        "- Objeto del contrato\n"
        "- Obligaciones de cada parte\n"
        "- Condiciones de pago (si aplica)\n"
        "- Confidencialidad\n"
        "- Resolución de conflictos\n"
        "- Vigencia y terminación\n"
        "- Firma de las partes\n\n"
        "NOTA: Este es un borrador modelo. Debe ser revisado por un abogado antes de firmar."
    )

    messages = [
        {"role": "system", "content": "Sos un asistente legal. Generás borradores claros. Respondé en español."},
        {"role": "user", "content": prompt},
    ]
    return chat(messages)


def compare_contracts(contract_a: str, contract_b: str) -> str:
    from inference_client import chat

    prompt = (
        "Compará estos dos contratos/versiones:\n\n"
        f"**CONTRATO A:**\n{contract_a[:4000]}\n\n"
        f"**CONTRATO B:**\n{contract_b[:4000]}\n\n"
        "Identificá:\n"
        "- **Diferencias clave** entre ambos\n"
        "- **Qué se agregó** en B vs A\n"
        "- **Qué se eliminó** en B vs A\n"
        "- **Cambios en términos** (montos, plazos, condiciones)\n"
        "- **Cuál es más favorable** y para quién\n"
    )

    messages = [
        {"role": "system", "content": "Sos un analista legal comparativo. Respondé en español."},
        {"role": "user", "content": prompt},
    ]
    return chat(messages)


def generate_counter_proposal(original_terms: str, desired_changes: str) -> str:
    from inference_client import chat

    prompt = (
        f"Generá una contra-propuesta para estos términos:\n\n"
        f"**Términos originales:** {original_terms}\n"
        f"**Cambios deseados:** {desired_changes}\n\n"
        "La contra-propuesta debe:\n"
        "- Ser profesional y respetuosa\n"
        "- Justificar cada cambio solicitado\n"
        "- Ofrecer alternativas donde sea posible\n"
        "- Mantener un tono de negociación win-win\n"
    )

    messages = [
        {"role": "system", "content": "Sos un negociador profesional. Respondé en español."},
        {"role": "user", "content": prompt},
    ]
    return chat(messages)
