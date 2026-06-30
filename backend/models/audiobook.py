"""
Pydantic models for the Audiobook workspace.

Supports long-text segmentation, chapter management, character-voice binding,
and emotional consistency constraints.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field


def _now() -> str:
    return datetime.utcnow().isoformat() + "Z"


# ── character profile ────────────────────────────────────────────────

class CharacterProfile(BaseModel):
    """A character in the audiobook, with persistent voice binding."""

    id: str = Field(..., description="Character UUID")
    name: str = Field(..., description="Character name as it appears in the text")
    description: str = Field("", description="Optional character description")

    # Voice binding
    profile_id: str | None = Field(None, description="Voice profile ID")
    engine: str | None = Field(None, description="Engine override")
    language: str = Field("en")

    # Emotional consistency
    default_emotion: str = Field("neutral")
    emotion_constraints: list[str] = Field(
        default_factory=list,
        description="Allowed emotion tags for this character (empty = all)",
    )

    created_at: str = Field(default_factory=_now)


class CharacterProfileCreate(BaseModel):
    name: str
    description: str = ""
    profile_id: str | None = None
    engine: str | None = None
    language: str = "en"
    default_emotion: str = "neutral"
    emotion_constraints: list[str] = Field(default_factory=list)


class CharacterProfileUpdate(BaseModel):
    name: str | None = None
    description: str | None = None
    profile_id: str | None = None
    engine: str | None = None
    language: str | None = None
    default_emotion: str | None = None
    emotion_constraints: list[str] | None = None


# ── narrator config ──────────────────────────────────────────────────

class NarratorConfig(BaseModel):
    """Configuration for the narrator (non-dialogue text)."""

    profile_id: str | None = Field(None, description="Narrator voice profile ID")
    engine: str | None = Field(None)
    language: str = Field("en")
    emotion: str = Field("neutral")


# ── audiobook chapter ───────────────────────────────────────────────

class AudiobookChapter(BaseModel):
    """A chapter in the audiobook, with segmented text."""

    id: str = Field(..., description="Chapter UUID")
    title: str = Field("", description="Chapter title (auto-detected or manual)")
    chapter_index: int = Field(0, description="Chapter number (1-based)")

    # Full text of this chapter (can be very long)
    text: str = Field("", description="Full chapter text")

    # Segmentation: text is split into smaller chunks for TTS
    segments: list[dict[str, Any]] = Field(
        default_factory=list,
        description="List of {text, character_id, emotion, generation_id}",
    )

    status: Literal["draft", "segmenting", "generating", "done", "failed"] = Field(
        "draft"
    )
    error: str | None = Field(None)

    word_count: int = Field(0)
    estimated_duration_sec: float | None = Field(None)

    created_at: str = Field(default_factory=_now)
    updated_at: str = Field(default_factory=_now)


class AudiobookChapterCreate(BaseModel):
    title: str = ""
    text: str = ""
    chapter_index: int = 0


class AudiobookChapterUpdate(BaseModel):
    title: str | None = None
    text: str | None = None
    chapter_index: int | None = None


# ── audiobook project ───────────────────────────────────────────────

class AudiobookProject(BaseModel):
    id: str = Field(..., description="Project UUID")
    name: str = Field("Untitled Audiobook")
    description: str = ""
    author: str = ""
    cover_path: str | None = Field(None)

    # Full raw text (for reference; actual work is done per-chapter)
    raw_text: str = Field("")

    chapters: list[AudiobookChapter] = Field(default_factory=list)
    characters: list[CharacterProfile] = Field(default_factory=list)

    narrator: NarratorConfig = Field(default_factory=NarratorConfig)

    # Segmentation settings
    segment_strategy: Literal["chapter", "paragraph", "sentence", "word_count"] = Field(
        "paragraph"
    )
    segment_word_limit: int = Field(500, ge=50, le=2000)

    created_at: str = Field(default_factory=_now)
    updated_at: str = Field(default_factory=_now)


class AudiobookProjectCreate(BaseModel):
    name: str = "Untitled Audiobook"
    description: str = ""
    author: str = ""
    raw_text: str = ""  # Optional: if provided, auto-segment into chapters


class AudiobookProjectUpdate(BaseModel):
    name: str | None = None
    description: str | None = None
    author: str | None = None
    raw_text: str | None = None
    narrator_profile_id: str | None = None
    segment_strategy: Literal["chapter", "paragraph", "sentence", "word_count"] | None = None
    segment_word_limit: int | None = Field(None, ge=50, le=2000)


# ── response wrappers ────────────────────────────────────────────────

class AudiobookProjectResponse(BaseModel):
    project: AudiobookProject


class AudiobookProjectsListResponse(BaseModel):
    projects: list[dict[str, Any]]
    total: int


class TextAnalysisResponse(BaseModel):
    chapters: list[dict[str, Any]]
    characters: list[dict[str, Any]]
    total_words: int
