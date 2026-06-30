"""
Pydantic models for the collaboration system.

Covers sessions, participants, sync events, and conflict detection
for multi-user collaborative editing.
"""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


# ── participant ──────────────────────────────────────────────────────

VALID_ROLES = ["host", "editor", "viewer"]


class ParticipantInfo(BaseModel):
    """A participant in a collaboration session."""
    user_id: str = Field(..., description="Unique user identifier")
    name: str = Field(..., min_length=1, max_length=100)
    role: str = Field("editor", description="host / editor / viewer")
    joined_at: datetime = Field(default_factory=datetime.utcnow)
    last_active: datetime = Field(default_factory=datetime.utcnow)
    is_online: bool = Field(True)


# ── session ──────────────────────────────────────────────────────────


class SessionInfo(BaseModel):
    """A collaboration session for a project."""
    id: str = Field(..., description="Unique session ID")
    project_id: str = Field(..., description="Associated project ID")
    project_type: str = Field("", description="documentary / commercial / storytelling / etc.")
    host_user: str = Field(..., description="User ID of the session host")
    session_code: str = Field(..., description="6-digit invite code")
    participants: list[ParticipantInfo] = Field(default_factory=list)
    status: str = Field("active", description="active / closed / paused")
    created_at: datetime = Field(default_factory=datetime.utcnow)
    closed_at: Optional[datetime] = None


# ── sync events ─────────────────────────────────────────────────────

VALID_EVENT_TYPES = [
    "text_insert",
    "text_delete",
    "text_replace",
    "param_change",
    "scene_reorder",
    "scene_add",
    "scene_delete",
    "voice_binding_change",
    "segment_add",
    "segment_delete",
    "cursor_move",
    "selection_change",
]


class SyncEvent(BaseModel):
    """A single synchronisation event in a collaborative session."""
    id: str = Field(..., description="Unique event ID")
    session_id: str = Field(...)
    type: str = Field(..., description="Event type")
    payload: dict = Field(default_factory=dict, description="Event-specific data")
    target_id: str = Field("", description="ID of the affected object (scene/segment/etc)")
    user_id: str = Field(...)
    user_name: str = Field("")
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    sequence_number: int = Field(0, description="Monotonic sequence number for ordering")


# ── requests ─────────────────────────────────────────────────────────


class CreateSessionRequest(BaseModel):
    """Request to create a new collaboration session."""
    project_id: str = Field(...)
    project_type: str = Field("documentary")


class JoinSessionRequest(BaseModel):
    """Request to join a session via invite code."""
    session_code: str = Field(..., min_length=6, max_length=6)
    user_id: str = Field(..., min_length=1)
    name: str = Field(..., min_length=1, max_length=100)


class LeaveSessionRequest(BaseModel):
    """Request to leave a session."""
    user_id: str = Field(...)


class SyncRequest(BaseModel):
    """Submit one or more sync events."""
    events: list[SyncEvent] = Field(..., min_items=1, max_items=50)
    base_sequence: int = Field(0, description="Last known sequence number from client")


# ── response wrappers ────────────────────────────────────────────────


class SessionResponse(BaseModel):
    session: SessionInfo


class SessionsListResponse(BaseModel):
    sessions: list[SessionInfo]
    total: int


class ParticipantsResponse(BaseModel):
    participants: list[ParticipantInfo]
    total: int
    session_id: str


class EventsResponse(BaseModel):
    events: list[SyncEvent]
    last_sequence: int
    session_id: str
    has_more: bool = False


class SyncResponse(BaseModel):
    accepted: int
    rejected: int
    last_sequence: int
    conflicts: list[str] = Field(
        default_factory=list,
        description="IDs of events rejected due to conflicts",
    )
