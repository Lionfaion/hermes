import logging
import re
import uuid
from typing import Optional, Generator

from pathlib import Path

from config import (
    ASSISTANT_NAME, OLLAMA_MODEL, SYSTEM_PROMPT, RAG_ENABLED, LEARNING_ENABLED,
    VAULT_PATH, CHROMA_PATH, TOOL_CALLING_ENABLED, TOOL_MAX_ITERATIONS,
    AGENTS_ENABLED, WEB_ENABLED, WEB_SEARCH_MAX_RESULTS, WEB_SEARCH_REGION,
    GOOGLE_AI_API_KEY,
)
from memory import init_db, save_message, get_history, clear_session
from inference_client import is_online, chat, chat_stream, chat_with_tools, chat_google
from tools.registry import ToolRegistry

_MEMORIES_NOTE = "Hermes/Memorias"  # path relativo dentro del vault (sin .md)
_vault_indexer = None
_vault_searcher = None


def _get_vault_rag():
    """Inicializa y retorna el indexer+searcher del vault (lazy, singleton)."""
    global _vault_indexer, _vault_searcher
    if _vault_searcher is not None:
        return _vault_indexer, _vault_searcher
    if not RAG_ENABLED:
        return None, None
    try:
        from rag.indexer import VaultIndexer
        from rag.searcher import VaultSearcher
        _vault_indexer = VaultIndexer(vault_path=VAULT_PATH, db_path=CHROMA_PATH)
        _vault_searcher = VaultSearcher(_vault_indexer)
        # Indexar en segundo plano solo si el vault tiene notas
        vault = Path(VAULT_PATH)
        if list(vault.rglob("*.md")):
            import threading
            threading.Thread(target=_vault_indexer.index_vault, daemon=True).start()
    except Exception as e:
        logger.warning("RAG no disponible: %s", e)
    return _vault_indexer, _vault_searcher

_WEB_SEARCH_TRIGGERS = {
    "busca", "buscá", "buscar", "googlea", "googleá", "googlear",
    "qué pasó", "qué paso", "qué dice", "qué dicen", "qué es",
    "quién es", "quien es", "qué hay", "qué hubo",
    "noticias", "última hora", "últimas noticias", "novedades",
    "precio de", "cuánto sale", "cuanto sale", "cotización", "cotizacion",
    "dólar", "dolar", "euro", "clima", "tiempo en", "pronóstico",
    "wikipedia", "encontrá", "investigá", "búscame", "busqueme",
    "reciente", "recientes", "actual", "actualidad", "hoy en día",
}

logger = logging.getLogger(__name__)

_OFFLINE_MSG = (
    f"[{ASSISTANT_NAME}]: GPU node está offline. "
    "Asegurate de que la PC principal esté encendida y Ollama esté corriendo."
)

_skills_manager = None
_interaction_logger = None
_tool_registry = None
_vault_searcher = None
_knowledge_graph = None


def _get_skills():
    global _skills_manager
    if _skills_manager is None and LEARNING_ENABLED:
        try:
            from learning.skills_manager import SkillsManager
            _skills_manager = SkillsManager()
        except Exception as e:
            logger.warning("SkillsManager no disponible: %s", e)
    return _skills_manager


def _get_ilog():
    global _interaction_logger
    if _interaction_logger is None and LEARNING_ENABLED:
        try:
            from learning.logger import InteractionLogger
            _interaction_logger = InteractionLogger()
        except Exception as e:
            logger.warning("InteractionLogger no disponible: %s", e)
    return _interaction_logger


def _get_vault_searcher():
    """Obtiene el buscador de vault para RAG automático."""
    global _vault_searcher
    if _vault_searcher is None and RAG_ENABLED:
        try:
            from rag.indexer import VaultIndexer
            from rag.searcher import VaultSearcher
            indexer = VaultIndexer(VAULT_PATH, CHROMA_PATH)
            _vault_searcher = VaultSearcher(indexer)
        except Exception as e:
            logger.warning("VaultSearcher no disponible: %s", e)
    return _vault_searcher


def _get_knowledge_graph():
    """Obtiene el grafo de conocimiento de Obsidian."""
    global _knowledge_graph
    if _knowledge_graph is None and RAG_ENABLED:
        try:
            from rag.graph import KnowledgeGraph
            _knowledge_graph = KnowledgeGraph(VAULT_PATH)
        except Exception as e:
            logger.warning("KnowledgeGraph no disponible: %s", e)
    return _knowledge_graph


