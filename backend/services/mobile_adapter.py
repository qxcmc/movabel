"""
Mobile adapter service — converts between desktop and mobile project formats.

Handles:
- Desktop project → mobile lightweight format
- Mobile format → desktop project restoration
- Audio downsampling (48kHz → 16kHz)
- Model quantization config generation
"""

from __future__ import annotations

import json
import logging
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from .. import config
from ..models.mobile import (
    ExportMobileRequest,
    ImportMobileRequest,
    MobileProject,
    MobileScene,
    MobileVoiceProfile,
    MobileSyncStatus,
)

logger = logging.getLogger(__name__)

# ── paths ────────────────────────────────────────────────────────────


def _data_dir() -> Path:
    return config.get_data_dir()


def _mobile_dir() -> Path:
    d = _data_dir() / "mobile"
    d.mkdir(parents=True, exist_ok=True)
    return d


def _mobile_projects_dir() -> Path:
    d = _data_dir() / "mobile" / "projects"
    d.mkdir(parents=True, exist_ok=True)
    return d


# ── project export ───────────────────────────────────────────────────


def export_project(request: ExportMobileRequest) -> MobileProject:
    """
    Export a desktop project to mobile-compatible lightweight format.

    Steps:
    1. Load desktop project JSON from projects directory
    2. Strip full-resolution audio, keep references
    3. Downsample configuration (48kHz → target sample rate)
    4. Package as MobileProject
    """
    project_path = _data_dir() / "projects" / request.project_type / f"{request.project_id}.json"
    if not project_path.exists():
        raise FileNotFoundError(f"Project not found: {project_path}")

    try:
        raw = json.loads(project_path.read_text(encoding="utf-8"))
    except Exception as exc:
        raise ValueError(f"Failed to read project: {exc}") from exc

    # Extract scenes
    scenes: list[MobileScene] = []
    for i, scene_data in enumerate(raw.get("scenes", raw.get("segments", []))):
        scene = MobileScene(
            id=scene_data.get("id", str(uuid.uuid4())),
            order=scene_data.get("order", i),
            text=scene_data.get("text", scene_data.get("content", "")),
            voice_profile_id=scene_data.get("voice_profile_id", scene_data.get("voice_id", "")),
            start_time_ms=scene_data.get("start_time_ms", scene_data.get("start_ms", 0)),
            duration_ms=scene_data.get("duration_ms", scene_data.get("duration", 0)),
            emotion=scene_data.get("emotion"),
            speed=scene_data.get("speed", scene_data.get("rate", 1.0)),
        )
        scenes.append(scene)

    # Extract voice profiles
    voice_profiles: list[MobileVoiceProfile] = []
    for vp_data in raw.get("voice_profiles", raw.get("voices", [])):
        profile = MobileVoiceProfile(
            profile_id=vp_data.get("id", vp_data.get("profile_id", "")),
            name=vp_data.get("name", ""),
            preview_url=vp_data.get("preview_url", ""),
            engine=vp_data.get("engine", ""),
            language=vp_data.get("language", "zh"),
        )
        voice_profiles.append(profile)

    mobile = MobileProject(
        id=raw.get("id", str(uuid.uuid4())),
        name=raw.get("name", "Exported Project"),
        project_type=request.project_type,
        original_project_id=request.project_id,
        scenes=scenes,
        voice_profiles=voice_profiles,
        sample_rate=request.sample_rate,
        bit_depth=16,
        channels=1,
        total_duration_ms=sum(s.duration_ms for s in scenes),
        tags=raw.get("tags", []),
    )

    # Persist exported mobile project
    out_path = _mobile_projects_dir() / f"{mobile.id}.json"
    out_path.write_text(
        json.dumps(mobile.model_dump(mode="json"), indent=2, default=str),
        encoding="utf-8",
    )
    logger.info("Exported mobile project: %s -> %s", request.project_id, mobile.id)
    return mobile


# ── project import ───────────────────────────────────────────────────


