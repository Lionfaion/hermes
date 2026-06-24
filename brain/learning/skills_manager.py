"""
Gestiona el archivo skills.yaml — base de conocimiento de comportamiento aprendido.
Las lecciones se inyectan al system prompt en cada conversación.
"""
import logging
from pathlib import Path

import yaml

from config import SKILLS_PATH, MAX_SKILLS

logger = logging.getLogger(__name__)

_DEFAULT = {"reglas": [], "preferencias": [], "errores_conocidos": []}


class SkillsManager:
    def __init__(self):
        self.path = Path(SKILLS_PATH)
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def load(self) -> dict:
        if not self.path.exists():
            return dict(_DEFAULT)
        try:
            with open(self.path, "r", encoding="utf-8") as f:
                data = yaml.safe_load(f)
            return data if isinstance(data, dict) else dict(_DEFAULT)
        except Exception as e:
            logger.warning("Error leyendo skills.yaml: %s", e)
            return dict(_DEFAULT)

    def save(self, skills: dict):
        try:
            with open(self.path, "w", encoding="utf-8") as f:
                yaml.dump(skills, f, allow_unicode=True, default_flow_style=False)
        except Exception as e:
            logger.error("Error guardando skills.yaml: %s", e)

    def add_lessons(self, lessons: list):
        skills = self.load()

        for lesson in lessons:
            cat = lesson.get("categoria", "reglas")
            text = lesson.get("texto", "").strip()
            if not text:
                continue
            if cat not in skills:
                skills[cat] = []
            if text not in skills[cat]:
                skills[cat].append(text)

        # Poda: conservar solo las últimas MAX_SKILLS por categoría
        for key in skills:
            if isinstance(skills[key], list) and len(skills[key]) > MAX_SKILLS:
                skills[key] = skills[key][-MAX_SKILLS:]

        self.save(skills)
        logger.info("skills.yaml actualizado con %d lecciones.", len(lessons))

    def build_system_injection(self) -> str:
        skills = self.load()
        parts = []

        if skills.get("preferencias"):
            parts.append("Preferencias del usuario:")
            parts.extend(f"- {p}" for p in skills["preferencias"])

        if skills.get("reglas"):
            parts.append("Reglas aprendidas de experiencia:")
            parts.extend(f"- {r}" for r in skills["reglas"])

        if skills.get("errores_conocidos"):
            parts.append("Errores que debes evitar:")
            parts.extend(f"- {e}" for e in skills["errores_conocidos"])

        return "\n".join(parts)
