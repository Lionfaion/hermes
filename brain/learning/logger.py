"""
Logger de interacciones del día.
Guarda cada mensaje en /logs/interacciones/YYYY-MM-DD.jsonl
"""
import json
import logging
from datetime import datetime
from pathlib import Path

from config import LOGS_DIR

logger = logging.getLogger(__name__)


class InteractionLogger:
    def __init__(self):
        self.logs_dir = Path(LOGS_DIR)
        self.logs_dir.mkdir(parents=True, exist_ok=True)

    def _today_file(self) -> Path:
        return self.logs_dir / f"{datetime.now().strftime('%Y-%m-%d')}.jsonl"

    def log(self, session_id: str, role: str, content: str, corrected: bool = False):
        entry = {
            "ts": datetime.now().isoformat(),
            "session": session_id,
            "role": role,
            "content": content[:1000],  # cap largo
            "corrected": corrected,
        }
        try:
            with open(self._today_file(), "a", encoding="utf-8") as f:
                f.write(json.dumps(entry, ensure_ascii=False) + "\n")
        except Exception as e:
            logger.warning("Error guardando log: %s", e)

    def get_today(self) -> list:
        f = self._today_file()
        if not f.exists():
            return []
        logs = []
        with open(f, "r", encoding="utf-8") as fh:
            for line in fh:
                try:
                    logs.append(json.loads(line))
                except Exception:
                    pass
        return logs

    def get_day(self, date_str: str) -> list:
        f = self.logs_dir / f"{date_str}.jsonl"
        if not f.exists():
            return []
        logs = []
        with open(f, "r", encoding="utf-8") as fh:
            for line in fh:
                try:
                    logs.append(json.loads(line))
                except Exception:
                    pass
        return logs
