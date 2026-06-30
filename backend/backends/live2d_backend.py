"""
Live2D backend — manages Live2D models, real-time lip-sync analysis,
expression handling, and phoneme-to-viseme mapping.

Performs RMS energy analysis and phoneme mapping from audio chunks
to drive mouth_open/mouth_form parameters for Live2D Cubism SDK.
"""

from __future__ import annotations

import logging
import math
from pathlib import Path
from typing import Optional

import numpy as np

logger = logging.getLogger(__name__)

# ── viseme mapping ───────────────────────────────────────────────────

# Standard phoneme-to-viseme mapping (based on Pocketsphinx viseme set)
PHONEME_TO_VISEME: dict[str, str] = {
    # Bilabial
    "p": "PBM", "b": "PBM", "m": "PBM",
    # Labiodental
    "f": "FV", "v": "FV",
    # Dental/Alveolar
    "th": "ThDh", "dh": "ThDh",
    "t": "TD", "d": "TD", "n": "TD", "l": "TD",
    "s": "SZ", "z": "SZ",
    "sh": "SH", "zh": "SH", "ch": "SH", "jh": "SH",
    # Palatal
    "y": "Y", "r": "R", "w": "W",
    # Velar
    "k": "KG", "g": "KG", "ng": "KG",
    # Vowels - open
    "aa": "AA", "ae": "AA", "ah": "AA", "ao": "AA",
    "aw": "AA", "ay": "AA",
    # Vowels - mid
    "eh": "EH", "er": "ER", "ey": "EY",
    # Vowels - close
    "ih": "IH", "iy": "IY",
    # Vowels - rounded
    "ow": "OW", "oy": "OY", "uh": "UH", "uw": "UW",
}


VISEME_MOUTH_OPEN: dict[str, float] = {
    "PBM": 0.0,  # Lips closed
    "FV": 0.3,   # Lip-teeth
    "ThDh": 0.2,
    "TD": 0.4,
    "SZ": 0.35,
    "SH": 0.45,
    "Y": 0.4,
    "R": 0.3,
    "W": 0.25,
    "KG": 0.3,
    "AA": 0.8,   # Wide open
    "EH": 0.5,
    "ER": 0.4,
    "EY": 0.5,
    "IH": 0.3,
    "IY": 0.25,
    "OW": 0.5,
    "OY": 0.5,
    "UH": 0.3,
    "UW": 0.2,
}

VISEME_MOUTH_WIDTH: dict[str, float] = {
    "PBM": 0.3,
    "FV": 0.4,
    "ThDh": 0.45,
    "TD": 0.5,
    "SZ": 0.55,
    "SH": 0.5,
    "Y": 0.5,
    "R": 0.45,
    "W": 0.3,
    "KG": 0.4,
    "AA": 0.6,
    "EH": 0.55,
    "ER": 0.45,
    "EY": 0.5,
    "IH": 0.4,
    "IY": 0.3,
    "OW": 0.4,
    "OY": 0.4,
    "UH": 0.3,
    "UW": 0.2,
}


