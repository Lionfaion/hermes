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


def chat(messages: list, model: str = OLLAMA_MODEL) -> str:
    last_error: Exception = RuntimeError("Unknown error")

    for attempt in range(1, INFERENCE_RETRY_ATTEMPTS + 1):
        try:
            with httpx.Client(timeout=OLLAMA_TIMEOUT) as client:
                r = client.post(
                    f"{_BASE_URL}/api/chat",
                    json={"model": model, "messages": messages, "stream": False},
                )
                r.raise_for_status()
                return r.json()["message"]["content"]
        except httpx.ConnectError:
            last_error = ConnectionError(
                f"GPU node offline at {_BASE_URL}. Is the main PC on and Ollama running?"
            )
        except httpx.TimeoutException:
            last_error = TimeoutError(
                f"GPU node timed out after {OLLAMA_TIMEOUT}s. Model may still be loading."
            )
        except Exception as e:
            last_error = RuntimeError(f"Inference error: {e}")
            break

        logger.warning("Attempt %d/%d failed: %s", attempt, INFERENCE_RETRY_ATTEMPTS, last_error)

    raise last_error


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
