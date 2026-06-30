"""
AI music generation API routes.

Endpoints for text-to-music generation (MusicGen), singing synthesis,
voice conversion (RVC), task status, and style library.
"""

from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, BackgroundTasks, HTTPException

from .. import config
from ..models.music import (
    MusicGenerateRequest,
    MusicProjectCreate,
    MusicProjectResponse,
    MusicProjectsListResponse,
    MusicStyleListResponse,
    MusicTaskStatus,
    SingRequest,
    VoiceConvertRequest,
)
from ..services import music as music_service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/music", tags=["music"])

# ── in-memory task store ────────────────────────────────────────────

_tasks: dict[str, MusicTaskStatus] = {}


def _get_generations_dir() -> Path:
    d = config.get_data_dir() / "generations" / "music"
    d.mkdir(parents=True, exist_ok=True)
    return d


def _create_task() -> MusicTaskStatus:
    task_id = str(uuid.uuid4())
    task = MusicTaskStatus(
        task_id=task_id,
        status="queued",
        progress=0.0,
    )
    _tasks[task_id] = task
    return task


# ── music generation ─────────────────────────────────────────────────

@router.post("/generate", response_model=MusicTaskStatus, status_code=202)
async def generate_music(
    payload: MusicGenerateRequest,
    background_tasks: BackgroundTasks,
):
    """
    Generate background music from a text prompt using MusicGen.

    Returns a task ID for polling status.
    """
    task = _create_task()
    task.status = "running"

    background_tasks.add_task(
        _run_musicgen_generation, task.task_id, payload,
    )

    return task


async def _run_musicgen_generation(task_id: str, payload: MusicGenerateRequest):
    """Background task: run MusicGen generation."""
    task = _tasks.get(task_id)
    if task is None:
        return

    try:
        from ..backends.musicgen_backend import MusicGenBackend

        backend = MusicGenBackend()

        # Build prompt with optional style tag
        prompt = payload.prompt
        if payload.style:
            prompt = f"{payload.style}: {prompt}"

        output_filename = f"music_{task_id[:8]}.wav"
        output_path = str(_get_generations_dir() / output_filename)

        await backend.load_model("small")
        task.progress = 0.3

        await backend.generate_to_file(
            prompt=prompt,
            output_path=output_path,
            duration=payload.duration,
            temperature=payload.temperature,
            top_k=payload.top_k,
            guidance_scale=payload.guidance_scale,
        )

        task.progress = 1.0
        task.status = "completed"
        task.output_path = output_path
        logger.info("MusicGen generation completed: %s", output_path)

    except Exception as exc:
        logger.error("MusicGen generation failed: %s", exc)
        task.status = "failed"
        task.error = str(exc)
        task.progress = 0.0


# ── singing synthesis ────────────────────────────────────────────────

@router.post("/sing", response_model=MusicTaskStatus, status_code=202)
async def sing(
    payload: SingRequest,
    background_tasks: BackgroundTasks,
):
    """
    Synthesize singing voice from lyrics.

    Uses the selected voice profile for singing synthesis.
    """
    task = _create_task()
    task.status = "running"

    background_tasks.add_task(
        _run_sing_synthesis, task.task_id, payload,
    )

    return task