class Live2DBackend:
    """
    Live2D avatar backend for real-time lip-sync.

    Analyzes audio chunks to produce frame-by-frame lip-sync parameters
    (mouth_open, mouth_form, volume) that can be fed to a Live2D Cubism
    SDK renderer on the frontend.

    Usage::

        backend = Live2DBackend()
        frames = await backend.analyze_audio(audio_path)
        # Each frame: {timestamp_ms, mouth_open, mouth_width, volume}
    """

    def __init__(self):
        self._models_dir: Optional[Path] = None

    # ── model management ─────────────────────────────────────────────

    def get_models_dir(self) -> Path:
        """Get the Live2D models directory."""
        if self._models_dir is not None:
            return self._models_dir

        from .. import config
        d = config.get_data_dir() / "live2d_models"
        d.mkdir(parents=True, exist_ok=True)
        self._models_dir = d
        return d

    def list_installed_models(self) -> list[dict]:
        """
        Discover installed Live2D models.

        Returns:
            List of model info dicts with id, name, version, expressions, etc.
        """
        from datetime import datetime

        base = self.get_models_dir()
        models = []

        if not base.exists():
            return models

        for model_dir in sorted(base.iterdir()):
            if not model_dir.is_dir():
                continue

            model_json = model_dir / f"{model_dir.name}.model3.json"
            if not model_json.exists():
                # Try to find any .model3.json
                candidates = list(model_dir.glob("*.model3.json"))
                if candidates:
                    model_json = candidates[0]
                else:
                    continue

            try:
                import json
                data = json.loads(model_json.read_text(encoding="utf-8"))
                name = data.get("Name", model_dir.name)
                version = str(data.get("Version", "1.0"))

                # Discover expressions
                expressions = []
                exp_dir = model_dir / "expressions"
                if exp_dir.exists():
                    for exp_file in exp_dir.glob("*.exp3.json"):
                        exp_name = exp_file.stem.replace(".exp3", "")
                        expressions.append(exp_name)
                    if not expressions:
                        # Alt: check motions
                        mot_dir = model_dir / "motions"
                        if mot_dir.exists():
                            for mot_sub in mot_dir.iterdir():
                                if mot_sub.is_dir():
                                    expressions.append(mot_sub.name)

                # Check optional features
                has_physics = (model_dir / f"{model_dir.name}.physics3.json").exists()
                has_poses = (model_dir / f"{model_dir.name}.pose3.json").exists()
                file_count = len(list(model_dir.rglob("*")))

                preview = None
                for ext in (".png", ".jpg"):
                    for pattern in (f"texture_00{ext}", f"{model_dir.name}_preview{ext}"):
                        p = model_dir / pattern
                        if p.exists():
                            preview = str(p)
                            break
                    if preview:
                        break

                # Get mtime for installed_at
                mtime = model_dir.stat().st_mtime
                installed_at = datetime.fromtimestamp(mtime)

                models.append({
                    "id": model_dir.name,
                    "name": name,
                    "version": version,
                    "author": data.get("Author", ""),
                    "description": data.get("Description", ""),
                    "preview_image": preview,
                    "installed_at": installed_at,
                    "file_count": file_count,
                    "has_physics": has_physics,
                    "has_poses": has_poses,
                    "expressions": sorted(set(expressions)),
                })
            except Exception as exc:
                logger.warning("Skipping model dir %s: %s", model_dir.name, exc)

        return models

    def get_model_info(self, model_id: str) -> dict | None:
        """Get information for a specific model."""
        for model in self.list_installed_models():
            if model["id"] == model_id:
                return model
        return None

    def get_model_path(self, model_id: str) -> Path:
        """Get the path to a model directory."""
        return self.get_models_dir() / model_id

    def delete_model(self, model_id: str) -> bool:
        """Delete an installed Live2D model."""
        import shutil

        model_dir = self.get_models_dir() / model_id
        if not model_dir.exists():
            return False
        try:
            shutil.rmtree(model_dir)
            logger.info("Deleted Live2D model: %s", model_id)
            return True
        except Exception as exc:
            logger.error("Failed to delete model %s: %s", model_id, exc)
            return False

    def get_model_expressions(self, model_id: str) -> list[dict]:
        """Get expressions for a specific model with parameter values."""
        model_dir = self.get_models_dir() / model_id
        if not model_dir.exists():
            return []

        import json

        expressions = []
        exp_dir = model_dir / "expressions"
        if exp_dir.exists():
            for exp_file in sorted(exp_dir.glob("*.exp3.json")):
                try:
                    data = json.loads(exp_file.read_text(encoding="utf-8"))
                    exp_id = exp_file.stem.replace(".exp3", "")
                    params = {}
                    for param in data.get("Parameters", []):
                        params[param.get("Id", "")] = param.get("Value", 0.0)
                    expressions.append({
                        "id": exp_id,
                        "name": data.get("Name", exp_id),
                        "parameters": params,
                    })
                except Exception as exc:
                    logger.warning("Failed to parse expression %s: %s", exp_file, exc)

        return expressions

    # ── lip-sync analysis ────────────────────────────────────────────

    async def analyze_audio(
        self,
        audio_path: str,
        sample_rate: int = 22050,
        frame_rate: int = 30,
        sensitivity: float = 1.0,
        include_visemes: bool = False,
    ) -> dict:
        """
        Analyze an audio file for lip-sync.

        Produces a frame-by-frame breakdown of mouth parameters.

        Args:
            audio_path: Path to audio file
            sample_rate: Target sample rate for analysis
            frame_rate: Frames per second for output
            sensitivity: Multiplier for mouth openness
            include_visemes: Include viseme/phoneme labels

        Returns:
            Dict with 'frames' list and 'duration_ms', 'frame_count', etc.
        """
        import asyncio

        loop = asyncio.get_event_loop()

        def _analyze():
            import soundfile as sf

            audio, sr = sf.read(audio_path, dtype="float32")
            if audio.ndim > 1:
                audio = audio.mean(axis=1)

            duration_ms = int(len(audio) / sr * 1000)
            hop_samples = sr // frame_rate
            n_frames = max(1, len(audio) // hop_samples)

            frames = []
            for i in range(n_frames):
                start = i * hop_samples
                end = min(start + hop_samples, len(audio))
                chunk = audio[start:end]

                # RMS energy
                rms = float(np.sqrt(np.mean(chunk ** 2))) if len(chunk) > 0 else 0.0

                # Mouth openness derived from RMS
                # Scale RMS to 0-1 range with sensitivity
                mouth_open_raw = min(1.0, rms * 8.0 * sensitivity)
                # Smooth: mouth_open rarely stays at 0 even in silence
                mouth_open = max(0.02, mouth_open_raw)

                # Mouth width: correlates with frequency distribution
                mouth_width = self._estimate_mouth_width(chunk, sr)

                # Volume: RMS in dB-like scale
                volume = math.log10(max(rms, 1e-10)) + 5
                volume = max(0.0, volume / 5.0)

                frame = {
                    "timestamp_ms": i * 1000 // frame_rate,
                    "mouth_open": min(1.0, max(0.0, mouth_open)),
                    "mouth_width": min(1.0, max(0.0, mouth_width)),
                    "volume": min(1.0, max(0.0, volume)),
                }

                if include_visemes:
                    frame["viseme"] = self._detect_viseme(chunk, sr)

                frames.append(frame)

            return {
                "frames": frames,
                "duration_ms": duration_ms,
                "frame_count": n_frames,
                "sample_rate": sr,
                "frame_rate": frame_rate,
            }

        result = await loop.run_in_executor(None, _analyze)
        return result

    def analyze_audio_sync(
        self,
        audio_chunk: np.ndarray,
        sample_rate: int = 22050,
        sensitivity: float = 1.0,
    ) -> dict:
        """
        Synchronous analysis of a single audio chunk (for real-time use).

        Args:
            audio_chunk: numpy float32 audio data
            sample_rate: Sample rate of the chunk
            sensitivity: Sensitivity multiplier

        Returns:
            Dict with mouth_open, mouth_width, volume, viseme
        """
        rms = float(np.sqrt(np.mean(audio_chunk ** 2))) if len(audio_chunk) > 0 else 0.0

        mouth_open = min(1.0, max(0.02, rms * 8.0 * sensitivity))
        mouth_width = self._estimate_mouth_width(audio_chunk, sample_rate)
        volume = max(0.0, (math.log10(max(rms, 1e-10)) + 5) / 5.0)

        return {
            "mouth_open": min(1.0, mouth_open),
            "mouth_width": min(1.0, max(0.0, mouth_width)),
            "volume": min(1.0, max(0.0, volume)),
            "viseme": self._detect_viseme(audio_chunk, sample_rate),
        }

    def _estimate_mouth_width(self, audio: np.ndarray, sr: int) -> float:
        """Estimate mouth width from spectral centroid and spread."""
        if len(audio) < 64:
            return 0.5

        try:
            # Use FFT for spectral analysis
            fft = np.abs(np.fft.rfft(audio))
            freqs = np.fft.rfftfreq(len(audio), 1.0 / sr)

            if len(freqs) < 2 or fft.sum() < 1e-10:
                return 0.5

            # Spectral centroid
            centroid = np.sum(freqs * fft) / np.sum(fft)
            # Normalize: centroid ~500-2000Hz typical for voice
            # Higher centroid -> wider mouth (more high-frequency energy)
            width = (centroid - 200) / 2000
            return min(1.0, max(0.1, width))
        except Exception:
            return 0.5

    def _detect_viseme(self, audio: np.ndarray, sr: int) -> str:
        """Detect the most likely viseme from an audio chunk."""
        # Simplified: based on spectral shape
        # Low RMS -> silence/PBM (closed mouth)
        rms = float(np.sqrt(np.mean(audio ** 2))) if len(audio) > 0 else 0.0
        if rms < 0.005:
            return "PBM"

        try:
            fft = np.abs(np.fft.rfft(audio))
            freqs = np.fft.rfftfreq(len(audio), 1.0 / sr)

            if len(freqs) < 2 or fft.sum() < 1e-10:
                return "PBM"

            centroid = np.sum(freqs * fft) / np.sum(fft)

            if centroid < 300:
                return "PBM"
            elif centroid < 600:
                return "UH"
            elif centroid < 1000:
                return "AA"
            elif centroid < 1500:
                return "EH"
            elif centroid < 2200:
                return "IH"
            elif centroid < 3000:
                return "SZ"
            else:
                return "IY"
        except Exception:
            return "AA"

    def get_default_expressions(self) -> list[dict]:
        """Return the standard Live2D expression parameter presets."""
        return [
            {
                "id": "neutral",
                "name": "Neutral",
                "parameters": {
                    "ParamMouthOpenY": 0.5,
                    "ParamMouthForm": 0.5,
                    "ParamEyeLOpen": 1.0,
                    "ParamEyeROpen": 1.0,
                    "ParamBrowLY": 0.5,
                    "ParamBrowRY": 0.5,
                },
            },
            {
                "id": "happy",
                "name": "Happy",
                "parameters": {
                    "ParamMouthOpenY": 0.6,
                    "ParamMouthForm": 0.8,
                    "ParamEyeLOpen": 1.0,
                    "ParamEyeROpen": 1.0,
                    "ParamBrowLY": 0.8,
                    "ParamBrowRY": 0.8,
                },
            },
            {
                "id": "sad",
                "name": "Sad",
                "parameters": {
                    "ParamMouthOpenY": 0.2,
                    "ParamMouthForm": 0.3,
                    "ParamEyeLOpen": 0.6,
                    "ParamEyeROpen": 0.6,
                    "ParamBrowLY": 0.2,
                    "ParamBrowRY": 0.2,
                },
            },
            {
                "id": "surprised",
                "name": "Surprised",
                "parameters": {
                    "ParamMouthOpenY": 0.9,
                    "ParamMouthForm": 0.7,
                    "ParamEyeLOpen": 1.0,
                    "ParamEyeROpen": 1.0,
                    "ParamBrowLY": 1.0,
                    "ParamBrowRY": 1.0,
                },
            },
            {
                "id": "angry",
                "name": "Angry",
                "parameters": {
                    "ParamMouthOpenY": 0.4,
                    "ParamMouthForm": 0.2,
                    "ParamEyeLOpen": 0.8,
                    "ParamEyeROpen": 0.8,
                    "ParamBrowLY": 0.1,
                    "ParamBrowRY": 0.1,
                },
            },
        ]
