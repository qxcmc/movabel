"""
Collaboration service — manages real-time collaborative editing sessions.

Handles session lifecycle, 6-digit invite codes, sync event logging,
conflict detection (last-writer-wins), and participant management.
"""

from __future__ import annotations

import json
import logging
import random
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from .. import config
from ..models.collaboration import (
    CreateSessionRequest,
    JoinSessionRequest,
    ParticipantInfo,
    SessionInfo,
    SyncEvent,
    SyncRequest,
)

logger = logging.getLogger(__name__)

# ── paths ────────────────────────────────────────────────────────────


def _data_dir() -> Path:
    return config.get_data_dir()


def _sessions_dir() -> Path:
    d = _data_dir() / "collab" / "sessions"
    d.mkdir(parents=True, exist_ok=True)
    return d


def _events_dir(session_id: str) -> Path:
    d = _data_dir() / "collab" / "events" / session_id
    d.mkdir(parents=True, exist_ok=True)
    return d


def _session_path(session_id: str) -> Path:
    return _sessions_dir() / f"{session_id}.json"


# ── persistence ──────────────────────────────────────────────────────


def _load_session(session_id: str) -> SessionInfo | None:
    path = _session_path(session_id)
    if not path.exists():
        return None
    try:
        return SessionInfo(**json.loads(path.read_text(encoding="utf-8")))
    except Exception:
        return None


def _save_session(session: SessionInfo) -> None:
    path = _session_path(session.id)
    path.write_text(
        json.dumps(session.model_dump(mode="json"), indent=2, default=str),
        encoding="utf-8",
    )


def _delete_session_file(session_id: str) -> None:
    path = _session_path(session_id)
    if path.exists():
        path.unlink()


def _load_events(session_id: str) -> list[SyncEvent]:
    events_dir = _events_dir(session_id)
    events: list[SyncEvent] = []
    for f in sorted(events_dir.glob("*.json")):
        try:
            data = json.loads(f.read_text(encoding="utf-8"))
            for item in data if isinstance(data, list) else [data]:
                events.append(SyncEvent(**item))
        except Exception:
            continue
    return events


def _append_events(session_id: str, events: list[SyncEvent]) -> None:
    events_dir = _events_dir(session_id)
    batch_id = uuid.uuid4().hex[:12]
    batch_path = events_dir / f"{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}_{batch_id}.json"
    data = [e.model_dump(mode="json") for e in events]
    batch_path.write_text(json.dumps(data, indent=2, default=str), encoding="utf-8")


# ── invite code ──────────────────────────────────────────────────────


def _generate_invite_code() -> str:
    """Generate a unique 6-digit invite code."""
    existing_sessions = _sessions_dir().glob("*.json")
    existing_codes: set[str] = set()
    for f in existing_sessions:
        try:
            data = json.loads(f.read_text(encoding="utf-8"))
            if "session_code" in data:
                existing_codes.add(data["session_code"])
        except Exception:
            continue

    for _ in range(100):  # Retry up to 100 times for uniqueness
        code = f"{random.randint(100000, 999999)}"
        if code not in existing_codes:
            return code
    # Fallback — extremely unlikely
    return f"{random.randint(100000, 999999)}"


# ── session lifecycle ────────────────────────────────────────────────


def create_session(request: CreateSessionRequest, host_user_id: str, host_name: str) -> SessionInfo:
    """Create a new collaboration session."""
    session = SessionInfo(
        id=str(uuid.uuid4()),
        project_id=request.project_id,
        project_type=request.project_type,
        host_user=host_user_id,
        session_code=_generate_invite_code(),
        status="active",
        participants=[
            ParticipantInfo(
                user_id=host_user_id,
                name=host_name,
                role="host",
            )
        ],
    )
    _save_session(session)
    logger.info("Collaboration session created: %s (code: %s)", session.id, session.session_code)
    return session


def join_session(request: JoinSessionRequest) -> SessionInfo | None:
    """Join an existing session using invite code."""
    for f in _sessions_dir().glob("*.json"):
        try:
            data = json.loads(f.read_text(encoding="utf-8"))
            if data.get("session_code") == request.session_code and data.get("status") == "active":
                session = SessionInfo(**data)
                _add_participant(session, request.user_id, request.name)
                _save_session(session)
                logger.info("User %s joined session %s", request.user_id, session.id)
                return session
        except Exception:
            continue
    return None


