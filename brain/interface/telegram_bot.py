#!/usr/bin/env python3
"""
Hermes Telegram Bot — secured with rate limiting and input validation.
"""
import asyncio
import faulthandler
import logging
import os
import sys
from pathlib import Path

import httpx

# Asegurar que ffmpeg esté en PATH
_FFMPEG_BIN = r"C:\Users\chsan\ffmpeg\bin"
if _FFMPEG_BIN not in os.environ.get("PATH", ""):
    os.environ["PATH"] = _FFMPEG_BIN + ";" + os.environ.get("PATH", "")

# Dump stack trace on crash (Windows access violations, etc.)
faulthandler.enable()

# Fix asyncio on Windows when running without a console (hidden process)
if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

sys.path.insert(0, str(Path(__file__).parent.parent))

from telegram import Update
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    filters,
    ContextTypes,
)

from assistant import HermesAssistant
from inference_client import is_online
from config import ASSISTANT_NAME, TELEGRAM_TOKEN, TELEGRAM_ALLOWED_USERS, DATA_DIR
from security import validate_message

logger = logging.getLogger(__name__)
_sessions: dict = {}


async def _send_video_direct(token: str, chat_id: int, video_path: str, caption: str) -> bool:
    """Upload video via raw httpx POST with 600s timeout — bypasses PTB timeout limits."""
    api_url = f"https://api.telegram.org/bot{token}/sendVideo"
    try:
        async with httpx.AsyncClient(timeout=httpx.Timeout(600.0, connect=30.0)) as client:
            with open(video_path, "rb") as f:
                resp = await client.post(
                    api_url,
                    data={"chat_id": str(chat_id), "caption": caption},
                    files={"video": (Path(video_path).name, f, "video/mp4")},
                )
        result = resp.json()
        if not result.get("ok"):
            logger.error("Telegram API error: %s", result)
        return result.get("ok", False)
    except Exception as e:
        logger.error("Error subiendo video directo: %s", e)
        return False


def _get_session(user_id: int) -> HermesAssistant:
    if user_id not in _sessions:
        _sessions[user_id] = HermesAssistant(session_id=f"tg_{user_id}")
    return _sessions[user_id]


def _is_allowed(user_id: int) -> bool:
    if not TELEGRAM_ALLOWED_USERS:
        return True
    return str(user_id) in TELEGRAM_ALLOWED_USERS


async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not _is_allowed(update.effective_user.id):
        await update.message.reply_text("Unauthorized.")
        return
    await update.message.reply_text(
        f"Hola, soy {ASSISTANT_NAME}, tu asistente de IA personal.\n\n"
        "Podés escribirme o mandarme audios de voz.\n\n"
        "Comandos:\n"
        "/viral [URL] [tema] — Replicar un video viral con nuevo tema\n"
        "/remember [texto] — Guardar algo en Obsidian para que lo recuerde siempre\n"
        "/status  — Estado del servidor de IA\n"
        "/clear   — Borrar memoria de conversación\n"
        "/new     — Nueva sesión\n"
        "/help    — Mostrar esta ayuda"
    )


