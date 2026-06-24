"""
Hermes Security Layer
- Rate limiting por usuario
- Sanitización de input
- Detección de prompt injection
"""
import logging
import re
import time
from collections import defaultdict
from typing import Optional

logger = logging.getLogger(__name__)

# ── Configuración ──────────────────────────────────────────────────────────────
MAX_MESSAGE_LENGTH = 2000
RATE_LIMIT_MESSAGES = 10   # max mensajes
RATE_LIMIT_WINDOW = 60     # por minuto
RATE_LIMIT_BURST = 3       # burst permitido

# Patrones de prompt injection conocidos
_INJECTION_PATTERNS = [
    r"ignore\s+(all\s+)?previous\s+instructions",
    r"forget\s+(all\s+)?previous",
    r"you\s+are\s+now\s+(a\s+)?(?:dan|jailbreak|evil|unrestricted)",
    r"act\s+as\s+(if\s+you\s+are\s+)?(?:an?\s+)?(?:evil|unrestricted|jailbreak)",
    r"do\s+anything\s+now",
    r"disregard\s+(your\s+)?(previous\s+)?instructions",
    r"system\s*:\s*you\s+are",
    r"\[system\]",
    r"<\|im_start\|>system",
    r"###\s*instruction",
    r"reveal\s+(your\s+)?(system\s+)?prompt",
    r"print\s+(your\s+)?(system\s+)?prompt",
    r"what\s+(are\s+your|is\s+your)\s+(system\s+)?instructions",
]
_INJECTION_RE = re.compile("|".join(_INJECTION_PATTERNS), re.IGNORECASE)

# Rate limiter state
_rate_buckets: dict = defaultdict(lambda: {"tokens": RATE_LIMIT_BURST, "last": 0.0})


# ── Rate Limiter (Token Bucket) ────────────────────────────────────────────────
def check_rate_limit(user_id: str) -> tuple[bool, Optional[str]]:
    """Returns (allowed, error_message)."""
    bucket = _rate_buckets[user_id]
    now = time.monotonic()
    elapsed = now - bucket["last"]
    bucket["last"] = now

    # Recargar tokens según tiempo transcurrido
    refill = elapsed * (RATE_LIMIT_MESSAGES / RATE_LIMIT_WINDOW)
    bucket["tokens"] = min(RATE_LIMIT_BURST, bucket["tokens"] + refill)

    if bucket["tokens"] >= 1:
        bucket["tokens"] -= 1
        return True, None

    wait = round((1 - bucket["tokens"]) * (RATE_LIMIT_WINDOW / RATE_LIMIT_MESSAGES))
    logger.warning("Rate limit exceeded for user %s", user_id)
    return False, f"Demasiados mensajes. Esperá {wait} segundos."


# ── Sanitización ───────────────────────────────────────────────────────────────
def sanitize_input(text: str) -> tuple[str, Optional[str]]:
    """
    Limpia y valida el input del usuario.
    Returns (cleaned_text, error_message).
    """
    if not text or not text.strip():
        return "", "Mensaje vacío."

    # Strip null bytes y caracteres de control peligrosos
    text = text.replace("\x00", "").replace("\r", "")
    text = re.sub(r"[\x01-\x08\x0b\x0c\x0e-\x1f\x7f]", "", text)

    # Límite de longitud
    if len(text) > MAX_MESSAGE_LENGTH:
        text = text[:MAX_MESSAGE_LENGTH]
        logger.info("Input truncated to %d chars", MAX_MESSAGE_LENGTH)

    return text.strip(), None


# ── Detección de Prompt Injection ──────────────────────────────────────────────
def detect_injection(text: str) -> bool:
    """Returns True si se detecta intento de prompt injection."""
    if _INJECTION_RE.search(text):
        logger.warning("Prompt injection attempt detected: %.80s", text)
        return True
    return False


# ── Validación completa ────────────────────────────────────────────────────────
def validate_message(user_id: str, text: str) -> tuple[Optional[str], Optional[str]]:
    """
    Validación completa: rate limit + sanitización + injection.
    Returns (clean_text, error_message). Si error_message != None, rechazar.
    """
    # Rate limit
    allowed, err = check_rate_limit(user_id)
    if not allowed:
        return None, err

    # Sanitizar
    clean, err = sanitize_input(text)
    if err:
        return None, err

    # Prompt injection
    if detect_injection(clean):
        return None, "Mensaje no permitido."

    return clean, None
