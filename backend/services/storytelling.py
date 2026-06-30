"""
Storytelling project persistence layer.

Projects stored as JSON under data_dir/projects/storytelling/<project_id>.json.
"""

from __future__ import annotations

import json
import re
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .. import config
from ..models.storytelling import (
    SFXCue,
    StoryCharacter,
    StoryCharacterCreate,
    StoryCharacterUpdate,
    StoryParagraph,
    StoryParagraphCreate,
    StoryParagraphUpdate,
    StoryProject,
    StoryProjectCreate,
)

PROJECT_TYPE = "storytelling"


def _dir() -> Path:
    d = config.get_data_dir() / "projects" / PROJECT_TYPE
    d.mkdir(parents=True, exist_ok=True)
    return d


def _path(project_id: str) -> Path:
    return _dir() / f"{project_id}.json"


def _load(project_id: str) -> StoryProject | None:
    p = _path(project_id)
    if not p.exists():
        return None
    return StoryProject(**json.loads(p.read_text(encoding="utf-8")))


def _save(project: StoryProject) -> None:
    project.updated_at = datetime.now(timezone.utc).isoformat()
    _path(project.id).write_text(project.model_dump_json(indent=2), encoding="utf-8")


def list_projects() -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    for path in sorted(_dir().glob("*.json"), key=lambda p: p.stat().st_mtime, reverse=True):
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            continue
        items.append({
            "id": data.get("id"),
            "name": data.get("name"),
            "description": data.get("description", ""),
            "character_count": len(data.get("characters", [])),
            "paragraph_count": len(data.get("paragraphs", [])),
            "created_at": data.get("created_at"),
            "updated_at": data.get("updated_at"),
        })
    return items


def create_project(payload: StoryProjectCreate) -> StoryProject:
    project = StoryProject(
        id=str(uuid.uuid4()),
        name=payload.name,
        description=payload.description,
    )
    _save(project)
    return project


def get_project(project_id: str) -> StoryProject | None:
    return _load(project_id)


def update_project(project_id: str, updates: dict[str, Any]) -> StoryProject | None:
    project = _load(project_id)
    if project is None:
        return None
    for key in ("name", "description", "narrator_profile_id"):
        if key in updates and updates[key] is not None:
            setattr(project, key, updates[key])
    _save(project)
    return project


def delete_project(project_id: str) -> bool:
    p = _path(project_id)
    if p.exists():
        p.unlink()
        return True
    return False


# ── character operations ─────────────────────────────────────────────

def add_character(project_id: str, payload: StoryCharacterCreate) -> StoryProject | None:
    project = _load(project_id)
    if project is None:
        return None
    char = StoryCharacter(
        id=str(uuid.uuid4()),
        name=payload.name,
        description=payload.description,
        profile_id=payload.profile_id,
        engine=payload.engine,
        language=payload.language,
        default_emotion=payload.default_emotion,
    )
    project.characters.append(char)
    _save(project)
    return project


def update_character(
    project_id: str,
    character_id: str,
    payload: StoryCharacterUpdate,
) -> StoryProject | None:
    project = _load(project_id)
    if project is None:
        return None
    for i, char in enumerate(project.characters):
        if char.id == character_id:
            updates = payload.model_dump(exclude_none=True)
            for key, val in updates.items():
                setattr(char, key, val)
            project.characters[i] = char
            _save(project)
            return project
    return None


def delete_character(project_id: str, character_id: str) -> StoryProject | None:
    project = _load(project_id)
    if project is None:
        return None
    original_len = len(project.characters)
    project.characters = [c for c in project.characters if c.id != character_id]
    if len(project.characters) == original_len:
        return None
    # Also un-assign this character from paragraphs
    for para in project.paragraphs:
        if para.character_id == character_id:
            para.character_id = None
    _save(project)
    return project


# ── paragraph operations ────────────────────────────────────────────

def add_paragraph(project_id: str, payload: StoryParagraphCreate) -> StoryProject | None:
    project = _load(project_id)
    if project is None:
        return None
    para = StoryParagraph(
        id=str(uuid.uuid4()),
        text=payload.text,
        character_id=payload.character_id,
        emotion=payload.emotion,
        sort_index=payload.sort_index,
    )
    # Auto-detect dialogue
    if para.text:
        para.is_dialogue = _detect_dialogue(para.text)
        if para.is_dialogue:
            para.speaker_name = _extract_speaker(para.text)
    project.paragraphs.append(para)
    _save(project)
    return project


