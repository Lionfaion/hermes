"""Course Factory: genera cursos/info-productos completos automáticamente."""

import logging

logger = logging.getLogger(__name__)


def research_course_market(topic: str) -> str:
    from web.search import web_search
    from inference_client import chat

    results = web_search(f"curso online {topic} precio udemy hotmart", max_results=10)
    market_text = "\n".join(
        f"- {r.get('title', '')}: {r.get('body', r.get('snippet', ''))[:150]}"
        for r in results
    )

    prompt = (
        f"Investigá el mercado de cursos online sobre '{topic}':\n\n"
        f"**Resultados de búsqueda:**\n{market_text}\n\n"
        "Analizá:\n"
        "- **Demanda:** ¿la gente busca esto?\n"
        "- **Competencia:** ¿cuántos cursos hay? ¿Rango de precios?\n"
        "- **Gaps:** ¿qué NO están cubriendo los cursos existentes?\n"
        "- **Ángulo diferenciador:** ¿cómo puedo hacer uno mejor/distinto?\n"
        "- **Precio sugerido:** basado en el mercado\n"
        "- **Plataforma recomendada:** Hotmart, Udemy, propio, etc\n"
    )

    messages = [
        {"role": "system", "content": "Sos un experto en info-productos y cursos online. Respondé en español."},
        {"role": "user", "content": prompt},
    ]
    return chat(messages)


def generate_course_structure(topic: str, level: str = "principiante a intermedio", duration_hours: int = 5) -> str:
    from inference_client import chat

    prompt = (
        f"Diseñá la estructura completa de un curso online:\n\n"
        f"**Tema:** {topic}\n"
        f"**Nivel:** {level}\n"
        f"**Duración total:** {duration_hours} horas\n\n"
        "Generá:\n"
        "1. **Nombre del curso** (atractivo y claro)\n"
        "2. **Descripción** (para la página de venta, 200 palabras)\n"
        "3. **Módulos** (4-8 módulos)\n"
        "4. **Lecciones por módulo** (3-5 lecciones cada uno)\n"
        "   - Título de la lección\n"
        "   - Duración estimada\n"
        "   - Tipo (video, ejercicio, quiz, descargable)\n"
        "   - Resumen de 1 línea\n"
        "5. **Bonus** sugeridos\n"
        "6. **Requisitos previos**\n"
        "7. **Resultados prometidos** (qué va a saber/poder hacer el alumno)\n"
    )

    messages = [
        {"role": "system", "content": "Sos un instructional designer experto. Respondé en español."},
        {"role": "user", "content": prompt},
    ]
    return chat(messages)


def generate_lesson_script(lesson_title: str, lesson_topic: str, duration_minutes: int = 10) -> str:
    from inference_client import chat

    prompt = (
        f"Escribí el guión completo para esta lección de curso:\n\n"
        f"**Título:** {lesson_title}\n"
        f"**Tema:** {lesson_topic}\n"
        f"**Duración:** {duration_minutes} minutos\n\n"
        "El guión debe:\n"
        "- Empezar con lo que van a aprender\n"
        "- Explicar con ejemplos concretos\n"
        "- Incluir pasos prácticos\n"
        "- Ser conversacional (no leer un libro)\n"
        "- Terminar con resumen + preview de la siguiente lección\n"
        "- Incluir [SLIDE] markers donde iría un cambio de diapositiva\n"
        "- Incluir [DEMO] markers donde haría una demostración\n"
    )

    messages = [
        {"role": "system", "content": "Sos un instructor online carismático. Respondé en español."},
        {"role": "user", "content": prompt},
    ]
    return chat(messages)


def generate_sales_page(course_name: str, description: str, price: str, target: str = "") -> str:
    from inference_client import chat

    prompt = (
        f"Escribí el copy para la página de venta de este curso:\n\n"
        f"**Curso:** {course_name}\n"
        f"**Descripción:** {description}\n"
        f"**Precio:** {price}\n"
        f"**Target:** {target or 'Profesionales que quieren aprender ' + course_name}\n\n"
        "Estructura:\n"
        "1. **Headline** impactante\n"
        "2. **Subheadline** con la promesa\n"
        "3. **Problema** que resuelve (pain points)\n"
        "4. **Solución** (el curso)\n"
        "5. **Qué incluye** (módulos + bonus)\n"
        "6. **Testimonios** (placeholder)\n"
        "7. **Precio** con anclaje\n"
        "8. **Garantía**\n"
        "9. **FAQ** (5 preguntas)\n"
        "10. **CTA final**\n"
    )

    messages = [
        {"role": "system", "content": "Sos un copywriter de ventas experto en info-productos. Respondé en español."},
        {"role": "user", "content": prompt},
    ]
    return chat(messages)
