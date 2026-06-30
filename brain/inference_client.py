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
    OPENROUTER_API_KEY,
    OPENROUTER_BASE_URL,
    OPENROUTER_MODEL,
    OPENROUTER_TIMEOUT,
    GROQ_API_KEY,
    GROQ_BASE_URL,
    GROQ_MODEL,
    GROQ_TIMEOUT,
    GOOGLE_AI_API_KEY,
    GOOGLE_AI_BASE_URL,
    GOOGLE_AI_CHAT_MODEL,
    GOOGLE_AI_TIMEOUT,
    ZAI_API_KEY,
    ZAI_BASE_URL,
    ZAI_MODEL,
    ZAI_TIMEOUT,
)

logger = logging.getLogger(__name__)
_OLLAMA_URL = f"http://{GPU_NODE_HOST}:{GPU_NODE_PORT}"

_USE_OPENROUTER = bool(OPENROUTER_API_KEY)
_USE_GROQ = bool(GROQ_API_KEY)
_USE_GOOGLE = bool(GOOGLE_AI_API_KEY)
_USE_ZAI = bool(ZAI_API_KEY)


def _resolve_openrouter_model(requested: str | None) -> str:
    """Ollama names (e.g. qwen2.5:7b) get replaced with OPENROUTER_MODEL."""
    if requested and "/" in requested:
        return requested  # ya es un model ID de OpenRouter
    return OPENROUTER_MODEL


def _resolve_zai_model(requested: str | None) -> str:
    """Map model param to Z.ai model. Ollama names get replaced with ZAI_MODEL."""
    if requested and requested.startswith("glm"):
        return requested
    return ZAI_MODEL


def _get_openrouter_client():
    from openai import OpenAI
    return OpenAI(api_key=OPENROUTER_API_KEY, base_url=OPENROUTER_BASE_URL)


def _get_groq_client():
    from openai import OpenAI
    return OpenAI(api_key=GROQ_API_KEY, base_url=GROQ_BASE_URL)


def _get_google_client():
    from openai import OpenAI
    return OpenAI(api_key=GOOGLE_AI_API_KEY, base_url=GOOGLE_AI_BASE_URL)


def _get_openai_client():
    from openai import OpenAI
    return OpenAI(api_key=ZAI_API_KEY, base_url=ZAI_BASE_URL)


def is_online() -> bool:
    if _USE_OPENROUTER:
        return True  # OpenRouter es siempre online
    if _USE_ZAI:
        try:
            client = _get_openai_client()
            client.models.list()
            return True
        except Exception:
            return False
    try:
        r = httpx.get(f"{_OLLAMA_URL}/api/tags", timeout=3.0)
        return r.status_code == 200
    except Exception:
        return False


def list_models() -> list:
    if _USE_ZAI:
        try:
            client = _get_openai_client()
            models = client.models.list()
            return [m.id for m in models.data]
        except Exception as e:
            logger.warning("Could not list Z.ai models: %s", e)
            return []
    try:
        r = httpx.get(f"{_OLLAMA_URL}/api/tags", timeout=5.0)
        r.raise_for_status()
        return [m["name"] for m in r.json().get("models", [])]
    except Exception as e:
        logger.warning("Could not list models: %s", e)
        return []


# ---------------------------------------------------------------------------
# OpenRouter backend (prioridad 1)
# ---------------------------------------------------------------------------

