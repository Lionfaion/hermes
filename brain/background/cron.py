"""Cron Scheduler: tareas recurrentes persistentes en SQLite."""

import logging
import re
import sqlite3
import threading
import uuid
from datetime import datetime, timedelta
from dataclasses import dataclass

from config import DB_PATH

logger = logging.getLogger(__name__)

NATURAL_SCHEDULES = {
    r"cada hora": "0 * * * *",
    r"cada (\d+) horas?": None,
    r"cada (\d+) minutos?": None,
    r"diario a las? (\d{1,2})(?::(\d{2}))?": None,
    r"todos los d[ií]as? a las? (\d{1,2})(?::(\d{2}))?": None,
    r"cada d[ií]a": "0 9 * * *",
    r"cada lunes": "0 9 * * 1",
    r"cada martes": "0 9 * * 2",
    r"cada mi[eé]rcoles": "0 9 * * 3",
    r"cada jueves": "0 9 * * 4",
    r"cada viernes": "0 9 * * 5",
    r"cada s[aá]bado": "0 9 * * 6",
    r"cada domingo": "0 9 * * 0",
    r"cada semana": "0 9 * * 1",
    r"cada mes": "0 9 1 * *",
    r"every hour": "0 * * * *",
    r"every day": "0 9 * * *",
    r"every week": "0 9 * * 1",
    r"every month": "0 9 1 * *",
    r"every monday": "0 9 * * 1",
    r"every tuesday": "0 9 * * 2",
    r"every wednesday": "0 9 * * 3",
    r"every thursday": "0 9 * * 4",
    r"every friday": "0 9 * * 5",
}


def parse_schedule(text: str) -> str:
    """Convierte lenguaje natural o cron expression a cron expression."""
    text = text.strip().lower()

    # Already a cron expression
    parts = text.split()
    if len(parts) == 5 and all(
        re.match(r'^[\d\*,/\-]+$', p) for p in parts
    ):
        return text

    # cada N horas
    m = re.search(r'cada (\d+) horas?', text)
    if m:
        hours = int(m.group(1))
        return f"0 */{hours} * * *"

    # cada N minutos
    m = re.search(r'cada (\d+) minutos?', text)
    if m:
        mins = int(m.group(1))
        return f"*/{mins} * * * *"

    # diario a las X / todos los días a las X
    m = re.search(r'(?:diario|todos los d[ií]as?) a las? (\d{1,2})(?::(\d{2}))?', text)
    if m:
        hour = int(m.group(1))
        minute = int(m.group(2)) if m.group(2) else 0
        return f"{minute} {hour} * * *"

    # every N hours
    m = re.search(r'every (\d+) hours?', text)
    if m:
        hours = int(m.group(1))
        return f"0 */{hours} * * *"

    # Fixed schedules
    for pattern, cron in NATURAL_SCHEDULES.items():
        if cron and re.search(pattern, text):
            return cron

    return text


def _compute_next_run(cron_expr: str, after: datetime = None) -> datetime:
    """Calcula la próxima ejecución basada en la expresión cron."""
    try:
        from croniter import croniter
        base = after or datetime.now()
        cron = croniter(cron_expr, base)
        return cron.get_next(datetime)
    except ImportError:
        # Fallback sin croniter: estimar próxima ejecución simple
        now = after or datetime.now()
        parts = cron_expr.split()
        if len(parts) != 5:
            return now + timedelta(hours=1)

        minute, hour = parts[0], parts[1]

        if "*/" in minute:
            interval = int(minute.split("/")[1])
            return now + timedelta(minutes=interval)
        if "*/" in hour:
            interval = int(hour.split("/")[1])
            return now + timedelta(hours=interval)

        return now + timedelta(hours=1)


@dataclass
class CronJob:
    job_id: str
    name: str
    agent: str
    task: str
    context: str
    cron_expression: str
    next_run: str
    last_run: str
    last_result: str
    enabled: bool
    created_at: str
    spec_id: str = ""


