"""Cliente de GitHub API para Hermes."""

import logging
import os
from dataclasses import dataclass

logger = logging.getLogger(__name__)

GITHUB_TOKEN = os.getenv("GITHUB_TOKEN", "")
GITHUB_API_URL = "https://api.github.com"


def _headers():
    if not GITHUB_TOKEN:
        raise RuntimeError(
            "GITHUB_TOKEN no configurado. Generá un Personal Access Token en "
            "https://github.com/settings/tokens con permisos de repo."
        )
    return {
        "Authorization": f"token {GITHUB_TOKEN}",
        "Accept": "application/vnd.github.v3+json",
        "User-Agent": "Hermes-AI-Assistant",
    }


def _get(endpoint: str, params: dict = None) -> dict | list:
    import requests
    url = f"{GITHUB_API_URL}/{endpoint.lstrip('/')}"
    resp = requests.get(url, headers=_headers(), params=params, timeout=15)
    resp.raise_for_status()
    return resp.json()


def _post(endpoint: str, data: dict = None) -> dict:
    import requests
    url = f"{GITHUB_API_URL}/{endpoint.lstrip('/')}"
    resp = requests.post(url, headers=_headers(), json=data, timeout=15)
    resp.raise_for_status()
    return resp.json()


def list_repos(user: str = "", org: str = "") -> list[dict]:
    """Lista repositorios del usuario autenticado, un usuario, o una organización."""
    if org:
        repos = _get(f"orgs/{org}/repos", {"per_page": 30, "sort": "updated"})
    elif user:
        repos = _get(f"users/{user}/repos", {"per_page": 30, "sort": "updated"})
    else:
        repos = _get("user/repos", {"per_page": 30, "sort": "updated", "affiliation": "owner"})

    return [
        {
            "name": r["full_name"],
            "description": r.get("description", ""),
            "language": r.get("language", ""),
            "stars": r.get("stargazers_count", 0),
            "updated": r.get("updated_at", ""),
            "url": r.get("html_url", ""),
            "private": r.get("private", False),
        }
        for r in repos
    ]


def get_repo(owner: str, repo: str) -> dict:
    """Obtiene información detallada de un repositorio."""
    r = _get(f"repos/{owner}/{repo}")
    return {
        "name": r["full_name"],
        "description": r.get("description", ""),
        "language": r.get("language", ""),
        "stars": r.get("stargazers_count", 0),
        "forks": r.get("forks_count", 0),
        "open_issues": r.get("open_issues_count", 0),
        "default_branch": r.get("default_branch", "main"),
        "url": r.get("html_url", ""),
        "topics": r.get("topics", []),
        "created": r.get("created_at", ""),
        "updated": r.get("updated_at", ""),
    }


def list_issues(owner: str, repo: str, state: str = "open", labels: str = "") -> list[dict]:
    """Lista issues de un repositorio."""
    params = {"state": state, "per_page": 20, "sort": "updated"}
    if labels:
        params["labels"] = labels
    issues = _get(f"repos/{owner}/{repo}/issues", params)
    return [
        {
            "number": i["number"],
            "title": i["title"],
            "state": i["state"],
            "labels": [l["name"] for l in i.get("labels", [])],
            "author": i.get("user", {}).get("login", ""),
            "created": i.get("created_at", ""),
            "comments": i.get("comments", 0),
            "url": i.get("html_url", ""),
        }
        for i in issues
        if "pull_request" not in i
    ]


def get_issue(owner: str, repo: str, number: int) -> dict:
    """Obtiene un issue específico con su contenido."""
    i = _get(f"repos/{owner}/{repo}/issues/{number}")
    comments = []
    if i.get("comments", 0) > 0:
        raw_comments = _get(f"repos/{owner}/{repo}/issues/{number}/comments", {"per_page": 10})
        comments = [
            {
                "author": c.get("user", {}).get("login", ""),
                "body": c.get("body", ""),
                "created": c.get("created_at", ""),
            }
            for c in raw_comments
        ]

    return {
        "number": i["number"],
        "title": i["title"],
        "body": i.get("body", ""),
        "state": i["state"],
        "labels": [l["name"] for l in i.get("labels", [])],
        "author": i.get("user", {}).get("login", ""),
        "created": i.get("created_at", ""),
        "comments": comments,
        "url": i.get("html_url", ""),
    }


