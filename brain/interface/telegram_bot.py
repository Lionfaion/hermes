#!/usr/bin/env python3
"""
Hermes Telegram Bot — secured with rate limiting and input validation.
"""
import logging
import sys
from pathlib import Path

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
        "/status — Estado del servidor de IA\n"
        "/clear  — Borrar memoria de conversación\n"
        "/new    — Nueva sesión\n"
        "/help   — Mostrar esta ayuda"
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


def main() -> None:
    if not TELEGRAM_TOKEN:
        logger.error("TELEGRAM_TOKEN no configurado.")
        sys.exit(1)

    app = Application.builder().token(TELEGRAM_TOKEN).build()
    app.add_handler(CommandHandler("start",  cmd_start))
    app.add_handler(CommandHandler("help",   cmd_start))
    app.add_handler(CommandHandler("status", cmd_status))
    app.add_handler(CommandHandler("clear",  cmd_clear))
    app.add_handler(CommandHandler("new",    cmd_new))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    app.add_handler(MessageHandler(filters.VOICE | filters.AUDIO, handle_voice))

    logger.info("Starting %s Telegram bot...", ASSISTANT_NAME)
    app.run_polling(drop_pending_updates=True)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    main()