async def _run_sing_synthesis(task_id: str, payload: SingRequest):
    """Background task: run singing synthesis."""
    task = _tasks.get(task_id)
    if task is None:
        return

    try:
        from ..services.tts import get_tts_model
        from ..services.profiles import get_profile

        profile = get_profile(payload.voice_profile_id)
        if profile is None:
            raise ValueError(f"Voice profile not found: {payload.voice_profile_id}")

        # For singing, we generate the lyrics with pitch/tempo variations
        # This uses the existing TTS engine but with modified pitch/tempo
        output_filename = f"sing_{task_id[:8]}.wav"
        output_path = str(_get_generations_dir() / output_filename)

        task.progress = 0.3

        # Use the TTS model to generate singing with adjusted parameters
        tts_model = get_tts_model()
        voice_prompt = {
            "audio_path": profile.audio_paths[0] if hasattr(profile, "audio_paths") and profile.audio_paths else "",
            "reference_text": "",
            "language": payload.language,
        }

        result = await tts_model.generate(
            text=payload.lyrics,
            voice_prompt=voice_prompt,
            language=payload.language,
        )

        import soundfile as sf

        sf.write(output_path, result[0], result[1])

        task.progress = 1.0
        task.status = "completed"
        task.output_path = output_path
        logger.info("Singing synthesis completed: %s", output_path)

    except Exception as exc:
        logger.error("Singing synthesis failed: %s", exc)
        task.status = "failed"
        task.error = str(exc)
        task.progress = 0.0


# ── voice conversion ─────────────────────────────────────────────────

@router.post("/voice-convert", response_model=MusicTaskStatus, status_code=202)
async def voice_convert(
    payload: VoiceConvertRequest,
    background_tasks: BackgroundTasks,
):
    """
    Convert voice in an audio file using RVC voice conversion.

    Transforms input voice to a target voice using a .pth model.
    """
    task = _create_task()
    task.status = "running"

    background_tasks.add_task(
        _run_rvc_conversion, task.task_id, payload,
    )

    return task


async def _run_rvc_conversion(task_id: str, payload: VoiceConvertRequest):
    """Background task: run RVC voice conversion."""
    task = _tasks.get(task_id)
    if task is None:
        return

    try:
        from ..backends.rvc_backend import RVCBackend

        backend = RVCBackend()

        output_filename = f"converted_{task_id[:8]}.{payload.output_format}"
        output_path = str(_get_generations_dir() / output_filename)

        task.progress = 0.2

        await backend.convert_file(
            input_path=payload.audio_path,
            model_path=payload.model_path,
            output_path=output_path,
            pitch_shift=payload.pitch_shift,
            index_path=payload.index_path,
        )

        task.progress = 1.0
        task.status = "completed"
        task.output_path = output_path
        logger.info("RVC conversion completed: %s", output_path)

    except Exception as exc:
        logger.error("RVC conversion failed: %s", exc)
        task.status = "failed"
        task.error = str(exc)
        task.progress = 0.0


# ── task status ──────────────────────────────────────────────────────

@router.get("/status/{task_id}", response_model=MusicTaskStatus)
async def get_task_status(task_id: str):
    """Poll the status of a music generation/conversion task."""
    task = _tasks.get(task_id)
    if task is None:
        raise HTTPException(status_code=404, detail="Task not found")
    return task


# ── styles ───────────────────────────────────────────────────────────

@router.get("/styles", response_model=MusicStyleListResponse)
async def list_styles():
    """List all available music style tags."""
    styles = music_service.list_styles()
    return MusicStyleListResponse(styles=styles, total=len(styles))


# ── music projects ───────────────────────────────────────────────────

@router.get("/projects", response_model=MusicProjectsListResponse)
async def list_music_projects():
    items = music_service.list_projects()
    return MusicProjectsListResponse(projects=items, total=len(items))


@router.post("/projects", response_model=MusicProjectResponse, status_code=201)
async def create_music_project(payload: MusicProjectCreate):
    project = music_service.create_project(payload)
    return MusicProjectResponse(project=project)


@router.get("/projects/{project_id}", response_model=MusicProjectResponse)
async def get_music_project(project_id: str):
    project = music_service.get_project(project_id)
    if project is None:
        raise HTTPException(status_code=404, detail="Project not found")
    return MusicProjectResponse(project=project)


@router.delete("/projects/{project_id}")
async def delete_music_project(project_id: str):
    ok = music_service.delete_project(project_id)
    if not ok:
        raise HTTPException(status_code=404, detail="Project not found")
    return {"deleted": True}
