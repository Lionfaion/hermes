"""Herramientas de Knowledge Graph para explorar conexiones en Obsidian."""

from tools.base import BaseTool


class GraphConnectionsTool(BaseTool):
    name = "graph_connections"
    description = (
        "Explora las conexiones de una nota en el grafo de conocimiento de Obsidian. "
        "Muestra qué notas están enlazadas, backlinks, y tags relacionados. "
        "Úsala cuando el usuario pregunte 'qué está conectado a X' o 'qué notas se relacionan con Y'."
    )
    parameters = {
        "type": "object",
        "properties": {
            "note": {
                "type": "string",
                "description": "Título de la nota a explorar",
            },
            "depth": {
                "type": "integer",
                "description": "Profundidad de exploración (1-3, default 1)",
            },
        },
        "required": ["note"],
    }

    def execute(self, note: str, depth: int = 1) -> str:
        from config import VAULT_PATH
        from rag.graph import KnowledgeGraph

        graph = KnowledgeGraph(VAULT_PATH)
        depth = min(max(depth, 1), 3)

        connections = graph.get_connections(note, depth=depth)

        if not connections["nodes"]:
            return f"No se encontró la nota '{note}' en el grafo. ¿Querés que reconstruya el grafo?"

        lines = [f"**Conexiones de '{note}' (profundidad {depth}):**\n"]

        notes = [n for n in connections["nodes"] if n["type"] == "note"]
        tags = [n for n in connections["nodes"] if n["type"] == "tag"]

        if notes:
            lines.append("📝 **Notas conectadas:**")
            for n in notes:
                lines.append(f"  - {n['title']}")

        if tags:
            lines.append("\n🏷️ **Tags:**")
            for t in tags:
                lines.append(f"  - {t['title']}")

        lines.append(f"\n🔗 {len(connections['edges'])} conexiones totales")

        # Backlinks
        backlinks = graph.get_backlinks(note)
        if backlinks:
            lines.append(f"\n↩️ **Backlinks ({len(backlinks)}):**")
            for b in backlinks[:10]:
                ctx = f" — _{b['context'][:60]}..._" if b.get("context") else ""
                lines.append(f"  - {b['title']}{ctx}")

        return "\n".join(lines)


class GraphSearchTool(BaseTool):
    name = "graph_search"
    description = (
        "Busca en el grafo de conocimiento por tag, título, o relación. "
        "Puede encontrar notas con un tag específico, buscar caminos entre notas, "
        "o mostrar estadísticas del grafo."
    )
    parameters = {
        "type": "object",
        "properties": {
            "action": {
                "type": "string",
                "description": "Acción: 'tag' (buscar por tag), 'path' (camino entre notas), 'stats' (estadísticas), 'rebuild' (reconstruir grafo)",
                "enum": ["tag", "path", "stats", "rebuild"],
            },
            "query": {
                "type": "string",
                "description": "Tag a buscar, o nota de origen (para path)",
            },
            "target": {
                "type": "string",
                "description": "Nota de destino (solo para action='path')",
            },
        },
        "required": ["action"],
    }

    def execute(self, action: str, query: str = "", target: str = "") -> str:
        from config import VAULT_PATH
        from rag.graph import KnowledgeGraph

        graph = KnowledgeGraph(VAULT_PATH)

        if action == "rebuild":
            result = graph.build_graph()
            return f"Grafo reconstruido: {result['nodes']} nodos, {result['edges']} conexiones."

        if action == "tag":
            if not query:
                return "Necesito el tag a buscar."
            notes = graph.find_by_tag(query)
            if not notes:
                return f"No se encontraron notas con el tag #{query}."
            lines = [f"**Notas con #{query}:**"]
            for n in notes:
                lines.append(f"  - {n['title']}")
            return "\n".join(lines)

        if action == "path":
            if not query or not target:
                return "Necesito query (origen) y target (destino) para buscar el camino."
            path = graph.shortest_path(query, target)
            if not path:
                return f"No se encontró camino entre '{query}' y '{target}'."
            return f"**Camino:** {' → '.join(path)}"

        if action == "stats":
            stats = graph.get_stats()
            lines = [
                "**Estadísticas del Knowledge Graph:**\n",
                f"📝 Notas: {stats['total_notes']}",
                f"🏷️ Tags: {stats['total_tags']}",
                f"🔗 Conexiones: {stats['total_edges']}",
            ]
            if stats["most_connected"]:
                lines.append("\n**Notas más conectadas:**")
                for n in stats["most_connected"][:5]:
                    lines.append(f"  - {n['title']} ({n['connections']} conexiones)")
            if stats["orphan_notes"]:
                lines.append(f"\n🏝️ Notas huérfanas: {len(stats['orphan_notes'])}")
                for n in stats["orphan_notes"][:5]:
                    lines.append(f"  - {n}")
            return "\n".join(lines)

        return f"Acción '{action}' no reconocida."
