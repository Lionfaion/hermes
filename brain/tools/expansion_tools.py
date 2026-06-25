"""Herramientas de expansión: lead gen, freelance, SEO, ecommerce, market, courses, meetings, reputation, legal, CRM."""

from tools.base import BaseTool


class LeadGenTool(BaseTool):
    name = "lead_gen"
    description = (
        "Busca leads/prospectos por industria y genera emails de outreach personalizados. "
        "Ideal para prospección B2B automatizada."
    )
    parameters = {
        "type": "object",
        "properties": {
            "action": {
                "type": "string",
                "description": "search (buscar leads), outreach (generar email), list (ver leads guardados)",
                "enum": ["search", "outreach", "list"],
            },
            "industry": {"type": "string", "description": "Industria para buscar leads"},
            "location": {"type": "string", "description": "Ubicación geográfica"},
            "product_service": {"type": "string", "description": "Lo que ofrecés (para outreach)"},
            "count": {"type": "integer", "description": "Cantidad de leads (default: 10)"},
        },
        "required": ["action"],
    }

    def execute(self, action: str, industry: str = "", location: str = "", product_service: str = "", count: int = 10) -> str:
        from automation.lead_gen import search_leads, generate_outreach, get_leads, save_lead
        import json

        if action == "search":
            if not industry:
                return "Necesito la industria para buscar leads."
            leads = search_leads(industry, location, count)
            for l in leads:
                save_lead(l)
            lines = [f"**{len(leads)} leads encontrados en '{industry}':**\n"]
            for i, l in enumerate(leads):
                lines.append(f"{i+1}. **{l['title'][:80]}**\n   {l['snippet'][:120]}")
            return "\n".join(lines)

        elif action == "outreach":
            leads = get_leads(status="new", industry=industry)
            if not leads:
                return "No hay leads nuevos. Buscá primero con action=search."
            lead = leads[0]
            return generate_outreach(lead, product_service or "mis servicios")

        elif action == "list":
            leads = get_leads(industry=industry)
            if not leads:
                return "No hay leads guardados."
            return f"**{len(leads)} leads:**\n" + "\n".join(f"- {l['title'][:80]} ({l['status']})" for l in leads[-20:])

        return "Acción no reconocida."


class FreelanceTool(BaseTool):
    name = "freelance"
    description = (
        "Busca trabajos freelance, analiza fit y genera propuestas ganadoras. "
        "Autopilot para encontrar oportunidades."
    )
    parameters = {
        "type": "object",
        "properties": {
            "action": {
                "type": "string",
                "description": "search (buscar trabajos), proposal (generar propuesta), analyze (analizar fit)",
                "enum": ["search", "proposal", "analyze"],
            },
            "skills": {"type": "string", "description": "Tus habilidades/especialidad"},
            "experience": {"type": "string", "description": "Tu experiencia relevante"},
            "rate": {"type": "string", "description": "Tu tarifa"},
        },
        "required": ["action", "skills"],
    }

    def execute(self, action: str, skills: str, experience: str = "", rate: str = "") -> str:
        from automation.freelance import search_freelance_jobs, generate_proposal, analyze_job_fit

        if action == "search":
            jobs = search_freelance_jobs(skills)
            if not jobs:
                return "No se encontraron trabajos."
            lines = [f"**Trabajos freelance para '{skills}':**\n"]
            for i, j in enumerate(jobs[:10]):
                lines.append(f"{i+1}. **{j['title'][:80]}**\n   {j['description'][:120]}")
            return "\n".join(lines)

        elif action == "proposal":
            jobs = search_freelance_jobs(skills, max_results=3)
            if not jobs:
                return "No se encontraron trabajos para generar propuesta."
            return generate_proposal(jobs[0], skills, experience, rate)

        elif action == "analyze":
            jobs = search_freelance_jobs(skills, max_results=3)
            if not jobs:
                return "No se encontraron trabajos para analizar."
            return analyze_job_fit(jobs[0], skills)

        return "Acción no reconocida."


