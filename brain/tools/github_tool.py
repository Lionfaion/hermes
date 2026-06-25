"""Herramienta de GitHub para Hermes."""

import json
from tools.base import BaseTool


class GitHubTool(BaseTool):
    name = "github"
    description = (
        "Interactúa con GitHub: listar repos, ver issues/PRs, leer archivos de repositorios, "
        "buscar código, crear issues, y comentar. "
        "Úsala cuando el usuario pregunte sobre sus repos, código, issues o PRs."
    )
    parameters = {
        "type": "object",
        "properties": {
            "action": {
                "type": "string",
                "description": "Acción a realizar",
                "enum": [
                    "repos", "repo_info", "issues", "issue_detail",
                    "pulls", "pull_detail", "read_file", "search_code",
                    "create_issue", "comment", "commits",
                ],
            },
            "owner": {
                "type": "string",
                "description": "Dueño del repo (usuario u organización)",
            },
            "repo": {
                "type": "string",
                "description": "Nombre del repositorio",
            },
            "number": {
                "type": "integer",
                "description": "Número de issue o PR",
            },
            "path": {
                "type": "string",
                "description": "Ruta de archivo dentro del repo",
            },
            "query": {
                "type": "string",
                "description": "Texto de búsqueda (para search_code)",
            },
            "title": {
                "type": "string",
                "description": "Título (para create_issue)",
            },
            "body": {
                "type": "string",
                "description": "Cuerpo/contenido (para create_issue o comment)",
            },
            "state": {
                "type": "string",
                "description": "Estado: open, closed, all",
                "enum": ["open", "closed", "all"],
            },
            "branch": {
                "type": "string",
                "description": "Branch/ref (para read_file o commits)",
            },
        },
        "required": ["action"],
    }

    def execute(
        self,
        action: str,
        owner: str = "",
        repo: str = "",
        number: int = 0,
        path: str = "",
        query: str = "",
        title: str = "",
        body: str = "",
        state: str = "open",
        branch: str = "",
    ) -> str:
        from integrations.github_client import (
            list_repos, get_repo, list_issues, get_issue,
            list_pulls, get_pull, get_file_content, search_code,
            create_issue, add_comment, list_commits,
        )

        try:
            if action == "repos":
                repos = list_repos(user=owner)
                if not repos:
                    return "No se encontraron repositorios."
                lines = []
                for r in repos:
                    vis = "🔒" if r["private"] else "🌐"
                    lang = f" [{r['language']}]" if r["language"] else ""
                    stars = f" ⭐{r['stars']}" if r["stars"] else ""
                    lines.append(f"{vis} **{r['name']}**{lang}{stars}")
                    if r["description"]:
                        lines.append(f"  {r['description']}")
                return "\n".join(lines)

            if action == "repo_info":
                if not owner or not repo:
                    return "Necesito owner y repo. Ej: owner='usuario', repo='mi-repo'"
                info = get_repo(owner, repo)
                return (
                    f"**{info['name']}**\n"
                    f"Descripción: {info['description'] or 'Sin descripción'}\n"
                    f"Lenguaje: {info['language'] or 'N/A'}\n"
                    f"⭐ {info['stars']} | 🔀 {info['forks']} | 🐛 {info['open_issues']} issues\n"
                    f"Branch principal: {info['default_branch']}\n"
                    f"Topics: {', '.join(info['topics']) if info['topics'] else 'N/A'}\n"
                    f"URL: {info['url']}"
                )

            if action == "issues":
                if not owner or not repo:
                    return "Necesito owner y repo."
                issues = list_issues(owner, repo, state=state)
                if not issues:
                    return f"No hay issues ({state}) en {owner}/{repo}."
                lines = []
                for i in issues:
                    labels = f" [{', '.join(i['labels'])}]" if i["labels"] else ""
                    lines.append(f"#{i['number']} {i['title']}{labels} (💬{i['comments']})")
                return "\n".join(lines)

            if action == "issue_detail":
                if not owner or not repo or not number:
                    return "Necesito owner, repo y number."
                issue = get_issue(owner, repo, number)
                result = (
                    f"**#{issue['number']} {issue['title']}** [{issue['state']}]\n"
                    f"Autor: {issue['author']} | Creado: {issue['created']}\n"
                    f"Labels: {', '.join(issue['labels']) if issue['labels'] else 'ninguno'}\n\n"
                    f"{issue['body'] or 'Sin descripción'}"
                )
                if issue["comments"]:
                    result += "\n\n--- Comentarios ---"
                    for c in issue["comments"]:
                        result += f"\n\n**{c['author']}** ({c['created']}):\n{c['body']}"
                return result

            if action == "pulls":
                if not owner or not repo:
                    return "Necesito owner y repo."
                prs = list_pulls(owner, repo, state=state)
                if not prs:
                    return f"No hay PRs ({state}) en {owner}/{repo}."
                lines = []
                for p in prs:
                    draft = " [DRAFT]" if p["draft"] else ""
                    lines.append(f"#{p['number']} {p['title']}{draft} ({p['branch']} → {p['base']})")
                return "\n".join(lines)

            if action == "pull_detail":
                if not owner or not repo or not number:
                    return "Necesito owner, repo y number."
                pr = get_pull(owner, repo, number)
                return (
                    f"**#{pr['number']} {pr['title']}** [{pr['state']}]\n"
                    f"Autor: {pr['author']} | Merged: {'Sí' if pr['merged'] else 'No'}\n"
                    f"Branch: {pr['branch']} → {pr['base']}\n"
                    f"+{pr['additions']} / -{pr['deletions']} ({pr['changed_files']} archivos)\n\n"
                    f"{pr['body'] or 'Sin descripción'}"
                )

            if action == "read_file":
                if not owner or not repo or not path:
                    return "Necesito owner, repo y path."
                content = get_file_content(owner, repo, path, ref=branch)
                if len(content) > 3000:
                    content = content[:3000] + "\n\n... [truncado, archivo muy largo]"
                return content

            if action == "search_code":
                if not query:
                    return "Necesito query para buscar."
                results = search_code(query, owner=owner, repo=repo)
                if not results:
                    return "No se encontraron resultados."
                lines = []
                for r in results:
                    lines.append(f"📄 {r['path']} ({r['repo']})")
                return "\n".join(lines)

            if action == "create_issue":
                if not owner or not repo or not title:
                    return "Necesito owner, repo y title."
                result = create_issue(owner, repo, title, body=body)
                return f"Issue creado: #{result['number']} - {result['title']}\n{result['url']}"

            if action == "comment":
                if not owner or not repo or not number or not body:
                    return "Necesito owner, repo, number y body."
                result = add_comment(owner, repo, number, body)
                return f"Comentario agregado: {result['url']}"

            if action == "commits":
                if not owner or not repo:
                    return "Necesito owner y repo."
                commits = list_commits(owner, repo, branch=branch)
                if not commits:
                    return "No se encontraron commits."
                lines = []
                for c in commits:
                    lines.append(f"`{c['sha']}` {c['message']} ({c['author']})")
                return "\n".join(lines)

            return f"Acción '{action}' no reconocida."

        except Exception as e:
            return f"Error en GitHub: {e}"