def _openrouter_chat(messages: list, model: str, tools: list | None = None, stream: bool = False) -> dict:
    from inference_errors import classify_error

    last_error: Exception = RuntimeError("Unknown error")

    for attempt in range(1, INFERENCE_RETRY_ATTEMPTS + 1):
        try:
            client = _get_openrouter_client()
            kwargs = {
                "model": model,
                "messages": messages,
                "stream": stream,
                "timeout": OPENROUTER_TIMEOUT,
            }
            if tools:
                oai_tools = _convert_tools_to_openai(tools)
                if oai_tools:
                    kwargs["tools"] = oai_tools

            response = client.chat.completions.create(**kwargs)
            msg = response.choices[0].message

            result = {"content": msg.content or ""}
            if msg.tool_calls:
                result["tool_calls"] = [
                    {
                        "function": {
                            "name": tc.function.name,
                            "arguments": json.loads(tc.function.arguments)
                            if isinstance(tc.function.arguments, str)
                            else tc.function.arguments,
                        }
                    }
                    for tc in msg.tool_calls
                ]
            return result

        except Exception as e:
            last_error = RuntimeError(f"OpenRouter error: {e}")
            classified = classify_error(last_error)
            logger.warning(
                "OpenRouter attempt %d/%d [%s]: %s -> %s",
                attempt, INFERENCE_RETRY_ATTEMPTS,
                classified.category.value,
                str(last_error)[:100],
                classified.recovery_action,
            )
            if not classified.retryable:
                break
            if classified.retry_delay > 0 and attempt < INFERENCE_RETRY_ATTEMPTS:
                import time
                time.sleep(min(classified.retry_delay * (2 ** (attempt - 1)), 30))

    raise last_error


def _openrouter_chat_stream(messages: list, model: str) -> Generator:
    try:
        client = _get_openrouter_client()
        stream = client.chat.completions.create(
            model=model,
            messages=messages,
            stream=True,
            timeout=OPENROUTER_TIMEOUT,
        )
        for chunk in stream:
            if chunk.choices and chunk.choices[0].delta.content:
                yield chunk.choices[0].delta.content
    except Exception as e:
        raise RuntimeError(f"OpenRouter stream error: {e}")


# ---------------------------------------------------------------------------
# Z.ai (OpenAI-compatible) backend
# ---------------------------------------------------------------------------

def _zai_chat(messages: list, model: str, tools: list | None = None, stream: bool = False) -> dict:
    from inference_errors import classify_error

    last_error: Exception = RuntimeError("Unknown error")

    for attempt in range(1, INFERENCE_RETRY_ATTEMPTS + 1):
        try:
            client = _get_openai_client()
            kwargs = {
                "model": model,
                "messages": messages,
                "stream": stream,
                "timeout": ZAI_TIMEOUT,
            }
            if tools:
                oai_tools = _convert_tools_to_openai(tools)
                if oai_tools:
                    kwargs["tools"] = oai_tools

            response = client.chat.completions.create(**kwargs)
            msg = response.choices[0].message

            result = {"content": msg.content or ""}
            if msg.tool_calls:
                result["tool_calls"] = [
                    {
                        "function": {
                            "name": tc.function.name,
                            "arguments": json.loads(tc.function.arguments)
                            if isinstance(tc.function.arguments, str)
                            else tc.function.arguments,
                        }
                    }
                    for tc in msg.tool_calls
                ]
            return result

        except Exception as e:
            last_error = RuntimeError(f"Z.ai error: {e}")
            classified = classify_error(last_error)
            logger.warning(
                "Z.ai attempt %d/%d [%s]: %s -> %s",
                attempt, INFERENCE_RETRY_ATTEMPTS,
                classified.category.value,
                str(last_error)[:100],
                classified.recovery_action,
            )
            if not classified.retryable:
                break
            if classified.retry_delay > 0 and attempt < INFERENCE_RETRY_ATTEMPTS:
                import time
                delay = classified.retry_delay * (2 ** (attempt - 1))
                time.sleep(min(delay, 30))

    raise last_error


def _zai_chat_stream(messages: list, model: str) -> Generator:
    try:
        client = _get_openai_client()
        stream = client.chat.completions.create(
            model=model,
            messages=messages,
            stream=True,
            timeout=ZAI_TIMEOUT,
        )
        for chunk in stream:
            if chunk.choices and chunk.choices[0].delta.content:
                yield chunk.choices[0].delta.content
    except Exception as e:
        raise RuntimeError(f"Z.ai stream error: {e}")


# ---------------------------------------------------------------------------
# Groq backend (prioridad 2 — tier gratuito generoso)
# ---------------------------------------------------------------------------