class SEOTool(BaseTool):
    name = "seo_factory"
    description = (
        "Fábrica de contenido SEO: keyword research, artículos optimizados, "
        "y guiones de video complementarios. Pipeline completo de blog a video."
    )
    parameters = {
        "type": "object",
        "properties": {
            "action": {
                "type": "string",
                "description": "keywords (research), article (generar artículo), pipeline (artículo + video completo)",
                "enum": ["keywords", "article", "pipeline"],
            },
            "keyword": {"type": "string", "description": "Keyword o nicho para el contenido"},
            "word_count": {"type": "integer", "description": "Palabras del artículo (default: 1500)"},
        },
        "required": ["action", "keyword"],
    }

    def execute(self, action: str, keyword: str, word_count: int = 1500) -> str:
        from automation.seo_factory import research_keywords, generate_seo_article, full_seo_pipeline

        if action == "keywords":
            return research_keywords(keyword)
        elif action == "article":
            return generate_seo_article(keyword, word_count)
        elif action == "pipeline":
            result = full_seo_pipeline(keyword)
            return f"**Artículo:**\n{result['article'][:2000]}...\n\n**Guión de video:**\n{result['video_script']}\n\n**Próximos pasos:**\n{result['next_steps']}"
        return "Acción no reconocida."


class EcommerceTool(BaseTool):
    name = "ecommerce"
    description = (
        "Investigación de productos para ecommerce/dropshipping. "
        "Busca tendencias, genera listings y analiza competencia."
    )
    parameters = {
        "type": "object",
        "properties": {
            "action": {
                "type": "string",
                "description": "research (investigar productos), listing (generar listing), competition (analizar competencia)",
                "enum": ["research", "listing", "competition"],
            },
            "product": {"type": "string", "description": "Producto o nicho"},
            "marketplace": {"type": "string", "description": "Marketplace (mercadolibre, amazon, etc)"},
            "features": {"type": "string", "description": "Características del producto (para listing)"},
        },
        "required": ["action", "product"],
    }

    def execute(self, action: str, product: str, marketplace: str = "", features: str = "") -> str:
        from automation.ecommerce import research_products, generate_product_listing, analyze_competition

        if action == "research":
            return research_products(product, marketplace)
        elif action == "listing":
            return generate_product_listing(product, features)
        elif action == "competition":
            return analyze_competition(product, marketplace)
        return "Acción no reconocida."


class MarketMonitorTool(BaseTool):
    name = "market_monitor"
    description = (
        "Monitor de mercados: crypto, acciones, commodities. "
        "Watchlist, alertas, análisis de sentimiento."
    )
    parameters = {
        "type": "object",
        "properties": {
            "action": {
                "type": "string",
                "description": "check (analizar asset), scan (escanear watchlist), add (agregar a watchlist), remove (quitar), list (ver watchlist)",
                "enum": ["check", "scan", "add", "remove", "list"],
            },
            "asset": {"type": "string", "description": "Nombre del asset (bitcoin, ethereum, AAPL, etc)"},
            "asset_type": {"type": "string", "description": "Tipo: crypto, stock, commodity"},
        },
        "required": ["action"],
    }

    def execute(self, action: str, asset: str = "", asset_type: str = "crypto") -> str:
        from automation.market_monitor import check_market, scan_watchlist, add_to_watchlist, remove_from_watchlist, get_watchlist

        if action == "check":
            if not asset:
                return "Necesito el nombre del asset."
            return check_market(asset)
        elif action == "scan":
            return scan_watchlist()
        elif action == "add":
            if not asset:
                return "Necesito el nombre del asset."
            add_to_watchlist(asset, asset_type)
            return f"**{asset}** agregado a watchlist."
        elif action == "remove":
            if not asset:
                return "Necesito el nombre del asset."
            remove_from_watchlist(asset)
            return f"**{asset}** removido de watchlist."
        elif action == "list":
            wl = get_watchlist()
            if not wl:
                return "Watchlist vacía."
            return "**Watchlist:**\n" + "\n".join(f"- {w['asset']} ({w['type']})" for w in wl)
        return "Acción no reconocida."


