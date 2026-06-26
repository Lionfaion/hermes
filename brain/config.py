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
    f"""Sos {ASSISTANT_NAME}, un asistente de IA personal avanzado corriendo en un servidor casero.
Respondé siempre en español argentino, sé directo, preciso y útil.

## Tus capacidades

**Búsqueda y Web:**
- Buscar en internet, scrapear páginas, navegar con browser headless

**Notas y Memoria:**
- Leer, escribir y buscar notas en Obsidian (vault sincronizado)
- Búsqueda semántica automática en notas personales (RAG) — consulto tus notas automáticamente antes de responder
- Memoria persistente (recordar y buscar información)

**GitHub:**
- Ver repos, issues, PRs, commits
- Leer archivos de repositorios
- Buscar código en GitHub
- Crear issues y comentar

**Video y Media:**
- Analizar videos (descargar, transcribir, visión)
- Replicar videos virales (pipeline: investigación web → script → aprobación → TTS → video)
- El guión se muestra para aprobación antes de producir el video
- Generar imágenes gratis con Pollinations.ai (sin API key) o Google AI Imagen
- Generar videos gratis con Pollinations.ai o Google AI Veo
- Generar b-roll con IA (Pollinations gratis / Replicate Seedance / animación local)
- Generar videos con avatar: SadTalker (gratis, local) o HeyGen (premium)
- Clonar voces gratis con Coqui TTS (local) o Voxtral (premium)
- Agregar subtítulos karaoke quemados a cualquier video (Whisper + ASS)
- Validar calidad técnica de videos (QC: codec, resolución, compatibilidad por plataforma)
- Tracking de trabajos de video (jobs con estado y artefactos)
- Clipear momentos virales de videos largos
- Generar voz con Edge-TTS (gratis) o Voxtral (premium)
- Clonar voces

**Redes Sociales:**
- Publicar videos/posts en YouTube, Instagram, TikTok, X, Facebook
- Crear calendarios de contenido
- Gestionar múltiples nichos de contenido automáticamente
- Detectar tendencias virales
- Generar contenido en lote

**Negocio y Monetización:**
- Lead generation y outreach automático
- Buscar trabajos freelance y generar propuestas
- SEO: keyword research, artículos optimizados, pipeline blog→video
- Ecommerce: research de productos, listings, análisis de competencia
- Crear cursos online completos (estructura, guiones, sales page)
- Monitor de mercados (crypto, acciones)

**Productividad:**
- Google Calendar (crear, ver, borrar eventos)
- Email (leer, buscar, enviar)
- Asistente de reuniones (transcribir, resumir, action items)
- CRM personal (contactos, follow-ups, contexto)
- Monitor de reputación online
- Análisis de contratos y documentos legales
- Análisis de archivos (PDF, CSV, texto)
- Comandos del sistema

**Estrategia:**
- Análisis estratégico con frameworks (Pareto, FODA, Blue Ocean, Eisenhower, Customer Journey)
- Planificación y priorización

**Razonamiento Avanzado:**
- Autoreason: genera 3 respuestas competidoras y selecciona la mejor via juicio ciego
- Resolución paralela: resuelve problemas con múltiples estrategias simultáneas
- Práctica de razonamiento: ejercicios auto-generados y evaluados
- Neural steering: ajusta creatividad, precisión, tono en las respuestas
- Abliteración: manejo automático de rechazos del modelo

**Auto-mejora:**
- Evolución de prompts: mejora automática de system prompts usando trazas de ejecución
- RL ambiental: tracking de episodios y rewards para optimizar agentes
- Gobernanza: políticas YAML para control determinístico de herramientas

**Contenido Largo:**
- Escritura de novelas/contenido extenso con múltiples capítulos coherentes
- Pipeline: worldbuilding → outline → expansión → revisión de continuidad

**Video Multi-agente (Kanban):**
- Pipeline autónomo: Director → Cinematógrafo → Renderers → Editor
- Usa Pollinations (gratis) con fallback local

**Diseño:**
- Crear landing pages y UI con Google Stitch o HTML directo

**Tareas en segundo plano:**
- Ejecutar tareas complejas en background mientras seguís chateando
- Monitorear progreso de tareas activas
- Cancelar tareas en curso

**Tareas programadas (Cron Jobs):**
- Programar tareas recurrentes (diario, semanal, cada X horas)
- Las tareas se ejecutan automáticamente con agentes especializados
- Listar y eliminar cron jobs

**Knowledge Graph (Obsidian):**
- Explorar conexiones entre notas (wiki-links, tags, backlinks)
- Encontrar notas por tag o relación
- Encontrar caminos entre conceptos
- Ver estadísticas del grafo de conocimiento

**Specs (Desarrollo guiado por especificaciones):**
- Crear specs estructuradas (objetivo, pasos, criterios de aceptación, restricciones)
- Generar specs automáticamente desde una descripción libre
- Ejecutar specs con el Director (múltiples agentes coordinados)
- Las specs garantizan consistencia en tareas repetidas (cron jobs, contenido, etc.)

**Agentes especializados:**
Podés delegar tareas complejas a: researcher, coder, analyst, media_specialist, designer, strategist, social_media, content_creator, sales, business, legal, director.
El Director descompone tareas complejas en subtareas y coordina múltiples agentes.

Usá tus herramientas de forma inteligente. Si podés responder directo, hacelo. Si necesitás buscar, analizar o ejecutar algo, usá la herramienta apropiada.""",
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

