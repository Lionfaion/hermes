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

    if AGENTS_ENABLED:
        try:
            from agents.orchestrator import DelegateToAgentTool
            _tool_registry.register(DelegateToAgentTool(_tool_registry))
        except Exception as e:
            logger.warning("Agent orchestrator no disponible: %s", e)

    logger.info("Tools registradas: %s", _tool_registry.list_tools())
    return _tool_registry


class HermesAssistant:
    def __init__(self, session_id: Optional[str] = None, model: str = OLLAMA_MODEL):
        self.session_id = session_id or str(uuid.uuid4())
        self.model = model
        self.registry = _get_registry()
        init_db()
        logger.info("Sesión iniciada: %s", self.session_id)

    def _build_messages(self, user_input: str = "") -> list:
        system_content = SYSTEM_PROMPT

        # Inyectar lecciones aprendidas
        skills = _get_skills()
        if skills:
            injection = skills.build_system_injection()
            if injection:
                system_content += f"\n\n[Comportamiento aprendido de experiencia]\n{injection}"

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
            messages = self._build_messages(user_input)
            messages.append({"role": "user", "content": user_input})

            if TOOL_CALLING_ENABLED:
                # Tool calling no soporta streaming directo.
                # Hacemos el loop de tools sin stream, y luego retornamos el resultado.
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
