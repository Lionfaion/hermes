"""Background Task Manager: ejecuta sub-agentes en segundo plano."""

import logging
import sqlite3
import threading
import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum

from config import DB_PATH

logger = logging.getLogger(__name__)


class TaskStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass
class TaskInfo:
    task_id: str
    name: str
    description: str
    agent: str
    status: TaskStatus
    result: str = ""
    error: str = ""
    progress: str = ""
    created_at: str = ""
    started_at: str = ""
    completed_at: str = ""
    tools_used: list[str] = field(default_factory=list)


def _init_tasks_db():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS background_tasks (
                task_id      TEXT PRIMARY KEY,
                name         TEXT NOT NULL,
                description  TEXT NOT NULL,
                agent        TEXT NOT NULL DEFAULT '',
                status       TEXT NOT NULL DEFAULT 'pending',
                result       TEXT DEFAULT '',
                error        TEXT DEFAULT '',
                progress     TEXT DEFAULT '',
                tools_used   TEXT DEFAULT '',
                created_at   DATETIME DEFAULT CURRENT_TIMESTAMP,
                started_at   DATETIME,
                completed_at DATETIME
            )
        """)


_init_tasks_db()


class BackgroundTaskManager:
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
        self._threads: dict[str, threading.Thread] = {}
        self._cancel_flags: dict[str, threading.Event] = {}
        logger.info("BackgroundTaskManager inicializado")

    def create_task(
        self,
        name: str,
        description: str,
        agent: str,
        task_text: str,
        context: str = "",
        registry=None,
    ) -> str:
        task_id = str(uuid.uuid4())[:8]

        with sqlite3.connect(DB_PATH) as conn:
            conn.execute(
                "INSERT INTO background_tasks (task_id, name, description, agent, status) VALUES (?, ?, ?, ?, ?)",
                (task_id, name, description, agent, TaskStatus.PENDING),
            )

        cancel_event = threading.Event()
        self._cancel_flags[task_id] = cancel_event

        thread = threading.Thread(
            target=self._run_task,
            args=(task_id, agent, task_text, context, registry, cancel_event),
            daemon=True,
            name=f"task-{task_id}",
        )
        self._threads[task_id] = thread
        thread.start()

        logger.info("Tarea '%s' creada: %s (agente: %s)", name, task_id, agent)
        return task_id

    def _run_task(self, task_id, agent_name, task_text, context, registry, cancel_event):
        self._update_status(task_id, TaskStatus.RUNNING, started=True)
        self._update_progress(task_id, "Iniciando agente...")

        try:
            from agents.profiles import AGENT_PROFILES
            from agents.base_agent import BaseAgent

            if agent_name not in AGENT_PROFILES:
                raise ValueError(f"Agente '{agent_name}' no existe")

            if registry is None:
                from assistant import _get_registry
                registry = _get_registry()

            profile = AGENT_PROFILES[agent_name]
            agent = BaseAgent(profile, registry)

            self._update_progress(task_id, f"Agente {profile.name} trabajando...")

            if cancel_event.is_set():
                self._update_status(task_id, TaskStatus.CANCELLED)
                return

            result = agent.run(task_text, context)

            if cancel_event.is_set():
                self._update_status(task_id, TaskStatus.CANCELLED)
                return

            with sqlite3.connect(DB_PATH) as conn:
                conn.execute(
                    "UPDATE background_tasks SET status=?, result=?, completed_at=CURRENT_TIMESTAMP WHERE task_id=?",
                    (TaskStatus.COMPLETED, result, task_id),
                )
            logger.info("Tarea %s completada", task_id)

        except Exception as e:
            logger.error("Tarea %s falló: %s", task_id, e)
            with sqlite3.connect(DB_PATH) as conn:
                conn.execute(
                    "UPDATE background_tasks SET status=?, error=?, completed_at=CURRENT_TIMESTAMP WHERE task_id=?",
                    (TaskStatus.FAILED, str(e), task_id),
                )

    def _update_status(self, task_id: str, status: TaskStatus, started: bool = False):
        with sqlite3.connect(DB_PATH) as conn:
            if started:
                conn.execute(
                    "UPDATE background_tasks SET status=?, started_at=CURRENT_TIMESTAMP WHERE task_id=?",
                    (status, task_id),
                )
            else:
                conn.execute(
                    "UPDATE background_tasks SET status=? WHERE task_id=?",
                    (status, task_id),
                )

    def _update_progress(self, task_id: str, progress: str):
        with sqlite3.connect(DB_PATH) as conn:
            conn.execute(
                "UPDATE background_tasks SET progress=? WHERE task_id=?",
                (progress, task_id),
            )

    def get_task(self, task_id: str) -> TaskInfo | None:
        with sqlite3.connect(DB_PATH) as conn:
            conn.row_factory = sqlite3.Row
            row = conn.execute(
                "SELECT * FROM background_tasks WHERE task_id=?", (task_id,)
            ).fetchone()
            if not row:
                return None
            return TaskInfo(
                task_id=row["task_id"],
                name=row["name"],
                description=row["description"],
                agent=row["agent"],
                status=TaskStatus(row["status"]),
                result=row["result"] or "",
                error=row["error"] or "",
                progress=row["progress"] or "",
                created_at=row["created_at"] or "",
                started_at=row["started_at"] or "",
                completed_at=row["completed_at"] or "",
                tools_used=(row["tools_used"] or "").split(",") if row["tools_used"] else [],
            )

    def list_tasks(self, status: str = "", limit: int = 20) -> list[TaskInfo]:
        with sqlite3.connect(DB_PATH) as conn:
            conn.row_factory = sqlite3.Row
            if status:
                rows = conn.execute(
                    "SELECT * FROM background_tasks WHERE status=? ORDER BY created_at DESC LIMIT ?",
                    (status, limit),
                ).fetchall()
            else:
                rows = conn.execute(
                    "SELECT * FROM background_tasks ORDER BY created_at DESC LIMIT ?",
                    (limit,),
                ).fetchall()

            return [
                TaskInfo(
                    task_id=r["task_id"],
                    name=r["name"],
                    description=r["description"],
                    agent=r["agent"],
                    status=TaskStatus(r["status"]),
                    result=r["result"] or "",
                    error=r["error"] or "",
                    progress=r["progress"] or "",
                    created_at=r["created_at"] or "",
                    started_at=r["started_at"] or "",
                    completed_at=r["completed_at"] or "",
                )
                for r in rows
            ]

    def cancel_task(self, task_id: str) -> bool:
        if task_id in self._cancel_flags:
            self._cancel_flags[task_id].set()
            self._update_status(task_id, TaskStatus.CANCELLED)
            logger.info("Tarea %s cancelada", task_id)
            return True
        task = self.get_task(task_id)
        if task and task.status == TaskStatus.PENDING:
            self._update_status(task_id, TaskStatus.CANCELLED)
            return True
        return False

    def get_active_count(self) -> int:
        with sqlite3.connect(DB_PATH) as conn:
            row = conn.execute(
                "SELECT COUNT(*) FROM background_tasks WHERE status IN ('pending', 'running')"
            ).fetchone()
            return row[0] if row else 0
