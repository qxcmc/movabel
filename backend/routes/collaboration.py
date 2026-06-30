"""
Collaboration session routes.

POST   /collab/sessions                  — Create session
POST   /collab/sessions/join             — Join via invite code
POST   /collab/sessions/{id}/leave       — Leave session
GET    /collab/sessions/{id}             — Session details
GET    /collab/sessions/{id}/participants — Participant list
POST   /collab/sessions/{id}/sync        — Submit sync events
GET    /collab/sessions/{id}/events      — Pull incremental events
DELETE /collab/sessions/{id}             — Close session (host)
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query

from ..models.collaboration import (
    CreateSessionRequest,
    JoinSessionRequest,
    LeaveSessionRequest,
    SessionResponse,
    ParticipantsResponse,
    SyncRequest,
    EventsResponse,
    SyncResponse,
)
from ..services import collaboration as collab_service

router = APIRouter(prefix="/collab/sessions", tags=["collaboration"])


# ── session lifecycle ────────────────────────────────────────────────


@router.post("", response_model=SessionResponse)
async def create_session(
    request: CreateSessionRequest,
    host_user_id: str = Query("default_user", alias="user_id"),
    host_name: str = Query("Host", alias="user_name"),
):
    """Create a new collaboration session."""
    session = collab_service.create_session(request, host_user_id, host_name)
    return SessionResponse(session=session)


@router.post("/join", response_model=SessionResponse)
async def join_session(request: JoinSessionRequest):
    """Join an existing session using a 6-digit invite code."""
    session = collab_service.join_session(request)
    if session is None:
        raise HTTPException(
            status_code=404,
            detail="Session not found, closed, or invalid invite code",
        )
    return SessionResponse(session=session)


@router.post("/{session_id}/leave", response_model=SessionResponse)
async def leave_session(session_id: str, request: LeaveSessionRequest):
    """Leave a collaboration session."""
    session = collab_service.leave_session(session_id, request.user_id)
    if session is None:
        raise HTTPException(status_code=404, detail="Session not found")
    return SessionResponse(session=session)


@router.delete("/{session_id}", response_model=SessionResponse)
async def close_session(
    session_id: str,
    user_id: str = Query("default_user", alias="user_id"),
):
    """Close a collaboration session (host only)."""
    session = collab_service.close_session(session_id, user_id)
    if session is None:
        raise HTTPException(status_code=404, detail="Session not found or not authorized")
    return SessionResponse(session=session)


# ── session info ─────────────────────────────────────────────────────


@router.get("/{session_id}", response_model=SessionResponse)
async def get_session(session_id: str):
    """Get session details."""
    session = collab_service.get_session(session_id)
    if session is None:
        raise HTTPException(status_code=404, detail="Session not found")
    return SessionResponse(session=session)


@router.get("/{session_id}/participants", response_model=ParticipantsResponse)
async def get_participants(session_id: str):
    """Get participant list for a session."""
    participants = collab_service.get_participants(session_id)
    if participants is None:
        raise HTTPException(status_code=404, detail="Session not found")
    return ParticipantsResponse(
        participants=participants,
        total=len(participants),
        session_id=session_id,
    )


# ── sync ─────────────────────────────────────────────────────────────


@router.post("/{session_id}/sync", response_model=SyncResponse)
async def submit_sync(
    session_id: str,
    request: SyncRequest,
    user_id: str = Query("default_user", alias="user_id"),
):
    """Submit sync events for collaborative editing."""
    result = collab_service.submit_sync_events(session_id, request, user_id)
    return SyncResponse(
        accepted=result["accepted"],
        rejected=result["rejected"],
        last_sequence=result["last_sequence"],
        conflicts=result["conflicts"],
    )


@router.get("/{session_id}/events", response_model=EventsResponse)
async def pull_events(
    session_id: str,
    after_sequence: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=500),
):
    """Pull incremental events after a given sequence number."""
    events, last_seq, has_more = collab_service.get_events_after(session_id, after_sequence, limit)
    return EventsResponse(
        events=events,
        last_sequence=last_seq,
        session_id=session_id,
        has_more=has_more,
    )
