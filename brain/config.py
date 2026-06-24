import os
from pathlib import Path

try:
    from dotenv import load_dotenv
    load_dotenv(Path(__file__).parent / ".env")
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
BASE_DIR = Path(__file__).parent
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
VAULT_PATH = os.getenv("VAULT_PATH", r"C:\Users\chsan\hermes-vault")
CHROMA_PATH = os.getenv("CHROMA_PATH", str(DATA_DIR / "chromadb"))
RAG_ENABLED = os.getenv("RAG_ENABLED", "true").lower() == "true"

# Self-learning
LOGS_DIR = os.getenv("LOGS_DIR", str(BASE_DIR.parent / "logs" / "interacciones"))
SKILLS_PATH = os.getenv("SKILLS_PATH", str(BASE_DIR.parent / "skills.yaml"))
MAX_SKILLS = int(os.getenv("MAX_SKILLS", "25"))
LEARNING_ENABLED = os.getenv("LEARNING_ENABLED", "true").lower() == "true"

# Web browsing
WEB_ENABLED = os.getenv("WEB_ENABLED", "true").lower() == "true"
WEB_SEARCH_REGION = os.getenv("WEB_SEARCH_REGION", "es-ar")
WEB_SEARCH_MAX_RESULTS = int(os.getenv("WEB_SEARCH_MAX_RESULTS", "5"))
WEB_USE_BROWSER = os.getenv("WEB_USE_BROWSER", "false").lower() == "true"
