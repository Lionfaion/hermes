# Pipeline Viral - Fixes y Arquitectura

## Qué hace el pipeline

`/viral [URL] [tema]` en Telegram ejecuta 8 pasos:
1. Descarga el video original con yt-dlp
2. Transcribe el audio con Whisper
3. Analiza frames con vision (llava/ollama)
4. Analiza estructura viral con LLM
5. Genera nuevo guion sobre el tema nuevo
6. TTS con edge-tts (voz: es-ar-male)
7. Busca stock footage en Pexels (máx 1080p)
8. Ensambla con ffmpeg (ultrafast, crf=28)
9. Comprime si >20MB → sube a Telegram vía httpx directo
10. Publica en YouTube vía Make.com webhook

## Archivos clave

| Archivo | Función |
|---|---|
| `brain/video/pipeline.py` | Orquesta los 8 pasos |
| `brain/video/assembler.py` | ffmpeg + `compress_for_telegram()` |
| `brain/video/tts.py` | edge-tts, usa `get_srt()` no `generate_subs()` |
| `brain/video/stock.py` | Pexels API, cap 1080p |
| `brain/media/downloader.py` | yt-dlp, catch `MaxDownloadsReached` |
| `brain/interface/telegram_bot.py` | Comando `/viral`, upload httpx directo |
| `brain/config.py` | `BASE_DIR` con `.resolve()` para paths absolutos |

## Fixes críticos aplicados (jun 2026)

### WinError 5 Acceso Denegado en pipeline
- **Causa**: `.env` tenía `MEDIA_DOWNLOAD_DIR=data/media` (path relativo)
- **Efecto**: schtask arranca Python con CWD en `C:\Windows\System32` → intentaba crear `System32\data\media\` → sin permiso
- **Fix 1**: `.env` del Lenovo ahora tiene `MEDIA_DOWNLOAD_DIR=C:\Users\chsan\hermes\brain\data\media`
- **Fix 2**: `config.py` usa `BASE_DIR = Path(__file__).resolve().parent` para forzar absolute siempre

### Telegram Timed Out al subir video
- **Causa**: PTB (python-telegram-bot) `write_timeout` no se aplica correctamente a uploads multipart grandes
- **Fix**: `_send_video_direct()` en `telegram_bot.py` — POST httpx directo a `api.telegram.org/bot{token}/sendVideo` con `timeout=600s`, bypaseando PTB completamente

### yt-dlp MaxDownloadsReached
- **Causa**: yt-dlp lanza excepción DESPUÉS del 100% de descarga exitosa
- **Fix**: `except yt_dlp.utils.MaxDownloadsReached: pass` + buscar archivo descargado con `glob(f"{video_id}.*")`

### edge-tts API v7
- **Causa**: `submaker.generate_subs()` eliminado en v7+
- **Fix**: `submaker.get_srt() if hasattr(submaker, 'get_srt') else submaker.generate_subs()`

### Pexels 4K timeout en Lenovo
- **Causa**: Lenovo G50-70 no puede procesar videos 4K en tiempo razonable
- **Fix**: `stock.py` filtra archivos con `720 <= height <= 1080` en Pexels API

## Infraestructura del Lenovo

| Componente | Detalle |
|---|---|
| Bot Telegram | schtask `HermesBotStart`, Python PID ~9000+ |
| Vault API | `run_vault_api.vbs`, puerto 8091, PID ~8832 |
| ffmpeg | `C:\Users\chsan\ffmpeg\bin\` |
| Python | `C:\Users\chsan\hermes-python\python.exe` |
| Reiniciar bot | `schtasks /run /tn HermesBotStart` |

## Make.com — YouTube auto-publish

- Scenario ID: 5486064 (activo)
- Trigger: Webhook `https://hook.us2.make.com/socolwwhvnncxz4t2qh6ixrvi8jeo5jp`
- Acción: YouTube uploadVideo, privacidad=public, categoría=24
- Payload que envía Hermes: `{"title":"...", "video_base64":"...", "description":"..."}`

## TikTok workflow (sin API personal)

TikTok no expone API para cuentas personales — solo Ads API.
Workflow actual:
1. `/viral URL tema` → genera video → llega a Telegram (para guardar/compartir)
2. YouTube se publica automáticamente via Make.com
3. TikTok: subir manualmente desde Telegram o celular

## Cómo reiniciar el bot manualmente

Desde SSH al Lenovo (`chsan@192.168.0.182`):
```powershell
taskkill /F /IM python.exe /FI "memusage gt 50000"
schtasks /run /tn HermesBotStart
```
