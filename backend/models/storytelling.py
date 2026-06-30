"""
Pydantic models for the Storytelling workspace.

A StoryProject contains characters, paragraphs (with dialogue detection),
and SFX cues.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field


def _now() -> str:
    return datetime.utcnow().isoformat() + "Z"


# ── emotion tags ─────────────────────────────────────────────────────

VALID_EMOTIONS = ("happy", "sad", "angry", "scared", "whisper", "excited", "neutral")


# ── story character ──────────────────────────────────────────────────

class StoryCharacter(BaseModel):
    """A character in the story, bound to a voice profile."""

    id: str = Field(..., description="Character UUID")
    name: str = Field(..., description="Character display name")
    description: str = Field("", description="Optional character description")
    profile_id: str | None = Field(None, description="Voice profile ID for this character")
    engine: str | None = Field(None, description="Engine override")
    language: str = Field("en")

    # Emotional state for consistency
    default_emotion: str = Field("neutral", description="Default emotion tag")

    created_at: str = Field(default_factory=_now)


class StoryCharacterCreate(BaseModel):
    name: str
    description: str = ""
    profile_id: str | None = None
    engine: str | None = None
    language: str = "en"
    default_emotion: str = "neutral"


class StoryCharacterUpdate(BaseModel):
    name: str | None = None
    description: str | None = None
    profile_id: str | None = None
    engine: str | None = None
    language: str | None = None
    default_emotion: str | None = None


# ── SFX cue ──────────────────────────────────────────────────────────

class SFXCue(BaseModel):
    """A sound effect cue placed at a specific position in the story."""

    id: str = Field(..., description="Cue UUID")
    name: str = Field(..., description="Display name, e.g. 'door_creak'")
    category: str = Field("", description="SFX category")
    file_path: str = Field(..., description="Absolute path to the SFX audio file")

    # Timing (in seconds from story start)
    start_time: float = Field(0.0)
    duration: float | None = Field(None, description="Audio duration in seconds")
    fade_in: float = Field(0.0, description="Fade-in duration (seconds)")
    fade_out: float = Field(0.0, description="Fade-out duration (seconds)")
    volume: float = Field(1.0, ge=0.0, le=2.0, description="Volume multiplier")


class SFXCueCreate(BaseModel):
    name: str
    category: str = ""
    file_path: str
    start_time: float = 0.0
    fade_in: float = 0.0
    fade_out: float = 0.0
    volume: float = 1.0


# ── story paragraph ──────────────────────────────────────────────────

class StoryParagraph(BaseModel):
    """A paragraph in the story, with dialogue detection and character assignment."""

    id: str = Field(..., description="Paragraph UUID")
    text: str = Field("", description="Full paragraph text")

    # Character assignment
    character_id: str | None = Field(
        None,
        description="Assigned character (manual or auto-detected)",
    )
    is_dialogue: bool = Field(
        False,
        description="Whether this paragraph contains detected dialogue",
    )
    speaker_name: str | None = Field(
        None,
        description="Detected speaker name from quoted dialogue",
    )

    # Emotion override
    emotion: str = Field("neutral", description="Emotion tag for this paragraph")

    sort_index: int = Field(0)
    status: Literal["draft", "generating", "done", "failed"] = Field("draft")
    generation_id: str | None = Field(None)
    error: str | None = Field(None)

    created_at: str = Field(default_factory=_now)
    updated_at: str = Field(default_factory=_now)


class StoryParagraphCreate(BaseModel):
    text: str = ""
    character_id: str | None = None
    emotion: str = "neutral"
    sort_index: int = 0


class StoryParagraphUpdate(BaseModel):
    text: str | None = None
    character_id: str | None = None
    emotion: str | None = None
    sort_index: int | None = None


# ── story project ───────────────────────────────────────────────────

class StoryProject(BaseModel):
    id: str = Field(..., description="Project UUID")
    name: str = Field("Untitled Story")
    description: str = ""

    characters: list[StoryCharacter] = Field(default_factory=list)
    paragraphs: list[StoryParagraph] = Field(default_factory=list)
    sfx_cues: list[SFXCue] = Field(default_factory=list)

    # Default voice / narrator
    narrator_profile_id: str | None = Field(
        None,
        description="Voice profile for narration (non-dialogue paragraphs)",
    )

    created_at: str = Field(default_factory=_now)
    updated_at: str = Field(default_factory=_now)


class StoryProjectCreate(BaseModel):
    name: str = "Untitled Story"
    description: str = ""


class StoryProjectUpdate(BaseModel):
    name: str | None = None
    description: str | None = None
    narrator_profile_id: str | None = None


# ── response wrappers ────────────────────────────────────────────────

class StoryProjectResponse(BaseModel):
    project: StoryProject


class StoryProjectsListResponse(BaseModel):
    projects: list[dict[str, Any]]
    total: int