def leave_session(session_id: str, user_id: str) -> SessionInfo | None:
    """Remove a participant from a session."""
    session = _load_session(session_id)
    if session is None:
        return None
    session.participants = [p for p in session.participants if p.user_id != user_id]
    _save_session(session)
    logger.info("User %s left session %s", user_id, session_id)
    return session


def close_session(session_id: str, host_user_id: str) -> SessionInfo | None:
    """Close a session (host only)."""
    session = _load_session(session_id)
    if session is None:
        return None
    if session.host_user != host_user_id:
        return None
    session.status = "closed"
    session.closed_at = datetime.now(timezone.utc)
    _save_session(session)
    logger.info("Session closed: %s", session_id)
    return session


def get_session(session_id: str) -> SessionInfo | None:
    return _load_session(session_id)


def list_active_sessions() -> list[SessionInfo]:
    sessions: list[SessionInfo] = []
    for f in _sessions_dir().glob("*.json"):
        try:
            data = json.loads(f.read_text(encoding="utf-8"))
            if data.get("status") == "active":
                sessions.append(SessionInfo(**data))
        except Exception:
            continue
    return sessions


# ── participant management ───────────────────────────────────────────


def _add_participant(session: SessionInfo, user_id: str, name: str) -> None:
    """Add or update a participant."""
    for p in session.participants:
        if p.user_id == user_id:
            p.last_active = datetime.now(timezone.utc)
            p.is_online = True
            return
    session.participants.append(
        ParticipantInfo(
            user_id=user_id,
            name=name,
            role="editor",
        )
    )


def get_participants(session_id: str) -> list[ParticipantInfo] | None:
    session = _load_session(session_id)
    if session is None:
        return None
    return session.participants


# ── sync events ──────────────────────────────────────────────────────


def submit_sync_events(session_id: str, sync_request: SyncRequest, user_id: str) -> dict:
    """
    Submit sync events with last-writer-wins conflict detection.

    Returns dict with accepted/rejected counts, last sequence, and conflict details.
    """
    session = _load_session(session_id)
    if session is None:
        return {"accepted": 0, "rejected": len(sync_request.events), "last_sequence": 0, "conflicts": []}

    existing_events = _load_events(session_id)
    last_seq = max((e.sequence_number for e in existing_events), default=0)

    accepted: list[SyncEvent] = []
    rejected: list[str] = []

    for event in sync_request.events:
        event.id = event.id or str(uuid.uuid4())
        event.session_id = session_id
        event.user_id = user_id
        event.timestamp = event.timestamp or datetime.now(timezone.utc)

        # Conflict detection: same target_id + same type within a small time window
        conflict = _detect_conflict(event, existing_events)
        if conflict:
            # Last-writer-wins: still accept but log conflict
            event.sequence_number = last_seq + 1
            last_seq += 1
            accepted.append(event)
            rejected.append(event.id)
        else:
            event.sequence_number = last_seq + 1
            last_seq += 1
            accepted.append(event)

    if accepted:
        _append_events(session_id, accepted)

    return {
        "accepted": len(accepted),
        "rejected": len(rejected),
        "last_sequence": last_seq,
        "conflicts": rejected,
    }


def get_events_after(session_id: str, after_sequence: int, limit: int = 100) -> tuple[list[SyncEvent], int, bool]:
    """
    Pull events with sequence number > after_sequence.

    Returns (events, last_sequence, has_more).
    """
    all_events = _load_events(session_id)
    filtered = [e for e in all_events if e.sequence_number > after_sequence]
    filtered.sort(key=lambda e: e.sequence_number)

    has_more = len(filtered) > limit
    result = filtered[:limit]
    last_seq = result[-1].sequence_number if result else after_sequence

    return result, last_seq, has_more


# ── conflict detection ───────────────────────────────────────────────


def _detect_conflict(event: SyncEvent, existing: list[SyncEvent]) -> bool:
    """
    Detect if event conflicts with existing events.

    Same target_id + same type + within 2 seconds = conflict.
    """
    now = event.timestamp
    for existing_event in existing:
        if existing_event.target_id != event.target_id:
            continue
        if existing_event.type != event.type:
            continue
        delta = abs((now - existing_event.timestamp).total_seconds())
        if delta < 2.0:
            return True
    return False


# ── session broadcast stub ───────────────────────────────────────────


def broadcast_session_update(session_id: str, event_type: str, payload: dict) -> None:
    """
    Broadcast a session state change to all participants.

    Placeholder — in production this would use WebSocket.
    """
    logger.debug("Broadcast [%s] to session %s: %s", event_type, session_id, payload)
