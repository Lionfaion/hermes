"""Error classification pipeline for inference failures.

Inspired by NousResearch/hermes-agent error handling.
Categorizes API failures and applies per-category recovery actions.
"""

import logging
import time
from dataclasses import dataclass
from enum import Enum

logger = logging.getLogger(__name__)


class ErrorCategory(Enum):
    RATE_LIMIT = "rate_limit"
    AUTH = "auth"
    CONTEXT_OVERFLOW = "context_overflow"
    TIMEOUT = "timeout"
    CONNECTION = "connection"
    CONTENT_POLICY = "content_policy"
    MODEL_NOT_FOUND = "model_not_found"
    SERVER_ERROR = "server_error"
    UNKNOWN = "unknown"


@dataclass
class ClassifiedError:
    category: ErrorCategory
    original_error: Exception
    message: str
    retryable: bool
    retry_delay: float = 0.0
    recovery_action: str = ""


CLASSIFICATION_RULES = [
    (["rate limit", "429", "too many requests"], ErrorCategory.RATE_LIMIT),
    (["unauthorized", "401", "403", "forbidden", "auth"], ErrorCategory.AUTH),
    (["context length", "token limit", "too long", "context_length"], ErrorCategory.CONTEXT_OVERFLOW),
    (["timeout", "timed out", "deadline"], ErrorCategory.TIMEOUT),
    (["connection", "connect", "refused", "unreachable", "offline"], ErrorCategory.CONNECTION),
    (["content policy", "safety", "blocked", "inappropriate", "filtered"], ErrorCategory.CONTENT_POLICY),
    (["model not found", "unknown model", "not found"], ErrorCategory.MODEL_NOT_FOUND),
    (["500", "502", "503", "504", "internal server", "bad gateway"], ErrorCategory.SERVER_ERROR),
]

RECOVERY_ACTIONS = {
    ErrorCategory.RATE_LIMIT: {
        "retryable": False,
        "base_delay": 0,
        "action": "fallback_provider",
        "description": "Rate limit alcanzado, caer al siguiente proveedor inmediatamente",
    },
    ErrorCategory.AUTH: {
        "retryable": False,
        "base_delay": 0,
        "action": "check_credentials",
        "description": "Verificar credenciales y API keys",
    },
    ErrorCategory.CONTEXT_OVERFLOW: {
        "retryable": True,
        "base_delay": 0,
        "action": "compress_context",
        "description": "Comprimir contexto y reintentar",
    },
    ErrorCategory.TIMEOUT: {
        "retryable": True,
        "base_delay": 2.0,
        "action": "retry_with_timeout",
        "description": "Reintentar con timeout mayor",
    },
    ErrorCategory.CONNECTION: {
        "retryable": True,
        "base_delay": 3.0,
        "action": "retry_connection",
        "description": "Reintentar conexión con backoff",
    },
    ErrorCategory.CONTENT_POLICY: {
        "retryable": True,
        "base_delay": 0,
        "action": "rephrase",
        "description": "Reformular el contenido y reintentar",
    },
    ErrorCategory.MODEL_NOT_FOUND: {
        "retryable": False,
        "base_delay": 0,
        "action": "check_model",
        "description": "Verificar que el modelo esté instalado en Ollama",
    },
    ErrorCategory.SERVER_ERROR: {
        "retryable": True,
        "base_delay": 5.0,
        "action": "retry_server",
        "description": "Error del servidor, reintentar",
    },
    ErrorCategory.UNKNOWN: {
        "retryable": False,
        "base_delay": 0,
        "action": "log_and_report",
        "description": "Error desconocido, reportar",
    },
}


def classify_error(error: Exception) -> ClassifiedError:
    """Classify an error into a category with recovery action."""
    error_str = str(error).lower()
    error_type = type(error).__name__.lower()
    combined = f"{error_type}: {error_str}"

    category = ErrorCategory.UNKNOWN
    for patterns, cat in CLASSIFICATION_RULES:
        if any(p in combined for p in patterns):
            category = cat
            break

    recovery = RECOVERY_ACTIONS[category]
    return ClassifiedError(
        category=category,
        original_error=error,
        message=str(error),
        retryable=recovery["retryable"],
        retry_delay=recovery["base_delay"],
        recovery_action=recovery["action"],
    )


def retry_with_classification(
    func,
    max_retries: int = 3,
    on_context_overflow=None,
    on_content_policy=None,
):
    """Execute a function with classified error handling and smart retries.

    Args:
        func: Callable to execute (no args)
        max_retries: Max retry attempts
        on_context_overflow: Callback when context is too long (should compress and return new func)
        on_content_policy: Callback when content is blocked (should rephrase and return new func)
    """
    last_error = None

    for attempt in range(max_retries + 1):
        try:
            return func()
        except Exception as e:
            classified = classify_error(e)
            last_error = classified
            logger.warning(
                "[ErrorClassifier] %s (attempt %d/%d): %s -> %s",
                classified.category.value, attempt + 1, max_retries + 1,
                classified.message[:100], classified.recovery_action,
            )

            if not classified.retryable or attempt >= max_retries:
                break

            if classified.category == ErrorCategory.CONTEXT_OVERFLOW and on_context_overflow:
                func = on_context_overflow()
                continue

            if classified.category == ErrorCategory.CONTENT_POLICY and on_content_policy:
                func = on_content_policy()
                continue

            if classified.retry_delay > 0:
                delay = classified.retry_delay * (2 ** attempt)
                logger.info("[ErrorClassifier] Waiting %.1fs before retry...", delay)
                time.sleep(delay)

    if last_error:
        raise RuntimeError(
            f"[{last_error.category.value}] {last_error.message} "
            f"(recovery: {last_error.recovery_action})"
        ) from last_error.original_error
