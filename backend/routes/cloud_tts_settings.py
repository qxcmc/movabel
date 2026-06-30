"""
Cloud TTS settings routes.

GET  /settings/cloud-tts — retrieve current settings (keys masked).
PUT  /settings/cloud-tts — update API keys and defaults.
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException

from .. import models
from ..services import cloud_tts_settings

router = APIRouter(prefix="/settings", tags=["settings"])


@router.get("/cloud-tts", response_model=models.CloudTTSSettingsResponse)
async def get_cloud_tts_settings():
    """Get cloud TTS settings with API keys masked."""
    pub = cloud_tts_settings.get_settings_public()
    return models.CloudTTSSettingsResponse(**pub)


@router.put("/cloud-tts", response_model=models.CloudTTSSettingsResponse)
async def update_cloud_tts_settings(req: models.CloudTTSSettingsUpdate):
    """Update cloud TTS API keys and defaults."""
    updates = {}
    if req.openai_api_key is not None:
        if len(req.openai_api_key.strip()) < 3:
            raise HTTPException(status_code=400, detail="OpenAI API key is too short.")
        updates["openai_api_key"] = req.openai_api_key.strip()
    if req.openai_base_url is not None:
        updates["openai_base_url"] = req.openai_base_url.strip()
    if req.openai_default_model is not None:
        if req.openai_default_model not in ("tts-1", "tts-1-hd", "gpt-4o-mini-tts"):
            raise HTTPException(
                status_code=400,
                detail=f"Unknown OpenAI model: {req.openai_default_model}. "
                       "Supported: tts-1, tts-1-hd, gpt-4o-mini-tts",
            )
        updates["openai_default_model"] = req.openai_default_model
    if req.openai_default_voice is not None:
        updates["openai_default_voice"] = req.openai_default_voice
    if req.elevenlabs_api_key is not None:
        if len(req.elevenlabs_api_key.strip()) < 3:
            raise HTTPException(status_code=400, detail="ElevenLabs API key is too short.")
        updates["elevenlabs_api_key"] = req.elevenlabs_api_key.strip()
    if req.elevenlabs_default_model is not None:
        if req.elevenlabs_default_model not in (
            "eleven_multilingual_v2",
            "eleven_turbo_v2_5",
            "eleven_flash_v2_5",
            "eleven_multilingual_sts_v2",
        ):
            raise HTTPException(
                status_code=400,
                detail=f"Unknown ElevenLabs model: {req.elevenlabs_default_model}",
            )
        updates["elevenlabs_default_model"] = req.elevenlabs_default_model
    if req.elevenlabs_default_voice_id is not None:
        updates["elevenlabs_default_voice_id"] = req.elevenlabs_default_voice_id

    pub = cloud_tts_settings.update_settings(updates)
    return models.CloudTTSSettingsResponse(**pub)
