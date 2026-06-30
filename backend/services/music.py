"""
Music project persistence and style library.

Projects stored as JSON under data_dir/projects/music/<project_id>.json.
"""

from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .. import config
from ..models.music import (
    MusicProject,
    MusicProjectCreate,
    MusicProjectUpdate,
    MusicStyle,
)

PROJECT_TYPE = "music"

# ── built-in style library ──────────────────────────────────────────

BUILTIN_STYLES: list[MusicStyle] = [
    MusicStyle(id="classical", name="Classical", description="Orchestral classical music", category="traditional", tags=["orchestra", "symphony", "piano"]),
    MusicStyle(id="jazz", name="Jazz", description="Swing, bebop, and smooth jazz", category="traditional", tags=["saxophone", "swing", "bebop"]),
    MusicStyle(id="electronic", name="Electronic", description="EDM, synthwave, ambient electronic", category="modern", tags=["synth", "edm", "ambient"]),
    MusicStyle(id="rock", name="Rock", description="Electric guitar-driven rock music", category="traditional", tags=["guitar", "drums", "metal"]),
    MusicStyle(id="folk", name="Folk", description="Acoustic folk and traditional music", category="traditional", tags=["acoustic", "guitar", "traditional"]),
    MusicStyle(id="pop", name="Pop", description="Catchy mainstream pop music", category="modern", tags=["vocal", "catchy", "mainstream"]),
    MusicStyle(id="hiphop", name="Hip-Hop", description="Rap beats and hip-hop instrumentals", category="modern", tags=["rap", "beats", "trap"]),
    MusicStyle(id="ambient", name="Ambient", description="Atmospheric ambient and drone music", category="modern", tags=["atmospheric", "drone", "soundscape"]),
    MusicStyle(id="epic", name="Epic", description="Cinematic epic orchestral music", category="cinematic", tags=["orchestra", "cinematic", "trailer"]),
    MusicStyle(id="chiptune", name="8-Bit / Chiptune", description="Retro video game music style", category="electronic", tags=["retro", "game", "arcade"]),
    MusicStyle(id="funk", name="Funk", description="Groovy funk with prominent bass", category="traditional", tags=["bass", "groove", "rhythm"]),
    MusicStyle(id="reggae", name="Reggae", description="Laid-back reggae and dub", category="traditional", tags=["dub", "ska", "caribbean"]),
    MusicStyle(id="soul", name="Soul", description="Emotional soul and R&B", category="traditional", tags=["vocal", "emotional", "motown"]),
    MusicStyle(id="rnb", name="R&B", description="Contemporary rhythm and blues", category="modern", tags=["vocal", "smooth", "contemporary"]),
    MusicStyle(id="newage", name="New Age", description="Meditative new age music", category="modern", tags=["meditation", "relaxation", "spiritual"]),
    MusicStyle(id="lofi", name="Lo-Fi", description="Lo-fi hip hop beats for study/relaxation", category="modern", tags=["chill", "study", "beats"]),
    MusicStyle(id="latin", name="Latin", description="Latin, salsa, bossa nova rhythms", category="traditional", tags=["salsa", "bossa", "samba"]),
    MusicStyle(id="blues", name="Blues", description="Traditional blues and delta blues", category="traditional", tags=["guitar", "harmonica", "delta"]),
    MusicStyle(id="country", name="Country", description="Country and western music", category="traditional", tags=["guitar", "banjo", "western"]),
]


def list_styles() -> list[MusicStyle]:
    return list(BUILTIN_STYLES)


def get_style(style_id: str) -> MusicStyle | None:
    for s in BUILTIN_STYLES:
        if s.id == style_id:
            return s
    return None


# ── project persistence ─────────────────────────────────────────────


def _projects_dir() -> Path:
    d = config.get_data_dir() / "projects" / PROJECT_TYPE
    d.mkdir(parents=True, exist_ok=True)
    return d


def _project_path(project_id: str) -> Path:
    return _projects_dir() / f"{project_id}.json"


def _load(project_id: str) -> MusicProject | None:
    p = _project_path(project_id)
    if not p.exists():
        return None
    return MusicProject(**json.loads(p.read_text(encoding="utf-8")))


def _save(project: MusicProject) -> None:
    project.updated_at = datetime.now(timezone.utc)
    _project_path(project.id).write_text(
        project.model_dump_json(indent=2), encoding="utf-8",
    )


def list_projects() -> list[MusicProject]:
    projects: list[MusicProject] = []
    d = _projects_dir()
    if not d.exists():
        return projects
    for p in sorted(d.glob("*.json")):
        try:
            projects.append(MusicProject(**json.loads(p.read_text(encoding="utf-8"))))
        except Exception:
            continue
    return projects


def create_project(payload: MusicProjectCreate) -> MusicProject:
    project = MusicProject(
        id=str(uuid.uuid4()),
        name=payload.name,
        description=payload.description,
        prompt=payload.prompt,
        style=payload.style,
        duration=payload.duration,
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )
    _save(project)
    return project


def get_project(project_id: str) -> MusicProject | None:
    return _load(project_id)


def update_project(project_id: str, updates: dict[str, Any]) -> MusicProject | None:
    project = _load(project_id)
    if project is None:
        return None
    for k, v in updates.items():
        if v is not None and hasattr(project, k):
            setattr(project, k, v)
    _save(project)
    return project


def delete_project(project_id: str) -> bool:
    p = _project_path(project_id)
    if not p.exists():
        return False
    p.unlink()
    return True


def add_output_path(project_id: str, output_path: str) -> MusicProject | None:
    project = _load(project_id)
    if project is None:
        return None
    if output_path not in project.output_paths:
        project.output_paths.append(output_path)
    _save(project)
    return project
