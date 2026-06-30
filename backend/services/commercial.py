"""
Commercial project persistence layer.

Projects stored as JSON under data_dir/projects/commercial/<project_id>.json.
"""

from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .. import config
from ..models.commercial import (
    CommercialProject,
    CommercialProjectCreate,
    CommercialSegment,
    CommercialSegmentCreate,
    CommercialSegmentUpdate,
    EmotionPresetRef,
)

PROJECT_TYPE = "commercial"


def _dir() -> Path:
    d = config.get_data_dir() / "projects" / PROJECT_TYPE
    d.mkdir(parents=True, exist_ok=True)
    return d


def _path(project_id: str) -> Path:
    return _dir() / f"{project_id}.json"


def _load(project_id: str) -> CommercialProject | None:
    p = _path(project_id)
    if not p.exists():
        return None
    return CommercialProject(**json.loads(p.read_text(encoding="utf-8")))


def _save(project: CommercialProject) -> None:
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
            "segment_count": len(data.get("segments", [])),
            "created_at": data.get("created_at"),
            "updated_at": data.get("updated_at"),
        })
    return items


def create_project(payload: CommercialProjectCreate) -> CommercialProject:
    project = CommercialProject(
        id=str(uuid.uuid4()),
        name=payload.name,
        description=payload.description,
        reference_path=payload.reference_path,
    )
    _save(project)
    return project


def get_project(project_id: str) -> CommercialProject | None:
    return _load(project_id)


def update_project(project_id: str, updates: dict[str, Any]) -> CommercialProject | None:
    project = _load(project_id)
    if project is None:
        return None
    for key in ("name", "description", "reference_path", "default_profile_id"):
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


# ── segment operations ───────────────────────────────────────────────

def add_segment(project_id: str, payload: CommercialSegmentCreate) -> CommercialProject | None:
    project = _load(project_id)
    if project is None:
        return None
    seg = CommercialSegment(
        id=str(uuid.uuid4()),
        title=payload.title,
        text=payload.text,
        profile_id=payload.profile_id,
        engine=payload.engine,
        language=payload.language,
        emotion=EmotionPresetRef(preset_id=payload.preset_id),
        sort_index=payload.sort_index,
    )
    project.segments.append(seg)
    _save(project)
    return project


def update_segment(
    project_id: str,
    segment_id: str,
    payload: CommercialSegmentUpdate,
) -> CommercialProject | None:
    project = _load(project_id)
    if project is None:
        return None
    for i, seg in enumerate(project.segments):
        if seg.id == segment_id:
            updates = payload.model_dump(exclude_none=True)
            if "preset_id" in updates:
                preset_id = updates.pop("preset_id")
                seg.emotion = EmotionPresetRef(preset_id=preset_id)
            for key, val in updates.items():
                setattr(seg, key, val)
            seg.updated_at = datetime.now(timezone.utc).isoformat()
            project.segments[i] = seg
            _save(project)
            return project
    return None


def delete_segment(project_id: str, segment_id: str) -> CommercialProject | None:
    project = _load(project_id)
    if project is None:
        return None
    original_len = len(project.segments)
    project.segments = [s for s in project.segments if s.id != segment_id]
    if len(project.segments) == original_len:
        return None
    _save(project)
    return project


def reorder_segments(project_id: str, segment_ids: list[str]) -> CommercialProject | None:
    project = _load(project_id)
    if project is None:
        return None
    seg_map = {s.id: s for s in project.segments}
    ordered: list[CommercialSegment] = []
    for idx, sid in enumerate(segment_ids):
        s = seg_map.get(sid)
        if s:
            s.sort_index = idx
            ordered.append(s)
    project.segments = ordered
    _save(project)
    return project
