"""
Pydantic models for the Commercial (ad/promo) workspace.

Supports emotion presets, speed curve, and multi-language mixing.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Literal

from pydantic import BaseModel, Field


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


class EmotionPreset(BaseModel):
    id: str
    name: str
    description: str = ""
    category: Literal["激昂", "温情", "紧迫", "轻松", "大气"] = "大气"
    pitch_shift: float = Field(0.0, ge=-12.0, le=12.0)
    speed_multiplier: float = Field(1.0, ge=0.3, le=3.0)
    energy: float = Field(0.5, ge=0.0, le=1.0)
    pause_pattern: str = "normal"
    effects: list[dict[str, Any]] = Field(default_factory=list)


class SpeedPoint(BaseModel):
    position: float = Field(..., ge=0.0, le=1.0)
    multiplier: float = Field(1.0, ge=0.3, le=3.0)


class CommercialSegment(BaseModel):
    id: str
    text: str = ""
    language: str = "en"
    voice_profile_id: str | None = None
    voice_name: str = ""
    emotion_preset_id: str | None = None
    speed_points: list[SpeedPoint] = Field(default_factory=list)
    generation_id: str | None = None
    status: Literal["draft", "generating", "done", "failed"] = "draft"
    sort_index: int = 0


class CommercialSegmentCreate(BaseModel):
    text: str = ""
    language: str = "en"
    voice_profile_id: str | None = None
    voice_name: str = ""
    emotion_preset_id: str | None = None
    sort_index: int = 0


class CommercialSegmentUpdate(BaseModel):
    text: str | None = None
    language: str | None = None
    voice_profile_id: str | None = None
    voice_name: str | None = None
    emotion_preset_id: str | None = None
    speed_points: list[SpeedPoint] | None = None
    sort_index: int | None = None


class CommercialProject(BaseModel):
    id: str
    name: str = "Untitled Commercial"
    description: str = ""
    target_duration_sec: float | None = None
    background_audio_path: str | None = None
    background_volume: float = Field(0.3, ge=0.0, le=1.0)
    segments: list[CommercialSegment] = Field(default_factory=list)
    created_at: str = Field(default_factory=_now)
    updated_at: str = Field(default_factory=_now)


class CommercialProjectCreate(BaseModel):
    name: str = "Untitled Commercial"
    description: str = ""
    target_duration_sec: float | None = None


class CommercialProjectUpdate(BaseModel):
    name: str | None = None
    description: str | None = None
    target_duration_sec: float | None = None
    background_audio_path: str | None = None
    background_volume: float | None = None


class CommercialProjectResponse(BaseModel):
    project: CommercialProject


class CommercialProjectsListResponse(BaseModel):
    projects: list[dict[str, Any]]
    total: int