class CourseFactoryTool(BaseTool):
    name = "course_factory"
    description = (
        "Generador de cursos online/info-productos. Investiga mercado, "
        "crea estructura, genera guiones de lecciones y sales pages."
    )
    parameters = {
        "type": "object",
        "properties": {
            "action": {
                "type": "string",
                "description": "research (mercado), structure (estructura), lesson (guión), sales_page (página de venta)",
                "enum": ["research", "structure", "lesson", "sales_page"],
            },
            "topic": {"type": "string", "description": "Tema del curso"},
            "lesson_title": {"type": "string", "description": "Título de la lección (para action=lesson)"},
            "price": {"type": "string", "description": "Precio del curso (para sales_page)"},
        },
        "required": ["action", "topic"],
    }

    def execute(self, action: str, topic: str, lesson_title: str = "", price: str = "") -> str:
        from automation.course_factory import research_course_market, generate_course_structure, generate_lesson_script, generate_sales_page

        if action == "research":
            return research_course_market(topic)
        elif action == "structure":
            return generate_course_structure(topic)
        elif action == "lesson":
            return generate_lesson_script(lesson_title or topic, topic)
        elif action == "sales_page":
            return generate_sales_page(topic, topic, price or "A definir")
        return "Acción no reconocida."


class MeetingTool(BaseTool):
    name = "meeting_assistant"
    description = (
        "Asistente de reuniones: transcribe audio, genera resumen con action items, "
        "guarda en Obsidian, y crea follow-ups en calendario."
    )
    parameters = {
        "type": "object",
        "properties": {
            "action": {
                "type": "string",
                "description": "transcribe (audio a texto), summarize (resumir), save (guardar en vault)",
                "enum": ["transcribe", "summarize", "save"],
            },
            "audio_path": {"type": "string", "description": "Ruta al audio de la reunión (para transcribe)"},
            "transcript": {"type": "string", "description": "Transcripción para resumir"},
            "participants": {"type": "string", "description": "Nombres de los participantes"},
            "summary": {"type": "string", "description": "Resumen para guardar en vault"},
        },
        "required": ["action"],
    }

    def execute(self, action: str, audio_path: str = "", transcript: str = "", participants: str = "", summary: str = "") -> str:
        from automation.meetings import transcribe_meeting, summarize_meeting, save_to_vault

        if action == "transcribe":
            if not audio_path:
                return "Necesito la ruta al audio."
            result = transcribe_meeting(audio_path)
            if "error" in result:
                return result["error"]
            return f"**Transcripción:**\n{result['transcript'][:3000]}"

        elif action == "summarize":
            if not transcript:
                return "Necesito la transcripción para resumir."
            return summarize_meeting(transcript, participants)

        elif action == "save":
            if not summary:
                return "Necesito el resumen para guardar."
            return save_to_vault(summary)

        return "Acción no reconocida."


class ReputationTool(BaseTool):
    name = "reputation_monitor"
    description = (
        "Monitor de reputación online: busca menciones de tu marca/nombre, "
        "analiza sentimiento, y genera respuestas a reviews negativas."
    )
    parameters = {
        "type": "object",
        "properties": {
            "action": {
                "type": "string",
                "description": "monitor (buscar menciones), respond (generar respuesta a review negativa)",
                "enum": ["monitor", "respond"],
            },
            "brand": {"type": "string", "description": "Nombre de la marca/persona a monitorear"},
            "review": {"type": "string", "description": "Review negativa para responder (action=respond)"},
            "context": {"type": "string", "description": "Contexto de la marca"},
        },
        "required": ["action", "brand"],
    }

    def execute(self, action: str, brand: str, review: str = "", context: str = "") -> str:
        from automation.reputation import monitor_brand, generate_response

        if action == "monitor":
            return monitor_brand(brand)
        elif action == "respond":
            if not review:
                return "Necesito la review para responder."
            return generate_response(review, context)
        return "Acción no reconocida."


