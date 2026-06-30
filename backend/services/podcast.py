"""
Podcast project persistence layer.

Projects stored as JSON under data_dir/projects/podcast/<project_id>.json.
"""

from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .. import config
from ..models.podcast import (
    PodcastProject,
    PodcastProjectCreate,
    PodcastTemplate,
    PostProcessingConfig,
    SpeakerTurn,
    SpeakerTurnCreate,
    SpeakerTurnUpdate,
)
from . import podcast_templates

PROJECT_TYPE = "podcast"


def _dir() -> Path:
    d = config.get_data_dir() / "projects" / PROJECT_TYPE
    d.mkdir(parents=True, exist_ok=True)
    return d


def _path(project_id: str) -> Path:
    return _dir() / f"{project_id}.json"


def _load(project_id: str) -> PodcastProject | None:
    p = _path(project_id)
    if not p.exists():
        return None
    data = json.loads(p.read_text(encoding="utf-8"))
    # Re-hydrate nested objects
    if "template" in data and data["template"]:
        data["template"] = PodcastTemplate(**data["template"])
    if "speaker_turns" in data:
        data["speaker_turns"] = [SpeakerTurn(**t) for t in data["speaker_turns"]]
    if "post_processing" in data:
        data["post_processing"] = PostProcessingConfig(**data["post_processing"])
    return PodcastProject(**data)


def _save(project: PodcastProject) -> None:
    project.updated_at = datetime.now(timezone.utc).isoformat()
    _path(project.id).write_text(project.model_dump_json(indent=2), encoding="utf-8")


# ── project CRUD ─────────────────────────────────────────────────────

def list_projects() -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    for path in sorted(
        _dir().glob("*.json"), key=lambda p: p.stat().st_mtime, reverse=True,
    ):
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            continue
        items.append({
            "id": data.get("id"),
            "name": data.get("name"),
            "template_name": (
                data.get("template", {}).get("name") if data.get("template") else None
            ),
            "turn_count": len(data.get("speaker_turns", [])),
            "estimated_duration_sec": data.get("estimated_duration_sec"),
            "created_at": data.get("created_at"),
            "updated_at": data.get("updated_at"),
        })
    return items


def create_project(payload: PodcastProjectCreate) -> PodcastProject:
    project = PodcastProject(
        id=str(uuid.uuid4()),
        name=payload.name,
        description=payload.description,
    )
    if payload.template_id:
        tpl = podcast_templates.get_template(payload.template_id)
        if tpl:
            project.template = tpl
            project.template_id = tpl.id
    _save(project)
    return project


def get_project(project_id: str) -> PodcastProject | None:
    return _load(project_id)


def update_project(project_id: str, updates: dict[str, Any]) -> PodcastProject | None:
    project = _load(project_id)
    if project is None:
        return None
    for key in ("name", "description", "intro_text", "outro_text"):
        if key in updates and updates[key] is not None:
            setattr(project, key, updates[key])
    if "template_id" in updates and updates["template_id"] is not None:
        tpl = podcast_templates.get_template(updates["template_id"])
        if tpl:
            project.template = tpl
            project.template_id = tpl.id
    _save(project)
    return project


def delete_project(project_id: str) -> bool:
    p = _path(project_id)
    if p.exists():
        p.unlink()
        return True
    return False


# ── speaker turns ────────────────────────────────────────────────────

def add_turn(project_id: str, payload: SpeakerTurnCreate) -> PodcastProject | None:
    project = _load(project_id)
    if project is None:
        return None
    turn = SpeakerTurn(
        id=str(uuid.uuid4()),
        speaker_id=payload.speaker_id,
        speaker_name=payload.speaker_name,
        text=payload.text,
        emotion=payload.emotion,
        language=payload.language,
        pause_before=payload.pause_before,
        pause_after=payload.pause_after,
        profile_id=payload.profile_id,
        engine=payload.engine,
        sort_index=payload.sort_index or len(project.speaker_turns),
    )
    project.speaker_turns.append(turn)
    _save(project)
    return project


def update_turn(
    project_id: str,
    turn_id: str,
    payload: SpeakerTurnUpdate,
) -> PodcastProject | None:
    project = _load(project_id)
    if project is None:
        return None
    for i, turn in enumerate(project.speaker_turns):
        if turn.id == turn_id:
            updates = payload.model_dump(exclude_none=True)
            for key, val in updates.items():
                setattr(turn, key, val)
            project.speaker_turns[i] = turn
            _save(project)
            return project
    return None


def delete_turn(project_id: str, turn_id: str) -> PodcastProject | None:
    project = _load(project_id)
    if project is None:
        return None
    original_len = len(project.speaker_turns)
    project.speaker_turns = [t for t in project.speaker_turns if t.id != turn_id]
    if len(project.speaker_turns) == original_len:
        return None
    _save(project)
    return project


def reorder_turns(project_id: str, turn_ids: list[str]) -> PodcastProject | None:
    project = _load(project_id)
    if project is None:
        return None
    t_map = {t.id: t for t in project.speaker_turns}
    ordered: list[SpeakerTurn] = []
    for idx, tid in enumerate(turn_ids):
        t = t_map.get(tid)
        if t:
            t.sort_index = idx
            ordered.append(t)
    project.speaker_turns = ordered
    _save(project)
    return project


# ── apply template ───────────────────────────────────────────────────

def apply_template(project_id: str, template_id: str) -> PodcastProject | None:
    project = _load(project_id)
    if project is None:
        return None
    tpl = podcast_templates.get_template(template_id)
    if tpl is None:
        return None
    project.template = tpl
    project.template_id = tpl.id
    project.intro_text = tpl.intro_text or project.intro_text
    project.outro_text = tpl.outro_text or project.outro_text
    _save(project)
    return project


# ── post processing ──────────────────────────────────────────────────

def update_post_processing(
    project_id: str,
    config: dict[str, Any],
) -> PodcastProject | None:
    project = _load(project_id)
    if project is None:
        return None
    current = project.post_processing.model_dump()
    current.update({k: v for k, v in config.items() if v is not None})
    project.post_processing = PostProcessingConfig(**current)
    _save(project)
    return project


def get_post_processing(project_id: str) -> PostProcessingConfig | None:
    project = _load(project_id)
    if project is None:
        return None
    return project.post_processing
