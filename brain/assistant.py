import logging
import uuid
from typing import Optional, Generator

from config import (
    ASSISTANT_NAME, OLLAMA_MODEL, SYSTEM_PROMPT, RAG_ENABLED, LEARNING_ENABLED,
    VAULT_PATH, CHROMA_PATH, TOOL_CALLING_ENABLED, TOOL_MAX_ITERATIONS,
    AGENTS_ENABLED,
)
from memory import init_db, save_message, get_history, clear_session
from inference_client import is_online, chat, chat_stream, chat_with_tools
from tools.registry import ToolRegistry

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
            GenerateBrollTool, HeyGenAvatarTool, AddCaptionsTool,
            VideoQCTool, ListVideoJobsTool,
        )
        _tool_registry.register(ReplicateViralTool())
        _tool_registry.register(GenerateVideoTool())
        _tool_registry.register(AnalyzeViralTool())
        _tool_registry.register(CloneVoiceTool())
        _tool_registry.register(ProduceVideoTool())
        _tool_registry.register(GenerateImageTool())
        _tool_registry.register(GenerateBrollTool())
        _tool_registry.register(HeyGenAvatarTool())
        _tool_registry.register(AddCaptionsTool())
        _tool_registry.register(VideoQCTool())
        _tool_registry.register(ListVideoJobsTool())
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

    # Reasoning, evolution, steering, and advanced AI tools
    try:
        from tools.reasoning_tool import (
            AutoReasonTool, ParallelSolveTool, ReasoningPracticeTool,
            EvolvePromptTool, NeuralSteerTool, AbliterateTool,
            KanbanVideoTool, NovelWriterTool, AgentStatsTool,
            MoATool, CodeDiagnosticsTool, CodeDefinitionTool, CodeReferencesTool,
        )
        _tool_registry.register(AutoReasonTool())
        _tool_registry.register(ParallelSolveTool())
        _tool_registry.register(ReasoningPracticeTool())
        _tool_registry.register(EvolvePromptTool())
        _tool_registry.register(NeuralSteerTool())
        _tool_registry.register(AbliterateTool())
        _tool_registry.register(KanbanVideoTool())
        _tool_registry.register(NovelWriterTool())
        _tool_registry.register(AgentStatsTool())
        _tool_registry.register(MoATool())
        _tool_registry.register(CodeDiagnosticsTool())
        _tool_registry.register(CodeDefinitionTool())
        _tool_registry.register(CodeReferencesTool())
    except Exception as e:
        logger.warning("Reasoning/AI tools no disponibles: %s", e)

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

    def _maybe_compress(self, messages: list) -> list:
        """Compress context if it's getting too large."""
        try:
            from context.compressor import compress_context, estimate_tokens
            token_est = estimate_tokens(messages)
            if token_est > 6000 or len(messages) > 30:
                result = compress_context(messages, max_messages=30, model=self.model)
                if result.compressed_count < result.original_count:
                    logger.info(
                        "Context compressed: %d → %d messages (pruned %d tool outputs)",
                        result.original_count, result.compressed_count, result.pruned_tool_outputs,
                    )
                    return result.messages
        except Exception as e:
            logger.debug("Context compression skipped: %s", e)
        return messages

    def _build_messages(self, user_input: str = "") -> list:
        try:
            from soul import CORE_PROMPT, TOOLS_REFERENCE
            system_content = CORE_PROMPT
        except ImportError:
            system_content = SYSTEM_PROMPT

        # Inyectar lecciones aprendidas
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
                try:
                    from soul import TOOLS_REFERENCE
                    system_content += f"\n\n{TOOLS_REFERENCE}"
                except ImportError:
                    system_content += (
                        "\n\nTenés acceso a herramientas que podés usar cuando sea necesario. "
                        "Usá las herramientas de forma inteligente: no las uses si podés responder "
                        "directamente con tu conocimiento."
                    )

        messages = [{"role": "system", "content": system_content}]
        messages += get_history(self.session_id)
        messages = self._maybe_compress(messages)
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

        if not is_online():
            logger.warning("GPU node offline")
            return _OFFLINE_MSG

        try:
            messages = self._build_messages(user_input)
            messages.append({"role": "user", "content": user_input})

            if TOOL_CALLING_ENABLED:
                response = self._tool_call_loop(messages)
            else:
                response = chat(messages, self.model)

            save_message(self.session_id, "assistant", response)
            if ilog:
                ilog.log(self.session_id, "assistant", response)
            return response
        except Exception as e:
            logger.error("respond() falló: %s", e)
            return f"[Error]: {e}"

    def _tool_call_loop(self, messages: list) -> str:
        """Loop de tool calling con budget inteligente y clasificación de errores."""
        schemas = self.registry.get_schemas()

        try:
            from agents.budget import get_budget_manager
            budget = get_budget_manager().get_budget(self.session_id)
        except Exception:
            budget = None

        for iteration in range(TOOL_MAX_ITERATIONS):
            if budget and budget.exhausted:
                logger.warning("Iteration budget exhausted for session %s", self.session_id)
                return response.get("content", "") or "[Se agotó el presupuesto de iteraciones]"
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

                # Governance: check policy before executing
                try:
                    from governance.policy_engine import check_permission
                    decision = check_permission(name, agent_name=getattr(self, '_current_agent', ''), args=args)
                    if not decision.allowed:
                        result = f"[BLOQUEADO] Herramienta '{name}' denegada por política: {decision.rule_name}"
                        logger.warning("Governance DENY: %s -> %s", name, decision.rule_name)
                        messages.append({"role": "tool", "content": result})
                        continue
                except Exception:
                    pass

                if budget and not budget.consume(name):
                    result = "[BUDGET] Presupuesto de iteraciones agotado"
                    messages.append({"role": "tool", "content": result})
                    continue

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
            messages = self._build_messages(user_input)
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
