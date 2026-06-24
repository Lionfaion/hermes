#!/usr/bin/env python3
"""
Hermes Telegram Bot — control the assistant from anywhere via Telegram.
Set TELEGRAM_TOKEN and optionally TELEGRAM_ALLOWED_USERS in .env
"""
import sys
import logging
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
from config import ASSISTANT_NAME, TELEGRAM_TOKEN, TELEGRAM_ALLOWED_USERS

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
        f"Hi! I'm {ASSISTANT_NAME}, your home AI assistant.\n\n"
        "Commands:\n"
        "/status — GPU node status\n"
        "/clear  — Erase conversation memory\n"
        "/new    — Start fresh session\n"
        "/help   — Show this message"
    )


async def cmd_status(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not _is_allowed(update.effective_user.id):
        return
    status = "🟢 ONLINE" if is_online() else "🔴 OFFLINE"
    await update.message.reply_text(f"GPU node: {status}")


async def cmd_clear(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not _is_allowed(update.effective_user.id):
        return
    _get_session(update.effective_user.id).clear_memory()
    await update.message.reply_text("Memory cleared.")


async def cmd_new(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not _is_allowed(update.effective_user.id):
        return
    _get_session(update.effective_user.id).new_session()
    await update.message.reply_text("New session started.")


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_id = update.effective_user.id
    if not _is_allowed(user_id):
        await update.message.reply_text("Unauthorized.")
        return

    await context.bot.send_chat_action(
        chat_id=update.effective_chat.id, action="typing"
    )

    response = _get_session(user_id).respond(update.message.text)
    if not response:
        return

    # Telegram hard limit is 4096 chars per message
    for i in range(0, len(response), 4000):
        await update.message.reply_text(response[i: i + 4000])


def main() -> None:
    if not TELEGRAM_TOKEN:
        logger.error("TELEGRAM_TOKEN is not set. Add it to .env")
        sys.exit(1)

    app = Application.builder().token(TELEGRAM_TOKEN).build()
    app.add_handler(CommandHandler("start", cmd_start))
    app.add_handler(CommandHandler("help",  cmd_start))
    app.add_handler(CommandHandler("status", cmd_status))
    app.add_handler(CommandHandler("clear",  cmd_clear))
    app.add_handler(CommandHandler("new",    cmd_new))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    logger.info("Starting %s Telegram bot...", ASSISTANT_NAME)
    app.run_polling(drop_pending_updates=True)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    main()
