"""Guarda el resumen de la sesión en GitHub como issue."""
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'brain'))

try:
    from dotenv import load_dotenv
    from pathlib import Path
    load_dotenv(Path(__file__).parent.parent / 'brain' / '.env')
except Exception:
    pass

import requests

token = os.getenv('GITHUB_TOKEN', '')
if not token:
    print('ERROR: GITHUB_TOKEN no configurado')
    sys.exit(1)

headers = {
    'Authorization': f'token {token}',
    'Accept': 'application/vnd.github.v3+json',
    'User-Agent': 'Hermes-AI-Assistant',
}

body_text = """## Resumen de sesion 2026-06-25

### Features implementadas
- **Gemini fallback**: si Ollama offline, usa gemini-2.0-flash automaticamente
- **Fecha en system prompt**: inyecta fecha/hora actual en cada respuesta
- **/status**, **/tools**, **/logs** (sube log a Gist privado)
- **/improve**: auto-mejora de comportamiento
  - Lee ultimas 80 interacciones de la DB
  - Las manda a Gemini con prompt de coach de IA
  - Guarda reglas en vault Obsidian (Hermes/Mejoras.md)
  - Las reglas se inyectan automaticamente en cada system prompt
- **GitHub tool**: ya integrado — lista repos, issues, PRs, lee archivos, crea issues

### Archivos nuevos/modificados
- `brain/self_improvement.py` (NUEVO)
- `brain/assistant.py` — `_load_memories()` carga mejoras del vault
- `brain/interface/telegram_bot.py` — /improve, /logs, /tools mejorado
- `brain/inference_client.py` — `chat_google()` + fallback en `respond()`

### Infraestructura
- SSH a Lenovo (192.168.0.182) via `~/.ssh/hermes_key`, user: chsan
- Bot corre via schtask `HermesBotStart` (requiere sesion interactiva Windows)
- Restart: `ssh -i ~/.ssh/hermes_key chsan@192.168.0.182 "powershell ..."`
- GPU node Ollama: 192.168.0.145:11434
- Log: C:\\Users\\chsan\\hermes\\logs\\hermes.log
- `drop_pending_updates=True`: mensajes antes del reinicio se descartan

### Pendiente
- [ ] Hermes mas rapido: Gemini como LLM primario (no solo fallback)
- [ ] Primera ejecucion real de /improve con conversaciones acumuladas
"""

payload = {
    'title': '[Sesion 2026-06-25] Auto-mejora, Gemini fallback, SSH Lenovo, comandos Telegram',
    'body': body_text,
}

r = requests.post(
    'https://api.github.com/repos/Lionfaion/hermes/issues',
    json=payload,
    headers=headers,
    timeout=15,
)
if r.ok:
    data = r.json()
    print(f"Issue creado: #{data['number']} — {data.get('html_url', '')}")
else:
    print(f"Error: {r.status_code} — {r.text[:300]}")