def _get_registry() -> ToolRegistry:
    """Inicializa y retorna el registro global de herramientas."""
    global _tool_registry
    if _tool_registry is not None:
        return _tool_registry

    _tool_registry = ToolRegistry()

    try:
        from tools.web_tool import WebSearchTool, WebFetchTool
        _tool_registry.register(WebSearchTool())
        _tool_registry.register(WebFetchTool())
    except Exception as e:
        logger.warning("Web tools no disponibles: %s", e)

    if RAG_ENABLED:
        try:
            from tools.rag_tool import SearchNotesTool
            _tool_registry.register(SearchNotesTool())
        except Exception as e:
            logger.warning("RAG tool no disponible: %s", e)

    try:
        from tools.vault_tool import VaultReadTool, VaultWriteTool, VaultListTool
        _tool_registry.register(VaultReadTool())
        _tool_registry.register(VaultWriteTool())
        _tool_registry.register(VaultListTool())
    except Exception as e:
        logger.warning("Vault tools no disponibles: %s", e)

    try:
        from tools.media_tool import AnalyzeMediaTool
        _tool_registry.register(AnalyzeMediaTool())
    except Exception as e:
        logger.warning("Media tool no disponible: %s", e)

    try:
        from tools.file_tool import AnalyzeFileTool
        _tool_registry.register(AnalyzeFileTool())
    except Exception as e:
        logger.warning("File tool no disponible: %s", e)

    try:
        from tools.system_tool import SystemCommandTool
        _tool_registry.register(SystemCommandTool())
    except Exception as e:
        logger.warning("System tool no disponible: %s", e)

    try:
        from tools.memory_tool import RememberTool, RecallTool
        _tool_registry.register(RememberTool())
        _tool_registry.register(RecallTool())
    except Exception as e:
        logger.warning("Memory tools no disponibles: %s", e)

    try:
        from tools.reminder_tool import SetReminderTool
        _tool_registry.register(SetReminderTool())
    except Exception as e:
        logger.warning("Reminder tool no disponible: %s", e)

    try:
        from tools.video_tool import (
            ReplicateViralTool, GenerateVideoTool, AnalyzeViralTool,
            CloneVoiceTool, ProduceVideoTool, GenerateImageTool,
        )
        _tool_registry.register(ReplicateViralTool())
        _tool_registry.register(GenerateVideoTool())
        _tool_registry.register(AnalyzeViralTool())
        _tool_registry.register(CloneVoiceTool())
        _tool_registry.register(ProduceVideoTool())
        _tool_registry.register(GenerateImageTool())
    except Exception as e:
        logger.warning("Video tools no disponibles: %s", e)

    try:
        from tools.design_tool import DesignPageTool, IterateDesignTool, GenerateHTMLTool
        _tool_registry.register(DesignPageTool())
        _tool_registry.register(IterateDesignTool())
        _tool_registry.register(GenerateHTMLTool())
    except Exception as e:
        logger.warning("Design tools no disponibles: %s", e)

    try:
        from tools.strategy_tool import StrategicAnalysisTool, FrameworkGuideTool
        _tool_registry.register(StrategicAnalysisTool())
        _tool_registry.register(FrameworkGuideTool())
    except Exception as e:
        logger.warning("Strategy tools no disponibles: %s", e)

    try:
        from tools.social_tool import PublishVideoTool, PublishTextTool, ContentCalendarTool
        _tool_registry.register(PublishVideoTool())
        _tool_registry.register(PublishTextTool())
        _tool_registry.register(ContentCalendarTool())
    except Exception as e:
        logger.warning("Social tools no disponibles: %s", e)

    try:
        from tools.automation_tool import (
            ManageNicheTool, GenerateContentTool, DetectTrendsTool,
            ClipContentTool, BatchGenerateTool, VideoAnalyticsTool,
            DailyBriefingTool,
        )
        _tool_registry.register(ManageNicheTool())
        _tool_registry.register(GenerateContentTool())
        _tool_registry.register(DetectTrendsTool())
        _tool_registry.register(ClipContentTool())
        _tool_registry.register(BatchGenerateTool())
        _tool_registry.register(VideoAnalyticsTool())
        _tool_registry.register(DailyBriefingTool())
    except Exception as e:
        logger.warning("Automation tools no disponibles: %s", e)

    try:
        from tools.calendar_tool import CalendarTool
        _tool_registry.register(CalendarTool())
    except Exception as e:
        logger.warning("Calendar tool no disponible: %s", e)

    try:
        from tools.email_tool import EmailTool
        _tool_registry.register(EmailTool())
    except Exception as e:
        logger.warning("Email tool no disponible: %s", e)

    try:
        from tools.expansion_tools import (
            LeadGenTool, FreelanceTool, SEOTool, EcommerceTool,
            MarketMonitorTool, CourseFactoryTool, MeetingTool,
            ReputationTool, LegalTool, CRMTool,
        )
        _tool_registry.register(LeadGenTool())
        _tool_registry.register(FreelanceTool())
        _tool_registry.register(SEOTool())
        _tool_registry.register(EcommerceTool())
        _tool_registry.register(MarketMonitorTool())
        _tool_registry.register(CourseFactoryTool())
        _tool_registry.register(MeetingTool())
        _tool_registry.register(ReputationTool())
        _tool_registry.register(LegalTool())
        _tool_registry.register(CRMTool())
    except Exception as e:
        logger.warning("Expansion tools no disponibles: %s", e)

    try:
        from tools.github_tool import GitHubTool
        _tool_registry.register(GitHubTool())
    except Exception as e:
        logger.warning("GitHub tool no disponible: %s", e)

    # Background tasks
    try:
        from tools.task_tool import CreateBackgroundTaskTool, CheckTasksTool, CancelTaskTool
        _tool_registry.register(CreateBackgroundTaskTool(registry=_tool_registry))
        _tool_registry.register(CheckTasksTool())
        _tool_registry.register(CancelTaskTool())
    except Exception as e:
        logger.warning("Task tools no disponibles: %s", e)

    # Cron jobs
    try:
        from tools.cron_tool import CreateCronJobTool, ListCronJobsTool, DeleteCronJobTool
        _tool_registry.register(CreateCronJobTool())
        _tool_registry.register(ListCronJobsTool())
        _tool_registry.register(DeleteCronJobTool())
    except Exception as e:
        logger.warning("Cron tools no disponibles: %s", e)

    # Knowledge Graph
    try:
        from tools.graph_tool import GraphConnectionsTool, GraphSearchTool
        _tool_registry.register(GraphConnectionsTool())
        _tool_registry.register(GraphSearchTool())
    except Exception as e:
        logger.warning("Graph tools no disponibles: %s", e)

    # Specs (Spec Driven Development)
    try:
        from tools.spec_tool import (
            CreateSpecTool, ListSpecsTool, GetSpecTool,
            ExecuteSpecTool, DeleteSpecTool,
        )
        _tool_registry.register(CreateSpecTool())
        _tool_registry.register(ListSpecsTool())
        _tool_registry.register(GetSpecTool())
        _tool_registry.register(ExecuteSpecTool(registry=_tool_registry))
        _tool_registry.register(DeleteSpecTool())
    except Exception as e:
        logger.warning("Spec tools no disponibles: %s", e)

    # Director (multi-agent orchestration)
    try:
        from tools.director_tool import DirectorTool
        _tool_registry.register(DirectorTool(registry=_tool_registry))
    except Exception as e:
        logger.warning("Director tool no disponible: %s", e)

    if AGENTS_ENABLED:
        try:
            from agents.orchestrator import DelegateToAgentTool
            _tool_registry.register(DelegateToAgentTool(_tool_registry))
        except Exception as e:
            logger.warning("Agent orchestrator no disponible: %s", e)

    # Start cron scheduler
    try:
        from background.cron import CronScheduler
        scheduler = CronScheduler()
        scheduler.set_registry(_tool_registry)
        scheduler.start()
    except Exception as e:
        logger.warning("Cron scheduler no iniciado: %s", e)

    logger.info("Tools registradas: %s", _tool_registry.list_tools())
    return _tool_registry


