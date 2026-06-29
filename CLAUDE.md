# Hermes — Contexto del Proyecto para Claude Code

## Estado — Sesión 2026-06-29 (PAUSADO)

### ✅ Completado
- Merge de `claude/fervent-euler-7v5g1u` → `master` (5484 inserciones: governance, reasoning, context, video pipeline, SadTalker, kanban, etc.)
- `pip install -r requirements.txt` — todo OK excepto `TTS>=0.22.0` (comentado, no soporta Python 3.13; ya existe `edge-tts`)
- `openai-whisper` instalado
- Todos los imports verificados: soul, governance, reasoning, context, inference_errors, budget_manager

### ⏳ Pendiente en Lenovo (192.168.1.100) — requiere SSH
```bash
# 1. Modelo de visión
ollama pull obsidian:3b

# 2. Cron jobs (pegar en terminal SSH)
(crontab -l 2>/dev/null; echo "0 3 * * * cd ~/hermes/brain && python3 learning/reflexion_diaria.py >> ~/hermes/logs/reflexion.log 2>&1"; echo "30 3 * * * cd ~/hermes/brain && python3 learning/debate_sintetico.py >> ~/hermes/logs/debate.log 2>&1") | crontab -

# 3. SadTalker
cd ~ && git clone https://github.com/OpenTalker/SadTalker.git
cd SadTalker && pip install -r requirements.txt && bash scripts/download_models.sh
```

### ✅ Z.ai integrado (2026-06-29)
- `ZAI_API_KEY` y `ZAI_MODEL=glm-4.5-air` seteados en `brain/.env`
- Backend dual activo: Z.ai cuando hay key, Ollama como fallback
- ⚠️ Cuenta Z.ai sin saldo — recargar en z.ai para activar; mientras tanto usa Gemini

### ⏳ Pendiente en brain/.env (este PC)
```
VISION_MODEL=obsidian:3b
SADTALKER_PATH=/home/cris/SadTalker   # ajustar ruta real en Lenovo
HERMES_AVATAR_IMAGE=/ruta/a/avatar.jpg
WHISPER_MODEL_SIZE=small               # o medium si querés mejor calidad
```

---

## ¿Qué es Hermes?

Asistente de IA personal que responde por **Telegram**. Puede:
- Descargar y replicar videos virales (TikTok → guión → TTS → video nuevo)
- Buscar en internet, scrapear páginas
- Leer/escribir notas en Obsidian (vault sincronizado)
- Publicar en YouTube
- Administrar Google Calendar, email, GitHub
- Ejecutar tareas en background y cron jobs

---

## Arquitectura: DOS máquinas

```
[PC Principal — Windows C:\Users\Cris]          [Lenovo — GPU Node 192.168.1.100]
  Corre: Telegram bot (hermes brain)    <──>      Corre: Ollama (modelos de IA)
  Desarrollo con Claude Code                       WSL2 Ubuntu, SSH activo
  Conecta a Lenovo via SSH                         También puede correr hermes brain
                                                   como servicio Linux (secundario)
```

- El bot en Windows le habla a Ollama en la Lenovo por `http://192.168.1.100:11434`
- Si la Lenovo está apagada → fallback automático a Google Gemini (`GOOGLE_AI_API_KEY`)
- Modelo LLM por defecto: `qwen2.5:7b` (configurable en `.env`)

---

## Cómo arrancar el bot (en este PC)

```powershell
# Primera vez: instalar dependencias
C:\Users\Cris\hermes\venv\Scripts\pip.exe install -r C:\Users\Cris\hermes\brain\requirements.txt

# Arrancar el bot (en segundo plano)
# IMPORTANTE: usar python.exe, NO pythonw.exe — pythonw cae silenciosamente en Windows con asyncio
Start-Process -FilePath "C:\Users\Cris\hermes\venv\Scripts\python.exe" `
  -ArgumentList "C:\Users\Cris\hermes\brain\main.py" `
  -WorkingDirectory "C:\Users\Cris\hermes\brain" `
  -WindowStyle Hidden `
  -RedirectStandardError "C:\Users\Cris\hermes\logs\hermes_err.log"

# Ver logs en vivo
Get-Content C:\Users\Cris\hermes\logs\hermes.log -Wait -Tail 30
```

### Para conectar a la Lenovo via SSH
```powershell
ssh cris@192.168.1.100   # o la IP que tenga la Lenovo
```

---

## Estructura de carpetas

