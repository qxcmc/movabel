"""
Digital avatar API routes.

Endpoints for Live2D model management, lip-sync analysis,
expression handling, and animation control.
"""

from __future__ import annotations

import logging
import shutil
import tempfile
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, BackgroundTasks, File, HTTPException, UploadFile

from .. import config
from ..backends.live2d_backend import Live2DBackend
from ..models.avatar import (
    AnimationRequest,
    AnimationResponse,
    AvatarModelInfo,
    AvatarModelsListResponse,
    ExpressionListResponse,
    LipSyncRequest,
    LipSyncResponse,
)
from ..services import avatar_downloader as downloader

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/avatar", tags=["avatar"])

# ── backend singleton ────────────────────────────────────────────────

_live2d = Live2DBackend()


def _get_backend() -> Live2DBackend:
    return _live2d


# ── model list / info ───────────────────────────────────────────────

@router.get("/models", response_model=AvatarModelsListResponse)
async def list_models():
    """
    List all installed Live2D models.
    """
    models = _get_backend().list_installed_models()
    return AvatarModelsListResponse(
        models=[AvatarModelInfo(**m) for m in models],
        total=len(models),
    )


@router.get("/models/{model_id}", response_model=AvatarModelInfo)
async def get_model(model_id: str):
    """
    Get detailed information about a specific model.
    """
    info = _get_backend().get_model_info(model_id)
    if info is None:
        raise HTTPException(status_code=404, detail="Model not found")
    return AvatarModelInfo(**info)


# ── model import ─────────────────────────────────────────────────────

@router.post("/models/import", response_model=AvatarModelInfo, status_code=201)
async def import_model(
    background_tasks: BackgroundTasks,
    source: str = "official",
    model_name: str = "haru",
):
    """
    Import a Live2D model.

    Sources:
    - 'official': Download from Live2D official free model repository
    - 'file': User uploads a ZIP (use /models/import/upload endpoint)
    """
    valid_names = downloader.AVAILABLE_MODELS

    if source == "official":
        if model_name not in valid_names:
            raise HTTPException(
                status_code=400,
                detail=f"Unknown model '{model_name}'. Available: {', '.join(valid_names)}",
            )

        # Check if already installed
        installed = _get_backend().list_installed_models()
        for m in installed:
            if m.get("id") == model_name:
                return AvatarModelInfo(**m)

        # Download and install in background
        background_tasks.add_task(
            downloader.download_and_install_model, model_name, str(_get_backend().get_models_dir()),
        )

        return AvatarModelInfo(
            id=model_name,
            name=model_name.title(),
            version="downloading",
            author="Live2D",
            description="Downloading...",
            installed_at=datetime.now(timezone.utc),
            file_count=0,
            has_physics=False,
            has_poses=False,
            expressions=[],
        )

    elif source == "file":
        raise HTTPException(
            status_code=400,
            detail="For file uploads, use POST /avatar/models/import/upload",
        )
    else:
        raise HTTPException(
            status_code=400,
            detail=f"Unknown source '{source}'. Use 'official' or 'file'.",
        )


@router.post("/models/import/upload", response_model=AvatarModelInfo, status_code=201)
async def import_model_upload(
    file: UploadFile = File(...),
    model_name: Optional[str] = None,
):
    """
    Upload and import a Live2D model ZIP file.
    """
    if not file.filename or not file.filename.lower().endswith(".zip"):
        raise HTTPException(status_code=400, detail="Only .zip files are accepted")

    name = model_name or Path(file.filename).stem

    # Save uploaded file to temp
    tmp_dir = config.get_data_dir() / "temp" / "live2d_uploads"
    tmp_dir.mkdir(parents=True, exist_ok=True)

    tmp_path = tmp_dir / f"{uuid.uuid4().hex}_{file.filename}"
    with open(tmp_path, "wb") as f:
        content = await file.read()
        f.write(content)

    # Extract to models directory
    model_dir = _get_backend().get_models_dir() / name
    if model_dir.exists():
        shutil.rmtree(model_dir)

    import zipfile

    with zipfile.ZipFile(tmp_path, "r") as zf:
        zf.extractall(model_dir)

    # Clean up temp
    tmp_path.unlink(missing_ok=True)

    # Refresh model info
    info = _get_backend().get_model_info(name)
    if info is None:
        raise HTTPException(status_code=500, detail="Failed to import model")

    return AvatarModelInfo(**info)


