"""Iteration budget with refund: principled loop control for agents.

Inspired by NousResearch/hermes-agent iteration management.
Thread-safe counter capping agent loops with refunds for cheap operations.
"""

import logging
import threading
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)

DEFAULT_PARENT_BUDGET = 90
DEFAULT_SUBAGENT_BUDGET = 50

CHEAP_OPERATIONS = {
    "search_notes", "vault_read", "vault_list", "recall",
    "list_video_jobs", "agent_stats", "check_tasks",
    "list_cron_jobs", "list_specs", "get_spec",
    "graph_connections", "graph_search",
}

REFUND_AMOUNT = 0.5


@dataclass
class IterationBudget:
    """Thread-safe iteration budget with refund for cheap operations."""
    max_iterations: int
    _used: float = 0.0
    _lock: threading.Lock = field(default_factory=threading.Lock, repr=False)
    _history: list[dict] = field(default_factory=list, repr=False)

    @property
    def remaining(self) -> float:
        with self._lock:
            return self.max_iterations - self._used

    @property
    def exhausted(self) -> bool:
        return self.remaining <= 0

    def consume(self, tool_name: str = "", cost: float = 1.0) -> bool:
        """Consume budget for an operation. Returns True if budget available."""
        with self._lock:
            if self._used >= self.max_iterations:
                logger.warning("Budget exhausted: %s/%s used", self._used, self.max_iterations)
                return False

            if tool_name in CHEAP_OPERATIONS:
                actual_cost = cost * (1 - REFUND_AMOUNT)
            else:
                actual_cost = cost

            self._used += actual_cost
            self._history.append({
                "tool": tool_name,
                "cost": actual_cost,
                "total_used": self._used,
            })
            return True

    def refund(self, amount: float = 1.0):
        """Refund budget (e.g., when a tool call was a no-op)."""
        with self._lock:
            self._used = max(0, self._used - amount)

    def get_stats(self) -> dict:
        with self._lock:
            return {
                "max": self.max_iterations,
                "used": round(self._used, 1),
                "remaining": round(self.max_iterations - self._used, 1),
                "operations": len(self._history),
            }


class BudgetManager:
    """Manages budgets for parent and subagent contexts."""

    def __init__(self):
        self._budgets: dict[str, IterationBudget] = {}
        self._lock = threading.Lock()

    def get_budget(self, session_id: str, is_subagent: bool = False) -> IterationBudget:
        """Get or create a budget for a session."""
        with self._lock:
            if session_id not in self._budgets:
                max_iter = DEFAULT_SUBAGENT_BUDGET if is_subagent else DEFAULT_PARENT_BUDGET
                self._budgets[session_id] = IterationBudget(max_iterations=max_iter)
            return self._budgets[session_id]

    def reset_budget(self, session_id: str):
        """Reset budget for a new conversation turn."""
        with self._lock:
            if session_id in self._budgets:
                del self._budgets[session_id]

    def get_all_stats(self) -> dict[str, dict]:
        with self._lock:
            return {sid: b.get_stats() for sid, b in self._budgets.items()}


_manager = BudgetManager()


def get_budget_manager() -> BudgetManager:
    return _manager
