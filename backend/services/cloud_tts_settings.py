"""
Cloud TTS settings persistence — JSON-file-backed key store for API keys
and default parameters used by the cloud TTS backends (OpenAI / ElevenLabs).
"""
from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Optional

from ..config import get_data_dir

_SETTINGS_FILE = Path(get_data_dir()) / "cloud_tts_settings.json"


def _read_settings() -> dict:
    if _SETTINGS_FILE.exists():
        try:
            return json.loads(_SETTINGS_FILE.read_text())
        except (json.JSONDecodeError, OSError):
            pass
    return {}


def _write_settings(data: dict) -> None:
    _SETTINGS_FILE.parent.mkdir(parents=True, exist_ok=True)
    _SETTINGS_FILE.write_text(json.dumps(data, indent=2))


def get_openai_api_key() -> str:
    """Return the stored OpenAI API key, or env var fallback."""
    settings = _read_settings()
    return settings.get("openai_api_key") or os.environ.get("OPENAI_API_KEY", "")


def get_elevenlabs_api_key() -> str:
    """Return the stored ElevenLabs API key, or env var fallback."""
    settings = _read_settings()
    return settings.get("elevenlabs_api_key") or os.environ.get("ELEVENLABS_API_KEY", "")


def get_settings() -> dict:
    """Return the full settings dict (with keys masked)."""
    settings = _read_settings()
    masked = dict(settings)
    if masked.get("openai_api_key"):
        masked["openai_api_key"] = masked["openai_api_key"][:6] + "..." if len(masked["openai_api_key"]) > 6 else "***"
    if masked.get("elevenlabs_api_key"):
        masked["elevenlabs_api_key"] = masked["elevenlabs_api_key"][:6] + "..." if len(masked["elevenlabs_api_key"]) > 6 else "***"
    return masked


def get_settings_public() -> dict:
    """Return settings safe for public exposure (keys fully hidden)."""
    settings = _read_settings()
    result = {
        "openai_api_key_set": bool(settings.get("openai_api_key")),
        "openai_base_url": settings.get("openai_base_url", "https://api.openai.com"),
        "openai_default_model": settings.get("openai_default_model", "tts-1"),
        "openai_default_voice": settings.get("openai_default_voice", "alloy"),
        "elevenlabs_api_key_set": bool(settings.get("elevenlabs_api_key")),
        "elevenlabs_default_model": settings.get("elevenlabs_default_model", "eleven_multilingual_v2"),
        "elevenlabs_default_voice_id": settings.get("elevenlabs_default_voice_id"),
    }
    return result


def update_settings(updates: dict) -> dict:
    """Merge partial updates into the settings file and return public view."""
    settings = _read_settings()
    for key in (
        "openai_api_key",
        "openai_base_url",
        "openai_default_model",
        "openai_default_voice",
        "elevenlabs_api_key",
        "elevenlabs_default_model",
        "elevenlabs_default_voice_id",
    ):
        if key in updates and updates[key] is not None:
            settings[key] = updates[key]
    _write_settings(settings)
    return get_settings_public()
