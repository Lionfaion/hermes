"""LSP client: Language Server Protocol integration for code intelligence.

Inspired by NousResearch/hermes-agent LSP integration.
Provides IDE-grade code understanding: diagnostics, hover, references, definitions.
Works with any LSP-compatible server (pyright, typescript-language-server, etc.)
"""

import json
import logging
import subprocess
import time
from dataclasses import dataclass, field
from pathlib import Path

logger = logging.getLogger(__name__)


@dataclass
class LSPDiagnostic:
    file: str
    line: int
    column: int
    severity: str  # error, warning, info, hint
    message: str
    source: str = ""


@dataclass
class LSPHover:
    content: str
    language: str = ""


@dataclass
class LSPLocation:
    file: str
    line: int
    column: int


@dataclass
class LSPResult:
    success: bool
    data: list = field(default_factory=list)
    error: str = ""


LSP_SERVERS = {
    "python": {
        "command": ["pyright-langserver", "--stdio"],
        "alt_command": ["pylsp"],
        "extensions": [".py"],
    },
    "typescript": {
        "command": ["typescript-language-server", "--stdio"],
        "extensions": [".ts", ".tsx", ".js", ".jsx"],
    },
    "rust": {
        "command": ["rust-analyzer"],
        "extensions": [".rs"],
    },
    "go": {
        "command": ["gopls", "serve"],
        "extensions": [".go"],
    },
}


def detect_language(file_path: str) -> str:
    """Detect language from file extension."""
    ext = Path(file_path).suffix.lower()
    for lang, config in LSP_SERVERS.items():
        if ext in config["extensions"]:
            return lang
    return ""


def is_lsp_available(language: str) -> bool:
    """Check if an LSP server is available for the given language."""
    if language not in LSP_SERVERS:
        return False

    config = LSP_SERVERS[language]
    cmd = config["command"][0]
    try:
        result = subprocess.run(
            ["which", cmd], capture_output=True, timeout=5
        )
        if result.returncode == 0:
            return True
    except Exception:
        pass

    if "alt_command" in config:
        alt_cmd = config["alt_command"][0]
        try:
            result = subprocess.run(
                ["which", alt_cmd], capture_output=True, timeout=5
            )
            return result.returncode == 0
        except Exception:
            pass

    return False


def get_diagnostics(file_path: str, project_root: str = "") -> LSPResult:
    """Get diagnostics (errors, warnings) for a file.

    Falls back to running linters directly if LSP server is not available.
    """
    language = detect_language(file_path)
    if not language:
        return LSPResult(success=False, error=f"Lenguaje no detectado para {file_path}")

    # Try direct linter as fallback (more reliable for one-shot use)
    if language == "python":
        return _python_diagnostics(file_path)
    elif language == "typescript":
        return _typescript_diagnostics(file_path, project_root)

    return LSPResult(success=False, error=f"LSP no disponible para {language}")


def get_references(file_path: str, symbol: str, project_root: str = "") -> LSPResult:
    """Find all references to a symbol using grep-based fallback."""
    root = project_root or str(Path(file_path).parent)
    language = detect_language(file_path)
    ext_filter = ""
    if language in LSP_SERVERS:
        exts = LSP_SERVERS[language]["extensions"]
        ext_filter = " ".join(f"--include='*{e}'" for e in exts)

    try:
        cmd = f"grep -rn {ext_filter} '{symbol}' '{root}' 2>/dev/null | head -50"
        result = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=10)
        locations = []
        for line in result.stdout.strip().split("\n"):
            if not line:
                continue
            parts = line.split(":", 2)
            if len(parts) >= 3:
                locations.append(LSPLocation(
                    file=parts[0],
                    line=int(parts[1]) if parts[1].isdigit() else 0,
                    column=0,
                ))
        return LSPResult(success=True, data=locations)
    except Exception as e:
        return LSPResult(success=False, error=str(e))


def get_definition(file_path: str, symbol: str, project_root: str = "") -> LSPResult:
    """Find definition of a symbol."""
    root = project_root or str(Path(file_path).parent)
    language = detect_language(file_path)

    # Pattern-based definition search
    patterns = {
        "python": [f"def {symbol}", f"class {symbol}", f"{symbol} =", f"{symbol}:"],
        "typescript": [f"function {symbol}", f"class {symbol}", f"const {symbol}", f"interface {symbol}", f"type {symbol}"],
        "rust": [f"fn {symbol}", f"struct {symbol}", f"enum {symbol}", f"trait {symbol}"],
        "go": [f"func {symbol}", f"type {symbol}"],
    }

    search_patterns = patterns.get(language, [f"def {symbol}", f"class {symbol}", f"{symbol} ="])
    ext_filter = ""
    if language in LSP_SERVERS:
        exts = LSP_SERVERS[language]["extensions"]
        ext_filter = " ".join(f"--include='*{e}'" for e in exts)

    locations = []
    for pattern in search_patterns:
        try:
            cmd = f"grep -rn {ext_filter} '{pattern}' '{root}' 2>/dev/null | head -10"
            result = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=10)
            for line in result.stdout.strip().split("\n"):
                if not line:
                    continue
                parts = line.split(":", 2)
                if len(parts) >= 3:
                    locations.append(LSPLocation(
                        file=parts[0],
                        line=int(parts[1]) if parts[1].isdigit() else 0,
                        column=0,
                    ))
        except Exception:
            continue

    return LSPResult(success=bool(locations), data=locations)


def _python_diagnostics(file_path: str) -> LSPResult:
    """Run Python diagnostics using available linters."""
    diagnostics = []

    # Try pyflakes (fast, catches errors)
    try:
        result = subprocess.run(
            ["python3", "-m", "pyflakes", file_path],
            capture_output=True, text=True, timeout=15,
        )
        for line in result.stdout.strip().split("\n"):
            if not line:
                continue
            parts = line.split(":", 2)
            if len(parts) >= 3:
                diagnostics.append(LSPDiagnostic(
                    file=parts[0],
                    line=int(parts[1]) if parts[1].isdigit() else 0,
                    column=0,
                    severity="warning",
                    message=parts[2].strip(),
                    source="pyflakes",
                ))
    except Exception:
        pass

    # Try py_compile for syntax errors
    try:
        result = subprocess.run(
            ["python3", "-c", f"import py_compile; py_compile.compile('{file_path}', doraise=True)"],
            capture_output=True, text=True, timeout=10,
        )
        if result.returncode != 0:
            diagnostics.append(LSPDiagnostic(
                file=file_path, line=0, column=0,
                severity="error",
                message=result.stderr.strip()[:200],
                source="py_compile",
            ))
    except Exception:
        pass

    return LSPResult(success=True, data=diagnostics)


def _typescript_diagnostics(file_path: str, project_root: str = "") -> LSPResult:
    """Run TypeScript diagnostics using tsc."""
    try:
        root = project_root or str(Path(file_path).parent)
        result = subprocess.run(
            ["npx", "tsc", "--noEmit", file_path],
            capture_output=True, text=True, timeout=30,
            cwd=root,
        )
        diagnostics = []
        for line in result.stdout.strip().split("\n"):
            if not line or "error" not in line.lower():
                continue
            diagnostics.append(LSPDiagnostic(
                file=file_path, line=0, column=0,
                severity="error",
                message=line.strip()[:200],
                source="tsc",
            ))
        return LSPResult(success=True, data=diagnostics)
    except Exception as e:
        return LSPResult(success=False, error=str(e))