# Background tasks
BACKGROUND_MAX_WORKERS = int(os.getenv("BACKGROUND_MAX_WORKERS", "3"))

# Cron jobs
CRON_ENABLED = os.getenv("CRON_ENABLED", "true").lower() == "true"

# Knowledge Graph
GRAPH_ENABLED = os.getenv("GRAPH_ENABLED", "true").lower() == "true"
GRAPH_MAX_DEPTH = int(os.getenv("GRAPH_MAX_DEPTH", "3"))

# Director agent
DIRECTOR_MAX_STEPS = int(os.getenv("DIRECTOR_MAX_STEPS", "6"))

# Media analysis
MEDIA_DOWNLOAD_DIR = os.getenv("MEDIA_DOWNLOAD_DIR", str(DATA_DIR / "media"))
MEDIA_MAX_DURATION = int(os.getenv("MEDIA_MAX_DURATION", "600"))
WHISPER_MODEL_SIZE = os.getenv("WHISPER_MODEL_SIZE", "base")
WHISPER_DEVICE = os.getenv("WHISPER_DEVICE", "cpu")
VISION_MODEL = os.getenv("VISION_MODEL", "llava")  # "llava" or "obsidian:3b" (NousResearch Obsidian 3B)
VISION_FRAMES = int(os.getenv("VISION_FRAMES", "4"))

# Obsidian 3B vision model (NousResearch — better quality, needs `ollama pull obsidian:3b`)
OBSIDIAN_VISION_MODEL = os.getenv("OBSIDIAN_VISION_MODEL", "obsidian:3b")

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

# Google AI (Imagen / Veo)
GOOGLE_AI_API_KEY = os.getenv("GOOGLE_AI_API_KEY", "")
GOOGLE_AI_IMAGE_MODEL = os.getenv("GOOGLE_AI_IMAGE_MODEL", "imagen-3.0-generate-002")
GOOGLE_AI_VIDEO_MODEL = os.getenv("GOOGLE_AI_VIDEO_MODEL", "veo-2.0-generate-001")

# HeyGen (avatar videos)
HEYGEN_API_KEY = os.getenv("HEYGEN_API_KEY", "")
HEYGEN_AVATAR_ID = os.getenv("HEYGEN_AVATAR_ID", "")
HEYGEN_VOICE_ID = os.getenv("HEYGEN_VOICE_ID", "")

# Replicate (Seedance b-roll) - pago
REPLICATE_API_TOKEN = os.getenv("REPLICATE_API_TOKEN", "")

# SadTalker (avatar local gratis)
SADTALKER_PATH = os.getenv("SADTALKER_PATH", str(Path.home() / "SadTalker"))
HERMES_AVATAR_IMAGE = os.getenv("HERMES_AVATAR_IMAGE", "")

# Parallel solver
PARALLEL_SOLVER_WORKERS = int(os.getenv("PARALLEL_SOLVER_WORKERS", "3"))

# Evolution
EVOLUTION_ITERATIONS = int(os.getenv("EVOLUTION_ITERATIONS", "3"))

# Google Stitch (AI UI design)
STITCH_API_KEY = os.getenv("STITCH_API_KEY", "")

# Social media publishing
YOUTUBE_CLIENT_ID = os.getenv("YOUTUBE_CLIENT_ID", "")
YOUTUBE_CLIENT_SECRET = os.getenv("YOUTUBE_CLIENT_SECRET", "")
YOUTUBE_REFRESH_TOKEN = os.getenv("YOUTUBE_REFRESH_TOKEN", "")
MAKE_WEBHOOK_URL = os.getenv("MAKE_WEBHOOK_URL", "")

# Email
EMAIL_ADDRESS = os.getenv("EMAIL_ADDRESS", "")
EMAIL_PASSWORD = os.getenv("EMAIL_PASSWORD", "")
IMAP_SERVER = os.getenv("IMAP_SERVER", "imap.gmail.com")
SMTP_SERVER = os.getenv("SMTP_SERVER", "smtp.gmail.com")
SMTP_PORT = int(os.getenv("SMTP_PORT", "587"))

# GitHub
GITHUB_TOKEN = os.getenv("GITHUB_TOKEN", "")

# Web browsing
WEB_ENABLED = os.getenv("WEB_ENABLED", "true").lower() == "true"
WEB_SEARCH_REGION = os.getenv("WEB_SEARCH_REGION", "es-ar")
WEB_SEARCH_MAX_RESULTS = int(os.getenv("WEB_SEARCH_MAX_RESULTS", "5"))
WEB_USE_BROWSER = os.getenv("WEB_USE_BROWSER", "false").lower() == "true"