```
hermes/
├── brain/                  ← TODO el código Python del bot
│   ├── main.py             ← ENTRYPOINT: arranca bot Telegram o servidor HTTP
│   ├── config.py           ← Toda la configuración (lee brain/.env)
│   ├── assistant.py        ← Lógica central del asistente (respond, RAG, tools)
│   ├── inference_client.py ← Cliente Ollama + fallback Google Gemini
│   ├── memory.py           ← Historial de conversación (SQLite)
│   ├── self_improvement.py ← Auto-mejora desde conversaciones
│   ├── .env                ← Variables de entorno (NO commitear)
│   ├── requirements.txt    ← Dependencias Python
│   │
│   ├── interface/
│   │   └── telegram_bot.py ← Bot de Telegram (comandos, handlers)
│   │
│   ├── video/              ← Pipeline de video viral
│   │   ├── pipeline.py     ← Orquestador: download→transcribe→script→TTS→video
│   │   ├── analyzer.py     ← Analiza estructura del video viral, genera guión
│   │   ├── assembler.py    ← Ensambla audio+clips+subtítulos en video final
│   │   ├── tts.py          ← Text-to-Speech (Edge-TTS o Voxtral)
│   │   ├── stock.py        ← Busca y descarga stock footage (Pexels/Pixabay)
│   │   └── google_ai.py    ← Genera imágenes/video con Google Imagen/Veo
│   │
│   ├── social/             ← Publicación en redes
│   │   ├── publisher.py    ← Orquestador multi-plataforma
│   │   └── youtube.py      ← Upload a YouTube (OAuth2 + resumable upload)
│   │
│   ├── media/              ← Descarga y análisis de media
│   │   ├── downloader.py   ← yt-dlp: descarga videos de TikTok/YT/etc
│   │   ├── transcriber.py  ← Whisper: audio → texto
│   │   └── vision.py       ← LLaVA: analiza frames del video
│   │
│   ├── rag/                ← Búsqueda semántica en Obsidian vault
│   │   ├── indexer.py      ← Indexa notas .md en ChromaDB
│   │   ├── searcher.py     ← Búsqueda semántica + contexto para el LLM
│   │   └── graph.py        ← Knowledge graph de wiki-links entre notas
│   │
│   ├── tools/              ← Herramientas que el LLM puede invocar (tool calling)
│   │   ├── web_tool.py     ← Búsqueda web + fetch de páginas
│   │   ├── vault_tool.py   ← Leer/escribir notas Obsidian
│   │   ├── video_tool.py   ← Replicar viral, generar video, analizar
│   │   ├── social_tool.py  ← Publicar contenido
│   │   ├── memory_tool.py  ← Recordar y buscar información
│   │   ├── calendar_tool.py← Google Calendar
│   │   ├── email_tool.py   ← Gmail (leer/enviar)
│   │   ├── github_tool.py  ← GitHub API
│   │   ├── cron_tool.py    ← Crear/listar/borrar cron jobs
│   │   ├── task_tool.py    ← Tareas en background
│   │   ├── director_tool.py← Multi-agente: descompone tareas complejas
│   │   └── ...             ← strategy, automation, spec, graph, etc.
│   │
│   ├── web/                ← Navegación web
│   │   ├── search.py       ← DuckDuckGo search
│   │   ├── scraper.py      ← Scraper estático (httpx + BeautifulSoup)
│   │   └── browser.py      ← Playwright (renderiza JS)
│   │
│   ├── learning/           ← Auto-mejora y logging de interacciones
│   ├── agents/             ← Orquestador multi-agente
│   ├── background/         ← Scheduler de cron jobs
│   ├── specs/              ← Spec-driven development
│   ├── integrations/       ← Google Calendar, GitHub, Email (clientes raw)
│   ├── automation/         ← Automatización de contenido (nichos, batch, etc.)
│   ├── strategy/           ← Frameworks de análisis estratégico
│   └── design/             ← Generación de landing pages / HTML
│
├── scripts/                ← Scripts de setup e infraestructura
│   │
│   ├── — PARA ESTE PC (Windows) —
│   ├── ssh_setup.ps1           ← Genera clave SSH para conectar a Lenovo
│   ├── crear_vault.ps1         ← Crea la estructura del vault Obsidian
│   ├── save_session.py         ← Guarda sesión de conversación
│   │
│   ├── — PARA LENOVO (setup inicial, correr UNA VEZ) —
│   ├── lenovo_setup_inicial.ps1← Setup SSH + WSL2 en la Lenovo (PowerShell Admin)
│   ├── setup_wsl2_lenovo.ps1   ← Configura WSL2/Ubuntu en la Lenovo
│   ├── setup_mdns.sh           ← mDNS para acceder por nombre en vez de IP
│   ├── setup_static_ip.sh      ← IP estática para que la Lenovo siempre sea .100
│   ├── syncthing-config-lenovo.xml ← Sync de archivos entre PCs via Syncthing
│   │
│   ├── — PARA LENOVO (hermes como servicio Linux) —
│   ├── deploy_brain.sh         ← Copia el brain a /opt/hermes-assistant en Lenovo
│   ├── setup_autostart.sh      ← Instala hermes.service en systemd (Linux)
│   ├── auto_update.sh          ← Pull automático desde git + restart del servicio
│   ├── hermes.service          ← Definición del servicio systemd
│   ├── hermes-updater.service  ← Servicio auto-update
│   ├── hermes-updater.timer    ← Timer: corre auto_update cada 5 min
│   ├── monitor.sh              ← Monitor de logs del servicio Linux
│   │
│   └── — OBSOLETOS (rutas C:\Users\chsan ya no existen) —
│       ├── nightly.bat             ← Usar nightly_learning.py directamente
│       ├── start_hermes_v2.bat     ← Ver "Cómo arrancar el bot" arriba
│       ├── desplegar_v2.ps1        ← Reemplazado por deploy_brain.sh
│       └── instalar_dependencias_v2.ps1 ← Usar pip install -r requirements.txt
│
├── logs/                   ← Logs del bot (hermes.log, hermes_err.log)
├── venv/                   ← Entorno virtual Python (no commitear)
├── watchdog.py             ← OBSOLETO (rutas C:\Users\chsan) — no usar
├── restart_bot.vbs         ← OBSOLETO (rutas C:\Users\chsan) — no usar
└── run_graph.py            ← Utilidad para explorar el knowledge graph
```

