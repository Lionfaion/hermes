import logging
import uuid
from typing import Optional, Generator

from config import (
    ASSISTANT_NAME, OLLAMA_MODEL, SYSTEM_PROMPT, RAG_ENABLED, LEARNING_ENABLED,
    VAULT_PATH, CHROMA_PATH, WEB_ENABLED, WEB_USE_BROWSER,
)
from memory import init_db, save_message, get_history, clear_session
from inference_client import is_online, chat, chat_stream

logger = logging.getLogger(__name__)

_OFFLINE_MSG = (
    f"[{ASSISTANT_NAME}]: GPU node está offline. "
    "Asegurate de que la PC principal esté encendida y Ollama esté corriendo."
)

# Lazy singletons para no bloquear el arranque
_rag_searcher = None
_skills_manager = None
_interaction_logger = None


def _get_rag():
    global _rag_searcher
    if _rag_searcher is None and RAG_ENABLED:
        try:
            from rag.indexer import VaultIndexer
            from rag.searcher import VaultSearcher
            indexer = VaultIndexer(VAULT_PATH, CHROMA_PATH)
            _rag_searcher = VaultSearcher(indexer)
            logger.info("RAG listo (vault: %s)", VAULT_PATH)
        except Exception as e:
            logger.warning("RAG no disponible: %s", e)
    return _rag_searcher


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


class HermesAssistant:
    def __init__(self, session_id: Optional[str] = None, model: str = OLLAMA_MODEL):
        self.session_id = session_id or str(uuid.uuid4())
        self.model = model
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

        messages = [{"role": "system", "content": system_content}]

        # Inyectar contexto RAG si hay query
        if user_input:
            rag = _get_rag()
            if rag:
                try:
                    ctx = rag.build_context(user_input)
                    if ctx:
                        messages.append({"role": "system", "content": ctx})
                except Exception as e:
                    logger.warning("RAG search falló: %s", e)

        # Inyectar contenido web si se detecta intención de navegación
        if user_input and WEB_ENABLED:
            web_ctx = self._get_web_context(user_input)
            if web_ctx:
                messages.append({"role": "system", "content": web_ctx})

        messages += get_history(self.session_id)
        return messages

    def _get_web_context(self, user_input: str) -> str:
        """Detecta intención web y obtiene contenido de internet."""
        try:
            from web.web_tools import detect_web_intent, process_web_action
            intent = detect_web_intent(user_input)
            if intent["action"] == "none":
                return ""
            logger.info("Intención web detectada: %s", intent)
            return process_web_action(intent, use_browser=WEB_USE_BROWSER)
        except Exception as e:
            logger.warning("Web context falló: %s", e)
            return ""

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
            response = chat(self._build_messages(user_input), self.model)
            save_message(self.session_id, "assistant", response)
            if ilog:
                ilog.log(self.session_id, "assistant", response)
            return response
        except Exception as e:
            logger.error("respond() falló: %s", e)
            return f"[Error]: {e}"

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

        full_response = ""
        try:
            for chunk in chat_stream(self._build_messages(user_input), self.model):
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
