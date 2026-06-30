"""
MusicGen backend — text-to-music generation via transformers.

Uses facebook/musicgen-small (300M parameters) for local music generation.
Supports CPU and GPU inference, outputs 32kHz WAV files.
"""

from __future__ import annotations

import logging
import tempfile
import uuid
from pathlib import Path
from typing import Optional

import numpy as np
import soundfile as sf
import torch

logger = logging.getLogger(__name__)

# Model repo IDs
MUSICGEN_MODELS = {
    "small": "facebook/musicgen-small",   # 300M, fastest, decent quality
    "medium": "facebook/musicgen-medium", # 1.5B, better quality
    "large": "facebook/musicgen-large",   # 3.3B, best quality
}

DEVICE = "cuda" if torch.cuda.is_available() else "cpu"
DTYPE = torch.float16 if torch.cuda.is_available() else torch.float32


class MusicGenBackend:
    """
    Wrapper around transformers MusicGen pipeline.

    Usage::

        backend = MusicGenBackend()
        await backend.load_model("small")
        audio = await backend.generate("upbeat electronic dance music", duration=30)
        sf.write("output.wav", audio, 32000)
    """

    def __init__(self):
        self.model_size: str = "small"
        self.pipeline = None
        self.processor = None
        self.model = None
        self._device = DEVICE

    @property
    def is_loaded(self) -> bool:
        return self.pipeline is not None or self.model is not None

    async def load_model(self, model_size: str = "small") -> None:
        """
        Load MusicGen model.

        Args:
            model_size: "small" (300M), "medium" (1.5B), or "large" (3.3B)
        """
        import asyncio

        self.model_size = model_size
        repo_id = MUSICGEN_MODELS.get(model_size, MUSICGEN_MODELS["small"])

        logger.info("Loading MusicGen model: %s on %s", repo_id, self._device)

        loop = asyncio.get_event_loop()

        def _load():
            try:
                from transformers import AutoProcessor, MusicgenForConditionalGeneration

                self.processor = AutoProcessor.from_pretrained(repo_id)
                self.model = MusicgenForConditionalGeneration.from_pretrained(
                    repo_id,
                    torch_dtype=DTYPE,
                ).to(self._device)
                logger.info("MusicGen %s loaded successfully", model_size)
            except Exception as exc:
                logger.error("Failed to load MusicGen %s: %s", model_size, exc)
                raise

        await loop.run_in_executor(None, _load)

    async def generate(
        self,
        prompt: str,
        duration: float = 30.0,
        temperature: float = 1.0,
        top_k: int = 250,
        guidance_scale: float = 3.0,
    ) -> np.ndarray:
        """
        Generate music from text prompt.

        Args:
            prompt: Text description of desired music
            duration: Target duration in seconds (max 300)
            temperature: Sampling temperature (0.1-3.0)
            top_k: Top-k sampling parameter
            guidance_scale: Classifier-free guidance scale

        Returns:
            numpy array of audio at 32kHz sample rate
        """
        import asyncio

        if not self.is_loaded:
            await self.load_model(self.model_size)

        loop = asyncio.get_event_loop()

        def _generate():
            # MusicGen generates fixed-length chunks; duration -> max_new_tokens
            # ~50 tokens per second of audio at 32kHz
            max_new_tokens = int(duration * 50)
            max_new_tokens = max(256, min(max_new_tokens, 15000))

            inputs = self.processor(
                text=[prompt],
                padding=True,
                return_tensors="pt",
            ).to(self._device)

            generation_kwargs = {
                "max_new_tokens": max_new_tokens,
                "do_sample": True,
                "temperature": temperature,
                "top_k": top_k,
                "guidance_scale": guidance_scale,
            }

            with torch.no_grad():
                audio_values = self.model.generate(**inputs, **generation_kwargs)

            # audio_values shape: (batch, num_channels, seq_len)
            audio = audio_values[0, 0].cpu().numpy()
            return audio

        audio = await loop.run_in_executor(None, _generate)
        return audio

    async def generate_to_file(
        self,
        prompt: str,
        output_path: str,
        duration: float = 30.0,
        temperature: float = 1.0,
        top_k: int = 250,
        guidance_scale: float = 3.0,
    ) -> str:
        """
        Generate music and save to WAV file.

        Returns:
            Path to the output WAV file
        """
        audio = await self.generate(
            prompt=prompt,
            duration=duration,
            temperature=temperature,
            top_k=top_k,
            guidance_scale=guidance_scale,
        )

        # MusicGen outputs 32kHz
        sf.write(output_path, audio, 32000)
        logger.info("Music saved to: %s (%.1fs)", output_path, len(audio) / 32000)
        return output_path

    def unload_model(self) -> None:
        """Unload model to free memory."""
        if self.model is not None:
            del self.model
            self.model = None
        if self.processor is not None:
            del self.processor
            self.processor = None
        if torch.cuda.is_available():
            torch.cuda.empty_cache()
        logger.info("MusicGen model unloaded")

    async def generate_batch(
        self,
        prompts: list[str],
        durations: list[float],
        output_dir: str,
    ) -> list[str]:
        """
        Generate multiple music tracks in batch.

        Args:
            prompts: List of text prompts
            durations: List of durations (must match prompts length)
            output_dir: Directory to save outputs

        Returns:
            List of output file paths
        """
        import asyncio

        output_dir_path = Path(output_dir)
        output_dir_path.mkdir(parents=True, exist_ok=True)

        results = []
        for i, (prompt, duration) in enumerate(zip(prompts, durations)):
            output_filename = f"music_{i:03d}_{uuid.uuid4().hex[:8]}.wav"
            output_path = str(output_dir_path / output_filename)
            try:
                result_path = await self.generate_to_file(
                    prompt=prompt,
                    output_path=output_path,
                    duration=duration,
                )
                results.append(result_path)
            except Exception as exc:
                logger.error("Failed to generate music for prompt %d: %s", i, exc)
                results.append(None)

        return results
