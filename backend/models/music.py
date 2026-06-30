"""
Pydantic models for AI music generation features.

Covers MusicGen text-to-music, RVC voice conversion, singing synthesis,
and music project persistence.
"""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


# ── music styles ─────────────────────────────────────────────────────


class MusicStyle(BaseModel):
    """A predefined music style / genre tag."""
    id: str = Field(..., description="Style identifier slug")
    name: str = Field(..., description="Human-readable style name")
    description: str = Field("", description="Short description of the style")
    category: str = Field("general", description="Broad category grouping")
    tags: list[str] = Field(default_factory=list, description="Search tags")


class MusicStyleListResponse(BaseModel):
    styles: list[MusicStyle]
    total: int


# ── generation requests ──────────────────────────────────────────────


class MusicGenerateRequest(BaseModel):
    """Request to generate background music from a text prompt."""
    prompt: str = Field(..., min_length=1, max_length=500, description="Text description of the desired music")
    duration: float = Field(30.0, ge=1.0, le=300.0, description="Target duration in seconds")
    temperature: float = Field(1.0, ge=0.1, le=3.0, description="Sampling temperature")
    top_k: int = Field(250, ge=1, le=1000, description="Top-k sampling")
    guidance_scale: float = Field(3.0, ge=1.0, le=20.0, description="Classifier-free guidance scale")
    style: Optional[str] = Field(None, description="Optional style tag to prepend to prompt")


class SingRequest(BaseModel):
    """Request to synthesize singing voice from lyrics + melody."""
    lyrics: str = Field(..., min_length=1, max_length=2000, description="Lyrics text for singing")
    melody_description: Optional[str] = Field(None, max_length=500, description="Text description of melody style")
    voice_profile_id: str = Field(..., description="Voice profile to use for singing")
    language: str = Field("zh", description="Language of the lyrics")
    pitch_shift: int = Field(0, ge=-12, le=12, description="Semitone pitch shift")
    tempo: float = Field(1.0, ge=0.5, le=2.0, description="Speed multiplier")


class VoiceConvertRequest(BaseModel):
    """Request to convert voice in an audio file using RVC."""
    audio_path: str = Field(..., description="Path to the input audio file (WAV recommended)")
    model_path: str = Field(..., description="Path to the RVC .pth model file")
    pitch_shift: int = Field(0, ge=-24, le=24, description="Semitone pitch shift")
    index_path: Optional[str] = Field(None, description="Optional .index file path for feature retrieval")
    output_format: str = Field("wav", description="Output audio format")


# ── task status ──────────────────────────────────────────────────────


class MusicTaskStatus(BaseModel):
    task_id: str
    status: str = Field(..., description="queued / running / completed / failed")
    progress: float = Field(0.0, ge=0.0, le=1.0)
    output_path: Optional[str] = None
    error: Optional[str] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)


# ── music project persistence ────────────────────────────────────────


class MusicProjectCreate(BaseModel):
    """Payload for creating a music project."""
    name: str = Field(..., min_length=1, max_length=200)
    description: str = Field("", max_length=2000)
    prompt: str = Field("", max_length=500)
    style: Optional[str] = None
    duration: float = Field(30.0, ge=1.0, le=300.0)


class MusicProjectUpdate(BaseModel):
    """Payload for updating an existing music project."""
    name: Optional[str] = Field(None, min_length=1, max_length=200)
    description: Optional[str] = Field(None, max_length=2000)
    prompt: Optional[str] = Field(None, max_length=500)
    style: Optional[str] = None
    duration: Optional[float] = Field(None, ge=1.0, le=300.0)


class MusicProject(BaseModel):
    """A persisted music generation project."""
    id: str
    name: str
    description: str = ""
    prompt: str = ""
    style: Optional[str] = None
    duration: float = 30.0
    output_paths: list[str] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)


class MusicProjectResponse(BaseModel):
    project: MusicProject


class MusicProjectsListResponse(BaseModel):
    projects: list[MusicProject]
    total: int
