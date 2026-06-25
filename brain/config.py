import os
from pathlib import Path

try:
    from dotenv import load_dotenv
    load_dotenv(Path(__file__).resolve().parent / ".env")
except ImportError:
    pass

# GPU Node (Main PC with Ollama)
GPU_NODE_HOST = os.getenv("GPU_NODE_HOST", "192.168.1.100")
GPU_NODE_PORT = int(os.getenv("GPU_NODE_PORT", "11434"))
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "qwen2.5:7b")
OLLAMA_TIMEOUT = int(os.getenv("OLLAMA_TIMEOUT", "120"))
INFERENCE_RETRY_ATTEMPTS = int(os.getenv("INFERENCE_RETRY_ATTEMPTS", "2"))

# Assistant identity
ASSISTANT_NAME = os.getenv("ASSISTANT_NAME", "Hermes")
MAX_HISTORY_MESSAGES = int(os.getenv("MAX_HISTORY", "20"))
SYSTEM_PROMPT = os.getenv(
    "SYSTEM_PROMPT",
    f"You are {ASSISTANT_NAME}, a concise and helpful AI assistant running on a home server. "
    "Be accurate, brief, and honest. If you are unsure about something, say so.",
)

# Paths
BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"
DB_PATH = DATA_DIR / "hermes.db"

# HTTP API server
API_HOST = os.getenv("API_HOST", "0.0.0.0")
API_PORT = int(os.getenv("API_PORT", "8080"))
API_SECRET = os.getenv("API_SECRET", "")

# Telegram bot (optional)
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN", "")
TELEGRAM_ALLOWED_USERS = [
    u.strip() for u in os.getenv("TELEGRAM_ALLOWED_USERS", "").split(",") if u.strip()
]

# Vault & RAG
VAULT_PATH = os.getenv("VAULT_PATH", str(Path.home() / "hermes-vault"))
CHROMA_PATH = os.getenv("CHROMA_PATH", str(DATA_DIR / "chromadb"))
RAG_ENABLED = os.getenv("RAG_ENABLED", "true").lower() == "true"

# Self-learning
LOGS_DIR = os.getenv("LOGS_DIR", str(BASE_DIR.parent / "logs" / "interacciones"))
SKILLS_PATH = os.getenv("SKILLS_PATH", str(BASE_DIR.parent / "skills.yaml"))
MAX_SKILLS = int(os.getenv("MAX_SKILLS", "25"))
LEARNING_ENABLED = os.getenv("LEARNING_ENABLED", "true").lower() == "true"

# Tool calling
TOOL_CALLING_ENABLED = os.getenv("TOOL_CALLING_ENABLED", "true").lower() == "true"
TOOL_MAX_ITERATIONS = int(os.getenv("TOOL_MAX_ITERATIONS", "5"))

# Multi-agent
AGENTS_ENABLED = os.getenv("AGENTS_ENABLED", "true").lower() == "true"

# Media analysis
MEDIA_DOWNLOAD_DIR = os.getenv("MEDIA_DOWNLOAD_DIR", str(DATA_DIR / "media"))
MEDIA_MAX_DURATION = int(os.getenv("MEDIA_MAX_DURATION", "600"))
WHISPER_MODEL_SIZE = os.getenv("WHISPER_MODEL_SIZE", "base")
WHISPER_DEVICE = os.getenv("WHISPER_DEVICE", "cpu")
VISION_MODEL = os.getenv("VISION_MODEL", "llava")
VISION_FRAMES = int(os.getenv("VISION_FRAMES", "4"))

# System commands (allowlist)
ALLOWED_COMMANDS = [
    c.strip() for c in os.getenv(
        "ALLOWED_COMMANDS",
        "df,free,uptime,docker ps,systemctl status,ls,cat,head,tail,wc,date,whoami,hostname,ip addr"
    ).split(",") if c.strip()
]

# TTS / Voice
TTS_BACKEND = os.getenv("TTS_BACKEND", "edge")  # "edge" (gratis) o "voxtral" (premium)
MISTRAL_API_KEY = os.getenv("MISTRAL_API_KEY", "")

# Google Stitch (AI UI design)
STITCH_API_KEY = os.getenv("STITCH_API_KEY", "")

# Social media publishing
YOUTUBE_CLIENT_ID = os.getenv("YOUTUBE_CLIENT_ID", "")
YOUTUBE_CLIENT_SECRET = os.getenv("YOUTUBE_CLIENT_SECRET", "")
YOUTUBE_REFRESH_TOKEN = os.getenv("YOUTUBE_REFRESH_TOKEN", "")
MAKE_WEBHOOK_URL = os.getenv("MAKE_WEBHOOK_URL", "")

# Web browsing
WEB_ENABLED = os.getenv("WEB_ENABLED", "true").lower() == "true"
WEB_SEARCH_REGION = os.getenv("WEB_SEARCH_REGION", "es-ar")
WEB_SEARCH_MAX_RESULTS = int(os.getenv("WEB_SEARCH_MAX_RESULTS", "5"))
WEB_USE_BROWSER = os.getenv("WEB_USE_BROWSER", "false").lower() == "true"
