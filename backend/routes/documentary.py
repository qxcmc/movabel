"""
Documentary workspace API routes.

Manages documentary dubbing projects: CRUD for projects and scenes,
reference track analysis, SMPTE timecode handling.
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException

from .. import models
from ..models import documentary as dm
from ..services import documentary as doc_service

router = APIRouter(prefix="/projects/documentary", tags=["documentary"])


# ── projects ─────────────────────────────────────────────────────────

@router.get("/", response_model=dm.DocumentaryProjectsListResponse)
async def list_documentary_projects():
    items = doc_service.list_projects()
    return dm.DocumentaryProjectsListResponse(projects=items, total=len(items))


@router.post("/", response_model=dm.DocumentaryProjectResponse, status_code=201)
async def create_documentary_project(payload: dm.DocumentaryProjectCreate):
    project = doc_service.create_project(payload)
    return dm.DocumentaryProjectResponse(project=project)


@router.get("/{project_id}", response_model=dm.DocumentaryProjectResponse)
async def get_documentary_project(project_id: str):
    project = doc_service.get_project(project_id)
    if project is None:
        raise HTTPException(status_code=404, detail="Project not found")
    return dm.DocumentaryProjectResponse(project=project)


@router.patch("/{project_id}", response_model=dm.DocumentaryProjectResponse)
async def update_documentary_project(
    project_id: str,
    payload: dm.DocumentaryProjectUpdate,
):
    project = doc_service.update_project(
        project_id, payload.model_dump(exclude_none=True),
    )
    if project is None:
        raise HTTPException(status_code=404, detail="Project not found")
    return dm.DocumentaryProjectResponse(project=project)


@router.delete("/{project_id}")
async def delete_documentary_project(project_id: str):
    ok = doc_service.delete_project(project_id)
    if not ok:
        raise HTTPException(status_code=404, detail="Project not found")
    return {"deleted": True}


# ── scenes ───────────────────────────────────────────────────────────

@router.post(
    "/{project_id}/scenes",
    response_model=dm.DocumentaryProjectResponse,
    status_code=201,
)
async def add_scene(project_id: str, payload: dm.DocumentarySceneCreate):
    if not payload.text.strip():
        raise HTTPException(status_code=400, detail="Scene text is required")
    project = doc_service.add_scene(project_id, payload)
    if project is None:
        raise HTTPException(status_code=404, detail="Project not found")
    return dm.DocumentaryProjectResponse(project=project)


@router.patch(
    "/{project_id}/scenes/{scene_id}",
    response_model=dm.DocumentaryProjectResponse,
)
async def update_scene(
    project_id: str,
    scene_id: str,
    payload: dm.DocumentarySceneUpdate,
):
    project = doc_service.update_scene(project_id, scene_id, payload)
    if project is None:
        raise HTTPException(
            status_code=404, detail="Project or scene not found",
        )
    return dm.DocumentaryProjectResponse(project=project)


@router.delete(
    "/{project_id}/scenes/{scene_id}",
    response_model=dm.DocumentaryProjectResponse,
)
async def delete_scene(project_id: str, scene_id: str):
    project = doc_service.delete_scene(project_id, scene_id)
    if project is None:
        raise HTTPException(
            status_code=404, detail="Project or scene not found",
        )
    return dm.DocumentaryProjectResponse(project=project)


@router.post(
    "/{project_id}/scenes/reorder",
    response_model=dm.DocumentaryProjectResponse,
)
async def reorder_scenes(
    project_id: str,
    payload: models.ReorderRequest,
):
    project = doc_service.reorder_scenes(project_id, payload.scene_ids)
    if project is None:
        raise HTTPException(status_code=404, detail="Project not found")
    return dm.DocumentaryProjectResponse(project=project)


# ── reference track ─────────────────────────────────────────────────

@router.post("/{project_id}/reference/analyze")
async def analyze_reference_track(project_id: str):
    """Analyze the reference video/audio track and extract waveform data."""
    project = doc_service.get_project(project_id)
    if project is None:
        raise HTTPException(status_code=404, detail="Project not found")
    if not project.reference_track_path:
        raise HTTPException(
            status_code=400,
            detail="No reference track attached to this project.",
        )
    ref_path = project.reference_track_path
    import subprocess
    import tempfile
    from pathlib import Path

    if not Path(ref_path).exists():
        raise HTTPException(
            status_code=400,
            detail=f"Reference track not found: {ref_path}",
        )

    # Extract audio duration via ffprobe
    try:
        result = subprocess.run(
            [
                "ffprobe", "-v", "error", "-show_entries",
                "format=duration", "-of",
                "default=noprint_wrappers=1:nokey=1", ref_path,
            ],
            capture_output=True, text=True, check=True,
        )
        duration = float(result.stdout.strip())
    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to analyze reference track: {exc}",
        )

    # Generate waveform peaks for visualization (1 peak per 100ms)
    peaks: list[float] = []
    try:
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
            tmp_wav = tmp.name
        subprocess.run(
            [
                "ffmpeg", "-y", "-i", ref_path,
                "-ac", "1", "-ar", "16000", "-f", "wav", tmp_wav,
            ],
            capture_output=True, check=True,
        )
        import wave
        import struct

        with wave.open(tmp_wav, "rb") as wf:
            n_frames = wf.getnframes()
            sample_width = wf.getsampwidth()
            chunk_size = int(wf.getframerate() * 0.1)  # 100ms
            raw = wf.readframes(chunk_size)
            while raw:
                if sample_width == 2:
                    samples = struct.unpack(
                        f"<{len(raw) // 2}h", raw,
                    )
                    peak = max(abs(s) for s in samples) / 32768.0
                else:
                    peak = 0.0
                peaks.append(round(peak, 4))
                raw = wf.readframes(chunk_size)
    except Exception:
        peaks = []
    finally:
        Path(tmp_wav).unlink(missing_ok=True)

    project.reference_duration = duration
    doc_service.update_project(
        project_id,
        {"reference_duration": duration},
    )
    return {
        "project_id": project_id,
        "duration": duration,
        "format": Path(ref_path).suffix,
        "waveform_peaks": peaks,
        "sample_rate": 10,  # 10 peaks per second (every 100ms)
    }
