"""Spec Driven Development: especificaciones estructuradas para tareas complejas."""

import json
import logging
import sqlite3
import uuid
from dataclasses import dataclass, field
from datetime import datetime

from config import DB_PATH

logger = logging.getLogger(__name__)


@dataclass
class Spec:
    spec_id: str
    name: str
    objective: str
    context: str = ""
    steps: list[dict] = field(default_factory=list)
    acceptance_criteria: list[str] = field(default_factory=list)
    constraints: list[str] = field(default_factory=list)
    audience: str = ""
    tone: str = ""
    format_spec: str = ""
    examples: list[str] = field(default_factory=list)
    tags: list[str] = field(default_factory=list)
    status: str = "draft"
    created_at: str = ""
    updated_at: str = ""


def _init_specs_db():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS specs (
                spec_id    TEXT PRIMARY KEY,
                name       TEXT NOT NULL,
                objective  TEXT NOT NULL,
                context    TEXT DEFAULT '',
                steps      TEXT DEFAULT '[]',
                acceptance_criteria TEXT DEFAULT '[]',
                constraints TEXT DEFAULT '[]',
                audience   TEXT DEFAULT '',
                tone       TEXT DEFAULT '',
                format_spec TEXT DEFAULT '',
                examples   TEXT DEFAULT '[]',
                tags       TEXT DEFAULT '[]',
                status     TEXT DEFAULT 'draft',
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        """)


_init_specs_db()


class SpecManager:
    def create_spec(
        self,
        name: str,
        objective: str,
        context: str = "",
        steps: list[dict] = None,
        acceptance_criteria: list[str] = None,
        constraints: list[str] = None,
        audience: str = "",
        tone: str = "",
        format_spec: str = "",
        examples: list[str] = None,
        tags: list[str] = None,
    ) -> str:
        spec_id = str(uuid.uuid4())[:8]
        with sqlite3.connect(DB_PATH) as conn:
            conn.execute(
                """INSERT INTO specs (spec_id, name, objective, context, steps,
                   acceptance_criteria, constraints, audience, tone, format_spec, examples, tags)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    spec_id, name, objective, context,
                    json.dumps(steps or [], ensure_ascii=False),
                    json.dumps(acceptance_criteria or [], ensure_ascii=False),
                    json.dumps(constraints or [], ensure_ascii=False),
                    audience, tone, format_spec,
                    json.dumps(examples or [], ensure_ascii=False),
                    json.dumps(tags or [], ensure_ascii=False),
                ),
            )
        logger.info("Spec '%s' creada: %s", name, spec_id)
        return spec_id

    def get_spec(self, spec_id: str) -> Spec | None:
        with sqlite3.connect(DB_PATH) as conn:
            conn.row_factory = sqlite3.Row
            row = conn.execute("SELECT * FROM specs WHERE spec_id=?", (spec_id,)).fetchone()
            if not row:
                return None
            return self._row_to_spec(row)

    def find_spec(self, name: str) -> Spec | None:
        with sqlite3.connect(DB_PATH) as conn:
            conn.row_factory = sqlite3.Row
            row = conn.execute(
                "SELECT * FROM specs WHERE name LIKE ? ORDER BY updated_at DESC LIMIT 1",
                (f"%{name}%",),
            ).fetchone()
            if not row:
                return None
            return self._row_to_spec(row)

    def list_specs(self, tag: str = "", status: str = "") -> list[Spec]:
        with sqlite3.connect(DB_PATH) as conn:
            conn.row_factory = sqlite3.Row
            query = "SELECT * FROM specs"
            params = []
            conditions = []

            if status:
                conditions.append("status=?")
                params.append(status)
            if tag:
                conditions.append("tags LIKE ?")
                params.append(f"%{tag}%")

            if conditions:
                query += " WHERE " + " AND ".join(conditions)
            query += " ORDER BY updated_at DESC"

            rows = conn.execute(query, params).fetchall()
            return [self._row_to_spec(r) for r in rows]

    def update_spec(self, spec_id: str, **kwargs) -> bool:
        allowed = {
            "name", "objective", "context", "steps", "acceptance_criteria",
            "constraints", "audience", "tone", "format_spec", "examples", "tags", "status",
        }
        json_fields = {"steps", "acceptance_criteria", "constraints", "examples", "tags"}

        updates = []
        params = []
        for key, value in kwargs.items():
            if key not in allowed:
                continue
            if key in json_fields and isinstance(value, list):
                value = json.dumps(value, ensure_ascii=False)
            updates.append(f"{key}=?")
            params.append(value)

        if not updates:
            return False

        updates.append("updated_at=CURRENT_TIMESTAMP")
        params.append(spec_id)

        with sqlite3.connect(DB_PATH) as conn:
            cursor = conn.execute(
                f"UPDATE specs SET {', '.join(updates)} WHERE spec_id=?", params,
            )
            return cursor.rowcount > 0

    def delete_spec(self, spec_id: str) -> bool:
        with sqlite3.connect(DB_PATH) as conn:
            cursor = conn.execute("DELETE FROM specs WHERE spec_id=?", (spec_id,))
            return cursor.rowcount > 0

    def build_prompt_injection(self, spec: Spec) -> str:
        """Genera el bloque de contexto que se inyecta en el prompt del agente."""
        parts = [f"## ESPECIFICACIÓN: {spec.name}\n"]
        parts.append(f"**Objetivo:** {spec.objective}\n")

        if spec.context:
            parts.append(f"**Contexto:** {spec.context}\n")

        if spec.audience:
            parts.append(f"**Audiencia:** {spec.audience}")
        if spec.tone:
            parts.append(f"**Tono:** {spec.tone}")
        if spec.format_spec:
            parts.append(f"**Formato:** {spec.format_spec}")

        if spec.steps:
            parts.append("\n**Pasos:**")
            for i, step in enumerate(spec.steps, 1):
                if isinstance(step, dict):
                    desc = step.get("description", step.get("task", str(step)))
                    agent = step.get("agent", "")
                    agent_tag = f" [{agent}]" if agent else ""
                    parts.append(f"  {i}. {desc}{agent_tag}")
                else:
                    parts.append(f"  {i}. {step}")

        if spec.acceptance_criteria:
            parts.append("\n**Criterios de aceptación:**")
            for c in spec.acceptance_criteria:
                parts.append(f"  ✓ {c}")

        if spec.constraints:
            parts.append("\n**Restricciones:**")
            for c in spec.constraints:
                parts.append(f"  ⚠ {c}")

        if spec.examples:
            parts.append("\n**Ejemplos de referencia:**")
            for e in spec.examples:
                parts.append(f"  - {e}")

        return "\n".join(parts)

    def generate_spec_from_description(self, description: str) -> dict:
        """Usa el LLM para generar una spec estructurada desde una descripción libre."""
        from inference_client import chat
        from config import OLLAMA_MODEL

        prompt = f"""Analizá esta descripción de tarea y generá una especificación estructurada en JSON.

Descripción: {description}

Respondé SOLO con JSON válido con esta estructura:
{{
    "name": "nombre corto de la spec",
    "objective": "objetivo claro y medible",
    "context": "contexto relevante",
    "steps": [
        {{"description": "paso 1", "agent": "agente sugerido"}},
        {{"description": "paso 2", "agent": "agente sugerido"}}
    ],
    "acceptance_criteria": ["criterio 1", "criterio 2"],
    "constraints": ["restricción 1"],
    "audience": "audiencia objetivo",
    "tone": "tono del contenido",
    "format_spec": "formato esperado del resultado",
    "tags": ["tag1", "tag2"]
}}

Agentes disponibles: researcher, coder, analyst, media_specialist, designer, strategist, social_media, content_creator, sales, business, legal, director"""

        messages = [
            {"role": "system", "content": "Respondé SOLO con JSON válido."},
            {"role": "user", "content": prompt},
        ]

        response = chat(messages, OLLAMA_MODEL)

        try:
            text = response.strip()
            if "```" in text:
                text = text.split("```")[1]
                if text.startswith("json"):
                    text = text[4:]
                text = text.strip()
            return json.loads(text)
        except (json.JSONDecodeError, IndexError):
            return {
                "name": description[:50],
                "objective": description,
                "steps": [{"description": description, "agent": "researcher"}],
                "acceptance_criteria": ["Tarea completada satisfactoriamente"],
                "tags": [],
            }

    def _row_to_spec(self, row) -> Spec:
        return Spec(
            spec_id=row["spec_id"],
            name=row["name"],
            objective=row["objective"],
            context=row["context"] or "",
            steps=json.loads(row["steps"] or "[]"),
            acceptance_criteria=json.loads(row["acceptance_criteria"] or "[]"),
            constraints=json.loads(row["constraints"] or "[]"),
            audience=row["audience"] or "",
            tone=row["tone"] or "",
            format_spec=row["format_spec"] or "",
            examples=json.loads(row["examples"] or "[]"),
            tags=json.loads(row["tags"] or "[]"),
            status=row["status"] or "draft",
            created_at=row["created_at"] or "",
            updated_at=row["updated_at"] or "",
        )
