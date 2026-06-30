"""
OpenAI TTS backend — cloud-based text-to-speech via OpenAI's /v1/audio/speech.

Implements the TTSBackend Protocol so it slots directly into the existing
Movabel engine pipeline without any architecture changes.  Uses httpx for
async HTTP transport; streams the response into an in-memory WAV buffer.
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

OPENAI_VOICES = ["alloy", "ash", "coral", "echo", "fable", "onyx", "nova", "sage", "shimmer"]
OPENAI_MODELS = ["tts-1", "tts-1-hd", "gpt-4o-mini-tts"]
OPENAI_FORMATS = ["mp3", "opus", "aac", "flac", "wav", "pcm"]
OPENAI_LANGUAGES = [
    "zh", "en", "ja", "ko", "de", "fr", "ru", "pt", "es", "it",
    "he", "ar", "da", "el", "fi", "hi", "ms", "nl", "no", "pl", "sv", "sw", "tr",
]

DEFAULT_OPENAI_MODEL = "tts-1"
DEFAULT_OPENAI_VOICE = "alloy"
DEFAULT_OPENAI_RESPONSE_FORMAT = "wav"

_SPECIAL_VOICES = {
    "gpt-4o-mini-tts": ["alloy", "ash", "coral", "echo", "fable", "onyx", "nova", "sage", "shimmer"],
}


def _get_api_key() -> str:
    """Resolve the OpenAI API key from config file."""
    settings_file = Path(get_data_dir()) / "cloud_tts_settings.json"
    if settings_file.exists():
        import json
        try:
            settings = json.loads(settings_file.read_text())
            key = settings.get("openai_api_key")
            if key and key.strip():
                return key.strip()
        except Exception:
            pass
    key = os.environ.get("OPENAI_API_KEY", "").strip()
    if not key:
        import subprocess
        try:
            result = subprocess.run(
                ["keyring", "get", "movabel_openai", "api_key"],
                capture_output=True, text=True, timeout=5,
            )
            if result.returncode == 0 and result.stdout.strip():
                key = result.stdout.strip()
        except Exception:
            pass
    return key


def _get_base_url() -> str:
    """Resolve the OpenAI base URL from config file."""
    settings_file = Path(get_data_dir()) / "cloud_tts_settings.json"
    if settings_file.exists():
        import json
        try:
            settings = json.loads(settings_file.read_text())
            url = settings.get("openai_base_url")
            if url and url.strip():
                return url.strip().rstrip("/")
        except Exception:
            pass
    return os.environ.get("OPENAI_BASE_URL", "https://api.openai.com").rstrip("/")


class OpenAITTSBackend:
    """OpenAI cloud TTS backend conforming to the TTSBackend Protocol."""

    MODEL_CONFIGS: list = []  # defined once registered in __init__.py

    def __init__(self):
        self._client: Optional[httpx.AsyncClient] = None
        self._loaded = False  # cloud backends are always "loaded" on demand

    # ── Protocol methods ─────────────────────────────────────────────

    async def load_model(self, model_size: str = "default") -> None:
        """Cloud backends are stateless — just mark as ready."""
        self._loaded = True

    async def create_voice_prompt(
        self,
        audio_path: str,
        reference_text: str,
        use_cache: bool = True,
    ) -> Tuple[dict, bool]:
        """Cloud backends don't support voice cloning — return empty prompt."""
        return {}, False

    async def combine_voice_prompts(
        self,
        audio_paths: list[str],
        reference_texts: list[str],
    ) -> Tuple[np.ndarray, str]:
        """Not supported — return empty."""
        return np.array([], dtype=np.float32), ""

    async def generate(
        self,
        text: str,
        voice_prompt: dict,
        language: str = "en",
        seed: Optional[int] = None,
        instruct: Optional[str] = None,
    ) -> Tuple[np.ndarray, int]:
        """Generate speech via OpenAI TTS API."""
        api_key = _get_api_key()
        if not api_key:
            raise RuntimeError(
                "OpenAI API key not configured. Set it in Settings → Cloud TTS or "
                "export OPENAI_API_KEY."
            )

        base_url = _get_base_url()
        settings_file = Path(get_data_dir()) / "cloud_tts_settings.json"

        model = DEFAULT_OPENAI_MODEL
        voice = DEFAULT_OPENAI_VOICE
        response_format = DEFAULT_OPENAI_RESPONSE_FORMAT

        if settings_file.exists():
            import json
            try:
                settings = json.loads(settings_file.read_text())
                model = settings.get("openai_default_model", model)
                voice = settings.get("openai_default_voice", voice)
            except Exception:
                pass

        payload: dict = {
            "model": model,
            "input": text,
            "voice": voice,
            "response_format": response_format,
        }
        if instruct and model == "gpt-4o-mini-tts":
            payload["instructions"] = instruct
        if seed is not None:
            payload["seed"] = seed

        if self._client is None:
            self._client = httpx.AsyncClient(timeout=httpx.Timeout(120.0))

        try:
            response = await self._client.post(
                f"{base_url}/v1/audio/speech",
                json=payload,
                headers={
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json",
                },
            )
            response.raise_for_status()
        except httpx.HTTPStatusError as e:
            detail = e.response.text[:500] if e.response else str(e)
            raise RuntimeError(f"OpenAI TTS API error ({e.response.status_code}): {detail}") from e
        except httpx.RequestError as e:
            raise RuntimeError(f"OpenAI TTS request failed: {e}") from e

        # Parse audio from response
        audio_bytes = response.content
        if not audio_bytes:
            raise RuntimeError("OpenAI TTS returned empty response.")

        # soundfile can't read WAV from a BytesIO reliably on all platforms,
        # so we write to a temp file first.
        with tempfile.NamedTemporaryFile(suffix=f".{response_format}", delete=False) as tmp:
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
        """Close the HTTP client."""
        self._loaded = False
        if self._client is not None:
            # httpx clients are cleaned up via context manager, but for sync unload
            # we can't await close. The client will be recreated on next generate.
            self._client = None

    def is_loaded(self) -> bool:
        """Cloud backends are always available as long as API key is set."""
        return bool(_get_api_key())

    def _get_model_path(self, model_size: str = "default") -> str:
        return "openai-tts-api"
