"""
Documentary project persistence layer.

Projects are stored as JSON files under data_dir/projects/documentary/<project_id>.json.
"""

from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .. import config
from ..models.documentary import (
    DocumentaryProject,
    DocumentaryProjectCreate,
    DocumentaryScene,
    DocumentarySceneCreate,
    DocumentarySceneUpdate,
    SceneVoiceBinding,
)

PROJECT_TYPE = "documentary"


def _projects_dir() -> Path:
    d = config.get_data_dir() / "projects" / PROJECT_TYPE
    d.mkdir(parents=True, exist_ok=True)
    return d


def _project_path(project_id: str) -> Path:
    return _projects_dir() / f"{project_id}.json"


def _load(project_id: str) -> DocumentaryProject | None:
    p = _project_path(project_id)
    if not p.exists():
        return None
    return DocumentaryProject(**json.loads(p.read_text(encoding="utf-8")))


def _save(project: DocumentaryProject) -> None:
    p = _project_path(project.id)
    project.updated_at = datetime.now(timezone.utc).isoformat()
    p.write_text(project.model_dump_json(indent=2), encoding="utf-8")


def list_projects() -> list[dict[str, Any]]:
    """Return lightweight summaries of all documentary projects."""
    items: list[dict[str, Any]] = []
    for path in sorted(_projects_dir().glob("*.json"), key=lambda p: p.stat().st_mtime, reverse=True):
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            continue
        items.append({
            "id": data.get("id"),
            "name": data.get("name"),
            "description": data.get("description", ""),
            "scene_count": len(data.get("scenes", [])),
            "created_at": data.get("created_at"),
            "updated_at": data.get("updated_at"),
        })
    return items


def create_project(payload: DocumentaryProjectCreate) -> DocumentaryProject:
    project = DocumentaryProject(
        id=str(uuid.uuid4()),
        name=payload.name,
        description=payload.description,
        reference_track_path=payload.reference_track_path,
    )
    _save(project)
    return project


def get_project(project_id: str) -> DocumentaryProject | None:
    return _load(project_id)


def update_project(project_id: str, payload: dict[str, Any]) -> DocumentaryProject | None:
    project = _load(project_id)
    if project is None:
        return None
    for key in ("name", "description", "reference_track_path", "default_profile_id"):
        if key in payload and payload[key] is not None:
            setattr(project, key, payload[key])
    _save(project)
    return project


def delete_project(project_id: str) -> bool:
    p = _project_path(project_id)
    if p.exists():
        p.unlink()
        return True
    return False


# ── scene operations ─────────────────────────────────────────────────

def _resolve_voice_binding(
    profile_id: str | None,
    engine: str | None,
    language: str | None,
) -> SceneVoiceBinding | None:
    if not profile_id and not engine:
        return None
    return SceneVoiceBinding(
        profile_id=profile_id or "",
        engine=engine,
        language=language or "en",
    )


def add_scene(project_id: str, payload: DocumentarySceneCreate) -> DocumentaryProject | None:
    project = _load(project_id)
    if project is None:
        return None
    scene = DocumentaryScene(
        id=str(uuid.uuid4()),
        title=payload.title,
        text=payload.text,
        timecode_start=payload.timecode_start,
        timecode_end=payload.timecode_end,
        timecode_mode=payload.timecode_mode,
        voice_binding=_resolve_voice_binding(
            payload.profile_id, payload.engine, payload.language,
        ),
        sort_index=payload.sort_index,
    )
    project.scenes.append(scene)
    _save(project)
    return project


def update_scene(
    project_id: str,
    scene_id: str,
    payload: DocumentarySceneUpdate,
) -> DocumentaryProject | None:
    project = _load(project_id)
    if project is None:
        return None
    for i, scene in enumerate(project.scenes):
        if scene.id == scene_id:
            updates = payload.model_dump(exclude_none=True)
            if "profile_id" in updates or "engine" in updates or "language" in updates:
                current = scene.voice_binding or SceneVoiceBinding(profile_id="", language="en")
                profile_id = updates.pop("profile_id", current.profile_id)
                engine = updates.pop("engine", current.engine)
                language = updates.pop("language", current.language)
                scene.voice_binding = SceneVoiceBinding(
                    profile_id=profile_id,
                    engine=engine,
                    language=language,
                )
            for key, val in updates.items():
                setattr(scene, key, val)
            scene.updated_at = datetime.now(timezone.utc).isoformat()
            project.scenes[i] = scene
            _save(project)
            return project
    return None


def delete_scene(project_id: str, scene_id: str) -> DocumentaryProject | None:
    project = _load(project_id)
    if project is None:
        return None
    original_len = len(project.scenes)
    project.scenes = [s for s in project.scenes if s.id != scene_id]
    if len(project.scenes) == original_len:
        return None  # scene not found
    _save(project)
    return project


def reorder_scenes(
    project_id: str,
    scene_ids: list[str],
) -> DocumentaryProject | None:
    """Re-order scenes to match the provided ID list."""
    project = _load(project_id)
    if project is None:
        return None
    scene_map = {s.id: s for s in project.scenes}
    ordered: list[DocumentaryScene] = []
    for idx, sid in enumerate(scene_ids):
        scene = scene_map.get(sid)
        if scene:
            scene.sort_index = idx
            ordered.append(scene)
    project.scenes = ordered
    _save(project)
    return project