def _groq_chat(messages: list, model: str, tools: list | None = None) -> dict:
    from inference_errors import classify_error

    last_error: Exception = RuntimeError("Unknown error")

    for attempt in range(1, INFERENCE_RETRY_ATTEMPTS + 1):
        try:
            client = _get_groq_client()
            kwargs = {
                "model": model,
                "messages": messages,
                "timeout": GROQ_TIMEOUT,
            }
            if tools:
                oai_tools = _convert_tools_to_openai(tools)
                if oai_tools:
                    kwargs["tools"] = oai_tools

            response = client.chat.completions.create(**kwargs)
            msg = response.choices[0].message

            result = {"content": msg.content or ""}
            if msg.tool_calls:
                result["tool_calls"] = [
                    {
                        "function": {
                            "name": tc.function.name,
                            "arguments": json.loads(tc.function.arguments)
                            if isinstance(tc.function.arguments, str)
                            else tc.function.arguments,
                        }
                    }
                    for tc in msg.tool_calls
                ]
            return result

        except Exception as e:
            last_error = RuntimeError(f"Groq error: {e}")
            classified = classify_error(last_error)
            logger.warning(
                "Groq attempt %d/%d [%s]: %s -> %s",
                attempt, INFERENCE_RETRY_ATTEMPTS,
                classified.category.value,
                str(last_error)[:100],
                classified.recovery_action,
            )
            if not classified.retryable:
                break
            if classified.retry_delay > 0 and attempt < INFERENCE_RETRY_ATTEMPTS:
                import time
                time.sleep(min(classified.retry_delay * (2 ** (attempt - 1)), 30))

    raise last_error


def _groq_chat_stream(messages: list, model: str) -> Generator:
    try:
        client = _get_groq_client()
        stream = client.chat.completions.create(
            model=model,
            messages=messages,
            stream=True,
            timeout=GROQ_TIMEOUT,
        )
        for chunk in stream:
            if chunk.choices and chunk.choices[0].delta.content:
                yield chunk.choices[0].delta.content
    except Exception as e:
        raise RuntimeError(f"Groq stream error: {e}")


# ---------------------------------------------------------------------------
# Google AI (Gemini) backend — prioridad 3
# ---------------------------------------------------------------------------

def _google_chat(messages: list, model: str, tools: list | None = None) -> dict:
    from inference_errors import classify_error

    last_error: Exception = RuntimeError("Unknown error")

    for attempt in range(1, INFERENCE_RETRY_ATTEMPTS + 1):
        try:
            client = _get_google_client()
            kwargs = {
                "model": model,
                "messages": messages,
                "timeout": GOOGLE_AI_TIMEOUT,
            }
            if tools:
                oai_tools = _convert_tools_to_openai(tools)
                if oai_tools:
                    kwargs["tools"] = oai_tools

            response = client.chat.completions.create(**kwargs)
            msg = response.choices[0].message

            result = {"content": msg.content or ""}
            if msg.tool_calls:
                result["tool_calls"] = [
                    {
                        "function": {
                            "name": tc.function.name,
                            "arguments": json.loads(tc.function.arguments)
                            if isinstance(tc.function.arguments, str)
                            else tc.function.arguments,
                        }
                    }
                    for tc in msg.tool_calls
                ]
            return result

        except Exception as e:
            last_error = RuntimeError(f"Google AI error: {e}")
            classified = classify_error(last_error)
            logger.warning(
                "Google AI attempt %d/%d [%s]: %s -> %s",
                attempt, INFERENCE_RETRY_ATTEMPTS,
                classified.category.value,
                str(last_error)[:100],
                classified.recovery_action,
            )
            if not classified.retryable:
                break
            if classified.retry_delay > 0 and attempt < INFERENCE_RETRY_ATTEMPTS:
                import time
                time.sleep(min(classified.retry_delay * (2 ** (attempt - 1)), 30))

    raise last_error


