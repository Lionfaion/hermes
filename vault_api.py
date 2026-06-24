"""API HTTP simple para acceso al vault de Obsidian desde la red local."""
import json, os, threading
from http.server import HTTPServer, BaseHTTPRequestHandler
from pathlib import Path
from urllib.parse import urlparse, parse_qs, unquote

VAULT = Path(os.environ.get("VAULT_PATH", r"C:\Users\chsan\hermes-vault"))
API_KEY = os.environ.get("VAULT_API_KEY", "hermes-vault-2024")
PORT = int(os.environ.get("VAULT_API_PORT", "8091"))


class VaultHandler(BaseHTTPRequestHandler):
    def log_message(self, *a): pass

    def _auth(self):
        key = self.headers.get("X-API-Key", "")
        if key != API_KEY:
            self.send_response(401)
            self.end_headers()
            return False
        return True

    def _json(self, data, code=200):
        body = json.dumps(data, ensure_ascii=False, indent=2).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        if not self._auth(): return
        parsed = urlparse(self.path)
        path = parsed.path.rstrip("/")
        qs = parse_qs(parsed.query)

        if path == "/notes":
            notes = [str(f.relative_to(VAULT)) for f in VAULT.rglob("*.md")]
            self._json({"notes": notes})
        elif path.startswith("/notes/"):
            rel = unquote(path[7:])
            if not rel.endswith(".md"): rel += ".md"
            note = (VAULT / rel).resolve()
            if not str(note).startswith(str(VAULT.resolve())):
                self._json({"error": "forbidden"}, 403); return
            if not note.exists():
                self._json({"error": "not found"}, 404); return
            self._json({"path": rel, "content": note.read_text(encoding="utf-8", errors="ignore")})
        elif path == "/search":
            query = qs.get("q", [""])[0]
            if not query:
                self._json({"error": "missing q"}); return
            try:
                sys_path_backup = __import__("sys").path[:]
                __import__("sys").path.insert(0, str(Path(__file__).parent / "brain"))
                from config import CHROMA_PATH
                from rag.indexer import VaultIndexer
                from rag.searcher import VaultSearcher
                idx = VaultIndexer(vault_path=str(VAULT), db_path=CHROMA_PATH)
                results = VaultSearcher(idx).search(query, n_results=5)
                self._json({"results": results})
            except Exception as e:
                self._json({"error": str(e)})
        else:
            self._json({"error": "not found"}, 404)

    def do_POST(self):
        if not self._auth(): return
        parsed = urlparse(self.path)
        path = parsed.path.rstrip("/")
        if not path.startswith("/notes/"):
            self._json({"error": "not found"}, 404); return
        length = int(self.headers.get("Content-Length", 0))
        body = json.loads(self.rfile.read(length) or b"{}")
        rel = unquote(path[7:])
        if not rel.endswith(".md"): rel += ".md"
        note = (VAULT / rel).resolve()
        if not str(note).startswith(str(VAULT.resolve())):
            self._json({"error": "forbidden"}, 403); return
        note.parent.mkdir(parents=True, exist_ok=True)
        content = body.get("content", "")
        mode = body.get("mode", "create")
        if mode == "append" and note.exists():
            content = note.read_text(encoding="utf-8", errors="ignore") + "\n" + content
        note.write_text(content, encoding="utf-8")
        self._json({"ok": True, "path": rel})


if __name__ == "__main__":
    server = HTTPServer(("0.0.0.0", PORT), VaultHandler)
    print(f"Vault API en http://0.0.0.0:{PORT} (key: {API_KEY})")
    server.serve_forever()