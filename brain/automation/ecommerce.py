"""Ecommerce Product Research: analiza tendencias de productos y oportunidades."""

import logging

logger = logging.getLogger(__name__)


def research_products(niche: str, marketplace: str = "mercadolibre", count: int = 10) -> str:
    from web.search import web_search
    from inference_client import chat

    queries = [
        f"{niche} más vendidos {marketplace} 2025",
        f"{niche} tendencia producto dropshipping",
        f"best selling {niche} products trending",
        f"{niche} producto viral redes sociales",
    ]

    results_text = []
    for q in queries:
        try:
            results = web_search(q, max_results=5)
            for r in results:
                results_text.append(f"- {r.get('title', '')}: {r.get('body', r.get('snippet', ''))[:150]}")
        except Exception:
            pass

    prompt = (
        f"Basándote en esta investigación de mercado del nicho '{niche}':\n\n"
        + "\n".join(results_text[:20]) + "\n\n"
        f"Identificá los {count} productos con mayor potencial.\n"
        "Para cada producto:\n"
        "- **Producto:** nombre\n"
        "- **Rango de precio:** estimado\n"
        "- **Demanda:** alta/media/baja\n"
        "- **Competencia:** alta/media/baja\n"
        "- **Margen estimado:** %\n"
        "- **Plataformas ideales:** dónde vender\n"
        "- **Estrategia de marketing:** cómo promocionarlo\n"
    )

    messages = [
        {"role": "system", "content": "Sos un experto en ecommerce y dropshipping. Respondé en español con datos concretos."},
        {"role": "user", "content": prompt},
    ]
    return chat(messages)


def generate_product_listing(product_name: str, features: str = "", target: str = "") -> str:
    from inference_client import chat

    prompt = (
        f"Generá un listing completo para vender este producto:\n\n"
        f"**Producto:** {product_name}\n"
        f"**Características:** {features or 'A determinar'}\n"
        f"**Target:** {target or 'General'}\n\n"
        "Generá:\n"
        "1. **Título optimizado** para marketplace (MercadoLibre/Amazon style)\n"
        "2. **Descripción larga** (features + beneficios, 300 palabras)\n"
        "3. **Bullet points** (5 puntos clave)\n"
        "4. **Descripción corta** para redes sociales (150 chars)\n"
        "5. **Hashtags** relevantes\n"
        "6. **Keywords** para SEO del listing\n"
    )

    messages = [
        {"role": "system", "content": "Sos un copywriter especializado en ecommerce. Respondé en español."},
        {"role": "user", "content": prompt},
    ]
    return chat(messages)


def analyze_competition(product: str, marketplace: str = "") -> str:
    from web.search import web_search
    from inference_client import chat

    results = web_search(f"{product} {marketplace} precio envío", max_results=10)
    results_text = "\n".join(
        f"- {r.get('title', '')}: {r.get('body', r.get('snippet', ''))[:150]}"
        for r in results
    )

    prompt = (
        f"Analizá la competencia para este producto:\n\n"
        f"**Producto:** {product}\n"
        f"**Marketplace:** {marketplace or 'General'}\n\n"
        f"**Resultados de búsqueda:**\n{results_text}\n\n"
        "Analizá:\n"
        "- Rango de precios de la competencia\n"
        "- Puntos débiles que puedo explotar\n"
        "- Diferenciadores posibles\n"
        "- Estrategia de pricing recomendada\n"
        "- Oportunidad general (1-10)\n"
    )

    messages = [
        {"role": "system", "content": "Sos un analista de mercado ecommerce. Sé objetivo y basate en datos."},
        {"role": "user", "content": prompt},
    ]
    return chat(messages)
