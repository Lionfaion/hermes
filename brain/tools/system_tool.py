"""Herramienta para ejecutar comandos seguros del sistema."""

import subprocess
import logging
import shlex

from tools.base import BaseTool
from config import ALLOWED_COMMANDS

logger = logging.getLogger(__name__)


class SystemCommandTool(BaseTool):
    name = "run_command"
    description = (
        "Ejecuta un comando del sistema operativo (solo comandos permitidos). "
        "Úsala para verificar estado del servidor, espacio en disco, uso de memoria, etc."
    )
    parameters = {
        "type": "object",
        "properties": {
            "command": {
                "type": "string",
                "description": "Comando a ejecutar (debe estar en la lista de permitidos)",
            },
        },
        "required": ["command"],
    }

    def execute(self, command: str) -> str:
        cmd_parts = shlex.split(command)
        if not cmd_parts:
            return "Comando vacío."

        base_cmd = cmd_parts[0]
        if not any(command.startswith(allowed) for allowed in ALLOWED_COMMANDS):
            return (
                f"Comando '{base_cmd}' no permitido. "
                f"Comandos disponibles: {', '.join(ALLOWED_COMMANDS)}"
            )

        try:
            result = subprocess.run(
                cmd_parts,
                capture_output=True,
                text=True,
                timeout=30,
            )
            output = result.stdout or result.stderr
            if not output.strip():
                return f"Comando ejecutado (código: {result.returncode}), sin output."
            if len(output) > 5000:
                output = output[:5000] + "\n[... truncado]"
            return output
        except subprocess.TimeoutExpired:
            return "Comando excedió el timeout de 30 segundos."
        except Exception as e:
            return f"Error ejecutando comando: {e}"
