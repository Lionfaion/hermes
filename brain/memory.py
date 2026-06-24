import sqlite3
import logging
from config import DB_PATH, MAX_HISTORY_MESSAGES

logger = logging.getLogger(__name__)


def init_db() -> None:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS messages (
                id         INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id TEXT    NOT NULL,
                role       TEXT    NOT NULL CHECK(role IN ('user', 'assistant', 'system')),
                content    TEXT    NOT NULL,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        """)
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_session ON messages(session_id, created_at)"
        )


def save_message(session_id: str, role: str, content: str) -> None:
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute(
            "INSERT INTO messages (session_id, role, content) VALUES (?, ?, ?)",
            (session_id, role, content),
        )


def get_history(session_id: str) -> list:
    """Return last MAX_HISTORY_MESSAGES in chronological order."""
    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.execute(
            """
            SELECT role, content FROM (
                SELECT role, content, created_at
                FROM messages
                WHERE session_id = ?
                ORDER BY created_at DESC
                LIMIT ?
            ) ORDER BY created_at ASC
            """,
            (session_id, MAX_HISTORY_MESSAGES),
        )
        return [{"role": row[0], "content": row[1]} for row in cursor.fetchall()]


def clear_session(session_id: str) -> None:
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute("DELETE FROM messages WHERE session_id = ?", (session_id,))
    logger.info("Session cleared: %s", session_id)


def list_sessions() -> list:
    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.execute(
            "SELECT DISTINCT session_id FROM messages ORDER BY MAX(created_at) DESC"
        )
        return [row[0] for row in cursor.fetchall()]
