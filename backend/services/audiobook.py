"""
Audiobook project persistence layer.

Projects stored as JSON under data_dir/projects/audiobook/<project_id>.json.
"""

from __future__ import annotations

import json
import re
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .. import config
from ..models.audiobook import (
    AudiobookChapter,
    AudiobookChapterCreate,
    AudiobookChapterUpdate,
    AudiobookProject,
    AudiobookProjectCreate,
    CharacterProfile,
    CharacterProfileCreate,
    CharacterProfileUpdate,
    NarratorConfig,
)
from .text_analyzer import detect_chapters, segment_text

PROJECT_TYPE = "audiobook"


def _dir() -> Path:
    d = config.get_data_dir() / "projects" / PROJECT_TYPE
    d.mkdir(parents=True, exist_ok=True)
    return d


def _path(project_id: str) -> Path:
    return _dir() / f"{project_id}.json"


def _load(project_id: str) -> AudiobookProject | None:
    p = _path(project_id)
    if not p.exists():
        return None
    return AudiobookProject(**json.loads(p.read_text(encoding="utf-8")))


def _save(project: AudiobookProject) -> None:
    project.updated_at = datetime.now(timezone.utc).isoformat()
    _path(project.id).write_text(project.model_dump_json(indent=2), encoding="utf-8")


# ── project CRUD ─────────────────────────────────────────────────────

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
            "author": data.get("author", ""),
            "chapter_count": len(data.get("chapters", [])),
            "character_count": len(data.get("characters", [])),
            "total_words": sum(
                len(ch.get("text", "").split())
                for ch in data.get("chapters", [])
            ),
            "created_at": data.get("created_at"),
            "updated_at": data.get("updated_at"),
        })
    return items


def create_project(payload: AudiobookProjectCreate) -> AudiobookProject:
    project = AudiobookProject(
        id=str(uuid.uuid4()),
        name=payload.name,
        description=payload.description,
        author=payload.author,
        raw_text=payload.raw_text or "",
    )
    # Auto-segment raw_text into chapters if provided
    if project.raw_text.strip():
        chapters_data = detect_chapters(project.raw_text)
        for i, cd in enumerate(chapters_data):
            ch = AudiobookChapter(
                id=str(uuid.uuid4()),
                title=cd["title"],
                chapter_index=i + 1,
                text=project.raw_text[cd["start_pos"]:cd["end_pos"]].strip(),
                word_count=len(project.raw_text[cd["start_pos"]:cd["end_pos"]].split()),
            )
            project.chapters.append(ch)
    _save(project)
    return project


def get_project(project_id: str) -> AudiobookProject | None:
    return _load(project_id)


def update_project(project_id: str, updates: dict[str, Any]) -> AudiobookProject | None:
    project = _load(project_id)
    if project is None:
        return None
    for key in ("name", "description", "author", "segment_strategy", "segment_word_limit"):
        if key in updates and updates[key] is not None:
            setattr(project, key, updates[key])
    if "narrator_profile_id" in updates and updates["narrator_profile_id"] is not None:
        project.narrator.profile_id = updates["narrator_profile_id"]
    if "raw_text" in updates and updates["raw_text"] is not None:
        project.raw_text = updates["raw_text"]
    _save(project)
    return project


def delete_project(project_id: str) -> bool:
    p = _path(project_id)
    if p.exists():
        p.unlink()
        return True
    return False


# ── chapter operations ───────────────────────────────────────────────

def add_chapter(project_id: str, payload: AudiobookChapterCreate) -> AudiobookProject | None:
    project = _load(project_id)
    if project is None:
        return None
    ch = AudiobookChapter(
        id=str(uuid.uuid4()),
        title=payload.title,
        chapter_index=payload.chapter_index or len(project.chapters) + 1,
        text=payload.text,
        word_count=len(payload.text.split()) if payload.text else 0,
    )
    project.chapters.append(ch)
    _save(project)
    return project


def update_chapter(
    project_id: str,
    chapter_id: str,
    payload: AudiobookChapterUpdate,
) -> AudiobookProject | None:
    project = _load(project_id)
    if project is None:
        return None
    for i, ch in enumerate(project.chapters):
        if ch.id == chapter_id:
            updates = payload.model_dump(exclude_none=True)
            for key, val in updates.items():
                setattr(ch, key, val)
            if "text" in updates or "chapter_index" in updates:
                ch.word_count = len(ch.text.split()) if ch.text else 0
            ch.updated_at = datetime.now(timezone.utc).isoformat()
            project.chapters[i] = ch
            _save(project)
            return project
    return None


def delete_chapter(project_id: str, chapter_id: str) -> AudiobookProject | None:
    project = _load(project_id)
    if project is None:
        return None
    original_len = len(project.chapters)
    project.chapters = [c for c in project.chapters if c.id != chapter_id]
    if len(project.chapters) == original_len:
        return None
    _save(project)
    return project


def reorder_chapters(project_id: str, chapter_ids: list[str]) -> AudiobookProject | None:
    project = _load(project_id)
    if project is None:
        return None
    ch_map = {c.id: c for c in project.chapters}
    ordered: list[AudiobookChapter] = []
    for idx, cid in enumerate(chapter_ids):
        ch = ch_map.get(cid)
        if ch:
            ch.chapter_index = idx + 1
            ordered.append(ch)
    project.chapters = ordered
    _save(project)
    return project


def segment_chapter(
    project_id: str,
    chapter_id: str,
) -> AudiobookProject | None:
    """Auto-segment a chapter into TTS-ready chunks based on project strategy."""
    project = _load(project_id)
    if project is None:
        return None
    for ch in project.chapters:
        if ch.id == chapter_id:
            strategy = project.segment_strategy
            limit = project.segment_word_limit
            segs = segment_text(ch.text, strategy=strategy, word_limit=limit)
            ch.segments = [
                {"text": s["text"], "character_id": None, "emotion": "neutral"}
                for s in segs
            ]
            ch.status = "segmenting"
            ch.updated_at = datetime.now(timezone.utc).isoformat()
            _save(project)
            return project
    return None


# ── character operations ─────────────────────────────────────────────

def add_character(project_id: str, payload: CharacterProfileCreate) -> AudiobookProject | None:
    project = _load(project_id)
    if project is None:
        return None
    char = CharacterProfile(
        id=str(uuid.uuid4()),
        name=payload.name,
        description=payload.description,
        profile_id=payload.profile_id,
        engine=payload.engine,
        language=payload.language,
        default_emotion=payload.default_emotion,
        emotion_constraints=payload.emotion_constraints,
    )
    project.characters.append(char)
    _save(project)
    return project


def update_character(
    project_id: str,
    character_id: str,
    payload: CharacterProfileUpdate,
) -> AudiobookProject | None:
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


def delete_character(project_id: str, character_id: str) -> AudiobookProject | None:
    project = _load(project_id)
    if project is None:
        return None
    original_len = len(project.characters)
    project.characters = [c for c in project.characters if c.id != character_id]
    if len(project.characters) == original_len:
        return None
    _save(project)
    return project


def auto_detect_characters(project_id: str) -> dict[str, Any]:
    """Run character name detection across all chapter texts."""
    from .text_analyzer import extract_character_names
    project = _load(project_id)
    if project is None:
        return {"error": "Project not found"}
    all_text = "\n\n".join(ch.text for ch in project.chapters)
    if not all_text:
        return {"characters": [], "total": 0}
    detected = extract_character_names(all_text)
    return {"characters": detected, "total": len(detected)}