# ── model delete ─────────────────────────────────────────────────────

@router.delete("/models/{model_id}")
async def delete_model(model_id: str):
    """
    Delete an installed Live2D model.
    """
    ok = _get_backend().delete_model(model_id)
    if not ok:
        raise HTTPException(status_code=404, detail="Model not found")
    return {"deleted": True}


# ── lip-sync ─────────────────────────────────────────────────────────

@router.post("/lip-sync", response_model=LipSyncResponse)
async def lip_sync(payload: LipSyncRequest):
    """
    Analyze an audio file and generate lip-sync frame data.

    Returns mouth_open, mouth_width, volume, and optional viseme labels
    for each animation frame.
    """
    backend = _get_backend()

    result = await backend.analyze_audio(
        audio_path=payload.audio_path,
        sample_rate=payload.sample_rate,
        frame_rate=payload.frame_rate,
        sensitivity=payload.sensitivity,
        include_visemes=payload.include_visemes,
    )

    from ..models.avatar import LipSyncFrame

    frames = [LipSyncFrame(**f) for f in result["frames"]]

    return LipSyncResponse(
        frames=frames,
        duration_ms=result["duration_ms"],
        frame_count=result["frame_count"],
        sample_rate=result["sample_rate"],
        frame_rate=result["frame_rate"],
    )


# ── expressions ──────────────────────────────────────────────────────

@router.get("/expressions", response_model=ExpressionListResponse)
async def list_expressions(model_id: Optional[str] = None):
    """
    List available expressions.

    If model_id is provided, returns model-specific expressions.
    Otherwise returns the default expression presets.
    """
    if model_id:
        expressions = _get_backend().get_model_expressions(model_id)
    else:
        expressions = _get_backend().get_default_expressions()

    return ExpressionListResponse(
        expressions=expressions,
        total=len(expressions),
    )


# ── animation ────────────────────────────────────────────────────────

@router.post("/animation", response_model=AnimationResponse)
async def play_animation(payload: AnimationRequest):
    """
    Request a specific animation/expression for a Live2D model.

    Returns the parameter values for the requested animation.
    """
    backend = _get_backend()

    if payload.animation_type == "expression":
        model_exprs = backend.get_model_expressions(payload.model_id) if payload.model_id else []
        expr_lookup = {e["id"]: e for e in model_exprs}

        if payload.expression_id in expr_lookup:
            expr = expr_lookup[payload.expression_id]
            params = expr["parameters"]
        else:
            # Try default presets
            defaults = backend.get_default_expressions()
            default_lookup = {e["id"]: e for e in defaults}
            if payload.expression_id in default_lookup:
                params = default_lookup[payload.expression_id]["parameters"]
            else:
                raise HTTPException(
                    status_code=404,
                    detail=f"Expression '{payload.expression_id}' not found",
                )
    elif payload.animation_type == "idle":
        params = {
            "ParamMouthOpenY": 0.03,
            "ParamMouthForm": 0.5,
            "ParamEyeLOpen": 1.0,
            "ParamEyeROpen": 1.0,
            "ParamBrowLY": 0.5,
            "ParamBrowRY": 0.5,
            "ParamBreath": 0.5,
        }
    elif payload.animation_type == "custom":
        params = payload.custom_parameters or {}
    else:
        raise HTTPException(status_code=400, detail=f"Unknown animation type: {payload.animation_type}")

    return AnimationResponse(
        model_id=payload.model_id,
        animation_type=payload.animation_type,
        parameters=params,
    )


# ── model download status ────────────────────────────────────────────

@router.get("/models/{model_id}/status")
async def get_model_status(model_id: str):
    """
    Check download/installation status for a model.
    """
    info = _get_backend().get_model_info(model_id)
    if info is not None:
        return {"status": "installed", "model": AvatarModelInfo(**info)}

    # Check if download is in progress
    # (Simplified: return unknown if not installed)
    return {"status": "not_installed", "message": "Model is not installed"}
