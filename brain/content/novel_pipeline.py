"""Autonovel: long-form content generation with coherent multi-chapter output.

Inspired by NousResearch/autonovel.
Generates novels/long content via outline → chapter expansion → continuity review.
"""

import json
import logging
import time
from dataclasses import dataclass, field
from pathlib import Path

from inference_client import chat
from config import OLLAMA_MODEL, MEDIA_DOWNLOAD_DIR

logger = logging.getLogger(__name__)


@dataclass
class Chapter:
    number: int
    title: str
    summary: str = ""
    content: str = ""
    word_count: int = 0


@dataclass
class NovelProject:
    title: str
    genre: str = ""
    premise: str = ""
    outline: list[dict] = field(default_factory=list)
    chapters: list[Chapter] = field(default_factory=list)
    characters: list[dict] = field(default_factory=list)
    world_notes: str = ""
    total_words: int = 0
    output_path: str = ""


def generate_novel(
    premise: str,
    genre: str = "ficción",
    num_chapters: int = 5,
    words_per_chapter: int = 1500,
    model: str = "",
    output_dir: str = "",
) -> NovelProject:
    """Full pipeline: premise → outline → chapters → continuity review."""
    model = model or OLLAMA_MODEL
    out = Path(output_dir) if output_dir else Path(MEDIA_DOWNLOAD_DIR) / "novels" / f"novel_{int(time.time())}"
    out.mkdir(parents=True, exist_ok=True)

    project = NovelProject(title="", genre=genre, premise=premise)

    # Stage 1: World building + characters
    logger.info("[Autonovel] Construyendo mundo y personajes...")
    world = _build_world(premise, genre, model)
    project.title = world.get("title", premise[:50])
    project.characters = world.get("characters", [])
    project.world_notes = world.get("world_notes", "")

    # Stage 2: Generate outline
    logger.info("[Autonovel] Generando outline de %d capítulos...", num_chapters)
    project.outline = _generate_outline(premise, genre, num_chapters, project.characters, model)

    # Stage 3: Expand each chapter
    previous_summaries = []
    for i, chapter_outline in enumerate(project.outline):
        logger.info("[Autonovel] Escribiendo capítulo %d/%d...", i + 1, len(project.outline))
        chapter = _expand_chapter(
            chapter_outline, i + 1, project, previous_summaries,
            words_per_chapter, model,
        )
        project.chapters.append(chapter)
        previous_summaries.append(f"Cap {chapter.number} - {chapter.title}: {chapter.summary}")

    # Stage 4: Continuity review
    logger.info("[Autonovel] Revisando continuidad...")
    _continuity_review(project, model)

    # Save output
    project.total_words = sum(c.word_count for c in project.chapters)
    project.output_path = str(out / f"{_sanitize(project.title)}.md")
    _save_novel(project)

    logger.info("[Autonovel] Novela completa: %d palabras, %s", project.total_words, project.output_path)
    return project


def _build_world(premise: str, genre: str, model: str) -> dict:
    msg = (
        f"Sos un escritor de {genre}. A partir de esta premisa, creá el mundo de la historia.\n\n"
        f"PREMISA: {premise}\n\n"
        f"Generá un JSON con:\n"
        f'- "title": título de la novela\n'
        f'- "characters": lista de personajes, cada uno con "name", "role", "description", "arc"\n'
        f'- "world_notes": notas sobre el mundo, ambientación, reglas\n\n'
        f"Respondé SOLO con JSON válido."
    )
    response = chat(
        [{"role": "system", "content": f"Sos un worldbuilder experto en {genre}. Respondés en JSON."},
         {"role": "user", "content": msg}],
        model,
    )
    return _parse_json_object(response)


def _generate_outline(premise: str, genre: str, num_chapters: int, characters: list, model: str) -> list[dict]:
    chars_desc = json.dumps(characters, ensure_ascii=False)[:1000] if characters else "Sin personajes definidos"
    msg = (
        f"Generá un outline de {num_chapters} capítulos para esta novela.\n\n"
        f"PREMISA: {premise}\n"
        f"GÉNERO: {genre}\n"
        f"PERSONAJES: {chars_desc}\n\n"
        f"Para cada capítulo:\n"
        f'- "chapter": número\n'
        f'- "title": título del capítulo\n'
        f'- "summary": resumen de qué pasa (2-3 oraciones)\n'
        f'- "key_events": lista de eventos clave\n'
        f'- "pov": punto de vista (qué personaje)\n\n'
        f"Respondé SOLO con JSON array."
    )
    response = chat(
        [{"role": "system", "content": "Sos un novelista experto en estructura narrativa. Respondés en JSON."},
         {"role": "user", "content": msg}],
        model,
    )
    outline = _parse_json_array(response)
    if not outline:
        outline = [{"chapter": i + 1, "title": f"Capítulo {i + 1}", "summary": premise, "key_events": [], "pov": ""} for i in range(num_chapters)]
    return outline