---

## Variables de entorno clave (brain/.env)

| Variable | Descripción | Requerida |
|---|---|---|
| `TELEGRAM_TOKEN` | Token del bot de Telegram | Sí |
| `TELEGRAM_ALLOWED_USERS` | IDs de usuarios autorizados (comma-separated) | Sí |
| `GPU_NODE_HOST` | IP de la Lenovo (default: 192.168.1.100) | Sí |
| `OLLAMA_MODEL` | Modelo LLM (default: qwen2.5:7b) | No |
| `GOOGLE_AI_API_KEY` | Gemini — fallback si Lenovo está offline | Recomendado |
| `VAULT_PATH` | Ruta al vault de Obsidian | Para RAG |
| `YOUTUBE_CLIENT_ID/SECRET/REFRESH_TOKEN` | OAuth YouTube | Para publicar |
| `GITHUB_TOKEN` | Token GitHub | Para tools GitHub |
| `GOOGLE_AI_API_KEY` | También para Imagen/Veo (generación de imágenes) | Para video AI |

---

## Comandos del bot (Telegram)

| Comando | Descripción |
|---|---|
| `/viral [URL] [tema]` | Replica video viral con nuevo tema |
| `/remember [texto]` | Guarda nota en Obsidian |
| `/improve` | Auto-mejora analizando conversaciones recientes |
| `/voice` | Activa/desactiva respuestas por audio |
| `/status` | Estado del GPU node (Lenovo) y modelo activo |
| `/tools` | Lista herramientas cargadas |
| `/logs` | Ver logs recientes (sube a GitHub Gist) |
| `/clear` | Borrar historial de conversación |
| `/new` | Nueva sesión |

---

## Flujo del comando /viral

```
URL TikTok
  → yt-dlp descarga video + audio
  → Whisper transcribe audio
  → LLaVA analiza frames
  → LLM analiza estructura viral
  → Web search sobre el tema nuevo
  → LLM genera guión nuevo
  → Edge-TTS genera narración + subtítulos .srt
  → Pexels/Pixabay busca stock footage
  → ffmpeg ensambla video final
  → Comprime a ≤20MB para Telegram
  → Sube a Telegram + intenta publicar en YouTube
```

---

## Problemas frecuentes

| Síntoma | Causa | Solución |
|---|---|---|
| "GPU node offline" | Lenovo apagada o Ollama no corre | Encender Lenovo, `ollama serve` en WSL2 |
| YouTube: error | Falta `YOUTUBE_REFRESH_TOKEN` en .env | Configurar OAuth YouTube |
| Bot no arranca | `TELEGRAM_TOKEN` no cargado | Verificar brain/.env |
| Hermes responde como LLM genérico | Modelo rompió personaje | El bot reintenta automáticamente; si persiste, reiniciar |
| Video nunca se genera | `require_approval=True` en pipeline | Ya corregido — era un bug |

---

## Notas de desarrollo

- **Editar y probar**: modificar archivos en `brain/`, reiniciar el proceso Python
- **Agregar herramientas**: crear `brain/tools/nueva_tool.py` y registrarla en `assistant.py` → `_get_registry()`
- **Logs**: `C:\Users\Cris\hermes\logs\hermes.log`
- El `.env` está en `brain/.env` — nunca commitear
- El venv está en `hermes/venv/` — nunca commitear
