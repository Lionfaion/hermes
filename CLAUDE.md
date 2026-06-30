# Hermes — Contexto del Proyecto para Claude Code

## Estado — Sesión 2026-06-29 (COMPLETADA)

### ✅ Completado (2026-06-29)
- SSH sin contraseña desde este PC a Lenovo: `ssh lenovo` funciona directo
- No-sleep con tapa cerrada configurado en Lenovo (powercfg AC+DC)
- `~/.ssh/config` creado con alias `lenovo → chsan@192.168.0.182`
- `git pull` en Lenovo: 44 archivos, todo el código nuevo deployado
- `openai` instalado en Lenovo (necesario para OpenRouter)
- `.env` Lenovo actualizado: TOOL_CALLING_ENABLED=true, AGENTS_ENABLED=true, sin trailing spaces
- Bot corriendo en Lenovo (schtask HermesBotStart activo, polling Telegram OK)
- Arquitectura real documentada: bot en Lenovo, Ollama en este PC (192.168.0.145)
- Fallback OpenRouter → Z.ai → Ollama funcionando (probado con debate_sintetico)
- `debate_sintetico.py` completó 5 rondas exitosamente usando Ollama como fallback
- Notificación Telegram agregada a `debate_sintetico.py`
- `debate_sintetico.py`: delays de 4s entre turnos para evitar rate limit
- `inference_client.py`: cascada real con try/except en `chat()` y `chat_with_tools()`
- Bugs `chat_google` eliminados en `nightly_learning`, `self_improvement`, `video/analyzer`

### ⏳ Pendiente
- DHCP reservation en router (MAC `C0-38-96-5E-43-D7` → IP fija `192.168.0.182`) — usuario pendiente
- SadTalker (requiere dependencias pesadas, baja prioridad)
- Cargar saldo en Z.ai para tener segundo proveedor cloud operativo

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

## Arquitectura real del sistema

```
[Este PC — 192.168.0.145 (Cris)]              [Lenovo — 192.168.0.182 (chsan)]
  Ollama (GPU node, puerto 11434)      <──>    Bot Telegram corre acá 24/7
  Desarrollo con Claude Code                   Python: C:\Users\chsan\hermes-python\
  Repo: C:\Users\Cris\hermes                  Repo: C:\Users\chsan\hermes
                                               Vault: C:\Users\chsan\hermes-vault
                                               schtask: HermesBotStart
                                               schtask: HermesNightlyLearning (3am)
```

### Deploy flow
```
1. Desarrollar en este PC → git push
2. ssh lenovo "cd C:\Users\chsan\hermes && git pull origin master"
3. schtasks /run /tn HermesBotStart  (reinicia el bot)
```

### Cadena de inferencia (orden de prioridad)
```
1. OpenRouter → google/gemma-4-31b-it:free   ← primario (gratis, 50 req/día)
2. Z.ai → glm-4.5-air                        ← sin saldo actualmente
3. Ollama en ESTE PC → llama3.1:8b           ← fallback local (192.168.0.145:11434)
```
La cascada tiene try/except real: si uno falla, pasa al siguiente automáticamente.

---

## SSH a la Lenovo

```bash
# Conexión directa (sin contraseña, sin opciones):
ssh lenovo

# Ejecutar comando remoto:
ssh lenovo "comando"

# Ejecutar PowerShell remoto:
ssh lenovo "powershell.exe -Command \"...\""
```

Config en `~/.ssh/config`:
```
Host lenovo
    HostName 192.168.0.182
    User chsan
    IdentityFile ~/.ssh/hermes_key
    IdentitiesOnly yes
    ServerAliveInterval 30
    ServerAliveCountMax 3
    StrictHostKeyChecking no
```

⚠️ **IP puede cambiar** si la Lenovo se reconecta al router (pendiente DHCP reservation con MAC `C0-38-96-5E-43-D7`).

---

## Cómo arrancar el bot (en este PC)

