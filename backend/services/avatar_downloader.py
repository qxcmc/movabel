"""
Live2D model downloader — provides access to free official sample models.

Lists available free models from the Live2D official CDN, downloads
and extracts them into the Movabel models directory.
"""

from __future__ import annotations

import logging
import shutil
import zipfile
from pathlib import Path
from typing import Optional

import httpx

from .. import config

logger = logging.getLogger(__name__)

# Free Live2D sample models available for download
# These are the official Cubism SDK samples distributed under the Live2D Free Material License.
FREE_MODELS: list[dict] = [
    {
        "id": "haru",
        "name": "Haru",
        "description": "Official Live2D sample model — cheerful female character",
        "author": "Live2D Inc.",
        "url": "https://cdn.live2d.com/cubism/samples/SampleModel1.zip",
        "version": "4.0",
        "size_mb": 5,
        "expressions": ["neutral", "happy", "sad", "surprised", "angry"],
        "tags": ["female", "casual", "sample"],
    },
    {
        "id": "hiyori",
        "name": "Hiyori",
        "description": "Official Live2D sample model — gentle female character",
        "author": "Live2D Inc.",
        "url": "https://cdn.live2d.com/cubism/samples/SampleModel2.zip",
        "version": "4.0",
        "size_mb": 4,
        "expressions": ["neutral", "happy", "sad", "surprised"],
        "tags": ["female", "school", "sample"],
    },
    {
        "id": "mark",
        "name": "Mark",
        "description": "Official Live2D sample model — male character",
        "author": "Live2D Inc.",
        "url": "https://cdn.live2d.com/cubism/samples/SampleModel3.zip",
        "version": "4.0",
        "size_mb": 4,
        "expressions": ["neutral", "happy", "sad", "surprised"],
        "tags": ["male", "casual", "sample"],
    },
    {
        "id": "natori",
        "name": "Natori",
        "description": "Official Live2D sample model — elegant female character",
        "author": "Live2D Inc.",
        "url": "https://cdn.live2d.com/cubism/samples/SampleModel4.zip",
        "version": "4.0",
        "size_mb": 5,
        "expressions": ["neutral", "happy", "sad", "surprised", "angry"],
        "tags": ["female", "kimono", "sample"],
    },
    {
        "id": "rice",
        "name": "Rice",
        "description": "Official Live2D sample model — animal mascot character",
        "author": "Live2D Inc.",
        "url": "https://cdn.live2d.com/cubism/samples/SampleModel5.zip",
        "version": "4.0",
        "size_mb": 3,
        "expressions": ["neutral", "happy", "sad"],
        "tags": ["animal", "mascot", "sample"],
    },
]


def list_free_models() -> list[dict]:
    """Return the list of free downloadable models."""
    return [dict(m) for m in FREE_MODELS]


def _models_base_dir() -> Path:
    d = config.get_data_dir() / "live2d_models"
    d.mkdir(parents=True, exist_ok=True)
    return d


def is_model_installed(model_id: str) -> bool:
    """Check if a free model is already installed."""
    target = _models_base_dir() / model_id
    return target.exists() and any(target.glob("*.model3.json"))


def download_model(model_id: str, timeout: int = 120) -> Path | None:
    """
    Download and extract a free Live2D model.

    Returns the path to the extracted model directory, or None on failure.
    """
    model_info = None
    for m in FREE_MODELS:
        if m["id"] == model_id:
            model_info = m
            break

    if model_info is None:
        logger.warning("Unknown free model ID: %s", model_id)
        return None

    target_dir = _models_base_dir() / model_id
    url = model_info["url"]

    # Download ZIP
    try:
        logger.info("Downloading Live2D model %s from %s", model_id, url)
        resp = httpx.get(url, timeout=timeout, follow_redirects=True)
        resp.raise_for_status()
    except Exception as exc:
        logger.error("Failed to download model %s: %s", model_id, exc)
        return None

    # Extract to target directory
    import tempfile

    with tempfile.NamedTemporaryFile(suffix=".zip", delete=False) as tmp:
        tmp.write(resp.content)
        tmp_path = tmp.name

    try:
        # Clear target if exists
        if target_dir.exists():
            shutil.rmtree(target_dir)
        target_dir.mkdir(parents=True)

        with zipfile.ZipFile(tmp_path, "r") as zf:
            # Check for nested single-directory structure
            members = zf.namelist()
            top_dirs = set()
            for name in members:
                parts = name.split("/")
                if parts[0]:
                    top_dirs.add(parts[0])

            if len(top_dirs) == 1 and not any(
                name.endswith(".model3.json") and "/" not in name
                for name in members
            ):
                # Nested: extract then flatten one level
                extract_dir = target_dir.parent / f"{model_id}_tmp"
                zf.extractall(extract_dir)
                inner_dir = extract_dir / list(top_dirs)[0]
                if inner_dir.is_dir():
                    for item in inner_dir.iterdir():
                        shutil.move(str(item), str(target_dir / item.name))
                shutil.rmtree(extract_dir)
            else:
                zf.extractall(target_dir)

        logger.info("Model %s extracted to %s", model_id, target_dir)
        return target_dir

    except Exception as exc:
        logger.error("Failed to extract model %s: %s", model_id, exc)
        if target_dir.exists():
            shutil.rmtree(target_dir)
        return None
    finally:
        Path(tmp_path).unlink(missing_ok=True)


def download_model_async(model_id: str) -> Path | None:
    """Synchronous wrapper for download_model (for use with run_in_executor)."""
    return download_model(model_id)


# ── convenience aliases for route layer ─────────────────────────────

AVAILABLE_MODELS: list[str] = [m["id"] for m in FREE_MODELS]


def download_and_install_model(model_id: str, target_dir: str) -> None:
    """
    Download and install a Live2D model to the target directory.

    Convenience wrapper for route layer.
    """
    result = download_model(model_id)
    if result is None:
        raise RuntimeError(f"Failed to download model: {model_id}")
    logger.info("Model %s installed to %s", model_id, result)
