"""Knowledge Graph: mapea relaciones entre notas de Obsidian (wiki-links, tags, backlinks)."""

import logging
import os
import re
import sqlite3
from collections import deque
from dataclasses import dataclass, field
from pathlib import Path

from config import DB_PATH

logger = logging.getLogger(__name__)

WIKILINK_RE = re.compile(r'\[\[([^\]|]+)(?:\|[^\]]+)?\]\]')
TAG_RE = re.compile(r'(?<!\w)#([a-zA-Z][\w/-]*)')
HEADING_RE = re.compile(r'^#{1,6}\s+(.+)$', re.MULTILINE)


def _init_graph_db():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS graph_nodes (
                id        TEXT PRIMARY KEY,
                file_path TEXT,
                title     TEXT,
                tags      TEXT DEFAULT '[]',
                updated_at DATETIME
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS graph_edges (
                source    TEXT,
                target    TEXT,
                edge_type TEXT CHECK(edge_type IN ('wikilink','tag','heading')),
                context   TEXT DEFAULT '',
                PRIMARY KEY (source, target, edge_type)
            )
        """)
        conn.execute("CREATE INDEX IF NOT EXISTS idx_edge_source ON graph_edges(source)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_edge_target ON graph_edges(target)")


_init_graph_db()


@dataclass
class GraphNode:
    id: str
    title: str
    file_path: str = ""
    tags: list[str] = field(default_factory=list)
    node_type: str = "note"


@dataclass
class GraphEdge:
    source: str
    target: str
    edge_type: str
    context: str = ""


class KnowledgeGraph:
    def __init__(self, vault_path: str):
        self.vault_path = Path(vault_path)

    def build_graph(self) -> dict:
        """Escanea el vault y construye el grafo de conocimiento."""
        md_files = list(self.vault_path.rglob("*.md"))
        if not md_files:
            return {"nodes": 0, "edges": 0}

        nodes_count = 0
        edges_count = 0

        with sqlite3.connect(DB_PATH) as conn:
            conn.execute("DELETE FROM graph_nodes")
            conn.execute("DELETE FROM graph_edges")

            for file_path in md_files:
                try:
                    content = file_path.read_text(encoding="utf-8", errors="ignore")
                    title = file_path.stem
                    node_id = title.lower().replace(" ", "_")
                    mtime = os.path.getmtime(file_path)

                    # Extract tags
                    tags = list(set(TAG_RE.findall(content)))

                    # Insert node
                    conn.execute(
                        "INSERT OR REPLACE INTO graph_nodes (id, file_path, title, tags, updated_at) VALUES (?, ?, ?, ?, datetime(?, 'unixepoch'))",
                        (node_id, str(file_path), title, str(tags), mtime),
                    )
                    nodes_count += 1

                    # Extract wiki-links → edges
                    for match in WIKILINK_RE.finditer(content):
                        target_title = match.group(1).strip()
                        target_id = target_title.lower().replace(" ", "_")

                        # Get surrounding context (50 chars before/after)
                        start = max(0, match.start() - 50)
                        end = min(len(content), match.end() + 50)
                        ctx = content[start:end].replace("\n", " ").strip()

                        conn.execute(
                            "INSERT OR IGNORE INTO graph_edges (source, target, edge_type, context) VALUES (?, ?, 'wikilink', ?)",
                            (node_id, target_id, ctx),
                        )
                        edges_count += 1

                    # Tags as edges to tag nodes
                    for tag in tags:
                        tag_node_id = f"tag:{tag.lower()}"
                        conn.execute(
                            "INSERT OR REPLACE INTO graph_nodes (id, file_path, title, tags, updated_at) VALUES (?, '', ?, '[]', CURRENT_TIMESTAMP)",
                            (tag_node_id, f"#{tag}"),
                        )
                        conn.execute(
                            "INSERT OR IGNORE INTO graph_edges (source, target, edge_type) VALUES (?, ?, 'tag')",
                            (node_id, tag_node_id),
                        )
                        edges_count += 1

                except Exception as e:
                    logger.warning("Error procesando %s: %s", file_path.name, e)

        logger.info("Knowledge graph construido: %d nodos, %d edges", nodes_count, edges_count)
        return {"nodes": nodes_count, "edges": edges_count}

    def get_connections(self, note_title: str, depth: int = 1) -> dict:
        """BFS: encuentra nodos conectados hasta N niveles de profundidad."""
        start_id = note_title.lower().replace(" ", "_")
        visited = set()
        nodes = []
        edges = []
        queue = deque([(start_id, 0)])

        with sqlite3.connect(DB_PATH) as conn:
            conn.row_factory = sqlite3.Row

            while queue:
                current_id, current_depth = queue.popleft()
                if current_id in visited or current_depth > depth:
                    continue
                visited.add(current_id)

                # Get node info
                row = conn.execute(
                    "SELECT * FROM graph_nodes WHERE id=?", (current_id,)
                ).fetchone()
                if row:
                    nodes.append({
                        "id": row["id"],
                        "title": row["title"],
                        "tags": row["tags"],
                        "type": "tag" if current_id.startswith("tag:") else "note",
                    })

                if current_depth < depth:
                    # Outgoing edges
                    for edge in conn.execute(
                        "SELECT * FROM graph_edges WHERE source=?", (current_id,)
                    ).fetchall():
                        edges.append({
                            "from": edge["source"],
                            "to": edge["target"],
                            "type": edge["edge_type"],
                        })
                        if edge["target"] not in visited:
                            queue.append((edge["target"], current_depth + 1))

                    # Incoming edges (backlinks)
                    for edge in conn.execute(
                        "SELECT * FROM graph_edges WHERE target=?", (current_id,)
                    ).fetchall():
                        edges.append({
                            "from": edge["source"],
                            "to": edge["target"],
                            "type": edge["edge_type"],
                        })
                        if edge["source"] not in visited:
                            queue.append((edge["source"], current_depth + 1))

        return {"nodes": nodes, "edges": edges}

    def get_backlinks(self, note_title: str) -> list[dict]:
        """Notas que enlazan a esta nota."""
        target_id = note_title.lower().replace(" ", "_")
        with sqlite3.connect(DB_PATH) as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute(
                """SELECT n.title, n.id, e.context, e.edge_type
                   FROM graph_edges e JOIN graph_nodes n ON e.source = n.id
                   WHERE e.target=? AND e.edge_type='wikilink'""",
                (target_id,),
            ).fetchall()
            return [
                {"title": r["title"], "id": r["id"], "context": r["context"]}
                for r in rows
            ]

    def find_by_tag(self, tag: str) -> list[dict]:
        """Notas con un tag específico."""
        tag_id = f"tag:{tag.lower().lstrip('#')}"
        with sqlite3.connect(DB_PATH) as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute(
                """SELECT n.title, n.id, n.file_path
                   FROM graph_edges e JOIN graph_nodes n ON e.source = n.id
                   WHERE e.target=? AND e.edge_type='tag'""",
                (tag_id,),
            ).fetchall()
            return [{"title": r["title"], "id": r["id"]} for r in rows]

    def shortest_path(self, from_note: str, to_note: str) -> list[str]:
        """BFS shortest path entre dos notas."""
        start = from_note.lower().replace(" ", "_")
        end = to_note.lower().replace(" ", "_")

        if start == end:
            return [start]

        visited = {start}
        queue = deque([(start, [start])])

        with sqlite3.connect(DB_PATH) as conn:
            while queue:
                current, path = queue.popleft()
                if len(path) > 10:
                    break

                # Get neighbors (both directions)
                neighbors = set()
                for row in conn.execute(
                    "SELECT target FROM graph_edges WHERE source=?", (current,)
                ).fetchall():
                    neighbors.add(row[0])
                for row in conn.execute(
                    "SELECT source FROM graph_edges WHERE target=?", (current,)
                ).fetchall():
                    neighbors.add(row[0])

                for neighbor in neighbors:
                    if neighbor == end:
                        return path + [neighbor]
                    if neighbor not in visited:
                        visited.add(neighbor)
                        queue.append((neighbor, path + [neighbor]))

        return []

    def get_stats(self) -> dict:
        """Estadísticas del grafo."""
        with sqlite3.connect(DB_PATH) as conn:
            total_nodes = conn.execute(
                "SELECT COUNT(*) FROM graph_nodes WHERE id NOT LIKE 'tag:%'"
            ).fetchone()[0]
            total_tags = conn.execute(
                "SELECT COUNT(*) FROM graph_nodes WHERE id LIKE 'tag:%'"
            ).fetchone()[0]
            total_edges = conn.execute("SELECT COUNT(*) FROM graph_edges").fetchone()[0]

            # Most connected notes
            most_connected = conn.execute("""
                SELECT n.title,
                       (SELECT COUNT(*) FROM graph_edges WHERE source=n.id) +
                       (SELECT COUNT(*) FROM graph_edges WHERE target=n.id) as connections
                FROM graph_nodes n
                WHERE n.id NOT LIKE 'tag:%'
                ORDER BY connections DESC LIMIT 10
            """).fetchall()

            # Orphan notes (no edges)
            orphans = conn.execute("""
                SELECT n.title FROM graph_nodes n
                WHERE n.id NOT LIKE 'tag:%'
                  AND n.id NOT IN (SELECT source FROM graph_edges)
                  AND n.id NOT IN (SELECT target FROM graph_edges)
            """).fetchall()

        return {
            "total_notes": total_nodes,
            "total_tags": total_tags,
            "total_edges": total_edges,
            "most_connected": [{"title": r[0], "connections": r[1]} for r in most_connected],
            "orphan_notes": [r[0] for r in orphans],
        }

    def build_context_for_query(self, query: str) -> str:
        """Genera contexto de grafo para una query del usuario."""
        query_lower = query.lower().replace(" ", "_")

        # Try exact match first
        with sqlite3.connect(DB_PATH) as conn:
            row = conn.execute(
                "SELECT id, title FROM graph_nodes WHERE id=? OR title LIKE ?",
                (query_lower, f"%{query}%"),
            ).fetchone()

        if not row:
            return ""

        note_id = row[0]
        connections = self.get_connections(note_id, depth=1)

        if not connections["nodes"] and not connections["edges"]:
            return ""

        parts = [f"[Grafo de conocimiento — conexiones de '{row[1]}':]"]

        linked_notes = [n for n in connections["nodes"] if n["id"] != note_id and n["type"] == "note"]
        if linked_notes:
            parts.append("Notas relacionadas: " + ", ".join(n["title"] for n in linked_notes))

        tags = [n for n in connections["nodes"] if n["type"] == "tag"]
        if tags:
            parts.append("Tags: " + ", ".join(n["title"] for n in tags))

        backlinks = self.get_backlinks(row[1])
        if backlinks:
            parts.append("Notas que mencionan esto: " + ", ".join(b["title"] for b in backlinks[:5]))

        return "\n".join(parts) if len(parts) > 1 else ""