class HermesAssistant:
    def __init__(self, session_id: Optional[str] = None, model: str = OLLAMA_MODEL):
        self.session_id = session_id or str(uuid.uuid4())
        self.model = model
        self.registry = _get_registry()
        init_db()
        logger.info("Sesión iniciada: %s", self.session_id)

    def _load_memories(self) -> str:
        """Lee la nota de memorias del vault e inyecta en el system prompt."""
        parts = []
        try:
            vault = Path(VAULT_PATH)
            note = (vault / _MEMORIES_NOTE).with_suffix(".md")
            if note.exists():
                content = note.read_text(encoding="utf-8", errors="ignore").strip()
                if content:
                    parts.append(f"[Lo que sé del usuario — información persistente]\n{content}")
        except Exception as e:
            logger.debug("_load_memories error: %s", e)

        try:
            from self_improvement import load_improvements
            improvements = load_improvements()
            if improvements:
                parts.append(f"[Comportamiento aprendido de auto-mejora]\n{improvements}")
        except Exception as e:
            logger.debug("_load_improvements error: %s", e)

        return "\n\n".join(parts)

    def _search_vault(self, query: str) -> str:
        """Búsqueda semántica en el vault para contexto relevante al mensaje."""
        _, searcher = _get_vault_rag()
        if searcher is None:
            return ""
        try:
            ctx = searcher.build_context(query)
            return ctx
        except Exception as e:
            logger.debug("_search_vault error: %s", e)
        return ""

    def _fetch_web_context(self, user_input: str) -> str:
        """Auto-búsqueda web si el mensaje lo requiere. Retorna contexto formateado o ''."""
        if not WEB_ENABLED:
            return ""
        try:
            text = user_input.strip()

            # URL explícita → fetch
            url_match = re.search(r'https?://\S+', text)
            if url_match:
                url = url_match.group(0).rstrip('.,)')
                # Usar Playwright (renderiza JS) para capturar SPAs y páginas dinámicas
                try:
                    from web.browser import browse_page
                    result = browse_page(url)
                except Exception:
                    result = None
                # Fallback a scraper estático si Playwright falla
                if not result or not result.success or len(result.text.strip()) < 100:
                    from web.scraper import fetch_page
                    static = fetch_page(url)
                    if static.success and len(static.text.strip()) > (len(result.text.strip()) if result else 0):
                        result = static
                if result and result.success:
                    content = result.text.strip()[:5000]
                    header = f"Título: {result.title}" if result.title else ""
                    return f"{header}\n\n{content}".strip()
                return ""

            # Detección de intención de búsqueda
            lower = text.lower()
            needs_search = any(trigger in lower for trigger in _WEB_SEARCH_TRIGGERS)
            if not needs_search:
                return ""

            from web.search import web_search, format_search_results
            results = web_search(text, max_results=WEB_SEARCH_MAX_RESULTS, region=WEB_SEARCH_REGION)
            if results:
                logger.info("Web search ejecutada para: %.60s", text)
                return format_search_results(results)
        except Exception as e:
            logger.warning("_fetch_web_context falló: %s", e)
        return ""

    def _build_messages(self, user_input: str = "") -> list:
        from datetime import datetime
        today = datetime.now().strftime("%A %d de %B de %Y, %H:%M")
        system_content = f"Fecha y hora actual: {today}\n\n{SYSTEM_PROMPT}"

        # Memorias persistentes del vault (siempre incluidas)
        memories = self._load_memories()
        if memories:
            system_content += f"\n\n{memories}"

        # Contexto semántico del vault relevante al mensaje
        if user_input:
            vault_ctx = self._search_vault(user_input)
            if vault_ctx:
                system_content += f"\n\n{vault_ctx}"

        skills = _get_skills()
        if skills:
            injection = skills.build_system_injection()
            if injection:
                system_content += f"\n\n[Comportamiento aprendido de experiencia]\n{injection}"

        # RAG automático: buscar en Obsidian vault + knowledge graph
        if user_input and RAG_ENABLED:
            vault_context = self._get_vault_context(user_input)
            if vault_context:
                system_content += f"\n\n{vault_context}"

        if TOOL_CALLING_ENABLED:
            tool_names = self.registry.list_tools()
            if tool_names:
                system_content += (
                    "\n\nTenés acceso a herramientas que podés usar cuando sea necesario. "
                    "Usá las herramientas de forma inteligente: no las uses si podés responder "
                    "directamente con tu conocimiento."
                )

        messages = [{"role": "system", "content": system_content}]
        messages += get_history(self.session_id)
        return messages

    def _get_vault_context(self, query: str) -> str:
        """Busca contexto relevante en el vault de Obsidian (RAG + Knowledge Graph)."""
        parts = []

        # Semantic search (RAG)
        searcher = _get_vault_searcher()
        if searcher:
            try:
                context = searcher.build_context(query)
                if context:
                    parts.append(context)
                    logger.debug("RAG automático inyectó contexto para: %s", query[:50])
            except Exception as e:
                logger.warning("RAG automático falló: %s", e)

        # Knowledge Graph context
        graph = _get_knowledge_graph()
        if graph:
            try:
                graph_context = graph.build_context_for_query(query)
                if graph_context:
                    parts.append(graph_context)
                    logger.debug("Graph inyectó contexto para: %s", query[:50])
            except Exception as e:
                logger.warning("Knowledge Graph falló: %s", e)

        return "\n\n".join(parts)

    def respond(self, user_input: str) -> str:
        if not user_input.strip():
            return ""

        ilog = _get_ilog()
        if ilog:
            ilog.log(self.session_id, "user", user_input)

        save_message(self.session_id, "user", user_input)

        ollama_online = is_online()

        try:
            web_context = self._fetch_web_context(user_input)
            messages = self._build_messages(user_input)

            if web_context:
                augmented = f"{user_input}\n\n---\n{web_context}\n---"
                messages.append({"role": "user", "content": augmented})
            else:
                messages.append({"role": "user", "content": user_input})

            if ollama_online:
                if TOOL_CALLING_ENABLED:
                    response = self._tool_call_loop(messages)
                else:
                    response = chat(messages, self.model)
            elif GOOGLE_AI_API_KEY:
                logger.info("GPU node offline — usando Google AI como fallback")
                response = chat_google(messages)
            else:
                logger.warning("GPU node offline y sin fallback de Google AI")
                return _OFFLINE_MSG

            save_message(self.session_id, "assistant", response)
            if ilog:
                ilog.log(self.session_id, "assistant", response)
            return response
        except Exception as e:
            logger.error("respond() falló: %s", e)
            if not ollama_online and GOOGLE_AI_API_KEY:
                try:
                    messages_fallback = self._build_messages(user_input)
                    messages_fallback.append({"role": "user", "content": user_input})
                    return chat_google(messages_fallback)
                except Exception as e2:
                    logger.error("Google AI fallback también falló: %s", e2)
            return f"[Error]: {e}"

    def _tool_call_loop(self, messages: list) -> str:
        """Loop de tool calling: el LLM decide qué herramienta usar."""
        schemas = self.registry.get_schemas()

        for iteration in range(TOOL_MAX_ITERATIONS):
            response = chat_with_tools(messages, schemas, self.model)

            tool_calls = response.get("tool_calls")
            content = response.get("content", "")

            if not tool_calls:
                return content

            logger.info("Tool calls (iteración %d): %s",
                       iteration + 1,
                       [tc.get("function", {}).get("name") for tc in tool_calls])

            messages.append({"role": "assistant", "content": content, "tool_calls": tool_calls})

            for tc in tool_calls:
                func = tc.get("function", {})
                name = func.get("name", "")
                args = func.get("arguments", {})
                if isinstance(args, str):
                    import json
                    try:
                        args = json.loads(args)
                    except json.JSONDecodeError:
                        args = {}

                result = self.registry.execute(name, args)
                messages.append({"role": "tool", "content": result})

        return response.get("content", "") or "[Se alcanzó el límite de iteraciones de herramientas]"

    def respond_stream(self, user_input: str) -> Generator:
        if not user_input.strip():
            return

        ilog = _get_ilog()
        if ilog:
            ilog.log(self.session_id, "user", user_input)

        save_message(self.session_id, "user", user_input)

        if not is_online():
            logger.warning("GPU node offline")
            yield _OFFLINE_MSG
            return

        try:
            web_context = self._fetch_web_context(user_input)
            messages = self._build_messages(user_input)

            if web_context:
                augmented = f"{user_input}\n\n---\n{web_context}\n---"
                messages.append({"role": "user", "content": augmented})
            else:
                messages.append({"role": "user", "content": user_input})

            if TOOL_CALLING_ENABLED:
                response = self._tool_call_loop(messages)
                save_message(self.session_id, "assistant", response)
                if ilog:
                    ilog.log(self.session_id, "assistant", response)
                yield response
            else:
                full_response = ""
                for chunk in chat_stream(messages, self.model):
                    full_response += chunk
                    yield chunk
                save_message(self.session_id, "assistant", full_response)
                if ilog:
                    ilog.log(self.session_id, "assistant", full_response)
        except Exception as e:
            logger.error("respond_stream() falló: %s", e)
            yield f"\n[Error]: {e}"

    def clear_memory(self) -> None:
        clear_session(self.session_id)

    def new_session(self) -> str:
        self.session_id = str(uuid.uuid4())
        logger.info("Nueva sesión: %s", self.session_id)
        return self.session_id