def _expand_chapter(
    outline: dict, number: int, project: NovelProject,
    previous_summaries: list[str], target_words: int, model: str,
) -> Chapter:
    prev_context = "\n".join(previous_summaries[-3:]) if previous_summaries else "Este es el primer capítulo."
    chars_desc = json.dumps(project.characters, ensure_ascii=False)[:800] if project.characters else ""

    msg = (
        f"Escribí el capítulo {number} de la novela '{project.title}'.\n\n"
        f"OUTLINE DEL CAPÍTULO:\n{json.dumps(outline, ensure_ascii=False)}\n\n"
        f"CAPÍTULOS ANTERIORES (resumen):\n{prev_context}\n\n"
        f"PERSONAJES:\n{chars_desc}\n\n"
        f"NOTAS DEL MUNDO:\n{project.world_notes[:500]}\n\n"
        f"Escribí aproximadamente {target_words} palabras. "
        f"Mantené consistencia con los capítulos anteriores. "
        f"Usá diálogos, descripciones vívidas y desarrollo de personajes.\n\n"
        f"Escribí SOLO el contenido del capítulo."
    )

    content = chat(
        [{"role": "system", "content": f"Sos un novelista de {project.genre}. Escribís prosa envolvente y consistente."},
         {"role": "user", "content": msg}],
        model,
    )

    summary_msg = f"Resumí en 2-3 oraciones qué pasó en este capítulo:\n\n{content[:2000]}"
    summary = chat(
        [{"role": "user", "content": summary_msg}],
        model,
    ).strip()

    return Chapter(
        number=number,
        title=outline.get("title", f"Capítulo {number}"),
        summary=summary,
        content=content,
        word_count=len(content.split()),
    )


def _continuity_review(project: NovelProject, model: str):
    """Check for continuity errors across chapters."""
    summaries = "\n".join(
        f"Cap {c.number} - {c.title}: {c.summary}" for c in project.chapters
    )
    chars = json.dumps(project.characters, ensure_ascii=False)[:500]

    msg = (
        f"Revisá la continuidad de esta novela. ¿Hay inconsistencias?\n\n"
        f"PERSONAJES: {chars}\n"
        f"RESUMEN POR CAPÍTULO:\n{summaries}\n\n"
        f"Si encontrás problemas, listalós brevemente. Si todo está bien, decí 'Sin problemas de continuidad'."
    )
    review = chat(
        [{"role": "system", "content": "Sos un editor literario experto en continuidad narrativa."},
         {"role": "user", "content": msg}],
        model,
    ).strip()

    if "sin problemas" not in review.lower():
        logger.warning("[Autonovel] Problemas de continuidad detectados: %s", review[:200])


def _save_novel(project: NovelProject):
    """Save novel as markdown file."""
    lines = [f"# {project.title}\n"]
    if project.genre:
        lines.append(f"*Género: {project.genre}*\n")
    lines.append(f"*{project.total_words} palabras*\n\n---\n")

    for chapter in project.chapters:
        lines.append(f"\n## Capítulo {chapter.number}: {chapter.title}\n")
        lines.append(chapter.content)
        lines.append("\n")

    Path(project.output_path).write_text("\n".join(lines), encoding="utf-8")


def _sanitize(text: str) -> str:
    return "".join(c if c.isalnum() or c in " -_" else "" for c in text).strip().replace(" ", "_")[:50]


def _parse_json_object(text: str) -> dict:
    text = text.strip()
    start = text.find("{")
    end = text.rfind("}")
    if start >= 0 and end > start:
        try:
            return json.loads(text[start:end + 1])
        except json.JSONDecodeError:
            pass
    return {"title": text[:50], "characters": [], "world_notes": ""}


def _parse_json_array(text: str) -> list[dict]:
    text = text.strip()
    start = text.find("[")
    end = text.rfind("]")
    if start >= 0 and end > start:
        try:
            return json.loads(text[start:end + 1])
        except json.JSONDecodeError:
            pass
    return []