def _google_chat_stream(messages: list, model: str) -> Generator:
    try:
        client = _get_google_client()
        stream = client.chat.completions.create(
            model=model,
            messages=messages,
            stream=True,
            timeout=GOOGLE_AI_TIMEOUT,
        )
        for chunk in stream:
            if chunk.choices and chunk.choices[0].delta.content:
                yield chunk.choices[0].delta.content
    except Exception as e:
        raise RuntimeError(f"Google AI stream error: {e}")


def _convert_tools_to_openai(ollama_tools: list) -> list:
    """Convert Ollama tool format to OpenAI tool format."""
    oai_tools = []
    for tool in ollama_tools:
        if "function" in tool:
            oai_tools.append({"type": "function", "function": tool["function"]})
        elif "type" in tool and tool["type"] == "function":
            oai_tools.append(tool)
        else:
            oai_tools.append({"type": "function", "function": tool})
    return oai_tools


# ---------------------------------------------------------------------------
# Ollama backend
# ---------------------------------------------------------------------------

def _post_chat(payload: dict) -> dict:
    """Envía un request a /api/chat con reintentos y clasificación de errores."""
    from inference_errors import classify_error

    last_error: Exception = RuntimeError("Unknown error")

    for attempt in range(1, INFERENCE_RETRY_ATTEMPTS + 1):
        try:
            with httpx.Client(timeout=OLLAMA_TIMEOUT) as client:
                r = client.post(f"{_OLLAMA_URL}/api/chat", json=payload)
                r.raise_for_status()
                return r.json()
        except httpx.ConnectError:
            last_error = ConnectionError(
                f"GPU node offline at {_OLLAMA_URL}. Is the main PC on and Ollama running?"
            )
        except httpx.TimeoutException:
            last_error = TimeoutError(
                f"GPU node timed out after {OLLAMA_TIMEOUT}s. Model may still be loading."
            )
        except httpx.HTTPStatusError as e:
            last_error = RuntimeError(f"HTTP {e.response.status_code}: {e.response.text[:200]}")
        except Exception as e:
            last_error = RuntimeError(f"Inference error: {e}")

        classified = classify_error(last_error)
        logger.warning(
            "Attempt %d/%d [%s]: %s -> %s",
            attempt, INFERENCE_RETRY_ATTEMPTS,
            classified.category.value,
            str(last_error)[:100],
            classified.recovery_action,
        )

        if not classified.retryable:
            break

        if classified.retry_delay > 0 and attempt < INFERENCE_RETRY_ATTEMPTS:
            import time
            delay = classified.retry_delay * (2 ** (attempt - 1))
            time.sleep(min(delay, 30))

    raise last_error


# ---------------------------------------------------------------------------
# Public API — auto-selects backend
# ---------------------------------------------------------------------------

def chat(messages: list, model: str | None = None) -> str:
    if _USE_OPENROUTER:
        try:
            result = _openrouter_chat(messages, _resolve_openrouter_model(model))
            return result["content"]
        except Exception as e:
            logger.warning("OpenRouter falló, intentando Groq: %s", e)
    if _USE_GROQ:
        try:
            result = _groq_chat(messages, GROQ_MODEL)
            return result["content"]
        except Exception as e:
            logger.warning("Groq falló, intentando Google AI: %s", e)
    if _USE_GOOGLE:
        try:
            result = _google_chat(messages, GOOGLE_AI_CHAT_MODEL)
            return result["content"]
        except Exception as e:
            logger.warning("Google AI falló, intentando Z.ai: %s", e)
    if _USE_ZAI:
        try:
            result = _zai_chat(messages, _resolve_zai_model(model))
            return result["content"]
        except Exception as e:
            logger.warning("Z.ai falló, intentando Ollama: %s", e)
    data = _post_chat({"model": model or OLLAMA_MODEL, "messages": messages, "stream": False})
    return data["message"]["content"]