def list_pulls(owner: str, repo: str, state: str = "open") -> list[dict]:
    """Lista pull requests de un repositorio."""
    prs = _get(f"repos/{owner}/{repo}/pulls", {"state": state, "per_page": 20, "sort": "updated"})
    return [
        {
            "number": p["number"],
            "title": p["title"],
            "state": p["state"],
            "author": p.get("user", {}).get("login", ""),
            "branch": p.get("head", {}).get("ref", ""),
            "base": p.get("base", {}).get("ref", ""),
            "created": p.get("created_at", ""),
            "draft": p.get("draft", False),
            "url": p.get("html_url", ""),
        }
        for p in prs
    ]


def get_pull(owner: str, repo: str, number: int) -> dict:
    """Obtiene un PR específico con detalles."""
    p = _get(f"repos/{owner}/{repo}/pulls/{number}")
    return {
        "number": p["number"],
        "title": p["title"],
        "body": p.get("body", ""),
        "state": p["state"],
        "merged": p.get("merged", False),
        "author": p.get("user", {}).get("login", ""),
        "branch": p.get("head", {}).get("ref", ""),
        "base": p.get("base", {}).get("ref", ""),
        "additions": p.get("additions", 0),
        "deletions": p.get("deletions", 0),
        "changed_files": p.get("changed_files", 0),
        "url": p.get("html_url", ""),
    }


def get_file_content(owner: str, repo: str, path: str, ref: str = "") -> str:
    """Lee el contenido de un archivo de un repositorio."""
    import base64
    params = {}
    if ref:
        params["ref"] = ref
    data = _get(f"repos/{owner}/{repo}/contents/{path}", params)

    if isinstance(data, list):
        entries = []
        for item in data:
            icon = "📁" if item["type"] == "dir" else "📄"
            entries.append(f"{icon} {item['name']}")
        return "Contenido del directorio:\n" + "\n".join(entries)

    if data.get("encoding") == "base64":
        content = base64.b64decode(data["content"]).decode("utf-8", errors="replace")
        return content

    return data.get("content", "")


def search_code(query: str, owner: str = "", repo: str = "", language: str = "") -> list[dict]:
    """Busca código en GitHub."""
    q = query
    if owner and repo:
        q += f" repo:{owner}/{repo}"
    elif owner:
        q += f" user:{owner}"
    if language:
        q += f" language:{language}"

    data = _get("search/code", {"q": q, "per_page": 10})
    return [
        {
            "file": item.get("name", ""),
            "path": item.get("path", ""),
            "repo": item.get("repository", {}).get("full_name", ""),
            "url": item.get("html_url", ""),
        }
        for item in data.get("items", [])
    ]


def create_issue(owner: str, repo: str, title: str, body: str = "", labels: list = None) -> dict:
    """Crea un nuevo issue."""
    data = {"title": title, "body": body}
    if labels:
        data["labels"] = labels
    result = _post(f"repos/{owner}/{repo}/issues", data)
    return {
        "number": result["number"],
        "title": result["title"],
        "url": result.get("html_url", ""),
    }


def add_comment(owner: str, repo: str, number: int, body: str) -> dict:
    """Agrega un comentario a un issue o PR."""
    result = _post(f"repos/{owner}/{repo}/issues/{number}/comments", {"body": body})
    return {
        "id": result["id"],
        "url": result.get("html_url", ""),
    }


def list_commits(owner: str, repo: str, branch: str = "", per_page: int = 10) -> list[dict]:
    """Lista commits recientes de un repositorio."""
    params = {"per_page": per_page}
    if branch:
        params["sha"] = branch
    commits = _get(f"repos/{owner}/{repo}/commits", params)
    return [
        {
            "sha": c["sha"][:7],
            "message": c.get("commit", {}).get("message", "").split("\n")[0],
            "author": c.get("commit", {}).get("author", {}).get("name", ""),
            "date": c.get("commit", {}).get("author", {}).get("date", ""),
        }
        for c in commits
    ]
