"""
Pydantic models for digital avatar (Live2D) features.

Covers avatar model management, lip-sync analysis, expressions,
and animation triggering.
"""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


# ── model management ─────────────────────────────────────────────────


class Live2DModelInfo(BaseModel):
    """Metadata for an installed Live2D model."""
    id: str = Field(..., description="Unique model identifier (directory name)")
    name: str = Field(..., description="Display name from model3.json")
    version: str = Field("1.0", description="Model version string")
    author: str = Field("", description="Model author")
    description: str = Field("", description="Model description from model3.json")
    preview_image: Optional[str] = Field(None, description="Path to preview/icon image relative to model dir")
    installed_at: datetime = Field(default_factory=datetime.utcnow)
    file_count: int = Field(0, description="Number of files in the model directory")
    has_physics: bool = Field(False, description="Whether the model includes physics definition")
    has_poses: bool = Field(False, description="Whether the model includes pose definitions")
    expressions: list[str] = Field(default_factory=list, description="Available expression names")


class Live2DModelListResponse(BaseModel):
    models: list[Live2DModelInfo]
    total: int


class Live2DImportRequest(BaseModel):
    """Request to import a Live2D model from a local path or URL."""
    source: str = Field(..., description="Local ZIP path, directory path, or download URL")
    model_name: Optional[str] = Field(None, max_length=100, description="Custom name override")


# ── lip sync ─────────────────────────────────────────────────────────


class LipSyncRequest(BaseModel):
    """Request for real-time lip-sync analysis of an audio chunk."""
    audio_path: str = Field(..., description="Path to the audio file to analyze")
    sample_rate: int = Field(22050, ge=8000, le=48000, description="Expected sample rate for analysis")
    frame_rate: int = Field(30, ge=10, le=60, description="Target frames per second for output")
    sensitivity: float = Field(1.0, ge=0.1, le=5.0, description="Sensitivity multiplier for mouth openness")
    include_visemes: bool = Field(False, description="Include viseme/phoneme labels")


class LipSyncFrame(BaseModel):
    """A single frame of lip-sync data."""
    timestamp_ms: int = Field(..., description="Timestamp in milliseconds from audio start")
    mouth_open: float = Field(..., ge=0.0, le=1.0, description="Mouth openness 0-1")
    mouth_width: float = Field(0.5, ge=0.0, le=1.0, description="Mouth width 0-1")
    volume: float = Field(..., ge=0.0, description="RMS volume at this frame")
    viseme: Optional[str] = Field(None, description="Viseme label if include_visemes is true")


class LipSyncResponse(BaseModel):
    frames: list[LipSyncFrame]
    duration_ms: int = Field(..., description="Total audio duration in ms")
    frame_count: int
    sample_rate: int
    frame_rate: int


# ── expressions & animations ─────────────────────────────────────────


class AvatarExpression(BaseModel):
    """A named expression preset available on a model."""
    id: str = Field(..., description="Expression identifier")
    name: str = Field(..., description="Display name")
    parameters: dict[str, float] = Field(
        default_factory=dict,
        description="Parameter name to value mapping (0.0-1.0)",
    )


class AvatarExpressionListResponse(BaseModel):
    expressions: list[AvatarExpression]
    total: int


class AnimationRequest(BaseModel):
    """Request to trigger an animation/motion on an avatar model."""
    model_id: Optional[str] = Field(None, description="Target model ID")
    animation_type: str = Field(..., description="Animation type: idle / expression / custom")
    expression_id: Optional[str] = Field(None, description="Expression ID for expression-type animation")
    intensity: float = Field(1.0, ge=0.0, le=1.0, description="Animation intensity")
    duration_ms: Optional[int] = Field(None, ge=100, le=30000, description="Optional override duration in ms")
    custom_parameters: Optional[dict[str, float]] = Field(None, description="Custom parameter overrides")


class AnimationResponse(BaseModel):
    """Response for animation execution."""
    model_id: Optional[str] = None
    animation_type: str
    parameters: dict[str, float] = Field(default_factory=dict)


# ── convenience aliases for route layer ─────────────────────────────

AvatarModelInfo = Live2DModelInfo
AvatarModelsListResponse = Live2DModelListResponse
ExpressionListResponse = AvatarExpressionListResponse
