"""
Hermes HTTP API Server
Provides a REST interface to the assistant so any device on the LAN can query it.
Runs as the default service mode when no Telegram token is configured.
"""
import logging
import secrets
from functools import wraps

from flask import Flask, request, jsonify, Response, stream_with_context

from assistant import HermesAssistant
from inference_client import is_online, list_models
from config import ASSISTANT_NAME, API_HOST, API_PORT, API_SECRET

app = Flask(__name__)
logger = logging.getLogger(__name__)
_sessions: dict = {}


def require_secret(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
        if API_SECRET:
            token = request.headers.get("X-API-Key", "")
            if not secrets.compare_digest(token, API_SECRET):
                return jsonify({"error": "Unauthorized"}), 401
        return f(*args, **kwargs)
    return wrapper


def _get_session(session_id: str) -> HermesAssistant:
    if session_id not in _sessions:
        _sessions[session_id] = HermesAssistant(session_id=session_id)
    return _sessions[session_id]


@app.route("/health")
def health():
    return jsonify({
        "status": "ok",
        "assistant": ASSISTANT_NAME,
        "gpu_node": "online" if is_online() else "offline",
    })


@app.route("/models")
@require_secret
def models():
    return jsonify({"models": list_models()})


@app.route("/chat", methods=["POST"])
@require_secret
def chat_endpoint():
    data = request.get_json(silent=True) or {}
    session_id = data.get("session_id", "default")
    message = data.get("message", "").strip()
    stream = data.get("stream", False)

    if not message:
        return jsonify({"error": "message is required"}), 400

    assistant = _get_session(session_id)

    if stream:
        def generate():
            for chunk in assistant.respond_stream(message):
                yield chunk
        return Response(stream_with_context(generate()), mimetype="text/plain")

    response = assistant.respond(message)
    return jsonify({"response": response, "session_id": session_id})


@app.route("/session/<session_id>", methods=["DELETE"])
@require_secret
def delete_session(session_id: str):
    if session_id in _sessions:
        _sessions[session_id].clear_memory()
        del _sessions[session_id]
    return jsonify({"cleared": session_id})


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    logger.info("Starting %s API on %s:%d", ASSISTANT_NAME, API_HOST, API_PORT)
    app.run(host=API_HOST, port=API_PORT, debug=False)