def import_project(request: ImportMobileRequest) -> dict:
    """
    Import a mobile project back into desktop format.

    Steps:
    1. Accept MobileProject payload
    2. Convert to desktop project JSON structure
    3. Optionally re-render with desktop quality settings
    4. Save to projects directory
    """
    mp = request.mobile_project

    desktop_scenes = []
    for scene in mp.scenes:
        desktop_scenes.append({
            "id": scene.id,
            "order": scene.order,
            "text": scene.text,
            "voice_profile_id": scene.voice_profile_id,
            "start_time_ms": scene.start_time_ms,
            "duration_ms": scene.duration_ms,
            "emotion": scene.emotion,
            "speed": scene.speed,
        })

    desktop_voices = []
    for vp in mp.voice_profiles:
        desktop_voices.append({
            "id": vp.profile_id,
            "name": vp.name,
            "preview_url": vp.preview_url,
            "engine": vp.engine,
            "language": vp.language,
        })

    project_data = {
        "id": mp.original_project_id or str(uuid.uuid4()),
        "name": mp.name,
        "type": destination_project_type(request.destination_project_type),
        "description": mp.description,
        "scenes": desktop_scenes,
        "voice_profiles": desktop_voices,
        "created_at": mp.created_at.isoformat(),
        "updated_at": datetime.now(timezone.utc).isoformat(),
        "imported_from_mobile": True,
        "mobile_project_id": mp.id,
        "requires_high_quality_rerender": request.restore_high_quality,
    }

    project_id = project_data["id"]
    out_path = _data_dir() / "projects" / project_data["type"] / f"{project_id}.json"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(project_data, indent=2), encoding="utf-8")

    logger.info("Imported mobile project: %s -> desktop %s", mp.id, project_id)
    return project_data


def destination_project_type(project_type: str) -> str:
    """Normalize project type string."""
    valid = {"documentary", "commercial", "storytelling", "audiobook", "podcast"}
    return project_type if project_type in valid else "documentary"


# ── audio conversion stubs ───────────────────────────────────────────


def get_downsample_config(sample_rate: int) -> dict:
    """
    Return FFmpeg-style configuration for audio downsampling.
    Desktop: 48000 Hz → Mobile: 16000 Hz (default).
    """
    return {
        "input_format": "wav",
        "output_format": "aac",
        "input_sample_rate": 48000,
        "output_sample_rate": sample_rate,
        "bit_depth": 16,
        "channels": 1,
        "bitrate": f"{64 if sample_rate <= 16000 else 128}k",
        "ffmpeg_args": [
            "-acodec", "aac",
            "-ar", str(sample_rate),
            "-ac", "1",
            "-b:a", f"{64 if sample_rate <= 16000 else 128}k",
        ],
    }


def get_quantization_config() -> dict:
    """
    Model quantization configuration for mobile inference.

    Returns settings for ONNX Runtime / TensorRT Lite quantization
    to reduce model size and memory footprint for mobile deployment.
    """
    return {
        "backend": "onnxruntime",
        "precision": "int8",
        "calibration_method": "minmax",
        "optimization_level": "all",
        "enable_memory_pattern": True,
        "enable_cpu_mem_arena": True,
        "graph_optimization_level": "ENABLE_ALL",
        "execution_mode": "parallel",
        "inter_op_num_threads": 4,
        "intra_op_num_threads": 4,
        "quantization": {
            "method": "dynamic",
            "weight_type": "QInt8",
            "reduce_range": True,
            "per_channel": False,
        },
    }


# ── sync status ──────────────────────────────────────────────────────


def get_sync_status(project_id: str) -> MobileSyncStatus | None:
    """
    Get sync status between desktop and mobile for a given project.
    Checks if a corresponding mobile export exists.
    """
    mobile_dir = _mobile_projects_dir()
    mobile_project_id: Optional[str] = None
    mobile_version = 0

    for f in mobile_dir.glob("*.json"):
        try:
            data = json.loads(f.read_text(encoding="utf-8"))
            if data.get("original_project_id") == project_id:
                mobile_project_id = data.get("id")
                mobile_version = data.get("version", 1)
                break
        except Exception:
            continue

    if mobile_project_id is None:
        return None

    return MobileSyncStatus(
        project_id=project_id,
        mobile_project_id=mobile_project_id,
        last_synced_at=datetime.now(timezone.utc),
        desktop_version=1,
        mobile_version=mobile_version,
        has_conflicts=False,
        pending_items=0,
        status="idle",
    )
