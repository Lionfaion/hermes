"""SEO Content Factory: keyword research + artículos + videos optimizados para SEO."""

import logging

logger = logging.getLogger(__name__)


def research_keywords(niche: str, count: int = 10) -> str:
    from web.search import web_search
    from inference_client import chat

    search_results = []
    queries = [
        f"{niche} preguntas frecuentes",
        f"{niche} guía completa",
        f"cómo {niche} principiantes",
        f"mejores {niche} 2025",
    ]

    for q in queries:
        try:
            results = web_search(q, max_results=5)
            for r in results:
                search_results.append(f"- {r.get('title', '')}: {r.get('body', r.get('snippet', ''))[:100]}")
        except Exception:
            pass

    prompt = (
        f"Basándote en estos resultados de búsqueda del nicho '{niche}':\n\n"
        + "\n".join(search_results[:20]) + "\n\n"
        f"Identificá {count} keywords de cola larga con potencial SEO.\n"
        "Para cada una incluí:\n"
        "- **Keyword**\n"
        "- **Intención de búsqueda** (informacional, transaccional, comparativa)\n"
        "- **Competencia estimada** (baja/media/alta)\n"
        "- **Título sugerido** para artículo\n"
        "- **Título de video** complementario\n"
    )

    messages = [
        {"role": "system", "content": "Sos un experto en SEO y content marketing. Respondé en español."},
        {"role": "user", "content": prompt},
    ]
    return chat(messages)


def generate_seo_article(keyword: str, word_count: int = 1500) -> str:
    from inference_client import chat

    prompt = (
        f"Escribí un artículo de blog optimizado para SEO sobre: **{keyword}**\n\n"
        f"Extensión: ~{word_count} palabras\n\n"
        "Requisitos SEO:\n"
        "- Título con la keyword principal (H1)\n"
        "- Meta description (150-160 chars)\n"
        "- Mínimo 5 subtítulos H2\n"
        "- Keyword density natural (2-3%)\n"
        "- Introducción que enganche en las primeras 2 líneas\n"
        "- Lista de puntos donde sea natural\n"
        "- Conclusión con CTA\n"
        "- Sugerencias de internal linking\n"
        "- Alt text sugerido para imágenes\n\n"
        "Formato: Markdown completo listo para publicar."
    )

    messages = [
        {"role": "system", "content": "Sos un redactor SEO experto. Escribís contenido que rankea. Respondé en español."},
        {"role": "user", "content": prompt},
    ]
    return chat(messages)


def generate_video_script_from_article(article: str, duration: int = 60) -> str:
    from inference_client import chat

    prompt = (
        f"Convertí este artículo de blog en un guión de video de {duration} segundos:\n\n"
        f"{article[:4000]}\n\n"
        "El guión debe:\n"
        "- Empezar con un hook impactante (3 segundos)\n"
        "- Resumir los puntos clave del artículo\n"
        "- Ser conversacional, no una lectura del artículo\n"
        "- Terminar con CTA: 'link en la descripción' + suscribirse\n"
        "- Incluir timestamps para cada sección\n"
    )

    messages = [
        {"role": "system", "content": "Sos un creador de contenido que convierte artículos en videos virales. Respondé en español."},
        {"role": "user", "content": prompt},
    ]
    return chat(messages)


def full_seo_pipeline(keyword: str) -> dict:
    article = generate_seo_article(keyword)
    video_script = generate_video_script_from_article(article)
    return {
        "keyword": keyword,
        "article": article,
        "video_script": video_script,
        "next_steps": (
            "1. Publicá el artículo en tu blog\n"
            "2. Usá generate_video con el guión para crear el video\n"
            "3. Publicá el video con publish_video\n"
            "4. Linkeá el video en el artículo y viceversa"
        ),
    }
