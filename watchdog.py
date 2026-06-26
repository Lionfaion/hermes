"""Watchdog: reinicia el bot si muere y captura stderr en hermes_err.log."""
import subprocess
import time
import datetime
import pathlib

BASE = pathlib.Path(r"C:\Users\chsan\hermes")
CMD = [str(BASE.parent / "hermes-python" / "python.exe"), str(BASE / "brain" / "main.py")]
WATCHDOG_LOG = BASE / "logs" / "watchdog.log"
ERR_LOG = BASE / "logs" / "hermes_err.log"


def ts():
    return datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def log(msg):
    line = f"[{ts()}] {msg}\n"
    print(line, end="", flush=True)
    WATCHDOG_LOG.parent.mkdir(parents=True, exist_ok=True)
    with WATCHDOG_LOG.open("a", encoding="utf-8") as f:
        f.write(line)


while True:
    log("Iniciando bot...")
    with ERR_LOG.open("a", encoding="utf-8") as err:
        p = subprocess.run(CMD, stderr=err)
    log(f"Bot salio con codigo {p.returncode}. Reiniciando en 5s...")
    time.sleep(5)
