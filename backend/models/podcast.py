"""
Pydantic models for the Podcast workspace.

Supports speaker turns, template system, Intro/Outro, and post-processing.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field


def _now() -> str:
    return datetime.utcnow().isoformat() + "Z"


# ── speaker turn ─────────────────────────────────────────────────────

class SpeakerTurn(BaseModel):
    """A single turn in a multi-speaker conversation."""

    id: str = Field(..., description="Turn UUID")
    speaker_id: str = Field("", description="Speaker identifier (can map to a profile)")
    speaker_name: str = Field("Speaker", description="Display name")
    text: str = Field("", description="What this speaker says")
    emotion: str = Field("neutral")
    language: str = Field("en")

    # Timing
    pause_before: float = Field(0.5, ge=0.0, description="Seconds of silence before this turn")
    pause_after: float = Field(0.3, ge=0.0, description="Seconds of silence after this turn")

    profile_id: str | None = Field(None, description="Voice profile ID for this speaker")
    engine: str | None = Field(None)

    generation_id: str | None = Field(None)
    status: Literal["draft", "generating", "done", "failed"] = Field("draft")

    sort_index: int = Field(0)


class SpeakerTurnCreate(BaseModel):
    speaker_id: str = ""
    speaker_name: str = "Speaker"
    text: str = ""
    emotion: str = "neutral"
    language: str = "en"
    pause_before: float = 0.5
    pause_after: float = 0.3
    profile_id: str | None = None
    engine: str | None = None
    sort_index: int = 0


class SpeakerTurnUpdate(BaseModel):
    speaker_id: str | None = None
    speaker_name: str | None = None
    text: str | None = None
    emotion: str | None = None
    language: str | None = None
    pause_before: float | None = None
    pause_after: float | None = None
    profile_id: str | None = None
    engine: str | None = None
    sort_index: int | None = None


# ── podcast template ─────────────────────────────────────────────────

class PodcastTemplate(BaseModel):
    """A reusable podcast structure template."""

    id: str = Field(..., description="Template UUID")
    name: str
    description: str = ""
    category: Literal["interview", "news", "story", "education", "business"] = Field(
        "interview"
    )

    # Predefined sections
    intro_text: str = Field("")
    intro_duration_sec: float = Field(15.0)
    outro_text: str = Field("")
    outro_duration_sec: float = Field(10.0)

    # Speaker archetypes
    speaker_archetypes: list[dict[str, str]] = Field(
        default_factory=list,
        description="List of {role: 'host', name: 'Host'} archetypes",
    )

    # Typical structure hints
    segment_hints: list[dict[str, Any]] = Field(
        default_factory=list,
        description="Suggested segments e.g. {name: 'Guest Intro', type: 'dialogue'}",
    )


# ── post-processing config ───────────────────────────────────────────

class PostProcessingConfig(BaseModel):
    """Audio post-processing settings."""

    enabled: bool = Field(True)

    # Loudness normalization (LUFS)
    target_lufs: float = Field(-16.0, ge=-30.0, le=0.0, description="Target LUFS loudness")
    enable_lufs: bool = Field(True)

    # Noise reduction
    enable_noise_reduction: bool = Field(False)
    noise_reduction_db: float = Field(12.0, ge=0.0, le=48.0)

    # Dynamics
    enable_compressor: bool = Field(True)
    compressor_threshold_db: float = Field(-20.0)
    compressor_ratio: float = Field(2.0, ge=1.0, le=20.0)

    # Fade in/out
    fade_in_sec: float = Field(0.5, ge=0.0, le=5.0)
    fade_out_sec: float = Field(1.5, ge=0.0, le=10.0)

    # De-esser
    enable_deesser: bool = Field(False)

    # Sample rate
    output_sample_rate: int = Field(44100, ge=8000, le=96000)
    output_format: Literal["wav", "mp3", "flac"] = Field("wav")
    mp3_bitrate_kbps: int = Field(192, ge=64, le=320)


# ── podcast project ─────────────────────────────────────────────────

class PodcastProject(BaseModel):
    id: str = Field(..., description="Project UUID")
    name: str = Field("Untitled Podcast")
    description: str = ""

    # Template
    template_id: str | None = Field(None)
    template: PodcastTemplate | None = Field(None)

    # Intro / Outro
    intro_text: str = Field("")
    intro_generation_id: str | None = Field(None)
    outro_text: str = Field("")
    outro_generation_id: str | None = Field(None)

    # Speaker turns
    speaker_turns: list[SpeakerTurn] = Field(default_factory=list)

    # Post processing
    post_processing: PostProcessingConfig = Field(default_factory=PostProcessingConfig)

    # Final output
    mixdown_generation_id: str | None = Field(None)
    estimated_duration_sec: float | None = Field(None)

    created_at: str = Field(default_factory=_now)
    updated_at: str = Field(default_factory=_now)


class PodcastProjectCreate(BaseModel):
    name: str = "Untitled Podcast"
    description: str = ""
    template_id: str | None = None


class PodcastProjectUpdate(BaseModel):
    name: str | None = None
    description: str | None = None
    intro_text: str | None = None
    outro_text: str | None = None


# ── response wrappers ────────────────────────────────────────────────

class PodcastProjectResponse(BaseModel):
    project: PodcastProject


class PodcastProjectsListResponse(BaseModel):
    projects: list[dict[str, Any]]
    total: int


class PostProcessingResult(BaseModel):
    output_path: str | None = None
    duration_sec: float | None = None
    input_lufs: float | None = None
    output_lufs: float | None = None
    errors: list[str] = Field(default_factory=list)
