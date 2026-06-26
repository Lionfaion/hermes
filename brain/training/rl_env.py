"""Atropos-inspired RL environment for agent self-improvement.

Inspired by NousResearch/atropos.
Provides reward signals from task outcomes to improve agent behavior over time.
Uses execution history to compute rewards and adjust agent strategies.
"""

import json
import logging
import sqlite3
import time
from dataclasses import dataclass, field
from pathlib import Path

from inference_client import chat
from config import OLLAMA_MODEL, DB_PATH

logger = logging.getLogger(__name__)


@dataclass
class Episode:
    id: str
    agent: str
    task: str
    actions: list[dict] = field(default_factory=list)
    reward: float = 0.0
    done: bool = False
    metadata: dict = field(default_factory=dict)


@dataclass
class Policy:
    agent: str
    strategy: str = ""
    preferences: dict = field(default_factory=dict)
    generation: int = 0
    avg_reward: float = 0.0


def _init_rl_db():
    conn = sqlite3.connect(str(DB_PATH))
    conn.execute("""
        CREATE TABLE IF NOT EXISTS rl_episodes (
            id TEXT PRIMARY KEY,
            agent TEXT NOT NULL,
            task TEXT,
            actions TEXT,
            reward REAL DEFAULT 0,
            done INTEGER DEFAULT 0,
            metadata TEXT,
            created_at REAL
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS rl_policies (
            agent TEXT PRIMARY KEY,
            strategy TEXT,
            preferences TEXT,
            generation INTEGER DEFAULT 0,
            avg_reward REAL DEFAULT 0,
            updated_at REAL
        )
    """)
    conn.commit()
    return conn


def start_episode(agent: str, task: str) -> Episode:
    """Start a new RL episode for tracking."""
    ep_id = f"{agent}_{int(time.time() * 1000)}"
    episode = Episode(id=ep_id, agent=agent, task=task)

    try:
        conn = _init_rl_db()
        conn.execute(
            "INSERT INTO rl_episodes (id, agent, task, actions, reward, done, metadata, created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (ep_id, agent, task, "[]", 0.0, 0, "{}", time.time()),
        )
        conn.commit()
        conn.close()
    except Exception as e:
        logger.debug("Error starting episode: %s", e)

    return episode


def record_action(episode: Episode, action: str, result: str, success: bool):
    """Record an action within an episode."""
    episode.actions.append({
        "action": action,
        "result": result[:500],
        "success": success,
        "timestamp": time.time(),
    })

    try:
        conn = _init_rl_db()
        conn.execute(
            "UPDATE rl_episodes SET actions = ? WHERE id = ?",
            (json.dumps(episode.actions), episode.id),
        )
        conn.commit()
        conn.close()
    except Exception as e:
        logger.debug("Error recording action: %s", e)


def end_episode(episode: Episode, reward: float = None):
    """End an episode and compute reward."""
    episode.done = True

    if reward is None:
        reward = compute_reward(episode)
    episode.reward = reward

    try:
        conn = _init_rl_db()
        conn.execute(
            "UPDATE rl_episodes SET reward = ?, done = 1, metadata = ? WHERE id = ?",
            (reward, json.dumps(episode.metadata), episode.id),
        )
        conn.commit()
        conn.close()
    except Exception as e:
        logger.debug("Error ending episode: %s", e)

    _update_policy(episode.agent)


def compute_reward(episode: Episode) -> float:
    """Compute reward from episode actions."""
    if not episode.actions:
        return 0.0

    total = len(episode.actions)
    successes = sum(1 for a in episode.actions if a.get("success"))
    success_rate = successes / total if total > 0 else 0

    efficiency = max(0, 1 - (total - 1) / 10)

    return success_rate * 0.7 + efficiency * 0.3


def _update_policy(agent: str):
    """Update agent policy based on recent episodes."""
    try:
        conn = _init_rl_db()
        cursor = conn.execute(
            "SELECT reward, actions FROM rl_episodes WHERE agent = ? AND done = 1 ORDER BY created_at DESC LIMIT 20",
            (agent,),
        )
        rows = cursor.fetchall()
        if not rows:
            conn.close()
            return

        avg_reward = sum(r[0] for r in rows) / len(rows)

        cursor = conn.execute(
            "SELECT strategy, generation FROM rl_policies WHERE agent = ?",
            (agent,),
        )
        existing = cursor.fetchone()
        generation = (existing[1] + 1) if existing else 1

        if existing:
            conn.execute(
                "UPDATE rl_policies SET avg_reward = ?, generation = ?, updated_at = ? WHERE agent = ?",
                (avg_reward, generation, time.time(), agent),
            )
        else:
            conn.execute(
                "INSERT INTO rl_policies (agent, strategy, preferences, generation, avg_reward, updated_at) VALUES (?, ?, ?, ?, ?, ?)",
                (agent, "", "{}", generation, avg_reward, time.time()),
            )

        conn.commit()
        conn.close()
    except Exception as e:
        logger.debug("Error updating policy: %s", e)


def evolve_strategy(agent: str, model: str = "") -> str:
    """Use LLM to suggest strategy improvements based on episode history."""
    model = model or OLLAMA_MODEL

    try:
        conn = _init_rl_db()
        cursor = conn.execute(
            "SELECT task, reward, actions FROM rl_episodes WHERE agent = ? AND done = 1 ORDER BY created_at DESC LIMIT 10",
            (agent,),
        )
        rows = cursor.fetchall()
        conn.close()
    except Exception:
        rows = []

    if not rows:
        return "Sin historial suficiente para evolucionar estrategia."

    history = []
    for task, reward, actions_json in rows:
        actions = json.loads(actions_json) if actions_json else []
        success_count = sum(1 for a in actions if a.get("success"))
        history.append(f"- Tarea: {task[:100]} | Reward: {reward:.2f} | Acciones: {len(actions)} ({success_count} exitosas)")

    msg = (
        f"Analizá el historial de este agente ('{agent}') y sugerí mejoras en su estrategia.\n\n"
        f"HISTORIAL RECIENTE:\n" + "\n".join(history) + "\n\n"
        f"Identificá patrones de éxito/fracaso y proponé 3 mejoras concretas para la estrategia del agente."
    )

    return chat(
        [{"role": "system", "content": "Sos un experto en optimización de agentes de IA."},
         {"role": "user", "content": msg}],
        model,
    ).strip()


def get_agent_stats(agent: str) -> dict:
    """Get performance stats for an agent."""
    try:
        conn = _init_rl_db()
        cursor = conn.execute(
            "SELECT COUNT(*), AVG(reward), MAX(reward), MIN(reward) FROM rl_episodes WHERE agent = ? AND done = 1",
            (agent,),
        )
        row = cursor.fetchone()
        conn.close()

        if row and row[0] > 0:
            return {
                "episodes": row[0],
                "avg_reward": round(row[1], 3),
                "max_reward": round(row[2], 3),
                "min_reward": round(row[3], 3),
            }
    except Exception:
        pass
    return {"episodes": 0, "avg_reward": 0, "max_reward": 0, "min_reward": 0}