class LegalTool(BaseTool):
    name = "legal_assistant"
    description = (
        "Asistente legal: analiza contratos, genera borradores, compara versiones, "
        "y crea contra-propuestas. NO reemplaza asesoría legal profesional."
    )
    parameters = {
        "type": "object",
        "properties": {
            "action": {
                "type": "string",
                "description": "analyze (analizar contrato), generate (crear borrador), compare (comparar), counter (contra-propuesta)",
                "enum": ["analyze", "generate", "compare", "counter"],
            },
            "text": {"type": "string", "description": "Texto del contrato o términos"},
            "contract_type": {"type": "string", "description": "Tipo de contrato (para generate)"},
            "parties": {"type": "string", "description": "Partes involucradas"},
            "text_b": {"type": "string", "description": "Segundo contrato (para compare)"},
            "changes": {"type": "string", "description": "Cambios deseados (para counter)"},
        },
        "required": ["action"],
    }

    def execute(self, action: str, text: str = "", contract_type: str = "", parties: str = "", text_b: str = "", changes: str = "") -> str:
        from automation.legal import analyze_contract, generate_contract, compare_contracts, generate_counter_proposal

        if action == "analyze":
            if not text:
                return "Necesito el texto del contrato."
            return analyze_contract(text)
        elif action == "generate":
            if not contract_type:
                return "Necesito el tipo de contrato."
            return generate_contract(contract_type, parties or "A definir")
        elif action == "compare":
            if not text or not text_b:
                return "Necesito ambos contratos (text y text_b)."
            return compare_contracts(text, text_b)
        elif action == "counter":
            if not text or not changes:
                return "Necesito los términos originales (text) y cambios deseados (changes)."
            return generate_counter_proposal(text, changes)
        return "Acción no reconocida."


class CRMTool(BaseTool):
    name = "crm"
    description = (
        "CRM personal: gestiona contactos, registra interacciones, "
        "detecta follow-ups pendientes, y prepara contexto para reuniones."
    )
    parameters = {
        "type": "object",
        "properties": {
            "action": {
                "type": "string",
                "description": "add (agregar contacto), view (ver contacto), log (registrar interacción), followups (pendientes), search (buscar), prepare (contexto reunión)",
                "enum": ["add", "view", "log", "followups", "search", "prepare"],
            },
            "name": {"type": "string", "description": "Nombre del contacto"},
            "email": {"type": "string", "description": "Email"},
            "company": {"type": "string", "description": "Empresa"},
            "role": {"type": "string", "description": "Rol/cargo"},
            "notes": {"type": "string", "description": "Notas o resumen de interacción"},
            "interaction_type": {"type": "string", "description": "Tipo: llamada, email, reunión, chat"},
            "query": {"type": "string", "description": "Búsqueda (para action=search)"},
        },
        "required": ["action"],
    }

    def execute(self, action: str, name: str = "", email: str = "", company: str = "", role: str = "", notes: str = "", interaction_type: str = "", query: str = "") -> str:
        from automation.crm import add_contact, get_contact, log_interaction, get_pending_followups, search_contacts, prepare_meeting_context

        if action == "add":
            if not name:
                return "Necesito el nombre del contacto."
            result = add_contact(name, email=email, company=company, role=role, notes=notes)
            return f"Contacto **{name}** agregado al CRM."
        elif action == "view":
            if not name:
                return "Necesito el nombre."
            return get_contact(name)
        elif action == "log":
            if not name or not notes:
                return "Necesito nombre y notas de la interacción."
            return log_interaction(name, interaction_type or "general", notes)
        elif action == "followups":
            return get_pending_followups()
        elif action == "search":
            return search_contacts(query or name or "")
        elif action == "prepare":
            if not name:
                return "Necesito el nombre del contacto."
            return prepare_meeting_context(name)
        return "Acción no reconocida."
