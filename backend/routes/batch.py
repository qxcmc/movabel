"""
Batch generation routes.

POST /batch/generate — submit a batch of texts for sequential TTS generation.
GET  /batch/{batch_id}/status — poll batch progress.
"""

from __future__ import annotations

import uuid
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from .. import models
from ..database import get_db
from ..database.models import BatchJob as DBBatchJob, Generation as DBGeneration
from .generations import generate_speech

router = APIRouter(prefix="/batch", tags=["batch"])


@router.post("/generate", response_model=models.BatchGenerationResponse)
async def generate_batch(
    req: models.BatchGenerateRequest,
    db: Session = Depends(get_db),
):
    """Submit a batch of texts for sequential voice generation.

    Each item in the batch is processed independently via the existing
    /generate pipeline (personality rewrite, TTS, effects). The returned
    batch_id can be polled via GET /batch/{batch_id}/status.
    """
    if not req.items:
        raise HTTPException(status_code=400, detail="Batch items list cannot be empty.")
    if len(req.items) > 500:
        raise HTTPException(
            status_code=400,
            detail="Batch size must not exceed 500 items.",
        )

    batch_id = str(uuid.uuid4())
    generation_ids: list[str] = []

    for idx, item in enumerate(req.items):
        if not item.text or not isinstance(item.text, str) or not item.text.strip():
            raise HTTPException(
                status_code=400,
                detail=f"Item {idx}: 'text' is required and must be a non-empty string.",
            )

        item_engine = item.engine or req.engine
        item_language = item.language or req.language or "en"

        gen_req = models.GenerationRequest(
            profile_id="",  # Will be resolved inside generate_speech from the route context
            text=item.text,
            language=item_language,
            engine=item_engine,
            personality=item.personality,
            instruct=item.instruct,
            effects_chain=item.effects_chain,
        )

        # The batch route needs to resolve profiles by name/id.
        # For now, items must provide a valid profile_id.
        # If a profile name was given, resolve it through the profiles service.
        if item.profile:
            from ..services.profiles import get_profile_by_name_or_id
            profile = get_profile_by_name_or_id(item.profile, db)
            if profile is None:
                raise HTTPException(
                    status_code=404,
                    detail=f"Item {idx}: Profile not found: {item.profile}",
                )
            gen_req.profile_id = profile.id
        else:
            raise HTTPException(
                status_code=400,
                detail=f"Item {idx}: 'profile' is required for batch generation.",
            )

        generation = await generate_speech(gen_req, db)
        generation_ids.append(generation.id)

    batch = DBBatchJob(
        id=batch_id,
        total=len(req.items),
        generation_ids=",".join(generation_ids),
        status="processing",
    )
    db.add(batch)
    db.commit()

    return models.BatchGenerationResponse(
        batch_id=batch_id,
        total=len(req.items),
        generation_ids=generation_ids,
        status="processing",
    )


@router.get("/{batch_id}/status", response_model=models.BatchGenerationStatusResponse)
async def get_batch_status(
    batch_id: str,
    db: Session = Depends(get_db),
):
    """Poll the status of a batch generation job."""
    batch = db.query(DBBatchJob).filter_by(id=batch_id).first()
    if not batch:
        raise HTTPException(status_code=404, detail="Batch job not found.")

    gen_ids = batch.generation_ids.split(",") if batch.generation_ids else []
    generations = (
        db.query(DBGeneration)
        .filter(DBGeneration.id.in_(gen_ids))
        .all()
    )
    gen_map = {g.id: g for g in generations}

    items_status: list[models.BatchGenerationItemStatus] = []
    completed = 0
    failed = 0

    for gid in gen_ids:
        g = gen_map.get(gid)
        if g is None:
            items_status.append(
                models.BatchGenerationItemStatus(
                    generation_id=gid,
                    status="unknown",
                )
            )
            continue
        st = g.status or "completed"
        if st == "completed":
            completed += 1
        elif st == "failed":
            failed += 1
        items_status.append(
            models.BatchGenerationItemStatus(
                generation_id=gid,
                status=st,
                duration=g.duration,
                error=g.error,
                poll_url=f"/generate/{gid}/status",
            )
        )

    # Auto-transition batch status
    if completed + failed == len(gen_ids):
        if batch.status != "done":
            batch.status = "done"
            db.commit()

    return models.BatchGenerationStatusResponse(
        batch_id=batch_id,
        status=batch.status,
        total=batch.total,
        completed=completed,
        failed=failed,
        items=items_status,
    )