def _init_cron_db():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS cron_jobs (
                job_id          TEXT PRIMARY KEY,
                name            TEXT NOT NULL,
                agent           TEXT NOT NULL,
                task            TEXT NOT NULL,
                context         TEXT DEFAULT '',
                cron_expression TEXT NOT NULL,
                next_run        DATETIME,
                last_run        DATETIME,
                last_result     TEXT DEFAULT '',
                enabled         INTEGER DEFAULT 1,
                spec_id         TEXT DEFAULT '',
                created_at      DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        """)


_init_cron_db()


class CronScheduler:
    _instance = None
    _lock = threading.Lock()

    def __new__(cls):
        with cls._lock:
            if cls._instance is None:
                cls._instance = super().__new__(cls)
                cls._instance._initialized = False
            return cls._instance

    def __init__(self):
        if self._initialized:
            return
        self._initialized = True
        self._running = False
        self._stop_event = threading.Event()
        self._thread = None
        self._registry = None
        logger.info("CronScheduler inicializado")

    def set_registry(self, registry):
        self._registry = registry

    def add_job(
        self,
        name: str,
        agent: str,
        task: str,
        schedule: str,
        context: str = "",
        spec_id: str = "",
    ) -> str:
        cron_expr = parse_schedule(schedule)
        job_id = str(uuid.uuid4())[:8]
        next_run = _compute_next_run(cron_expr)

        # If spec_id provided, inject spec as context
        if spec_id:
            try:
                from specs.manager import SpecManager
                manager = SpecManager()
                spec = manager.get_spec(spec_id)
                if spec:
                    spec_context = manager.build_prompt_injection(spec)
                    task = f"{task}\n\n{spec_context}"
            except Exception:
                pass

        with sqlite3.connect(DB_PATH) as conn:
            conn.execute(
                """INSERT INTO cron_jobs (job_id, name, agent, task, context, cron_expression, next_run, spec_id)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                (job_id, name, agent, task, context, cron_expr, next_run.isoformat(), spec_id),
            )

        logger.info("Cron job '%s' creado: %s (%s)", name, job_id, cron_expr)
        return job_id

    def list_jobs(self) -> list[CronJob]:
        with sqlite3.connect(DB_PATH) as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute(
                "SELECT * FROM cron_jobs ORDER BY created_at DESC"
            ).fetchall()

        return [
            CronJob(
                job_id=r["job_id"],
                name=r["name"],
                agent=r["agent"],
                task=r["task"],
                context=r["context"] or "",
                cron_expression=r["cron_expression"],
                next_run=r["next_run"] or "",
                last_run=r["last_run"] or "",
                last_result=r["last_result"] or "",
                enabled=bool(r["enabled"]),
                created_at=r["created_at"] or "",
                spec_id=r["spec_id"] if "spec_id" in r.keys() else "",
            )
            for r in rows
        ]

    def delete_job(self, job_id: str) -> bool:
        with sqlite3.connect(DB_PATH) as conn:
            cursor = conn.execute("DELETE FROM cron_jobs WHERE job_id=?", (job_id,))
            return cursor.rowcount > 0

    def toggle_job(self, job_id: str, enabled: bool) -> bool:
        with sqlite3.connect(DB_PATH) as conn:
            cursor = conn.execute(
                "UPDATE cron_jobs SET enabled=? WHERE job_id=?",
                (1 if enabled else 0, job_id),
            )
            return cursor.rowcount > 0

    def start(self):
        if self._running:
            return
        self._running = True
        self._stop_event.clear()
        self._thread = threading.Thread(target=self._poll_loop, daemon=True, name="cron-scheduler")
        self._thread.start()
        logger.info("CronScheduler iniciado")

    def stop(self):
        self._running = False
        self._stop_event.set()
        if self._thread:
            self._thread.join(timeout=5)
        logger.info("CronScheduler detenido")

    def _poll_loop(self):
        while not self._stop_event.is_set():
            try:
                self._check_and_run()
            except Exception as e:
                logger.error("Cron poll error: %s", e)
            self._stop_event.wait(60)

    def _check_and_run(self):
        now = datetime.now()
        with sqlite3.connect(DB_PATH) as conn:
            conn.row_factory = sqlite3.Row
            due_jobs = conn.execute(
                "SELECT * FROM cron_jobs WHERE enabled=1 AND next_run <= ?",
                (now.isoformat(),),
            ).fetchall()

        for job in due_jobs:
            logger.info("Ejecutando cron job: %s (%s)", job["name"], job["job_id"])
            try:
                from background.task_manager import BackgroundTaskManager
                manager = BackgroundTaskManager()
                manager.create_task(
                    name=f"[CRON] {job['name']}",
                    description=job["task"][:200],
                    agent=job["agent"],
                    task_text=job["task"],
                    context=job["context"] or "",
                    registry=self._registry,
                )

                next_run = _compute_next_run(job["cron_expression"], now)
                with sqlite3.connect(DB_PATH) as conn:
                    conn.execute(
                        "UPDATE cron_jobs SET last_run=?, next_run=?, last_result='ejecutado' WHERE job_id=?",
                        (now.isoformat(), next_run.isoformat(), job["job_id"]),
                    )
            except Exception as e:
                logger.error("Cron job %s falló: %s", job["job_id"], e)
                with sqlite3.connect(DB_PATH) as conn:
                    conn.execute(
                        "UPDATE cron_jobs SET last_run=?, last_result=? WHERE job_id=?",
                        (now.isoformat(), f"error: {e}", job["job_id"]),
                    )
