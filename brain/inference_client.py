import json
import logging
from typing import Generator

import httpx

from config import (
    GPU_NODE_HOST,
    GPU_NODE_PORT,
    OLLAMA_MODEL,
    OLLAMA_TIMEOUT,
    INFERENCE_RETRY_ATTEMPTS,
)

logger = logging.getLogger(__name__)
_BASE_URL = f"http://{GPU_NODE_HOST}:{GPU_NODE_PORT}"


def is_online() -> bool:
    try:
        r = httpx.get(f"{_BASE_URL}/api/tags", timeout=3.0)
        return r.status_code == 200
    except Exception:
        return False


def list_models() -> list:
    try:
        r = httpx.get(f"{_BASE_URL}/api/tags", timeout=5.0)
        r.raise_for_status()
        return [m["name"] for m in r.json().get("models", [])]
    except Exception as e:
        logger.warning("Could not list models: %s", e)
        return []


def _post_chat(payload: dict) -> dict:
    """Envía un request a /api/chat con reintentos y clasificación de errores."""
    from inference_errors import classify_error

    last_error: Exception = RuntimeError("Unknown error")
    last_classified = None

    for attempt in range(1, INFERENCE_RETRY_ATTEMPTS + 1):
        try:
            with httpx.Client(timeout=OLLAMA_TIMEOUT) as client:
                r = client.post(f"{_BASE_URL}/api/chat", json=payload)
                r.raise_for_status()
                return r.json()
        except httpx.ConnectError:
            last_error = ConnectionError(
                f"GPU node offline at {_BASE_URL}. Is the main PC on and Ollama running?"
            )
        except httpx.TimeoutException:
            last_error = TimeoutError(
                f"GPU node timed out after {OLLAMA_TIMEOUT}s. Model may still be loading."
            )
        except httpx.HTTPStatusError as e:
            last_error = RuntimeError(f"HTTP {e.response.status_code}: {e.response.text[:200]}")
        except Exception as e:
            last_error = RuntimeError(f"Inference error: {e}")

        last_classified = classify_error(last_error)
        logger.warning(
            "Attempt %d/%d [%s]: %s -> %s",
            attempt, INFERENCE_RETRY_ATTEMPTS,
            last_classified.category.value,
            str(last_error)[:100],
            last_classified.recovery_action,
        )

        if not last_classified.retryable:
            break

        if last_classified.retry_delay > 0 and attempt < INFERENCE_RETRY_ATTEMPTS:
            import time
            delay = last_classified.retry_delay * (2 ** (attempt - 1))
            time.sleep(min(delay, 30))

    raise last_error


def chat(messages: list, model: str = OLLAMA_MODEL) -> str:
    data = _post_chat({"model": model, "messages": messages, "stream": False})
    return data["message"]["content"]


def chat_with_tools(messages: list, tools: list, model: str = OLLAMA_MODEL) -> dict:
    """Chat con soporte de tool calling. Retorna el dict message completo."""
    payload = {"model": model, "messages": messages, "stream": False}
    if tools:
        payload["tools"] = tools
    data = _post_chat(payload)
    return data.get("message", {})


def chat_with_images(messages: list, images: list[str], model: str = OLLAMA_MODEL) -> str:
    """Chat con imágenes (base64). Para modelos de visión como LLaVA."""
    if messages and images:
        messages = list(messages)
        last_msg = dict(messages[-1])
        last_msg["images"] = images
        messages[-1] = last_msg

    data = _post_chat({"model": model, "messages": messages, "stream": False})
    return data["message"]["content"]


def chat_stream(messages: list, model: str = OLLAMA_MODEL) -> Generator:
    try:
        with httpx.Client(timeout=OLLAMA_TIMEOUT) as client:
            with client.stream(
                "POST",
                f"{_BASE_URL}/api/chat",
                json={"model": model, "messages": messages, "stream": True},
            ) as r:
                r.raise_for_status()
                for line in r.iter_lines():
                    if not line:
                        continue
                    chunk = json.loads(line)
                    if not chunk.get("done") and "message" in chunk:
                        yield chunk["message"]["content"]
    except httpx.ConnectError:
        raise ConnectionError(f"GPU node offline at {_BASE_URL}")
    except httpx.TimeoutException:
        raise TimeoutError(f"GPU node timed out after {OLLAMA_TIMEOUT}s")
    except Exception as e:
        raise RuntimeError(f"Stream error: {e}")