async def cmd_status(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not _is_allowed(update.effective_user.id):
        return
    status = "ONLINE" if is_online() else "OFFLINE"
    await update.message.reply_text(f"GPU node: {status}")


async def cmd_clear(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not _is_allowed(update.effective_user.id):
        return
    _get_session(update.effective_user.id).clear_memory()
    await update.message.reply_text("Memoria borrada.")


async def cmd_new(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not _is_allowed(update.effective_user.id):
        return
    _get_session(update.effective_user.id).new_session()
    await update.message.reply_text("Nueva sesión iniciada.")


async def cmd_viral(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not _is_allowed(update.effective_user.id):
        return
    args = context.args or []
    if len(args) < 2:
        await update.message.reply_text(
            "Uso: /viral [URL] [tema]\n"
            "Ejemplo: /viral https://tiktok.com/... inversiones en Argentina"
        )
        return

    url = args[0]
    topic = " ".join(args[1:])
    msg = await update.message.reply_text(f"Generando video sobre '{topic}'... esto tarda 2-5 minutos.")

    loop = asyncio.get_event_loop()
    try:
        result = await loop.run_in_executor(None, _run_viral_pipeline, url, topic)
        if not result["success"]:
            await msg.edit_text(f"Error en el pipeline: {result['error']}")
            return

        video_path = result["video_path"]

        # Comprimir si el video es demasiado grande para Telegram (<= 20 MB)
        from video.assembler import compress_for_telegram
        compressed = await loop.run_in_executor(None, compress_for_telegram, video_path, 20)
        size_mb = Path(compressed).stat().st_size / (1024 * 1024)
        await msg.edit_text(f"Video listo ({size_mb:.1f} MB). Subiendo a Telegram y YouTube...")

        # Subir con httpx directo (600s timeout, bypasea PTB)
        ok = await _send_video_direct(
            TELEGRAM_TOKEN,
            update.effective_chat.id,
            compressed,
            f"{topic}\n\nGenerado por Hermes — listo para subir a TikTok",
        )
        if not ok:
            await update.message.reply_text(
                f"No pude enviar el video por Telegram (podría ser demasiado grande o lento). "
                f"El archivo está en el servidor: {Path(compressed).name}"
            )

        # Publicar en YouTube via Make.com
        pub_result = await loop.run_in_executor(None, _publish_video, video_path, topic, result.get("script", ""))
        status = "YouTube: publicado" if pub_result.get("success") else f"YouTube: {pub_result.get('error','error')}"
        await msg.edit_text(f"Listo.\n{status}\nPasos completados: {', '.join(result['steps'])}")

    except Exception as e:
        logger.error("cmd_viral error: %s", e, exc_info=True)
        await msg.edit_text(f"Error inesperado: {e}")


def _run_viral_pipeline(url: str, topic: str) -> dict:
    try:
        import config  # noqa — carga .env
        from video.pipeline import replicate_viral, PipelineConfig
        cfg = PipelineConfig(voice="es-ar-male", format="vertical", use_stock_footage=True)
        r = replicate_viral(source_url=url, new_topic=topic, config=cfg)
        return {
            "success": r.success,
            "video_path": r.video_path,
            "script": r.script,
            "steps": r.steps_completed,
            "error": r.error,
        }
    except Exception as e:
        return {"success": False, "error": str(e), "video_path": "", "script": "", "steps": []}


def _publish_video(video_path: str, title: str, script: str) -> dict:
    try:
        import config  # noqa
        from social.publisher import publish_video
        hashtags = ["viral", "hermes", "ia", "contenido"]
        return publish_video(
            video_path=video_path,
            title=title[:90],
            description=script[:400] if script else title,
            hashtags=hashtags,
            platforms=["youtube"],
            privacy="public",
        )
    except Exception as e:
        return {"success": False, "error": str(e)}


async def cmd_remember(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not _is_allowed(update.effective_user.id):
        return
    text = " ".join(context.args).strip() if context.args else ""
    if not text:
        await update.message.reply_text(
            "Uso: /remember [lo que querés que recuerde]\n"
            "Ejemplo: /remember me llamo Cris, soy de Argentina"
        )
        return
    try:
        from pathlib import Path
        from datetime import datetime
        from config import VAULT_PATH
        vault = Path(VAULT_PATH)
        note = vault / "Hermes" / "Memorias.md"
        note.parent.mkdir(parents=True, exist_ok=True)
        timestamp = datetime.now().strftime("%Y-%m-%d")
        entry = f"- [{timestamp}] {text}\n"
        if note.exists():
            note.write_text(note.read_text(encoding="utf-8") + entry, encoding="utf-8")
        else:
            note.write_text(f"# Memorias de Hermes\n\n{entry}", encoding="utf-8")
        await update.message.reply_text(f"Guardado en Obsidian: {text}")
    except Exception as e:
        logger.error("cmd_remember error: %s", e)
        await update.message.reply_text(f"Error al guardar: {e}")


async def handle_voice(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_id = update.effective_user.id

    if not _is_allowed(user_id):
        await update.message.reply_text("Unauthorized.")
        return

    await context.bot.send_chat_action(
        chat_id=update.effective_chat.id, action="typing"
    )

    voice = update.message.voice or update.message.audio
    if not voice:
        await update.message.reply_text("No se pudo leer el audio.")
        return

    voice_dir = DATA_DIR / "voice"
    voice_dir.mkdir(parents=True, exist_ok=True)
    ogg_path = voice_dir / f"voice_{user_id}_{update.message.message_id}.ogg"

    try:
        file = await context.bot.get_file(voice.file_id)
        await file.download_to_drive(str(ogg_path))

        from media.transcriber import transcribe
        text = transcribe(str(ogg_path))

        if not text or text.startswith("["):
            await update.message.reply_text("No pude entender el audio. Intentá de nuevo.")
            return

        await update.message.reply_text(f"🎤 *Escuché:* _{text}_", parse_mode="Markdown")

        clean_text, error = validate_message(str(user_id), text)
        if error:
            await update.message.reply_text(error)
            return

        response = _get_session(user_id).respond(clean_text)
        if not response:
            return

        for i in range(0, len(response), 4000):
            await update.message.reply_text(response[i: i + 4000])
    except Exception as e:
        logger.error("Error procesando audio: %s", e)
        await update.message.reply_text(f"Error procesando audio: {e}")
    finally:
        ogg_path.unlink(missing_ok=True)


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_id = update.effective_user.id

    if not _is_allowed(user_id):
        await update.message.reply_text("Unauthorized.")
        return

    raw_text = update.message.text or ""

    # Security validation: rate limit + sanitization + injection detection
    clean_text, error = validate_message(str(user_id), raw_text)
    if error:
        await update.message.reply_text(error)
        return

    await context.bot.send_chat_action(
        chat_id=update.effective_chat.id, action="typing"
    )

    response = _get_session(user_id).respond(clean_text)
    if not response:
        return

    for i in range(0, len(response), 4000):
        await update.message.reply_text(response[i: i + 4000])


async def _run(app: Application) -> None:
    """Manual async loop — avoids signal handler machinery that crashes on Windows without console."""
    await app.initialize()
    await app.updater.start_polling(drop_pending_updates=True)
    await app.start()
    logger.info("Bot running (background-safe loop)")
    try:
        while True:
            await asyncio.sleep(30)
    except (asyncio.CancelledError, KeyboardInterrupt):
        pass
    finally:
        logger.info("Shutting down bot...")
        try:
            await app.updater.stop()
            await app.stop()
            await app.shutdown()
        except Exception as e:
            logger.error("Error during shutdown: %s", e)


def main() -> None:
    if not TELEGRAM_TOKEN:
        logger.error("TELEGRAM_TOKEN no configurado.")
        sys.exit(1)

    app = (
        Application.builder()
        .token(TELEGRAM_TOKEN)
        .read_timeout(60)
        .write_timeout(300)
        .connect_timeout(30)
        .pool_timeout(300)
        .build()
    )
    app.add_handler(CommandHandler("start",    cmd_start))
    app.add_handler(CommandHandler("help",     cmd_start))
    app.add_handler(CommandHandler("status",   cmd_status))
    app.add_handler(CommandHandler("clear",    cmd_clear))
    app.add_handler(CommandHandler("new",      cmd_new))
    app.add_handler(CommandHandler("remember", cmd_remember))
    app.add_handler(CommandHandler("viral",   cmd_viral))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    app.add_handler(MessageHandler(filters.VOICE | filters.AUDIO, handle_voice))

    logger.info("Starting %s Telegram bot...", ASSISTANT_NAME)
    try:
        asyncio.run(_run(app))
        logger.info("asyncio.run() returned normally — bot stopped")
    except KeyboardInterrupt:
        logger.info("Bot stopped via KeyboardInterrupt")
    except SystemExit as e:
        logger.info("Bot stopped via SystemExit(%s)", e.code)
    except BaseException as e:
        logger.critical("Fatal crash (%s): %s", type(e).__name__, e, exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    main()
