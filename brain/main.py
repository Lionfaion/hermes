#!/usr/bin/env python3
"""
Hermes entrypoint: auto-selects Telegram bot or HTTP API server
based on available configuration. This is what systemd runs.
"""
import logging
import os
import sys
from pathlib import Path

# Asegurar que el directorio brain esté en sys.path sin importar desde dónde se ejecute
sys.path.insert(0, str(Path(__file__).parent))

# Certificados SSL para Python embeddable en Windows
try:
    import certifi
    os.environ.setdefault("SSL_CERT_FILE", certifi.where())
    os.environ.setdefault("REQUESTS_CA_BUNDLE", certifi.where())
except ImportError:
    pass

_LOG_DIR = Path(__file__).resolve().parent.parent / "logs"
_LOG_DIR.mkdir(parents=True, exist_ok=True)
_LOG_FILE = _LOG_DIR / "hermes.log"

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler(_LOG_FILE, encoding="utf-8"),
    ],
)

logger = logging.getLogger("hermes.main")

from config import TELEGRAM_TOKEN, ASSISTANT_NAME, API_HOST, API_PORT


def main():
    logger.info("Starting %s...", ASSISTANT_NAME)

    if TELEGRAM_TOKEN:
        logger.info("Telegram token found — starting Telegram bot mode")
        from interface.telegram_bot import main as run_bot
        run_bot()
    else:
        logger.info("No Telegram token — starting HTTP API server on %s:%d", API_HOST, API_PORT)
        from server import app
        app.run(host=API_HOST, port=API_PORT, debug=False)


if __name__ == "__main__":
    main()
