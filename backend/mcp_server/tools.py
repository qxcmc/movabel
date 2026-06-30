"""Movabel MCP tool implementations.

Thin wrappers over existing services/routes. Tools are registered with dotted
names (``movabel.speak`` etc.) so they look natural in agent logs —
the Python function name stays snake_case.
"""

from __future__ import annotations

import asyncio
import base64 as b64
import logging
import shutil
import tempfile
import uuid
from pathlib import Path
from typing import Any

from fastmcp import FastMCP

from .. import config, models
from ..database import get_db
from ..services import captures as captures_service
from ..services import history as history_service
from ..services import profiles as profiles_service
from . import events as mcp_events
from .context import current_client_id, request_is_loopback
from .resolve import resolve_profile


logger = logging.getLogger(__name__)

# Absolute-path transcribes are bounded to keep a bad client from
# asking us to ingest a 20 GB file.
MAX_TRANSCRIBE_BYTES = 200 * 1024 * 1024  # 200 MB


def register_tools(mcp: FastMCP) -> None:
    """Attach all Movabel tools to the given FastMCP instance."""

    # ── Existing tools ─────────────────────────────────────────────────

    @mcp.tool(
        name="movabel.speak",
        description=(
            "Speak text in a Movabel voice profile. Returns a generation id "
            "the caller can poll at /generate/{id}/status. Audio plays on the "
            "user's speakers and is saved to the Captures / History tab."
        ),
    )
    async def movabel_speak(
        text: str,
        profile: str | None = None,
        engine: str | None = None,
        personality: bool | None = None,
        language: str | None = None,
    ) -> dict[str, Any]:
        """Speak ``text`` in a voice profile.

        ``profile`` accepts a voice profile name (e.g. "Morgan") or id. If
        omitted, the server looks up the per-client binding for the calling
        MCP client, then falls back to the global default voice.

        ``personality`` only matters for profiles that have a personality
        prompt — when true, the text is first rewritten in character by the
        LLM before TTS. When omitted, the per-client binding's
        ``default_personality`` flag decides; when that is unset, the
        default is plain TTS.
        """
        from ..database.models import MCPClientBinding

        db = next(get_db())
        try:
            client_id = current_client_id.get()
            vp = resolve_profile(profile, client_id, db)
            if vp is None:
                raise ValueError(
                    "No voice profile resolved. Pass `profile=` with a "
                    "voice profile name or id, or set a default voice in "
                    "Movabel → Settings → MCP."
                )

            binding = None
            if client_id:
                binding = (
                    db.query(MCPClientBinding)
                    .filter(MCPClientBinding.client_id == client_id)
                    .first()
                )

            resolved_personality = personality
            if resolved_personality is None and binding is not None:
                resolved_personality = bool(binding.default_personality)

            resolved_engine = engine
            if resolved_engine is None and binding is not None:
                resolved_engine = binding.default_engine

            use_persona = bool(resolved_personality) and bool(vp.personality)
            return await _speak(
                profile_id=vp.id,
                profile_name=vp.name,
                text=text,
                engine=resolved_engine,
                language=language,
                personality=use_persona,
                db=db,
            )
        finally:
            db.close()

    @mcp.tool(
        name="movabel.transcribe",
        description=(
            "Transcribe an audio clip to text using Movabel's local Whisper. "
            "Pass exactly one of `audio_base64` (bytes as base64) or "
            "`audio_path` (absolute local file path — loopback callers only)."
        ),
    )
    async def movabel_transcribe(
        audio_base64: str | None = None,
        audio_path: str | None = None,
        language: str | None = None,
        model: str | None = None,
    ) -> dict[str, Any]:
        if bool(audio_base64) == bool(audio_path):
            raise ValueError(
                "Pass exactly one of `audio_base64` or `audio_path`."
            )

        if audio_path is not None:
            if not request_is_loopback():
                raise ValueError(
                    "`audio_path` is only available to loopback callers — "
                    "remote callers must use `audio_base64`."
                )
            path = Path(audio_path)
            if not path.is_absolute():
                raise ValueError("`audio_path` must be absolute.")
            if not path.is_file():
                raise ValueError(f"File not found: {audio_path}")
            if path.stat().st_size > MAX_TRANSCRIBE_BYTES:
                raise ValueError(
                    f"File exceeds {MAX_TRANSCRIBE_BYTES // (1024 * 1024)} MB limit."
                )
            return await _transcribe_file(path, language, model)

        try:
            raw = b64.b64decode(audio_base64, validate=True)
        except Exception as exc:
            raise ValueError(f"Invalid audio_base64: {exc}") from exc
        if len(raw) > MAX_TRANSCRIBE_BYTES:
            raise ValueError(
                f"Audio exceeds {MAX_TRANSCRIBE_BYTES // (1024 * 1024)} MB limit."
            )
        with tempfile.NamedTemporaryFile(
            suffix=".wav", delete=False
        ) as tmp:
            tmp.write(raw)
            tmp_path = Path(tmp.name)
        try:
            return await _transcribe_file(tmp_path, language, model)
        finally:
            tmp_path.unlink(missing_ok=True)

    @mcp.tool(
        name="movabel.list_captures",
        description=(
            "List recent voice captures (dictations, recordings, uploads) "
            "with their transcripts. Most-recent first."
        ),
    )
    async def movabel_list_captures(
        limit: int = 20, offset: int = 0
    ) -> dict[str, Any]:
        if not (1 <= limit <= 200):
            raise ValueError("`limit` must be between 1 and 200.")
        if offset < 0:
            raise ValueError("`offset` must be >= 0.")
        db = next(get_db())
        try:
            items, total = captures_service.list_captures(
                db, limit=limit, offset=offset
            )
            return {
                "captures": [
                    item.model_dump(mode="json") for item in items
                ],
                "total": total,
            }
        finally:
            db.close()

    @mcp.tool(
        name="movabel.list_profiles",
        description=(
            "List available voice profiles (both cloned voices and presets). "
            "Use the returned `name` with movabel.speak(profile=...)."
        ),
    )
    async def movabel_list_profiles() -> dict[str, Any]:
        db = next(get_db())
        try:
            profiles = await profiles_service.list_profiles(db)
            return {
                "profiles": [
                    {
                        "id": p.id,
                        "name": p.name,
                        "voice_type": p.voice_type,
                        "language": p.language,
                        "has_personality": bool(getattr(p, "personality", None)),
                    }
                    for p in profiles
                ]
            }
        finally:
            db.close()

    # ── New tools (Phase 1) ────────────────────────────────────────────

    @mcp.tool(
        name="movabel.generate_batch",
        description=(
            "Submit a batch of texts for voice generation. Each item can "
            "specify its own profile, engine, and language. Returns a batch "
            "id for polling status via movabel.batch_status."
        ),
    )
    async def movabel_generate_batch(
        items: list[dict[str, Any]],
        engine: str | None = None,
        language: str | None = None,
    ) -> dict[str, Any]:
        """Submit multiple texts for sequential generation.

        Each item in ``items`` is a dict with keys:
          - ``text`` (required): The text to speak
          - ``profile`` (optional): Voice profile name or id
          - ``engine`` (optional): Per-item engine override
          - ``language`` (optional): Per-item language override
          - ``personality`` (optional): Whether to use personality rewrite

        ``engine`` and ``language`` serve as batch-wide defaults for items
        that do not specify their own.
        """
        if not items:
            raise ValueError("`items` must be a non-empty list.")
        if len(items) > 500:
            raise ValueError("Batch size must not exceed 500 items.")

        from ..database.models import MCPClientBinding
        from ..routes.generations import generate_speech

        db = next(get_db())
        batch_id = str(uuid.uuid4())
        client_id = current_client_id.get()

        try:
            binding = None
            if client_id:
                binding = (
                    db.query(MCPClientBinding)
                    .filter(MCPClientBinding.client_id == client_id)
                    .first()
                )

            generation_ids: list[str] = []
            for idx, item in enumerate(items):
                text = item.get("text")
                if not text or not isinstance(text, str):
                    raise ValueError(
                        f"Item {idx}: 'text' is required and must be a non-empty string."
                    )

                profile_ref = item.get("profile")
                vp = resolve_profile(profile_ref, client_id, db)
                if vp is None:
                    raise ValueError(
                        f"Item {idx}: No voice profile resolved. "
                        "Pass 'profile' with a voice profile name or id."
                    )

                item_engine = item.get("engine") or engine
                item_engine = item_engine or (
                    binding.default_engine if binding else None
                )

                item_personality = item.get("personality")
                if item_personality is None and binding is not None:
                    item_personality = bool(binding.default_personality)
                use_persona = bool(item_personality) and bool(vp.personality)

                item_language = item.get("language") or language or "en"

                req = models.GenerationRequest(
                    profile_id=vp.id,
                    text=text,
                    language=item_language,
                    engine=item_engine,
                    personality=use_persona,
                )
                generation = await generate_speech(req, db)
                generation_ids.append(generation.id)

            from ..database.models import BatchJob as DBBatchJob

            batch = DBBatchJob(
                id=batch_id,
                total=len(items),
                generation_ids=",".join(generation_ids),
                status="processing",
            )
            db.add(batch)
            db.commit()

            return {
                "batch_id": batch_id,
                "total": len(items),
                "generation_ids": generation_ids,
                "poll_url": f"/batch/{batch_id}/status",
            }
        finally:
            db.close()

    @mcp.tool(
        name="movabel.batch_status",
        description=(
            "Poll the status of a batch generation job submitted via "
            "movabel.generate_batch. Returns per-generation progress."
        ),
    )
    async def movabel_batch_status(
        batch_id: str,
    ) -> dict[str, Any]:
        """Get the current status of a batch generation job."""
        from ..database.models import BatchJob as DBBatchJob
        from ..database.models import Generation as DBGeneration

        db = next(get_db())
        try:
            batch = db.query(DBBatchJob).filter_by(id=batch_id).first()
            if not batch:
                raise ValueError(f"Batch job not found: {batch_id}")

            gen_ids = batch.generation_ids.split(",") if batch.generation_ids else []
            generations = (
                db.query(DBGeneration)
                .filter(DBGeneration.id.in_(gen_ids))
                .all()
            )
            gen_map = {g.id: g for g in generations}

            items_status = []
            completed = 0
            failed = 0
            for gid in gen_ids:
                g = gen_map.get(gid)
                if g is None:
                    items_status.append({"generation_id": gid, "status": "unknown"})
                    continue
                st = g.status or "completed"
                if st == "completed":
                    completed += 1
                elif st == "failed":
                    failed += 1
                items_status.append({
                    "generation_id": gid,
                    "status": st,
                    "duration": g.duration,
                    "error": g.error,
                    "poll_url": f"/generate/{gid}/status",
                })

            if completed + failed == len(gen_ids):
                batch.status = "done"
                db.commit()

            return {
                "batch_id": batch_id,
                "status": batch.status,
                "total": batch.total,
                "completed": completed,
                "failed": failed,
                "items": items_status,
            }
        finally:
            db.close()

    @mcp.tool(
        name="movabel.list_models",
        description=(
            "List available TTS, STT, and LLM models with their download "
            "and load status. Use to discover which engines are ready for use."
        ),
    )
    async def movabel_list_models(
        category: str | None = None,
    ) -> dict[str, Any]:
        """List all available models.

        ``category`` filters by type: ``"tts"``, ``"stt"``, ``"llm"``, or
        ``None`` for all.
        """
        from ..backends import (
            get_all_model_configs,
            get_tts_model_configs,
            get_stt_model_configs,
            get_llm_model_configs,
        )
        from ..backends import check_model_loaded

        configs: list = []
        if category == "tts":
            configs = get_tts_model_configs()
        elif category == "stt":
            configs = get_stt_model_configs()
        elif category == "llm":
            configs = get_llm_model_configs()
        else:
            configs = get_all_model_configs()

        models_list = []
        for cfg in configs:
            loaded = check_model_loaded(cfg)
            models_list.append({
                "model_name": cfg.model_name,
                "display_name": cfg.display_name,
                "engine": cfg.engine,
                "category": (
                    "tts" if cfg.engine != "whisper" and cfg.engine != "qwen_llm"
                    else "stt" if cfg.engine == "whisper"
                    else "llm"
                ),
                "size_mb": cfg.size_mb,
                "languages": cfg.languages,
                "loaded": loaded,
                "supports_instruct": cfg.supports_instruct,
                "hf_repo_id": cfg.hf_repo_id,
            })

        return {"models": models_list, "total": len(models_list)}

    @mcp.tool(
        name="movabel.profile_status",
        description=(
            "Get detailed status information for one or all voice profiles. "
            "Includes sample counts, generation history, and engine compatibility."
        ),
    )
    async def movabel_profile_status(
        profile: str | None = None,
    ) -> dict[str, Any]:
        """Get detailed status for voice profiles.

        ``profile`` accepts a profile name or id. If omitted, returns status
        for all profiles.
        """
        db = next(get_db())
        try:
            client_id = current_client_id.get()
            from ..database.models import (
                VoiceProfile as DBVoiceProfile,
                ProfileSample as DBProfileSample,
                Generation as DBGeneration,
            )

            if profile:
                vp = resolve_profile(profile, client_id, db)
                if vp is None:
                    raise ValueError(f"Profile not found: {profile}")
                target_profiles = [vp]
            else:
                target_profiles = await profiles_service.list_profiles(db)

            results = []
            for vp in target_profiles:
                sample_count = (
                    db.query(DBProfileSample)
                    .filter_by(profile_id=vp.id)
                    .count()
                )
                generation_count = (
                    db.query(DBGeneration)
                    .filter_by(profile_id=vp.id)
                    .count()
                )
                last_gen = (
                    db.query(DBGeneration)
                    .filter_by(profile_id=vp.id)
                    .order_by(DBGeneration.created_at.desc())
                    .first()
                )

                results.append({
                    "id": vp.id,
                    "name": vp.name,
                    "voice_type": vp.voice_type,
                    "language": vp.language,
                    "description": getattr(vp, "description", None),
                    "has_personality": bool(getattr(vp, "personality", None)),
                    "default_engine": getattr(vp, "default_engine", None),
                    "sample_count": sample_count,
                    "generation_count": generation_count,
                    "last_generation_at": (
                        last_gen.created_at.isoformat() if last_gen else None
                    ),
                    "created_at": vp.created_at.isoformat(),
                    "updated_at": vp.updated_at.isoformat(),
                })

            return {"profiles": results, "total": len(results)}
        finally:
            db.close()

    @mcp.tool(
        name="movabel.export_audio",
        description=(
            "Export a generation's audio file to a specified destination path. "
            "The generation must be completed. Destination must be an absolute "
            "path (loopback callers only for security)."
        ),
    )
    async def movabel_export_audio(
        generation_id: str,
        destination: str,
        format: str | None = None,
    ) -> dict[str, Any]:
        """Export a generation's audio to a filesystem location.

        ``generation_id`` — ID returned by movabel.speak or
        movabel.generate_batch.

        ``destination`` — Absolute destination path. Only available to
        loopback callers. If the path points to an existing directory,
        the file is placed inside it with the original filename.

        ``format`` — Output format: ``"wav"`` (default) or ``"mp3"``.
        """
        if not request_is_loopback():
            raise ValueError(
                "`export_audio` is only available to loopback callers."
            )
        dest = Path(destination)
        if not dest.is_absolute():
            raise ValueError("`destination` must be an absolute path.")

        from ..database.models import Generation as DBGeneration

        db = next(get_db())
        try:
            gen = db.query(DBGeneration).filter_by(id=generation_id).first()
            if not gen:
                raise ValueError(f"Generation not found: {generation_id}")
            if (gen.status or "completed") != "completed":
                raise ValueError(
                    f"Generation {generation_id} is not completed (status: {gen.status})."
                )

            src_path = config.resolve_storage_path(gen.audio_path)
            if src_path is None or not src_path.exists():
                raise ValueError(
                    f"Audio file missing for generation {generation_id}."
                )

            if dest.is_dir():
                dest = dest / src_path.name

            if format and format.lower() == "mp3":
                _convert_to_mp3(str(src_path), str(dest))
            else:
                shutil.copy2(str(src_path), str(dest))

            return {
                "generation_id": generation_id,
                "source": str(src_path),
                "destination": str(dest),
                "format": format or "wav",
                "size_bytes": dest.stat().st_size,
            }
        finally:
            db.close()

    @mcp.tool(
        name="movabel.system_status",
        description=(
            "Get Movabel system status including loaded models, GPU info, "
            "disk space, active tasks, and server health."
        ),
    )
    async def movabel_system_status() -> dict[str, Any]:
        """Return comprehensive system and server status."""
        from ..backends import (
            get_tts_backend_for_engine,
            get_stt_backend,
            get_llm_backend,
            TTS_ENGINES,
        )
        from ..backends import check_model_loaded, get_tts_model_configs
        from ..services import tts as tts_service
        from ..services import transcribe as transcribe_service
        from ..utils.tasks import get_task_manager
        from ..utils.platform_detect import get_backend_type

        task_manager = get_task_manager()
        active = task_manager.get_active()
        backend_type = get_backend_type()

        # GPU info
        gpu_available = False
        gpu_type = None
        vram_mb = None
        try:
            import torch
            if torch.cuda.is_available():
                gpu_available = True
                gpu_type = "CUDA"
                vram_mb = torch.cuda.get_device_properties(0).total_mem / (1024 * 1024)
            elif hasattr(torch.backends, "mps") and torch.backends.mps.is_available():
                gpu_available = True
                gpu_type = "MPS"
        except Exception:
            pass

        # Disk info
        data_dir = config.get_data_dir()
        try:
            usage = shutil.disk_usage(str(data_dir))
            disk_free_mb = usage.free / (1024 * 1024)
            disk_total_mb = usage.total / (1024 * 1024)
        except Exception:
            disk_free_mb = None
            disk_total_mb = None

        # Loaded models
        loaded_models: list[dict[str, Any]] = []
        for cfg in get_tts_model_configs():
            if check_model_loaded(cfg):
                loaded_models.append({
                    "model_name": cfg.model_name,
                    "engine": cfg.engine,
                    "display_name": cfg.display_name,
                })
        whisper = transcribe_service.get_whisper_model()
        if whisper.is_loaded():
            loaded_models.append({
                "model_name": f"whisper-{whisper.model_size}",
                "engine": "whisper",
                "display_name": f"Whisper {whisper.model_size.title()}",
            })

        # Active tasks
        active_tasks = []
        for gen_id in active.get("generations", []):
            active_tasks.append({"type": "generation", "id": gen_id})
        for dl in active.get("downloads", []):
            active_tasks.append({
                "type": "download",
                "model": dl.get("model_name", "unknown"),
                "progress": dl.get("progress"),
            })

        return {
            "backend_type": backend_type,
            "gpu_available": gpu_available,
            "gpu_type": gpu_type,
            "vram_mb": vram_mb,
            "disk_free_mb": disk_free_mb,
            "disk_total_mb": disk_total_mb,
            "data_dir": str(data_dir),
            "loaded_models": loaded_models,
            "active_tasks": active_tasks,
            "active_task_count": len(active_tasks),
            "supported_engines": list(TTS_ENGINES.keys()),
        }

    @mcp.tool(
        name="movabel.list_voices",
        description=(
            "List all available voice profiles with full metadata including "
            "engine compatibility, generated audio count, and last used date. "
            "More detailed than list_profiles — use this when you need to "
            "assess voice availability for batch or multi-voice projects."
        ),
    )
    async def movabel_list_voices(
        voice_type: str | None = None,
        language: str | None = None,
    ) -> dict[str, Any]:
        """List voices with optional filtering.

        ``voice_type`` — Filter by type: ``"cloned"``, ``"preset"``, or
        ``"designed"``.

        ``language`` — Filter by language code (e.g. ``"en"``, ``"zh"``).
        """
        db = next(get_db())
        try:
            all_profiles = await profiles_service.list_profiles(db)

            from ..database.models import (
                ProfileSample as DBProfileSample,
                Generation as DBGeneration,
            )

            filtered = all_profiles
            if voice_type:
                filtered = [p for p in filtered if p.voice_type == voice_type]
            if language:
                filtered = [p for p in filtered if p.language == language]

            voices = []
            for vp in filtered:
                sample_count = (
                    db.query(DBProfileSample)
                    .filter_by(profile_id=vp.id)
                    .count()
                )
                gen_count = (
                    db.query(DBGeneration)
                    .filter_by(profile_id=vp.id)
                    .count()
                )
                # Determine compatible engines
                from ..backends import TTS_ENGINES
                compatible_engines = list(TTS_ENGINES.keys())
                # Preset voices tied to specific engines
                preset_engine = getattr(vp, "preset_engine", None)
                if preset_engine:
                    compatible_engines = [preset_engine]

                voices.append({
                    "id": vp.id,
                    "name": vp.name,
                    "voice_type": vp.voice_type,
                    "language": vp.language,
                    "description": getattr(vp, "description", None),
                    "has_personality": bool(getattr(vp, "personality", None)),
                    "default_engine": getattr(vp, "default_engine", None),
                    "compatible_engines": compatible_engines,
                    "sample_count": sample_count,
                    "generation_count": gen_count,
                    "created_at": vp.created_at.isoformat(),
                })

            return {"voices": voices, "total": len(voices)}
        finally:
            db.close()


