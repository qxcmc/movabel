"""
Pydantic models for the Documentary workspace.

Supports video reference track import, scene segmentation, SMPTE timecode,
and per-scene voice binding.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Literal

from pydantic import BaseModel, Field


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


class Timecode(BaseModel):
    """SMPTE timecode: HH:MM:SS:FF."""

    hours: int = Field(0, ge=0, le=23)
    minutes: int = Field(0, ge=0, le=59)
    seconds: int = Field(0, ge=0, le=59)
    frames: int = Field(0, ge=0, le=99)
    fps: float = Field(29.97, ge=1.0, le=120.0)

    @property
    def total_seconds(self) -> float:
        total_frames = (
            self.hours * 3600 + self.minutes * 60 + self.seconds
        ) * self.fps + self.frames
        return total_frames / self.fps

    @classmethod
    def from_seconds(cls, seconds: float, fps: float = 29.97) -> "Timecode":
        total_frames = int(round(seconds * fps))
        h = total_frames // int(3600 * fps)
        m = (total_frames // int(60 * fps)) % 60
        s = (total_frames // int(fps)) % 60
        f = total_frames % int(fps)
        return cls(hours=h, minutes=m, seconds=s, frames=f, fps=fps)

    @classmethod
    def parse(cls, tc_str: str, fps: float = 29.97) -> "Timecode":
        tc_str = tc_str.strip().replace(",", ":")
        parts = tc_str.split(":")
        if len(parts) != 4:
            raise ValueError(f"Invalid timecode format: {tc_str}")
        return cls(
            hours=int(parts[0]),
            minutes=int(parts[1]),
            seconds=int(parts[2]),
            frames=int(parts[3]),
            fps=fps,
        )

    def to_string(self) -> str:
        return f"{self.hours:02d}:{self.minutes:02d}:{self.seconds:02d}:{self.frames:02d}"


class SceneVoiceBinding(BaseModel):
    profile_id: str | None = None
    profile_name: str = ""
    engine: str | None = None
    language: str = "en"
    emotion: str = "neutral"
    effects_chain: list[dict[str, Any]] = Field(default_factory=list)
    generation_id: str | None = None
    status: Literal["draft", "generating", "done", "failed"] = "draft"


class DocumentaryScene(BaseModel):
    id: str
    name: str = "Untitled Scene"
    start_tc: Timecode = Field(default_factory=Timecode)
    end_tc: Timecode = Field(default_factory=Timecode)
    duration_sec: float = 0.0
    text: str = ""
    voice_bindings: list[SceneVoiceBinding] = Field(default_factory=list)
    reference_audio_path: str | None = None
    sort_index: int = 0
    created_at: str = Field(default_factory=_now)


class DocumentarySceneCreate(BaseModel):
    name: str = "Untitled Scene"
    start_tc_str: str = "00:00:00:00"
    end_tc_str: str = "00:00:05:00"
    fps: float = 29.97
    text: str = ""


class DocumentarySceneUpdate(BaseModel):
    name: str | None = None
    start_tc_str: str | None = None
    end_tc_str: str | None = None
    text: str | None = None
    reference_audio_path: str | None = None
    sort_index: int | None = None


class VoiceBindingCreate(BaseModel):
    profile_id: str | None = None
    profile_name: str = ""
    engine: str | None = None
    language: str = "en"
    emotion: str = "neutral"


class DocumentaryProject(BaseModel):
    id: str
    name: str = "Untitled Documentary"
    description: str = ""
    video_path: str | None = None
    video_fps: float = Field(29.97, ge=1.0, le=120.0)
    background_audio_path: str | None = None
    background_volume: float = Field(0.3, ge=0.0, le=1.0)
    scenes: list[DocumentaryScene] = Field(default_factory=list)
    created_at: str = Field(default_factory=_now)
    updated_at: str = Field(default_factory=_now)


class DocumentaryProjectCreate(BaseModel):
    name: str = "Untitled Documentary"
    description: str = ""
    video_path: str | None = None
    video_fps: float = 29.97


class DocumentaryProjectUpdate(BaseModel):
    name: str | None = None
    description: str | None = None
    video_path: str | None = None
    video_fps: float | None = None
    background_audio_path: str | None = None
    background_volume: float | None = None


class SMPTEParseRequest(BaseModel):
    timecode: str
    fps: float = 29.97


class SMPTEParseResponse(BaseModel):
    hours: int
    minutes: int
    seconds: int
    frames: int
    fps: float
    total_seconds: float


class DocumentaryProjectResponse(BaseModel):
    project: DocumentaryProject


class DocumentaryProjectsListResponse(BaseModel):
    projects: list[dict[str, Any]]
    total: int