def update_paragraph(
    project_id: str,
    paragraph_id: str,
    payload: StoryParagraphUpdate,
) -> StoryProject | None:
    project = _load(project_id)
    if project is None:
        return None
    for i, para in enumerate(project.paragraphs):
        if para.id == paragraph_id:
            updates = payload.model_dump(exclude_none=True)
            for key, val in updates.items():
                setattr(para, key, val)
            # Re-detect dialogue if text changed
            if "text" in updates:
                para.is_dialogue = _detect_dialogue(para.text)
                if para.is_dialogue:
                    para.speaker_name = _extract_speaker(para.text)
            para.updated_at = datetime.now(timezone.utc).isoformat()
            project.paragraphs[i] = para
            _save(project)
            return project
    return None


def delete_paragraph(project_id: str, paragraph_id: str) -> StoryProject | None:
    project = _load(project_id)
    if project is None:
        return None
    original_len = len(project.paragraphs)
    project.paragraphs = [p for p in project.paragraphs if p.id != paragraph_id]
    if len(project.paragraphs) == original_len:
        return None
    _save(project)
    return project


def reorder_paragraphs(project_id: str, paragraph_ids: list[str]) -> StoryProject | None:
    project = _load(project_id)
    if project is None:
        return None
    para_map = {p.id: p for p in project.paragraphs}
    ordered: list[StoryParagraph] = []
    for idx, pid in enumerate(paragraph_ids):
        p = para_map.get(pid)
        if p:
            p.sort_index = idx
            ordered.append(p)
    project.paragraphs = ordered
    _save(project)
    return project


# ── SFX cue operations ───────────────────────────────────────────────

def add_sfx_cue(project_id: str, payload: dict[str, Any]) -> StoryProject | None:
    project = _load(project_id)
    if project is None:
        return None
    cue = SFXCue(
        id=str(uuid.uuid4()),
        name=payload.get("name", "SFX"),
        category=payload.get("category", ""),
        file_path=payload.get("file_path", ""),
        start_time=payload.get("start_time", 0.0),
        fade_in=payload.get("fade_in", 0.0),
        fade_out=payload.get("fade_out", 0.0),
        volume=payload.get("volume", 1.0),
    )
    project.sfx_cues.append(cue)
    _save(project)
    return project


def delete_sfx_cue(project_id: str, cue_id: str) -> StoryProject | None:
    project = _load(project_id)
    if project is None:
        return None
    original_len = len(project.sfx_cues)
    project.sfx_cues = [c for c in project.sfx_cues if c.id != cue_id]
    if len(project.sfx_cues) == original_len:
        return None
    _save(project)
    return project


# ── dialogue detection helpers ──────────────────────────────────────

def _detect_dialogue(text: str) -> bool:
    """Detect if a paragraph contains quoted dialogue."""
    if not text:
        return False
    # Check for paired quotes (Chinese or English)
    paired = bool(re.search(r'["\u201c\u201d].*?["\u201c\u201d]', text, re.DOTALL))
    if paired:
        return True
    # Check for em-dash or dash dialogue markers
    if re.search(r'[\u2014\-]\s*[A-Z\u4e00-\u9fff]', text):
        return True
    return False


def _extract_speaker(text: str) -> str | None:
    """Try to extract a speaker name from quoted dialogue."""
    # Pattern: "Name: 'dialogue'" or "Name: dialogue"
    m = re.match(r'^([A-Za-z\u4e00-\u9fff]+)\s*[:：]\s*["\u201c]', text)
    if m:
        return m.group(1)
    return None


def auto_assign_characters(project_id: str) -> dict[str, Any]:
    """Auto-assign characters to paragraphs based on speaker detection."""
    project = _load(project_id)
    if project is None:
        return {"error": "Project not found"}
    assigned = 0
    char_map = {c.name.lower(): c.id for c in project.characters}
    for para in project.paragraphs:
        if para.speaker_name and para.character_id is None:
            sid = char_map.get(para.speaker_name.lower())
            if sid:
                para.character_id = sid
                assigned += 1
    _save(project)
    return {"assigned": assigned, "total_paragraphs": len(project.paragraphs)}