# ─── Helpers ────────────────────────────────────────────────────────────


async def _speak(
    *,
    profile_id: str,
    profile_name: str,
    text: str,
    engine: str | None,
    language: str | None,
    personality: bool,
    db,
) -> dict[str, Any]:
    """Delegate to POST /generate — the route handles personality-rewrite
    internally when ``personality=true`` and the profile has a prompt."""
    from ..routes.generations import generate_speech

    req = models.GenerationRequest(
        profile_id=profile_id,
        text=text,
        language=language or "en",
        engine=engine,
        personality=personality,
    )
    generation = await generate_speech(req, db)
    return _speak_response(generation, profile_name, source="mcp")


def _speak_response(
    generation, profile_name: str, *, source: str
) -> dict[str, Any]:
    """Normalize a GenerationResponse into the MCP tool's return shape.

    Also fires a speak-start event so the DictateWindow pill surfaces
    the agent's speech. Speak-end is fired from run_generation's
    completion hook.
    """
    payload = generation.model_dump(mode="json") if hasattr(
        generation, "model_dump"
    ) else dict(generation)
    generation_id = payload.get("id")
    mcp_events.publish(
        "speak-start",
        {
            "generation_id": generation_id,
            "profile_name": profile_name,
            "source": source,
            "client_id": current_client_id.get(),
        },
    )
    return {
        "generation_id": generation_id,
        "status": payload.get("status"),
        "profile": profile_name,
        "source": source,
        "poll_url": f"/generate/{generation_id}/status"
        if generation_id
        else None,
    }


