"""
Pydantic models for mobile adaptation layer.

Handles lightweight project formats, import/export, sync status,
and QR code sharing for mobile access.
"""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


# ── mobile project ───────────────────────────────────────────────────


class MobileVoiceProfile(BaseModel):
    """Lightweight voice profile reference for mobile."""
    profile_id: str
    name: str
    preview_url: str = ""
    engine: str = ""
    language: str = "zh"


class MobileScene(BaseModel):
    """Lightweight scene/segment for mobile project."""
    id: str = Field(...)
    order: int = Field(0)
    text: str = Field("")
    voice_profile_id: str = Field("")
    start_time_ms: int = Field(0)
    duration_ms: int = Field(0)
    emotion: Optional[str] = None
    speed: float = Field(1.0)


class MobileProject(BaseModel):
    """Lightweight project format optimized for mobile."""
    id: str = Field(...)
    name: str = Field(..., min_length=1, max_length=200)
    project_type: str = Field("documentary")
    original_project_id: str = Field("")
    description: str = Field("", max_length=2000)
    scenes: list[MobileScene] = Field(default_factory=list)
    voice_profiles: list[MobileVoiceProfile] = Field(default_factory=list)
    sample_rate: int = Field(16000, description="Mobile-optimized sample rate")
    bit_depth: int = Field(16)
    channels: int = Field(1)
    total_duration_ms: int = Field(0)
    file_size_bytes: int = Field(0)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    tags: list[str] = Field(default_factory=list)


# ── export/import ────────────────────────────────────────────────────


class ExportMobileRequest(BaseModel):
    """Request to export a desktop project for mobile."""
    project_id: str = Field(...)
    project_type: str = Field("documentary")
    include_audio: bool = Field(True, description="Bundle rendered audio files")
    include_previews: bool = Field(True, description="Include voice preview clips")
    sample_rate: int = Field(16000, ge=8000, le=48000)
    compression: str = Field("aac", description="aac / mp3 / opus")
    bitrate_kbps: int = Field(64, ge=16, le=320)


class ImportMobileRequest(BaseModel):
    """Request to import a mobile project into the desktop app."""
    mobile_project: MobileProject = Field(...)
    destination_project_type: str = Field("documentary")
    restore_high_quality: bool = Field(False, description="Re-render with desktop-quality settings")


# ── sync status ──────────────────────────────────────────────────────


class MobileSyncStatus(BaseModel):
    """Sync status between desktop and mobile versions of a project."""
    project_id: str
    mobile_project_id: str
    last_synced_at: Optional[datetime] = None
    desktop_version: int = Field(1, description="Monotonic version number")
    mobile_version: int = Field(0)
    has_conflicts: bool = Field(False)
    pending_items: int = Field(0, description="Changes waiting to sync")
    status: str = Field("idle", description="idle / syncing / conflict / error")
    error_message: str = Field("")


# ── QR code ──────────────────────────────────────────────────────────


class QRCodeResponse(BaseModel):
    """Response containing QR code data for mobile access."""
    project_id: str
    session_code: str = Field("", description="6-digit access code")
    qr_data_url: str = Field("", description="Base64 data URL of QR PNG")
    expire_at: datetime = Field(..., description="QR code expiration time")
    access_url: str = Field("", description="Full URL for mobile access")


# ── mobile conversion config ─────────────────────────────────────────


class MobileConversionConfig(BaseModel):
    """Configuration for desktop→mobile project conversion."""
    sample_rate: int = Field(16000, ge=8000, le=48000)
    bit_depth: int = Field(16, ge=8, le=32)
    channels: int = Field(1, ge=1, le=2)
    audio_codec: str = Field("aac")
    bitrate_kbps: int = Field(64, ge=16, le=320)
    include_text: bool = Field(True)
    include_reference_audio: bool = Field(False)
    max_scene_count: int = Field(500, ge=1, le=5000)
    strip_metadata: bool = Field(True)


# ── response wrappers ────────────────────────────────────────────────


class MobileProjectResponse(BaseModel):
    project: MobileProject


class MobileSyncStatusResponse(BaseModel):
    status: MobileSyncStatus


class MobileProjectsListResponse(BaseModel):
    projects: list[MobileProject]
    total: int