```powershell
# Arrancar el bot (en segundo plano)
Start-Process -FilePath "C:\Users\Cris\hermes\venv\Scripts\python.exe" `
  -ArgumentList "C:\Users\Cris\hermes\brain\main.py" `
  -WorkingDirectory "C:\Users\Cris\hermes\brain" `
  -WindowStyle Hidden `
  -RedirectStandardError "C:\Users\Cris\hermes\logs\hermes_err.log"

# Ver logs en vivo
Get-Content C:\Users\Cris\hermes\logs\hermes.log -Wait -Tail 30
```

---

## Estructura de carpetas

```
hermes/
├── brain/                  ← TODO el código Python del bot
│   ├── main.py             ← ENTRYPOINT: arranca bot Telegram o servidor HTTP
│   ├── config.py           ← Toda la configuración (lee brain/.env)
│   ├── assistant.py        ← Lógica central del asistente (respond, RAG, tools)
│   ├── inference_client.py ← OpenRouter → Z.ai → Ollama → Gemini
│   ├── memory.py           ← Historial de conversación (SQLite)
│   ├── self_improvement.py ← Auto-mejora desde conversaciones
│   ├── .env                ← Variables de entorno (NO commitear)
│   ├── requirements.txt    ← Dependencias Python
│   │
│   ├── interface/
│   │   └── telegram_bot.py ← Bot de Telegram (comandos, handlers)
│   │
│   ├── video/              ← Pipeline de video viral
│   ├── social/             ← Publicación en redes
│   ├── media/              ← Descarga y análisis de media
│   ├── rag/                ← Búsqueda semántica en Obsidian vault
│   ├── tools/              ← Herramientas que el LLM puede invocar
│   ├── web/                ← Navegación web
│   ├── learning/           ← Auto-mejora y logging
│   ├── agents/             ← Multi-agente
│   ├── background/         ← Scheduler de cron jobs
│   └── ...
│
├── scripts/                ← Scripts de setup
├── logs/                   ← Logs del bot
├── venv/                   ← Entorno virtual Python (no commitear)
└── docs/                   ← Documentación y planes
```

---

## Variables de entorno clave (brain/.env)

| Variable | Descripción | Estado |
|---|---|---|
| `TELEGRAM_TOKEN` | Token del bot | ✅ configurado |
| `TELEGRAM_ALLOWED_USERS` | IDs autorizados | ✅ configurado |
| `GPU_NODE_HOST` | IP este PC/GPU node (192.168.0.145) | ✅ configurado en Lenovo |
| `OPENROUTER_API_KEY` | LLM primario | ✅ configurado |
| `GOOGLE_AI_API_KEY` | Gemini fallback | ✅ configurado |
| `ZAI_API_KEY` | Z.ai (sin saldo) | ⚠️ sin saldo |
| `GROQ_API_KEY` | Groq (llama-3.3-70b) | ✅ configurado |
| `VISION_MODEL` | obsidian:3b | ⏳ pendiente |
| `SADTALKER_PATH` | Ruta SadTalker | ⏳ pendiente |
| `WHISPER_MODEL_SIZE` | small/medium | ⏳ pendiente |

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
| `/logs` | Ver logs recientes |
| `/clear` | Borrar historial de conversación |

---

## Problemas frecuentes

| Síntoma | Causa | Solución |
|---|---|---|
| "GPU node offline" | Lenovo apagada o Ollama no corre | `ssh lenovo "ollama serve"` |
| Bot no arranca | `TELEGRAM_TOKEN` no cargado | Verificar brain/.env |
| IP Lenovo cambió | DHCP sin reserva | Ver `ssh lenovo "ipconfig"` y actualizar .env + ssh config |
| SSH rechaza clave | Usuario incorrecto | Usuario Lenovo es `chsan`, no `cris` |

---

## Notas de desarrollo

- **El bot corre en la Lenovo** (chsan@192.168.0.182), no en este PC
- **Ollama corre en ESTE PC** (192.168.0.145:11434), la Lenovo lo accede por red
- Usuario Windows de la Lenovo: **chsan** (no "cris")
- Los cron jobs de Linux no aplican — usar **Windows Task Scheduler** en Lenovo
- SadTalker requiere WSL2 o adaptación a Windows nativo
- El `.env` está en `brain/.env` — nunca commitear
- El venv está en `hermes/venv/` — nunca commitear