async def _transcribe_file(
    path: Path, language: str | None, model: str | None
) -> dict[str, Any]:
    from ..backends import WHISPER_HF_REPOS
    from ..services import transcribe as transcribe_service
    from ..utils.audio import load_audio

    whisper = transcribe_service.get_whisper_model()
    model_size = model or whisper.model_size
    valid = list(WHISPER_HF_REPOS.keys())
    if model_size not in valid:
        raise ValueError(
            f"Invalid STT model '{model_size}'. Must be one of: {', '.join(valid)}"
        )

    audio, sr = await asyncio.to_thread(load_audio, str(path))
    duration = len(audio) / sr

    if (
        not whisper.is_loaded() or whisper.model_size != model_size
    ) and not whisper._is_model_cached(model_size):
        raise ValueError(
            f"Whisper model '{model_size}' is not yet downloaded. Open "
            "Movabel → Settings → Models to download it first."
        )

    text = await whisper.transcribe(str(path), language, model_size)
    return {
        "text": text,
        "duration": duration,
        "language": language,
        "model": model_size,
    }


def _convert_to_mp3(src: str, dst: str) -> None:
    """Convert a WAV file to MP3 using pydub."""
    try:
        from pydub import AudioSegment
        audio = AudioSegment.from_wav(src)
        audio.export(dst, format="mp3", bitrate="192k")
    except ImportError:
        import subprocess
        subprocess.run(
            ["ffmpeg", "-y", "-i", src, "-b:a", "192k", dst],
            check=True, capture_output=True,
        )
