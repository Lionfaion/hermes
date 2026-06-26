"""Guarda el resumen de la sesion en GitHub como issue."""
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

body_text = """## Rutina nocturna de aprendizaje automatico — 3am Argentina

### Que se implemento
- `brain/nightly_learning.py`: conversacion multi-turno con Gemini cada noche
  - Fase 1: analiza ultimas conversaciones, identifica 3-5 temas a aprender
  - Fase 2: por cada tema, 3 turnos con Gemini (explicacion, aplicacion, regla)
  - Fase 3: corre auto-mejora de comportamiento
  - Guarda en vault: `Hermes/Aprendizaje/YYYY-MM-DD.md` + `Hermes/Mejoras.md`
  - Envia notificacion Telegram al terminar
- `scripts/nightly.bat`: wrapper para schtask de Windows
- Schtask `HermesNightlyLearning` creado en Lenovo (03:00 AM diario)
- `TELEGRAM_CHAT_ID=8389062307` agregado al .env de Lenovo

### Actualizacion de modelo Gemini
- `gemini-2.0-flash` deprecado (404 NOT_FOUND desde jun 2026)
- Nuevo default en `brain/config.py`: `gemini-2.5-flash`
- Afecta: fallback de chat, self_improvement, nightly_learning

### Test exitoso
- Primera ejecucion manual: 2026-06-25 22:53
- 4 temas aprendidos, nota guardada en vault, Telegram notificado

### Archivos modificados/creados
- `brain/nightly_learning.py` (nuevo)
- `scripts/nightly.bat` (nuevo)
- `brain/config.py` — modelo gemini actualizado
- `brain/self_improvement.py` — del turno anterior
- `brain/assistant.py` — carga mejoras del vault
- `brain/interface/telegram_bot.py` — comando /improve

### Pendiente
- [ ] Hermes mas rapido: Gemini como LLM primario (no solo fallback)
"""

payload = {
    'title': '[2026-06-25] Rutina nocturna 3am: aprendizaje automatico + gemini-2.5-flash',
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
    print(f"Issue creado: #{data['number']} -- {data.get('html_url', '')}")
else:
    print(f"Error: {r.status_code} -- {r.text[:300]}")
