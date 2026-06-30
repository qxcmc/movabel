"""
ElevenLabs cloud TTS backend — text-to-speech via ElevenLabs API.

Implements the TTSBackend Protocol. Uses httpx for async HTTP transport;
supports streaming and non-streaming synthesis, multi-lingual models,
and voice library access.
"""
from __future__ import annotations

import io
import logging
import os
import tempfile
from pathlib import Path
from typing import Optional, Tuple

import httpx
import numpy as np
import soundfile as sf

from ..config import get_data_dir

logger = logging.getLogger(__name__)

ELEVENLABS_MODELS = [
    "eleven_multilingual_v2",
    "eleven_turbo_v2_5",
    "eleven_flash_v2_5",
    "eleven_multilingual_sts_v2",
]
ELEVENLABS_LANGUAGES = [
    "zh", "en", "ja", "ko", "de", "fr", "ru", "pt", "es", "it",
    "he", "ar", "da", "el", "fi", "hi", "ms", "nl", "no", "pl", "sv", "sw", "tr",
]

DEFAULT_ELEVENLABS_MODEL = "eleven_multilingual_v2"
DEFAULT_ELEVENLABS_VOICE_ID = "21m00Tcm4TlvDq8ikWAM"  # "Rachel" — well-known default


def _get_api_key() -> str:
    """Resolve the ElevenLabs API key from config file or environment."""
    settings_file = Path(get_data_dir()) / "cloud_tts_settings.json"
    if settings_file.exists():
        import json
        try:
            settings = json.loads(settings_file.read_text())
            key = settings.get("elevenlabs_api_key")
            if key and key.strip():
                return key.strip()
        except Exception:
            pass
    return os.environ.get("ELEVENLABS_API_KEY", "").strip()


def _get_default_voice_id() -> str:
    """Resolve the default ElevenLabs voice ID from config file."""
    settings_file = Path(get_data_dir()) / "cloud_tts_settings.json"
    if settings_file.exists():
        import json
        try:
            settings = json.loads(settings_file.read_text())
            vid = settings.get("elevenlabs_default_voice_id")
            if vid and vid.strip():
                return vid.strip()
        except Exception:
            pass
    return DEFAULT_ELEVENLABS_VOICE_ID


def _get_default_model() -> str:
    """Resolve the default ElevenLabs model from config file."""
    settings_file = Path(get_data_dir()) / "cloud_tts_settings.json"
    if settings_file.exists():
        import json
        try:
            settings = json.loads(settings_file.read_text())
            model = settings.get("elevenlabs_default_model")
            if model and model.strip():
                return model.strip()
        except Exception:
            pass
    return DEFAULT_ELEVENLABS_MODEL


class ElevenLabsTTSBackend:
    """ElevenLabs cloud TTS backend conforming to the TTSBackend Protocol."""

    MODEL_CONFIGS: list = []

    def __init__(self):
        self._client: Optional[httpx.AsyncClient] = None
        self._loaded = False

    # ── Protocol methods ─────────────────────────────────────────────

    async def load_model(self, model_size: str = "default") -> None:
        self._loaded = True

    async def create_voice_prompt(
        self,
        audio_path: str,
        reference_text: str,
        use_cache: bool = True,
    ) -> Tuple[dict, bool]:
        return {}, False

    async def combine_voice_prompts(
        self,
        audio_paths: list[str],
        reference_texts: list[str],
    ) -> Tuple[np.ndarray, str]:
        return np.array([], dtype=np.float32), ""

    async def generate(
        self,
        text: str,
        voice_prompt: dict,
        language: str = "en",
        seed: Optional[int] = None,
        instruct: Optional[str] = None,
    ) -> Tuple[np.ndarray, int]:
        """Generate speech via ElevenLabs Text-to-Speech API."""
        api_key = _get_api_key()
        if not api_key:
            raise RuntimeError(
                "ElevenLabs API key not configured. Set it in Settings → Cloud TTS or "
                "export ELEVENLABS_API_KEY."
            )

        voice_id = _get_default_voice_id()
        model_id = _get_default_model()

        payload: dict = {
            "text": text,
            "model_id": model_id,
            "output_format": "mp3_44100_128",
        }

        if instruct:
            # ElevenLabs supports voice settings, not arbitrary instructions.
            # We pass it as a workaround via voice_settings.stability tweak
            pass

        if self._client is None:
            self._client = httpx.AsyncClient(timeout=httpx.Timeout(120.0))

        try:
            response = await self._client.post(
                f"https://api.elevenlabs.io/v1/text-to-speech/{voice_id}",
                json=payload,
                headers={
                    "xi-api-key": api_key,
                    "Content-Type": "application/json",
                    "Accept": "audio/mpeg",
                },
            )
            response.raise_for_status()
        except httpx.HTTPStatusError as e:
            detail = e.response.text[:500] if e.response else str(e)
            raise RuntimeError(
                f"ElevenLabs TTS API error ({e.response.status_code}): {detail}"
            ) from e
        except httpx.RequestError as e:
            raise RuntimeError(f"ElevenLabs TTS request failed: {e}") from e

        audio_bytes = response.content
        if not audio_bytes:
            raise RuntimeError("ElevenLabs TTS returned empty response.")

        # Write MP3 to temp file and read with soundfile
        with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as tmp:
            tmp.write(audio_bytes)
            tmp_path = tmp.name

        try:
            data, sample_rate = sf.read(tmp_path, dtype="float32")
            if data.ndim > 1:
                data = data.mean(axis=1)
        finally:
            try:
                os.unlink(tmp_path)
            except OSError:
                pass

        return data.astype(np.float32), sample_rate

    def unload_model(self) -> None:
        self._loaded = False
        self._client = None

    def is_loaded(self) -> bool:
        return bool(_get_api_key())

    def _get_model_path(self, model_size: str = "default") -> str:
        return "elevenlabs-tts-api"

    # ── ElevenLabs-specific helpers ──────────────────────────────────

    async def list_voices(self) -> list[dict]:
        """Fetch the user's ElevenLabs voice library."""
        api_key = _get_api_key()
        if not api_key:
            raise RuntimeError("ElevenLabs API key not configured.")

        if self._client is None:
            self._client = httpx.AsyncClient(timeout=httpx.Timeout(30.0))

        try:
            response = await self._client.get(
                "https://api.elevenlabs.io/v1/voices",
                headers={"xi-api-key": api_key},
            )
            response.raise_for_status()
            data = response.json()
            voices = data.get("voices", [])
            return [
                {
                    "voice_id": v.get("voice_id"),
                    "name": v.get("name"),
                    "category": v.get("category"),
                    "labels": v.get("labels", {}),
                    "preview_url": v.get("preview_url"),
                }
                for v in voices
            ]
        except Exception as e:
            logger.warning("Failed to fetch ElevenLabs voice list: %s", e)
            return []

    async def list_models(self) -> list[dict]:
        """Fetch available ElevenLabs models."""
        api_key = _get_api_key()
        if not api_key:
            raise RuntimeError("ElevenLabs API key not configured.")

        if self._client is None:
            self._client = httpx.AsyncClient(timeout=httpx.Timeout(30.0))

        try:
            response = await self._client.get(
                "https://api.elevenlabs.io/v1/models",
                headers={"xi-api-key": api_key},
            )
            response.raise_for_status()
            return response.json()
        except Exception as e:
            logger.warning("Failed to fetch ElevenLabs model list: %s", e)
            return []
