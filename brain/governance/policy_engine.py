"""Agent Governance: deterministic policy enforcement for tool calls.

Inspired by NousResearch/agent-governance-toolkit.
Evaluates every tool call against YAML policies before execution.
"""

import logging
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

from config import BASE_DIR

logger = logging.getLogger(__name__)

POLICIES_FILE = BASE_DIR / "governance" / "policies.yaml"
AUDIT_LOG_FILE = BASE_DIR / "data" / "audit.log"


@dataclass
class PolicyDecision:
    allowed: bool
    rule_name: str = ""
    reason: str = ""
    evaluation_ms: float = 0.0


@dataclass
class PolicyRule:
    name: str
    action: str  # "allow" or "deny"
    tools: list[str] = field(default_factory=list)
    agents: list[str] = field(default_factory=list)
    conditions: dict = field(default_factory=dict)
    priority: int = 0


class PolicyEngine:
    def __init__(self, policies_file: str = ""):
        self.rules: list[PolicyRule] = []
        self.audit_enabled = True
        path = Path(policies_file) if policies_file else POLICIES_FILE
        if path.exists():
            self._load_policies(path)
        else:
            self._create_default_policies(path)

    def _load_policies(self, path: Path):
        try:
            with open(path) as f:
                data = yaml.safe_load(f) or {}
            for rule_data in data.get("rules", []):
                self.rules.append(PolicyRule(
                    name=rule_data.get("name", "unnamed"),
                    action=rule_data.get("action", "allow"),
                    tools=rule_data.get("tools", []),
                    agents=rule_data.get("agents", []),
                    conditions=rule_data.get("conditions", {}),
                    priority=rule_data.get("priority", 0),
                ))
            self.rules.sort(key=lambda r: r.priority, reverse=True)
            logger.info("Cargadas %d reglas de gobernanza", len(self.rules))
        except Exception as e:
            logger.error("Error cargando policies: %s", e)

    def _create_default_policies(self, path: Path):
        path.parent.mkdir(parents=True, exist_ok=True)
        default = {
            "version": "1.0",
            "default_action": "allow",
            "rules": [
                {
                    "name": "block_dangerous_commands",
                    "action": "deny",
                    "tools": ["run_command"],
                    "conditions": {
                        "args_contain": ["rm -rf", "mkfs", "dd if=", "> /dev/", "shutdown", "reboot"],
                    },
                    "priority": 100,
                },
                {
                    "name": "limit_background_tasks",
                    "action": "deny",
                    "tools": ["create_task"],
                    "conditions": {
                        "max_active": 5,
                    },
                    "priority": 50,
                },
                {
                    "name": "allow_all_default",
                    "action": "allow",
                    "tools": ["*"],
                    "agents": ["*"],
                    "priority": 0,
                },
            ],
        }
        with open(path, "w") as f:
            yaml.dump(default, f, default_flow_style=False, allow_unicode=True)
        self._load_policies(path)

    def evaluate(
        self,
        tool_name: str,
        agent_name: str = "",
        args: dict = None,
    ) -> PolicyDecision:
        """Evaluate a tool call against policies. Sub-millisecond."""
        start = time.perf_counter()
        args = args or {}

        for rule in self.rules:
            if not self._matches_tool(rule, tool_name):
                continue
            if rule.agents and not self._matches_agent(rule, agent_name):
                continue
            if rule.conditions and not self._matches_conditions(rule, args):
                continue

            elapsed = (time.perf_counter() - start) * 1000
            decision = PolicyDecision(
                allowed=rule.action == "allow",
                rule_name=rule.name,
                reason=f"Matched rule: {rule.name} ({rule.action})",
                evaluation_ms=elapsed,
            )

            if self.audit_enabled:
                self._audit_log(tool_name, agent_name, args, decision)

            return decision

        elapsed = (time.perf_counter() - start) * 1000
        decision = PolicyDecision(allowed=True, rule_name="default", evaluation_ms=elapsed)
        if self.audit_enabled:
            self._audit_log(tool_name, agent_name, args, decision)
        return decision

    def _matches_tool(self, rule: PolicyRule, tool_name: str) -> bool:
        if not rule.tools or "*" in rule.tools:
            return True
        return tool_name in rule.tools

    def _matches_agent(self, rule: PolicyRule, agent_name: str) -> bool:
        if not rule.agents or "*" in rule.agents:
            return True
        return agent_name in rule.agents

    def _matches_conditions(self, rule: PolicyRule, args: dict) -> bool:
        conditions = rule.conditions

        if "args_contain" in conditions:
            args_str = str(args).lower()
            for pattern in conditions["args_contain"]:
                if pattern.lower() in args_str:
                    return True
            return False

        if "max_active" in conditions:
            try:
                from background.task_manager import BackgroundTaskManager
                mgr = BackgroundTaskManager()
                if mgr.get_active_count() >= conditions["max_active"]:
                    return True
            except Exception:
                pass
            return False

        if "time_range" in conditions:
            import datetime
            now = datetime.datetime.now().hour
            start_h, end_h = conditions["time_range"]
            if start_h <= now < end_h:
                return True
            return False

        return True

    def _audit_log(self, tool: str, agent: str, args: dict, decision: PolicyDecision):
        try:
            AUDIT_LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
            ts = time.strftime("%Y-%m-%d %H:%M:%S")
            status = "ALLOW" if decision.allowed else "DENY"
            arg_summary = str(args)[:200] if args else ""
            line = f"[{ts}] {status} | tool={tool} | agent={agent} | rule={decision.rule_name} | {decision.evaluation_ms:.2f}ms | {arg_summary}\n"
            with open(AUDIT_LOG_FILE, "a") as f:
                f.write(line)
        except Exception:
            pass

    def add_rule(self, rule: PolicyRule):
        self.rules.append(rule)
        self.rules.sort(key=lambda r: r.priority, reverse=True)

    def get_rules(self) -> list[dict]:
        return [
            {"name": r.name, "action": r.action, "tools": r.tools,
             "agents": r.agents, "priority": r.priority}
            for r in self.rules
        ]


_engine: PolicyEngine | None = None


def get_policy_engine() -> PolicyEngine:
    global _engine
    if _engine is None:
        _engine = PolicyEngine()
    return _engine


def check_permission(tool_name: str, agent_name: str = "", args: dict = None) -> PolicyDecision:
    """Quick check if a tool call is allowed."""
    return get_policy_engine().evaluate(tool_name, agent_name, args)