def chat_with_tools(messages: list, tools: list, model: str | None = None) -> dict:
    """Chat con soporte de tool calling. Retorna el dict message completo."""
    if _USE_OPENROUTER:
        try:
            return _openrouter_chat(messages, _resolve_openrouter_model(model), tools=tools)
        except Exception as e:
            logger.warning("OpenRouter falló en tool call, intentando Groq: %s", e)
    if _USE_GROQ:
        try:
            return _groq_chat(messages, GROQ_MODEL, tools=tools)
        except Exception as e:
            logger.warning("Groq falló en tool call, intentando Google AI: %s", e)
    if _USE_GOOGLE:
        try:
            return _google_chat(messages, GOOGLE_AI_CHAT_MODEL, tools=tools)
        except Exception as e:
            logger.warning("Google AI falló en tool call, intentando Z.ai: %s", e)
    if _USE_ZAI:
        try:
            return _zai_chat(messages, _resolve_zai_model(model), tools=tools)
        except Exception as e:
            logger.warning("Z.ai falló en tool call, intentando Ollama: %s", e)
    payload = {"model": model or OLLAMA_MODEL, "messages": messages, "stream": False}
    if tools:
        payload["tools"] = tools
    data = _post_chat(payload)
    return data.get("message", {})


def chat_with_images(messages: list, images: list[str], model: str | None = None) -> str:
    """Chat con imágenes (base64). Para modelos de visión como LLaVA."""
    # OpenRouter y Z.ai usan el mismo formato de imagen
    if _USE_OPENROUTER or _USE_ZAI:
        src_messages = []
        for msg in messages:
            src_messages.append(dict(msg))
        if src_messages and images:
            last = src_messages[-1]
            content_parts = [{"type": "text", "text": last.get("content", "")}]
            for img in images:
                content_parts.append({
                    "type": "image_url",
                    "image_url": {"url": f"data:image/jpeg;base64,{img}"},
                })
            last["content"] = content_parts
        if _USE_OPENROUTER:
            result = _openrouter_chat(src_messages, _resolve_openrouter_model(model))
        else:
            result = _zai_chat(src_messages, _resolve_zai_model(model))
        return result["content"]

    if messages and images:
        messages = list(messages)
        last_msg = dict(messages[-1])
        last_msg["images"] = images
        messages[-1] = last_msg
    data = _post_chat({"model": model or OLLAMA_MODEL, "messages": messages, "stream": False})
    return data["message"]["content"]


def chat_stream(messages: list, model: str | None = None) -> Generator:
    if _USE_OPENROUTER:
        try:
            yield from _openrouter_chat_stream(messages, _resolve_openrouter_model(model))
            return
        except Exception as e:
            logger.warning("OpenRouter stream falló, intentando Groq: %s", e)
    if _USE_GROQ:
        try:
            yield from _groq_chat_stream(messages, GROQ_MODEL)
            return
        except Exception as e:
            logger.warning("Groq stream falló, intentando Google AI: %s", e)
    if _USE_GOOGLE:
        try:
            yield from _google_chat_stream(messages, GOOGLE_AI_CHAT_MODEL)
            return
        except Exception as e:
            logger.warning("Google AI stream falló, intentando Z.ai: %s", e)
    if _USE_ZAI:
        try:
            yield from _zai_chat_stream(messages, _resolve_zai_model(model))
            return
        except Exception as e:
            logger.warning("Z.ai stream falló, intentando Ollama: %s", e)
    try:
        with httpx.Client(timeout=OLLAMA_TIMEOUT) as client:
            with client.stream(
                "POST",
                f"{_OLLAMA_URL}/api/chat",
                json={"model": model or OLLAMA_MODEL, "messages": messages, "stream": True},
            ) as r:
                r.raise_for_status()
                for line in r.iter_lines():
                    if not line:
                        continue
                    chunk = json.loads(line)
                    if not chunk.get("done") and "message" in chunk:
                        yield chunk["message"]["content"]
    except httpx.ConnectError:
        raise ConnectionError(f"GPU node offline at {_OLLAMA_URL}")
    except httpx.TimeoutException:
        raise TimeoutError(f"GPU node timed out after {OLLAMA_TIMEOUT}s")
    except Exception as e:
        raise RuntimeError(f"Stream error: {e}")
